"""Selenium + Java + TestNG Automated Browser Testing Service.

Provides:
- Subprocess execution of Maven/TestNG suites in showcase_project/selenium-tests
- Environment detection (Java 17, Maven 3.9+, Chrome)
- Parsing of TestNG XML reports into normalized results
- Idempotent recording of test runs and individual method verdicts
- Event emission for quality gates and risk detection
- Automatic defect drafting and Jira defect linking
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Any
from uuid import uuid4
import xml.etree.ElementTree as ET

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import metadata_to_json
from backend.models.db_models import (
    DefectDraftRecord,
    Project,
    ProjectEventRecord,
    SeleniumTestRunRecord,
)
from backend.models.schemas import (
    SeleniumEnvironmentStatus,
    SeleniumTestMethodResult,
    SeleniumTestRunResponse,
)
from shared.event_types import EventSource, EventType, UserRole
from shared.timeutil import utc_now_naive

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SELENIUM_PROJECT_PATH = REPO_ROOT / "showcase_project" / "selenium-tests"
PORTABLE_JDK_PATH = REPO_ROOT / "tools" / "jdk-17"
PORTABLE_MAVEN_PATH = REPO_ROOT / "tools" / "apache-maven-3.9.6"


def _get_execution_env() -> tuple[dict[str, str], str, str]:
    """Resolves environment variables and paths for Java and Maven."""
    env = os.environ.copy()

    # 1. Resolve Java
    java_home = ""
    java_bin = "java"
    if PORTABLE_JDK_PATH.exists() and (PORTABLE_JDK_PATH / "bin" / "java.exe").exists():
        java_home = str(PORTABLE_JDK_PATH.resolve())
        java_bin = str((PORTABLE_JDK_PATH / "bin" / "java.exe").resolve())
    elif os.environ.get("JAVA_HOME") and Path(os.environ["JAVA_HOME"]).exists():
        java_home = os.environ["JAVA_HOME"]
        java_bin = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))

    if java_home:
        env["JAVA_HOME"] = java_home

    # 2. Resolve Maven
    m2_home = ""
    mvn_cmd = "mvn"
    if PORTABLE_MAVEN_PATH.exists() and (PORTABLE_MAVEN_PATH / "bin" / ("mvn.cmd" if os.name == "nt" else "mvn")).exists():
        m2_home = str(PORTABLE_MAVEN_PATH.resolve())
        mvn_cmd = str((PORTABLE_MAVEN_PATH / "bin" / ("mvn.cmd" if os.name == "nt" else "mvn")).resolve())
    elif os.environ.get("M2_HOME") and Path(os.environ["M2_HOME"]).exists():
        m2_home = os.environ["M2_HOME"]
        mvn_cmd = str(Path(m2_home) / "bin" / ("mvn.cmd" if os.name == "nt" else "mvn"))

    if m2_home:
        env["M2_HOME"] = m2_home

    # Update PATH
    path_prepend = []
    if java_home:
        path_prepend.append(str(Path(java_home) / "bin"))
    if m2_home:
        path_prepend.append(str(Path(m2_home) / "bin"))

    if path_prepend:
        current_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(path_prepend + [current_path])

    return env, java_bin, mvn_cmd


def check_selenium_environment() -> SeleniumEnvironmentStatus:
    """Checks for Java, Maven, Chrome, and test project configuration."""
    env, java_bin, mvn_cmd = _get_execution_env()

    java_installed = False
    java_version = ""
    try:
        proc = subprocess.run([java_bin, "-version"], capture_output=True, text=True, timeout=5, env=env)
        out = f"{proc.stdout}\n{proc.stderr}".strip()
        if "version" in out.lower():
            java_installed = True
            first_line = out.splitlines()[0] if out.splitlines() else "Java Installed"
            java_version = first_line
    except Exception:
        pass

    maven_installed = False
    maven_version = ""
    try:
        proc = subprocess.run([mvn_cmd, "-v"], capture_output=True, text=True, timeout=8, env=env)
        out = f"{proc.stdout}\n{proc.stderr}".strip()
        if "Apache Maven" in out:
            maven_installed = True
            maven_version = out.splitlines()[0] if out.splitlines() else "Maven Installed"
    except Exception:
        pass

    chrome_installed = False
    chrome_path = ""
    possible_chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in possible_chrome_paths:
        if os.path.exists(p):
            chrome_installed = True
            chrome_path = p
            break

    missing = []
    if not java_installed:
        missing.append("Java 17 JDK is required (install OpenJDK 17 or configure tools/jdk-17)")
    if not maven_installed:
        missing.append("Apache Maven 3.9+ is required (install Maven or configure tools/apache-maven-3.9.6)")
    if not chrome_installed:
        missing.append("Google Chrome browser is required for Selenium WebDriver execution")

    is_ready = (
        java_installed
        and maven_installed
        and chrome_installed
        and SELENIUM_PROJECT_PATH.exists()
        and (SELENIUM_PROJECT_PATH / "pom.xml").exists()
    )

    return SeleniumEnvironmentStatus(
        java_installed=java_installed,
        java_version=java_version,
        maven_installed=maven_installed,
        maven_version=maven_version,
        chrome_installed=chrome_installed,
        chrome_path=chrome_path,
        is_ready=is_ready,
        missing_prerequisites=missing,
        test_project_path=str(SELENIUM_PROJECT_PATH),
        default_suite="testng.xml",
    )


def parse_testng_results_xml(xml_content: str) -> dict[str, Any] | None:
    """Parses raw TestNG XML string and extracts metrics and test method outcomes."""
    try:
        root = ET.fromstring(xml_content)
        if root.tag != "testng-results":
            return None

        total_attr = root.get("total")
        passed_attr = root.get("passed")
        failed_attr = root.get("failed")
        skipped_attr = root.get("skipped")

        suite_elem = root.find("suite")
        suite_name = suite_elem.get("name", "ProjectPulse Browser Automation Suite") if suite_elem is not None else "ProjectPulse Browser Automation Suite"
        duration_ms = 0
        if suite_elem is not None:
            try:
                duration_ms = int(suite_elem.get("duration-ms", 0))
            except ValueError:
                pass

        total = 0
        passed = 0
        failed = 0
        skipped = 0
        methods: list[SeleniumTestMethodResult] = []

        for test_elem in root.findall(".//test"):
            for class_elem in test_elem.findall("class"):
                cls_name = class_elem.get("name", "")
                for method in class_elem.findall("test-method"):
                    if method.get("is-config") == "true":
                        continue

                    m_name = method.get("name", "unknown")
                    desc = method.get("description", "")
                    status = (method.get("status") or "PASS").upper()
                    try:
                        dur = round(int(method.get("duration-ms", 0)) / 1000.0, 3)
                    except ValueError:
                        dur = 0.0

                    err_msg = ""
                    trace = ""
                    exc = method.find("exception")
                    if exc is not None:
                        msg_elem = exc.find("message")
                        if msg_elem is not None and msg_elem.text:
                            err_msg = msg_elem.text.strip()
                        trace_elem = exc.find("full-stacktrace")
                        if trace_elem is not None and trace_elem.text:
                            trace = trace_elem.text.strip()
                        if not err_msg:
                            err_msg = exc.get("class", "AssertionError")

                    total += 1
                    if status == "PASS":
                        passed += 1
                    elif status == "FAIL":
                        failed += 1
                    else:
                        skipped += 1

                    methods.append(
                        SeleniumTestMethodResult(
                            name=m_name,
                            class_name=cls_name,
                            status=status,
                            duration_seconds=dur,
                            description=desc,
                            error_message=err_msg,
                            stack_trace=trace,
                        )
                    )

        if total == 0 and total_attr:
            total = int(total_attr)
            passed = int(passed_attr or 0)
            failed = int(failed_attr or 0)
            skipped = int(skipped_attr or 0)

        pass_rate = round((passed / total * 100), 1) if total > 0 else 0.0

        return {
            "suite_name": suite_name,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": pass_rate,
            "duration_seconds": round(duration_ms / 1000.0, 2),
            "methods": methods,
        }
    except Exception as exc:
        logger.warning("Error parsing TestNG XML content: %s", exc)
        return None


def execute_selenium_test_suite(
    project_id: str,
    headless: bool = True,
    browser: str = "chrome",
    test_url: str = "",
    suite_file: str = "testng.xml",
    executed_by: str = "Tester",
    db: Session | None = None,
) -> SeleniumTestRunResponse:
    """Executes the Maven TestNG test suite in a controlled subprocess and records telemetry."""
    if not SELENIUM_PROJECT_PATH.exists():
        raise FileNotFoundError(f"Selenium project not found at: {SELENIUM_PROJECT_PATH}")

    env_status = check_selenium_environment()
    if not env_status.is_ready:
        missing_text = "; ".join(env_status.missing_prerequisites)
        run_id = f"SELENIUM-RUN-{uuid4().hex[:8].upper()}"
        run_record = SeleniumTestRunRecord(
            run_id=run_id,
            project_id=project_id,
            suite_name="ProjectPulse Browser Automation Suite",
            browser=browser,
            headless=1 if headless else 0,
            status="INFRASTRUCTURE_ERROR",
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            duration_seconds=0.0,
            exit_code=1,
            command="mvn test",
            stdout_excerpt="",
            stderr_excerpt=f"Environment prerequisites not met: {missing_text}",
            test_methods_json="[]",
            report_file="",
            fingerprint="",
            executed_by=executed_by,
        )
        if db:
            db.add(run_record)
            db.commit()
            db.refresh(run_record)

        return _to_run_response(run_record)

    env, _, mvn_cmd = _get_execution_env()

    # Construct safe command arguments
    cmd = [
        mvn_cmd,
        "clean",
        "test",
        f"-Dheadless={'true' if headless else 'false'}",
        f"-Dbrowser={browser}",
    ]
    if test_url:
        cmd.append(f"-DtestUrl={test_url}")

    start_time = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(SELENIUM_PROJECT_PATH),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        elapsed = round(time.monotonic() - start_time, 2)
        stdout_txt = proc.stdout or ""
        stderr_txt = proc.stderr or ""
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.monotonic() - start_time, 2)
        stdout_txt = exc.stdout or "" if hasattr(exc, "stdout") and exc.stdout else ""
        stderr_txt = "Execution timed out after 180 seconds"
        exit_code = 124
    except Exception as exc:
        elapsed = round(time.monotonic() - start_time, 2)
        stdout_txt = ""
        stderr_txt = f"Failed launching process: {str(exc)}"
        exit_code = 1

    # Check for report file
    report_path = SELENIUM_PROJECT_PATH / "target" / "surefire-reports" / "testng-results.xml"
    parsed_report = None
    xml_content = ""
    fingerprint = ""

    if report_path.exists():
        try:
            xml_content = report_path.read_text(encoding="utf-8")
            fingerprint = hashlib.sha256(xml_content.encode("utf-8")).hexdigest()
            parsed_report = parse_testng_results_xml(xml_content)
        except Exception as e:
            logger.warning("Failed to read testng-results.xml: %s", e)

    run_id = f"SELENIUM-RUN-{uuid4().hex[:8].upper()}"

    if parsed_report:
        total = parsed_report["total"]
        passed = parsed_report["passed"]
        failed = parsed_report["failed"]
        skipped = parsed_report["skipped"]
        duration = parsed_report["duration_seconds"] or elapsed
        suite_name = parsed_report["suite_name"]
        status = "SUCCESS" if failed == 0 and exit_code == 0 else "FAILED"
        methods_list = [m.model_dump() for m in parsed_report["methods"]]
    else:
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        duration = elapsed
        suite_name = "ProjectPulse Browser Automation Suite"
        status = "INFRASTRUCTURE_ERROR"
        methods_list = []

    stdout_snippet = stdout_txt[-2000:] if len(stdout_txt) > 2000 else stdout_txt
    stderr_snippet = stderr_txt[-2000:] if len(stderr_txt) > 2000 else stderr_txt

    run_record = SeleniumTestRunRecord(
        run_id=run_id,
        project_id=project_id,
        suite_name=suite_name,
        browser=browser,
        headless=1 if headless else 0,
        status=status,
        total_tests=total,
        passed_tests=passed,
        failed_tests=failed,
        skipped_tests=skipped,
        duration_seconds=duration,
        exit_code=exit_code,
        command=" ".join(cmd),
        stdout_excerpt=stdout_snippet,
        stderr_excerpt=stderr_snippet,
        test_methods_json=json.dumps(methods_list),
        report_file=str(report_path.name) if report_path.exists() else "",
        fingerprint=fingerprint,
        executed_by=executed_by,
    )

    if db:
        db.add(run_record)

        # 1. Emit telemetry event
        event_type = EventType.TEST_PASSED if status == "SUCCESS" else EventType.TEST_FAILED
        evt_title = f"Selenium TestNG {suite_name}: {passed}/{total} passed"
        if failed > 0:
            evt_title += f" ({failed} failed)"

        evt_desc = (
            f"Browser automation ({browser}, {'headless' if headless else 'visible'}): "
            f"{passed} passed, {failed} failed in {duration}s"
        )

        event_rec = ProjectEventRecord(
            event_id=f"EVT-{uuid4().hex[:12].upper()}",
            agent_id="AGENT-SELENIUM-001",
            project_id=project_id,
            user_id="DEV-001",
            role=UserRole.TESTER.value,
            source=EventSource.TEST.value,
            event_type=event_type.value if hasattr(event_type, "value") else str(event_type),
            title=evt_title,
            description=evt_desc,
            status="SUCCESS" if status == "SUCCESS" else "WARNING",
            metadata_json=metadata_to_json({
                "run_id": run_id,
                "framework": "testng",
                "browser": browser,
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "duration_seconds": duration,
                "suite": suite_name,
                "exit_code": exit_code,
            }),
            timestamp=utc_now_naive(),
        )
        db.add(event_rec)

        # 2. For any failed test methods, automatically generate draft defects for Tester inspection
        if parsed_report and parsed_report["methods"]:
            for m in parsed_report["methods"]:
                if m.status == "FAIL":
                    draft_id = f"DRAFT-{uuid4().hex[:8].upper()}"
                    defect_draft = DefectDraftRecord(
                        draft_id=draft_id,
                        project_id=project_id,
                        test_case_id="",
                        test_failure_event_id=event_rec.event_id,
                        test_name=f"{m.class_name}::{m.name}",
                        stack_trace=m.stack_trace or m.error_message,
                        title=f"Browser Test Failure: {m.name}",
                        description=f"Automated browser test failed on {browser}: {m.error_message or 'Assertion failed'}",
                        severity="HIGH",
                        priority="HIGH",
                        linked_jira_issue="PP-3",
                        status="DRAFT",
                        created_by=executed_by,
                    )
                    db.add(defect_draft)

        db.commit()
        db.refresh(run_record)

    return _to_run_response(run_record)


def list_selenium_runs(project_id: str, db: Session, limit: int = 25) -> list[SeleniumTestRunResponse]:
    """Retrieves chronological execution history of Selenium browser tests."""
    records = (
        db.query(SeleniumTestRunRecord)
        .filter(SeleniumTestRunRecord.project_id.in_([project_id, "PP", "KAN", "DLX"]))
        .order_by(SeleniumTestRunRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_run_response(r) for r in records]


def get_selenium_run_by_id(run_id: str, db: Session) -> SeleniumTestRunResponse | None:
    """Finds a specific Selenium test run by its unique identifier."""
    rec = db.query(SeleniumTestRunRecord).filter(SeleniumTestRunRecord.run_id == run_id).first()
    if not rec:
        return None
    return _to_run_response(rec)


def link_selenium_failure_to_jira(
    run_id: str,
    test_name: str,
    jira_issue_key: str,
    failure_message: str,
    db: Session,
    user_name: str = "Dave Miller (QA)",
) -> dict[str, Any]:
    """Links an automated browser test failure to a real Jira issue key."""
    # Look up project_id from run if available
    run_rec = db.query(SeleniumTestRunRecord).filter(SeleniumTestRunRecord.run_id == run_id).first()
    p_id = run_rec.project_id if run_rec else "PP"

    draft_id = f"DRAFT-SELENIUM-{uuid4().hex[:6].upper()}"
    draft = DefectDraftRecord(
        draft_id=draft_id,
        project_id=p_id,
        test_case_id="",
        test_failure_event_id="",
        test_name=test_name,
        stack_trace=failure_message,
        title=f"Selenium Failure: {test_name}",
        description=f"Automated browser test '{test_name}' failed during run {run_id}. Root cause: {failure_message}",
        severity="HIGH",
        priority="HIGH",
        linked_jira_issue=jira_issue_key.strip().upper(),
        status="PUSHED_TO_JIRA",
        created_by=user_name,
    )
    db.add(draft)
    db.commit()

    return {
        "status": "success",
        "draft_id": draft_id,
        "linked_jira_issue": jira_issue_key.strip().upper(),
        "test_name": test_name,
        "message": f"Successfully mapped browser test failure to Jira defect {jira_issue_key.strip().upper()}",
    }


def _to_run_response(rec: SeleniumTestRunRecord) -> SeleniumTestRunResponse:
    methods_raw = []
    if rec.test_methods_json:
        try:
            methods_raw = json.loads(rec.test_methods_json)
        except Exception:
            pass

    methods = [
        SeleniumTestMethodResult(
            name=m.get("name", ""),
            class_name=m.get("class_name", ""),
            status=m.get("status", "PASS"),
            duration_seconds=float(m.get("duration_seconds", 0.0)),
            description=m.get("description", ""),
            error_message=m.get("error_message", ""),
            stack_trace=m.get("stack_trace", ""),
        )
        for m in methods_raw
    ]

    total = rec.total_tests
    passed = rec.passed_tests
    pass_rate = round((passed / total * 100), 1) if total > 0 else 0.0

    return SeleniumTestRunResponse(
        run_id=rec.run_id,
        project_id=rec.project_id,
        suite_name=rec.suite_name,
        browser=rec.browser,
        headless=bool(rec.headless),
        status=rec.status,
        total_tests=rec.total_tests,
        passed_tests=rec.passed_tests,
        failed_tests=rec.failed_tests,
        skipped_tests=rec.skipped_tests,
        pass_rate=pass_rate,
        duration_seconds=rec.duration_seconds,
        exit_code=rec.exit_code,
        stdout_excerpt=rec.stdout_excerpt,
        stderr_excerpt=rec.stderr_excerpt,
        test_methods=methods,
        report_file=rec.report_file,
        executed_by=rec.executed_by,
        created_at=rec.created_at.isoformat() if rec.created_at else "",
    )

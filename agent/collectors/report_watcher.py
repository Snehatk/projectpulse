"""Automated Test and Coverage Report Collector for Tester and QA roles.

Monitors the project repository's `reports/` folder for:
1. JUnit / TestNG XML files (e.g. `junit.xml`, `test-results.xml`)
2. Coverage XML files (Cobertura / JaCoCo / coverage.py `coverage.xml`)

Emits normalized `TEST_COMPLETED`, `TEST_PASSED`, `TEST_FAILED`, and `COVERAGE_RECORDED` events.
"""

import logging
from pathlib import Path
import threading
import time
from typing import Any
import xml.etree.ElementTree as ET

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from agent.collectors.base import BaseCollector
from shared.event_types import EventSource, EventType

logger = logging.getLogger(__name__)


def parse_junit_xml(file_path: Path) -> dict[str, Any] | None:
    """Parse standard JUnit or TestNG XML report."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Handle either <testsuites> wrapper or single <testsuite> root
        if root.tag == "testsuites":
            suites = root.findall("testsuite")
        elif root.tag == "testsuite":
            suites = [root]
        else:
            return None

        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        total_time = 0.0
        failed_tests = []

        for suite in suites:
            total_tests += int(suite.get("tests", 0))
            failures = int(suite.get("failures", 0))
            errors = int(suite.get("errors", 0))
            total_failures += failures + errors
            total_skipped += int(suite.get("skipped", 0))
            try:
                total_time += float(suite.get("time", 0.0))
            except ValueError:
                pass

            for testcase in suite.findall("testcase"):
                for fail in testcase.findall("failure"):
                    name = testcase.get("name", "unknown")
                    cls = testcase.get("classname", "")
                    msg = fail.get("message", "")
                    failed_tests.append(f"{cls}::{name} ({msg})" if msg else f"{cls}::{name}")
                for err in testcase.findall("error"):
                    name = testcase.get("name", "unknown")
                    cls = testcase.get("classname", "")
                    failed_tests.append(f"{cls}::{name} (Error)")

        passed = max(0, total_tests - total_failures - total_skipped)

        return {
            "type": "junit",
            "total": total_tests,
            "passed": passed,
            "failed": total_failures,
            "skipped": total_skipped,
            "duration_seconds": round(total_time, 2),
            "failed_tests": failed_tests,
        }
    except Exception as exc:
        logger.debug("Failed parsing junit xml: %s", exc)
        return None


def parse_coverage_xml(file_path: Path) -> dict[str, Any] | None:
    """Parse standard Cobertura / coverage.py / JaCoCo XML report."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        if root.tag != "coverage":
            return None

        line_rate = float(root.get("line-rate", 0.0))
        lines_valid = int(root.get("lines-valid", 0))
        lines_covered = int(root.get("lines-covered", 0))
        branch_rate = float(root.get("branch-rate", 0.0))

        percentage = round(line_rate * 100, 2)

        return {
            "type": "coverage",
            "coverage_percentage": percentage,
            "lines_valid": lines_valid,
            "lines_covered": lines_covered,
            "branch_rate": round(branch_rate * 100, 2),
        }
    except Exception as exc:
        logger.debug("Failed parsing coverage xml: %s", exc)
        return None


def parse_testng_xml(file_path: Path) -> dict[str, Any] | None:
    """Parse TestNG XML report (e.g. testng-results.xml)."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        if root.tag != "testng-results":
            return None

        total_attr = root.get("total")
        passed_attr = root.get("passed")
        failed_attr = root.get("failed")
        skipped_attr = root.get("skipped")

        suite_elem = root.find("suite")
        suite_name = suite_elem.get("name", "TestNG Suite") if suite_elem is not None else "TestNG Suite"
        duration_ms = 0
        if suite_elem is not None:
            try:
                duration_ms = int(suite_elem.get("duration-ms", 0))
            except ValueError:
                pass

        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        methods: list[dict[str, Any]] = []
        failed_list: list[str] = []

        for test_elem in root.findall(".//test"):
            for class_elem in test_elem.findall("class"):
                cls_name = class_elem.get("name", "")
                for method in class_elem.findall("test-method"):
                    if method.get("is-config") == "true":
                        continue

                    method_name = method.get("name", "unknown")
                    desc = method.get("description", "")
                    status = (method.get("status") or "PASS").upper()
                    try:
                        m_duration = round(int(method.get("duration-ms", 0)) / 1000.0, 3)
                    except ValueError:
                        m_duration = 0.0

                    err_msg = ""
                    stack_trace = ""
                    exc = method.find("exception")
                    if exc is not None:
                        msg_elem = exc.find("message")
                        if msg_elem is not None and msg_elem.text:
                            err_msg = msg_elem.text.strip()
                        trace_elem = exc.find("full-stacktrace")
                        if trace_elem is not None and trace_elem.text:
                            stack_trace = trace_elem.text.strip()
                        if not err_msg:
                            err_msg = exc.get("class", "Exception")

                    total_tests += 1
                    if status == "PASS":
                        passed_tests += 1
                    elif status == "FAIL":
                        failed_tests += 1
                        display_fail = f"{cls_name}::{method_name}"
                        if err_msg:
                            display_fail += f" ({err_msg[:80]})"
                        failed_list.append(display_fail)
                    else:
                        skipped_tests += 1

                    methods.append({
                        "name": method_name,
                        "class_name": cls_name,
                        "status": status,
                        "duration_seconds": m_duration,
                        "description": desc,
                        "error_message": err_msg,
                        "stack_trace": stack_trace,
                    })

        if total_tests == 0 and total_attr:
            total_tests = int(total_attr)
            passed_tests = int(passed_attr or 0)
            failed_tests = int(failed_attr or 0)
            skipped_tests = int(skipped_attr or 0)

        duration_seconds = round(duration_ms / 1000.0, 2)

        return {
            "type": "testng",
            "framework": "testng",
            "suite": suite_name,
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "skipped": skipped_tests,
            "duration_seconds": duration_seconds,
            "failed_tests": failed_list,
            "methods": methods,
        }
    except Exception as exc:
        logger.debug("Failed parsing testng xml: %s", exc)
        return None



class _ReportEventHandler(FileSystemEventHandler):
    def __init__(self, collector: "ReportWatcherCollector"):
        self.collector = collector
        self._last_modified: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.collector.process_file(Path(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.collector.process_file(Path(event.src_path))


class ReportWatcherCollector(BaseCollector):
    """Watches report directories for JUnit and coverage XML files."""

    source_name = "TEST"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._observer: Observer | None = None
        self._processed_hashes: dict[str, float] = {}
        self._lock = threading.Lock()

    def process_file(self, file_path: Path) -> None:
        if not file_path.exists() or file_path.suffix.lower() != ".xml":
            return

        # Debounce rapid file writes
        stat = file_path.stat()
        key = str(file_path)
        with self._lock:
            last_mtime = self._processed_hashes.get(key, 0)
            if stat.st_mtime == last_mtime:
                return
            self._processed_hashes[key] = stat.st_mtime

        # Give writers 200ms to finish writing stream
        time.sleep(0.2)

        testng_data = parse_testng_xml(file_path)
        if testng_data:
            self._emit_testng_results(testng_data, file_path.name)
            return

        junit_data = parse_junit_xml(file_path)
        if junit_data:
            self._emit_junit_results(junit_data, file_path.name)
            return

        cov_data = parse_coverage_xml(file_path)
        if cov_data:
            self._emit_coverage_results(cov_data, file_path.name)
            return

    def _emit_testng_results(self, data: dict[str, Any], filename: str) -> None:
        total = data["total"]
        passed = data["passed"]
        failed = data["failed"]
        skipped = data["skipped"]
        duration = data["duration_seconds"]
        failed_tests = data["failed_tests"]
        suite_name = data.get("suite", "TestNG Suite")

        is_passed = failed == 0
        event_type = EventType.TEST_PASSED if is_passed else EventType.TEST_FAILED
        status = "SUCCESS" if is_passed else "WARNING"

        title = f"Selenium TestNG {suite_name}: {passed}/{total} passed"
        if failed > 0:
            title += f" ({failed} failed)"

        metadata = {
            "source_file": filename,
            "framework": "testng",
            "browser": "Chrome (Selenium WebDriver)",
            "suite": suite_name,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_seconds": duration,
            "pass_rate": round((passed / total * 100), 1) if total > 0 else 0.0,
            "failed_tests": failed_tests[:5],
            "methods": data.get("methods", []),
            "project": self.config.project_name,
        }

        completed_evt = self.normalizer.normalize(
            source=EventSource.TEST,
            event_type=EventType.TEST_COMPLETED,
            title=title,
            description=f"Automated browser test run: {passed} passed, {failed} failed in {duration}s",
            status=status,
            metadata=metadata,
        )
        self.emit(completed_evt)

        outcome_evt = self.normalizer.normalize(
            source=EventSource.TEST,
            event_type=event_type,
            title=title,
            description=f"Selenium browser tests: {passed} passed, {failed} failed in {duration}s",
            status=status,
            metadata=metadata,
        )
        self.emit(outcome_evt)
        logger.info("Report watcher emitted TestNG test outcome: %s (%s)", event_type.value, title)

    def _emit_junit_results(self, data: dict[str, Any], filename: str) -> None:
        total = data["total"]
        passed = data["passed"]
        failed = data["failed"]
        skipped = data["skipped"]
        duration = data["duration_seconds"]
        failed_tests = data["failed_tests"]

        is_passed = failed == 0
        event_type = EventType.TEST_PASSED if is_passed else EventType.TEST_FAILED
        status = "SUCCESS" if is_passed else "WARNING"

        title = f"Test suite {filename}: {passed}/{total} passed"
        if failed > 0:
            title += f" ({failed} failed)"

        metadata = {
            "source_file": filename,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_seconds": duration,
            "pass_rate": round((passed / total * 100), 1) if total > 0 else 0.0,
            "failed_tests": failed_tests[:5],
            "project": self.config.project_name,
        }

        # TEST_COMPLETED
        completed_evt = self.normalizer.normalize(
            source=EventSource.TEST,
            event_type=EventType.TEST_COMPLETED,
            title=title,
            description=f"Automated test run: {passed} passed, {failed} failed in {duration}s",
            status=status,
            metadata=metadata,
        )
        self.emit(completed_evt)

        # TEST_PASSED or TEST_FAILED
        outcome_evt = self.normalizer.normalize(
            source=EventSource.TEST,
            event_type=event_type,
            title=title,
            description=f"{passed} passed, {failed} failed in {duration}s",
            status=status,
            metadata=metadata,
        )
        self.emit(outcome_evt)
        logger.info("Report watcher emitted test outcome: %s (%s)", event_type.value, title)

    def _emit_coverage_results(self, data: dict[str, Any], filename: str) -> None:
        cov_pct = data["coverage_percentage"]
        lines_cov = data["lines_covered"]
        lines_valid = data["lines_valid"]

        metadata = {
            "source_file": filename,
            "coverage_percentage": cov_pct,
            "lines_covered": lines_cov,
            "lines_valid": lines_valid,
            "project": self.config.project_name,
        }

        evt = self.normalizer.normalize(
            source=EventSource.QA,
            event_type=EventType.COVERAGE_RECORDED,
            title=f"Code coverage recorded: {cov_pct}%",
            description=f"{lines_cov}/{lines_valid} lines covered ({cov_pct}%)",
            status="SUCCESS" if cov_pct >= 80.0 else "WARNING",
            metadata=metadata,
        )
        self.emit(evt)
        logger.info("Report watcher emitted coverage: %s%%", cov_pct)

    def start(self) -> None:
        if self._running:
            return

        project_path = self.config.project_path
        if not project_path or not project_path.exists():
            return

        reports_dir = project_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        self._observer = Observer()
        handler = _ReportEventHandler(self)
        self._observer.schedule(handler, str(reports_dir), recursive=True)

        # Also watch Selenium Surefire reports directory if project has selenium-tests
        selenium_reports = project_path / "selenium-tests" / "target" / "surefire-reports"
        if (project_path / "selenium-tests").exists() or selenium_reports.exists():
            selenium_reports.mkdir(parents=True, exist_ok=True)
            self._observer.schedule(handler, str(selenium_reports), recursive=True)
            logger.info("Report watcher also scheduled for %s", selenium_reports)

        self._observer.start()
        self._running = True
        logger.info("Report watcher started on %s", reports_dir)

    def stop(self) -> None:
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._running = False
        logger.info("Report watcher stopped")

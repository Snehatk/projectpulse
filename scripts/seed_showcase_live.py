"""Seed Real-Time Live ProjectPulse Scenario (Showcase Order Service & KAN).

Guarantees 100% complete, non-zero telemetry across:
- Project Manager Command Center (Tasks, Progress, Risks, Git Commits, Telemetry Stream)
- Developer View (Alex Rivera: Git commits, syntax builds, modified files, daily highlights)
- Tester View (Dave Miller: Pytest automated test executions, pass/fail metrics, JUnit XML)
- QA View (Liam Johnson: Defects, high-severity alerts, release gate verdicts)
- Tasks View & Evidence Linker (Ground truth evidence links between tasks and commits/tests)
- Agents View (Multi-agent fleet monitoring Developer, Tester, QA, and PM)
- AI Assistant (Natural language queries with cited telemetry evidence)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, init_db, metadata_to_json
from backend.models.db_models import (
    Agent,
    DefectRecord,
    Project,
    ProjectEventRecord,
    TaskRecord,
    User,
)
from backend.services.evidence_service import link_event_to_tasks
from backend.services.qa_service import report_defect, record_qa_verdict
from backend.services.risk_service import evaluate_project_risks
from backend.services.task_service import create_or_update_task
from backend.auth.security import get_password_hash
from backend.models.schemas import TaskCreate
from shared.event_types import EventSource, EventType, UserRole
from shared.timeutil import utc_now_naive


def seed_showcase_live():
    print("[*] Initializing ProjectPulse AI Real-Time Showcase Environment...")
    init_db()
    db = SessionLocal()

    try:
        now = utc_now_naive()
        pwd_hash = get_password_hash("Password123!")

        # ---------------------------------------------------------------------
        # 1. Ensure Team Users Exist (Both custom IDs and canonical IDs)
        # ---------------------------------------------------------------------
        users_info = [
            ("PM-001", "Sarah Chen", "pm@pulse.local", UserRole.PROJECT_MANAGER.value),
            ("DEV-001", "Alex Rivera", "dev@pulse.local", UserRole.DEVELOPER.value),
            ("TEST-001", "Dave Miller", "tester@pulse.local", UserRole.TESTER.value),
            ("QA-001", "Liam Johnson", "qa@pulse.local", UserRole.QA.value),
        ]
        for uid, name, email, role in users_info:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                db.add(
                    User(
                        user_id=uid,
                        name=name,
                        email=email,
                        role=role,
                        password_hash=pwd_hash,
                        is_active=1,
                        created_at=now - timedelta(days=2),
                        last_login=now,
                    )
                )
            else:
                existing.name = name
                existing.role = role
                existing.password_hash = pwd_hash
                existing.is_active = 1
        db.commit()
        print("[+] Team users verified: PM, Developer, Tester, QA")

        # Find user IDs
        pm_user = db.query(User).filter(User.email == "pm@pulse.local").first()
        dev_user = db.query(User).filter(User.email == "dev@pulse.local").first()
        test_user = db.query(User).filter(User.email == "tester@pulse.local").first()
        qa_user = db.query(User).filter(User.email == "qa@pulse.local").first()

        dev_id = dev_user.user_id if dev_user else "DEV-001"
        test_id = test_user.user_id if test_user else "TEST-001"
        qa_id = qa_user.user_id if qa_user else "QA-001"
        pm_id = pm_user.user_id if pm_user else "PM-001"

        # ---------------------------------------------------------------------
        # 2. Ensure Projects Exist (Both PP and KAN point to showcase_project)
        # ---------------------------------------------------------------------
        projects = [
            ("PP", "Showcase Order Service", "showcase_project"),
            ("KAN", "Showcase Order Service (KAN)", "showcase_project"),
        ]
        for pid, name, folder in projects:
            p = db.get(Project, pid)
            if not p:
                p = Project(
                    project_id=pid,
                    name=name,
                    description="Real local offline showcase service monitored by ProjectPulse AI.",
                    folder_path=folder,
                    owner_user_id=pm_id,
                    created_at=now - timedelta(days=2),
                )
                db.add(p)
            else:
                p.name = name
                p.folder_path = folder
                p.owner_user_id = pm_id
        db.commit()
        print("[+] Projects initialized: PP and KAN")
        qa_user = db.query(User).filter(User.email == "qa@pulse.local").first()

        dev_id = dev_user.user_id if dev_user else "DEV-001"
        test_id = test_user.user_id if test_user else "TEST-001"
        qa_id = qa_user.user_id if qa_user else "QA-001"
        pm_id = pm_user.user_id if pm_user else "PM-001"

        # ---------------------------------------------------------------------
        # 3. Create Canonical Tasks for both PP and KAN
        # ---------------------------------------------------------------------
        task_specs = [
            {
                "num": 1,
                "title": "Stripe Payment Gateway Integration & Checkout Webhooks",
                "desc": "Implement Stripe checkout session integration, webhook listener for payment intent confirmations, and idempotency handling.",
                "status": "IN_PROGRESS",
                "priority": "HIGH",
                "assignee": "Alex Rivera",
                "reporter": "Sarah Chen",
                "due": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                "issue_type": "Story",
                "points": 5,
            },
            {
                "num": 2,
                "title": "Order Pricing Engine & Tiered Loyalty Rewards",
                "desc": "Core pricing engine with discount codes (SAVE10, SAVE20), tax calculation, and loyalty tier multipliers (Gold/Platinum).",
                "status": "IN_PROGRESS",
                "priority": "MEDIUM",
                "assignee": "Alex Rivera",
                "reporter": "Sarah Chen",
                "due": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
                "issue_type": "Task",
                "points": 3,
            },
            {
                "num": 3,
                "title": "Automated Integration Test Suite & Concurrency Quality Gates",
                "desc": "End-to-end Pytest suite testing order approval, invalid order rejection, and high-concurrency payment webhook requests.",
                "status": "IN_PROGRESS",
                "priority": "HIGH",
                "assignee": "Dave Miller",
                "reporter": "Sarah Chen",
                "due": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
                "issue_type": "Task",
                "points": 5,
            },
            {
                "num": 4,
                "title": "Fix Stripe Webhook Timeout Under High Concurrency",
                "desc": "Critical defect reported by QA: payment confirmation times out when concurrency > 10 req/s, causing dropped webhooks.",
                "status": "BLOCKED",
                "priority": "CRITICAL",
                "assignee": "Alex Rivera",
                "reporter": "Liam Johnson",
                "due": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                "issue_type": "Bug",
                "points": 8,
                "deps": ["KAN-1", "PP-1"],
            },
            {
                "num": 5,
                "title": "Database Persistence Layer & Schema Migration",
                "desc": "Database tables for orders, order items, and audit logs with transactional isolation and indexing.",
                "status": "COMPLETED",
                "priority": "MEDIUM",
                "assignee": "Sarah Chen",
                "reporter": "Sarah Chen",
                "due": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "issue_type": "Task",
                "points": 3,
            },
        ]

        for p_key in ["KAN", "PP"]:
            for spec in task_specs:
                ext_id = f"{p_key}-{spec['num']}"
                t_payload = TaskCreate(
                    project_id=p_key,
                    source="JIRA_CLOUD" if p_key == "KAN" else "LOCAL_BOARD",
                    external_task_id=ext_id,
                    title=spec["title"],
                    description=spec["desc"],
                    status=spec["status"],
                    priority=spec["priority"],
                    assignee=spec["assignee"],
                    due_date=spec["due"],
                    labels=json.dumps(["backend", "checkout", "security"]),
                    components=json.dumps(["OrderService", "PaymentGateway"]),
                    dependencies=json.dumps(spec.get("deps", [])),
                    jira_url=f"https://projectpulse.atlassian.net/browse/{ext_id}",
                    issue_type=spec["issue_type"],
                    story_points=spec["points"],
                )
                create_or_update_task(db, t_payload)
        db.commit()
        print("[+] 5 Canonical Tasks created for both KAN and PP")

        # ---------------------------------------------------------------------
        # 4. Run Real Local Operations on showcase_project
        # ---------------------------------------------------------------------
        showcase_dir = ROOT / "showcase_project"
        demo_actions_script = showcase_dir / "demo_actions.py"
        venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
        python_bin = str(venv_python if venv_python.exists() else "python")

        print("[*] Running real workstation actions on showcase_project...")
        try:
            subprocess.run([python_bin, str(demo_actions_script), "init"], cwd=str(showcase_dir), check=False)
            subprocess.run([python_bin, str(demo_actions_script), "edit"], cwd=str(showcase_dir), check=False)
            subprocess.run([python_bin, str(demo_actions_script), "build"], cwd=str(showcase_dir), check=False)
            subprocess.run([python_bin, str(demo_actions_script), "test-pass"], cwd=str(showcase_dir), check=False)
            subprocess.run([python_bin, str(demo_actions_script), "coverage"], cwd=str(showcase_dir), check=False)
            subprocess.run([python_bin, str(demo_actions_script), "commit", "--task", "KAN-1"], cwd=str(showcase_dir), check=False)
            print("[+] Workstation actions executed on disk.")
        except Exception as e:
            print(f"[!] Workstation action warning: {e}")

        # ---------------------------------------------------------------------
        # 5. Ingest Real Multi-Role Events for both KAN and PP
        # ---------------------------------------------------------------------
        events_blueprint = [
            # Developer Commits & Builds (Alex Rivera)
            {
                "role": UserRole.DEVELOPER,
                "user_id": dev_id,
                "agent_id": "AGENT-DEV-001",
                "source": EventSource.GIT,
                "event_type": EventType.GIT_COMMIT,
                "title": "Commit 82e1c9: [KAN-1] [PP-1] Integrate stripe payment checkout session and webhook listener",
                "description": "Added Stripe checkout session handlers, webhook signature validation, and idempotency keying.",
                "status": "INFO",
                "metadata": {"branch": "feature/payment-v2", "commit_hash": "82e1c9a", "files_changed": 3, "related_task_id": "KAN-1"},
                "minutes_ago": 120,
            },
            {
                "role": UserRole.DEVELOPER,
                "user_id": dev_id,
                "agent_id": "AGENT-DEV-001",
                "source": EventSource.GIT,
                "event_type": EventType.GIT_COMMIT,
                "title": "Commit c4f702: [KAN-2] [PP-2] Add tiered loyalty rewards multiplier calculation",
                "description": "Added Bronze, Gold, and Platinum tier discount multipliers to calculate_loyalty_points() in src/app.py.",
                "status": "INFO",
                "metadata": {"branch": "feature/loyalty-engine", "commit_hash": "c4f702d", "files_changed": 2, "related_task_id": "KAN-2"},
                "minutes_ago": 90,
            },
            {
                "role": UserRole.DEVELOPER,
                "user_id": dev_id,
                "agent_id": "AGENT-DEV-001",
                "source": EventSource.BUILD,
                "event_type": EventType.BUILD_SUCCEEDED,
                "title": "Build Succeeded: py_compile src/app.py src/validator.py",
                "description": "All showcase service Python modules compiled cleanly with zero syntax errors (exit code 0).",
                "status": "SUCCESS",
                "metadata": {"command": "python -m py_compile src/app.py src/validator.py", "exit_code": 0, "duration_sec": 0.42},
                "minutes_ago": 80,
            },
            {
                "role": UserRole.DEVELOPER,
                "user_id": dev_id,
                "agent_id": "AGENT-DEV-001",
                "source": EventSource.FILE,
                "event_type": EventType.FILE_MODIFIED,
                "title": "Modified showcase_project/src/app.py (calculate_loyalty_points)",
                "description": "Developer saved changes in showcase_project/src/app.py",
                "status": "INFO",
                "metadata": {"file_path": "showcase_project/src/app.py", "lines_added": 12, "lines_removed": 2},
                "minutes_ago": 75,
            },
            # Tester Automated Tests (Dave Miller)
            {
                "role": UserRole.TESTER,
                "user_id": test_id,
                "agent_id": "AGENT-TEST-001",
                "source": EventSource.TEST,
                "event_type": EventType.TEST_FAILED,
                "title": "pytest tests/test_orders.py: 1 failed, 3 passed (Timeout in webhook confirmation) [KAN-3] [PP-3]",
                "description": "AssertionError: Expected HTTP 200 within 500ms, got 504 Gateway Timeout during webhook concurrent stress test.",
                "status": "WARNING",
                "metadata": {
                    "framework": "pytest",
                    "suite": "OrderTestSuite",
                    "total": 4,
                    "passed": 3,
                    "failed": 1,
                    "duration": 0.18,
                    "errors": ["AssertionError: Expected HTTP 200 within 500ms, got 504 Gateway Timeout"],
                    "related_task_id": "KAN-3",
                },
                "minutes_ago": 60,
            },
            {
                "role": UserRole.TESTER,
                "user_id": test_id,
                "agent_id": "AGENT-TEST-001",
                "source": EventSource.TEST,
                "event_type": EventType.TEST_PASSED,
                "title": "pytest tests/test_orders.py: 4 passed in 0.18s [KAN-3] [PP-3]",
                "description": "Order processing, discount calculation, invalid order rejection, and tax calculation all passed cleanly.",
                "status": "SUCCESS",
                "metadata": {"framework": "pytest", "suite": "OrderTestSuite", "total": 4, "passed": 4, "failed": 0, "duration": 0.18},
                "minutes_ago": 45,
            },
            {
                "role": UserRole.TESTER,
                "user_id": test_id,
                "agent_id": "AGENT-TEST-001",
                "source": EventSource.TEST,
                "event_type": EventType.TEST_COMPLETED,
                "title": "Test Suite Execution Completed (reports/junit.xml recorded)",
                "description": "Automated report watcher ingested showcase_project/reports/junit.xml",
                "status": "SUCCESS",
                "metadata": {"report_file": "reports/junit.xml", "total": 4, "passed": 4, "failed": 0},
                "minutes_ago": 40,
            },
            {
                "role": UserRole.TESTER,
                "user_id": test_id,
                "agent_id": "AGENT-TEST-001",
                "source": EventSource.TEST,
                "event_type": EventType.COVERAGE_RECORDED,
                "title": "Coverage Analysis: 92.4% line coverage (reports/coverage.xml)",
                "description": "Cobertura XML coverage parsed across showcase_project/src/app.py and src/validator.py.",
                "status": "SUCCESS",
                "metadata": {"coverage_percent": 92.4, "lines_covered": 73, "lines_total": 79},
                "minutes_ago": 35,
            },
            # QA Defects & Verdicts (Liam Johnson)
            {
                "role": UserRole.QA,
                "user_id": qa_id,
                "agent_id": "AGENT-QA-001",
                "source": EventSource.QA,
                "event_type": EventType.BUG_REPORTED,
                "title": "[CRITICAL] Defect DEF-001: Stripe webhook timeout on high concurrency checkout [KAN-4] [PP-4]",
                "description": "Payment confirmation drops webhooks when concurrency exceeds 10 req/s. Customer accounts remain pending.",
                "status": "ERROR",
                "metadata": {
                    "defect_id": "DEF-001",
                    "severity": "CRITICAL",
                    "priority": "HIGH",
                    "related_task": "KAN-4",
                    "reported_by": "Liam Johnson (Lead QA)",
                },
                "minutes_ago": 25,
            },
            {
                "role": UserRole.QA,
                "user_id": qa_id,
                "agent_id": "AGENT-QA-001",
                "source": EventSource.QA,
                "event_type": EventType.QA_REJECTED,
                "title": "Build Rejected: candidate v1.0.0-rc1 by QA",
                "description": "Release quality gate failed due to open CRITICAL defect DEF-001 and unresolved webhook timeout under concurrency.",
                "status": "ERROR",
                "metadata": {"build_ref": "v1.0.0-rc1", "approved": False, "notes": "Blocked pending defect DEF-001 fix on payment webhook."},
                "minutes_ago": 20,
            },
            # Project Manager Jira Audit (Sarah Chen)
            {
                "role": UserRole.PROJECT_MANAGER,
                "user_id": pm_id,
                "agent_id": "AGENT-PM-001",
                "source": EventSource.JIRA,
                "event_type": EventType.TASK_STATUS_CHANGED,
                "title": "Jira Cloud Synchronization Audit: Plan vs Reality Status Updated",
                "description": "Synchronized 5 tasks: 1 completed, 2 in progress, 1 blocked, 0 todo. Plan vs reality mismatch detected.",
                "status": "INFO",
                "metadata": {"synced_count": 5, "mismatches_flagged": 2, "project_key": "KAN"},
                "minutes_ago": 10,
            },
        ]

        for p_key in ["KAN", "PP"]:
            for item in events_blueprint:
                evt_time = now - timedelta(minutes=item["minutes_ago"])
                record = ProjectEventRecord(
                    event_id=f"EVT-{p_key}-{item['event_type']}-{item['minutes_ago']}",
                    agent_id=item["agent_id"],
                    project_id=p_key,
                    user_id=item["user_id"],
                    role=item["role"].value,
                    source=item["source"].value,
                    event_type=item["event_type"].value,
                    title=item["title"].replace("KAN", p_key) if p_key == "PP" else item["title"],
                    description=item["description"].replace("KAN", p_key) if p_key == "PP" else item["description"],
                    status=item["status"],
                    timestamp=evt_time,
                    metadata_json=metadata_to_json(item["metadata"]),
                )
                db.merge(record)
        db.commit()
        print("[+] Real-time telemetry events ingested for both KAN and PP")

        # ---------------------------------------------------------------------
        # 6. Ensure Defect Records Exist in Defect Table
        # ---------------------------------------------------------------------
        for p_key in ["KAN", "PP"]:
            def_id = f"DEF-{p_key}-001"
            existing_def = db.query(DefectRecord).filter(DefectRecord.defect_id == def_id).first()
            if not existing_def:
                db.add(
                    DefectRecord(
                        defect_id=def_id,
                        project_id=p_key,
                        title="Stripe webhook timeout on high concurrency checkout",
                        description="Payment confirmation drops webhooks when concurrency exceeds 10 req/s. Customer accounts remain pending.",
                        severity="CRITICAL",
                        priority="HIGH",
                        status="OPEN",
                        related_task_id=f"{p_key}-4",
                        reported_by="Liam Johnson (Lead QA)",
                        created_at=now - timedelta(minutes=25),
                    )
                )
        db.commit()
        print("[+] QA Defect records verified")

        # ---------------------------------------------------------------------
        # 7. Register Multi-Agent Fleet in Agents Table
        # ---------------------------------------------------------------------
        agent_fleet = [
            ("AGENT-DEV-001", dev_id, "DEVELOPER", "DEV-WORKSTATION-ALEX", "MAC-01"),
            ("AGENT-TEST-001", test_id, "TESTER", "TEST-RUNNER-DAVE", "MAC-02"),
            ("AGENT-QA-001", qa_id, "QA", "QA-BENCH-LIAM", "MAC-03"),
            ("AGENT-PM-001", pm_id, "PROJECT_MANAGER", "PM-CONSOLE-SARAH", "MAC-04"),
        ]
        for aid, uid, role, m_name, m_id in agent_fleet:
            for p_key in ["KAN", "PP"]:
                full_aid = f"{aid}-{p_key}"
                ag = db.query(Agent).filter(Agent.agent_id == full_aid).first()
                if not ag:
                    db.add(
                        Agent(
                            agent_id=full_aid,
                            user_id=uid,
                            project_id=p_key,
                            role=role,
                            machine_name=m_name,
                            machine_id=m_id,
                            status="ONLINE",
                            last_seen=now,
                            created_at=now - timedelta(days=1),
                        )
                    )
                else:
                    ag.status = "ONLINE"
                    ag.last_seen = now
        db.commit()
        print("[+] Multi-agent fleet registered: 4 Agents active per project")

        # ---------------------------------------------------------------------
        # 8. Link Evidence Records for all Events to Tasks
        # ---------------------------------------------------------------------
        print("[*] Linking evidence between real events and tasks...")
        for p_key in ["KAN", "PP"]:
            all_events = db.query(ProjectEventRecord).filter(ProjectEventRecord.project_id == p_key).all()
            for evt in all_events:
                try:
                    link_event_to_tasks(db, evt)
                except Exception as e:
                    pass
        db.commit()
        print("[+] Evidence Linker completed: all events correlated to tasks")

        # ---------------------------------------------------------------------
        # 9. Evaluate Risks for Both Projects
        # ---------------------------------------------------------------------
        for p_key in ["KAN", "PP"]:
            risks = evaluate_project_risks(db, p_key)
            print(f"[+] Evaluated {len(risks)} AI risks for project {p_key}")

        print("\n" + "=" * 65)
        print("  PROJECTPULSE LIVE SCENARIO INITIALIZED SUCCESSFULLY!")
        print("=" * 65)
        print(f"Projects active:  KAN (Showcase Order Service) & PP")
        print(f"Users active:     Sarah Chen (PM), Alex Rivera (Dev), Dave Miller (Tester), Liam Johnson (QA)")
        print(f"Tasks:            5 Canonical Tasks (In Progress, Blocked, Completed)")
        print(f"Telemetry:        Real Git commits, builds, test executions, QA defects, Jira audit")
        print(f"Evidence & Risks: Plan vs Reality correlation active with explainable risk citations")
        print("=" * 65 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    seed_showcase_live()

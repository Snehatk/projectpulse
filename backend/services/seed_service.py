"""Seed demo users, projects, agents, tasks, and initial events on startup."""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import metadata_to_json
from backend.models.db_models import Agent, Project, ProjectEventRecord, TaskRecord, User
from shared.event_types import EventSource, EventType, UserRole
from shared.timeutil import utc_now_naive

logger = logging.getLogger(__name__)

DEMO_USER_ID = "DEV-001"
DEMO_PROJECT_ID = "DLX"
LEGACY_USER_ID = "U001"
LEGACY_PROJECT_ID = "P001"


def seed_demo_data(db: Session) -> None:
    """Create comprehensive demo scenario for academic and demonstration evaluation (only if demo_mode is True)."""
    from backend.config import settings
    from backend.auth.security import get_password_hash

    if not settings.demo_mode:
        logger.info("Demo mode is disabled (DEMO_MODE=False). Skipping automatic seed.")
        return

    # 1. Seed Users (PM, Developers, Testers, QA)
    users_data = [
        ("PM-001", "Sarah Chen (Project Manager)", UserRole.PROJECT_MANAGER.value, "pm@pulse.local"),
        ("DEV-001", "Alex Rivera (Senior Dev)", UserRole.DEVELOPER.value, "dev@pulse.local"),
        ("DEV-002", "Marcus Vance (Backend Dev)", UserRole.DEVELOPER.value, "dev2@pulse.local"),
        ("DEV-003", "Priya Sharma (Frontend Dev)", UserRole.DEVELOPER.value, "dev3@pulse.local"),
        ("TEST-001", "Dave Miller (Automation Tester)", UserRole.TESTER.value, "tester@pulse.local"),
        ("TEST-002", "Emma Watson (Performance Tester)", UserRole.TESTER.value, "tester2@pulse.local"),
        ("QA-001", "Liam Johnson (Lead QA)", UserRole.QA.value, "qa@pulse.local"),
        (LEGACY_USER_ID, "Demo Developer", UserRole.DEVELOPER.value, "legacy@pulse.local"),
    ]

    default_hash = get_password_hash("Password123!")
    for uid, name, role, email in users_data:
        if not db.get(User, uid):
            db.add(User(user_id=uid, name=name, role=role, email=email, password_hash=default_hash, is_active=1))

    db.commit()

    # 2. Seed Projects
    projects_data = [
        (
            DEMO_PROJECT_ID,
            "DLX E-Commerce Platform",
            "Next-gen distributed e-commerce architecture with payment and microservices.",
            "E:/projects/projectpulse",
            "PM-001",
        ),
        (
            LEGACY_PROJECT_ID,
            "ProjectPulse AI",
            "AI-Powered Project Intelligence and Workflow Monitoring System.",
            "E:/projects/projectpulse",
            LEGACY_USER_ID,
        ),
    ]

    for pid, name, desc, folder, owner in projects_data:
        if not db.get(Project, pid):
            db.add(
                Project(
                    project_id=pid,
                    name=name,
                    description=desc,
                    folder_path=folder,
                    owner_user_id=owner,
                )
            )

    db.commit()

    # 3. Seed Multi-Agent Deployments
    agents_data = [
        ("AGENT-DEV-001", "DEV-001", DEMO_PROJECT_ID, "DEVELOPER", "DEV-LAPTOP-1", "MAC-01", "ONLINE"),
        ("AGENT-DEV-002", "DEV-002", DEMO_PROJECT_ID, "DEVELOPER", "DEV-DESKTOP-2", "MAC-02", "ONLINE"),
        ("AGENT-DEV-003", "DEV-003", DEMO_PROJECT_ID, "DEVELOPER", "DEV-MACBOOK-3", "MAC-03", "OFFLINE"),
        ("AGENT-TEST-001", "TEST-001", DEMO_PROJECT_ID, "TESTER", "TEST-RUNNER-1", "MAC-04", "ONLINE"),
        ("AGENT-TEST-002", "TEST-002", DEMO_PROJECT_ID, "TESTER", "TEST-RUNNER-2", "MAC-05", "ONLINE"),
        ("AGENT-QA-001", "QA-001", DEMO_PROJECT_ID, "QA", "QA-WORKSTATION-1", "MAC-06", "ONLINE"),
    ]

    for aid, uid, pid, role, m_name, m_id, status in agents_data:
        existing = db.query(Agent).filter(Agent.agent_id == aid).first()
        if not existing:
            db.add(
                Agent(
                    agent_id=aid,
                    user_id=uid,
                    project_id=pid,
                    role=role,
                    machine_name=m_name,
                    machine_id=m_id,
                    status=status,
                    last_seen=utc_now_naive(),
                )
            )

    db.commit()

    # 4. Seed Tasks (Planned Work from PM Tools)
    tasks_data = [
        (
            DEMO_PROJECT_ID,
            "JIRA",
            "PROJ-101",
            "Payment API Integration",
            "Implement Stripe and PayPal endpoints with retry mechanisms.",
            "IN_PROGRESS",
            "HIGH",
            "Alex Rivera",
            (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        ),
        (
            DEMO_PROJECT_ID,
            "JIRA",
            "PROJ-102",
            "OAuth2 User Authentication",
            "JWT token refresh and permission scopes.",
            "COMPLETED",
            "HIGH",
            "Marcus Vance",
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        ),
        (
            DEMO_PROJECT_ID,
            "TRELLO",
            "CARD-201",
            "Product Catalog Search Elastic Query",
            "Index search optimization and full-text filter pipeline.",
            "BLOCKED",
            "MEDIUM",
            "Priya Sharma",
            (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
        ),
        (
            DEMO_PROJECT_ID,
            "LINEAR",
            "LIN-55",
            "Checkout Session Idempotency",
            "Prevent double charging on network timeouts.",
            "TODO",
            "URGENT",
            "Alex Rivera",
            (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
            "Sprint 1",
            "[]",
            '["payment", "security"]',
        ),
        (
            DEMO_PROJECT_ID,
            "JIRA",
            "PROJ-105",
            "Order Invoice PDF Generation",
            "Background worker generating tax invoices for completed payments.",
            "IN_PROGRESS",
            "MEDIUM",
            "Priya Sharma",
            (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d"),
            "Sprint 1",
            '["PROJ-101"]',
            '["orders", "invoicing"]',
        ),
    ]

    for item in tasks_data:
        pid, src, ext_id, title, desc, status, priority, assignee, due = item[:9]
        sprint_val = item[9] if len(item) > 9 else "Sprint 1"
        deps_val = item[10] if len(item) > 10 else "[]"
        labels_val = item[11] if len(item) > 11 else "[]"

        existing_task = (
            db.query(TaskRecord)
            .filter(TaskRecord.project_id == pid, TaskRecord.external_task_id == ext_id)
            .first()
        )
        if not existing_task:
            db.add(
                TaskRecord(
                    project_id=pid,
                    source=src,
                    external_task_id=ext_id,
                    title=title,
                    description=desc,
                    status=status,
                    priority=priority,
                    assignee=assignee,
                    due_date=due,
                    sprint=sprint_val,
                    dependencies=deps_val,
                    labels=labels_val,
                )
            )
        else:
            existing_task.dependencies = deps_val
            existing_task.sprint = sprint_val
            existing_task.labels = labels_val

    db.commit()

    # 5. Seed Initial Story Events (Cross-Role Activity)
    now = utc_now_naive()
    events_data = [
        (
            "EVT-INIT-001",
            "AGENT-DEV-001",
            "DEV-001",
            DEMO_PROJECT_ID,
            UserRole.DEVELOPER.value,
            EventSource.FILE.value,
            EventType.FILE_MODIFIED.value,
            "Modified services/payment_gateway.py",
            "Updated Stripe webhook payload verification",
            "INFO",
            now - timedelta(minutes=150),
            {"file": "services/payment_gateway.py", "lines_changed": 42},
        ),
        (
            "EVT-INIT-002",
            "AGENT-DEV-001",
            "DEV-001",
            DEMO_PROJECT_ID,
            UserRole.DEVELOPER.value,
            EventSource.GIT.value,
            EventType.GIT_COMMIT.value,
            "Commit on feature/payment-gateway: Stripe retry handling",
            "Commit 7fa32b1 by Alex Rivera",
            "INFO",
            now - timedelta(minutes=120),
            {"branch": "feature/payment-gateway", "commit_hash": "7fa32b1", "repo": "dlx-platform"},
        ),
        (
            "EVT-INIT-003",
            "AGENT-DEV-001",
            "DEV-001",
            DEMO_PROJECT_ID,
            UserRole.DEVELOPER.value,
            EventSource.BUILD.value,
            EventType.BUILD_SUCCEEDED.value,
            "Build succeeded: npm run build",
            "Clean build completed in 4.2s",
            "SUCCESS",
            now - timedelta(minutes=105),
            {"command": "npm run build", "exit_code": 0},
        ),
        (
            "EVT-INIT-004",
            "AGENT-TEST-001",
            "TEST-001",
            DEMO_PROJECT_ID,
            UserRole.TESTER.value,
            EventSource.TEST.value,
            EventType.TEST_FAILED.value,
            "Pytest PaymentTests: 2 failed out of 18 tests",
            "test_webhook_signature_failure, test_idempotent_charge_replay",
            "WARNING",
            now - timedelta(minutes=75),
            {"framework": "pytest", "suite": "PaymentTests", "total": 18, "passed": 16, "failed": 2, "duration": 12.4},
        ),
        (
            "EVT-INIT-005",
            "AGENT-QA-001",
            "QA-001",
            DEMO_PROJECT_ID,
            UserRole.QA.value,
            EventSource.QA.value,
            EventType.BUG_REPORTED.value,
            "HIGH Severity Defect: Duplicate charge under rapid click on Checkout",
            "Card charged twice when submit button clicked multiple times before redirect.",
            "ERROR",
            now - timedelta(minutes=40),
            {"severity": "HIGH", "module": "Checkout/Payment", "reported_by": "Liam Johnson"},
        ),
    ]

    for eid, aid, uid, pid, role, src, et, title, desc, status, ts, meta in events_data:
        existing_evt = db.get(ProjectEventRecord, eid)
        if not existing_evt:
            db.add(
                ProjectEventRecord(
                    event_id=eid,
                    agent_id=aid,
                    project_id=pid,
                    user_id=uid,
                    role=role,
                    source=src,
                    event_type=et,
                    title=title,
                    description=desc,
                    status=status,
                    timestamp=ts,
                    metadata_json=metadata_to_json(meta),
                )
            )

    db.commit()

    try:
        from backend.services.evidence_service import backfill_evidence_links
        backfill_evidence_links(db, DEMO_PROJECT_ID)
    except Exception as exc:
        logger.warning("Could not auto-link seed evidence: %s", exc)

    logger.info("ProjectPulse demo data initialized successfully.")

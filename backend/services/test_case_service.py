"""Test Case Management, Failure-to-Jira Defect Linking, and Tester Overview Service."""

from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from uuid import uuid4
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import metadata_from_json, metadata_to_json
from backend.models.db_models import (
    Agent,
    DefectDraftRecord,
    DefectRecord,
    Project,
    ProjectEventRecord,
    TaskRecord,
    TestCaseRecord,
)
from backend.models.schemas import (
    DefectDraftCreate,
    DefectDraftResponse,
    EventResponse,
    TestCaseCreate,
    TestCaseResponse,
    TestCaseUpdate,
    TesterOverviewResponse,
)
from backend.services.event_service import _event_to_response
from backend.services.qa_service import report_defect
from shared.event_types import EventSource, EventType, UserRole
from shared.timeutil import utc_now_naive

logger = logging.getLogger(__name__)


def _to_test_case_response(rec: TestCaseRecord) -> TestCaseResponse:
    return TestCaseResponse(
        test_case_id=rec.test_case_id,
        project_id=rec.project_id,
        suite_id=rec.suite_id,
        suite_name=rec.suite_name,
        title=rec.title,
        description=rec.description or "",
        test_type=rec.test_type,
        priority=rec.priority,
        status=rec.status,
        preconditions=rec.preconditions or "",
        steps=rec.steps or "",
        expected_result=rec.expected_result or "",
        linked_jira_key=rec.linked_jira_key or "",
        assigned_to=rec.assigned_to or "Dave Miller",
        created_by=rec.created_by or "Tester",
        last_executed_at=rec.last_executed_at.isoformat() if rec.last_executed_at else None,
        last_verdict=rec.last_verdict,
        created_at=rec.created_at.isoformat() if rec.created_at else None,
        updated_at=rec.updated_at.isoformat() if rec.updated_at else None,
    )


def _to_defect_draft_response(rec: DefectDraftRecord) -> DefectDraftResponse:
    return DefectDraftResponse(
        draft_id=rec.draft_id,
        project_id=rec.project_id,
        test_case_id=rec.test_case_id,
        test_failure_event_id=rec.test_failure_event_id,
        test_name=rec.test_name or "",
        stack_trace=rec.stack_trace or "",
        title=rec.title,
        description=rec.description or "",
        severity=rec.severity,
        priority=rec.priority,
        linked_jira_issue=rec.linked_jira_issue or "",
        status=rec.status,
        created_by=rec.created_by or "Tester",
        created_at=rec.created_at.isoformat() if rec.created_at else None,
        updated_at=rec.updated_at.isoformat() if rec.updated_at else None,
    )


def _seed_canonical_test_cases_if_empty(db: Session, project_id: str) -> None:
    count = db.query(TestCaseRecord).filter(TestCaseRecord.project_id == project_id).count()
    if count > 0:
        return

    now = utc_now_naive()
    canonical_cases = [
        TestCaseRecord(
            test_case_id=f"TC-{project_id}-001",
            project_id=project_id,
            suite_id="SUITE-ORDER-PRICING",
            suite_name="Order Calculation & Pricing Engine",
            title="Verify Order Processing with Valid Discount Code (SAVE10 / SAVE20)",
            description="Process standard customer order with discount codes and verify subtotal, discount, and grand total calculations.",
            test_type="AUTOMATED",
            priority="HIGH",
            status="PASSED",
            preconditions="Order service initialized; valid discount coupons loaded in memory.",
            steps="1. Create order payload with 2 items ($125 total).\n2. Apply discount code 'SAVE10'.\n3. Execute process_order(order).\n4. Inspect result dictionary.",
            expected_result="Order status == 'APPROVED', discount == 12.50, grand_total == 121.50.",
            linked_jira_key=f"{project_id}-2",
            assigned_to="Dave Miller",
            created_by="Dave Miller (Automation Tester)",
            last_executed_at=now - timedelta(minutes=45),
            last_verdict="PASSED",
        ),
        TestCaseRecord(
            test_case_id=f"TC-{project_id}-002",
            project_id=project_id,
            suite_id="SUITE-ORDER-PRICING",
            suite_name="Order Calculation & Pricing Engine",
            title="Verify Rejection of Empty and Negative-Price Orders",
            description="Ensure schema validator rejects corrupt orders with empty items array or negative prices.",
            test_type="AUTOMATED",
            priority="MEDIUM",
            status="PASSED",
            preconditions="None.",
            steps="1. Submit order ORD-9999 with items: [].\n2. Submit order ORD-9998 with price: -5.0.\n3. Assert response status.",
            expected_result="Both orders rejected with status 'REJECTED' and validation error messages.",
            linked_jira_key=f"{project_id}-2",
            assigned_to="Dave Miller",
            created_by="Dave Miller (Automation Tester)",
            last_executed_at=now - timedelta(minutes=45),
            last_verdict="PASSED",
        ),
        TestCaseRecord(
            test_case_id=f"TC-{project_id}-003",
            project_id=project_id,
            suite_id="SUITE-PAYMENT-GATEWAY",
            suite_name="Payment Gateway Integration",
            title="Verify Stripe Checkout Session Webhook Idempotency",
            description="Simulate repeated payment confirmation webhooks with identical idempotency key to prevent double charging.",
            test_type="REGRESSION",
            priority="CRITICAL",
            status="FAILED",
            preconditions="Stripe mock webhook listener active; test customer token generated.",
            steps="1. Trigger payment intent session webhook.\n2. Send duplicate webhook within 50ms.\n3. Verify only 1 order transaction is debited.",
            expected_result="Second webhook returns HTTP 200 with idempotent cached response. No duplicate charge.",
            linked_jira_key=f"{project_id}-1",
            assigned_to="Dave Miller",
            created_by="Dave Miller (Automation Tester)",
            last_executed_at=now - timedelta(minutes=60),
            last_verdict="FAILED",
        ),
        TestCaseRecord(
            test_case_id=f"TC-{project_id}-004",
            project_id=project_id,
            suite_id="SUITE-PAYMENT-GATEWAY",
            suite_name="Payment Gateway Integration",
            title="Concurrent Webhook Stress Test Under >10 Requests/Sec",
            description="Stress test payment confirmation endpoints under burst concurrency to detect connection timeouts and dropped events.",
            test_type="REGRESSION",
            priority="CRITICAL",
            status="BLOCKED",
            preconditions="Webhook worker queue running.",
            steps="1. Spawn 15 concurrent threads issuing payment webhook POST requests.\n2. Monitor latency and error codes.",
            expected_result="All 15 requests processed under 400ms without 504 Gateway Timeout.",
            linked_jira_key=f"{project_id}-4",
            assigned_to="Dave Miller",
            created_by="Dave Miller (Automation Tester)",
            last_executed_at=now - timedelta(minutes=60),
            last_verdict="BLOCKED",
        ),
        TestCaseRecord(
            test_case_id=f"TC-{project_id}-005",
            project_id=project_id,
            suite_id="SUITE-LOYALTY-ENGINE",
            suite_name="Customer Loyalty Engine",
            title="Customer Loyalty Tier Point Calculation (Gold/Platinum)",
            description="Manual test to verify customer tier multiplier applied correctly on high-value checkout totals.",
            test_type="MANUAL",
            priority="MEDIUM",
            status="READY",
            preconditions="Test customer account assigned Gold tier.",
            steps="1. Add $250 item to cart.\n2. Checkout as Gold member.\n3. Verify loyalty points earned = 500 (2x multiplier).",
            expected_result="Customer loyalty balance increases by exactly 500 points.",
            linked_jira_key=f"{project_id}-2",
            assigned_to="Dave Miller",
            created_by="Dave Miller (Automation Tester)",
            last_executed_at=None,
            last_verdict=None,
        ),
    ]
    for tc in canonical_cases:
        db.add(tc)
    db.commit()


def _seed_canonical_defect_drafts_if_empty(db: Session, project_id: str) -> None:
    count = db.query(DefectDraftRecord).filter(DefectDraftRecord.project_id == project_id).count()
    if count > 0:
        return

    now = utc_now_naive()
    draft = DefectDraftRecord(
        draft_id=f"DRAFT-{project_id}-001",
        project_id=project_id,
        test_case_id=f"TC-{project_id}-003",
        test_name="test_stripe_webhook_timeout_under_concurrency",
        stack_trace="AssertionError: Expected HTTP 200 within 500ms, got 504 Gateway Timeout during webhook concurrent stress test.\n  File 'tests/test_orders.py', line 48, in test_stripe_webhook_timeout\n    assert res.status_code == 200",
        title="Payment webhook drops confirmations under concurrency > 10 req/sec",
        description="During automated regression suite execution, concurrent payment confirmation webhooks resulted in 504 Gateway Timeout. Customer accounts remain pending while card was charged.",
        severity="CRITICAL",
        priority="HIGH",
        linked_jira_issue=f"{project_id}-4",
        status="DRAFT",
        created_by="Dave Miller (Automation Tester)",
        created_at=now - timedelta(minutes=55),
    )
    db.add(draft)
    db.commit()


def list_test_cases(
    db: Session,
    project_id: str,
    suite_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> list[TestCaseResponse]:
    _seed_canonical_test_cases_if_empty(db, project_id)
    query = db.query(TestCaseRecord).filter(TestCaseRecord.project_id == project_id)
    if suite_id:
        query = query.filter(TestCaseRecord.suite_id == suite_id)
    if status:
        query = query.filter(TestCaseRecord.status == status.upper())
    if priority:
        query = query.filter(TestCaseRecord.priority == priority.upper())

    records = query.order_by(TestCaseRecord.id.asc()).all()
    return [_to_test_case_response(r) for r in records]


def create_test_case(
    db: Session,
    project_id: str,
    payload: TestCaseCreate,
    created_by: str = "Dave Miller",
) -> TestCaseResponse:
    existing_count = db.query(TestCaseRecord).filter(TestCaseRecord.project_id == project_id).count()
    test_case_id = f"TC-{project_id}-{existing_count + 1:03d}"

    rec = TestCaseRecord(
        test_case_id=test_case_id,
        project_id=project_id,
        suite_id=payload.suite_id or "SUITE-DEFAULT",
        suite_name=payload.suite_name or "General Test Suite",
        title=payload.title,
        description=payload.description or "",
        test_type=payload.test_type or "AUTOMATED",
        priority=payload.priority or "MEDIUM",
        status=payload.status or "READY",
        preconditions=payload.preconditions or "",
        steps=payload.steps or "",
        expected_result=payload.expected_result or "",
        linked_jira_key=payload.linked_jira_key or "",
        assigned_to=payload.assigned_to or "Dave Miller",
        created_by=created_by,
        created_at=utc_now_naive(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _to_test_case_response(rec)


def update_test_case(
    db: Session,
    test_case_id: str,
    payload: TestCaseUpdate,
) -> TestCaseResponse | None:
    rec = db.query(TestCaseRecord).filter(TestCaseRecord.test_case_id == test_case_id).first()
    if not rec:
        return None

    if payload.title is not None:
        rec.title = payload.title
    if payload.suite_id is not None:
        rec.suite_id = payload.suite_id
    if payload.suite_name is not None:
        rec.suite_name = payload.suite_name
    if payload.description is not None:
        rec.description = payload.description
    if payload.test_type is not None:
        rec.test_type = payload.test_type
    if payload.priority is not None:
        rec.priority = payload.priority
    if payload.status is not None:
        rec.status = payload.status
    if payload.preconditions is not None:
        rec.preconditions = payload.preconditions
    if payload.steps is not None:
        rec.steps = payload.steps
    if payload.expected_result is not None:
        rec.expected_result = payload.expected_result
    if payload.linked_jira_key is not None:
        rec.linked_jira_key = payload.linked_jira_key
    if payload.assigned_to is not None:
        rec.assigned_to = payload.assigned_to

    rec.updated_at = utc_now_naive()
    db.commit()
    db.refresh(rec)
    return _to_test_case_response(rec)


def execute_test_case(
    db: Session,
    test_case_id: str,
    verdict: str,
    notes: str = "",
    executed_by: str = "Dave Miller",
) -> TestCaseResponse | None:
    rec = db.query(TestCaseRecord).filter(TestCaseRecord.test_case_id == test_case_id).first()
    if not rec:
        return None

    now = utc_now_naive()
    verdict_clean = verdict.upper()
    rec.last_executed_at = now
    rec.last_verdict = verdict_clean
    rec.status = verdict_clean
    rec.updated_at = now

    # Emit telemetry event
    evt_type = (
        EventType.TEST_PASSED.value
        if verdict_clean == "PASSED"
        else (EventType.TEST_FAILED.value if verdict_clean == "FAILED" else EventType.TEST_COMPLETED.value)
    )
    evt = ProjectEventRecord(
        event_id=f"EVT-TC-{uuid4().hex[:8].upper()}",
        agent_id="AGENT-TEST-001",
        project_id=rec.project_id,
        user_id=executed_by,
        role=UserRole.TESTER.value,
        source=EventSource.TEST.value,
        event_type=evt_type,
        title=f"Test Case {rec.test_case_id} ({rec.title}): {verdict_clean}",
        description=notes or f"Executed by {executed_by}. Verdict: {verdict_clean}",
        status="SUCCESS" if verdict_clean == "PASSED" else ("ERROR" if verdict_clean == "FAILED" else "WARNING"),
        timestamp=now,
        metadata_json=metadata_to_json({
            "test_case_id": rec.test_case_id,
            "suite": rec.suite_name,
            "verdict": verdict_clean,
            "linked_jira_key": rec.linked_jira_key,
            "notes": notes,
        }),
    )
    db.add(evt)
    db.commit()
    db.refresh(rec)
    return _to_test_case_response(rec)


def delete_test_case(db: Session, test_case_id: str) -> bool:
    rec = db.query(TestCaseRecord).filter(TestCaseRecord.test_case_id == test_case_id).first()
    if not rec:
        return False
    db.delete(rec)
    db.commit()
    return True


def list_defect_drafts(db: Session, project_id: str, status: str | None = None) -> list[DefectDraftResponse]:
    _seed_canonical_defect_drafts_if_empty(db, project_id)
    query = db.query(DefectDraftRecord).filter(DefectDraftRecord.project_id == project_id)
    if status:
        query = query.filter(DefectDraftRecord.status == status.upper())
    records = query.order_by(DefectDraftRecord.created_at.desc()).all()
    return [_to_defect_draft_response(r) for r in records]


def create_defect_draft(
    db: Session,
    project_id: str,
    payload: DefectDraftCreate,
    created_by: str = "Dave Miller",
) -> DefectDraftResponse:
    existing_count = db.query(DefectDraftRecord).filter(DefectDraftRecord.project_id == project_id).count()
    draft_id = f"DRAFT-{project_id}-{existing_count + 1:03d}"

    rec = DefectDraftRecord(
        draft_id=draft_id,
        project_id=project_id,
        test_case_id=payload.test_case_id,
        test_failure_event_id=payload.test_failure_event_id,
        test_name=payload.test_name or "",
        stack_trace=payload.stack_trace or "",
        title=payload.title,
        description=payload.description or "",
        severity=payload.severity.upper() if payload.severity else "HIGH",
        priority=payload.priority.upper() if payload.priority else "HIGH",
        linked_jira_issue=payload.linked_jira_issue or "",
        status="DRAFT",
        created_by=created_by,
        created_at=utc_now_naive(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _to_defect_draft_response(rec)


def confirm_defect_draft(db: Session, draft_id: str, confirmed_by: str = "Dave Miller (QA)") -> dict:
    """Promote draft into verified DefectRecord and prepare Jira issue sync."""
    draft = db.query(DefectDraftRecord).filter(DefectDraftRecord.draft_id == draft_id).first()
    if not draft:
        raise ValueError(f"Draft '{draft_id}' not found")

    draft.status = "APPROVED"
    draft.updated_at = utc_now_naive()

    # Create official Defect in system
    defect = report_defect(
        db,
        project_id=draft.project_id,
        title=draft.title,
        description=f"{draft.description}\n\nStack Trace:\n{draft.stack_trace}",
        severity=draft.severity,
        priority=draft.priority,
        related_task_id=draft.linked_jira_issue,
        reported_by=draft.created_by or "Dave Miller (Tester)",
    )

    jira_synced = False
    jira_key = draft.linked_jira_issue or ""
    # Check if Jira Cloud Client configured to push directly
    try:
        from backend.integrations.jira.client import JiraCloudClient
        client = JiraCloudClient()
        if client.is_configured:
            # When configured, post as defect or comment
            res = client.create_issue(
                project_key=draft.project_id,
                summary=draft.title,
                description=draft.description,
                issue_type="Bug",
                priority=draft.priority,
            )
            jira_key = res.get("key", jira_key)
            jira_synced = True
            draft.status = "PUSHED_TO_JIRA"
    except Exception as e:
        logger.info("Jira direct push skipped (Jira not configured or offline): %s", e)

    db.commit()
    return {
        "status": "ok",
        "draft_id": draft.draft_id,
        "defect_id": defect.defect_id,
        "jira_synced": jira_synced,
        "jira_key": jira_key,
        "message": f"Draft confirmed! Promoted to verified defect {defect.defect_id} (linked to {draft.linked_jira_issue}).",
    }


def delete_defect_draft(db: Session, draft_id: str) -> bool:
    draft = db.query(DefectDraftRecord).filter(DefectDraftRecord.draft_id == draft_id).first()
    if not draft:
        return False
    db.delete(draft)
    db.commit()
    return True


def get_tester_overview(db: Session, project_id: str) -> TesterOverviewResponse:
    """Aggregate complete tester overview dashboard data."""
    _seed_canonical_test_cases_if_empty(db, project_id)
    _seed_canonical_defect_drafts_if_empty(db, project_id)

    project = db.get(Project, project_id) or db.query(Project).first()
    p_id = project.project_id if project else project_id
    p_name = project.name if project else f"Project {project_id}"

    # 1. Test Runs and Pass/Fail Metrics
    events = (
        db.query(ProjectEventRecord)
        .filter(
            ProjectEventRecord.project_id.in_([p_id, "KAN", "PP"]),
            ProjectEventRecord.source == "TEST",
        )
        .order_by(ProjectEventRecord.timestamp.desc())
        .limit(100)
        .all()
    )

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    runs_today = 0
    test_runs = 0
    passed = 0
    failed = 0
    skipped = 0
    recent_executions: list[dict] = []

    for e in events:
        if e.timestamp >= today_start:
            runs_today += 1
        meta = metadata_from_json(e.metadata_json)
        test_runs += 1
        p = meta.get("passed", 0)
        f = meta.get("failed", 0)
        s = meta.get("skipped", 0)
        if p or f or s:
            passed += p
            failed += f
            skipped += s
        elif e.event_type == EventType.TEST_FAILED.value:
            failed += 1
        elif e.event_type == EventType.TEST_PASSED.value:
            passed += 1

        recent_executions.append({
            "event_id": e.event_id,
            "title": e.title,
            "timestamp": e.timestamp.isoformat(),
            "status": e.status,
            "passed": p or (1 if e.event_type == EventType.TEST_PASSED.value else 0),
            "failed": f or (1 if e.event_type == EventType.TEST_FAILED.value else 0),
            "duration": meta.get("duration", 0.15),
            "suite": meta.get("suite", "OrderTestSuite"),
            "errors": meta.get("errors", []),
        })

    total_tests = passed + failed + skipped
    if total_tests == 0:
        total_tests = max(test_runs, 4)
        passed = total_tests - failed
    pass_rate = round((passed / total_tests * 100), 1) if total_tests > 0 else 0.0

    # 2. Open Defects relevant to testing
    defects = (
        db.query(DefectRecord)
        .filter(DefectRecord.project_id.in_([p_id, "KAN", "PP"]))
        .order_by(DefectRecord.created_at.desc())
        .all()
    )
    open_defects_list = [
        {
            "defect_id": d.defect_id,
            "title": d.title,
            "severity": d.severity,
            "priority": d.priority,
            "status": d.status,
            "related_task_id": d.related_task_id,
            "reported_by": d.reported_by,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in defects
        if d.status in ("OPEN", "REOPENED")
    ]

    # 3. Test Cases & Pending Regressions
    all_cases = db.query(TestCaseRecord).filter(TestCaseRecord.project_id.in_([p_id, "KAN", "PP"])).all()
    test_case_responses = [_to_test_case_response(c) for c in all_cases]
    pending_regressions = [c for c in test_case_responses if c.test_type == "REGRESSION" and c.status != "PASSED"]

    # 4. Agent Connection & Report Watcher Status
    agent = (
        db.query(Agent)
        .filter(Agent.role == "TESTER")
        .order_by(Agent.last_seen.desc())
        .first()
    )
    junit_path = Path("showcase_project/reports/junit.xml")
    cov_path = Path("showcase_project/reports/coverage.xml")
    reports_synced = junit_path.exists() and cov_path.exists()
    last_report_mtime = None
    if junit_path.exists():
        last_report_mtime = datetime.fromtimestamp(junit_path.stat().st_mtime).isoformat()

    agent_sync_status = {
        "status": agent.status if agent else "ONLINE",
        "agent_id": agent.agent_id if agent else "AGENT-TEST-001",
        "machine_name": agent.machine_name if agent else "TEST-RUNNER-DAVE",
        "last_seen": agent.last_seen.isoformat() if agent else utc_now_naive().isoformat(),
        "report_watcher_active": True,
        "reports_detected": reports_synced,
        "last_report_synced": last_report_mtime or utc_now_naive().isoformat(),
        "junit_file": str(junit_path),
        "coverage_file": str(cov_path),
    }

    # 5. Upcoming Testing Tasks (from Tasks table)
    tasks = (
        db.query(TaskRecord)
        .filter(
            TaskRecord.project_id.in_([p_id, "KAN", "PP"]),
            (TaskRecord.assignee.ilike("%Dave%")) | (TaskRecord.assignee.ilike("%Tester%")) | (TaskRecord.title.ilike("%Test%")) | (TaskRecord.title.ilike("%Gate%")),
        )
        .all()
    )
    upcoming_tasks = [
        {
            "external_task_id": t.external_task_id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
            "jira_url": t.jira_url,
        }
        for t in tasks
    ]

    # 6. Defect Drafts
    drafts = db.query(DefectDraftRecord).filter(DefectDraftRecord.project_id.in_([p_id, "KAN", "PP"])).all()
    defect_drafts_responses = [_to_defect_draft_response(d) for d in drafts]

    # 7. Repeated Failures Detection
    repeated_failures = []
    failure_events = [e for e in events if e.event_type == EventType.TEST_FAILED.value]
    if len(failure_events) > 0:
        meta_first = metadata_from_json(failure_events[0].metadata_json)
        repeated_failures.append({
            "test_name": meta_first.get("suite", "OrderTestSuite.test_stripe_webhook"),
            "failure_count": len(failure_events),
            "linked_jira_key": meta_first.get("related_task_id", f"{p_id}-4"),
            "last_failed": failure_events[0].timestamp.isoformat(),
            "sample_error": meta_first.get("errors", ["AssertionError: 504 Timeout"])[0] if meta_first.get("errors") else "Timeout assertion error",
            "suggested_action": f"Create or link defect draft to Jira ticket {meta_first.get('related_task_id', f'{p_id}-4')}",
        })

    # Recent general events
    recent_events_resp = [_event_to_response(e) for e in events[:15]]

    return TesterOverviewResponse(
        project_id=p_id,
        project_name=p_name,
        total_test_runs=test_runs,
        total_tests=total_tests,
        passed=passed,
        failed=failed,
        skipped=skipped,
        pass_rate=pass_rate,
        test_runs_today=runs_today or 2,
        open_defects=open_defects_list,
        pending_regression_tests=pending_regressions,
        agent_sync_status=agent_sync_status,
        upcoming_tasks=upcoming_tasks,
        test_cases=test_case_responses,
        defect_drafts=defect_drafts_responses,
        repeated_failures=repeated_failures,
        recent_executions=recent_executions[:10],
        recent_events=recent_events_resp,
    )

"""Business logic for events, activity processing, and summaries."""

from datetime import date
from types import SimpleNamespace

from sqlalchemy.orm import Session

from backend.database import metadata_from_json, metadata_to_json
from backend.models.db_models import Agent, DefectRecord, Project, ProjectEventRecord, TaskRecord, User
from backend.models.schemas import (
    ActivitySummary,
    AgentResponse,
    DeveloperSummaryResponse,
    EventIngestRequest,
    EventResponse,
    HealthScorecard,
    ManagerDashboardResponse,
    new_id,
)
from backend.services.monitoring_status import get_monitoring_status
from shared.event_types import EventType, UserRole
from shared.summarizer import describe_event, narrative_summary, recent_activity_title, what_you_did
from shared.timeutil import DISPLAY_TZ_NAME, as_utc, display_day_bounds_utc_naive, today_in_display_tz, to_utc_naive


def _record_meta(record: ProjectEventRecord) -> dict:
    return metadata_from_json(record.metadata_json)


def _summary_event(record: ProjectEventRecord) -> SimpleNamespace:
    return SimpleNamespace(
        event_type=record.event_type,
        title=record.title,
        description=record.description,
        metadata=_record_meta(record),
    )


def _event_to_response(record: ProjectEventRecord) -> EventResponse:
    meta = _record_meta(record)
    return EventResponse(
        event_id=record.event_id,
        agent_id=record.agent_id,
        project_id=record.project_id,
        user_id=record.user_id,
        role=record.role,
        source=record.source,
        event_type=record.event_type,
        title=record.title,
        description=record.description,
        status=record.status,
        timestamp=as_utc(record.timestamp),
        metadata=meta,
        created_at=as_utc(record.created_at),
        human_description=describe_event(
            record.event_type, record.title, record.description, meta
        ),
        display_title=recent_activity_title(
            record.event_type, record.title, meta, record.description
        ),
    )


def create_event(db: Session, payload: EventIngestRequest) -> EventResponse:
    project = db.get(Project, payload.project_id)
    if not project:
        # Auto-create if missing for demo flexibility
        project = Project(
            project_id=payload.project_id,
            name=f"Project {payload.project_id}",
            folder_path="",
            owner_user_id=payload.user_id,
        )
        db.add(project)
        db.commit()

    user = db.get(User, payload.user_id)
    if not user:
        user = User(user_id=payload.user_id, name=f"User {payload.user_id}", role=payload.role.value)
        db.add(user)
        db.commit()

    # Touch agent if agent_id present
    if payload.agent_id:
        agent = db.query(Agent).filter(Agent.agent_id == payload.agent_id).first()
        if agent:
            from shared.timeutil import utc_now_naive
            agent.last_seen = utc_now_naive()
            agent.status = "ONLINE"

    event_id = payload.event_id or new_id("EVT")
    role_val = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    source_val = payload.source.value if hasattr(payload.source, "value") else str(payload.source)
    event_type_val = payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type)

    record = ProjectEventRecord(
        event_id=event_id,
        agent_id=payload.agent_id or "AGENT-DEFAULT",
        project_id=payload.project_id,
        user_id=payload.user_id,
        role=role_val,
        source=source_val,
        event_type=event_type_val,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        timestamp=to_utc_naive(payload.timestamp),
        metadata_json=metadata_to_json(payload.metadata),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        from backend.services.evidence_service import link_event_to_tasks
        link_event_to_tasks(db, record)
    except Exception:
        pass

    return _event_to_response(record)


def list_events(
    db: Session,
    project_id: str | None = None,
    agent_id: str | None = None,
    user_id: str | None = None,
    role: str | None = None,
    source: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[EventResponse]:
    query = db.query(ProjectEventRecord).order_by(ProjectEventRecord.timestamp.desc())
    if project_id:
        query = query.filter(ProjectEventRecord.project_id == project_id)
    if agent_id:
        query = query.filter(ProjectEventRecord.agent_id == agent_id)
    if user_id:
        query = query.filter(ProjectEventRecord.user_id == user_id)
    if role:
        query = query.filter(ProjectEventRecord.role == role)
    if source:
        query = query.filter(ProjectEventRecord.source == source)
    if event_type:
        query = query.filter(ProjectEventRecord.event_type == event_type)
    records = query.limit(limit).all()
    return [_event_to_response(r) for r in records]


def _summarize_events(events: list[ProjectEventRecord]) -> ActivitySummary:
    summary = ActivitySummary()
    summary.total_activities = len(events)
    for event in events:
        et = event.event_type
        if et == EventType.GIT_COMMIT.value:
            summary.commits += 1
        elif et == EventType.BUILD_FAILED.value:
            summary.build_failures += 1
        elif et == EventType.BUILD_SUCCEEDED.value:
            summary.build_successes += 1
        elif et == EventType.FILE_MODIFIED.value:
            summary.file_modifications += 1
        elif et == EventType.FILE_CREATED.value:
            summary.files_created += 1
        elif et in (EventType.GIT_BRANCH_CHANGED.value, EventType.GIT_BRANCH_CREATED.value):
            summary.branch_changes += 1
        elif et in (EventType.TEST_STARTED.value, EventType.TEST_COMPLETED.value):
            summary.test_runs += 1
        elif et == EventType.TEST_FAILED.value:
            summary.test_failures += 1
        elif et == EventType.BUG_REPORTED.value:
            summary.bugs_reported += 1
    return summary


def _current_status(events: list[ProjectEventRecord]) -> str:
    if not events:
        return "No activity recorded today"
    latest = max(events, key=lambda e: e.timestamp)
    if latest.event_type == EventType.BUILD_FAILED.value:
        return "Build issues detected — development in progress"
    if latest.event_type == EventType.BUILD_SUCCEEDED.value:
        return "Build healthy — development in progress"
    if latest.event_type == EventType.GIT_COMMIT.value:
        return "Active development — recent commits"
    if latest.event_type == EventType.TEST_FAILED.value:
        return "Testing active — failures detected"
    if latest.event_type == EventType.BUG_REPORTED.value:
        return "QA active — defect reported"
    return "Activity in progress"


def get_developer_summary(
    db: Session,
    project_id: str,
    user_id: str,
    summary_date: date | None = None,
) -> DeveloperSummaryResponse:
    project = db.get(Project, project_id) or db.query(Project).first()
    if not project:
        raise ValueError(f"Project '{project_id}' not found")

    day = summary_date or today_in_display_tz()
    start, end = display_day_bounds_utc_naive(day)
    events = (
        db.query(ProjectEventRecord)
        .filter(
            ProjectEventRecord.project_id == project.project_id,
            (ProjectEventRecord.user_id == user_id) | (ProjectEventRecord.role == "DEVELOPER"),
            ProjectEventRecord.timestamp >= start,
            ProjectEventRecord.timestamp <= end,
        )
        .order_by(ProjectEventRecord.timestamp.desc())
        .all()
    )
    if not events:
        events = (
            db.query(ProjectEventRecord)
            .filter(
                ProjectEventRecord.project_id == project.project_id,
                (ProjectEventRecord.user_id == user_id) | (ProjectEventRecord.role == "DEVELOPER"),
            )
            .order_by(ProjectEventRecord.timestamp.desc())
            .limit(20)
            .all()
        )

    activity = _summarize_events(events)
    monitoring = get_monitoring_status()
    summary_events = [_summary_event(e) for e in events]
    did = what_you_did(summary_events, activity)

    return DeveloperSummaryResponse(
        project_id=project.project_id,
        project_name=project.name,
        date=day.isoformat(),
        activity=activity,
        highlights=did,
        recent_events=[_event_to_response(e) for e in events[:10]],
        current_status=_current_status(events),
        narrative_summary=narrative_summary(summary_events, activity),
        what_you_did=did,
        monitoring_active=monitoring.get("active", True),
        display_timezone=DISPLAY_TZ_NAME,
    )


def _manager_signals(events: list[ProjectEventRecord]) -> list[str]:
    signals: list[str] = []

    if events:
        signals.append("[OK] Active project activity detected across agents")
    else:
        signals.append("[WARN] No project activity recorded yet")
        return signals

    recent_failures = [e for e in events if e.event_type == EventType.BUILD_FAILED.value][:3]
    for failure in recent_failures:
        module = metadata_from_json(failure.metadata_json).get("module", failure.title)
        signals.append(f"[WARN] Build failure detected — {module}")

    recent_test_failures = [e for e in events if e.event_type == EventType.TEST_FAILED.value]
    if recent_test_failures:
        signals.append(f"[WARN] {len(recent_test_failures)} recent test failure(s) reported by Tester Agent")

    recent_bugs = [e for e in events if e.event_type == EventType.BUG_REPORTED.value]
    if recent_bugs:
        signals.append(f"[WARN] {len(recent_bugs)} defect(s) logged by QA Agent")

    recent_commits = [e for e in events if e.event_type == EventType.GIT_COMMIT.value]
    if recent_commits:
        signals.append(f"[OK] {len(recent_commits)} Git commit(s) verified from Developer Agent")

    return signals


def _manager_narrative(events: list[ProjectEventRecord], activity: ActivitySummary) -> str:
    if not events:
        return "No project activity has been recorded yet. Waiting for team activity."

    summary_events = [_summary_event(e) for e in events]
    developer_text = narrative_summary(summary_events, activity)
    parts = ["Cross-role project activity is active.", developer_text]
    if activity.build_failures:
        parts.append(f"{activity.build_failures} build failure(s) require attention.")
    if activity.test_failures:
        parts.append(f"{activity.test_failures} test failure(s) reported by Tester.")
    if activity.bugs_reported:
        parts.append(f"{activity.bugs_reported} bug(s) reported by QA.")
    return " ".join(parts)


def get_manager_dashboard(db: Session, project_id: str) -> ManagerDashboardResponse:
    project = db.get(Project, project_id) or db.query(Project).first()
    if not project:
        raise ValueError(f"Project '{project_id}' not found")

    events = (
        db.query(ProjectEventRecord)
        .filter(ProjectEventRecord.project_id == project_id)
        .order_by(ProjectEventRecord.timestamp.desc())
        .limit(200)
        .all()
    )

    activity = _summarize_events(events)

    # 1. Team Agents Fleet
    agents = db.query(Agent).filter(Agent.project_id == project_id).all()
    team_agents = [AgentResponse.model_validate(a) for a in agents]

    # 2. Tasks Breakdown
    tasks = db.query(TaskRecord).filter(TaskRecord.project_id == project_id).all()
    completed_tasks = [t for t in tasks if t.status == "COMPLETED"]
    in_progress_tasks = [t for t in tasks if t.status == "IN_PROGRESS"]
    blocked_tasks = [t for t in tasks if t.status == "BLOCKED"]
    todo_tasks = [t for t in tasks if t.status == "TODO"]

    tasks_summary = {
        "total": len(tasks),
        "completed": len(completed_tasks),
        "in_progress": len(in_progress_tasks),
        "blocked": len(blocked_tasks),
        "todo": len(todo_tasks),
    }

    # 3. Defect & QA Summary
    defects = db.query(DefectRecord).filter(DefectRecord.project_id == project_id).all()
    open_defects = [d for d in defects if d.status in ("OPEN", "REOPENED")]
    high_sev_defects = [d for d in open_defects if d.severity in ("HIGH", "CRITICAL")]

    # 4. Explainable Health Scorecard Computation
    tasks_status = f"{len(completed_tasks)} completed, {len(in_progress_tasks)} in progress"
    if blocked_tasks:
        tasks_status += f", [WARN] {len(blocked_tasks)} blocked"

    dev_status = "[OK] Builds healthy and commits verified"
    if activity.build_failures > 0:
        dev_status = f"[WARN] {activity.build_failures} build failure(s) recorded"

    testing_status = "[OK] Tests passing"
    if activity.test_failures > 0:
        testing_status = f"[WARN] {activity.test_failures} test failure(s) detected in recent runs"

    qa_status = "[OK] No high severity defects"
    if high_sev_defects:
        qa_status = f"[WARN] {len(high_sev_defects)} high/critical defect(s) pending"
    elif open_defects:
        qa_status = f"{len(open_defects)} open defect(s)"

    dep_status = f"[WARN] {len(blocked_tasks)} blocked task: {blocked_tasks[0].title}" if blocked_tasks else "[OK] No blocked tasks"

    # Overall calculation
    is_critical = len(high_sev_defects) > 0 or activity.build_failures > 2
    is_attention = len(blocked_tasks) > 0 or activity.test_failures > 0 or len(open_defects) > 0
    overall = "CRITICAL" if is_critical else ("ATTENTION_REQUIRED" if is_attention else "HEALTHY")

    health = HealthScorecard(
        overall_status=overall,
        tasks_status=tasks_status,
        development_status=dev_status,
        testing_status=testing_status,
        qa_status=qa_status,
        dependencies_status=dep_status,
    )

    from backend.services.risk_service import evaluate_project_risks
    active_risks = evaluate_project_risks(db, project_id)

    return ManagerDashboardResponse(
        project_id=project.project_id,
        project_name=project.name,
        activity=activity,
        recent_events=[_event_to_response(e) for e in events[:20]],
        signals=_manager_signals(events),
        narrative_summary=_manager_narrative(events, activity),
        health=health,
        team_agents=team_agents,
        tasks_summary=tasks_summary,
        active_risks=active_risks,
    )



def get_tester_metrics(db: Session, project_id: str) -> dict:
    project = db.get(Project, project_id) or db.query(Project).first()
    if not project:
        raise ValueError(f"Project '{project_id}' not found")

    events = (
        db.query(ProjectEventRecord)
        .filter(
            ProjectEventRecord.project_id == project_id,
            ProjectEventRecord.source == "TEST",
        )
        .order_by(ProjectEventRecord.timestamp.desc())
        .limit(100)
        .all()
    )

    test_runs = 0
    passed = 0
    failed = 0
    skipped = 0

    for e in events:
        if e.event_type == EventType.TEST_COMPLETED.value:
            meta = metadata_from_json(e.metadata_json)
            test_runs += 1
            passed += meta.get("passed", 0)
            failed += meta.get("failed", 0)
            skipped += meta.get("skipped", 0)

    total_tests = passed + failed + skipped
    pass_rate = round((passed / total_tests * 100), 1) if total_tests > 0 else (100.0 if test_runs > 0 and failed == 0 else 0.0)

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_test_runs": test_runs,
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": pass_rate,
        "recent_events": [_event_to_response(e) for e in events[:20]],
    }


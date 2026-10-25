"""QA and Defect Tracking Service for ProjectPulse AI."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from backend.database import metadata_to_json
from backend.models.db_models import DefectRecord, Project, ProjectEventRecord
from shared.event_types import EventSource, EventType, UserRole
from shared.timeutil import utc_now_naive


def list_defects(db: Session, project_id: str | None = None) -> list[DefectRecord]:
    query = db.query(DefectRecord).order_by(DefectRecord.created_at.desc())
    if project_id:
        query = query.filter(DefectRecord.project_id == project_id)
    return query.all()


def report_defect(
    db: Session,
    project_id: str,
    title: str,
    description: str = "",
    severity: str = "HIGH",
    priority: str = "HIGH",
    related_task_id: str = "",
    reported_by: str = "QA",
) -> DefectRecord:
    defect_id = f"DEF-{uuid4().hex[:6].upper()}"
    defect = DefectRecord(
        defect_id=defect_id,
        project_id=project_id,
        title=title,
        description=description,
        severity=severity.upper(),
        priority=priority.upper(),
        status="OPEN",
        related_task_id=related_task_id,
        reported_by=reported_by,
        created_at=utc_now_naive(),
    )
    db.add(defect)

    # Ingest corresponding BUG_REPORTED event
    now = utc_now_naive()
    evt = ProjectEventRecord(
        event_id=f"EVT-{uuid4().hex[:8].upper()}",
        agent_id="AGENT-QA-001",
        project_id=project_id,
        user_id="QA-001",
        role=UserRole.QA.value,
        source=EventSource.QA.value,
        event_type=EventType.BUG_REPORTED.value,
        title=f"[{severity.upper()}] Defect: {title}",
        description=description or f"Logged by {reported_by}",
        status="ERROR" if severity.upper() in ("HIGH", "CRITICAL") else "WARNING",
        timestamp=now,
        metadata_json=metadata_to_json({
            "defect_id": defect_id,
            "severity": severity.upper(),
            "priority": priority.upper(),
            "related_task": related_task_id,
            "reported_by": reported_by,
        }),
    )
    db.add(evt)
    db.commit()
    db.refresh(defect)
    return defect


def update_defect_status(db: Session, defect_id: str, new_status: str) -> DefectRecord | None:
    defect = db.query(DefectRecord).filter(DefectRecord.defect_id == defect_id).first()
    if not defect:
        return None

    defect.status = new_status.upper()
    defect.updated_at = utc_now_naive()

    # Determine event type
    status_map = {
        "VERIFIED": EventType.BUG_VERIFIED.value,
        "CLOSED": EventType.BUG_CLOSED.value,
        "REOPENED": EventType.BUG_REOPENED.value,
    }
    event_type = status_map.get(new_status.upper(), EventType.BUG_VERIFIED.value)
    now = utc_now_naive()

    evt = ProjectEventRecord(
        event_id=f"EVT-{uuid4().hex[:8].upper()}",
        agent_id="AGENT-QA-001",
        project_id=defect.project_id,
        user_id="QA-001",
        role=UserRole.QA.value,
        source=EventSource.QA.value,
        event_type=event_type,
        title=f"Defect {new_status.capitalize()}: {defect.defect_id} - {defect.title}",
        description=f"Status changed to {new_status.upper()}",
        status="SUCCESS" if new_status.upper() == "CLOSED" else "WARNING",
        timestamp=now,
        metadata_json=metadata_to_json({
            "defect_id": defect.defect_id,
            "new_status": new_status.upper(),
        }),
    )
    db.add(evt)
    db.commit()
    db.refresh(defect)
    return defect


def record_qa_verdict(db: Session, project_id: str, approved: bool, build_ref: str, notes: str = ""):
    now = utc_now_naive()
    event_type = EventType.QA_APPROVED.value if approved else EventType.QA_REJECTED.value
    status = "SUCCESS" if approved else "ERROR"
    verdict_text = "Approved" if approved else "Rejected"

    evt = ProjectEventRecord(
        event_id=f"EVT-{uuid4().hex[:8].upper()}",
        agent_id="AGENT-QA-001",
        project_id=project_id,
        user_id="QA-001",
        role=UserRole.QA.value,
        source=EventSource.QA.value,
        event_type=event_type,
        title=f"Build {verdict_text}: {build_ref}",
        description=notes or f"Build candidate {build_ref} {verdict_text.lower()} by QA",
        status=status,
        timestamp=now,
        metadata_json=metadata_to_json({"build_ref": build_ref, "approved": approved, "notes": notes}),
    )
    db.add(evt)
    db.commit()
    return {"status": "ok", "verdict": verdict_text, "build_ref": build_ref}


def get_qa_metrics(db: Session, project_id: str) -> dict:
    project = db.get(Project, project_id) or db.query(Project).first()
    if not project:
        raise ValueError(f"Project '{project_id}' not found")

    defects = db.query(DefectRecord).filter(DefectRecord.project_id == project_id).all()
    open_defects = [d for d in defects if d.status in ("OPEN", "REOPENED")]
    high_sev = [d for d in open_defects if d.severity in ("HIGH", "CRITICAL")]
    verified = [d for d in defects if d.status == "VERIFIED"]
    closed = [d for d in defects if d.status == "CLOSED"]

    # Recent QA events
    qa_events = (
        db.query(ProjectEventRecord)
        .filter(ProjectEventRecord.project_id == project_id, ProjectEventRecord.source == "QA")
        .order_by(ProjectEventRecord.timestamp.desc())
        .limit(20)
        .all()
    )
    from backend.services.event_service import _event_to_response

    # Latest QA verdict
    latest_verdict = "PENDING"
    for e in qa_events:
        if e.event_type == EventType.QA_APPROVED.value:
            latest_verdict = "APPROVED"
            break
        elif e.event_type == EventType.QA_REJECTED.value:
            latest_verdict = "REJECTED"
            break

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_defects": len(defects),
        "open_defects": len(open_defects),
        "high_severity_defects": len(high_sev),
        "verified_defects": len(verified),
        "closed_defects": len(closed),
        "latest_verdict": latest_verdict,
        "defects": [
            {
                "defect_id": d.defect_id,
                "title": d.title,
                "description": d.description,
                "severity": d.severity,
                "priority": d.priority,
                "status": d.status,
                "related_task_id": d.related_task_id,
                "reported_by": d.reported_by,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in defects
        ],
        "recent_events": [_event_to_response(e) for e in qa_events],
    }

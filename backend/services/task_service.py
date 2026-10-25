"""Service for managing normalized tasks (from PM tools or manual)."""

from sqlalchemy.orm import Session
from backend.models.db_models import Project, TaskRecord
from backend.models.schemas import TaskCreate


from shared.timeutil import utc_now_naive
import json


def create_or_update_task(db: Session, payload: TaskCreate) -> TaskRecord:
    external_id = payload.external_task_id
    if not external_id:
        existing_count = db.query(TaskRecord).filter(TaskRecord.project_id == payload.project_id).count()
        external_id = f"{payload.project_id or 'PP'}-{existing_count + 1}"

    task = (
        db.query(TaskRecord)
        .filter(
            TaskRecord.project_id == payload.project_id,
            TaskRecord.external_task_id == external_id,
        )
        .first()
    )
    deps_str = payload.dependencies if isinstance(payload.dependencies, str) else json.dumps(payload.dependencies or [])
    labels_str = payload.labels if isinstance(payload.labels, str) else json.dumps(payload.labels or [])
    components_str = payload.components if isinstance(payload.components, str) else json.dumps(payload.components or [])

    if not task:
        task = TaskRecord(
            project_id=payload.project_id,
            source=payload.source or "LOCAL_BOARD",
            external_task_id=external_id,
            title=payload.title,
            description=payload.description or "",
            status=payload.status,
            priority=payload.priority,
            assignee=payload.assignee or "",
            reporter=getattr(payload, "reporter", "") or "",
            due_date=payload.due_date,
            sprint=getattr(payload, "sprint", "Sprint 1") or "Sprint 1",
            dependencies=deps_str,
            labels=labels_str,
            components=components_str,
            jira_url=getattr(payload, "jira_url", "") or "",
            issue_type=getattr(payload, "issue_type", "Task") or "Task",
            story_points=getattr(payload, "story_points", None),
            parent_key=getattr(payload, "parent_key", "") or "",
            last_synced_at=utc_now_naive(),
        )
        db.add(task)
    else:
        task.title = payload.title
        task.description = payload.description or ""
        task.status = payload.status
        task.priority = payload.priority
        task.assignee = payload.assignee or ""
        if getattr(payload, "reporter", None):
            task.reporter = payload.reporter
        task.due_date = payload.due_date
        if getattr(payload, "sprint", None):
            task.sprint = payload.sprint
        if deps_str != "[]":
            task.dependencies = deps_str
        if labels_str != "[]":
            task.labels = labels_str
        if components_str != "[]":
            task.components = components_str
        if getattr(payload, "jira_url", None):
            task.jira_url = payload.jira_url
        if getattr(payload, "issue_type", None):
            task.issue_type = payload.issue_type
        if getattr(payload, "story_points", None) is not None:
            task.story_points = payload.story_points
        if getattr(payload, "parent_key", None):
            task.parent_key = payload.parent_key
        task.last_synced_at = utc_now_naive()
        task.updated_at = utc_now_naive()

    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, project_id: str | None = None) -> list[TaskRecord]:
    query = db.query(TaskRecord).order_by(TaskRecord.created_at.desc())
    if project_id:
        query = query.filter(TaskRecord.project_id == project_id)
    return query.all()

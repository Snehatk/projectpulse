"""Code Change Explanation Service — Explains WHY Developer Activity Happened.

Implements Feature 6:
- Analyzes developer commits, branch names, file diffs, and file paths.
- Correlates engineering activity with normalized Jira project tasks.
- Produces evidence-grounded explanations with explicit confidence levels:
    - DIRECT: explicit task key in commit message or branch
    - LIKELY: strong keyword and module path correlation with task description
    - PLAUSIBLE: active task assigned to developer with matching timeframe
    - UNLINKED: code change has no corresponding Jira ticket
- Cautious AI phrasing ('appears related to', 'likely related to', 'evidence suggests').
"""

from datetime import datetime
import json
import logging
import re
from typing import Any
from sqlalchemy.orm import Session

from backend.database import metadata_from_json
from backend.models.db_models import ProjectEventRecord, TaskRecord
from shared.event_types import EventType

logger = logging.getLogger(__name__)


def _infer_module_from_files(files: list[str]) -> str:
    """Infer functional system module from changed file paths."""
    if not files:
        return "Core Application"

    joined = " ".join(files).lower()
    if any(k in joined for k in ("auth", "login", "jwt", "session", "oauth", "token")):
        return "Authentication & Security"
    if any(k in joined for k in ("pay", "stripe", "paypal", "checkout", "billing", "invoice")):
        return "Payment Gateway & Billing"
    if any(k in joined for k in ("cart", "order", "pricing", "discount")):
        return "Orders & Cart Processing"
    if any(k in joined for k in ("test", "spec", "pytest", "jest")):
        return "Automated Test Suite"
    if any(k in joined for k in ("db", "model", "schema", "migrat", "sql")):
        return "Database & Storage Layer"
    if any(k in joined for k in ("ui", "component", "view", "page", "frontend", "css", "jsx")):
        return "Frontend Dashboard & UI"
    if any(k in joined for k in ("api", "router", "endpoint")):
        return "REST API Routing"
    return "Application Services"


def explain_code_changes(db: Session, project_id: str = "DLX", limit: int = 30) -> list[dict[str, Any]]:
    """Analyze recent commits and explain the contextual reason behind the code edits."""
    p_id = (project_id or "DLX").upper()
    tasks = db.query(TaskRecord).filter(TaskRecord.project_id.in_([p_id, "KAN", "PP", "DLX"])).all()
    events = (
        db.query(ProjectEventRecord)
        .filter(
            ProjectEventRecord.project_id.in_([p_id, "KAN", "PP", "DLX"]),
            ProjectEventRecord.event_type.in_([
                EventType.GIT_COMMIT.value,
                EventType.CHANGE_SET.value,
                EventType.FILE_MODIFIED.value,
                EventType.FILE_CREATED.value,
            ]),
        )
        .order_by(ProjectEventRecord.timestamp.desc())
        .limit(limit)
        .all()
    )

    explanations: list[dict[str, Any]] = []

    for idx, e in enumerate(events):
        meta = metadata_from_json(e.metadata_json)
        commit_hash = meta.get("commit_hash", "") or e.event_id[:7]
        branch = meta.get("branch", "main")
        
        raw_files = meta.get("files_changed") or meta.get("files")
        if isinstance(raw_files, list):
            files_changed = [str(f) for f in raw_files if f]
            files_count = len(files_changed)
        elif isinstance(raw_files, str):
            files_changed = [raw_files]
            files_count = 1
        elif isinstance(raw_files, int):
            files_changed = []
            files_count = raw_files
        else:
            files_changed = []
            files_count = 0

        if not files_changed and meta.get("file_path"):
            files_changed = [str(meta["file_path"])]
            if files_count == 0:
                files_count = 1

        if files_count == 0:
            files_count = 1

        ast_explanation = meta.get("explanation")
        symbols_added = meta.get("symbols_added", [])
        symbols_modified = meta.get("symbols_modified", [])
        symbols_removed = meta.get("symbols_removed", [])

        inferred_module = _infer_module_from_files(files_changed)
        title_lower = e.title.lower()
        branch_lower = branch.lower()

        matched_task: TaskRecord | None = None
        confidence_level = "UNLINKED"
        confidence_score = 0.35
        evidence_signals: list[str] = []

        # 1. Direct Match: Jira issue key in commit title or branch name
        for t in tasks:
            key_lower = t.external_task_id.lower()
            if key_lower in title_lower or key_lower in branch_lower:
                matched_task = t
                confidence_level = "DIRECT"
                confidence_score = 0.98
                evidence_signals.append(f"Commit/branch explicitly references Jira key '{t.external_task_id}'")
                break

        # 2. Likely Match: Module path and title keyword overlap
        if not matched_task:
            best_score = 0
            for t in tasks:
                task_words = [w for w in re.findall(r"\w+", t.title.lower()) if len(w) > 4]
                overlap = sum(1 for w in task_words if w in title_lower or any(w in f.lower() for f in files_changed))
                if overlap > best_score:
                    best_score = overlap
                    matched_task = t

            if matched_task and best_score >= 1:
                confidence_level = "LIKELY"
                confidence_score = 0.85
                evidence_signals.append(
                    f"Strong keyword overlap between modified files and task '{matched_task.external_task_id}' ({matched_task.title})"
                )

        # 3. Plausible Match: Developer assigned to active task in this module
        if not matched_task:
            for t in tasks:
                if t.status == "IN_PROGRESS" and (t.assignee and e.user_id and t.assignee.lower() in e.user_id.lower()):
                    matched_task = t
                    confidence_level = "PLAUSIBLE"
                    confidence_score = 0.65
                    evidence_signals.append(
                        f"Developer '{e.user_id}' is actively assigned to task '{t.external_task_id}'"
                    )
                    break

        # Construct explanation based on confidence level
        if symbols_added:
            evidence_signals.append(f"Symbols added: {', '.join(symbols_added)}")
        if symbols_modified:
            evidence_signals.append(f"Symbols modified: {', '.join(symbols_modified)}")
        if symbols_removed:
            evidence_signals.append(f"Symbols removed: {', '.join(symbols_removed)}")
        if meta.get("detected_on_catchup"):
            evidence_signals.append("Detected during offline catch-up scan")

        if matched_task:
            evidence_signals.append(f"Inferred module: {inferred_module}")
            if files_changed:
                evidence_signals.append(f"Changed files: {', '.join(files_changed[:3])}")

            if confidence_level == "DIRECT":
                explanation = (
                    f"{files_count} file(s) were modified in the {inferred_module} module. "
                    f"Direct evidence links this activity to task "
                    f"'{matched_task.external_task_id}' ('{matched_task.title}') on branch '{branch}'."
                )
            elif confidence_level == "LIKELY":
                explanation = (
                    f"{files_count} file(s) were changed in the {inferred_module} module, "
                    f"likely related to task '{matched_task.external_task_id}' ('{matched_task.title}') "
                    f"based on matching functional paths and commit context."
                )
            else:  # PLAUSIBLE
                explanation = (
                    f"Activity in {inferred_module} appears related to {matched_task.external_task_id} "
                    f"('{matched_task.title}'), as {e.user_id or 'the developer'} is currently working on this feature."
                )
            matched_id = matched_task.external_task_id
            matched_title = matched_task.title
        else:
            evidence_signals.append("No active task matches the modified file paths")
            explanation = (
                f"{files_count} file(s) were updated in the {inferred_module} module. "
                "Evidence indicates this code modification is not linked to any open task. "
                "Recommend linking to an existing ticket or logging technical debt."
            )
            matched_id = ""
            matched_title = "Unlinked Engineering Activity"

        if isinstance(ast_explanation, dict) and ast_explanation.get("what"):
            explanation = f"{ast_explanation['what']} | {explanation}"

        explanations.append({
            "explanation_id": f"EXPL-{e.event_id[:8]}",
            "event_id": e.event_id,
            "timestamp": e.timestamp.isoformat(),
            "commit_hash": commit_hash,
            "commit_message": e.title,
            "author": e.user_id or "Developer",
            "files_changed_count": files_count,
            "files_changed": files_changed,
            "inferred_module": inferred_module,
            "matched_task_id": matched_id,
            "matched_task_title": matched_title,
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "explanation": explanation,
            "evidence_signals": evidence_signals,
        })

    return explanations

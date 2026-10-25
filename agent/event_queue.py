"""Persistent SQLite Event Queue and Local History for ProjectPulse Desktop Agent.

Guarantees that telemetry events survive:
- Backend downtime / offline mode ("Local Only — Not Synced")
- Network disconnects and flaky Wi-Fi
- Agent crashes and machine reboots
- Unhandled collector exceptions

Features:
1. `queued_events`: FIFO dispatch queue. Deleted ONLY upon HTTP 200/201 response.
2. `local_event_history`: Searchable permanent event history preserved across restarts.
3. `work_sessions`: Recorded session intervals with active vs. idle time.
4. Duplicate prevention via UNIQUE event_id constraint.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable

from shared.events import ProjectEventCreate

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_DB = Path(__file__).resolve().parent / "config" / "agent_queue.db"


class PersistentEventQueue:
    """Thread-safe, crash-resilient SQLite event queue and history store."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_QUEUE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            with self._db() as conn:
                # 1. Outbound dispatch queue
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queued_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        event_type TEXT NOT NULL,
                        event_json TEXT NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                # 2. Permanent searchable local history
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS local_event_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        event_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        status TEXT DEFAULT 'INFO',
                        relative_path TEXT DEFAULT '',
                        metadata_json TEXT DEFAULT '{}',
                        timestamp TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                # 3. Work sessions
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS work_sessions (
                        session_id TEXT PRIMARY KEY,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        observed_session_seconds REAL DEFAULT 0.0,
                        active_interaction_seconds REAL DEFAULT 0.0,
                        idle_seconds REAL DEFAULT 0.0,
                        estimated_editing_seconds REAL DEFAULT 0.0,
                        verified_task_seconds REAL DEFAULT 0.0,
                        workspace_path TEXT DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()

    def enqueue(self, event: ProjectEventCreate) -> None:
        """Atomically persist event to both outbound queue and local history."""
        with self._lock:
            try:
                event_dict = event.model_dump() if hasattr(event, "model_dump") else dict(event)
                # Convert timestamps to isoformat if needed
                for k, v in event_dict.items():
                    if isinstance(v, datetime):
                        event_dict[k] = v.isoformat()

                event_id = event_dict.get("event_id") or ""
                raw_type = event_dict.get("event_type", "UNKNOWN")
                event_type = getattr(raw_type, "value", str(raw_type))
                raw_src = event_dict.get("source", "UNKNOWN")
                source = getattr(raw_src, "value", str(raw_src))
                project_id = str(event_dict.get("project_id", ""))
                user_id = str(event_dict.get("user_id", ""))
                title = str(event_dict.get("title", ""))
                description = str(event_dict.get("description", ""))
                status = str(event_dict.get("status", "INFO"))
                timestamp = str(event_dict.get("timestamp") or datetime.now(timezone.utc).isoformat())
                metadata = event_dict.get("metadata") or {}
                rel_path = metadata.get("relative_path") or metadata.get("file_path") or metadata.get("path") or ""

                event_json = json.dumps(event_dict)
                now_str = datetime.now(timezone.utc).isoformat()

                with self._db() as conn:
                    # Insert to outbound dispatch queue
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO queued_events (event_id, event_type, event_json, retry_count, created_at)
                        VALUES (?, ?, ?, 0, ?)
                        """,
                        (event_id, event_type, event_json, now_str),
                    )
                    # Insert to permanent local history
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO local_event_history (
                            event_id, event_type, source, project_id, user_id,
                            title, description, status, relative_path, metadata_json,
                            timestamp, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            event_type,
                            source,
                            project_id,
                            user_id,
                            title,
                            description,
                            status,
                            rel_path,
                            json.dumps(metadata),
                            timestamp,
                            now_str,
                        ),
                    )
                    conn.commit()
                logger.debug("Event persisted to SQLite queue and history: %s (%s)", event_id, event_type)
            except Exception as exc:
                logger.error("Failed to persist event to SQLite queue: %s", exc)

    def flush(self, send_fn: Callable[[dict], bool], batch_size: int = 50) -> int:
        """Attempt to send queued events in FIFO order. Deletes ONLY confirmed events."""
        with self._lock:
            sent_count = 0
            try:
                with self._db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, event_id, event_json, retry_count FROM queued_events ORDER BY id ASC LIMIT ?",
                        (batch_size,),
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        return 0

                    for row in rows:
                        row_id = row["id"]
                        event_id = row["event_id"]
                        raw_json = row["event_json"]
                        retries = row["retry_count"]

                        try:
                            event_data = json.loads(raw_json)
                            success = send_fn(event_data)
                        except Exception as exc:
                            logger.warning("send_fn raised exception for event %s: %s", event_id, exc)
                            success = False

                        if success:
                            conn.execute("DELETE FROM queued_events WHERE id = ?", (row_id,))
                            conn.commit()
                            sent_count += 1
                        else:
                            conn.execute(
                                "UPDATE queued_events SET retry_count = ? WHERE id = ?",
                                (retries + 1, row_id),
                            )
                            conn.commit()
                            logger.info(
                                "Network dispatch halted at event %s (will retry on next sync cycle).",
                                event_id,
                            )
                            break
            except Exception as exc:
                logger.error("Error during persistent queue flush: %s", exc)

            if sent_count > 0:
                logger.info("Successfully flushed %d queued event(s) to backend.", sent_count)
            return sent_count

    @property
    def pending_count(self) -> int:
        """Count of un-sent events currently stored in the outbound queue."""
        with self._lock:
            try:
                with self._db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM queued_events")
                    row = cursor.fetchone()
                    return row[0] if row else 0
            except Exception:
                return 0

    @property
    def total_history_count(self) -> int:
        """Count of total events stored in local permanent history."""
        with self._lock:
            try:
                with self._db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM local_event_history")
                    row = cursor.fetchone()
                    return row[0] if row else 0
            except Exception:
                return 0

    def search_history(
        self,
        query: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search local persistent event history with rich filters."""
        with self._lock:
            clauses = []
            params = []

            if query:
                clauses.append("(title LIKE ? OR description LIKE ? OR relative_path LIKE ?)")
                q_wild = f"%{query}%"
                params.extend([q_wild, q_wild, q_wild])

            if event_type:
                clauses.append("event_type = ?")
                params.append(getattr(event_type, "value", str(event_type)))

            if source:
                clauses.append("source = ?")
                params.append(getattr(source, "value", str(source)))

            if start_date:
                clauses.append("timestamp >= ?")
                params.append(start_date)

            if end_date:
                clauses.append("timestamp <= ?")
                params.append(end_date)

            where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"SELECT * FROM local_event_history {where_str} ORDER BY id DESC LIMIT ?"
            params.append(limit)

            try:
                with self._db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, tuple(params))
                    rows = cursor.fetchall()
                    results = []
                    for r in rows:
                        item = dict(r)
                        if item.get("metadata_json"):
                            try:
                                item["metadata"] = json.loads(item["metadata_json"])
                            except Exception:
                                item["metadata"] = {}
                        results.append(item)
                    return results
            except Exception as exc:
                logger.error("Error searching local event history: %s", exc)
                return []

    def save_work_session(self, metrics: dict[str, Any]) -> None:
        """Persist or update work session record."""
        with self._lock:
            session_id = metrics.get("session_id")
            if not session_id:
                return
            now_str = datetime.now(timezone.utc).isoformat()
            try:
                with self._db() as conn:
                    conn.execute(
                        """
                        INSERT INTO work_sessions (
                            session_id, start_time, end_time,
                            observed_session_seconds, active_interaction_seconds,
                            idle_seconds, estimated_editing_seconds, verified_task_seconds,
                            workspace_path, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            end_time = excluded.end_time,
                            observed_session_seconds = excluded.observed_session_seconds,
                            active_interaction_seconds = excluded.active_interaction_seconds,
                            idle_seconds = excluded.idle_seconds,
                            estimated_editing_seconds = excluded.estimated_editing_seconds,
                            verified_task_seconds = excluded.verified_task_seconds,
                            workspace_path = excluded.workspace_path
                        """,
                        (
                            session_id,
                            metrics.get("session_start_time", now_str),
                            metrics.get("last_activity_time", now_str),
                            metrics.get("observed_session_seconds", 0.0),
                            metrics.get("active_interaction_seconds", 0.0),
                            metrics.get("idle_seconds", 0.0),
                            metrics.get("estimated_editing_seconds", 0.0),
                            metrics.get("verified_task_seconds", 0.0),
                            metrics.get("approved_workspace", ""),
                            now_str,
                        ),
                    )
                    conn.commit()
            except Exception as exc:
                logger.error("Error saving work session to SQLite: %s", exc)

    def get_recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent work sessions."""
        with self._lock:
            try:
                with self._db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM work_sessions ORDER BY created_at DESC LIMIT ?", (limit,))
                    return [dict(r) for r in cursor.fetchall()]
            except Exception as exc:
                logger.error("Error retrieving work sessions: %s", exc)
                return []

    def clear(self) -> None:
        """Purge all queued events."""
        with self._lock:
            try:
                with self._db() as conn:
                    conn.execute("DELETE FROM queued_events")
                    conn.commit()
            except Exception as exc:
                logger.error("Failed to clear persistent queue: %s", exc)


# Backwards compatibility alias
EventQueue = PersistentEventQueue
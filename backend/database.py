"""SQLAlchemy database setup, session management, and auto-migration."""

import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_data_dir() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)


_ensure_data_dir()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_sqlite_migrations() -> None:
    """Safely apply missing columns if SQLite database existed from prior version."""
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        # Check users table
        try:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
            if columns:
                if "external_id" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN external_id VARCHAR(64)"))
                if "email" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(120)"))
                if "password_hash" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                if "is_active" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                if "last_login" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))
        except Exception:
            pass

        # Check projects table
        try:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(projects)")).fetchall()]
            if columns:
                if "description" not in columns:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN description TEXT DEFAULT ''"))
                if "updated_at" not in columns:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN updated_at DATETIME"))
        except Exception:
            pass

        # Check project_events table
        try:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(project_events)")).fetchall()]
            if columns and "agent_id" not in columns:
                conn.execute(text("ALTER TABLE project_events ADD COLUMN agent_id VARCHAR(64) DEFAULT 'AGENT-DEFAULT'"))
        except Exception:
            pass

        # Check tasks table
        try:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()]
            if columns:
                if "sprint" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN sprint VARCHAR(128) DEFAULT 'Sprint 1'"))
                if "dependencies" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN dependencies TEXT DEFAULT '[]'"))
                if "labels" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN labels TEXT DEFAULT '[]'"))
                if "reporter" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN reporter VARCHAR(255) DEFAULT ''"))
                if "started_at" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN started_at DATETIME"))
                if "completed_at" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN completed_at DATETIME"))
                if "issue_type" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN issue_type VARCHAR(64) DEFAULT 'Task'"))
                if "story_points" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN story_points FLOAT"))
                if "parent_key" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN parent_key VARCHAR(128) DEFAULT ''"))
                if "components" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN components TEXT DEFAULT '[]'"))
                if "jira_url" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN jira_url VARCHAR(512) DEFAULT ''"))
                if "last_synced_at" not in columns:
                    conn.execute(text("ALTER TABLE tasks ADD COLUMN last_synced_at DATETIME"))
        except Exception:
            pass

        # Check jira_connections table
        try:
            columns = [row[1] for row in conn.execute(text("PRAGMA table_info(jira_connections)")).fetchall()]
            if columns:
                if "email" not in columns:
                    conn.execute(text("ALTER TABLE jira_connections ADD COLUMN email VARCHAR(255) DEFAULT ''"))
                if "status" not in columns:
                    conn.execute(text("ALTER TABLE jira_connections ADD COLUMN status VARCHAR(32) DEFAULT 'CONNECTED'"))
                if "error_message" not in columns:
                    conn.execute(text("ALTER TABLE jira_connections ADD COLUMN error_message TEXT"))
                if "last_tested_at" not in columns:
                    conn.execute(text("ALTER TABLE jira_connections ADD COLUMN last_tested_at DATETIME"))
                if "last_synced_at" not in columns:
                    conn.execute(text("ALTER TABLE jira_connections ADD COLUMN last_synced_at DATETIME"))
        except Exception:
            pass


def init_db() -> None:
    from backend.models import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_migrations()


def metadata_to_json(data: dict) -> str:
    return json.dumps(data)


def metadata_from_json(raw: str | None) -> dict:
    if not raw:
        return {}
    return json.loads(raw)

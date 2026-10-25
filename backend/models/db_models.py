"""SQLAlchemy ORM models for ProjectPulse AI."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from shared.timeutil import utc_now_naive


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Integer, default=1)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="DEVELOPER")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    events: Mapped[list["ProjectEventRecord"]] = relationship(back_populates="user")
    agents: Mapped[list["Agent"]] = relationship(back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    folder_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    owner: Mapped["User"] = relationship(back_populates="projects")
    events: Mapped[list["ProjectEventRecord"]] = relationship(back_populates="project")
    agents: Mapped[list["Agent"]] = relationship(back_populates="project")
    tasks: Mapped[list["TaskRecord"]] = relationship(back_populates="project")
    external_connections: Mapped[list["ProjectExternal"]] = relationship(back_populates="project")
    defects: Mapped[list["DefectRecord"]] = relationship(back_populates="project")
    evidence_items: Mapped[list["EvidenceRecord"]] = relationship(back_populates="project")
    sync_runs: Mapped[list["SyncRunRecord"]] = relationship()


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="DEVELOPER")
    machine_name: Mapped[str] = mapped_column(String(255), default="LOCAL-PC")
    machine_id: Mapped[str] = mapped_column(String(255), default="LOCAL-MACHINE")
    status: Mapped[str] = mapped_column(String(32), default="ONLINE")
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    user: Mapped["User"] = relationship(back_populates="agents")
    project: Mapped["Project"] = relationship(back_populates="agents")


class ProjectEventRecord(Base):
    __tablename__ = "project_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), default="AGENT-DEFAULT", nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="INFO")
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    project: Mapped["Project"] = relationship(back_populates="events")
    user: Mapped["User"] = relationship(back_populates="events")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="MANUAL")
    external_task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="TODO")  # TODO, IN_PROGRESS, BLOCKED, COMPLETED
    priority: Mapped[str] = mapped_column(String(32), default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    assignee: Mapped[str] = mapped_column(String(255), default="")
    reporter: Mapped[str] = mapped_column(String(255), default="")
    due_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sprint: Mapped[str] = mapped_column(String(128), default="Sprint 1")
    dependencies: Mapped[str] = mapped_column(Text, default="[]")
    labels: Mapped[str] = mapped_column(Text, default="[]")
    issue_type: Mapped[str] = mapped_column(String(64), default="Task")
    story_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    parent_key: Mapped[str] = mapped_column(String(128), default="")
    components: Mapped[str] = mapped_column(Text, default="[]")
    jira_url: Mapped[str] = mapped_column(String(512), default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship(back_populates="tasks")


class JiraConnectionRecord(Base):
    __tablename__ = "jira_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, default="KAN")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    project_key: Mapped[str] = mapped_column(String(64), nullable=False, default="KAN")
    project_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email_identifier: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), default="CONNECTED")
    connected: Mapped[bool] = mapped_column(Integer, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class AIRiskRecord(Base):
    __tablename__ = "ai_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), default="")
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="QUALITY")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProjectExternal(Base):
    __tablename__ = "projects_external"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # JIRA, MONDAY, ASANA, TRELLO, CLICKUP, LINEAR
    external_project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    connection_status: Mapped[str] = mapped_column(String(32), default="CONNECTED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship(back_populates="external_connections")


class DefectRecord(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    defect_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    priority: Mapped[str] = mapped_column(String(32), default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    status: Mapped[str] = mapped_column(String(32), default="OPEN")  # OPEN, VERIFIED, CLOSED, REOPENED
    related_task_id: Mapped[str] = mapped_column(String(128), default="")
    reported_by: Mapped[str] = mapped_column(String(255), default="QA")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship(back_populates="defects")


class EvidenceRecord(Base):
    """Normalized evidence connecting real activity (commits, builds, tests, defects) to tasks."""
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    summary: Mapped[str] = mapped_column(String(512), default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    project: Mapped["Project"] = relationship(back_populates="evidence_items")


class SyncRunRecord(Base):
    """Audit log of synchronization runs across PM tool adapters."""
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False, default="DLX")
    sync_started: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    sync_completed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    error_message: Mapped[str] = mapped_column(Text, default="")


class DeviceToken(Base):
    """Device pairing tokens for desktop agent authentication."""
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    machine_name: Mapped[str] = mapped_column(String(255), default="LOCAL-PC")
    pairing_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_paired: Mapped[bool] = mapped_column(Integer, default=0)
    is_revoked: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLogRecord(Base):
    """Audit log of security actions: logins, role changes, device pairings/revocations."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)


class TestCaseRecord(Base):
    """Structured test case for manual, automated, and regression verification."""
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    suite_id: Mapped[str] = mapped_column(String(64), default="SUITE-DEFAULT")
    suite_name: Mapped[str] = mapped_column(String(128), default="General Test Suite")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    test_type: Mapped[str] = mapped_column(String(32), default="AUTOMATED")  # AUTOMATED, MANUAL, REGRESSION
    priority: Mapped[str] = mapped_column(String(32), default="MEDIUM")      # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(32), default="READY")         # DRAFT, READY, IN_PROGRESS, PASSED, FAILED, BLOCKED
    preconditions: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    linked_jira_key: Mapped[str] = mapped_column(String(64), default="")     # e.g. KAN-1, KAN-3
    assigned_to: Mapped[str] = mapped_column(String(255), default="Dave Miller")
    created_by: Mapped[str] = mapped_column(String(255), default="Tester")
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)  # PASSED, FAILED, BLOCKED, SKIPPED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship()


class DefectDraftRecord(Base):
    """Draft defects created from test failures before confirmation and Jira push."""
    __tablename__ = "defect_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    test_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_failure_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_name: Mapped[str] = mapped_column(String(255), default="")
    stack_trace: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(32), default="HIGH")        # LOW, MEDIUM, HIGH, CRITICAL
    priority: Mapped[str] = mapped_column(String(32), default="HIGH")        # LOW, MEDIUM, HIGH, URGENT
    linked_jira_issue: Mapped[str] = mapped_column(String(64), default="")   # e.g. KAN-1, KAN-4
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")         # DRAFT, REVIEWED, PUSHED_TO_JIRA, DISCARDED
    created_by: Mapped[str] = mapped_column(String(255), default="Tester")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship()


class ChangeSetRecord(Base):
    """Tracks grouped code modifications, affected symbols, and controlled Git finalization."""
    __tablename__ = "change_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_set_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, default="DEV-001")
    title: Mapped[str] = mapped_column(String(255), default="In-Progress Code Refactor")
    status: Mapped[str] = mapped_column(String(32), default="IN_PROGRESS")  # IN_PROGRESS, NEEDS_ATTENTION, READY_FOR_REVIEW, FINALIZED, SYNCED, SYNC_FAILED
    files_modified: Mapped[str] = mapped_column(Text, default="[]")       # JSON array of file paths
    symbols_impacted: Mapped[str] = mapped_column(Text, default="[]")     # JSON array of affected functions/classes
    diff_summary: Mapped[str] = mapped_column(Text, default="")            # AST or text diff summary
    commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, default="")
    remote_synced: Mapped[int] = mapped_column(Integer, default=0)         # 0 = not pushed, 1 = pushed to GitHub
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    project: Mapped["Project"] = relationship()


class ErrorRecord(Base):
    """Centralized tracking of syntax errors, build failures, and test exceptions."""
    __tablename__ = "detected_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    error_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    change_set_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_type: Mapped[str] = mapped_column(String(32), nullable=False)     # SYNTAX_ERROR, TEST_FAILURE, BUILD_ERROR, RUNTIME_EXCEPTION
    severity: Mapped[str] = mapped_column(String(32), default="HIGH")       # CRITICAL, HIGH, MEDIUM, LOW
    file_path: Mapped[str] = mapped_column(String(512), default="")
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")                  # Stack trace or compiler output
    status: Mapped[str] = mapped_column(String(32), default="OPEN")         # OPEN, RESOLVED, INVESTIGATING
    verification_method: Mapped[str] = mapped_column(String(64), default="")# AST_PARSE, PYTEST_RUN, MANUAL
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship()


class SeleniumTestRunRecord(Base):
    """Execution history of automated browser Selenium + TestNG test runs."""
    __tablename__ = "selenium_test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.project_id"), nullable=False)
    suite_name: Mapped[str] = mapped_column(String(128), default="ProjectPulse Browser Automation Suite")
    browser: Mapped[str] = mapped_column(String(64), default="Chrome")
    headless: Mapped[bool] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, FAILED, INFRASTRUCTURE_ERROR, RUNNING
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    exit_code: Mapped[int] = mapped_column(Integer, default=0)
    command: Mapped[str] = mapped_column(String(512), default="mvn test")
    stdout_excerpt: Mapped[str] = mapped_column(Text, default="")
    stderr_excerpt: Mapped[str] = mapped_column(Text, default="")
    test_methods_json: Mapped[str] = mapped_column(Text, default="[]")  # List of dicts with details
    report_file: Mapped[str] = mapped_column(String(255), default="testng-results.xml")
    fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)
    executed_by: Mapped[str] = mapped_column(String(255), default="Dave Miller (QA)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    project: Mapped["Project"] = relationship()




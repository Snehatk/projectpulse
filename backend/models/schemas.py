"""Pydantic API schemas for ProjectPulse AI."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer

from shared.event_types import EventSource, EventType, UserRole
from shared.events import ProjectEvent, ProjectEventCreate
from shared.timeutil import to_iso_utc, utc_now


def new_id(prefix: str = "") -> str:
    uid = uuid4().hex[:8].upper()
    return f"{prefix}-{uid}" if prefix else str(uuid4())


class UserCreate(BaseModel):
    user_id: str | None = None
    name: str
    role: UserRole = UserRole.DEVELOPER
    external_id: str | None = None


class UserResponse(BaseModel):
    user_id: str
    name: str
    role: str
    external_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    project_id: str | None = None
    name: str
    folder_path: str
    description: str = ""
    owner_user_id: str


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    folder_path: str
    description: str = ""
    owner_user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Agent Schemas
class AgentRegisterRequest(BaseModel):
    agent_id: str
    user_id: str
    project_id: str
    role: UserRole = UserRole.DEVELOPER
    machine_name: str = "LOCAL-PC"
    machine_id: str = "LOCAL-MACHINE"


class AgentHeartbeatRequest(BaseModel):
    agent_id: str
    monitoring_active: bool = True
    timestamp: datetime = Field(default_factory=utc_now)


class AgentResponse(BaseModel):
    agent_id: str
    user_id: str
    project_id: str
    role: str
    machine_name: str
    machine_id: str
    status: str
    last_seen: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("last_seen", "created_at")
    def _serialize_dates(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


# Event Schemas
class EventIngestRequest(ProjectEventCreate):
    pass


class EventResponse(ProjectEvent):
    created_at: datetime | None = None
    human_description: str = ""
    display_title: str = ""

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime | None) -> str | None:
        return to_iso_utc(value)


# Task Schemas
class TaskCreate(BaseModel):
    project_id: str
    source: str = "MANUAL"
    external_task_id: str
    title: str
    description: str = ""
    status: str = "TODO"
    priority: str = "MEDIUM"
    assignee: str = ""
    reporter: str = ""
    due_date: str | None = None
    sprint: str = "Sprint 1"
    dependencies: str = "[]"
    labels: str = "[]"
    components: str = "[]"
    jira_url: str = ""
    issue_type: str = "Task"
    story_points: float | None = None
    parent_key: str = ""


class TaskResponse(BaseModel):
    id: int
    project_id: str
    source: str
    external_task_id: str
    title: str
    description: str
    status: str
    priority: str
    assignee: str
    reporter: str = ""
    due_date: str | None
    sprint: str = "Sprint 1"
    dependencies: str = "[]"
    labels: str = "[]"
    components: str = "[]"
    jira_url: str = ""
    issue_type: str = "Task"
    story_points: float | None = None
    parent_key: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    id: int
    evidence_id: str
    project_id: str
    task_id: str
    event_id: str
    evidence_type: str
    source: str
    timestamp: datetime
    confidence: float = 1.0
    summary: str = ""
    metadata: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class TaskEvidenceDetailResponse(BaseModel):
    task: TaskResponse
    planned: dict
    actual_counts: dict
    plan_vs_reality: dict
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class SyncRunResponse(BaseModel):
    id: int
    integration_id: str
    source: str
    project_id: str
    sync_started: datetime
    sync_completed: datetime | None = None
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    status: str = "SUCCESS"
    error_message: str = ""

    model_config = {"from_attributes": True}


# Summaries & Dashboards
class ActivitySummary(BaseModel):
    total_activities: int = 0
    commits: int = 0
    build_failures: int = 0
    build_successes: int = 0
    file_modifications: int = 0
    files_created: int = 0
    branch_changes: int = 0
    test_runs: int = 0
    test_failures: int = 0
    bugs_reported: int = 0


class DeveloperSummaryResponse(BaseModel):
    project_id: str
    project_name: str
    date: str
    activity: ActivitySummary
    highlights: list[str] = Field(default_factory=list)
    recent_events: list[EventResponse] = Field(default_factory=list)
    current_status: str = "No activity recorded"
    narrative_summary: str = ""
    what_you_did: list[str] = Field(default_factory=list)
    monitoring_active: bool = True
    display_timezone: str = "Asia/Kolkata"


class HealthScorecard(BaseModel):
    overall_status: str = "ATTENTION_REQUIRED"  # HEALTHY, ATTENTION_REQUIRED, CRITICAL
    tasks_status: str = "Healthy"
    development_status: str = "Healthy"
    testing_status: str = "Healthy"
    qa_status: str = "Healthy"
    dependencies_status: str = "No blockers"


class ManagerDashboardResponse(BaseModel):
    project_id: str
    project_name: str
    activity: ActivitySummary
    recent_events: list[EventResponse] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    narrative_summary: str = ""
    health: HealthScorecard = Field(default_factory=HealthScorecard)
    team_agents: list[AgentResponse] = Field(default_factory=list)
    tasks_summary: dict = Field(default_factory=dict)
    active_risks: list[dict] = Field(default_factory=list)



class AppConfigResponse(BaseModel):
    project_id: str
    user_id: str
    project_name: str
    backend_url: str = "http://127.0.0.1:8000"
    frontend_url: str = "http://127.0.0.1:5173"
    monitoring_active: bool = True


class MonitoringStatusUpdate(BaseModel):
    active: bool
    project_id: str | None = None


# QA & Defect Schemas
class DefectCreate(BaseModel):
    title: str
    description: str = ""
    severity: str = "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL
    priority: str = "HIGH"  # LOW, MEDIUM, HIGH, URGENT
    related_task_id: str = ""
    reported_by: str = "QA"


class DefectStatusUpdate(BaseModel):
    status: str  # OPEN, VERIFIED, CLOSED, REOPENED


class VerdictCreate(BaseModel):
    approved: bool
    build_ref: str = "main"
    notes: str = ""


# AI Assistant Schemas (Phases 14 & 15)
class AIChatRequest(BaseModel):
    query: str


class AIChatResponse(BaseModel):
    query: str
    answer: str
    citations: list[str] = Field(default_factory=list)
    retrieved_context: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


# Real Jira Schemas
class JiraConnectRequest(BaseModel):
    base_url: str
    email: str
    api_token: str
    project_key: str = ""


class JiraProjectResponse(BaseModel):
    id: str
    key: str
    name: str
    lead: str = ""


class JiraSyncRequest(BaseModel):
    project_id: str = "DLX"
    jira_project_key: str = ""


# AI Risk Detection Schemas
class AIRiskItem(BaseModel):
    risk_id: str = ""
    rule_id: str
    risk_type: str
    severity: str
    category: str = "QUALITY"
    title: str
    task_id: str = ""
    task_title: str = ""
    facts: list[str] = Field(default_factory=list)
    explanation: str
    confidence: float = 1.0
    suggested_action: str = ""
    timestamp: str = ""


# AI Summary Schemas
class AISummaryRequest(BaseModel):
    summary_type: str = "project"  # project, task, developer, risk, timeline
    timeframe: str = "24h"
    user_id: str | None = None


class AISummaryResponse(BaseModel):
    project_id: str
    summary_type: str
    title: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""


# Unified Project Timeline Schemas
class TimelineItemResponse(BaseModel):
    id: str
    timestamp: str
    source: str
    event_type: str
    title: str
    description: str = ""
    task_id: str | None = None
    author: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# Code Change Explanation Schemas
class CodeExplanationResponse(BaseModel):
    explanation_id: str
    event_id: str
    timestamp: str
    commit_hash: str = ""
    commit_message: str = ""
    author: str = ""
    files_changed_count: int = 0
    files_changed: list[str] = Field(default_factory=list)
    inferred_module: str = ""
    matched_task_id: str = ""
    matched_task_title: str = ""
    confidence_level: str = "LIKELY"  # DIRECT, LIKELY, PLAUSIBLE, UNLINKED
    confidence_score: float = 0.85
    explanation: str = ""
    evidence_signals: list[str] = Field(default_factory=list)


# Test Case Management Schemas
class TestCaseCreate(BaseModel):
    title: str
    suite_id: str = "SUITE-DEFAULT"
    suite_name: str = "General Test Suite"
    description: str = ""
    test_type: str = "AUTOMATED"  # AUTOMATED, MANUAL, REGRESSION
    priority: str = "MEDIUM"      # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "READY"         # DRAFT, READY, IN_PROGRESS, PASSED, FAILED, BLOCKED
    preconditions: str = ""
    steps: str = ""
    expected_result: str = ""
    linked_jira_key: str = ""
    assigned_to: str = "Dave Miller"


class TestCaseUpdate(BaseModel):
    title: str | None = None
    suite_id: str | None = None
    suite_name: str | None = None
    description: str | None = None
    test_type: str | None = None
    priority: str | None = None
    status: str | None = None
    preconditions: str | None = None
    steps: str | None = None
    expected_result: str | None = None
    linked_jira_key: str | None = None
    assigned_to: str | None = None


class TestCaseExecuteRequest(BaseModel):
    verdict: str  # PASSED, FAILED, BLOCKED, SKIPPED
    notes: str = ""
    executed_by: str = "Dave Miller"


class TestCaseResponse(BaseModel):
    test_case_id: str
    project_id: str
    suite_id: str
    suite_name: str
    title: str
    description: str
    test_type: str
    priority: str
    status: str
    preconditions: str
    steps: str
    expected_result: str
    linked_jira_key: str
    assigned_to: str
    created_by: str
    last_executed_at: str | None = None
    last_verdict: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


# Defect Draft & Test Failure Linking Schemas
class DefectDraftCreate(BaseModel):
    title: str
    description: str = ""
    test_case_id: str | None = None
    test_failure_event_id: str | None = None
    test_name: str = ""
    stack_trace: str = ""
    severity: str = "HIGH"
    priority: str = "HIGH"
    linked_jira_issue: str = ""
    created_by: str = "Dave Miller"


class DefectDraftResponse(BaseModel):
    draft_id: str
    project_id: str
    test_case_id: str | None = None
    test_failure_event_id: str | None = None
    test_name: str
    stack_trace: str
    title: str
    description: str
    severity: str
    priority: str
    linked_jira_issue: str
    status: str
    created_by: str
    created_at: str | None = None
    updated_at: str | None = None


# Tester Overview Dashboard Response
class TesterOverviewResponse(BaseModel):
    project_id: str
    project_name: str
    total_test_runs: int
    total_tests: int
    passed: int
    failed: int
    skipped: int
    pass_rate: float
    test_runs_today: int
    open_defects: list[dict[str, Any]] = Field(default_factory=list)
    pending_regression_tests: list[TestCaseResponse] = Field(default_factory=list)
    agent_sync_status: dict[str, Any] = Field(default_factory=dict)
    upcoming_tasks: list[dict[str, Any]] = Field(default_factory=list)
    test_cases: list[TestCaseResponse] = Field(default_factory=list)
    defect_drafts: list[DefectDraftResponse] = Field(default_factory=list)
    repeated_failures: list[dict[str, Any]] = Field(default_factory=list)
    recent_executions: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[EventResponse] = Field(default_factory=list)


# Developer Overview Dashboard Response
class DeveloperOverviewResponse(BaseModel):
    project_id: str
    project_name: str
    user_id: str
    developer_name: str
    assigned_jira_issues: list[dict[str, Any]] = Field(default_factory=list)
    recent_commits_and_prs: list[dict[str, Any]] = Field(default_factory=list)
    build_pipeline_results: dict[str, Any] = Field(default_factory=dict)
    deadline_and_blocked_alerts: list[dict[str, Any]] = Field(default_factory=list)
    agent_sync_status: dict[str, Any] = Field(default_factory=dict)
    recent_activity: list[EventResponse] = Field(default_factory=list)
    what_you_did: list[str] = Field(default_factory=list)
    pending_reviews: list[dict[str, Any]] = Field(default_factory=list)
    current_status: str = "Active development"
    monitoring_active: bool = True


# AI Developer Assistant Schemas
class DeveloperAIAssistRequest(BaseModel):
    project_id: str
    user_id: str = "DEV-001"
    mode: str = "general"  # explain_build, summarize_pr, explain_code, debug_steps, jira_criteria, plan_implementation, general
    prompt: str = ""
    context_data: dict[str, Any] = Field(default_factory=dict)


class DeveloperAIAssistResponse(BaseModel):
    mode: str
    title: str
    explanation: str
    suggested_steps: list[str] = Field(default_factory=list)
    code_snippets: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    is_safe_advisory: bool = True


# =============================================================
# Code Studio, Real-Time Change Tracking & Git Sync Schemas
# =============================================================

class WorkspaceFileItem(BaseModel):
    path: str
    name: str
    is_dir: bool
    size: int = 0
    language: str = "plaintext"
    children: list["WorkspaceFileItem"] = Field(default_factory=list)


class FileReadResponse(BaseModel):
    path: str
    content: str
    language: str
    size: int
    last_modified: str


class FileSaveRequest(BaseModel):
    path: str
    content: str
    user_id: str = "DEV-001"
    change_set_title: str | None = None


class ErrorItem(BaseModel):
    error_id: str
    project_id: str
    change_set_id: str | None = None
    error_type: str  # SYNTAX_ERROR, TEST_FAILURE, BUILD_ERROR, RUNTIME_EXCEPTION
    severity: str    # CRITICAL, HIGH, MEDIUM, LOW
    file_path: str = ""
    line_number: int | None = None
    message: str
    details: str = ""
    status: str      # OPEN, RESOLVED, INVESTIGATING
    verification_method: str = ""
    detected_at: str
    resolved_at: str | None = None


class FileSaveResponse(BaseModel):
    success: bool
    path: str
    change_set_id: str
    change_set_status: str
    ast_symbols: list[dict[str, Any]] = Field(default_factory=list)
    errors_detected: list[ErrorItem] = Field(default_factory=list)
    message: str = "Saved and analyzed"


class TestRunResponse(BaseModel):
    success: bool
    total: int
    passed: int
    failed: int
    duration_sec: float
    output: str
    errors_detected: list[ErrorItem] = Field(default_factory=list)
    change_set_id: str | None = None
    change_set_status: str = "IN_PROGRESS"


class ChangeSetResponse(BaseModel):
    change_set_id: str
    project_id: str
    user_id: str
    title: str
    status: str  # IN_PROGRESS, NEEDS_ATTENTION, READY_FOR_REVIEW, FINALIZED, SYNCED, SYNC_FAILED
    files_modified: list[str] = Field(default_factory=list)
    symbols_impacted: list[dict[str, Any]] = Field(default_factory=list)
    diff_summary: str = ""
    commit_hash: str | None = None
    commit_message: str = ""
    remote_synced: bool = False
    sync_error: str | None = None
    errors: list[ErrorItem] = Field(default_factory=list)
    created_at: str
    updated_at: str


class FinalizeChangeSetRequest(BaseModel):
    commit_message: str
    author_name: str = "Alex Rivera <alex@projectpulse.local>"


class GitStatusResponse(BaseModel):
    branch: str = "main"
    is_clean: bool = True
    uncommitted_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)
    recent_commits: list[dict[str, Any]] = Field(default_factory=list)
    remote_url: str = ""
    active_change_set: ChangeSetResponse | None = None


# --- Selenium & TestNG Schemas ---

class SeleniumEnvironmentStatus(BaseModel):
    java_installed: bool
    java_version: str
    maven_installed: bool
    maven_version: str
    chrome_installed: bool
    chrome_path: str
    is_ready: bool
    missing_prerequisites: list[str] = Field(default_factory=list)
    test_project_path: str
    default_suite: str = "testng.xml"


class SeleniumTestMethodResult(BaseModel):
    name: str
    class_name: str
    status: str  # PASS, FAIL, SKIP
    duration_seconds: float
    description: str = ""
    error_message: str = ""
    stack_trace: str = ""


class SeleniumRunRequest(BaseModel):
    headless: bool = True
    browser: str = "chrome"
    test_url: str = ""
    suite_file: str = "testng.xml"


class SeleniumTestRunResponse(BaseModel):
    run_id: str
    project_id: str
    suite_name: str
    browser: str
    headless: bool
    status: str  # SUCCESS, FAILED, INFRASTRUCTURE_ERROR, RUNNING
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    pass_rate: float
    duration_seconds: float
    exit_code: int
    stdout_excerpt: str
    stderr_excerpt: str
    test_methods: list[SeleniumTestMethodResult] = Field(default_factory=list)
    report_file: str
    executed_by: str
    created_at: str


class SeleniumTestRunListResponse(BaseModel):
    project_id: str
    environment: SeleniumEnvironmentStatus
    runs: list[SeleniumTestRunResponse] = Field(default_factory=list)
    total_runs: int = 0


class SeleniumJiraLinkRequest(BaseModel):
    jira_issue_key: str
    test_name: str
    failure_message: str = ""

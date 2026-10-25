"""Tests for Tester Overview, Test Case Management, Defect Drafts, Developer Overview, and AI Assistant."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal, init_db, get_db
from backend.services.seed_service import seed_demo_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_and_clean_overrides():
    app.dependency_overrides.clear()
    init_db()
    db = SessionLocal()
    seed_demo_data(db)
    db.close()
    yield
    app.dependency_overrides.clear()


def test_tester_overview_endpoint():
    res = client.get("/api/projects/KAN/tester-overview")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == "KAN"
    assert data["total_tests"] >= 4
    assert "agent_sync_status" in data
    assert len(data["test_cases"]) >= 5
    assert len(data["defect_drafts"]) >= 1


def test_test_case_crud_and_execution():
    # 1. Create a test case
    payload = {
        "title": "Verify Checkout Session Expiration After 30 Minutes",
        "suite_id": "SUITE-PAYMENT",
        "suite_name": "Payment Gateway Suite",
        "description": "Ensure expired Stripe sessions cannot be paid.",
        "test_type": "REGRESSION",
        "priority": "HIGH",
        "status": "READY",
        "preconditions": "Session created 31 minutes ago.",
        "steps": "1. Attempt payment.\n2. Verify 400 Bad Request.",
        "expected_result": "Payment rejected with 'Session Expired'.",
        "linked_jira_key": "KAN-1",
        "assigned_to": "Dave Miller",
    }
    create_res = client.post("/api/projects/KAN/test-cases", json=payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["title"] == payload["title"]
    tc_id = created["test_case_id"]

    # 2. Execute test case
    exec_res = client.post(f"/api/test-cases/{tc_id}/execute", json={
        "verdict": "PASSED",
        "notes": "Verified session invalidated after TTL.",
        "executed_by": "Dave Miller (QA)",
    })
    assert exec_res.status_code == 200
    executed = exec_res.json()
    assert executed["last_verdict"] == "PASSED"
    assert executed["status"] == "PASSED"

    # 3. Clean up
    del_res = client.delete(f"/api/test-cases/{tc_id}")
    assert del_res.status_code == 200


def test_defect_draft_lifecycle():
    # 1. List defect drafts
    res = client.get("/api/projects/KAN/defect-drafts")
    assert res.status_code == 200
    drafts = res.json()
    assert len(drafts) >= 1
    assert drafts[0]["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")

    # 2. Create a new draft
    payload = {
        "title": "Simulated Webhook dropped packet on high load",
        "description": "Packet dropped when queue depth exceeds 50.",
        "test_name": "test_burst_traffic",
        "stack_trace": "ConnectionResetError: Connection reset by peer",
        "severity": "HIGH",
        "priority": "HIGH",
        "linked_jira_issue": "KAN-4",
        "created_by": "Dave Miller (QA)",
    }
    create_res = client.post("/api/projects/KAN/defect-drafts", json=payload)
    assert create_res.status_code == 200
    draft = create_res.json()
    draft_id = draft["draft_id"]

    # 3. Confirm defect draft
    confirm_res = client.post(f"/api/defect-drafts/{draft_id}/confirm")
    assert confirm_res.status_code == 200
    result = confirm_res.json()
    assert result["status"] in ("ok", "confirmed")
    assert "defect_id" in result


def test_developer_overview_endpoint():
    res = client.get("/api/projects/KAN/developer-overview?user_id=DEV-001")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == "KAN"
    assert "assigned_jira_issues" in data
    assert len(data["assigned_jira_issues"]) >= 1
    assert "recent_commits_and_prs" in data
    assert "build_pipeline_results" in data
    assert data["build_pipeline_results"]["status"] in ("SUCCESS", "UNSTABLE")
    assert "deadline_and_blocked_alerts" in data
    assert len(data["deadline_and_blocked_alerts"]) >= 1
    assert "agent_sync_status" in data
    assert "what_you_did" in data


def test_developer_ai_assist_modes():
    modes = ["explain_build", "summarize_pr", "explain_code", "debug_steps", "jira_criteria", "plan_implementation"]
    for m in modes:
        res = client.post("/api/projects/KAN/developer/ai-assist", json={
            "project_id": "KAN",
            "user_id": "DEV-001",
            "mode": m,
            "prompt": f"Please test {m}",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == m
        assert data["is_safe_advisory"] is True
        assert len(data["title"]) > 0
        assert len(data["explanation"]) > 0
        assert len(data["citations"]) > 0

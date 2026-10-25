"""Comprehensive Tests for Real-Time Code Tracking, Error Monitoring & Git Synchronization."""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.database import SessionLocal, init_db
from backend.main import app
from backend.models.db_models import ChangeSetRecord, ErrorRecord, Project, User
from backend.services.code_tracking_service import CodeTrackingService
from shared.timeutil import utc_now_naive

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    init_db()
    db = SessionLocal()
    try:
        # Ensure test project PP and user DEV-001 exist
        user = db.query(User).filter(User.user_id == "DEV-001").first()
        if not user:
            user = User(
                user_id="DEV-001",
                name="Alex Rivera",
                email="alex@projectpulse.local",
                role="DEVELOPER",
            )
            db.add(user)

        proj = db.query(Project).filter(Project.project_id == "PP").first()
        if not proj:
            proj = Project(
                project_id="PP",
                name="Showcase Order Service",
                folder_path="showcase_project",
                owner_user_id="DEV-001",
            )
            db.add(proj)
        db.commit()
    finally:
        db.close()


def test_list_workspace_files():
    """Verify listing workspace files returns files and folders in showcase_project."""
    res = client.get("/api/projects/PP/code/files")
    assert res.status_code == 200
    files = res.json()
    assert isinstance(files, list)
    assert len(files) > 0
    file_paths = [f["path"] for f in files]
    assert any("app.py" in p or "src" in p for p in file_paths)


def test_read_workspace_file_safe():
    """Verify safe reading of a workspace file."""
    res = client.get("/api/projects/PP/code/file?path=src/app.py")
    assert res.status_code == 200
    data = res.json()
    assert data["path"] == "src/app.py"
    assert data["language"] == "python"
    assert "calculate_subtotal" in data["content"]


def test_path_traversal_protection():
    """Verify path traversal attacks are blocked."""
    res = client.get("/api/projects/PP/code/file?path=../../etc/passwd")
    assert res.status_code in (400, 404)


def test_save_valid_code_detects_ast_symbols():
    """Verify saving valid Python code updates AST symbols and change set."""
    db = SessionLocal()
    try:
        # Read current app.py
        app_path = Path("showcase_project/src/app.py")
        original_content = app_path.read_text(encoding="utf-8")

        # Save with an added helper function
        new_content = original_content + "\n\ndef compute_express_shipping(weight: float) -> float:\n    return round(weight * 2.5, 2)\n"

        res = client.post(
            "/api/projects/PP/code/file",
            json={"path": "src/app.py", "content": new_content, "user_id": "DEV-001"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["change_set_id"].startswith("CS-")
        assert any(sym["name"] == "compute_express_shipping" for sym in data["ast_symbols"])

        # Clean up
        app_path.write_text(original_content, encoding="utf-8")
    finally:
        db.close()


def test_syntax_error_detection_and_resolution_verification():
    """Verify syntax error is detected, creates ErrorRecord, and resolves on fix."""
    db = SessionLocal()
    try:
        app_path = Path("showcase_project/src/app.py")
        original_content = app_path.read_text(encoding="utf-8")

        # 1. Introduce broken syntax (missing colon)
        broken_content = original_content + "\n\ndef broken_func(x)\n    return x\n"
        res1 = client.post(
            "/api/projects/PP/code/file",
            json={"path": "src/app.py", "content": broken_content, "user_id": "DEV-001"},
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["change_set_status"] == "NEEDS_ATTENTION"
        assert len(data1["errors_detected"]) > 0
        assert data1["errors_detected"][0]["error_type"] == "SYNTAX_ERROR"
        assert data1["errors_detected"][0]["severity"] == "CRITICAL"

        # Check centralized errors endpoint
        err_res = client.get("/api/projects/PP/code/errors?status=OPEN")
        assert err_res.status_code == 200
        open_errs = err_res.json()
        assert any(e["error_type"] == "SYNTAX_ERROR" for e in open_errs)

        # 2. Fix the syntax error
        fixed_content = original_content + "\n\ndef broken_func(x):\n    return x\n"
        res2 = client.post(
            "/api/projects/PP/code/file",
            json={"path": "src/app.py", "content": fixed_content, "user_id": "DEV-001"},
        )
        assert res2.status_code == 200
        data2 = res2.json()

        # Syntax error should be resolved
        err_res2 = client.get("/api/projects/PP/code/errors?status=RESOLVED")
        assert err_res2.status_code == 200
        resolved_errs = err_res2.json()
        assert any(e["verification_method"] == "AST_PARSE" for e in resolved_errs)
    finally:
        # Guarantee app.py is always restored to original content
        try:
            app_path = Path("showcase_project/src/app.py")
            if 'original_content' in locals():
                app_path.write_text(original_content, encoding="utf-8")
        except Exception:
            pass
        db.close()



def test_run_workspace_tests_passes():
    """Verify test execution detects test results and reports passing suite."""
    res = client.post("/api/projects/PP/code/test-run")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 4
    assert data["passed"] >= 4
    assert data["failed"] == 0
    assert data["success"] is True


def test_controlled_git_finalization():
    """Verify change set finalization commits locally and records commit hash."""
    db = SessionLocal()
    try:
        service = CodeTrackingService(db)
        cs = service.get_or_create_active_change_set("PP", "DEV-001", "Automated QA Verification")

        res = client.post(
            f"/api/projects/PP/code/change-sets/{cs.change_set_id}/finalize",
            json={"commit_message": "test: verified code change tracking and AST intelligence"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "FINALIZED"
        assert data["commit_hash"] is not None

        # Git status reflects update
        git_res = client.get("/api/projects/PP/code/git-status")
        assert git_res.status_code == 200
        git_data = git_res.json()
        assert git_data["branch"] is not None
    finally:
        db.close()

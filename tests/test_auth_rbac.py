"""Unit and integration tests for ProjectPulse AI Authentication and RBAC system."""

import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models.db_models import User
from backend.auth.security import get_password_hash

# Create isolated in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()



class TestAuthAndRBAC(unittest.TestCase):
    """Test suite verifying password hashing, JWT sessions, role permissions, and device pairing."""

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


    def test_first_run_flow_and_login(self):
        # 1. System starts with no PM
        res = self.client.get("/api/auth/status")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["has_pm_account"])

        # 2. Setup first PM
        setup_payload = {
            "email": "sarah.pm@pulse.local",
            "password": "Password123!",
            "name": "Sarah Chen",
            "project_id": "PP",
            "project_name": "Showcase Order Service",
        }
        res = self.client.post("/api/auth/setup-first-pm", json=setup_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["email"], "sarah.pm@pulse.local")
        self.assertEqual(data["role"], "PROJECT_MANAGER")
        pm_token = data["access_token"]
        self.assertTrue(bool(pm_token))

        # 3. Prevent duplicate PM setup
        res_dup = self.client.post("/api/auth/setup-first-pm", json=setup_payload)
        self.assertEqual(res_dup.status_code, 400)

        # 4. Status now reflects existing PM
        res_status = self.client.get("/api/auth/status")
        self.assertTrue(res_status.json()["has_pm_account"])

        # 5. Login with credentials
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "sarah.pm@pulse.local", "password": "Password123!"},
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()["role"], "PROJECT_MANAGER")

        # 6. Login fails with wrong password
        bad_login = self.client.post(
            "/api/auth/login",
            json={"email": "sarah.pm@pulse.local", "password": "WrongPassword"},
        )
        self.assertEqual(bad_login.status_code, 401)

    def test_rbac_user_management(self):
        # Create PM
        self.client.post(
            "/api/auth/setup-first-pm",
            json={
                "email": "pm@pulse.local",
                "password": "Password123!",
                "name": "PM Sarah",
            },
        )
        pm_login = self.client.post(
            "/api/auth/login",
            json={"email": "pm@pulse.local", "password": "Password123!"},
        )
        pm_token = pm_login.json()["access_token"]
        pm_headers = {"Authorization": f"Bearer {pm_token}"}

        # PM creates Developer account
        dev_res = self.client.post(
            "/api/auth/users",
            headers=pm_headers,
            json={
                "email": "alex.dev@pulse.local",
                "password": "Password123!",
                "name": "Alex Rivera",
                "role": "DEVELOPER",
            },
        )
        self.assertEqual(dev_res.status_code, 201)
        self.assertEqual(dev_res.json()["role"], "DEVELOPER")

        # Developer logs in
        dev_login = self.client.post(
            "/api/auth/login",
            json={"email": "alex.dev@pulse.local", "password": "Password123!"},
        )
        self.assertEqual(dev_login.status_code, 200)
        dev_token = dev_login.json()["access_token"]
        dev_headers = {"Authorization": f"Bearer {dev_token}"}

        # Developer attempts PM-restricted endpoint: MUST BE 403 FORBIDDEN
        forbidden_res = self.client.get("/api/auth/users", headers=dev_headers)
        self.assertEqual(forbidden_res.status_code, 403)

        # PM accesses PM-restricted endpoint: MUST BE 200 OK
        pm_users_res = self.client.get("/api/auth/users", headers=pm_headers)
        self.assertEqual(pm_users_res.status_code, 200)
        self.assertEqual(len(pm_users_res.json()), 2)

    def test_agent_device_pairing_and_revocation(self):
        # Setup PM and Developer
        self.client.post(
            "/api/auth/setup-first-pm",
            json={"email": "pm@pulse.local", "password": "Password123!", "name": "PM"},
        )
        pm_login = self.client.post("/api/auth/login", json={"email": "pm@pulse.local", "password": "Password123!"})
        pm_headers = {"Authorization": f"Bearer {pm_login.json()['access_token']}"}

        # Developer created
        self.client.post(
            "/api/auth/users",
            headers=pm_headers,
            json={"email": "dev@pulse.local", "password": "Password123!", "name": "Dev", "role": "DEVELOPER"},
        )
        dev_login = self.client.post("/api/auth/login", json={"email": "dev@pulse.local", "password": "Password123!"})
        dev_headers = {"Authorization": f"Bearer {dev_login.json()['access_token']}"}

        # 1. Developer generates pairing code in dashboard
        pair_code_res = self.client.post("/api/auth/pair-code?project_id=PP", headers=dev_headers)
        self.assertEqual(pair_code_res.status_code, 200)
        code = pair_code_res.json()["pairing_code"]
        self.assertEqual(len(code), 6)

        # 2. Agent pairs using the code
        agent_pair_res = self.client.post(
            "/api/auth/pair-device",
            json={"pairing_code": code, "machine_name": "DEV-WORKSTATION-1"},
        )
        self.assertEqual(agent_pair_res.status_code, 200)
        device_data = agent_pair_res.json()
        device_token = device_data["device_token"]
        device_id = device_data["device_id"]
        self.assertEqual(device_data["role"], "DEVELOPER")
        self.assertTrue(device_token.startswith("ppa_"))

        # 3. PM views paired devices
        devices_list = self.client.get("/api/auth/devices", headers=pm_headers)
        self.assertEqual(devices_list.status_code, 200)
        self.assertEqual(len(devices_list.json()), 1)
        self.assertFalse(devices_list.json()[0]["is_revoked"])

        # 4. PM revokes the device
        revoke_res = self.client.post(f"/api/auth/devices/{device_id}/revoke", headers=pm_headers)
        self.assertEqual(revoke_res.status_code, 200)

        # 5. Device is now marked revoked
        devices_list_after = self.client.get("/api/auth/devices", headers=pm_headers)
        self.assertTrue(devices_list_after.json()[0]["is_revoked"])


if __name__ == "__main__":
    unittest.main()

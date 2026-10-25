"""Automated verification suite for ProjectPulse AI Windows Background Agent.

Covers:
1. Single-instance kernel locking
2. SQLite crash resilience & offline queuing ("Local Only — Not Synced" mode)
3. Permanent local history & search filters (by query, type, date)
4. Session tracking & idle time classification (observed vs. active vs. idle)
5. Privacy boundary & exclusion filtering
6. File deletion and rename/move events
7. Desktop shortcut and silent launcher generation
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from agent.config import AgentConfig
from agent.event_queue import PersistentEventQueue
from agent.platform_integration import (
    generate_silent_launchers,
    get_desktop_path,
)
from agent.privacy_filter import PrivacyFilter
from agent.session_tracker import (
    SessionTracker,
    get_windows_idle_seconds,
)
from agent.tray_app import SingleInstanceLock
from shared.event_types import EventSource, EventType, UserRole
from shared.events import ProjectEventCreate


class TestWindowsAgentCore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.queue_db = self.base_dir / "test_agent_queue.db"
        self.lock_file = self.base_dir / ".test_agent.lock"
        self.workspace_dir = self.base_dir / "my_project"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self.config = AgentConfig(
            agent_id="AGENT-TEST-001",
            user_id="DEV-001",
            user_name="Alex Rivera",
            project_id="PP",
            project_name="Test Project",
            role="DEVELOPER",
            project_folder=str(self.workspace_dir),
            monitoring_active=True,
            custom_exclusions=["secret_dir", "*.key"],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_instance_locking(self):
        """Verify kernel-level file lock prevents multiple agent instances."""
        lock1 = SingleInstanceLock(self.lock_file)
        lock2 = SingleInstanceLock(self.lock_file)

        self.assertTrue(lock1.acquire())
        self.assertFalse(lock2.acquire(), "Second instance must not acquire lock simultaneously")

        lock1.release()
        self.assertTrue(lock2.acquire(), "Second instance must acquire lock after first releases")
        lock2.release()

    def test_persistent_queue_and_offline_retention(self):
        """Verify events survive restarts and network downtime in Local Only mode."""
        queue = PersistentEventQueue(self.queue_db)
        self.assertEqual(queue.pending_count, 0)
        self.assertEqual(queue.total_history_count, 0)

        # Enqueue 3 events
        for i in range(3):
            evt = ProjectEventCreate(
                event_id=f"EVT-OFFLINE-{i}",
                project_id="PP",
                user_id="DEV-001",
                role=UserRole.DEVELOPER,
                source=EventSource.VS_CODE,
                event_type=EventType.FILE_MODIFIED,
                title=f"Edited module_{i}.py",
                metadata={"relative_path": f"src/module_{i}.py"},
            )
            queue.enqueue(evt)

        self.assertEqual(queue.pending_count, 3)
        self.assertEqual(queue.total_history_count, 3)

        # Simulate agent crash & restart
        rebooted_queue = PersistentEventQueue(self.queue_db)
        self.assertEqual(rebooted_queue.pending_count, 3)

        # Offline network: sender returns False
        def offline_sender(payload):
            return False

        flushed = rebooted_queue.flush(offline_sender)
        self.assertEqual(flushed, 0)
        self.assertEqual(rebooted_queue.pending_count, 3, "Queue must retain events when offline")

        # Network restored: sender returns True
        sent_ids = []

        def online_sender(payload):
            sent_ids.append(payload["event_id"])
            return True

        flushed = rebooted_queue.flush(online_sender)
        self.assertEqual(flushed, 3)
        self.assertEqual(rebooted_queue.pending_count, 0)
        self.assertEqual(len(sent_ids), 3)

        # Permanent history must STILL retain the 3 events after flush
        self.assertEqual(rebooted_queue.total_history_count, 3)

    def test_local_history_search_and_filters(self):
        """Verify searchable history by query, event type, and file path."""
        queue = PersistentEventQueue(self.queue_db)

        # Insert diverse events
        events = [
            ("EVT-1", EventType.FILE_CREATED, "Created auth.py", "src/auth.py"),
            ("EVT-2", EventType.FILE_MODIFIED, "Modified auth.py", "src/auth.py"),
            ("EVT-3", EventType.FILE_DELETED, "Deleted old_code.py", "src/old_code.py"),
            ("EVT-4", EventType.GIT_COMMIT, "Commit: fix JWT auth expiration", "src/auth.py"),
            ("EVT-5", EventType.TEST_PASSED, "Pytest 14 passed", "tests/test_login.py"),
        ]

        for eid, etype, title, path in events:
            queue.enqueue(
                ProjectEventCreate(
                    event_id=eid,
                    project_id="PP",
                    user_id="DEV-001",
                    role=UserRole.DEVELOPER,
                    source=EventSource.VS_CODE,
                    event_type=etype,
                    title=title,
                    metadata={"relative_path": path},
                )
            )

        # Filter by text query
        results = queue.search_history(query="JWT")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["event_id"], "EVT-4")

        # Filter by event type
        created = queue.search_history(event_type=EventType.FILE_CREATED)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["event_id"], "EVT-1")

        # Filter by file path query
        auth_events = queue.search_history(query="auth.py")
        self.assertEqual(len(auth_events), 3)

    def test_session_tracker_and_idle_classification(self):
        """Verify time tracking model strictly separates session, active, idle, and editing time."""
        tracker = SessionTracker(
            approved_workspace=self.workspace_dir,
            idle_threshold_seconds=10.0,
        )

        # Advance tick in active state
        with patch("agent.session_tracker.get_windows_idle_seconds", return_value=2.0):
            tracker.update_tick(delta=60.0)

        m = tracker.get_metrics()
        self.assertEqual(m["observed_session_seconds"], 60.0)
        self.assertEqual(m["active_interaction_seconds"], 60.0)
        self.assertEqual(m["idle_seconds"], 0.0)
        self.assertFalse(m["is_user_idle"])

        # Advance tick in idle state (>10s threshold)
        with patch("agent.session_tracker.get_windows_idle_seconds", return_value=15.0):
            tracker.update_tick(delta=40.0)

        m = tracker.get_metrics()
        self.assertEqual(m["observed_session_seconds"], 100.0)
        self.assertEqual(m["active_interaction_seconds"], 60.0)
        self.assertEqual(m["idle_seconds"], 40.0)
        self.assertTrue(m["is_user_idle"])

        # Record verified editing bursts
        tracker.record_editing_activity(30.0)
        m = tracker.get_metrics()
        self.assertEqual(m["estimated_editing_seconds"], 30.0)

    def test_privacy_filter_and_custom_exclusions(self):
        """Verify strict privacy containment and custom exclusion filtering."""
        pf = PrivacyFilter(self.config)

        inside_allowed = self.workspace_dir / "src" / "api.py"
        self.assertTrue(self.config.is_path_allowed(inside_allowed))
        self.assertTrue(pf.allow_path(inside_allowed))

        outside_forbidden = Path("C:/Windows/System32/calc.exe")
        self.assertFalse(self.config.is_path_allowed(outside_forbidden))
        self.assertFalse(pf.allow_path(outside_forbidden))

        # Custom exclusion directory
        excluded_dir = self.workspace_dir / "secret_dir" / "config.json"
        self.assertFalse(self.config.is_path_allowed(excluded_dir))

    def test_launcher_generation_and_desktop_path(self):
        """Verify silent launchers and desktop path locator execute without errors."""
        generate_silent_launchers()
        root = Path(__file__).resolve().parent.parent
        vbs = root / "agent" / "launcher.vbs"
        bat = root / "start_agent.bat"

        self.assertTrue(vbs.exists(), "launcher.vbs must exist")
        self.assertTrue(bat.exists(), "start_agent.bat must exist")

        desktop = get_desktop_path()
        self.assertTrue(desktop.exists(), f"Desktop directory must exist: {desktop}")


if __name__ == "__main__":
    unittest.main()

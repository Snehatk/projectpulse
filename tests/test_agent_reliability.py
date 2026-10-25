"""Automated tests for desktop agent reliability, persistent SQLite queue, and process locking."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from agent.event_queue import PersistentEventQueue
from agent.tray_app import SingleInstanceLock
from shared.event_types import EventSource, EventType, UserRole
from shared.events import ProjectEventCreate


class TestAgentReliability(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.queue_db = Path(self.temp_dir.name) / "test_queue.db"
        self.lock_file = Path(self.temp_dir.name) / ".test_agent.lock"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_instance_lock(self):
        lock1 = SingleInstanceLock(self.lock_file)
        lock2 = SingleInstanceLock(self.lock_file)

        # First instance acquires lock successfully
        self.assertTrue(lock1.acquire())

        # Second instance must be denied lock
        self.assertFalse(lock2.acquire())

        # Release first instance; second instance can now acquire
        lock1.release()
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_persistent_queue_crash_resilience(self):
        queue = PersistentEventQueue(self.queue_db)
        self.assertEqual(queue.pending_count, 0)

        # Enqueue 3 events
        for i in range(3):
            evt = ProjectEventCreate(
                event_id=f"EVT-TEST-{i}",
                project_id="PP",
                user_id="DEV-001",
                role=UserRole.DEVELOPER,
                source=EventSource.FILE,
                event_type=EventType.FILE_MODIFIED,
                title=f"Modified file {i}.py",
            )
            queue.enqueue(evt)

        self.assertEqual(queue.pending_count, 3)

        # Simulate agent crash and reboot by instantiating a new queue pointing to same DB
        rebooted_queue = PersistentEventQueue(self.queue_db)
        self.assertEqual(rebooted_queue.pending_count, 3)

        # Failing network: flush should NOT delete events
        def failing_sender(payload):
            return False

        flushed = rebooted_queue.flush(failing_sender)
        self.assertEqual(flushed, 0)
        self.assertEqual(rebooted_queue.pending_count, 3)

        # Successful network: flush should transmit and delete events
        sent_events = []

        def successful_sender(payload):
            sent_events.append(payload["event_id"])
            return True

        flushed_success = rebooted_queue.flush(successful_sender)
        self.assertEqual(flushed_success, 3)
        self.assertEqual(rebooted_queue.pending_count, 0)
        self.assertEqual(len(sent_events), 3)


if __name__ == "__main__":
    unittest.main()

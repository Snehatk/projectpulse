"""Unit tests for AI Budget Manager free-tier quota and fallback enforcement."""

import unittest
from backend.services.ai_budget_manager import AIBudgetManager, DAILY_REQUEST_CAP


class TestAIBudgetManager(unittest.TestCase):
    def setUp(self):
        self.mgr = AIBudgetManager()

    def test_initial_status_is_local_without_key(self):
        status = self.mgr.get_status()
        self.assertEqual(status["daily_cap"], DAILY_REQUEST_CAP)
        self.assertEqual(status["requests_today"], 0)
        self.assertEqual(status["remaining_today"], DAILY_REQUEST_CAP)
        self.assertIn(status["mode"], ("LOCAL", "FALLBACK"))

    def test_context_hashing_returns_cached_response(self):
        query = "What is the project status?"
        context = {"tasks": [{"id": "PP-1", "title": "Validation"}], "defects": []}
        fallback = "Project is on track."
        citations = ["PP-1"]

        # First call
        res1 = self.mgr.generate_response(query, context, fallback, citations)
        self.assertEqual(res1["answer"], fallback)
        self.assertFalse(res1.get("cached", False))

        # Second call with identical query and context should hit cache
        res2 = self.mgr.generate_response(query, context, fallback, citations)
        self.assertEqual(res2["answer"], fallback)
        self.assertTrue(res2.get("cached", False))

    def test_daily_cap_blocks_excessive_api_calls(self):
        import os
        os.environ["GEMINI_API_KEY"] = "test-gemini-key-12345"
        try:
            # Artificially set requests to DAILY_REQUEST_CAP
            self.mgr._requests_today = DAILY_REQUEST_CAP
            status = self.mgr.get_status()
            self.assertEqual(status["remaining_today"], 0)
            self.assertEqual(status["mode"], "FALLBACK")

            res = self.mgr.generate_response("query", {}, "local answer", [])
            self.assertEqual(res["answer"], "local answer")
        finally:
            os.environ.pop("GEMINI_API_KEY", None)


if __name__ == "__main__":
    unittest.main()

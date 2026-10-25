"""Integration and Unit Tests for Selenium + Java + TestNG Browser Automation Workflow."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.database import Base, SessionLocal, engine, get_db
from backend.main import app
from backend.models.db_models import DefectDraftRecord, Project, ProjectEventRecord, SeleniumTestRunRecord
from backend.services.selenium_test_service import (
    check_selenium_environment,
    execute_selenium_test_suite,
    link_selenium_failure_to_jira,
    list_selenium_runs,
    parse_testng_results_xml,
)


class TestSeleniumTestNGIntegration(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)

        # Ensure project PP exists
        proj = self.db.query(Project).filter(Project.project_id == "PP").first()
        if not proj:
            proj = Project(
                project_id="PP",
                name="ProjectPulse AI",
                description="ProjectPulse AI Automated Testing",
                repo_path="./showcase_project",
                quality_gate_threshold=80.0,
            )
            self.db.add(proj)
            self.db.commit()

        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()

    def test_environment_detection(self):
        """Verify environment check detects Java, Maven, Chrome, and test project."""
        status = check_selenium_environment()
        self.assertIsNotNone(status)
        self.assertTrue(status.java_installed, "Java 17 should be detected")
        self.assertTrue(status.maven_installed, "Maven 3.9 should be detected")
        self.assertTrue(status.chrome_installed, "Chrome browser should be detected")
        self.assertTrue(status.is_ready, "Environment should be ready for execution")
        self.assertEqual(len(status.missing_prerequisites), 0)

    def test_parse_testng_results_xml_content(self):
        """Verify TestNG XML string parsing accurately extracts methods and metrics."""
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<testng-results ignored="0" total="4" passed="3" failed="1" skipped="0">
  <suite name="Order Suite" duration-ms="8500">
    <test name="Checkout Tests">
      <class name="com.projectpulse.tests.CheckoutTest">
        <test-method is-config="true" name="setUp" status="PASS" />
        <test-method name="testValidCheckout" duration-ms="2000" description="Verify checkout succeeds" status="PASS" />
        <test-method name="testNegativeInventoryCheckout" duration-ms="1800" description="Check negative inventory" status="FAIL">
          <exception class="java.lang.AssertionError">
            <message><![CDATA[expected [400 Bad Request] but found [500 Error]]]></message>
            <full-stacktrace><![CDATA[AssertionError: expected [400 Bad Request] but found [500 Error]]]></full-stacktrace>
          </exception>
        </test-method>
        <test-method is-config="true" name="tearDown" status="PASS" />
      </class>
      <class name="com.projectpulse.tests.PricingTest">
        <test-method name="testTierDiscount" duration-ms="1500" status="PASS" />
        <test-method name="testTaxCalculation" duration-ms="1200" status="PASS" />
      </class>
    </test>
  </suite>
</testng-results>
"""
        parsed = parse_testng_results_xml(sample_xml)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["total"], 4)
        self.assertEqual(parsed["passed"], 3)
        self.assertEqual(parsed["failed"], 1)
        self.assertEqual(parsed["skipped"], 0)
        self.assertEqual(parsed["pass_rate"], 75.0)
        self.assertEqual(parsed["duration_seconds"], 8.5)
        self.assertEqual(len(parsed["methods"]), 4)

        failed_method = [m for m in parsed["methods"] if m.status == "FAIL"][0]
        self.assertEqual(failed_method.name, "testNegativeInventoryCheckout")
        self.assertIn("500 Error", failed_method.error_message)

    def test_malformed_xml_handling(self):
        """Verify malformed TestNG XML does not crash the parser."""
        self.assertIsNone(parse_testng_results_xml("<broken><xml>"))
        self.assertIsNone(parse_testng_results_xml(""))

    def test_selenium_test_run_persistence_and_events(self):
        """Verify test execution persistence creates a database record and emits telemetry event."""
        run = execute_selenium_test_suite(
            project_id="PP",
            headless=True,
            browser="chrome",
            executed_by="Integration Tester",
            db=self.db,
        )
        self.assertIsNotNone(run)
        self.assertTrue(run.run_id.startswith("SELENIUM-RUN-"))
        self.assertEqual(run.status, "SUCCESS")
        self.assertEqual(run.total_tests, 5)
        self.assertEqual(run.passed_tests, 5)
        self.assertEqual(run.failed_tests, 0)
        self.assertEqual(run.exit_code, 0)
        self.assertEqual(len(run.test_methods), 5)

        # Check DB record
        rec = self.db.query(SeleniumTestRunRecord).filter(SeleniumTestRunRecord.run_id == run.run_id).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.total_tests, 5)

        # Check Event record
        evt = self.db.query(ProjectEventRecord).filter(
            ProjectEventRecord.project_id == "PP",
            ProjectEventRecord.metadata_json.like(f"%{run.run_id}%"),
        ).first()
        self.assertIsNotNone(evt)
        self.assertIn(evt.source, ["TEST", "test"])

    def test_api_selenium_endpoints(self):
        """Verify FastAPI REST API endpoints for Selenium workflow."""
        # Ensure at least one run exists for API testing
        existing = self.db.query(SeleniumTestRunRecord).filter(SeleniumTestRunRecord.project_id == "PP").first()
        if not existing:
            mock_run = SeleniumTestRunRecord(
                run_id="SELENIUM-RUN-MOCK01",
                project_id="PP",
                suite_name="Demo Suite",
                browser="chrome",
                headless=1,
                status="SUCCESS",
                total_tests=5,
                passed_tests=5,
                failed_tests=0,
                skipped_tests=0,
                duration_seconds=3.5,
                exit_code=0,
                command="mvn test",
                stdout_excerpt="BUILD SUCCESS",
                stderr_excerpt="",
                test_methods_json='[{"name": "testDemo", "class_name": "Demo", "status": "PASS", "duration_seconds": 1.0, "error_message": "", "stack_trace": ""}]',
                report_file="target/surefire-reports/testng-results.xml",
                fingerprint="mock-fingerprint-001",
                executed_by="Tester",
            )
            self.db.add(mock_run)
            self.db.commit()

        # 1. Status endpoint
        resp = self.client.get("/api/projects/PP/selenium/status")
        self.assertEqual(resp.status_code, 200)
        status_data = resp.json()
        self.assertTrue(status_data["is_ready"])
        self.assertTrue(status_data["java_installed"])

        # 2. Runs list endpoint
        resp = self.client.get("/api/projects/PP/selenium/runs")
        self.assertEqual(resp.status_code, 200)
        runs_data = resp.json()
        self.assertIn("runs", runs_data)
        self.assertIn("environment", runs_data)
        self.assertGreaterEqual(len(runs_data["runs"]), 1)

        # 3. Individual run details endpoint
        first_run_id = runs_data["runs"][0]["run_id"]
        resp = self.client.get(f"/api/selenium/runs/{first_run_id}")
        self.assertEqual(resp.status_code, 200)
        run_detail = resp.json()
        self.assertEqual(run_detail["run_id"], first_run_id)

    def test_link_failure_to_jira_defect(self):
        """Verify linking a test failure generates a defect record mapped to a Jira ticket."""
        link_res = link_selenium_failure_to_jira(
            run_id="SELENIUM-RUN-TEST01",
            test_name="com.projectpulse.tests.CheckoutTest::testTimeout",
            jira_issue_key="PP-3",
            failure_message="AssertionError: 504 Gateway Timeout during checkout",
            db=self.db,
            user_name="Dave Miller (QA)",
        )
        self.assertEqual(link_res["status"], "success")
        self.assertEqual(link_res["linked_jira_issue"], "PP-3")

        # Verify draft was created
        draft = self.db.query(DefectDraftRecord).filter(DefectDraftRecord.draft_id == link_res["draft_id"]).first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.linked_jira_issue, "PP-3")
        self.assertIn("testTimeout", draft.title)


if __name__ == "__main__":
    unittest.main()

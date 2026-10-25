"""Unit tests for Tester & QA Report Watcher Collector and XML Parsers."""

from pathlib import Path
import tempfile
import unittest

from agent.collectors.report_watcher import parse_coverage_xml, parse_junit_xml, parse_testng_xml


class TestReportWatcher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_testng_xml(self):
        testng_path = self.root / "testng-results.xml"
        testng_content = """<?xml version="1.0" encoding="UTF-8"?>
<testng-results ignored="0" total="3" passed="2" failed="1" skipped="0">
  <suite name="ProjectPulse Suite" duration-ms="5200">
    <test name="UI Tests">
      <class name="com.projectpulse.tests.LoginTest">
        <test-method is-config="true" name="setUp" status="PASS" />
        <test-method name="testLoginSuccess" duration-ms="1200" status="PASS" />
        <test-method name="testLoginFailure" duration-ms="1500" status="FAIL">
          <exception class="java.lang.AssertionError">
            <message><![CDATA[expected [true] but found [false]]]></message>
            <full-stacktrace><![CDATA[java.lang.AssertionError: expected [true] but found [false]]]></full-stacktrace>
          </exception>
        </test-method>
        <test-method is-config="true" name="tearDown" status="PASS" />
      </class>
      <class name="com.projectpulse.tests.OrderTest">
        <test-method name="testOrderPricing" duration-ms="2500" status="PASS" />
      </class>
    </test>
  </suite>
</testng-results>
"""
        testng_path.write_text(testng_content, encoding="utf-8")

        result = parse_testng_xml(testng_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["duration_seconds"], 5.2)
        self.assertEqual(len(result["methods"]), 3)
        self.assertTrue(any("testLoginFailure" in f for f in result["failed_tests"]))

    def test_parse_malformed_xml_graceful(self):
        malformed_path = self.root / "malformed.xml"
        malformed_path.write_text("<testng-results><unclosed-tag>", encoding="utf-8")

        self.assertIsNone(parse_testng_xml(malformed_path))
        self.assertIsNone(parse_junit_xml(malformed_path))
        self.assertIsNone(parse_coverage_xml(malformed_path))

    def test_parse_junit_xml(self):
        junit_path = self.root / "junit.xml"
        junit_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
    <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="4" time="0.45">
        <testcase classname="tests.test_orders" name="test_order_success" time="0.01" />
        <testcase classname="tests.test_orders" name="test_order_failure" time="0.02">
            <failure message="AssertionError: Order failed">Traceback info</failure>
        </testcase>
        <testcase classname="tests.test_orders" name="test_order_skipped" time="0.00">
            <skipped />
        </testcase>
        <testcase classname="tests.test_orders" name="test_order_tax" time="0.01" />
    </testsuite>
</testsuites>
"""
        junit_path.write_text(junit_content, encoding="utf-8")

        result = parse_junit_xml(junit_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["duration_seconds"], 0.45)
        self.assertTrue(any("test_order_failure" in f for f in result["failed_tests"]))

    def test_parse_coverage_xml(self):
        cov_path = self.root / "coverage.xml"
        cov_content = """<?xml version="1.0" ?>
<coverage version="7.17.0" lines-valid="100" lines-covered="85" line-rate="0.85" branch-rate="0.75">
    <packages />
</coverage>
"""
        cov_path.write_text(cov_content, encoding="utf-8")

        result = parse_coverage_xml(cov_path)
        self.assertIsNotNone(result)
        self.assertEqual(result["coverage_percentage"], 85.0)
        self.assertEqual(result["lines_covered"], 85)
        self.assertEqual(result["lines_valid"], 100)
        self.assertEqual(result["branch_rate"], 75.0)


if __name__ == "__main__":
    unittest.main()

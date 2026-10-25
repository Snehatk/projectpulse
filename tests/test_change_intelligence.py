"""Unit and integration tests for Change Intelligence Pipeline and AST Symbol Diffing."""

import unittest
from agent.ast_analyzer import (
    classify_file_change,
    diff_symbols,
    extract_python_symbols,
    generate_deterministic_explanation,
)


class TestChangeIntelligence(unittest.TestCase):
    def test_extract_python_symbols(self):
        sample_code = """
def calculate_tax(subtotal: float, rate: float = 0.08) -> float:
    return subtotal * rate

class OrderProcessor:
    def __init__(self, order_id: str):
        self.order_id = order_id

    def process(self, items: list):
        pass
"""
        symbols = extract_python_symbols(sample_code)
        self.assertIn("calculate_tax", symbols)
        self.assertEqual(symbols["calculate_tax"]["type"], "function")
        self.assertIn("subtotal", symbols["calculate_tax"]["args"])

        self.assertIn("OrderProcessor", symbols)
        self.assertEqual(symbols["OrderProcessor"]["type"], "class")
        method_names = [m["name"] for m in symbols["OrderProcessor"]["methods"]]
        self.assertIn("__init__", method_names)
        self.assertIn("process", method_names)

    def test_diff_symbols_detects_changes(self):
        old_code = """
def process_order(order_id):
    return True
"""
        new_code = """
def process_order(order_id, validate=True):
    return True

def apply_discount(order_id, code):
    return 10.0
"""
        old_syms = extract_python_symbols(old_code)
        new_syms = extract_python_symbols(new_code)

        diff = diff_symbols(old_syms, new_syms)
        added_names = [s["name"] for s in diff["added"]]
        modified_names = [s["name"] for s in diff["modified"]]

        self.assertIn("apply_discount", added_names)
        self.assertIn("process_order", modified_names)
        self.assertEqual(len(diff["removed"]), 0)

    def test_classify_file_change(self):
        self.assertEqual(classify_file_change("tests/test_orders.py"), "TEST_CODE")
        self.assertEqual(classify_file_change("pytest.ini"), "CONFIG")
        self.assertEqual(classify_file_change("requirements.txt"), "CONFIG")
        self.assertEqual(classify_file_change("README.md"), "DOCUMENTATION")
        self.assertEqual(classify_file_change("src/validator.py"), "FEATURE_LOGIC")

    def test_deterministic_explanation_no_hallucination(self):
        # 1. Unlinked without commit message or task key
        unlinked_expl = generate_deterministic_explanation(
            files_changed=["src/validator.py"],
            symbol_diffs={"added": [{"name": "validate_order"}], "modified": [], "removed": []},
            commit_message="",
            task_key="",
        )
        self.assertEqual(unlinked_expl["why"], "Reason not recorded (unlinked developer activity without commit or task tag).")
        self.assertIn("validate_order", unlinked_expl["what"])

        # 2. Linked to task PP-1
        linked_expl = generate_deterministic_explanation(
            files_changed=["src/validator.py"],
            commit_message="feat: validation",
            task_key="PP-1",
            task_title="Implement validation rules",
        )
        self.assertIn("Linked to planned work [PP-1]", linked_expl["why"])

        # 3. Offline catchup
        catchup_expl = generate_deterministic_explanation(
            files_changed=["src/app.py"],
            detected_on_catchup=True,
        )
        self.assertTrue(catchup_expl["what"].startswith("[Detected on catch-up scan]"))


if __name__ == "__main__":
    unittest.main()

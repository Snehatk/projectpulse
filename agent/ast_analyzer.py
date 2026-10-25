"""AST Symbol and Change Intelligence Analyzer for ProjectPulse Agent.

Extracts symbol-level semantic facts (functions, classes, arguments) from source code using
Python's standard library `ast`, classifies change types, and generates deterministic, evidence-grounded
explanations without requiring paid or third-party cloud LLMs.
"""

import ast
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_python_symbols(source_code: str) -> dict[str, dict[str, Any]]:
    """Parse Python source code and extract functions, classes, and method signatures."""
    symbols: dict[str, dict[str, Any]] = {}
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        logger.debug("AST syntax error (midway edit or non-python): %s", exc)
        return symbols
    except Exception as exc:
        logger.debug("AST parsing failed: %s", exc)
        return symbols

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            symbols[node.name] = {
                "name": node.name,
                "type": "function",
                "lineno": node.lineno,
                "args": args,
            }
        elif isinstance(node, ast.ClassDef):
            methods = []
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sub_args = [a.arg for a in sub.args.args]
                    methods.append({"name": sub.name, "args": sub_args, "lineno": sub.lineno})
            symbols[node.name] = {
                "name": node.name,
                "type": "class",
                "lineno": node.lineno,
                "methods": methods,
            }
    return symbols


def classify_file_change(rel_path: str) -> str:
    """Classify the role/purpose of a changed file."""
    path_lower = rel_path.lower().replace("\\", "/")
    p = Path(path_lower)
    name = p.name
    suffix = p.suffix

    if suffix in {".json", ".yaml", ".yml", ".ini", ".toml", ".cfg", ".env"} or name in {
        "requirements.txt",
        "package.json",
        "pom.xml",
        ".gitignore",
        "dockerfile",
    }:
        return "CONFIG"
    if suffix in {".md", ".rst", ".txt", ".adoc"}:
        return "DOCUMENTATION"
    if "/test" in path_lower or name.startswith("test_") or name.endswith("_test.py"):
        return "TEST_CODE"
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp"}:
        return "FEATURE_LOGIC"
    return "ASSET"


def diff_symbols(
    old_symbols: dict[str, dict[str, Any]], new_symbols: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Compute added, removed, and modified functions/classes between two AST symbol states."""
    added = []
    removed = []
    modified = []

    old_keys = set(old_symbols.keys())
    new_keys = set(new_symbols.keys())

    for k in new_keys - old_keys:
        added.append(new_symbols[k])

    for k in old_keys - new_keys:
        removed.append(old_symbols[k])

    for k in old_keys & new_keys:
        old_item = old_symbols[k]
        new_item = new_symbols[k]
        if old_item != new_item:
            modified.append({
                "name": k,
                "type": new_item.get("type", "unknown"),
                "before": old_item,
                "after": new_item,
            })

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def generate_deterministic_explanation(
    files_changed: list[str],
    symbol_diffs: dict[str, Any] | None = None,
    commit_message: str = "",
    task_key: str = "",
    task_title: str = "",
    build_outcome: str = "",
    test_outcome: str = "",
    detected_on_catchup: bool = False,
) -> dict[str, Any]:
    """Generate a structured, evidence-grounded change explanation.

    No hallucination: If no commit message or task exists, explicitly reports 'Reason not recorded'.
    """
    symbol_diffs = symbol_diffs or {"added": [], "removed": [], "modified": []}
    added_names = [s["name"] for s in symbol_diffs.get("added", [])]
    modified_names = [s["name"] for s in symbol_diffs.get("modified", [])]
    removed_names = [s["name"] for s in symbol_diffs.get("removed", [])]

    # 1. WHAT CHANGED
    what_parts = []
    if files_changed:
        what_parts.append(f"Modified {len(files_changed)} file(s): {', '.join(files_changed[:3])}{'...' if len(files_changed) > 3 else ''}")
    if added_names:
        what_parts.append(f"added {', '.join(added_names)}")
    if modified_names:
        what_parts.append(f"modified {', '.join(modified_names)}")
    if removed_names:
        what_parts.append(f"removed {', '.join(removed_names)}")

    what_str = ". ".join(what_parts) if what_parts else "Minor file content modifications."
    if detected_on_catchup:
        what_str = "[Detected on catch-up scan] " + what_str

    # 2. WHY CHANGED
    if task_key and task_title:
        why_str = f"Linked to planned work [{task_key}] {task_title}"
    elif task_key:
        why_str = f"Linked to planned task [{task_key}]"
    elif commit_message.strip():
        why_str = f"Commit message: '{commit_message.strip()}'"
    else:
        why_str = "Reason not recorded (unlinked developer activity without commit or task tag)."

    # 3. IMPACT
    impact_parts = []
    if build_outcome:
        impact_parts.append(f"Build: {build_outcome}")
    if test_outcome:
        impact_parts.append(f"Test suite: {test_outcome}")
    if not impact_parts:
        impact_parts.append("Awaiting automated build or test suite verification.")
    impact_str = "; ".join(impact_parts)

    # Classifications
    classifications = [classify_file_change(f) for f in files_changed]
    primary_classification = "FEATURE_LOGIC"
    if classifications:
        if all(c == "TEST_CODE" for c in classifications):
            primary_classification = "TEST_CODE"
        elif all(c == "CONFIG" for c in classifications):
            primary_classification = "CONFIG"
        elif all(c == "DOCUMENTATION" for c in classifications):
            primary_classification = "DOCUMENTATION"

    return {
        "what": what_str,
        "why": why_str,
        "impact": impact_str,
        "primary_classification": primary_classification,
        "files_changed": files_changed,
        "symbols_added": added_names,
        "symbols_modified": modified_names,
        "symbols_deleted": removed_names,
        "task_key": task_key or None,
        "commit_message": commit_message or None,
        "detected_on_catchup": detected_on_catchup,
    }

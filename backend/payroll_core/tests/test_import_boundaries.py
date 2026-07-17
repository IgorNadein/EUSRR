from __future__ import annotations

import ast
from pathlib import Path


ALLOWED_STDLIB_ROOTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "hashlib",
    "json",
    "re",
    "typing",
}


def test_payroll_core_has_no_host_or_framework_imports():
    package_root = Path(__file__).resolve().parents[1]
    violations = []

    for source_file in package_root.rglob("*.py"):
        if "tests" in source_file.parts:
            continue
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported_roots = []
            if isinstance(node, ast.Import):
                imported_roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported_roots = [node.module.split(".", 1)[0]]

            for imported_root in imported_roots:
                if imported_root not in ALLOWED_STDLIB_ROOTS:
                    violations.append(
                        f"{source_file.name}:{node.lineno} imports non-stdlib "
                        f"dependency {imported_root}"
                    )

    assert violations == []

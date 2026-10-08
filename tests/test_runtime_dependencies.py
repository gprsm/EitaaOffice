"""Find runtime imports that a developer environment can accidentally hide."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
import tomllib


def test_runtime_imports_have_installable_dependency_declarations():
    root = Path(__file__).resolve().parents[1]
    source = root / "src"
    local_modules = {path.name for path in source.iterdir() if path.is_dir()}
    imported = set()
    for path in source.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".", 1)[0])
    external = imported - sys.stdlib_module_names - local_modules
    normalize = lambda value: re.sub(r"[-_.]+", "-", value).lower()
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        normalize(re.match(r"[A-Za-z0-9_.-]+", requirement).group())
        for requirement in project["project"]["dependencies"]
    }
    missing = {name for name in external if normalize(name) not in declared}
    assert not missing, f"Undeclared runtime dependencies: {sorted(missing)}"
    requirements = {
        normalize(re.match(r"[A-Za-z0-9_.-]+", line).group())
        for line in (root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert declared == requirements

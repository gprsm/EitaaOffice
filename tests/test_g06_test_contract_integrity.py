from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"


def _test_functions() -> list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]:
    selected: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for path in sorted(TEST_ROOT.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                selected.append((path, node))
    return selected


def _substantive_statements(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return [
        statement
        for statement in body
        if not isinstance(statement, ast.Pass)
        and not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis
        )
    ]


def _marker_name(decorator: ast.expr) -> str | None:
    selected = decorator.func if isinstance(decorator, ast.Call) else decorator
    parts: list[str] = []
    while isinstance(selected, ast.Attribute):
        parts.append(selected.attr)
        selected = selected.value
    if isinstance(selected, ast.Name):
        parts.append(selected.id)
    name = ".".join(reversed(parts))
    return name if name.startswith("pytest.mark.") else None


def test_python_test_contracts_have_substantive_bodies():
    empty = [
        f"{path.relative_to(ROOT).as_posix()}::{node.name}"
        for path, node in _test_functions()
        if not _substantive_statements(node)
    ]
    assert empty == []


def test_skip_and_xfail_markers_are_conditional_and_reasoned():
    invalid: list[str] = []
    for path, node in _test_functions():
        for decorator in node.decorator_list:
            name = _marker_name(decorator)
            if name not in {"pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail"}:
                continue
            reason = None
            if isinstance(decorator, ast.Call):
                reason = next(
                    (
                        keyword.value.value
                        for keyword in decorator.keywords
                        if keyword.arg == "reason"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ),
                    None,
                )
            if name == "pytest.mark.skip" or not str(reason or "").strip():
                invalid.append(f"{path.relative_to(ROOT).as_posix()}::{node.name}")
    assert invalid == []


def test_phase10_runner_validates_helper_import_contract_not_old_location():
    runner = (
        ROOT / "ui" / "scripts" / "run-phase10-local-activation-tests.mjs"
    ).read_text(encoding="utf-8")
    assert "const helpers = source('src/utils/helpers.tsx')" in runner
    assert "export function normalizeLoginCodeInput" in runner
    assert "assert.match(app, /function normalizeLoginCodeInput/)" not in runner

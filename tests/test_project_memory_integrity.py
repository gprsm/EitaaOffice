from __future__ import annotations

from pathlib import Path

from scripts.check_project_memory_integrity import scan_project_memory


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_integrity_checker_accepts_clean_memory(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Project\n")
    _write(tmp_path, "AGENTS.md", "# Rules\n")
    _write(
        tmp_path,
        "docs/project-memory/FINDINGS_REGISTER.md",
        "# Findings\n\n### F-001 — سالم\n",
    )
    _write(
        tmp_path,
        "docs/project-memory/VALIDATION_LEDGER.md",
        "# Ledger\n\n| V-001 | تست | Static | PASS | local | change |\n",
    )

    assert scan_project_memory(tmp_path) == []


def test_integrity_checker_reports_corruption_and_duplicate_ids(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Project\n")
    _write(tmp_path, "AGENTS.md", "# Rules\n")
    _write(
        tmp_path,
        "docs/project-memory/FINDINGS_REGISTER.md",
        "# Findings\n\n### F-001 — first\n### F-001 — duplicate\n????\n",
    )
    _write(
        tmp_path,
        "docs/project-memory/VALIDATION_LEDGER.md",
        "# Ledger\n\n| V-001 | first | Static | PASS | local | change |\n"
        "| V-001 | duplicate | Static | PASS | local | change |\n"
        "pm run check\n",
    )
    corrupt = tmp_path / "docs" / "corrupt.md"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"# bad\nreplacement: \xef\xbf\xbd\ncontrol: \x08\n")

    issues = scan_project_memory(tmp_path)
    codes = {issue.code for issue in issues}

    assert {
        "control_character",
        "duplicate_finding_id",
        "duplicate_validation_id",
        "malformed_command_row",
        "question_mark_run",
        "replacement_character",
    } <= codes


def test_integrity_checker_reports_invalid_utf8_without_crashing(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Project\n")
    _write(tmp_path, "AGENTS.md", "# Rules\n")
    invalid = tmp_path / "docs" / "invalid.md"
    invalid.parent.mkdir(parents=True, exist_ok=True)
    invalid.write_bytes(b"# invalid\n\xff\n")

    issues = scan_project_memory(tmp_path)

    assert [issue.code for issue in issues] == ["invalid_utf8"]


def test_repository_documentation_is_clean() -> None:
    root = Path(__file__).resolve().parents[1]

    assert scan_project_memory(root) == []

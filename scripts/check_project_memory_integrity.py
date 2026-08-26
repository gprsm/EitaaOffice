from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path


FINDING_DEFINITION_RE = re.compile(r"^###\s+(F-\d{3})\b")
VALIDATION_HEADING_RE = re.compile(r"^###\s+(V-\d{3})\b")
VALIDATION_TABLE_RE = re.compile(r"^\|\s*(V-\d{3})\s*\|")
QUESTION_MARK_RUN_RE = re.compile(r"\?{4,}")
MALFORMED_COMMAND_ROW_RE = re.compile(r"^\s*(?:\\)?(?:n)?pm\s+run\b", re.IGNORECASE)
ALLOWED_CONTROL_CHARACTERS = {"\t", "\n", "\r"}


@dataclass(frozen=True, order=True)
class IntegrityIssue:
    path: str
    line: int
    column: int
    code: str
    detail: str


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _documentation_files(root: Path) -> tuple[Path, ...]:
    candidates = [root / "README.md", root / "AGENTS.md"]
    docs_root = root / "docs"
    if docs_root.exists():
        candidates.extend(docs_root.rglob("*.md"))
    return tuple(
        sorted(
            {path for path in candidates if path.is_file()},
            key=lambda path: _relative(path, root).casefold(),
        )
    )


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    return line, offset - line_start + 1


def _duplicate_definition_issues(
    *,
    path: Path,
    root: Path,
    text: str,
    kind: str,
) -> list[IntegrityIssue]:
    definitions: dict[str, list[int]] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if kind == "finding":
            match = FINDING_DEFINITION_RE.match(line)
        else:
            match = VALIDATION_HEADING_RE.match(line) or VALIDATION_TABLE_RE.match(line)
        if match:
            definitions.setdefault(match.group(1), []).append(line_number)

    issues: list[IntegrityIssue] = []
    for identifier, lines in sorted(definitions.items()):
        if len(lines) < 2:
            continue
        issues.append(
            IntegrityIssue(
                path=_relative(path, root),
                line=lines[1],
                column=1,
                code=f"duplicate_{kind}_id",
                detail=f"{identifier} is defined on lines {', '.join(str(line) for line in lines)}",
            )
        )
    return issues


def scan_project_memory(root: Path) -> list[IntegrityIssue]:
    selected_root = root.resolve(strict=True)
    issues: list[IntegrityIssue] = []
    decoded: dict[Path, str] = {}

    for path in _documentation_files(selected_root):
        relative = _relative(path, selected_root)
        payload = path.read_bytes()
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            issues.append(
                IntegrityIssue(
                    path=relative,
                    line=1,
                    column=exc.start + 1,
                    code="invalid_utf8",
                    detail=f"byte offset {exc.start}: {exc.reason}",
                )
            )
            continue
        decoded[path] = text

        for offset, character in enumerate(text):
            if character in ALLOWED_CONTROL_CHARACTERS:
                continue
            if unicodedata.category(character) == "Cc":
                line, column = _line_column(text, offset)
                issues.append(
                    IntegrityIssue(
                        path=relative,
                        line=line,
                        column=column,
                        code="control_character",
                        detail=f"forbidden control U+{ord(character):04X}",
                    )
                )

        for match in re.finditer("\ufffd", text):
            line, column = _line_column(text, match.start())
            issues.append(
                IntegrityIssue(
                    path=relative,
                    line=line,
                    column=column,
                    code="replacement_character",
                    detail="Unicode replacement character U+FFFD",
                )
            )

        for match in QUESTION_MARK_RUN_RE.finditer(text):
            line, column = _line_column(text, match.start())
            issues.append(
                IntegrityIssue(
                    path=relative,
                    line=line,
                    column=column,
                    code="question_mark_run",
                    detail=f"suspicious run of {len(match.group(0))} question marks",
                )
            )

        for line_number, line in enumerate(text.splitlines(), start=1):
            if MALFORMED_COMMAND_ROW_RE.match(line):
                issues.append(
                    IntegrityIssue(
                        path=relative,
                        line=line_number,
                        column=1,
                        code="malformed_command_row",
                        detail="orphaned npm command row; keep commands inside one Markdown row or code span",
                    )
                )

    finding_path = selected_root / "docs" / "project-memory" / "FINDINGS_REGISTER.md"
    if finding_path in decoded:
        issues.extend(
            _duplicate_definition_issues(
                path=finding_path,
                root=selected_root,
                text=decoded[finding_path],
                kind="finding",
            )
        )

    ledger_path = selected_root / "docs" / "project-memory" / "VALIDATION_LEDGER.md"
    if ledger_path in decoded:
        issues.extend(
            _duplicate_definition_issues(
                path=ledger_path,
                root=selected_root,
                text=decoded[ledger_path],
                kind="validation",
            )
        )

    return sorted(issues)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check project documentation for encoding corruption and duplicate memory IDs."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    issues = scan_project_memory(args.root)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "issue_count": len(issues),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif issues:
        for issue in issues:
            print(
                f"{issue.path}:{issue.line}:{issue.column}: "
                f"{issue.code}: {issue.detail}"
            )
        print(f"FAILED: {len(issues)} documentation integrity issue(s).")
    else:
        print("PASS: documentation UTF-8, control characters, IDs and command rows are clean.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

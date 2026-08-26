"""Generate safe project maps and document indexes without reading runtime data."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "docs" / "project-map"
SOURCE_ROOTS = (
    ROOT / "src" / "eitaa_bridge",
    ROOT / "ui" / "src",
    ROOT / "ui" / "electron",
    ROOT / "ui" / "scripts",
    ROOT / "scripts",
    ROOT / "tests",
    ROOT / "installer",
)
ALLOWED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".toml", ".ps1", ".bat", ".iss"}
IGNORED_PARTS = {"__pycache__", "node_modules", "dist", "release", ".pytest_cache"}
REPORT_GROUPS = (
    ("گزارش فازها", ROOT / "docs" / "reports" / "phases"),
    ("گزارش‌های GMI", ROOT / "docs" / "reports" / "gmi"),
    ("Artifactهای تاریخی GMI", ROOT / "docs" / "reports" / "gmi" / "artifacts"),
    ("گزارش قابلیت‌ها و UI", ROOT / "docs" / "reports" / "features"),
    ("گزارش معماری", ROOT / "docs" / "reports" / "architecture"),
    ("گزارش validation", ROOT / "docs" / "reports" / "validation"),
    ("گزارش blockerها", ROOT / "docs" / "reports" / "blockers"),
    ("گزارش‌های تثبیت", ROOT / "docs" / "reports" / "stabilization"),
    ("Handoffها", ROOT / "docs" / "handoffs"),
    ("چک‌لیست‌ها", ROOT / "docs" / "checklists"),
    ("مشخصات خاص", ROOT / "docs" / "specifications"),
)


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def role_for(path: Path) -> str:
    rel = relative(path)
    if rel.startswith("src/eitaa_bridge/domain/"):
        return "Domain"
    if rel.startswith("src/eitaa_bridge/application/"):
        return "Application"
    if rel.startswith("src/eitaa_bridge/infrastructure/"):
        return "Infrastructure"
    if rel.startswith("src/eitaa_bridge/interfaces/"):
        return "Interface"
    if rel.startswith("ui/src/"):
        return "React UI"
    if rel.startswith("ui/electron/"):
        return "Electron shell"
    if rel.startswith("ui/scripts/"):
        return "UI validation"
    if rel.startswith("tests/"):
        return "Python test"
    if rel.startswith("scripts/"):
        return "Operations/tooling"
    if rel.startswith("installer/"):
        return "Installer"
    return "Project"


def python_symbols(path: Path) -> tuple[list[Symbol], str]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeError, SyntaxError):
        return [], ""
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(Symbol(node.name, "class", node.lineno))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(Symbol(f"{node.name}.{child.name}", "method", child.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            symbols.append(Symbol(node.name, kind, node.lineno))
    doc = ast.get_docstring(tree) or ""
    summary = doc.strip().splitlines()[0][:140] if doc.strip() else ""
    return symbols, summary


JS_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:(?:async\s+)?function|class)\s+([A-Za-z_$][\w$]*)"
    r"|^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    re.MULTILINE,
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def script_symbols(path: Path) -> tuple[list[Symbol], str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return [], ""
    symbols: list[Symbol] = []
    for match in JS_SYMBOL_RE.finditer(source):
        name = match.group(1) or match.group(2)
        line = source.count("\n", 0, match.start()) + 1
        symbols.append(Symbol(name, "script symbol", line))
    return symbols, ""


def source_files() -> list[Path]:
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            if any(part in IGNORED_PARTS for part in path.parts):
                continue
            files.append(path)
    return sorted(set(files), key=lambda item: relative(item).casefold())


def build_maps() -> tuple[str, str]:
    entries: list[dict[str, object]] = []
    rows: list[str] = []
    for path in source_files():
        if path.suffix.lower() == ".py":
            symbols, summary = python_symbols(path)
        elif path.suffix.lower() in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
            symbols, summary = script_symbols(path)
        else:
            symbols, summary = [], ""
        rel = relative(path)
        entries.append(
            {
                "path": rel,
                "role": role_for(path),
                "summary": summary,
                "symbols": [symbol.__dict__ for symbol in symbols],
            }
        )
        label = summary.replace("|", "\\|") if summary else "—"
        rows.append(f"| `{rel}` | {role_for(path)} | {len(symbols)} | {label} |")

    digest = hashlib.sha256(
        "\n".join(str(path.stat().st_mtime_ns) + relative(path) for path in source_files()).encode("utf-8")
    ).hexdigest()[:16]
    markdown = "\n".join(
        [
            "# نقشهٔ ماشینی فایل‌های پروژه",
            "",
            "> این فایل تولیدشونده است؛ با `scripts/refresh_project_docs.py` بازسازی شود.",
            "",
            f"- تعداد فایل‌های نقشه: {len(entries)}",
            f"- اثرانگشت منبع: `{digest}`",
            "- دامنه: source، test، tooling و installer؛ runtime/data/config خصوصی عمداً حذف شده‌اند.",
            "",
            "| فایل | نقش | تعداد نماد | توضیح ماژول |",
            "|---|---:|---:|---|",
            *rows,
            "",
        ]
    )
    json_text = json.dumps(
        {"schema_version": 1, "source_fingerprint": digest, "files": entries},
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ) + "\n"
    return markdown, json_text


def build_reports_index() -> str:
    lines = [
        "# فهرست گزارش‌ها و اسناد دسته‌بندی‌شده",
        "",
        "> این فایل تولیدشونده است؛ با `scripts/refresh_project_docs.py` بازسازی شود.",
        "",
    ]
    total = 0
    for title, directory in REPORT_GROUPS:
        files = sorted(directory.glob("*"), key=lambda path: path.name.casefold()) if directory.exists() else []
        files = [path for path in files if path.is_file()]
        total += len(files)
        lines.extend([f"## {title}", ""])
        if files:
            lines.extend(f"- [`{path.name}`]({relative(path).removeprefix('docs/')})" for path in files)
        else:
            lines.append("- موردی ثبت نشده است.")
        lines.append("")
    lines[3:3] = [f"تعداد کل اسناد فهرست‌شده: {total}", ""]
    return "\n".join(lines)


def write_or_check(path: Path, content: str, *, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return True
    if check:
        print(f"STALE: {relative(path)}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"UPDATED: {relative(path)}")
    return True


def validate_local_markdown_links() -> bool:
    markdown_files = [ROOT / "README.md", ROOT / "AGENTS.md"]
    markdown_files.extend(sorted((ROOT / "docs").rglob("*.md")))
    broken: list[tuple[str, str]] = []
    for markdown in markdown_files:
        if not markdown.exists():
            continue
        text = markdown.read_text(encoding="utf-8", errors="replace")
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:", "app://")):
                continue
            target = target.split("#", 1)[0]
            if " " in target and not target.startswith(("./", "../")):
                target = target.split(" ", 1)[0]
            candidate = (markdown.parent / unquote(target)).resolve()
            if not candidate.exists():
                broken.append((relative(markdown), raw_target))
    for source, target in broken:
        print(f"BROKEN LINK: {source} -> {target}")
    return not broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when generated documentation is stale.")
    parser.add_argument("--check-links", action="store_true", help="Validate local Markdown link targets.")
    args = parser.parse_args()
    file_map, symbol_index = build_maps()
    results = [
        write_or_check(MAP_DIR / "PROJECT_FILE_MAP.md", file_map, check=args.check),
        write_or_check(MAP_DIR / "SYMBOL_INDEX.json", symbol_index, check=args.check),
        write_or_check(ROOT / "docs" / "REPORTS_INDEX.md", build_reports_index(), check=args.check),
    ]
    if args.check_links:
        results.append(validate_local_markdown_links())
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

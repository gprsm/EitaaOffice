from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from scripts.stabilization_baseline import collect_baseline_files, create_baseline


def _write(root: Path, relative: str, content: str = "content") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_baseline_allowlist_excludes_operational_and_dependency_state(tmp_path: Path) -> None:
    included = (
        "src/eitaa_bridge/app.py",
        "tests/test_app.py",
        "scripts/tool.py",
        "installer/setup.iss",
        "docs/README.md",
        "ui/src/App.tsx",
        "ui/scripts/check.mjs",
        "ui/electron/main.cjs",
        "ui/package.json",
        ".gitignore",
        ".env.example",
        "README.md",
        "package_clean.py",
    )
    excluded = (
        ".env",
        "bridge.json",
        ".eitaa_session.json",
        "data/coordinator.sqlite3",
        "runtime/app.jsonl",
        "diagnostics/private.jsonl",
        "backups/runtime.zip",
        "Bale/private-client.py",
        "catalog/private.json",
        "ui/node_modules/library/index.js",
        "ui/dist/index.html",
        "prompt_out.txt",
    )
    for relative in (*included, *excluded):
        _write(tmp_path, relative)

    selected = {path.relative_to(tmp_path).as_posix() for path in collect_baseline_files(tmp_path)}

    assert set(included) <= selected
    assert set(excluded).isdisjoint(selected)


def test_baseline_archive_is_deterministic_and_receipt_verifies_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write(root, "src/eitaa_bridge/app.py", "print('safe')\n")
    _write(root, "docs/README.md", "# Safe\n")
    _write(root, "ui/package.json", '{"name":"safe"}\n')
    _write(root, ".env", "SECRET=must-not-enter-archive\n")

    first_zip = tmp_path / "first.zip"
    first_receipt = tmp_path / "first.json"
    second_zip = tmp_path / "second.zip"
    second_receipt = tmp_path / "second.json"

    create_baseline(root, first_zip, first_receipt, created_at="2026-08-25T00:00:00+03:30")
    create_baseline(root, second_zip, second_receipt, created_at="2026-08-25T00:00:00+03:30")

    assert first_zip.read_bytes() == second_zip.read_bytes()
    receipt = json.loads(first_receipt.read_text(encoding="utf-8"))
    assert receipt["archive_sha256"] == hashlib.sha256(first_zip.read_bytes()).hexdigest()
    assert receipt["file_count"] == 3

    with ZipFile(first_zip) as archive:
        names = archive.namelist()
        assert names == [
            "docs/README.md",
            "src/eitaa_bridge/app.py",
            "ui/package.json",
            "_baseline/CONTENT_MANIFEST.json",
        ]
        manifest = json.loads(archive.read("_baseline/CONTENT_MANIFEST.json"))
        assert [entry["path"] for entry in manifest["files"]] == names[:-1]
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
        assert ".env" not in names

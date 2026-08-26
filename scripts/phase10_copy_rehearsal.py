"""Read-only Phase 10 rehearsal using disposable copies of runtime state."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from backup_runtime import create_backup
from restore_runtime import dry_run_backup, restore_backup
from runtime_state import sha256_file, state_entries, verify_backup

from eitaa_bridge.infrastructure.contact_store import SQLiteContactStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify backup, restore, rollback readiness, and Contacts 1-to-2 on copies."
    )
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--existing-backup", type=Path)
    parser.add_argument("--worker-root", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def _hashes(root: Path) -> dict[str, str]:
    return {
        entry.archive_name: sha256_file(entry.source)
        for entry in state_entries(root, include_media=True, include_logs=False)
    }


def _contact_summary(path: Path) -> dict[str, object]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        return {
            "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
            "quick_check": str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            "contacts": int(connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]),
            "categories": int(
                connection.execute("SELECT COUNT(*) FROM contact_categories").fetchone()[0]
            ),
        }


def _remove_disposable_tree(path: Path) -> None:
    """Remove our exact temporary tree, tolerating short Windows scanner locks."""

    selected = path.resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if system_temp not in selected.parents or not selected.name.startswith("eitaa-phase10-copy-"):
        raise ValueError("Refusing to remove an unexpected rehearsal path.")

    def clear_readonly_and_retry(function, name, _error_info):
        os.chmod(name, stat.S_IWRITE)
        function(name)

    last_error: OSError | None = None
    for delay in (0.0, 0.25, 0.5):
        if delay:
            time.sleep(delay)
        try:
            shutil.rmtree(selected, onerror=clear_readonly_and_retry)
            return
        except OSError as exc:
            last_error = exc
    if os.name == "nt" and selected.exists():
        literal = str(selected).replace("'", "''")
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"Remove-Item -LiteralPath '{literal}' -Recurse -Force -ErrorAction Stop",
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )
        if result.returncode == 0 and not selected.exists():
            return
    if selected.exists():
        raise PermissionError("Disposable Phase 10 rehearsal state could not be removed.") from last_error


def _rehearse_in_directory(
    source_root: Path,
    temporary_root: Path,
    existing_backup: Path | None = None,
) -> dict[str, object]:
    source = source_root.expanduser().resolve()
    contacts = source / "data" / "contacts.sqlite3"
    if not contacts.is_file():
        raise ValueError("Contacts database is missing.")
    temporary = temporary_root.expanduser().resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if (
        system_temp not in temporary.parents
        or not temporary.name.startswith("eitaa-phase10-copy-")
        or not temporary.is_dir()
    ):
        raise ValueError("Worker root is not a disposable Phase 10 directory.")
    source_before = _hashes(source)
    contact_before = _contact_summary(contacts)
    restored = temporary / "restored"
    restored.mkdir()
    if existing_backup is None:
        snapshot = temporary / "snapshot"
        snapshot.mkdir()
        for entry in state_entries(source, include_media=True, include_logs=False):
            destination = snapshot / Path(entry.archive_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry.source, destination)
        version = source / "VERSION.txt"
        if version.is_file():
            shutil.copyfile(version, snapshot / version.name)
        backup = create_backup(
            output=temporary / "phase10-copy-backup.zip",
            include_media=True,
            include_logs=False,
            root=snapshot,
        )
    else:
        backup = existing_backup.expanduser().resolve()
        if source not in backup.parents or "backups" not in backup.parts:
            raise ValueError("Existing backup must be inside the selected installation backups tree.")
    preview = dry_run_backup(backup)
    manifest = verify_backup(backup)
    restore_result = restore_backup(backup, root=restored)
    restored_hashes = _hashes(restored)
    expected_hashes = {
        str(item["path"]): str(item["sha256"])
        for item in manifest["files"]
    }
    restore_hashes_match = restored_hashes == expected_hashes

    copied_contacts = restored / "data" / "contacts.sqlite3"
    SQLiteContactStore(copied_contacts).initialize()
    contact_after = _contact_summary(copied_contacts)
    recovery_backups = sorted(
        copied_contacts.parent.glob("contacts.schema1.*.bak.sqlite3")
    )
    recovery_backup_valid = False
    if len(recovery_backups) == 1:
        recovery = _contact_summary(recovery_backups[0])
        recovery_backup_valid = (
            recovery == contact_before
            and len(sha256_file(recovery_backups[0])) == 64
        )

    source_after = _hashes(source)
    contacts_preserved = (
        contact_after["contacts"] == contact_before["contacts"]
        and contact_after["categories"] == contact_before["categories"]
        and contact_after["quick_check"] == "ok"
        and contact_after["schema_version"] == 2
    )
    ok = all(
        (
            preview["verified"],
            restore_result["restored"],
            restore_hashes_match,
            recovery_backup_valid,
            contacts_preserved,
            source_before == source_after,
        )
    )
    return {
        "ok": ok,
        "source_unchanged": source_before == source_after,
        "source_file_count": len(source_before),
        "backup_verified": bool(preview["verified"]),
        "backup_file_count": int(preview["file_count"]),
        "backup_total_bytes": int(preview["total_bytes"]),
        "restore_hashes_match": restore_hashes_match,
        "contact_schema_before": contact_before["schema_version"],
        "contact_schema_after_on_copy": contact_after["schema_version"],
        "contact_count_before": contact_before["contacts"],
        "contact_count_after_on_copy": contact_after["contacts"],
        "category_count_before": contact_before["categories"],
        "category_count_after_on_copy": contact_after["categories"],
        "contact_recovery_backup_verified": recovery_backup_valid,
    }


def rehearse(
    source_root: Path,
    existing_backup: Path | None = None,
) -> dict[str, object]:
    """Run file-intensive work in a child so Windows releases handles before cleanup."""

    source = source_root.expanduser().resolve()
    temporary = Path(tempfile.mkdtemp(prefix="eitaa-phase10-copy-"))
    try:
        worker = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source-root",
                str(source),
                "--worker-root",
                str(temporary),
                *(
                    ["--existing-backup", str(existing_backup.expanduser().resolve())]
                    if existing_backup is not None
                    else []
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=240,
        )
        try:
            payload = json.loads(worker.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("Phase 10 rehearsal worker returned invalid output.") from exc
        if worker.returncode != 0 or not isinstance(payload, dict):
            raise ValueError("Phase 10 rehearsal worker failed.")
        return payload
    finally:
        _remove_disposable_tree(temporary)


def main() -> int:
    args = parse_args()
    try:
        result = (
            _rehearse_in_directory(
                args.source_root,
                args.worker_root,
                args.existing_backup,
            )
            if args.worker_root is not None
            else rehearse(args.source_root, args.existing_backup)
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"ok": False, "error_code": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

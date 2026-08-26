"""Controlled live Contacts schema 1-to-2 migration for Phase 10."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from eitaa_bridge.infrastructure.contact_store import CONTACT_SCHEMA, SQLiteContactStore


CONFIRMATION = "MIGRATE_CONTACTS_SCHEMA_1_TO_2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summary(path: Path) -> dict[str, object]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        return {
            "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
            "quick_check": str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "contacts": int(connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]),
            "categories": int(
                connection.execute("SELECT COUNT(*) FROM contact_categories").fetchone()[0]
            ),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--confirm")
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="Verify an already-completed live migration without changing the database.",
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    database = (root / "data" / "contacts.sqlite3").resolve()
    if root != ROOT.resolve():
        raise ValueError("Live migration root must be this Phase 10 installation.")
    if not database.is_file():
        raise FileNotFoundError("Contacts database is missing.")

    before = _summary(database)
    if args.verify_existing:
        recovery_candidates = sorted(
            database.parent.glob("contacts.schema1.*.bak.sqlite3"),
            key=lambda path: path.stat().st_mtime_ns,
        )
        if not recovery_candidates:
            raise FileNotFoundError("No schema-1 recovery backup was found.")
        recovery = recovery_candidates[-1]
        recovery_summary = _summary(recovery)
        verified = all(
            (
                before["schema_version"] == CONTACT_SCHEMA,
                before["quick_check"] == "ok",
                before["foreign_key_violations"] == 0,
                recovery_summary["schema_version"] == 1,
                recovery_summary["quick_check"] == "ok",
                recovery_summary["foreign_key_violations"] == 0,
                before["contacts"] == recovery_summary["contacts"],
                before["categories"] == recovery_summary["categories"],
                recovery.stat().st_mtime_ns <= database.stat().st_mtime_ns,
            )
        )
        result = {
            "format": "eitaa-bridge-phase10-contacts-live-migration-v1",
            "operation": "verify_existing",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "verified": verified,
            "database_file": database.name,
            "database_sha256": _sha256(database),
            "after": before,
            "recovery_backup_file": recovery.name,
            "recovery_backup_sha256": _sha256(recovery),
            "recovery": recovery_summary,
        }
        return _emit(result, args.report, root)

    if args.confirm != CONFIRMATION:
        raise ValueError("Exact live-migration confirmation token was not supplied.")
    if not all(
        (
            before["schema_version"] == 1,
            before["quick_check"] == "ok",
            before["foreign_key_violations"] == 0,
        )
    ):
        raise ValueError("Contacts preflight did not pass for a schema-1 database.")
    prior_backups = set(database.parent.glob("contacts.schema1.*.bak.sqlite3"))
    source_sha256 = _sha256(database)

    SQLiteContactStore(database).initialize()

    after = _summary(database)
    new_backups = set(database.parent.glob("contacts.schema1.*.bak.sqlite3")) - prior_backups
    if len(new_backups) != 1:
        raise RuntimeError("Migration did not create exactly one recovery backup.")
    recovery = new_backups.pop()
    recovery_summary = _summary(recovery)
    verified = all(
        (
            after["schema_version"] == CONTACT_SCHEMA,
            after["quick_check"] == "ok",
            after["foreign_key_violations"] == 0,
            after["contacts"] == before["contacts"],
            after["categories"] == before["categories"],
            recovery_summary == before,
        )
    )
    result = {
        "format": "eitaa-bridge-phase10-contacts-live-migration-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "verified": verified,
        "database_file": database.name,
        "database_sha256_before": source_sha256,
        "database_sha256_after": _sha256(database),
        "before": before,
        "after": after,
        "recovery_backup_file": recovery.name,
        "recovery_backup_sha256": _sha256(recovery),
        "recovery": recovery_summary,
    }
    return _emit(result, args.report, root)


def _emit(result: dict[str, object], report_arg: Path | None, root: Path) -> int:
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if report_arg is not None:
        report = report_arg.expanduser().resolve()
        allowed = (root / "backups" / "phase10-rollout").resolve()
        if report.parent != allowed:
            raise ValueError("Migration report must be written directly in backups/phase10-rollout.")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if bool(result["verified"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

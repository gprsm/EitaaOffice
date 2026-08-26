"""Read-only verifier for the real Phase 10-B loopback activation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.contact_store import SQLiteContactStore
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    SafeCoordinatorAuditService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-active-session", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def _contact_summary(path: Path) -> dict[str, object]:
    uri = f"{path.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        return {
            "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
            "quick_check": str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "contacts": int(connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]),
            "categories": int(
                connection.execute("SELECT COUNT(*) FROM contact_categories").fetchone()[0]
            ),
            "audit_events": int(
                connection.execute("SELECT COUNT(*) FROM contact_audit_events").fetchone()[0]
            ),
        }


def _coordinator_summary(path: Path) -> dict[str, object]:
    uri = f"{path.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        connection.row_factory = sqlite3.Row
        latest_migration = connection.execute(
            """
            SELECT id,status,messenger_account_id,source_file_count,source_total_bytes
            FROM migration_runs ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        latest_worker = connection.execute(
            """
            SELECT messenger_account_id,generation,runtime_state,process_id,safe_reason_code
            FROM worker_instances ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        account = connection.execute(
            """
            SELECT id,provider,lifecycle_state,desired_worker_state
            FROM messenger_accounts ORDER BY created_at LIMIT 1
            """
        ).fetchone()
        messenger_session = connection.execute(
            """
            SELECT messenger_account_id,auth_state,session_generation,storage_revision,
                   last_validated_at,last_auth_transition_at,safe_reason_code
            FROM messenger_session_metadata ORDER BY created_at LIMIT 1
            """
        ).fetchone()
        credentials = connection.execute(
            """
            SELECT password_scheme,password_iterations,length(password_salt) AS salt_bytes,
                   length(password_digest) AS digest_bytes
            FROM app_user_credentials
            """
        ).fetchall()
        session_counts = {
            str(row["status"]): int(row["total"])
            for row in connection.execute(
                "SELECT status,COUNT(*) AS total FROM app_user_sessions GROUP BY status"
            ).fetchall()
        }
        return {
            "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
            "quick_check": str(connection.execute("PRAGMA quick_check").fetchone()[0]),
            "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
            "app_users": int(connection.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]),
            "messenger_accounts": int(
                connection.execute("SELECT COUNT(*) FROM messenger_accounts").fetchone()[0]
            ),
            "session_counts": session_counts,
            "credential_profiles": [dict(row) for row in credentials],
            "latest_migration": dict(latest_migration) if latest_migration else None,
            "account": dict(account) if account else None,
            "messenger_session": dict(messenger_session) if messenger_session else None,
            "latest_worker": dict(latest_worker) if latest_worker else None,
        }


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if root != ROOT.resolve():
        raise ValueError("Verifier root must be this Phase 10 installation.")
    config_path = root / "bridge.json"
    contacts_path = root / "data" / "contacts.sqlite3"
    coordinator_path = root / "data" / "coordinator" / "coordinator.sqlite3"
    config = BridgeConfigLoader.load(config_path)
    contacts = _contact_summary(contacts_path)
    coordinator = _coordinator_summary(coordinator_path)
    contact_audit_valid = SQLiteContactStore(contacts_path).verify_audit_chain()
    coordinator_audit = SafeCoordinatorAuditService(
        CoordinatorDatabase(coordinator_path)
    ).verify_chain()
    feature = config.features.multi_session
    default_account_id = feature.legacy_default_messenger_account_id
    latest_migration = coordinator["latest_migration"] or {}
    account = coordinator["account"] or {}
    credential_profiles = coordinator["credential_profiles"]
    active_sessions = int(coordinator["session_counts"].get("active", 0))
    checks = {
        "desktop_loopback": config.deployment.mode == "desktop_loopback",
        "loopback_bind": config.deployment.bind_host == "127.0.0.1",
        "app_user_auth_enabled": config.features.app_user_auth.enabled,
        "multi_session_enabled": feature.enabled,
        "worker_process_disabled": not config.features.worker_process.enabled,
        "default_account_matches_migration": default_account_id
        == latest_migration.get("messenger_account_id"),
        "migration_activated": latest_migration.get("status") == "activated",
        "account_identity_matches": default_account_id == account.get("id"),
        "account_is_eitaa": account.get("provider") == "eitaa",
        "coordinator_schema_5": coordinator["schema_version"] == 5,
        "coordinator_integrity": coordinator["quick_check"] == "ok"
        and coordinator["foreign_key_violations"] == 0,
        "contacts_schema_2": contacts["schema_version"] == 2,
        "contacts_integrity": contacts["quick_check"] == "ok"
        and contacts["foreign_key_violations"] == 0,
        "contacts_preserved": contacts["contacts"] == 574 and contacts["categories"] == 3,
        "one_admin_credential": coordinator["app_users"] == 1
        and len(credential_profiles) == 1,
        "credential_hash_profile_valid": len(credential_profiles) == 1
        and credential_profiles[0] == {
            "password_scheme": "pbkdf2_sha256",
            "password_iterations": 600000,
            "salt_bytes": 16,
            "digest_bytes": 32,
        },
        "contact_audit_chain_valid": contact_audit_valid,
        "coordinator_audit_chain_valid": coordinator_audit.valid,
        "active_session_present": active_sessions >= 1,
    }
    required = dict(checks)
    if not args.require_active_session:
        required.pop("active_session_present")
    result = {
        "format": "eitaa-bridge-phase10-local-activation-verification-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "verified": all(required.values()),
        "checks": checks,
        "contacts": contacts,
        "coordinator": coordinator,
        "coordinator_audit_event_count": coordinator_audit.event_count,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        report = args.report.expanduser().resolve()
        allowed = (root / "backups" / "phase10-rollout").resolve()
        if report.parent != allowed:
            raise ValueError("Report must be written directly in backups/phase10-rollout.")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Interactive, no-network migration utility for the initial legacy Eitaa account."""

from __future__ import annotations

import argparse
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"


def _use_project_python() -> None:
    """Re-launch interactive use with the application's owned Python runtime."""

    runtime = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not runtime.is_file():
        raise SystemExit(
            "The application runtime is missing. Run setup_venv.bat, then try again."
        )
    try:
        already_using_runtime = Path(sys.executable).resolve() == runtime.resolve()
    except OSError:
        already_using_runtime = False
    if not already_using_runtime:
        os.execv(
            str(runtime),
            [str(runtime), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


if __name__ == "__main__":
    _use_project_python()

if SOURCE.is_dir() and str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from backup_runtime import create_backup
from runtime_state import verify_backup

from eitaa_bridge.errors import CoordinatorError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    LegacyMigrationService,
    WindowsDpapiPhoneProtector,
    masked_phone,
    validate_canonical_e164,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely stage the legacy single Eitaa account for the coordinator."
    )
    parser.add_argument("--config", type=Path, default=Path("bridge.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    apply = sub.add_parser("apply")
    apply.add_argument("--display-name", default="Local administrator")
    sub.add_parser("status")
    rollback = sub.add_parser("rollback")
    rollback.add_argument("migration_id")
    return parser.parse_args()


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def _root(config_path: Path) -> Path:
    return config_path.expanduser().resolve().parent


def _backup_manifest_hash(manifest: dict[str, object]) -> str:
    canonical = json.dumps(
        manifest,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    root = _root(config_path)
    try:
        config = BridgeConfigLoader.load(config_path)
        service = LegacyMigrationService(root, config)
        if args.command == "preflight":
            report = service.preflight()
            _print(report.safe_summary())
            return 0 if report.ok else 2
        if args.command == "status":
            database_path = root / "data" / "coordinator" / "coordinator.sqlite3"
            if not database_path.is_file():
                _print({"initialized": False, "feature_enabled": False})
                return 0
            _print(
                {
                    "initialized": True,
                    "feature_enabled": config.features.multi_session.enabled,
                    **CoordinatorDatabase(database_path).read_only_safe_summary(),
                }
            )
            return 0
        if args.command == "apply":
            report = service.preflight()
            report.require_ok()
            phone = validate_canonical_e164(
                getpass("Confirmed legacy phone in canonical E.164 form: ")
            )
            print(f"Account to migrate: {masked_phone(phone)}")
            if input("Type MIGRATE to confirm the copy-and-verify migration: ").strip() != "MIGRATE":
                _print({"applied": False, "reason": "operator_confirmation_missing"})
                return 2
            backup = create_backup(
                output=root / "backups" / "phase2-migration",
                include_media=True,
                include_logs=False,
            )
            manifest = verify_backup(backup)
            protector = WindowsDpapiPhoneProtector(
                root / "data" / "coordinator" / "identity.key.dpapi"
            )
            result = service.migrate(
                protected_phone=protector.protect(phone),
                display_name=args.display_name,
                backup_name=backup.name,
                backup_manifest_sha256=_backup_manifest_hash(manifest),
                operator_confirmed=True,
            )
            _print(
                {
                    "applied": True,
                    "phone_hint": masked_phone(phone),
                    "backup_name": backup.name,
                    **result.safe_summary(),
                }
            )
            return 0
        if args.command == "rollback":
            if input("Type ROLLBACK to preserve and deactivate the migration: ").strip() != "ROLLBACK":
                _print({"rolled_back": False, "reason": "operator_confirmation_missing"})
                return 2
            _print(
                {
                    "rolled_back": True,
                    **service.rollback(args.migration_id, operator_confirmed=True),
                }
            )
            return 0
    except CoordinatorError as exc:
        _print(
            {
                "ok": False,
                "error_code": exc.code,
                "safe_context": exc.safe_context,
            }
        )
        return 1
    except (OSError, ValueError) as exc:
        _print({"ok": False, "error_code": type(exc).__name__})
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

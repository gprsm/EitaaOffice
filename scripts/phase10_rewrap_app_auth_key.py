"""Rewrap the live AppUser subject key for stable local-machine execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hmac
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from eitaa_bridge.infrastructure.coordinator import WindowsDpapiPhoneProtector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.confirm != "REWRAP_APP_AUTH_KEY":
        raise ValueError("Explicit REWRAP_APP_AUTH_KEY confirmation is required.")

    key_file = ROOT / "data" / "coordinator" / "app-auth-subject.key.dpapi"
    recovery_root = ROOT / "data" / "coordinator" / "identity-recovery"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup = recovery_root / f"app-auth-subject.key.dpapi.{timestamp}.bak"
    protector = WindowsDpapiPhoneProtector(key_file)
    before = protector._load_secret()
    installed_backup = protector.rewrap_install_key_for_machine_scope(backup)
    after = protector._load_secret()
    result = {
        "format": "eitaa-bridge-phase10-app-auth-key-rewrap-v1",
        "verified": hmac.compare_digest(before, after),
        "machine_scope": True,
        "key_file_present": key_file.is_file(),
        "key_file_bytes": key_file.stat().st_size,
        "backup_name": installed_backup.name,
        "backup_bytes": installed_backup.stat().st_size,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    before = after = b""
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        report = args.report.expanduser().resolve()
        allowed = (ROOT / "backups" / "phase10-rollout").resolve()
        if report.parent != allowed:
            raise ValueError("Report must be written directly in backups/phase10-rollout.")
        report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

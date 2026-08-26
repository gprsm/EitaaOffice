"""Safely verify the live coordinator phone identity without disclosing it."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from eitaa_bridge.errors import BridgeError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    WindowsDpapiPhoneProtector,
)


def _safe_error(exc: Exception) -> dict[str, object]:
    return {
        "error_type": type(exc).__name__,
        "error_code": getattr(exc, "code", "unknown_error"),
        "safe_context": dict(getattr(exc, "safe_context", {}) or {}),
    }


def main() -> int:
    coordinator_path = ROOT / "data" / "coordinator" / "coordinator.sqlite3"
    key_path = ROOT / "data" / "coordinator" / "identity.key.dpapi"
    uri = f"{coordinator_path.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
        row = connection.execute(
            "SELECT id FROM messenger_accounts ORDER BY created_at LIMIT 1"
        ).fetchone()
    if row is None:
        print(json.dumps({"verified": False, "reason": "account_missing"}, indent=2))
        return 2

    database = CoordinatorDatabase(coordinator_path)
    identity = database.messenger_account_phone_identity(str(row[0]))
    protector = WindowsDpapiPhoneProtector(key_path)
    result: dict[str, object] = {
        "format": "eitaa-bridge-phase10-identity-verification-v1",
        "key_file_present": key_path.is_file(),
        "key_file_bytes": key_path.stat().st_size if key_path.is_file() else 0,
        "ciphertext_bytes": len(identity.protected_phone.ciphertext),
        "key_version": identity.protected_phone.key_version,
        "fingerprint_shape_valid": len(identity.protected_phone.fingerprint) == 64,
    }

    try:
        secret = protector._load_secret()
    except (BridgeError, OSError) as exc:
        result.update(
            {
                "verified": False,
                "failure_stage": "install_key_unwrap",
                "error": _safe_error(exc),
            }
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    result["install_key_unwrap"] = len(secret) == 32
    try:
        revealed = protector.reveal(identity.protected_phone)
    except (BridgeError, OSError) as exc:
        result.update(
            {
                "verified": False,
                "failure_stage": "phone_ciphertext_unwrap",
                "error": _safe_error(exc),
            }
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    finally:
        if "secret" in locals():
            secret = b""

    result.update(
        {
            "verified": True,
            "phone_payload_valid": revealed.startswith("+") and revealed[1:].isdigit(),
        }
    )
    revealed = ""
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

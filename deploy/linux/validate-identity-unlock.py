"""Read-only identity unlock check; never prints an account identifier or phone."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    default_phone_protector,
)


def main() -> int:
    coordinator_root = Path(
        "/srv/projects/eitaa-bridge/shared/data/coordinator"
    )
    database_file = coordinator_root / "coordinator.sqlite3"
    try:
        with sqlite3.connect(f"file:{database_file}?mode=ro", uri=True) as connection:
            account_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM messenger_accounts "
                    "WHERE provider='eitaa' AND lifecycle_state<>'archived'"
                )
            ]
        if not account_ids:
            print("identity_unlock=not_checked reason=no_active_eitaa_account")
            return 1
        database = CoordinatorDatabase(database_file)
        protector = default_phone_protector(coordinator_root)
        for account_id in account_ids:
            identity = database.messenger_account_phone_identity(account_id)
            protector.reveal(identity.protected_phone)
    except Exception as exc:
        code = getattr(exc, "code", "identity_unlock_failed")
        print(f"identity_unlock=failed code={code} type={type(exc).__name__}")
        return 1
    print(f"identity_unlock=passed accounts={len(account_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

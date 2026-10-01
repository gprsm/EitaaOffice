"""Offline attempt-fence regression against an isolated coordinator database.

Exit 0 only if stale cleanup cannot release a newer claim for the same
account/owner/key/fingerprint. No provider, network, or operational data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from eitaa_bridge.infrastructure.coordinator import (  # noqa: E402
    CoordinatorDatabase,
    ProtectedPhone,
    ProviderOperationReceiptStore,
)


def main() -> int:
    with TemporaryDirectory(prefix="bale-attempt-fence-") as directory:
        database = CoordinatorDatabase(Path(directory) / "coordinator.sqlite3")
        database.initialize()
        bootstrap = database.bootstrap_legacy_account(
            protected_phone=ProtectedPhone(
                ciphertext=b"synthetic-only",
                key_version=1,
                fingerprint="1" * 64,
                display_hint="+••••••••67",
            ),
            display_name="Synthetic admin",
            backup_name="fixture.zip",
            source_manifest_sha256="a" * 64,
            source_file_count=1,
            source_total_bytes=1,
        )
        store = ProviderOperationReceiptStore(database)
        identity = dict(
            messenger_account_id=bootstrap.messenger_account_id,
            actor_app_user_id=bootstrap.app_user_id,
            operation="messages.send_text",
            idempotency_key="synthetic-fence-key-0001",
            request_fingerprint=hashlib.sha256(b"synthetic-payload").hexdigest(),
        )
        first = store.claim(
            **identity, actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_000,
        )
        first_release = store.release(**identity)
        newer = store.claim(
            **identity, actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_001,
        )
        # The prior attempt's duplicate/delayed cleanup must not release
        # the newer attempt, even though the request identity is identical.
        stale_release = store.release(**identity)
        third = store.claim(
            **identity, actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_002,
        )
        passed = (
            first.claimed and first_release and newer.claimed
            and not stale_release and not third.claimed
        )
        print(json.dumps({
            "probe": "stale_cleanup_vs_newer_attempt",
            "first_claimed": first.claimed,
            "first_release": first_release,
            "newer_claimed": newer.claimed,
            "stale_release": stale_release,
            "third_claimed": third.claimed,
            "passed": passed,
        }, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import sqlite3
import sys
from uuid import uuid4

import pytest

from eitaa_bridge.errors import CoordinatorIdentityError, CoordinatorSchemaError
from eitaa_bridge.infrastructure.coordinator import (
    COORDINATOR_SCHEMA_VERSION,
    CoordinatorDatabase,
    ProtectedPhone,
    WindowsDpapiPhoneProtector,
    masked_phone,
    validate_canonical_e164,
)
from eitaa_bridge.infrastructure.coordinator.schema import REQUIRED_TABLES
from eitaa_bridge.infrastructure.coordinator.schema import SCHEMA_V1_CHECKSUM, SCHEMA_V1_SQL


def protected_phone(
    seed: str = "1",
    *,
    display_hint: str = "+••••••••67",
) -> ProtectedPhone:
    return ProtectedPhone(
        ciphertext=f"protected-{seed}".encode("ascii"),
        key_version=1,
        fingerprint=(seed * 64)[:64],
        display_hint=display_hint,
    )


def bootstrap(
    database: CoordinatorDatabase,
    *,
    seed: str = "1",
    display_hint: str = "+••••••••67",
):
    return database.bootstrap_legacy_account(
        protected_phone=protected_phone(seed, display_hint=display_hint),
        display_name="Local administrator",
        backup_name="verified-backup.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=3,
        source_total_bytes=1234,
    )


def test_coordinator_schema_is_versioned_complete_and_idempotent(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(path)
    database.initialize()
    database.initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert REQUIRED_TABLES <= tables
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_schema6_upgrades_atomically_to_persistent_provider_receipts(tmp_path):
    path = tmp_path / "coordinator-v6.sqlite3"
    database = CoordinatorDatabase(path)
    database.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "DROP TRIGGER provider_operation_receipts_provider_scope_insert"
        )
        connection.execute("DROP TABLE provider_operation_receipts")
        connection.execute("DROP TABLE service_credentials")
        connection.execute("DELETE FROM schema_migrations WHERE version>=7")
        connection.execute("PRAGMA user_version=6")
        connection.commit()

    database.initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION
        assert connection.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name='provider_operation_receipts'
            """
        ).fetchone()[0] == 1
        assert connection.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name='service_credentials'
            """
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_read_only_summary_does_not_upgrade_or_change_an_old_database(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
            + f"1,'{SCHEMA_V1_CHECKSUM}','now');\n"
            + "PRAGMA user_version=1;\n"
            + "COMMIT;\n"
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    summary = CoordinatorDatabase(path).read_only_safe_summary()

    assert summary["schema_version"] == 1
    assert summary["schema_upgrade_required"] is True
    assert summary["latest_migration"] is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_bootstrap_is_scoped_safe_and_does_not_store_plain_phone(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(path)
    result = bootstrap(database)
    summary = database.safe_summary()

    assert summary["counts"] == {
        "app_users": 1,
        "phone_accounts": 1,
        "phone_account_memberships": 1,
        "messenger_accounts": 1,
        "audit_events": 1,
    }
    assert summary["latest_migration"]["status"] == "verified"
    assert summary["latest_migration"]["messenger_account_id"] == result.messenger_account_id
    with sqlite3.connect(path) as connection:
        session = connection.execute(
            """
            SELECT auth_state,safe_reason_code
            FROM messenger_session_metadata WHERE messenger_account_id=?
            """,
            (result.messenger_account_id,),
        ).fetchone()
        assert session == ("absent", "legacy_session_copied_unverified")
        membership = connection.execute(
            "SELECT role,status FROM phone_account_memberships"
        ).fetchone()
        assert membership == ("owner", "active")
    raw = path.read_bytes()
    assert b"+989121234567" not in raw
    assert b"normalized_phone" not in raw
    assert b"access_hash" not in raw


def test_bootstrap_accepts_full_canonical_display_hint(tmp_path):
    canonical = "+999123456789"
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    result = bootstrap(database, display_hint=canonical)

    with sqlite3.connect(database.path) as connection:
        stored = connection.execute(
            "SELECT display_hint FROM phone_accounts WHERE id=?",
            (result.phone_account_id,),
        ).fetchone()[0]
    if stored != canonical:
        pytest.fail(
            "Coordinator persistence did not preserve the allowed canonical display hint.",
            pytrace=False,
        )

def test_phone_and_provider_uniqueness_are_enforced(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    first = bootstrap(database)
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO phone_accounts(
                    id,phone_ciphertext,phone_key_version,phone_fingerprint,
                    status,created_at,updated_at
                ) VALUES(?,?,1,?,'active','now','now')
                """,
                (str(uuid4()), b"other", "1" * 64),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO messenger_accounts(
                    id,phone_account_id,provider,lifecycle_state,
                    desired_worker_state,created_at,updated_at
                ) VALUES(?,?,'eitaa','created','stopped','now','now')
                """,
                (str(uuid4()), first.phone_account_id),
            )


def test_last_active_owner_and_append_only_audit_are_database_invariants(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    result = bootstrap(database)
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError, match="last_active_owner_required"):
            connection.execute(
                "UPDATE phone_account_memberships SET status='revoked' WHERE id=?",
                (result.membership_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="audit_events_are_append_only"):
            connection.execute("UPDATE audit_events SET result='failed'")
        with pytest.raises(sqlite3.IntegrityError, match="audit_events_are_append_only"):
            connection.execute("DELETE FROM audit_events")


def test_coordinator_rejects_database_with_newer_schema(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={COORDINATOR_SCHEMA_VERSION + 1}")
    with pytest.raises(CoordinatorSchemaError) as error:
        CoordinatorDatabase(path).initialize()
    assert error.value.code == "coordinator_schema_newer"


@pytest.mark.parametrize(
    "value",
    ["09121234567", "+012345678", "+98 9121234567", "+98-9121234567", "", "+123"],
)
def test_phone_confirmation_requires_canonical_e164(value):
    with pytest.raises(CoordinatorIdentityError):
        validate_canonical_e164(value)


def test_product_phone_display_preserves_full_canonical_e164():
    canonical = "+999123456789"
    if masked_phone(canonical) != canonical:
        pytest.fail(
            "The product display boundary did not preserve canonical E.164.",
            pytrace=False,
        )



def test_schema9_binds_service_receipts_and_keeps_legacy_conservative(tmp_path):
    """F-085 gap #3: v9 adds per-service receipt ownership; a legacy v8 store
    upgrades in place, and owner-less receipts are never attributed to a
    service (no guessing)."""
    from eitaa_bridge.infrastructure.coordinator.receipts import (
        ProviderOperationReceiptStore,
    )
    from eitaa_bridge.infrastructure.coordinator.schema import (
        SCHEMA_CHECKSUMS,
        SCHEMA_V2_SQL,
        SCHEMA_V3_SQL,
        SCHEMA_V4_SQL,
        SCHEMA_V5_SQL,
        SCHEMA_V6_SQL,
        SCHEMA_V7_SQL,
        SCHEMA_V8_SQL,
    )

    path = tmp_path / "coordinator-v8.sqlite3"
    with sqlite3.connect(path) as connection:
        script = "BEGIN;\n" + SCHEMA_V1_SQL
        script += f"\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(1,'{SCHEMA_V1_CHECKSUM}','now');\n"
        for version, sql in (
            (2, SCHEMA_V2_SQL),
            (3, SCHEMA_V3_SQL),
            (4, SCHEMA_V4_SQL),
            (5, SCHEMA_V5_SQL),
            (6, SCHEMA_V6_SQL),
            (7, SCHEMA_V7_SQL),
            (8, SCHEMA_V8_SQL),
        ):
            script += sql
            script += f"\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES({version},'{SCHEMA_CHECKSUMS[version]}','now');\n"
        script += "PRAGMA user_version=8;\nCOMMIT;\n"
        connection.executescript(script)

    database = CoordinatorDatabase(path)
    database.initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(provider_operation_receipts)")
        }
        assert "service_credential_id" in columns

    summary = database.bootstrap_legacy_account(
        protected_phone=protected_phone(),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    admin_id = summary.app_user_id
    account_id = summary.messenger_account_id

    store = ProviderOperationReceiptStore(database)
    fingerprint = hashlib.sha256(b"synthetic-payload").hexdigest()
    deadline = 4_000_000_000_000

    legacy_claim = store.claim(
        messenger_account_id=account_id,
        actor_app_user_id=admin_id,
        actor_global_role="admin",
        operation="messages.send_text",
        idempotency_key="legacy-key-0000001",
        request_fingerprint=fingerprint,
        claim_deadline_unix_ms=deadline,
    )
    assert legacy_claim.claimed is True
    assert legacy_claim.receipt.service_credential_id is None
    store.complete(
        messenger_account_id=account_id,
        actor_app_user_id=admin_id,
        operation="messages.send_text",
        idempotency_key="legacy-key-0000001",
        request_fingerprint=fingerprint,
        outcome="succeeded",
        result_reference="message:1",
        contact_created=None,
        safe_reason_code=None,
    )

    # A service credential replaying a legacy key must be refused: the owner
    # of the legacy receipt is unknown and is never guessed.
    with pytest.raises(CoordinatorSchemaError) as conservative:
        store.claim(
            messenger_account_id=account_id,
            actor_app_user_id=admin_id,
            actor_global_role="user",
            operation="messages.send_text",
            idempotency_key="legacy-key-0000001",
            request_fingerprint=fingerprint,
            claim_deadline_unix_ms=deadline,
            service_credential_id="00000000-0000-4000-8000-0000000000c1",
        )
    assert conservative.value.code == "provider_idempotency_owner_mismatch"

    # A service-bound claim stores its owner and replays only for the owner.
    service_claim = store.claim(
        messenger_account_id=account_id,
        actor_app_user_id=admin_id,
        actor_global_role="user",
        operation="messages.send_text",
        idempotency_key="service-key-00000001",
        request_fingerprint=fingerprint,
        claim_deadline_unix_ms=deadline,
        service_credential_id="00000000-0000-4000-8000-0000000000c1",
    )
    assert service_claim.claimed is True
    assert service_claim.receipt.service_credential_id == "00000000-0000-4000-8000-0000000000c1"

    with pytest.raises(CoordinatorSchemaError) as other_service:
        store.claim(
            messenger_account_id=account_id,
            actor_app_user_id=admin_id,
            actor_global_role="user",
            operation="messages.send_text",
            idempotency_key="service-key-00000001",
            request_fingerprint=fingerprint,
            claim_deadline_unix_ms=deadline,
            service_credential_id="00000000-0000-4000-8000-0000000000c2",
        )
    assert other_service.value.code == "provider_idempotency_owner_mismatch"

from __future__ import annotations

import hashlib

import pytest

from eitaa_bridge.errors import CoordinatorSchemaError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
    ProviderOperationReceiptStore,
)


@pytest.fixture
def receipt_store(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    database.initialize()
    account = database.bootstrap_legacy_account(
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
    return database, ProviderOperationReceiptStore(database), account


def result_for(operation: str) -> dict[str, object]:
    if operation.startswith("messages."):
        return {
            "outcome": "succeeded",
            "result_reference": "bale:message:42",
            "contact_created": None,
            "safe_reason_code": None,
        }
    return {
        "outcome": "succeeded",
        "result_reference": "bale:contact:42",
        "contact_created": operation == "contacts.upsert",
        "safe_reason_code": None,
    }


@pytest.mark.parametrize(
    "operation",
    [
        "messages.send_text",
        "messages.send_media",
        "contacts.upsert",
        "contacts.remove",
    ],
)
def test_generation_two_complete_requires_current_attempt_token(
    receipt_store, operation
):
    database, store, account = receipt_store
    identity = {
        "messenger_account_id": account.messenger_account_id,
        "actor_app_user_id": account.app_user_id,
        "operation": operation,
        "idempotency_key": f"fence-test-{operation.replace('.', '-')}",
        "request_fingerprint": hashlib.sha256(operation.encode()).hexdigest(),
    }
    first = store.claim(
        **identity,
        actor_global_role="admin",
        claim_deadline_unix_ms=4_000_000_000_000,
    )
    old_token = first.receipt.attempt_token
    assert old_token
    assert store.release(**identity, attempt_token=old_token)
    second = store.claim(
        **identity,
        actor_global_role="admin",
        claim_deadline_unix_ms=4_000_000_000_001,
    )
    new_token = second.receipt.attempt_token
    assert second.claimed and second.receipt.attempt_generation == 2
    assert new_token and new_token != old_token

    database = CoordinatorDatabase(database.path)
    store = ProviderOperationReceiptStore(database)

    result = result_for(operation)
    with pytest.raises(CoordinatorSchemaError) as missing:
        store.complete(**identity, **result)
    assert missing.value.code == "provider_receipt_attempt_mismatch"

    with pytest.raises(CoordinatorSchemaError) as stale:
        store.complete(**identity, attempt_token=old_token, **result)
    assert stale.value.code == "provider_receipt_attempt_mismatch"

    with database._connect() as connection:
        row = connection.execute(
            "SELECT outcome,attempt_generation,attempt_token FROM provider_operation_receipts "
            "WHERE messenger_account_id=? AND operation=? AND idempotency_key=?",
            (identity["messenger_account_id"], operation, identity["idempotency_key"]),
        ).fetchone()
    assert row["outcome"] == "in_progress"
    assert row["attempt_generation"] == 2
    assert row["attempt_token"] == new_token

    completed = store.complete(
        **identity, attempt_token=new_token, **result
    )
    assert completed.outcome == "succeeded"
    assert completed.result_reference == result["result_reference"]
    replay = store.complete(**identity, attempt_token=new_token, **result)
    assert replay.outcome == "succeeded"
    assert replay.updated_at == completed.updated_at
    with pytest.raises(CoordinatorSchemaError) as terminal_conflict:
        store.complete(
            **identity,
            attempt_token=old_token,
            **{**result, "result_reference": "bale:other:99"},
        )
    assert terminal_conflict.value.code == "provider_receipt_result_mismatch"


def test_generation_one_legacy_completion_and_expired_replay(receipt_store):
    database, store, account = receipt_store
    identity = {
        "messenger_account_id": account.messenger_account_id,
        "actor_app_user_id": account.app_user_id,
        "operation": "messages.send_text",
        "idempotency_key": "fence-legacy-generation-one",
        "request_fingerprint": hashlib.sha256(b"legacy").hexdigest(),
    }
    claim = store.claim(
        **identity,
        actor_global_role="admin",
        claim_deadline_unix_ms=4_000_000_000_000,
    )
    # Simulate a row upgraded from the legacy schema: generation one and no token.
    with database._connect() as connection:
        connection.execute(
            "UPDATE provider_operation_receipts SET attempt_token=NULL,attempt_generation=1 "
            "WHERE messenger_account_id=? AND operation=? AND idempotency_key=?",
            (identity["messenger_account_id"], identity["operation"], identity["idempotency_key"]),
        )
    completed = store.complete(
        **identity,
        outcome="succeeded",
        result_reference="bale:message:legacy",
        contact_created=None,
        safe_reason_code=None,
    )
    assert completed.outcome == "succeeded"

    expired_identity = {**identity, "idempotency_key": "fence-expired-generation-one"}
    expired = store.claim(
        **expired_identity,
        actor_global_role="admin",
        claim_deadline_unix_ms=1,
    )
    token = expired.receipt.attempt_token
    replay = store.claim(
        **expired_identity,
        actor_global_role="admin",
        claim_deadline_unix_ms=4_000_000_000_000,
    )
    assert replay.claimed is False
    assert replay.receipt.attempt_generation == 1
    assert replay.receipt.attempt_token == token
    uncertain = store.complete(
        **expired_identity,
        attempt_token=token,
        outcome="uncertain",
        result_reference=None,
        contact_created=None,
        safe_reason_code="provider_send_previous_attempt_incomplete",
    )
    assert uncertain.outcome == "uncertain"
    assert uncertain.attempt_generation == 1

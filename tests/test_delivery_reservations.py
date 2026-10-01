"""P3 delivery reservation tests: durable atomic capacity accounting.

Every fixture is synthetic and offline. The tests assert the guarantees
the phase demands: atomic capacity acceptance across two connections AND
two separate OS processes, a final state machine (reserved→consumed/
cancelled/expired, never revived), one-shot refunds bounded by capacity,
restart durability, honest unavailability, and the documented legacy
interaction (an unreserved send cannot take a slot the reservation
already debited). Token, refund and operation counts are asserted
explicitly; no real worker ever runs.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
)
from eitaa_bridge.infrastructure.coordinator.rate_policy import (
    AccountExecutionPolicyService,
)
from eitaa_bridge.infrastructure.coordinator.reservations import (
    DeliveryReservationError,
    ServiceDeliveryReservationStore,
)
from eitaa_bridge.infrastructure.coordinator.service_credentials import (
    ServiceCredentialService,
)

_TEST_KEY = b"p3-reservation-test-key"
_BASE = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)


def _mac(payload: bytes) -> str:
    return hashlib.sha256(_TEST_KEY + b"|" + payload).hexdigest()


def _store(database, clock=None) -> ServiceDeliveryReservationStore:
    return ServiceDeliveryReservationStore(
        database,
        binding_mac=_mac,
        now=(clock or (lambda: _BASE)),
    )


def _create_kwargs(
    credential_id: str,
    actor_id: str,
    account_id: str,
    *,
    key: str = "res-key-000000000001",
    phone: str = "+989120000001",
) -> dict:
    return {
        "service_credential_id": credential_id,
        "actor_app_user_id": actor_id,
        "intent": "otp",
        "provider": "eitaa",
        "messenger_account_id": account_id,
        "recipient_binding": _mac(f"otp|service|{phone}".encode()),
        "idempotency_key": key,
    }


def _bucket(database_path: Path, account_id: str) -> dict:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT * FROM account_execution_limits
            WHERE messenger_account_id=? AND operation_scope='messages.send_text'
            """,
            (account_id,),
        ).fetchone()
    return dict(row) if row is not None else {}


def _set_bucket_tokens(database_path: Path, account_id: str, available: float) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO account_execution_limits(
                messenger_account_id, provider, operation_scope, capacity,
                refill_per_second, available_tokens, last_refill_at,
                circuit_state, consecutive_failures, created_at, updated_at
            ) VALUES(?, 'eitaa', 'messages.send_text', 5, 1.0, ?, ?, 'closed', 0, ?, ?)
            ON CONFLICT(messenger_account_id, operation_scope) DO UPDATE
            SET available_tokens=excluded.available_tokens,
                last_refill_at=excluded.last_refill_at
            """,
            (account_id, available, now, now, now),
        )
        connection.commit()


@pytest.fixture()
def environment(tmp_path: Path):
    database_path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(database_path)
    database.initialize()
    summary = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone",
            key_version=1,
            fingerprint="b" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    # Reservations reference REAL credential and app-user rows (FKs are
    # enforced): issue one service credential owned by the administrator.
    credential, _token = ServiceCredentialService(database).create_credential(
        service_name="reservation-test-service",
        allowed_providers=["eitaa"],
        allowed_messenger_account_ids=[summary.messenger_account_id],
        scopes=["messages.send"],
        description="P3 reservation fixture",
        created_by_app_user_id=summary.app_user_id,
    )
    return (
        database,
        database_path,
        summary.messenger_account_id,
        credential.id,
        summary.app_user_id,
    )


def test_atomic_capacity_acceptance_across_two_connections(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    _set_bucket_tokens(database_path, account_id, 1.0)
    store_a = _store(database)
    store_b = _store(CoordinatorDatabase(database_path))
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def _attempt(store: ServiceDeliveryReservationStore, key: str) -> None:
        barrier.wait()
        try:
            reservation = store.create(
                **_create_kwargs(credential_id, actor_id, account_id, key=key)
            )
            outcomes.append(f"accepted:{reservation.id}")
        except DeliveryReservationError as exc:
            outcomes.append(f"refused:{exc.code}")

    threads = [
        threading.Thread(target=_attempt, args=(store, key))
        for store, key in (
            (store_a, "res-key-000000000001"),
            (store_b, "res-key-000000000002"),
        )
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    accepted = [item for item in outcomes if item.startswith("accepted:")]
    refused = [item for item in outcomes if item.startswith("refused:")]
    assert len(accepted) == 1, outcomes
    assert len(refused) == 1
    assert refused[0].endswith("delivery_reservation_capacity_unavailable")
    # The winner holds the only slot: whatever refill has added since the
    # debit, less than one full token can be free.
    remaining = _bucket(database_path, account_id)["available_tokens"]
    assert 0.0 <= remaining < 1.0, remaining


_RACE_SCRIPT = """
import hashlib, json, os, sys, time, uuid
from pathlib import Path
from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase
from eitaa_bridge.infrastructure.coordinator.reservations import (
    DeliveryReservationError, ServiceDeliveryReservationStore,
)

database_path = Path(sys.argv[1])
account_id = sys.argv[2]
credential_id = sys.argv[3]
actor_id = sys.argv[4]
barrier_dir = Path(sys.argv[5])
idempotency_key = sys.argv[6]

key = b"p3-reservation-test-key"
def mac(payload: bytes) -> str:
    return hashlib.sha256(key + b"|" + payload).hexdigest()

database = CoordinatorDatabase(database_path)
store = ServiceDeliveryReservationStore(database, binding_mac=mac)
# An atomic cross-process start barrier: each process creates its own
# sentinel file (exclusive create, no read-modify-write race) and waits
# until both sentinels exist.
(barrier_dir / f"ready-{os.getpid()}-{uuid.uuid4().hex}.flag").write_text("go")
deadline = time.time() + 60
while len(list(barrier_dir.glob("ready-*.flag"))) < 2:
    if time.time() > deadline:
        raise SystemExit("barrier timeout")
    time.sleep(0.002)
try:
    reservation = store.create(
        service_credential_id=credential_id,
        actor_app_user_id=actor_id,
        intent="otp",
        provider="eitaa",
        messenger_account_id=account_id,
        recipient_binding=mac(b"otp|service|+989120000001"),
        idempotency_key=idempotency_key,
    )
    print(json.dumps({"outcome": "accepted", "id": reservation.id}))
except DeliveryReservationError as exc:
    print(json.dumps({"outcome": "refused", "code": exc.code}))
"""


def test_atomic_capacity_acceptance_across_two_processes(environment, tmp_path):
    _database, database_path, account_id, credential_id, actor_id = environment
    _set_bucket_tokens(database_path, account_id, 1.0)
    # Process startup can take longer than the fixture's one-second refill.
    # Keep this race about one atomic slot, independent of startup latency.
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE account_execution_limits SET refill_per_second=0.001 "
            "WHERE messenger_account_id=? AND operation_scope='messages.send_text'",
            (account_id,),
        )
    barrier_dir = tmp_path / "barrier"
    barrier_dir.mkdir()
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                _RACE_SCRIPT,
                str(database_path),
                account_id,
                credential_id,
                actor_id,
                str(barrier_dir),
                f"res-key-{index:016d}",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        for index in range(2)
    ]
    outputs = [process.communicate(timeout=180)[0].strip() for process in processes]
    for process in processes:
        assert process.returncode == 0, outputs
    results = [json.loads(output) for output in outputs if output]
    accepted = [item for item in results if item["outcome"] == "accepted"]
    refused = [item for item in results if item["outcome"] == "refused"]
    assert len(accepted) == 1, results
    assert len(refused) == 1
    assert refused[0]["code"] == "delivery_reservation_capacity_unavailable"
    remaining = _bucket(database_path, account_id)["available_tokens"]
    assert 0.0 <= remaining < 1.0, remaining


def test_idempotent_create_and_fingerprint_conflict(environment):
    database, _database_path, account_id, credential_id, actor_id = environment
    store = _store(database)
    first = store.create(**_create_kwargs(credential_id, actor_id, account_id))
    again = store.create(**_create_kwargs(credential_id, actor_id, account_id))
    assert again.id == first.id
    assert again.created_at == first.created_at

    # Same idempotency key, different recipient payload: a conflict — never
    # a silent second reservation on the same key.
    with pytest.raises(DeliveryReservationError) as conflict:
        store.create(
            **_create_kwargs(
                credential_id, actor_id, account_id, phone="+989120000002"
            )
        )
    assert conflict.value.code == "delivery_reservation_conflict"


def test_expiry_refunds_once_and_never_revives(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    clock = {"now": _BASE}
    store = _store(database, clock=lambda: clock["now"])
    reservation = store.create(**_create_kwargs(credential_id, actor_id, account_id), ttl_seconds=60)
    assert reservation.state == "reserved"
    assert reservation.token_reserved is True
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(4.0)

    clock["now"] = _BASE + timedelta(seconds=61)
    expired = store.status(
        reservation_id=reservation.id,
        service_credential_id=reservation.service_credential_id,
    )
    assert expired.state == "expired"
    assert expired.token_refunded is True
    # The refund is bounded by capacity and happens exactly once.
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(5.0)
    assert store.expire_due(now=clock["now"]) == 0
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(5.0)

    # Re-creating with the SAME idempotency key after expiry answers the
    # same terminal record — the decision is replayed, the row is never
    # revived. A new attempt needs a new key.
    replayed = store.create(
        **_create_kwargs(credential_id, actor_id, account_id), ttl_seconds=60
    )
    assert replayed.id == reservation.id
    assert replayed.state == "expired"
    fresh = store.create(
        **_create_kwargs(credential_id, actor_id, account_id, key="res-key-000000000002"),
        ttl_seconds=60,
    )
    assert fresh.id != reservation.id
    assert fresh.state == "reserved"


def test_cancel_is_owner_scoped_idempotent_and_refunds_once(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    store = _store(database)
    other_credential, _token = ServiceCredentialService(database).create_credential(
        service_name="other-service",
        allowed_providers=["eitaa"],
        allowed_messenger_account_ids=[account_id],
        scopes=["messages.send"],
        description="foreign owner fixture",
        created_by_app_user_id=actor_id,
    )
    reservation = store.create(**_create_kwargs(credential_id, actor_id, account_id))

    foreign = store.cancel(
        reservation_id=reservation.id,
        service_credential_id=other_credential.id,
    )
    assert foreign is None  # a foreign owner learns nothing and cancels nothing

    cancelled = store.cancel(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
    )
    assert cancelled.state == "cancelled"
    assert cancelled.token_refunded is True
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(5.0)

    again = store.cancel(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
    )
    assert again.state == "cancelled"
    assert again.token_refunded is True
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(5.0)


def test_consume_is_atomic_idempotent_and_checks_lifecycle_and_revision(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    clock = {"now": _BASE}
    store = _store(database, clock=lambda: clock["now"])
    reservation = store.create(**_create_kwargs(credential_id, actor_id, account_id))

    consumed = store.consume(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
        operation_id="11111111-1111-4111-8111-111111111111",
    )
    assert consumed.state == "consumed"
    assert consumed.operation_id == "11111111-1111-4111-8111-111111111111"

    # Repeated consume of the SAME operation returns the record without a
    # second debit; a different operation on a consumed slot is refused.
    replay = store.consume(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
        operation_id="11111111-1111-4111-8111-111111111111",
    )
    assert replay.state == "consumed"
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(4.0)
    with pytest.raises(DeliveryReservationError) as duplicate:
        store.consume(
            reservation_id=reservation.id,
            service_credential_id=credential_id,
            operation_id="22222222-2222-4222-8222-222222222222",
        )
    assert duplicate.value.code == "delivery_reservation_already_consumed"

    # Archive the pinned account: consumption is refused honestly.
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE messenger_accounts SET lifecycle_state='archived' WHERE id=?",
            (account_id,),
        )
        connection.commit()
    second = store.create(
        **_create_kwargs(credential_id, actor_id, account_id, key="res-key-000000000002")
    )
    with pytest.raises(DeliveryReservationError) as unavailable:
        store.consume(
            reservation_id=second.id,
            service_credential_id=credential_id,
            operation_id="33333333-3333-4333-8333-333333333333",
        )
    assert unavailable.value.code == "account_unavailable"

    # A changed profile revision refuses consumption: no silent account
    # switch; the caller must reserve fresh.
    clock["now"] = _BASE + timedelta(seconds=5)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE messenger_accounts SET lifecycle_state='active' WHERE id=?",
            (account_id,),
        )
        connection.execute(
            """
            INSERT INTO service_sender_profiles(
                id, service_credential_id, intent, provider, messenger_account_id,
                enabled, revision, created_by_app_user_id, created_at, updated_at
            ) VALUES(?, ?, 'otp', 'eitaa', ?, 1, 7, ?, ?, ?)
            """,
            (
                "44444444-4444-4444-8444-444444444444",
                credential_id,
                account_id,
                actor_id,
                datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            ),
        )
        connection.commit()
    pinned = store.create(
        **_create_kwargs(credential_id, actor_id, account_id, key="res-key-000000000003"),
        sender_profile_id="44444444-4444-4444-8444-444444444444",
        sender_profile_revision=7,
    )
    with pytest.raises(DeliveryReservationError) as revision:
        store.consume(
            reservation_id=pinned.id,
            service_credential_id=credential_id,
            operation_id="55555555-5555-4555-8555-555555555555",
            sender_profile_revision=8,
        )
    assert revision.value.code == "sender_profile_revision_changed"
    same_revision = store.consume(
        reservation_id=pinned.id,
        service_credential_id=credential_id,
        operation_id="55555555-5555-4555-8555-555555555555",
        sender_profile_revision=7,
    )
    assert same_revision.state == "consumed"


def test_restart_preserves_records_before_and_after_consume(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    store = _store(database)
    before = store.create(**_create_kwargs(credential_id, actor_id, account_id))

    # A crash after the debit: a fresh process sees the same reservation,
    # still reserved with its token accounted.
    restarted = _store(CoordinatorDatabase(database_path))
    recovered = restarted.status(
        reservation_id=before.id,
        service_credential_id=credential_id,
    )
    assert recovered.state == "reserved"
    assert recovered.token_reserved is True
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(4.0)

    # Consumption survives a restart: the operation id is durable.
    consumed = restarted.consume(
        reservation_id=before.id,
        service_credential_id=credential_id,
        operation_id="66666666-6666-4666-8666-666666666666",
    )
    assert consumed.state == "consumed"
    after_restart = _store(CoordinatorDatabase(database_path)).status(
        reservation_id=before.id,
        service_credential_id=credential_id,
    )
    assert after_restart.state == "consumed"
    assert after_restart.operation_id == "66666666-6666-4666-8666-666666666666"


def test_legacy_send_cannot_take_the_reserved_slot(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    # One free slot: the reservation takes it, leaving nothing for the
    # legacy unreserved path to grab.
    _set_bucket_tokens(database_path, account_id, 1.0)
    store = _store(database)
    reservation = store.create(**_create_kwargs(credential_id, actor_id, account_id))
    policy = AccountExecutionPolicyService(database)
    # The legacy unreserved path debits the same bucket: with the slot
    # already taken it is refused instead of overrunning capacity.
    permit = policy.acquire(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE,
    )
    assert permit.allowed is False
    assert permit.blocked_reason == "rate_limited"

    # Cancelling the reservation frees the slot again — a reservation never
    # locks capacity beyond its own debit.
    store.cancel(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
    )
    permit_after = policy.acquire(
        messenger_account_id=account_id,
        operation_scope="messages.send_text",
        now=_BASE + timedelta(milliseconds=50),
    )
    assert permit_after.allowed is True


def test_mark_send_started_forbids_refund(environment):
    database, database_path, account_id, credential_id, actor_id = environment
    clock = {"now": _BASE}
    store = _store(database, clock=lambda: clock["now"])
    reservation = store.create(**_create_kwargs(credential_id, actor_id, account_id))
    store.consume(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
        operation_id="77777777-7777-4777-8777-777777777777",
    )
    started = store.mark_send_started(
        reservation_id=reservation.id,
        operation_id="77777777-7777-4777-8777-777777777777",
    )
    assert started.send_started_at is not None

    clock["now"] = _BASE + timedelta(seconds=120)
    # The slot is long past expiry, but a started send is never refunded —
    # an uncertain outcome stays uncertain (timeout is not a refund).
    store.expire_due(now=clock["now"])
    row = store.status(
        reservation_id=reservation.id,
        service_credential_id=credential_id,
    )
    assert row.state == "consumed"
    assert row.token_refunded is False
    assert _bucket(database_path, account_id)["available_tokens"] == pytest.approx(4.0)


def test_outstanding_and_rate_limits(environment):
    database, _database_path, account_id, credential_id, actor_id = environment
    store = _store(database)
    ids = []
    for index in range(4):
        reservation = store.create(
            **_create_kwargs(credential_id, actor_id, account_id, key=f"res-key-{index:016d}")
        )
        ids.append(reservation.id)
    assert store.outstanding_count(service_credential_id=credential_id) == 4
    with pytest.raises(DeliveryReservationError) as limit:
        store.create(
            **_create_kwargs(credential_id, actor_id, account_id, key="res-key-000000000009")
        )
    assert limit.value.code == "delivery_reservation_outstanding_limit"

    # Cancelling one frees the outstanding slot again.
    store.cancel(reservation_id=ids[0], service_credential_id=credential_id)
    freed = store.create(
        **_create_kwargs(credential_id, actor_id, account_id, key="res-key-000000000009")
    )
    assert freed.state == "reserved"
    store.cancel(reservation_id=freed.id, service_credential_id=credential_id)
    for index in range(1, 4):
        store.cancel(reservation_id=ids[index], service_credential_id=credential_id)

    # Creation-rate abuse is refused before any accounting: twelve creates
    # fill the window (each immediately cancelled, so nothing is held), the
    # thirteenth is refused while outstanding stays zero.
    for index in range(7):
        churned = store.create(
            **_create_kwargs(credential_id, actor_id, account_id, key=f"res-key-2{index:015d}")
        )
        store.cancel(reservation_id=churned.id, service_credential_id=credential_id)
    assert store.outstanding_count(service_credential_id=credential_id) == 0
    with pytest.raises(DeliveryReservationError) as rate:
        store.create(
            **_create_kwargs(credential_id, actor_id, account_id, key="res-key-999999999999")
        )
    assert rate.value.code == "delivery_reservation_rate_limited"

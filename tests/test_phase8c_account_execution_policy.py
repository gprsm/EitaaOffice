from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
import threading
from uuid import uuid4

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import EitaaRuntimeError
from eitaa_bridge.infrastructure.coordinator import (
    AccountExecutionPolicyService,
    COORDINATOR_SCHEMA_VERSION,
    CoordinatorDatabase,
    ExecutionErrorClass,
    PersistentOperationJobService,
    ProtectedPhone,
    classify_failure,
)
from eitaa_bridge.infrastructure.coordinator.schema import (
    SCHEMA_CHECKSUMS,
    SCHEMA_V1_SQL,
    SCHEMA_V2_SQL,
    SCHEMA_V3_SQL,
)


UTC = timezone.utc


def _bootstrap(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    first = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-rate-phone",
            key_version=1,
            fingerprint="6" * 64,
            display_hint="+••••••••16",
        ),
        display_name="Rate administrator",
        backup_name="verified.zip",
        source_manifest_sha256="7" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    second_account, second_phone = str(uuid4()), str(uuid4())
    now = "2026-08-11T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO phone_accounts(
                id,phone_ciphertext,phone_key_version,phone_fingerprint,display_hint,
                status,created_at,updated_at
            ) VALUES(?,?,1,?,?,'active',?,?)
            """,
            (second_phone, b"protected-rate-second", "5" * 64, "+••••••••15", now, now),
        )
        connection.execute(
            """
            INSERT INTO messenger_accounts(
                id,phone_account_id,provider,label,lifecycle_state,desired_worker_state,
                capability_revision,created_at,updated_at
            ) VALUES(?,?,'eitaa','Second','created','stopped',0,?,?)
            """,
            (second_account, second_phone, now, now),
        )
        connection.execute(
            """
            INSERT INTO messenger_session_metadata(
                messenger_account_id,auth_state,session_generation,storage_revision,
                last_auth_transition_at,created_at,updated_at
            ) VALUES(?,'absent',1,1,?,?,?)
            """,
            (second_account, now, now, now),
        )
    return database, first, second_account


def test_schema3_upgrades_to_account_execution_policy_schema4(tmp_path):
    path = tmp_path / "coordinator-v3.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + f"\nINSERT INTO schema_migrations VALUES(1,'{SCHEMA_CHECKSUMS[1]}','now');\n"
            + SCHEMA_V2_SQL
            + f"\nINSERT INTO schema_migrations VALUES(2,'{SCHEMA_CHECKSUMS[2]}','now');\n"
            + SCHEMA_V3_SQL
            + f"\nINSERT INTO schema_migrations VALUES(3,'{SCHEMA_CHECKSUMS[3]}','now');\n"
            + "PRAGMA user_version=3;\nCOMMIT;"
        )
    CoordinatorDatabase(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=4"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[4]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    ("code", "kwargs", "expected"),
    [
        ("provider_timeout", {}, ExecutionErrorClass.TRANSIENT),
        ("session_revoked", {}, ExecutionErrorClass.AUTH),
        ("provider_not_authorized", {}, ExecutionErrorClass.AUTH),
        ("user_privacy_restricted", {}, ExecutionErrorClass.PRIVACY),
        ("recipient_invalid", {}, ExecutionErrorClass.PERMANENT),
        ("recipient_not_found", {}, ExecutionErrorClass.PERMANENT),
        ("send_timeout", {"effect_may_have_occurred": True}, ExecutionErrorClass.UNCERTAIN),
        ("unexpected_exception", {}, ExecutionErrorClass.INTERNAL),
    ],
)
def test_error_taxonomy_is_explicit_and_safe(code, kwargs, expected):
    classified = classify_failure(code, **kwargs)
    assert classified.error_class is expected
    assert classified.retryable is (expected in {ExecutionErrorClass.TRANSIENT, ExecutionErrorClass.INTERNAL})


def test_token_bucket_is_account_scoped_and_never_falls_back(tmp_path):
    database, first, second = _bootstrap(tmp_path)
    policy = AccountExecutionPolicyService(
        database, default_capacity=2, default_refill_per_second=1
    )
    now = datetime(2026, 8, 11, tzinfo=UTC)
    assert policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope="message.send", now=now,
    ).allowed
    assert policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope="message.send", now=now,
    ).allowed
    blocked = policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope="message.send", now=now,
    )
    other = policy.acquire(
        messenger_account_id=second,
        operation_scope="message.send", now=now,
    )

    assert blocked.allowed is False
    assert blocked.messenger_account_id == first.messenger_account_id
    assert blocked.blocked_reason == "rate_limited"
    assert blocked.retry_after_ms == 1000
    assert other.allowed is True
    assert other.messenger_account_id == second
    assert policy.state(
        messenger_account_id=first.messenger_account_id,
        operation_scope="message.send",
    )["available_tokens"] == 0
    assert policy.state(
        messenger_account_id=second,
        operation_scope="message.send",
    )["available_tokens"] == 1


def test_retry_after_backoff_and_half_open_circuit_have_one_probe(tmp_path):
    database, first, _ = _bootstrap(tmp_path)
    policy = AccountExecutionPolicyService(
        database,
        default_capacity=10,
        default_refill_per_second=10,
        circuit_failure_threshold=5,
    )
    start = datetime(2026, 8, 11, tzinfo=UTC)
    operation = "message.send"
    claim = str(uuid4())
    policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
        claim_id=claim,
        now=start,
    )
    first_failure = policy.record_failure(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
        claim_id=claim,
        failure=classify_failure("flood_wait", retry_after_ms=5000),
        now=start,
    )
    assert first_failure.retry_after_ms == 5000
    assert policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
        now=start + timedelta(seconds=4),
    ).blocked_reason == "retry_after"

    for index in range(1, 5):
        moment = start + timedelta(minutes=index)
        policy.record_failure(
            messenger_account_id=first.messenger_account_id,
            operation_scope=operation,
            failure=classify_failure(
                "provider_timeout",
                retry_after_ms=120_000 if index == 4 else None,
            ),
            now=moment,
        )
    state = policy.state(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
    )
    assert state["circuit_state"] == "open"
    assert state["consecutive_failures"] == 5
    fifth_at = start + timedelta(minutes=4)
    still_provider_blocked = policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
        now=fifth_at + timedelta(seconds=31),
    )
    assert still_provider_blocked.allowed is False
    assert still_provider_blocked.retry_after_ms >= 89_000

    probe_at = fifth_at + timedelta(seconds=121)
    claims = [str(uuid4()) for _ in range(8)]

    def acquire_probe(probe_claim):
        return policy.acquire(
            messenger_account_id=first.messenger_account_id,
            operation_scope=operation,
            claim_id=probe_claim,
            now=probe_at,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        permits = list(pool.map(acquire_probe, claims))
    allowed = [permit for permit in permits if permit.allowed]
    assert len(allowed) == 1
    assert all(
        permit.blocked_reason == "half_open_probe_in_progress"
        for permit in permits if not permit.allowed
    )
    policy.record_success(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
        claim_id=allowed[0].claim_id,
        now=probe_at,
    )
    assert policy.state(
        messenger_account_id=first.messenger_account_id,
        operation_scope=operation,
    )["circuit_state"] == "closed"


def test_auth_privacy_and_uncertain_do_not_auto_retry_but_permanent_is_local(tmp_path):
    database, first, _ = _bootstrap(tmp_path)
    policy = AccountExecutionPolicyService(database, default_capacity=3)
    now = datetime(2026, 8, 11, tzinfo=UTC)
    for operation, failure_class in (
        ("contacts.auth", ExecutionErrorClass.AUTH),
        ("contacts.privacy", ExecutionErrorClass.PRIVACY),
        ("contacts.uncertain", ExecutionErrorClass.UNCERTAIN),
    ):
        decision = policy.record_failure(
            messenger_account_id=first.messenger_account_id,
            operation_scope=operation,
            failure=classify_failure(
                "safe_failure",
                explicit_class=failure_class,
            ),
            now=now,
        )
        assert decision.retryable is False
        assert decision.retry_after_ms is None
        blocked = policy.acquire(
            messenger_account_id=first.messenger_account_id,
            operation_scope=operation,
            now=now + timedelta(days=1),
        )
        assert blocked.allowed is False
        assert blocked.blocked_reason == "circuit_manual_reset_required"
    permanent = policy.record_failure(
        messenger_account_id=first.messenger_account_id,
        operation_scope="contacts.invalid",
        failure=classify_failure(
            "recipient_invalid", explicit_class=ExecutionErrorClass.PERMANENT
        ),
        now=now,
    )
    assert permanent.retryable is False
    assert permanent.circuit_state == "closed"
    assert policy.acquire(
        messenger_account_id=first.messenger_account_id,
        operation_scope="contacts.invalid",
        now=now,
    ).allowed is True


def test_application_job_failure_uses_policy_retry_and_defers_same_account_only(tmp_path):
    database, account, second_account = _bootstrap(tmp_path)
    api = object.__new__(BridgeApplicationApi)
    api._persistent_job_service = PersistentOperationJobService(database)
    api._execution_policy = AccountExecutionPolicyService(
        database, default_capacity=1, default_refill_per_second=1
    )
    api._persistent_job_worker_id = str(uuid4())
    api._persistent_job_lease_lock = threading.RLock()
    api._persistent_job_lease_stops = {}
    api._request_actor_app_user_id = ContextVar("phase8c_actor", default=account.app_user_id)
    api._request_actor_global_role = ContextVar("phase8c_role", default="admin")
    runtime = SimpleNamespace(
        ownership=SimpleNamespace(messenger_account_id=account.messenger_account_id)
    )
    api._request_runtime = ContextVar("phase8c_runtime", default=runtime)
    api._v1_runtime = runtime
    api._application_logger = SimpleNamespace(emit=lambda *args, **kwargs: None)

    first_job = api._persistent_job_create("background.fake.rate")
    api._persistent_job_begin(first_job)
    api._persistent_job_finish(
        first_job, state="failed", error_code="provider_timeout"
    )
    persisted = api._persistent_job_service.get_job(first_job)
    assert persisted.status == "pending"
    assert persisted.last_error_class == "transient"
    assert persisted.last_error_code == "provider_timeout"

    second_job = api._persistent_job_create("background.fake.rate")
    with pytest.raises(EitaaRuntimeError) as deferred:
        api._persistent_job_begin(second_job)
    assert deferred.value.code == "account_execution_deferred"
    assert api._persistent_job_service.get_job(second_job).status == "pending"
    assert api._execution_policy.state(
        messenger_account_id=second_account,
        operation_scope="background.fake.rate",
    ) is None

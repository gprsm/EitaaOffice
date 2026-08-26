from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import sqlite3
from types import SimpleNamespace
import threading
from uuid import uuid4

import pytest

from eitaa_bridge.errors import CoordinatorSchemaError
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    COORDINATOR_SCHEMA_VERSION,
    CoordinatorDatabase,
    PersistentOperationJobService,
    ProtectedPhone,
)
from eitaa_bridge.infrastructure.coordinator.schema import (
    SCHEMA_CHECKSUMS,
    SCHEMA_V1_SQL,
    SCHEMA_V2_SQL,
)


def _bootstrap(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    account = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-job-phone",
            key_version=1,
            fingerprint="8" * 64,
            display_hint="+••••••••18",
        ),
        display_name="Job administrator",
        backup_name="verified.zip",
        source_manifest_sha256="9" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    return database, account


def _create(service, account, *, key="request-0001", recipients=("a" * 64,)):
    return service.create_job(
        actor_app_user_id=account.app_user_id,
        actor_global_role="admin",
        messenger_account_id=account.messenger_account_id,
        operation="message.send",
        idempotency_key=key,
        safe_payload_ref="payload:opaque-1",
        recipient_ref_hashes=recipients,
    )


def test_schema2_upgrades_to_persistent_job_schema3(tmp_path):
    path = tmp_path / "coordinator-v2.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES"
            + f"(1,'{SCHEMA_CHECKSUMS[1]}','now');\n"
            + SCHEMA_V2_SQL
            + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES"
            + f"(2,'{SCHEMA_CHECKSUMS[2]}','now');\n"
            + "PRAGMA user_version=2;\nCOMMIT;"
        )

    CoordinatorDatabase(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION
        columns = {row[1] for row in connection.execute("PRAGMA table_info(operation_jobs)")}
        assert {
            "attempt_count", "cancel_requested_at", "cancelled_at",
            "last_error_class", "last_error_code",
        } <= columns
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=3"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[3]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_idempotency_and_duplicate_recipients_are_persistent_and_owner_scoped(tmp_path):
    database, account = _bootstrap(tmp_path)
    service = PersistentOperationJobService(database)
    first = _create(
        service,
        account,
        recipients=("a" * 64, "a" * 64, "b" * 64),
    )
    repeated = _create(
        PersistentOperationJobService(database),
        account,
        recipients=("b" * 64, "a" * 64),
    )

    assert first.reused is False
    assert repeated.reused is True
    assert repeated.job.job_id == first.job.job_id
    assert len(service.recipients(first.job.job_id)) == 2

    other_user = str(uuid4())
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            """
            INSERT INTO app_users(id,display_name,global_role,status,created_at,updated_at)
            VALUES(?,'Other','user','active','now','now')
            """,
            (other_user,),
        )
        connection.execute(
            """
            INSERT INTO phone_account_memberships(
                id,app_user_id,phone_account_id,role,status,created_by_app_user_id,
                created_at,updated_at
            ) VALUES(?,?,?,'operator','active',?,'now','now')
            """,
            (str(uuid4()), other_user, account.phone_account_id, account.app_user_id),
        )
    with pytest.raises(CoordinatorSchemaError) as mismatch:
        service.create_job(
            actor_app_user_id=other_user,
            actor_global_role="user",
            messenger_account_id=account.messenger_account_id,
            operation="message.send",
            idempotency_key="request-0001",
            safe_payload_ref="payload:opaque-1",
            recipient_ref_hashes=("a" * 64, "b" * 64),
        )
    assert mismatch.value.code == "operation_job_idempotency_owner_mismatch"


def test_concurrent_lease_has_one_winner_and_stale_worker_is_fenced(tmp_path):
    database, account = _bootstrap(tmp_path)
    job = _create(PersistentOperationJobService(database), account).job
    workers = [str(uuid4()) for _ in range(8)]

    def lease(worker_id):
        return PersistentOperationJobService(database).lease_next_job(
            messenger_account_id=account.messenger_account_id,
            worker_id=worker_id,
            worker_generation=1,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lease, workers))
    winners = [(workers[index], value) for index, value in enumerate(results) if value]
    assert len(winners) == 1
    winning_worker, leased = winners[0]
    assert leased.job_id == job.job_id
    with pytest.raises(CoordinatorSchemaError) as stale:
        PersistentOperationJobService(database).start_attempt(
            job.job_id,
            worker_id=next(item for item in workers if item != winning_worker),
            worker_generation=1,
        )
    assert stale.value.code == "operation_job_lease_lost"


def test_retry_attempts_survive_service_restart_and_finish_exactly_once(tmp_path):
    database, account = _bootstrap(tmp_path)
    service = PersistentOperationJobService(database)
    job = _create(service, account).job
    first_worker, second_worker = str(uuid4()), str(uuid4())
    service.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=first_worker,
        worker_generation=1,
    )
    service.start_attempt(job.job_id, worker_id=first_worker, worker_generation=1)
    retry = service.complete_attempt(
        job.job_id,
        worker_id=first_worker,
        worker_generation=1,
        result="failed",
        error_class="transient",
        error_code="fake_timeout",
        retry_after_ms=0,
    )
    assert retry.status == "pending"

    restarted = PersistentOperationJobService(CoordinatorDatabase(database.path))
    leased = restarted.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=second_worker,
        worker_generation=2,
    )
    assert leased.job_id == job.job_id
    restarted.start_attempt(job.job_id, worker_id=second_worker, worker_generation=2)
    completed = restarted.complete_attempt(
        job.job_id,
        worker_id=second_worker,
        worker_generation=2,
        result="succeeded",
    )

    assert completed.status == "succeeded"
    assert completed.attempt_count == 2
    assert [item.result for item in restarted.attempts(job.job_id)] == ["failed", "succeeded"]
    assert {item["status"] for item in restarted.recipients(job.job_id)} == {"succeeded"}
    assert restarted.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=str(uuid4()), worker_generation=3,
    ) is None


def test_crash_recovery_marks_running_uncertain_but_requeues_unstarted_lease(tmp_path):
    database, account = _bootstrap(tmp_path)
    service = PersistentOperationJobService(database)
    running = _create(service, account, key="request-running").job
    unstarted = _create(service, account, key="request-leased2", recipients=("b" * 64,)).job
    worker = str(uuid4())
    service.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=worker,
        worker_generation=1,
    )
    service.start_attempt(running.job_id, worker_id=worker, worker_generation=1)
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE operation_jobs SET lease_expires_at='2020-01-01T00:00:00.000+00:00' WHERE id=?",
            (running.job_id,),
        )

    restarted = PersistentOperationJobService(CoordinatorDatabase(database.path))
    summary = restarted.recover_expired_jobs(
        messenger_account_id=account.messenger_account_id
    )
    assert summary.uncertain_recovered == 1
    assert restarted.get_job(running.job_id).status == "uncertain"
    assert restarted.attempts(running.job_id)[0].result == "uncertain"
    assert restarted.recipients(running.job_id)[0]["status"] == "uncertain"

    second_worker = str(uuid4())
    leased = restarted.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=second_worker,
        worker_generation=2,
    )
    assert leased.job_id == unstarted.job_id
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE operation_jobs SET lease_expires_at='2020-01-01T00:00:00.000+00:00' WHERE id=?",
            (unstarted.job_id,),
        )
    recovered = restarted.recover_expired_jobs(
        messenger_account_id=account.messenger_account_id
    )
    assert recovered.pending_recovered == 1
    assert restarted.get_job(unstarted.job_id).status == "pending"
    with pytest.raises(CoordinatorSchemaError) as stale:
        restarted.start_attempt(
            unstarted.job_id,
            worker_id=second_worker,
            worker_generation=2,
        )
    assert stale.value.code == "operation_job_lease_lost"


def test_cancellation_is_immediate_before_run_and_cooperative_while_running(tmp_path):
    database, account = _bootstrap(tmp_path)
    service = PersistentOperationJobService(database)
    pending = _create(service, account, key="request-cancel1").job
    cancelled = service.request_cancel(
        pending.job_id,
        actor_app_user_id=account.app_user_id,
        actor_global_role="admin",
    )
    assert cancelled.status == "cancelled"
    assert service.recipients(pending.job_id)[0]["status"] == "cancelled"

    running = _create(service, account, key="request-cancel2", recipients=("c" * 64,)).job
    worker = str(uuid4())
    service.lease_next_job(
        messenger_account_id=account.messenger_account_id,
        worker_id=worker,
        worker_generation=1,
    )
    service.start_attempt(running.job_id, worker_id=worker, worker_generation=1)
    requested = service.request_cancel(
        running.job_id,
        actor_app_user_id=account.app_user_id,
        actor_global_role="admin",
    )
    assert requested.status == "running"
    assert requested.cancel_requested_at is not None
    stopped = service.complete_attempt(
        running.job_id,
        worker_id=worker,
        worker_generation=1,
        result="cancelled",
    )
    assert stopped.status == "cancelled"
    assert stopped.completed_at is not None


def test_application_background_job_glue_uses_persistent_uuid_and_restart_snapshot(tmp_path):
    database, account = _bootstrap(tmp_path)
    api = object.__new__(BridgeApplicationApi)
    api._persistent_job_service = PersistentOperationJobService(database)
    api._execution_policy = None
    api._persistent_job_worker_id = str(uuid4())
    api._persistent_job_lease_lock = threading.RLock()
    api._persistent_job_lease_stops = {}
    api._request_actor_app_user_id = ContextVar("phase8b_actor", default=account.app_user_id)
    api._request_actor_global_role = ContextVar("phase8b_role", default="admin")
    runtime = SimpleNamespace(
        ownership=SimpleNamespace(messenger_account_id=account.messenger_account_id)
    )
    api._request_runtime = ContextVar("phase8b_runtime", default=runtime)
    api._v1_runtime = runtime
    api._application_logger = SimpleNamespace(emit=lambda *args, **kwargs: None)

    job_id = api._persistent_job_create("background.fake.test")
    assert len(job_id) == 36
    api._persistent_job_begin(job_id)
    api._persistent_job_finish(job_id, state="completed")

    snapshot = api._persistent_job_snapshot(
        job_id,
        kind="background",
        identifier_field="task_id",
        state_field="status",
    )
    assert snapshot["task_id"] == job_id
    assert snapshot["status"] == "completed"
    assert snapshot["persistent"] is True
    assert PersistentOperationJobService(
        CoordinatorDatabase(database.path)
    ).get_job(job_id).status == "succeeded"

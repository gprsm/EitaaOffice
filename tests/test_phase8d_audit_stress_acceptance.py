from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
import threading
from uuid import uuid4

import pytest

from eitaa_bridge.errors import CoordinatorSchemaError
from eitaa_bridge.infrastructure.coordinator import (
    COORDINATOR_SCHEMA_VERSION,
    CoordinatorDatabase,
    PersistentOperationJobService,
    ProtectedPhone,
    SafeCoordinatorAuditService,
)
from eitaa_bridge.infrastructure.coordinator.schema import (
    SCHEMA_CHECKSUMS,
    SCHEMA_V1_SQL,
    SCHEMA_V2_SQL,
    SCHEMA_V3_SQL,
    SCHEMA_V4_SQL,
)


def _bootstrap_three_accounts(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    first = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-stress-phone",
            key_version=1,
            fingerprint="3" * 64,
            display_hint="+••••••••13",
        ),
        display_name="Stress administrator",
        backup_name="verified.zip",
        source_manifest_sha256="4" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    second_user = str(uuid4())
    now = "2026-08-11T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO app_users(id,display_name,global_role,status,created_at,updated_at)
            VALUES(?,'Second stress user','user','active',?,?)
            """,
            (second_user, now, now),
        )

    accounts = [first.messenger_account_id]
    phone_accounts = [first.phone_account_id]
    for index in (2, 3):
        account_id, phone_id = str(uuid4()), str(uuid4())
        with sqlite3.connect(database.path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                INSERT INTO phone_accounts(
                    id,phone_ciphertext,phone_key_version,phone_fingerprint,display_hint,
                    status,created_at,updated_at
                ) VALUES(?,?,1,?,?,'active',?,?)
                """,
                (
                    phone_id,
                    f"protected-fake-{index}".encode("ascii"),
                    ("2" if index == 2 else "5") * 64,
                    f"+••••••••1{index}",
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO messenger_accounts(
                    id,phone_account_id,provider,label,lifecycle_state,desired_worker_state,
                    capability_revision,created_at,updated_at
                ) VALUES(?,?,'eitaa',?,'created','stopped',0,?,?)
                """,
                (account_id, phone_id, f"Fake account {index}", now, now),
            )
            connection.execute(
                """
                INSERT INTO messenger_session_metadata(
                    messenger_account_id,auth_state,session_generation,storage_revision,
                    last_auth_transition_at,created_at,updated_at
                ) VALUES(?,'absent',1,1,?,?,?)
                """,
                (account_id, now, now, now),
            )
            if index == 3:
                connection.execute(
                    """
                    INSERT INTO phone_account_memberships(
                        id,app_user_id,phone_account_id,role,status,created_by_app_user_id,
                        created_at,updated_at
                    ) VALUES(?,?,?,'owner','active',?,?,?)
                    """,
                    (
                        str(uuid4()),
                        second_user,
                        phone_id,
                        first.app_user_id,
                        now,
                        now,
                    ),
                )
        accounts.append(account_id)
        phone_accounts.append(phone_id)
    return database, first, second_user, tuple(accounts)


def _create_job(service, *, actor_id, role, account_id, index, operation="fake.execute"):
    return service.create_job(
        actor_app_user_id=actor_id,
        actor_global_role=role,
        messenger_account_id=account_id,
        operation=operation,
        idempotency_key=f"stress:{index:05d}",
        safe_payload_ref=f"fake:{index:05d}",
        recipient_ref_hashes=(hashlib.sha256(f"recipient:{index}".encode()).hexdigest(),),
    ).job


def test_schema4_upgrades_through_correlated_leases_to_current_schema(tmp_path):
    path = tmp_path / "coordinator-v4.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + f"\nINSERT INTO schema_migrations VALUES(1,'{SCHEMA_CHECKSUMS[1]}','now');\n"
            + SCHEMA_V2_SQL
            + f"\nINSERT INTO schema_migrations VALUES(2,'{SCHEMA_CHECKSUMS[2]}','now');\n"
            + SCHEMA_V3_SQL
            + f"\nINSERT INTO schema_migrations VALUES(3,'{SCHEMA_CHECKSUMS[3]}','now');\n"
            + SCHEMA_V4_SQL
            + f"\nINSERT INTO schema_migrations VALUES(4,'{SCHEMA_CHECKSUMS[4]}','now');\n"
            + "PRAGMA user_version=4;\nCOMMIT;"
        )
    CoordinatorDatabase(path).initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION == 9
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=5"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[5]
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=6"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[6]
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=7"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[7]
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=8"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[8]
        assert connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version=9"
        ).fetchone()[0] == SCHEMA_CHECKSUMS[9]
        attempt_columns = {row[1] for row in connection.execute("PRAGMA table_info(job_attempts)")}
        assert {"lease_id", "correlation_id"} <= attempt_columns
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_job_lease_attempt_retry_share_root_correlation_and_have_unique_child_ids(tmp_path):
    database, first, _, accounts = _bootstrap_three_accounts(tmp_path)
    service = PersistentOperationJobService(database)
    root_correlation = str(uuid4())
    job = service.create_job(
        actor_app_user_id=first.app_user_id,
        actor_global_role="admin",
        messenger_account_id=accounts[0],
        operation="fake.retry",
        idempotency_key="correlation:0001",
        correlation_id=root_correlation,
        safe_payload_ref="fake:correlation",
        recipient_ref_hashes=("a" * 64,),
    ).job
    first_worker, second_worker = str(uuid4()), str(uuid4())
    service.lease_job(job.job_id, worker_id=first_worker, worker_generation=1)
    service.start_attempt(job.job_id, worker_id=first_worker, worker_generation=1)
    service.complete_attempt(
        job.job_id,
        worker_id=first_worker,
        worker_generation=1,
        result="failed",
        error_class="transient",
        error_code="fake_timeout",
        retry_after_ms=0,
    )
    service.lease_job(job.job_id, worker_id=second_worker, worker_generation=2)
    service.start_attempt(job.job_id, worker_id=second_worker, worker_generation=2)
    service.complete_attempt(
        job.job_id,
        worker_id=second_worker,
        worker_generation=2,
        result="succeeded",
    )

    attempts = service.attempts(job.job_id)
    leases = service.leases(job.job_id)
    assert service.get_job(job.job_id).correlation_id == root_correlation
    assert len({item.lease_id for item in leases}) == 2
    assert len({item.correlation_id for item in leases}) == 2
    assert len({item.correlation_id for item in attempts}) == 2
    assert [item.lease_id for item in attempts] == [item.lease_id for item in leases]
    assert {item.status for item in leases} == {"released"}

    audit = SafeCoordinatorAuditService(database)
    page = audit.query(
        app_user_id=first.app_user_id,
        global_role="admin",
        correlation_id=root_correlation,
        limit=100,
    )
    actions = {event.action for event in page.events}
    assert {
        "operation_job.created",
        "operation_job.leased",
        "operation_job.attempt_started",
        "operation_job.retry_scheduled",
        "operation_job.succeeded",
    } <= actions
    child_metadata = [
        event.safe_metadata
        for event in page.events
        if event.action in {"operation_job.leased", "operation_job.attempt_started"}
    ]
    assert any("lease_correlation_id" in metadata for metadata in child_metadata)
    assert any("attempt_correlation_id" in metadata for metadata in child_metadata)
    assert audit.verify_chain().valid is True


def test_audit_query_pagination_export_and_tamper_detection_are_user_scoped(tmp_path):
    database, first, second_user, accounts = _bootstrap_three_accounts(tmp_path)
    service = PersistentOperationJobService(database)
    admin_job = _create_job(
        service, actor_id=first.app_user_id, role="admin", account_id=accounts[0], index=1
    )
    user_job = _create_job(
        service, actor_id=second_user, role="user", account_id=accounts[2], index=2
    )
    audit = SafeCoordinatorAuditService(database)

    first_page = audit.query(
        app_user_id=first.app_user_id,
        global_role="admin",
        action_prefix="operation_job.",
        limit=1,
    )
    assert len(first_page.events) == 1
    assert first_page.next_cursor is not None
    with pytest.raises(CoordinatorSchemaError) as invalid_cursor:
        audit.query(
            app_user_id=first.app_user_id,
            global_role="admin",
            cursor="%%%not-base64%%%",
        )
    assert invalid_cursor.value.code == "audit_cursor_invalid"
    second_page = audit.query(
        app_user_id=first.app_user_id,
        global_role="admin",
        action_prefix="operation_job.",
        cursor=first_page.next_cursor,
        limit=10,
    )
    assert {first_page.events[0].target_id, *[item.target_id for item in second_page.events]} == {
        admin_job.job_id,
        user_job.job_id,
    }

    user_page = audit.query(
        app_user_id=second_user,
        global_role="user",
        action_prefix="operation_job.",
        limit=100,
    )
    assert {event.target_id for event in user_page.events} == {user_job.job_id}
    assert all(event.messenger_account_id == accounts[2] for event in user_page.events)
    exported = audit.export_jsonl(
        app_user_id=second_user,
        global_role="user",
        output_directory=tmp_path / "exports",
        action_prefix="operation_job.",
    )
    raw = exported.path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == exported.sha256
    assert exported.event_count == len(user_page.events)
    assert accounts[0].encode() not in raw
    assert accounts[1].encode() not in raw
    assert accounts[2].encode() in raw
    assert b"password" not in raw.lower()
    assert audit.verify_chain().valid is True

    with sqlite3.connect(database.path) as connection:
        connection.execute("DROP TRIGGER audit_events_no_update")
        connection.execute(
            "UPDATE audit_events SET result='tampered' WHERE id=(SELECT id FROM audit_events ORDER BY rowid LIMIT 1)"
        )
    invalid = audit.verify_chain()
    assert invalid.valid is False
    assert invalid.first_invalid_event_id is not None


def test_two_users_three_fake_accounts_concurrent_restart_crash_cancel_have_no_leaks(tmp_path):
    database, first, second_user, accounts = _bootstrap_three_accounts(tmp_path)
    service = PersistentOperationJobService(database)
    total_per_account = 24
    specs = []
    for account_index, account_id in enumerate(accounts):
        actor = first.app_user_id if account_index < 2 else second_user
        role = "admin" if account_index < 2 else "user"
        for local_index in range(total_per_account):
            global_index = account_index * 1000 + local_index
            specs.append((actor, role, account_id, global_index))

    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = list(
            pool.map(
                lambda item: _create_job(
                    service,
                    actor_id=item[0],
                    role=item[1],
                    account_id=item[2],
                    index=item[3],
                ),
                specs,
            )
        )
    assert len({job.job_id for job in jobs}) == len(specs) == 72

    # Cancel a deterministic subset before any worker can lease it.
    for job in jobs:
        local_index = int(job.idempotency_key.rsplit(":", 1)[1]) % 1000
        if local_index % 11 == 0:
            service.request_cancel(
                job.job_id,
                actor_app_user_id=job.actor_app_user_id,
                actor_global_role="admin" if job.actor_app_user_id == first.app_user_id else "user",
            )

    crashed: list[str] = []
    crashed_lock = threading.Lock()

    def consume(account_id: str, worker_generation: int) -> int:
        worker_id = str(uuid4())
        processed = 0
        while True:
            leased = PersistentOperationJobService(database).lease_next_job(
                messenger_account_id=account_id,
                worker_id=worker_id,
                worker_generation=worker_generation,
                lease_seconds=30,
            )
            if leased is None:
                return processed
            assert leased.messenger_account_id == account_id
            current = PersistentOperationJobService(database)
            current.start_attempt(
                leased.job_id,
                worker_id=worker_id,
                worker_generation=worker_generation,
            )
            local_index = int(leased.idempotency_key.rsplit(":", 1)[1]) % 1000
            if local_index % 13 == 0:
                with crashed_lock:
                    crashed.append(leased.job_id)
                processed += 1
                continue
            if local_index % 7 == 0 and leased.attempt_count == 0:
                current.complete_attempt(
                    leased.job_id,
                    worker_id=worker_id,
                    worker_generation=worker_generation,
                    result="failed",
                    error_class="transient",
                    error_code="fake_retry",
                    retry_after_ms=0,
                )
            elif local_index % 5 == 0:
                current.request_cancel(
                    leased.job_id,
                    actor_app_user_id=leased.actor_app_user_id,
                    actor_global_role="admin" if leased.actor_app_user_id == first.app_user_id else "user",
                )
                current.complete_attempt(
                    leased.job_id,
                    worker_id=worker_id,
                    worker_generation=worker_generation,
                    result="cancelled",
                )
            else:
                current.complete_attempt(
                    leased.job_id,
                    worker_id=worker_id,
                    worker_generation=worker_generation,
                    result="succeeded",
                )
            processed += 1

    worker_specs = [
        (account_id, generation)
        for account_id in accounts
        for generation in (1, 2)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        processed_counts = list(pool.map(lambda item: consume(*item), worker_specs))
    assert sum(processed_counts) >= len(jobs) - 12
    assert crashed

    with sqlite3.connect(database.path) as connection:
        connection.executemany(
            "UPDATE operation_jobs SET lease_expires_at='2020-01-01T00:00:00.000+00:00' WHERE id=?",
            [(job_id,) for job_id in crashed],
        )
        connection.executemany(
            "UPDATE job_leases SET expires_at='2020-01-01T00:00:00.000+00:00' WHERE job_id=? AND status='active'",
            [(job_id,) for job_id in crashed],
        )
    restarted = PersistentOperationJobService(CoordinatorDatabase(database.path))
    recovered = restarted.recover_expired_jobs()
    assert recovered.uncertain_recovered == len(crashed)

    statuses = {restarted.get_job(job.job_id).status for job in jobs}
    assert statuses <= {"succeeded", "cancelled", "uncertain"}
    assert {"succeeded", "cancelled", "uncertain"} <= statuses
    with sqlite3.connect(database.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM job_leases WHERE status='active'"
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    audit = SafeCoordinatorAuditService(database)
    assert audit.verify_chain().valid is True
    second_user_events = audit.query(
        app_user_id=second_user,
        global_role="user",
        action_prefix="operation_job.",
        limit=1000,
    ).events
    assert second_user_events
    assert {event.messenger_account_id for event in second_user_events} == {accounts[2]}
    assert all(
        event.actor_app_user_id in {None, second_user}
        for event in second_user_events
    )

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sqlite3
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.account_runtime import EitaaRuntimeRegistry
from eitaa_bridge.application.process_runtime import EitaaProcessRuntime
from eitaa_bridge.errors import CoordinatorSchemaError, EitaaRuntimeError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase, ProtectedPhone
from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager, RuntimeLogger


def _bootstrap_account(database: CoordinatorDatabase, seed: str):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=f"protected-{seed}".encode("ascii"),
            key_version=1,
            fingerprint=(seed * 64)[:64],
            display_hint="+••••••••67",
        ),
        display_name=f"Administrator {seed}",
        backup_name=f"verified-{seed}.zip",
        source_manifest_sha256=(seed * 64)[:64],
        source_file_count=1,
        source_total_bytes=1,
    )


def _make_runnable(database: CoordinatorDatabase, *account_ids: str) -> None:
    with sqlite3.connect(database.path) as connection:
        connection.executemany(
            """
            UPDATE messenger_accounts
            SET lifecycle_state='active', desired_worker_state='running'
            WHERE id=?
            """,
            ((account_id,) for account_id in account_ids),
        )


def _write_config(
    root: Path,
    *,
    default_account_id: str,
    max_restarts: int = 3,
    heartbeat_failure_threshold: int = 1,
) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "test-site",
        "bridge": {
            "diagnostics_root": "diagnostics/bridge",
            "diagnostics_enabled": False,
        },
        "features": {
            "multi_session": {
                "enabled": True,
                "legacy_default_messenger_account_id": default_account_id,
            },
            "worker_process": {
                "schema_version": 1,
                "enabled": True,
                "startup_timeout_seconds": 10,
                "request_timeout_seconds": 10,
                "heartbeat_interval_seconds": 1,
                "heartbeat_timeout_seconds": 3,
                "heartbeat_failure_threshold": heartbeat_failure_threshold,
                "restart_window_seconds": 30,
                "max_restarts": max_restarts,
                "backoff_initial_seconds": 1,
                "backoff_max_seconds": 2,
                "quarantine_seconds": 30,
            },
            "app_user_auth": {"enabled": False},
        },
        "core": {
            "session_file": ".eitaa_session.json",
            "database_file": "data/eitaa_messages.sqlite3",
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": False,
            "timeout_seconds": 23,
        },
        "wordpress_sites": [
            {
                "site_key": "test-site",
                "base_url": "https://example.test",
                "default_status": "draft",
                "default_category_id": None,
                "verify_tls": True,
                "username_env": "TEST_WP_USER",
                "application_password_env": "TEST_WP_PASSWORD",
            }
        ],
    }
    path = root / "bridge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _registry(config_path: Path):
    config = BridgeConfigLoader.load(config_path)
    logger = RuntimeLogger(
        config.source_file.parent / "runtime" / "logs" / "application.jsonl"
    )
    diagnostics = BridgeDiagnosticManager(config.diagnostics.root, enabled=False)
    registry = EitaaRuntimeRegistry(
        config,
        application_diagnostics=diagnostics,
        application_logger=logger,
    )
    return registry, logger


def _wait_until(predicate, *, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.05)
    if last_error is not None:
        raise AssertionError("condition did not become true") from last_error
    raise AssertionError("condition did not become true")


def _current_runtime(
    registry: EitaaRuntimeRegistry,
    messenger_account_id: str,
) -> EitaaProcessRuntime | None:
    with registry._lock:
        runtime = registry._account_runtimes.get(messenger_account_id)
    return runtime if isinstance(runtime, EitaaProcessRuntime) else None


def _terminate_worker(runtime: EitaaProcessRuntime) -> None:
    os.kill(runtime.process_id, signal.SIGTERM)


def test_supervisor_config_is_bounded_and_fail_closed(tmp_path):
    account_id = str(uuid4())
    path = _write_config(tmp_path / "config", default_account_id=account_id)
    feature = BridgeConfigLoader.load(path).features.worker_process
    assert feature.heartbeat_interval_seconds == 1
    assert feature.heartbeat_timeout_seconds == 3
    assert feature.heartbeat_failure_threshold == 1
    assert feature.restart_window_seconds == 30
    assert feature.max_restarts == 3
    assert feature.backoff_initial_seconds == 1
    assert feature.backoff_max_seconds == 2
    assert feature.quarantine_seconds == 30

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["features"]["worker_process"]["heartbeat_timeout_seconds"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    invalid_timeout = BridgeConfigLoader.load(path).features.worker_process
    assert invalid_timeout.enabled is False
    assert invalid_timeout.fail_closed_reason == "heartbeat_timeout_seconds_invalid"

    payload["features"]["worker_process"]["heartbeat_timeout_seconds"] = 3
    payload["features"]["worker_process"]["backoff_initial_seconds"] = 3
    payload["features"]["worker_process"]["backoff_max_seconds"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")
    invalid_backoff = BridgeConfigLoader.load(path).features.worker_process
    assert invalid_backoff.enabled is False
    assert invalid_backoff.fail_closed_reason == "backoff_range_invalid"


def test_coordinator_fences_heartbeat_applies_backoff_and_quarantines(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    account = _bootstrap_account(database, "c1")
    _make_runnable(database, account.messenger_account_id)
    _, first = database.request_worker_start(
        account.messenger_account_id,
        process_id=31001,
        actor_app_user_id=None,
        actor_global_role=None,
    )
    first = database.mark_worker_ready(first.worker_instance_id)
    heartbeat = database.heartbeat_worker_fenced(
        first.worker_instance_id,
        expected_generation=first.generation,
        expected_process_id=31001,
    )
    assert heartbeat.last_heartbeat_at is not None
    with pytest.raises(CoordinatorSchemaError) as wrong_heartbeat:
        database.heartbeat_worker_fenced(
            first.worker_instance_id,
            expected_generation=first.generation + 1,
            expected_process_id=31001,
        )
    assert wrong_heartbeat.value.code == "worker_heartbeat_fence_mismatch"

    first_decision = database.record_worker_crash(
        first.worker_instance_id,
        expected_generation=first.generation,
        expected_process_id=31001,
        reason_code="worker_process_exited",
        exit_code=9,
        restart_window_seconds=30,
        max_restarts=1,
        backoff_initial_seconds=1,
        backoff_max_seconds=2,
        quarantine_seconds=30,
    )
    assert first_decision.restart_allowed is True
    assert first_decision.quarantined is False
    assert first_decision.crash_count == 1
    assert first_decision.retry_after_seconds == 1
    with pytest.raises(CoordinatorSchemaError) as backoff:
        database.request_worker_start(
            account.messenger_account_id,
            process_id=31002,
            actor_app_user_id=None,
            actor_global_role=None,
        )
    assert backoff.value.code == "worker_restart_backoff_active"

    time.sleep(1.05)
    _, second = database.request_worker_start(
        account.messenger_account_id,
        process_id=31002,
        actor_app_user_id=None,
        actor_global_role=None,
    )
    second = database.mark_worker_ready(second.worker_instance_id)
    second_decision = database.record_worker_crash(
        second.worker_instance_id,
        expected_generation=second.generation,
        expected_process_id=31002,
        reason_code="worker_heartbeat_failure_limit",
        exit_code=None,
        restart_window_seconds=30,
        max_restarts=1,
        backoff_initial_seconds=1,
        backoff_max_seconds=2,
        quarantine_seconds=30,
    )
    assert second_decision.restart_allowed is False
    assert second_decision.quarantined is True
    assert second_decision.crash_count == 2
    record = database.messenger_account_runtime(account.messenger_account_id)
    assert record.lifecycle_state == "quarantined"
    assert record.desired_worker_state == "stopped"
    history = database.worker_instances(account.messenger_account_id)
    assert [worker.runtime_state for worker in history] == ["crashed", "crashed"]
    assert history[0].exit_code == 9
    assert history[0].retry_not_before is not None


def test_actual_child_crash_restarts_only_its_account_and_preserves_auth(tmp_path):
    root = tmp_path / "isolated-recovery"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    first = _bootstrap_account(database, "c2")
    second = _bootstrap_account(database, "c3")
    _make_runnable(database, first.messenger_account_id, second.messenger_account_id)
    config = _write_config(root, default_account_id=first.messenger_account_id)
    registry, logger = _registry(config)
    try:
        first_runtime = registry.resolve_v1()
        second_runtime = registry.runtime_for_account(second.messenger_account_id)
        assert isinstance(first_runtime, EitaaProcessRuntime)
        assert isinstance(second_runtime, EitaaProcessRuntime)
        first_pid = first_runtime.process_id
        second_pid = second_runtime.process_id
        initial_heartbeat = database.active_worker_instance(
            first.messenger_account_id
        ).last_heartbeat_at
        _wait_until(
            lambda: (
                database.active_worker_instance(
                    first.messenger_account_id
                ).last_heartbeat_at
                != initial_heartbeat
            )
        )
        first_auth = database.messenger_account_runtime(
            first.messenger_account_id
        ).auth_state
        _terminate_worker(first_runtime)

        def replacement_ready() -> bool:
            replacement = _current_runtime(registry, first.messenger_account_id)
            return bool(
                replacement is not None
                and replacement is not first_runtime
                and replacement.process_id != first_pid
                and replacement.health().get("status") == "ready"
            )

        _wait_until(replacement_ready)
        replacement = _current_runtime(registry, first.messenger_account_id)
        assert replacement is not None
        assert second_runtime.process_id == second_pid
        assert second_runtime.health()["status"] == "ready"
        assert database.messenger_account_runtime(
            first.messenger_account_id
        ).auth_state == first_auth
        history = database.worker_instances(first.messenger_account_id)
        assert len(history) == 2
        assert history[0].runtime_state == "crashed"
        assert history[0].safe_reason_code in {
            "worker_process_exited",
            "worker_heartbeat_failure_limit",
        }
        assert history[1].runtime_state == "ready"
        assert history[1].generation == history[0].generation + 1
        stale_leases = list(
            replacement.ownership.worker_lock_file.parent.glob(
                "worker.lock.stale.*.json"
            )
        )
        assert stale_leases
        log_text = (
            root / "runtime" / "logs" / "application.jsonl"
        ).read_text(encoding="utf-8")
        assert "eitaa_process_recovery_decided" in log_text
        assert "eitaa_process_restart_succeeded" in log_text
    finally:
        registry.close()
        logger.close()


def test_repeated_actual_crashes_exhaust_budget_and_quarantine_account(tmp_path):
    root = tmp_path / "quarantine"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "c4")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(
        root,
        default_account_id=account.messenger_account_id,
        max_restarts=1,
    )
    registry, logger = _registry(config)
    try:
        first_runtime = registry.resolve_v1()
        assert isinstance(first_runtime, EitaaProcessRuntime)
        _terminate_worker(first_runtime)
        _wait_until(
            lambda: (
                _current_runtime(registry, account.messenger_account_id) is not None
                and _current_runtime(registry, account.messenger_account_id)
                is not first_runtime
            )
        )
        second_runtime = _current_runtime(registry, account.messenger_account_id)
        assert second_runtime is not None
        _terminate_worker(second_runtime)

        def quarantined() -> bool:
            record = database.messenger_account_runtime(account.messenger_account_id)
            return bool(
                record.lifecycle_state == "quarantined"
                and record.desired_worker_state == "stopped"
                and _current_runtime(registry, account.messenger_account_id) is None
            )

        _wait_until(quarantined)
        history = database.worker_instances(account.messenger_account_id)
        assert len(history) == 2
        assert all(worker.runtime_state == "crashed" for worker in history)
        assert database.active_worker_instance(account.messenger_account_id) is None
        assert database.messenger_account_runtime(
            account.messenger_account_id
        ).auth_state == "absent"
    finally:
        registry.close()
        logger.close()


def test_duplicate_registry_is_rejected_and_controlled_restart_is_clean(tmp_path):
    root = tmp_path / "controlled-restart"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "c5")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(root, default_account_id=account.messenger_account_id)
    first_registry, first_logger = _registry(config)
    second_registry = None
    second_logger = None
    first_process = None
    first_generation = None
    try:
        first_runtime = first_registry.resolve_v1()
        assert isinstance(first_runtime, EitaaProcessRuntime)
        first_process = first_runtime.client.process
        first_generation = first_runtime.worker.generation

        duplicate_registry, duplicate_logger = _registry(config)
        try:
            with pytest.raises(EitaaRuntimeError) as duplicate:
                duplicate_registry.resolve_v1()
            assert duplicate.value.code == "eitaa_worker_process_alive"
        finally:
            duplicate_registry.close()
            duplicate_logger.close()

        first_registry.close()
        first_logger.close()
        assert first_process.poll() == 0
        assert database.active_worker_instance(account.messenger_account_id) is None

        second_registry, second_logger = _registry(config)
        restarted = second_registry.resolve_v1()
        assert isinstance(restarted, EitaaProcessRuntime)
        assert restarted.worker.generation == first_generation + 1
        assert restarted.health()["status"] == "ready"
    finally:
        try:
            first_registry.close()
        finally:
            first_logger.close()
        if second_registry is not None:
            second_registry.close()
        if second_logger is not None:
            second_logger.close()

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4

import pytest

from eitaa_bridge.application.account_runtime import EitaaRuntimeRegistry
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.process_runtime import EitaaProcessRuntime
from eitaa_bridge.application.scheduler import EitaaPriority
from eitaa_bridge.errors import EitaaRuntimeError
from eitaa_bridge.facade import EitaaBridge
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase, ProtectedPhone
from eitaa_bridge.infrastructure.diagnostics import BridgeDiagnosticManager, RuntimeLogger
from eitaa_bridge.infrastructure.worker_ipc import (
    WorkerIpcSecretFile,
    ipc_error_category,
)


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
    process_enabled: bool,
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
                "enabled": process_enabled,
                "startup_timeout_seconds": 15,
                "request_timeout_seconds": 30,
                "heartbeat_interval_seconds": 1,
                "heartbeat_timeout_seconds": 5,
                "heartbeat_failure_threshold": 2,
                "restart_window_seconds": 30,
                "max_restarts": 3,
                "backoff_initial_seconds": 1,
                "backoff_max_seconds": 4,
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


def test_worker_process_config_is_versioned_opt_in_and_fail_closed(
    tmp_path,
    monkeypatch,
):
    account_id = str(uuid4())
    path = _write_config(
        tmp_path / "enabled",
        default_account_id=account_id,
        process_enabled=True,
    )
    loaded = BridgeConfigLoader.load(path).features.worker_process
    assert loaded.schema_version == 1
    assert loaded.enabled is True
    assert loaded.startup_timeout_seconds == 15
    assert loaded.request_timeout_seconds == 30

    payload = json.loads(path.read_text(encoding="utf-8"))
    process_settings = payload["features"].pop("worker_process")
    path.write_text(json.dumps(payload), encoding="utf-8")
    absent = BridgeConfigLoader.load(path).features.worker_process
    assert absent.enabled is False
    assert absent.fail_closed_reason is None

    payload["features"]["worker_process"] = process_settings
    payload["features"]["worker_process"]["schema_version"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")
    invalid = BridgeConfigLoader.load(path).features.worker_process
    assert invalid.enabled is False
    assert invalid.fail_closed_reason == "schema_version_invalid"

    payload["features"]["worker_process"]["schema_version"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_WORKER_PROCESS", "1")
    killed = BridgeConfigLoader.load(path).features.worker_process
    assert killed.enabled is False
    assert killed.fail_closed_reason == "environment_kill_switch"

    payload["features"]["multi_session"]["enabled"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_WORKER_PROCESS", "0")
    dependency = BridgeConfigLoader.load(path).features.worker_process
    assert dependency.enabled is False
    assert dependency.fail_closed_reason == "multi_session_required"
    assert ipc_error_category("eitaa_worker_process_feature_disabled") == "bootstrap"
    assert ipc_error_category("eitaa_process_runtime_record_invalid") == "worker"


def test_process_flag_off_preserves_in_process_legacy_account_runtime(tmp_path):
    root = tmp_path / "legacy"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "1")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(
        root,
        default_account_id=account.messenger_account_id,
        process_enabled=False,
    )
    registry, logger = _registry(config)
    try:
        runtime = registry.resolve_v1()
        assert not isinstance(runtime, EitaaProcessRuntime)
        active = database.active_worker_instance(account.messenger_account_id)
        assert active is not None
        assert active.process_id == os.getpid()
    finally:
        registry.close()
        logger.close()


def test_one_child_owns_core_scheduler_paths_cache_log_and_lease(tmp_path):
    EitaaBridge.close_shared_cores()
    root = tmp_path / "isolated"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "2")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(
        root,
        default_account_id=account.messenger_account_id,
        process_enabled=True,
    )
    registry, logger = _registry(config)
    runtime = None
    process = None
    lock_file = None
    try:
        runtime = registry.resolve_v1()
        assert isinstance(runtime, EitaaProcessRuntime)
        assert registry._legacy_runtime is None
        assert runtime.logger is logger
        process = runtime.client.process
        assert runtime.process_id != os.getpid()
        assert process.poll() is None
        active = database.active_worker_instance(account.messenger_account_id)
        assert active is not None
        assert active.process_id == runtime.process_id
        assert active.runtime_state == "ready"

        lock_file = runtime.ownership.worker_lock_file
        assert lock_file is not None and lock_file.is_file()
        lease = json.loads(lock_file.read_text(encoding="utf-8"))
        assert lease["process_id"] == runtime.process_id
        assert lease["messenger_account_id"] == account.messenger_account_id

        probe = runtime.core_probe()
        assert probe == {
            "status": "ready",
            "core_owner_pid": runtime.process_id,
            "core_opened": False,
            "core_open_deferred": True,
            "database_file_name": "messages.sqlite3",
            "session_file_name": "eitaa_session.json",
            "media_directory_name": "media",
        }
        scheduler = runtime.scheduler.snapshot()
        assert scheduler["worker_name"].startswith("eitaa-operation-")
        assert EitaaBridge._shared_cores == {}
        assert not list((runtime.ownership.account_runtime_directory / "ipc").glob("*.json"))

        summary = runtime.safe_summary()
        assert summary["process_isolated"] is True
        assert summary["process_id"] == runtime.process_id
        assert summary["worker_runtime_scoped"] is True
        assert "secret" not in json.dumps(summary).lower()
        with pytest.raises(EitaaRuntimeError) as callback:
            runtime.run_sync(
                priority=EitaaPriority.BACKGROUND,
                kind="forbidden-parent-callback",
                callback=lambda: None,
            )
        assert callback.value.code == "eitaa_process_callback_not_serializable"
        with pytest.raises(EitaaRuntimeError) as state:
            runtime.background_tasks
        assert state.value.code == "eitaa_process_parent_state_forbidden"
    finally:
        registry.close()
        logger.close()
    assert process is not None and process.poll() == 0
    assert lock_file is not None and not lock_file.exists()


def test_two_accounts_use_distinct_children_and_normal_stop_does_not_stop_peer(tmp_path):
    root = tmp_path / "two-accounts"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    first = _bootstrap_account(database, "3")
    second = _bootstrap_account(database, "4")
    _make_runnable(database, first.messenger_account_id, second.messenger_account_id)
    config = _write_config(
        root,
        default_account_id=first.messenger_account_id,
        process_enabled=True,
    )
    registry, logger = _registry(config)
    try:
        first_runtime = registry.resolve_v1()
        second_runtime = registry.runtime_for_account(second.messenger_account_id)
        assert isinstance(first_runtime, EitaaProcessRuntime)
        assert isinstance(second_runtime, EitaaProcessRuntime)
        assert first_runtime.process_id != second_runtime.process_id
        assert first_runtime.ownership.core != second_runtime.ownership.core
        assert first_runtime.core_probe()["core_owner_pid"] == first_runtime.process_id
        assert second_runtime.core_probe()["core_owner_pid"] == second_runtime.process_id

        first_process = first_runtime.client.process
        second_process = second_runtime.client.process
        stopped = registry.stop_account(
            first.messenger_account_id,
            actor_app_user_id=first.app_user_id,
            actor_global_role="admin",
            request_id="phase7b-normal-stop",
        )
        assert stopped.lifecycle_state == "paused"
        assert first_process.poll() == 0
        assert second_process.poll() is None
        assert second_runtime.health()["status"] == "ready"
    finally:
        registry.close()
        logger.close()


def test_application_uses_remote_scheduler_and_blocks_unmigrated_parent_core(tmp_path):
    root = tmp_path / "api"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "5")
    _make_runnable(database, account.messenger_account_id)
    config = _write_config(
        root,
        default_account_id=account.messenger_account_id,
        process_enabled=True,
    )
    api = BridgeApplicationApi(config)
    try:
        scheduler = api.dispatch("GET", "/api/v1/scheduler/status")
        assert scheduler.status == 200
        assert scheduler.payload["scheduler"]["worker_name"].startswith(
            "eitaa-operation-"
        )

        auth = api.dispatch("GET", "/api/v1/auth/status")
        assert auth.status == 400
        assert auth.payload["error"]["error_code"] == (
            "eitaa_process_operation_ipc_required"
        )

        capabilities = api.dispatch("GET", "/api/v1/capabilities")
        assert capabilities.status == 400
        assert capabilities.payload["error"]["error_code"] == (
            "eitaa_process_operation_ipc_required"
        )
    finally:
        api.close()


def test_direct_eitaa_entrypoint_requires_enabled_feature_and_consumes_secret(tmp_path):
    root = Path(__file__).resolve().parents[1]
    install = tmp_path / "disabled-entrypoint"
    account_id = str(uuid4())
    config = _write_config(
        install,
        default_account_id=account_id,
        process_enabled=False,
    )
    _, secret_file = WorkerIpcSecretFile.create(
        install / "runtime" / "ipc",
        messenger_account_id=account_id,
        provider="eitaa",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root / "src"), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "eitaa_bridge.interfaces.provider_worker",
            "--provider",
            "eitaa",
            "--messenger-account-id",
            account_id,
            "--secret-file",
            str(secret_file),
            "--config",
            str(config),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert json.loads(completed.stderr)["error_code"] == (
        "eitaa_worker_process_feature_disabled"
    )
    assert not secret_file.exists()

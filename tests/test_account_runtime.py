from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from eitaa_bridge.application.account_runtime import EitaaRuntimeRegistry
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.scheduler import EitaaPriority
from eitaa_bridge.config import CoreDependencyConfig
from eitaa_bridge.errors import CompositionValidationError, EitaaRuntimeError
from eitaa_bridge.facade import EitaaBridge
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
)
from eitaa_bridge.infrastructure.diagnostics import (
    BridgeDiagnosticManager,
    RuntimeLogger,
)
from eitaa_bridge.infrastructure.eitaa.sender_directory import (
    current_sender_directory,
)
from eitaa_bridge.infrastructure.eitaa.session_ownership import (
    SessionOwnershipMode,
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
    enabled: bool,
    default_account_id: str | None = None,
) -> Path:
    multi_session: dict[str, object] = {"enabled": enabled}
    if default_account_id is not None:
        multi_session["legacy_default_messenger_account_id"] = default_account_id
    payload = {
        "schema_version": 1,
        "default_site_key": "test-site",
        "bridge": {
            "diagnostics_root": "diagnostics/bridge",
            "diagnostics_enabled": False,
        },
        "features": {
            "multi_session": multi_session,
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
    logger = RuntimeLogger(config.source_file.parent / "runtime" / "logs" / "application.jsonl")
    diagnostics = BridgeDiagnosticManager(
        config.diagnostics.root,
        enabled=False,
    )
    registry = EitaaRuntimeRegistry(
        config,
        application_diagnostics=diagnostics,
        application_logger=logger,
    )
    return registry, logger


def test_feature_off_keeps_v1_explicitly_legacy_and_does_not_open_coordinator(tmp_path):
    root = tmp_path / "installation"
    config_path = _write_config(root, enabled=False)
    registry, logger = _registry(config_path)
    try:
        runtime = registry.resolve_v1()
        assert runtime.ownership.mode is SessionOwnershipMode.LEGACY
        assert runtime.ownership.messenger_account_id is None
        assert not (root / "data" / "coordinator").exists()
        assert not (root / "data" / "accounts").exists()
        with pytest.raises(EitaaRuntimeError) as raised:
            registry.runtime_for_account(str(uuid4()))
        assert raised.value.code == "multi_session_runtime_disabled"
    finally:
        registry.close()
        logger.close()


def test_feature_on_requires_explicit_v1_default(tmp_path):
    root = tmp_path / "installation"
    config_path = _write_config(root, enabled=True)
    config = BridgeConfigLoader.load(config_path)
    logger = RuntimeLogger(root / "runtime" / "logs" / "application.jsonl")
    diagnostics = BridgeDiagnosticManager(root / "diagnostics" / "bridge", enabled=False)
    try:
        with pytest.raises(EitaaRuntimeError) as raised:
            EitaaRuntimeRegistry(
                config,
                application_diagnostics=diagnostics,
                application_logger=logger,
            )
        assert raised.value.code == "multi_session_legacy_default_required"
    finally:
        logger.close()


def test_two_account_runtimes_isolate_all_mutable_state_paths_and_logs(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    first = _bootstrap_account(database, "1")
    second = _bootstrap_account(database, "2")
    _make_runnable(database, first.messenger_account_id, second.messenger_account_id)
    config_path = _write_config(
        root,
        enabled=True,
        default_account_id=first.messenger_account_id,
    )
    registry, logger = _registry(config_path)
    first_runtime = registry.resolve_v1()
    second_runtime = registry.runtime_for_account(second.messenger_account_id)
    first_lock = first_runtime.ownership.worker_lock_file
    second_lock = second_runtime.ownership.worker_lock_file
    try:
        assert first_runtime is registry.runtime_for_account(first.messenger_account_id)
        assert first_runtime is not second_runtime
        assert first_runtime.scheduler is not second_runtime.scheduler
        assert first_runtime.eitaa_lock is not second_runtime.eitaa_lock
        assert first_runtime.jobs_lock is not second_runtime.jobs_lock
        assert first_runtime.content_index_jobs is not second_runtime.content_index_jobs
        assert first_runtime.contact_import_jobs is not second_runtime.contact_import_jobs
        assert first_runtime.pending_read_receipts is not second_runtime.pending_read_receipts
        assert first_runtime.media_cache_files is not second_runtime.media_cache_files
        assert first_runtime.content_index_store.path != second_runtime.content_index_store.path
        assert first_runtime.sender_directory.path != second_runtime.sender_directory.path
        assert first_runtime.dialog_catalog.path != second_runtime.dialog_catalog.path
        assert first_runtime.ownership.worker_log_file != second_runtime.ownership.worker_log_file
        assert first_lock is not None and first_lock.is_file()
        assert second_lock is not None and second_lock.is_file()

        scoped_first = first_runtime.run_sync(
            priority=EitaaPriority.BACKGROUND,
            kind="scope-test-first",
            callback=current_sender_directory,
        )
        scoped_second = second_runtime.run_sync(
            priority=EitaaPriority.BACKGROUND,
            kind="scope-test-second",
            callback=current_sender_directory,
        )
        assert scoped_first is first_runtime.sender_directory
        assert scoped_second is second_runtime.sender_directory

        first_runtime.logger.emit(
            "account_test_event",
            fields={"messenger_account_id": second.messenger_account_id},
        )
        log_path = first_runtime.ownership.worker_log_file
        assert log_path is not None
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        event = next(item for item in records if item["event"] == "account_test_event")
        assert event["fields"]["messenger_account_id"] == first.messenger_account_id
        assert event["fields"]["provider"] == "eitaa"
        assert "phone" not in json.dumps(event).lower()
        assert "token" not in json.dumps(event).lower()
    finally:
        registry.close()
        logger.close()
    assert first_lock is not None and not first_lock.exists()
    assert second_lock is not None and not second_lock.exists()


def test_second_registry_cannot_own_same_account_worker_lock(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "3")
    _make_runnable(database, account.messenger_account_id)
    config_path = _write_config(
        root,
        enabled=True,
        default_account_id=account.messenger_account_id,
    )
    first_registry, first_logger = _registry(config_path)
    second_registry, second_logger = _registry(config_path)
    try:
        first_registry.resolve_v1()
        with pytest.raises(EitaaRuntimeError) as raised:
            second_registry.resolve_v1()
        assert raised.value.code == "eitaa_worker_lease_held"
    finally:
        second_registry.close()
        second_logger.close()
        first_registry.close()
        first_logger.close()


def test_non_runnable_account_fails_closed_before_worker_files_are_created(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "4")
    config_path = _write_config(
        root,
        enabled=True,
        default_account_id=account.messenger_account_id,
    )
    registry, logger = _registry(config_path)
    try:
        with pytest.raises(EitaaRuntimeError) as raised:
            registry.resolve_v1()
        assert raised.value.code == "eitaa_runtime_account_not_runnable"
        assert not (root / "runtime" / "accounts" / account.messenger_account_id).exists()
    finally:
        registry.close()
        logger.close()


def test_application_api_v1_uses_only_configured_account_paths_when_enabled(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "5")
    _make_runnable(database, account.messenger_account_id)
    config_path = _write_config(
        root,
        enabled=True,
        default_account_id=account.messenger_account_id,
    )

    api = BridgeApplicationApi(config_path)
    lock_file = api._runtime.ownership.worker_lock_file
    try:
        assert api._runtime.ownership.messenger_account_id == account.messenger_account_id
        assert api._content_index_store.path == (
            root / "data" / "accounts" / account.messenger_account_id
            / "index" / "content_index.sqlite3"
        )
        core = api._core_config()
        assert core.session_file == (
            root / "data" / "accounts" / account.messenger_account_id
            / "provider" / "session" / "eitaa_session.json"
        )
        assert api.upload_root == (
            root / "runtime" / "accounts" / account.messenger_account_id
            / "cache" / "uploads"
        )
        other_account_file = root / "data" / "accounts" / str(uuid4()) / "media" / "x.jpg"
        other_account_file.parent.mkdir(parents=True)
        other_account_file.write_bytes(b"not-an-image")
        with pytest.raises(CompositionValidationError) as media_error:
            api.register_media_cache_file(other_account_file, "image/jpeg")
        assert media_error.value.code == "api_media_cache_account_boundary"

        outside_peer = root / "data" / "ui-peers" / "legacy.json"
        outside_peer.parent.mkdir(parents=True, exist_ok=True)
        outside_peer.write_text("{}", encoding="utf-8")
        with pytest.raises(CompositionValidationError) as peer_error:
            api._peer_path({"peer_file": str(outside_peer)})
        assert peer_error.value.code == "api_peer_file_account_boundary"
        response = api.dispatch("GET", "/api/v1/health")
        assert response.status == 200
    finally:
        api.close()
    assert lock_file is not None and not lock_file.exists()


def test_close_shared_core_is_limited_to_one_account_configuration(tmp_path):
    class FakeCore:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    first_config = CoreDependencyConfig(
        session_file=tmp_path / "a" / "session.json",
        database_file=tmp_path / "a" / "messages.sqlite3",
        media_directory=tmp_path / "a" / "media",
        diagnostics_root=tmp_path / "a" / "diagnostics",
    )
    second_config = CoreDependencyConfig(
        session_file=tmp_path / "b" / "session.json",
        database_file=tmp_path / "b" / "messages.sqlite3",
        media_directory=tmp_path / "b" / "media",
        diagnostics_root=tmp_path / "b" / "diagnostics",
    )
    first_core = FakeCore()
    second_core = FakeCore()
    EitaaBridge.close_shared_cores()
    try:
        EitaaBridge._shared_cores[EitaaBridge._shared_core_key(first_config)] = first_core
        EitaaBridge._shared_cores[EitaaBridge._shared_core_key(second_config)] = second_core

        EitaaBridge.close_shared_core(first_config)

        assert first_core.closed is True
        assert second_core.closed is False
        assert EitaaBridge._shared_core_key(second_config) in EitaaBridge._shared_cores
    finally:
        EitaaBridge.close_shared_cores()
    assert second_core.closed is True


def test_facade_core_override_replaces_the_complete_core_storage_contract(tmp_path):
    root = tmp_path / "installation"
    config_path = _write_config(root, enabled=False)
    account_root = root / "isolated-account"
    override = CoreDependencyConfig(
        session_file=account_root / "provider" / "session" / "eitaa_session.json",
        database_file=account_root / "core" / "messages.sqlite3",
        media_directory=account_root / "media",
        diagnostics_root=account_root / "diagnostics" / "core",
        diagnostics_enabled=False,
        timeout_seconds=31,
    )

    with EitaaBridge.open(config_path, core_config_override=override) as bridge:
        assert bridge.config.core == override
        assert bridge.core_binding.config == override
        assert bridge.publish_message_workflow.media_directory == override.media_directory
        assert bridge.compose_messages_workflow.media_directory == override.media_directory

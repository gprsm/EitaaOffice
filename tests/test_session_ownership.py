from __future__ import annotations

from pathlib import Path
from uuid import uuid1, uuid4

import pytest

from eitaa_bridge.config import CoreDependencyConfig
from eitaa_bridge.errors import SessionOwnershipError
from eitaa_bridge.infrastructure.eitaa.session_ownership import (
    EitaaSessionOwnership,
    SessionOwnershipMode,
)


def _legacy_core(root: Path) -> CoreDependencyConfig:
    return CoreDependencyConfig(
        session_file=root / ".eitaa_session.json",
        database_file=root / "data" / "eitaa_messages.sqlite3",
        media_directory=root / "data" / "media",
        diagnostics_root=root / "diagnostics" / "core",
        diagnostics_enabled=True,
        timeout_seconds=17.0,
    )


def test_account_ownership_matches_migrated_layout_without_writes(tmp_path):
    root = tmp_path / "installation"
    root.mkdir()
    account_id = str(uuid4())

    ownership = EitaaSessionOwnership.for_messenger_account(
        root,
        account_id,
        core_template=_legacy_core(root),
    )

    account = root / "data" / "accounts" / account_id
    runtime = root / "runtime" / "accounts" / account_id
    assert ownership.mode is SessionOwnershipMode.MESSENGER_ACCOUNT
    assert ownership.messenger_account_id == account_id
    assert ownership.account_data_directory == account
    assert ownership.account_runtime_directory == runtime
    assert ownership.core.session_file == (
        account / "provider" / "session" / "eitaa_session.json"
    )
    assert ownership.core.database_file == account / "core" / "messages.sqlite3"
    assert ownership.core.media_directory == account / "media"
    assert ownership.core.diagnostics_root == runtime / "diagnostics" / "core"
    assert ownership.content_index_file == account / "index" / "content_index.sqlite3"
    assert ownership.sender_directory_file == (
        account / "provider" / "state" / "sender_directory.sqlite3"
    )
    assert ownership.dialog_catalog_file == (
        account / "provider" / "state" / "ui-peers" / "catalog.json"
    )
    assert ownership.contact_peers_directory == (
        account / "provider" / "state" / "contact-peers"
    )
    assert ownership.worker_diagnostics_root == runtime / "diagnostics" / "worker"
    assert ownership.worker_log_file == runtime / "logs" / "worker.jsonl"
    assert ownership.worker_lock_file == runtime / "worker.lock"
    assert ownership.worker_cache_directory == runtime / "cache"
    assert ownership.core.timeout_seconds == 17.0
    assert list(root.iterdir()) == []


def test_two_accounts_have_disjoint_session_runtime_and_data_paths(tmp_path):
    root = tmp_path / "installation"
    first = EitaaSessionOwnership.for_messenger_account(
        root,
        str(uuid4()),
        core_template=_legacy_core(root),
    )
    second = EitaaSessionOwnership.for_messenger_account(
        root,
        str(uuid4()),
        core_template=_legacy_core(root),
    )

    first_paths = {
        first.core.session_file,
        first.core.database_file,
        first.core.media_directory,
        first.core.diagnostics_root,
        first.content_index_file,
        first.sender_directory_file,
        first.dialog_catalog_file,
        first.contact_peers_directory,
        first.worker_diagnostics_root,
        first.worker_log_file,
        first.worker_lock_file,
        first.worker_cache_directory,
    }
    second_paths = {
        second.core.session_file,
        second.core.database_file,
        second.core.media_directory,
        second.core.diagnostics_root,
        second.content_index_file,
        second.sender_directory_file,
        second.dialog_catalog_file,
        second.contact_peers_directory,
        second.worker_diagnostics_root,
        second.worker_log_file,
        second.worker_lock_file,
        second.worker_cache_directory,
    }
    assert first_paths.isdisjoint(second_paths)


@pytest.mark.parametrize(
    "account_id",
    [
        "",
        "not-a-uuid",
        "../other-account",
        str(uuid1()),
        str(uuid4()).upper(),
        "{" + str(uuid4()) + "}",
    ],
)
def test_account_ownership_rejects_noncanonical_uuid4(account_id, tmp_path):
    with pytest.raises(SessionOwnershipError) as raised:
        EitaaSessionOwnership.for_messenger_account(
            tmp_path,
            account_id,
            core_template=_legacy_core(tmp_path),
        )

    assert raised.value.code == "session_owner_identifier_invalid"
    if account_id:
        assert account_id not in str(raised.value)
        assert account_id not in str(raised.value.safe_context)


def test_legacy_ownership_is_explicit_and_preserves_current_paths(tmp_path):
    root = tmp_path / "installation"
    core = _legacy_core(root)

    ownership = EitaaSessionOwnership.legacy(root, core)

    assert ownership.mode is SessionOwnershipMode.LEGACY
    assert ownership.messenger_account_id is None
    assert ownership.account_data_directory is None
    assert ownership.account_runtime_directory is None
    assert ownership.core == core
    assert ownership.content_index_file == root / "data" / "content_index.sqlite3"
    assert ownership.sender_directory_file == root / "data" / "sender_directory.sqlite3"
    assert ownership.dialog_catalog_file == root / "data" / "ui-peers" / "catalog.json"
    assert ownership.contact_peers_directory == root / "data" / "eitaa-contact-peers"
    assert ownership.worker_log_file is None
    assert ownership.worker_diagnostics_root is None
    assert ownership.worker_lock_file is None
    assert ownership.worker_cache_directory is None


def test_legacy_ownership_rejects_a_core_path_outside_installation(tmp_path):
    root = tmp_path / "installation"
    core = _legacy_core(root)
    outside = tmp_path / "outside-session.json"
    unsafe = CoreDependencyConfig(
        session_file=outside,
        database_file=core.database_file,
        media_directory=core.media_directory,
        diagnostics_root=core.diagnostics_root,
    )

    with pytest.raises(SessionOwnershipError) as raised:
        EitaaSessionOwnership.legacy(root, unsafe)

    assert raised.value.code == "session_owner_path_outside_installation"
    assert raised.value.safe_context == {"field": "core.session_file"}
    assert str(outside) not in str(raised.value)


def test_safe_summary_omits_installation_path_and_secrets(tmp_path):
    account_id = str(uuid4())
    ownership = EitaaSessionOwnership.for_messenger_account(
        tmp_path,
        account_id,
        core_template=_legacy_core(tmp_path),
    )

    summary = ownership.safe_summary()

    assert summary["messenger_account_id"] == account_id
    assert summary["provider"] == "eitaa"
    assert str(tmp_path) not in str(summary)
    assert "token" not in str(summary).lower()
    assert "phone" not in str(summary).lower()


def test_phase4b_contract_is_wired_through_explicit_runtime_boundary():
    root = Path(__file__).resolve().parents[1]
    application_source = (
        root / "src" / "eitaa_bridge" / "application" / "api.py"
    ).read_text(encoding="utf-8")
    facade_source = (
        root / "src" / "eitaa_bridge" / "facade.py"
    ).read_text(encoding="utf-8")

    runtime_source = (
        root / "src" / "eitaa_bridge" / "application" / "account_runtime.py"
    ).read_text(encoding="utf-8")

    assert "EitaaRuntimeRegistry" in application_source
    assert "core_config_override=selected_runtime.ownership.core" in application_source
    assert "EitaaSessionOwnership.for_messenger_account" in runtime_source
    assert "def close_shared_core(" in facade_source

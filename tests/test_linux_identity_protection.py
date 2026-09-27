from __future__ import annotations

import os
import stat

import pytest

from eitaa_bridge.errors import CoordinatorIdentityError
from eitaa_bridge.application import account_runtime
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    FileKeyPhoneProtector,
    FileKeySubjectFingerprinter,
    ProtectedPhone,
)


def test_file_key_phone_protector_round_trip_and_tamper_detection(tmp_path):
    key_file = tmp_path / "coordinator" / "identity.key"
    protector = FileKeyPhoneProtector(key_file)

    protected = protector.protect("+989120000001")

    assert protector.reveal(protected) == "+989120000001"
    assert key_file.read_bytes() != b"+989120000001"
    if os.name != "nt":
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700

    tampered = ProtectedPhone(
        ciphertext=protected.ciphertext[:-1] + bytes([protected.ciphertext[-1] ^ 1]),
        key_version=protected.key_version,
        fingerprint=protected.fingerprint,
        display_hint=protected.display_hint,
    )
    with pytest.raises(CoordinatorIdentityError) as caught:
        protector.reveal(tampered)
    assert caught.value.code == "protected_phone_payload_invalid"


def test_linux_coordinator_file_keys_support_bootstrap_and_phone_storage(tmp_path):
    auth = CoordinatorAppAuth(
        tmp_path / "coordinator.sqlite3",
        fingerprinter=FileKeySubjectFingerprinter(tmp_path / "app-auth-subject.key"),
        phone_protector=FileKeyPhoneProtector(tmp_path / "identity.key"),
    )
    auth.initialize()

    issued = auth.bootstrap_admin(
        username="admin",
        password="correct horse battery staple",
        display_name="Administrator",
        client_kind="test",
    )

    assert issued.principal.global_role == "admin"
    assert (tmp_path / "app-auth-subject.key").stat().st_size == 32
    protected = auth.phone_protector.protect("+989120000002")
    assert auth.phone_protector.reveal(protected) == "+989120000002"


def test_child_runtime_reveals_identity_with_coordinator_protector(
    config_file, monkeypatch
):
    config = BridgeConfigLoader.load(config_file)
    coordinator_root = config_file.parent / "data" / "coordinator"
    protector = FileKeyPhoneProtector(coordinator_root / "identity.key")
    phone = "+989120000003"
    database = CoordinatorDatabase(coordinator_root / "coordinator.sqlite3")
    account = database.bootstrap_legacy_account(
        protected_phone=protector.protect(phone),
        display_name="Synthetic Account",
        backup_name="synthetic.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    selected_roots = []

    def select_protector(root):
        selected_roots.append(root)
        return protector

    monkeypatch.setattr(account_runtime, "default_phone_protector", select_protector)
    runtime = account_runtime.EitaaAccountRuntime.account_process(
        config,
        database.messenger_account_runtime(account.messenger_account_id),
    )
    try:
        assert runtime.resolve_login_phone() == phone
        assert selected_roots == [coordinator_root]
    finally:
        runtime.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are required")
def test_file_key_protector_rejects_broad_posix_permissions(tmp_path):
    key_file = tmp_path / "identity.key"
    key_file.write_bytes(os.urandom(32))
    key_file.chmod(0o644)
    with pytest.raises(CoordinatorIdentityError) as caught:
        FileKeyPhoneProtector(key_file)._load_secret()

    assert caught.value.code == "identity_key_permissions_invalid"

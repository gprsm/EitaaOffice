from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from eitaa_core.errors import NetworkError, RpcError

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import CoordinatorSchemaError
from eitaa_bridge.facade import EitaaBridge
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
    WindowsDpapiPhoneProtector,
)


PHONE_A = "+989121234567"
PHONE_B = "+989351112233"


def _bootstrap_account(database: CoordinatorDatabase, seed: str):
    result = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=f"protected-{seed}".encode("ascii"),
            key_version=1,
            fingerprint=(seed * 64)[:64],
            display_hint=f"+••••••••{seed[-1] * 2}",
        ),
        display_name=f"Administrator {seed}",
        backup_name=f"verified-{seed}.zip",
        source_manifest_sha256=(seed * 64)[:64],
        source_file_count=1,
        source_total_bytes=1,
    )
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            """
            UPDATE messenger_accounts
            SET lifecycle_state='active',desired_worker_state='running'
            WHERE id=?
            """,
            (result.messenger_account_id,),
        )
    return result


def _write_config(root: Path, account_id: str, *, name: str = "bridge.json") -> Path:
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
                "legacy_default_messenger_account_id": account_id,
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
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class ProviderChallenge:
    timeout_seconds = 120

    def safe_summary(self):
        return {
            "phone": "+••••••••67",
            "phone_code_hash_present": True,
            "delivery_type": "app",
            "code_length": 5,
            "next_type": None,
            "timeout_seconds": self.timeout_seconds,
        }


class StepResult:
    def __init__(self, *, completed: bool, password_required: bool = False) -> None:
        self.completed = completed
        self.password_required = password_required

    def safe_summary(self):
        return {
            "completed": self.completed,
            "password_required": self.password_required,
            "session": {"present": self.completed} if self.completed else None,
            "password_challenge": (
                {"algorithm": "srp", "hint_present": False}
                if self.password_required
                else None
            ),
        }


class FakeAuthService:
    def __init__(self, config, calls: dict[str, list[str]], *, require_password: bool) -> None:
        self.config = config
        self.calls = calls
        self.require_password = require_password

    def request_code(self, phone: str):
        self.calls.setdefault("phones", []).append(phone)
        return ProviderChallenge()

    def submit_code(self, challenge, code: str):
        assert isinstance(challenge, ProviderChallenge)
        self.calls.setdefault("codes", []).append(code)
        if self.require_password:
            return StepResult(completed=False, password_required=True)
        self._save_session()
        return StepResult(completed=True)

    def submit_password(self, password: str):
        self.calls.setdefault("passwords", []).append(password)
        self._save_session()
        return StepResult(completed=True)

    def _save_session(self) -> None:
        self.config.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.session_file.write_text(
            json.dumps({"token": "provider-secret-token", "imei": "test__web"}),
            encoding="utf-8",
        )


class FakeAuthRuntime:
    def __init__(self, config, calls: dict[str, list[str]], *, require_password: bool) -> None:
        self.auth = FakeAuthService(config, calls, require_password=require_password)
        self.closed = False

    def close(self):
        self.closed = True


def _install_auth(
    monkeypatch,
    *,
    require_password: bool = False,
) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {}

    def open_auth(config):
        return FakeAuthRuntime(
            config,
            calls,
            require_password=require_password,
        )

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaAuth.open", open_auth)
    return calls


def _install_phone_reveal(monkeypatch) -> None:
    class FakePhoneProtector:
        def reveal(self, protected: ProtectedPhone) -> str:
            return PHONE_A if protected.ciphertext.endswith(b"a") else PHONE_B

    monkeypatch.setattr(
        "eitaa_bridge.application.account_runtime.default_phone_protector",
        lambda _root: FakePhoneProtector(),
    )


def _audit_rows(database: CoordinatorDatabase, account_id: str):
    with sqlite3.connect(database.path) as connection:
        return connection.execute(
            """
            SELECT action,result,reason_code,safe_metadata_json,request_id
            FROM audit_events
            WHERE messenger_account_id=? AND action LIKE 'eitaa.auth.%'
            ORDER BY rowid
            """,
            (account_id,),
        ).fetchall()


def test_account_login_is_generation_bound_audited_and_secret_free(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)
    calls = _install_auth(monkeypatch)
    api = BridgeApplicationApi(config_path)
    log_file = api._runtime.ownership.worker_log_file
    lock_file = api._runtime.ownership.worker_lock_file
    try:
        mismatched_phone = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": PHONE_B},
        )
        assert mismatched_phone.status == 400
        assert mismatched_phone.payload["error"]["error_code"] == "eitaa_account_phone_mismatch"
        assert "phones" not in calls
        unchanged = database.messenger_account_runtime(account.messenger_account_id)
        assert unchanged.auth_state == "absent"
        assert unchanged.session_generation == 1

        requested = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        assert requested.status == 200
        challenge = requested.payload["challenge"]
        assert challenge["messenger_account_id"] == account.messenger_account_id
        assert challenge["session_generation"] == 2
        assert challenge["stage"] == "code"
        assert calls["phones"] == [PHONE_A]

        wrong = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": str(uuid4()), "code": "54321"},
        )
        assert wrong.status == 400
        assert wrong.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        assert database.messenger_account_runtime(account.messenger_account_id).auth_state == "challenge_pending"

        completed = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge["challenge_id"], "code": "54321"},
        )
        assert completed.status == 200
        assert completed.payload["auth_state"] == "authenticated"
        assert completed.payload["session_generation"] == 2
        assert calls["codes"] == ["54321"]
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "authenticated"
        assert record.session_generation == 2
        assert api._auth_challenge is None
        assert lock_file is not None
        lock_payload = json.loads(lock_file.read_text(encoding="utf-8"))
        assert lock_payload["session_generation"] == 2

        rows = _audit_rows(database, account.messenger_account_id)
        actions = [row[0] for row in rows]
        assert "eitaa.auth.request_code.succeeded" in actions
        assert "eitaa.auth.challenge.denied" in actions
        assert "eitaa.auth.login.completed" in actions
        metadata = "\n".join(row[3] for row in rows)
        assert PHONE_A not in metadata
        assert "54321" not in metadata
        assert "provider-secret-token" not in metadata
    finally:
        api.close()
    assert log_file is not None
    log_text = log_file.read_text(encoding="utf-8")
    assert PHONE_A not in log_text
    assert "54321" not in log_text
    assert "provider-secret-token" not in log_text


def test_account_login_normalizes_persian_otp_digits_and_direction_marks(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)
    calls = _install_auth(monkeypatch)
    api = BridgeApplicationApi(config_path)
    try:
        requested = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        challenge_id = requested.payload["challenge"]["challenge_id"]

        completed = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "\u200f۵۴۳۲۱\u200e"},
        )

        assert completed.status == 200
        assert calls["codes"] == ["54321"]
    finally:
        api.close()


def test_account_login_maps_provider_code_errors_without_exposing_the_otp(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)

    class RejectingAuthService:
        def request_code(self, phone: str):
            assert phone == PHONE_A
            return ProviderChallenge()

        def submit_code(self, challenge, code: str):
            assert isinstance(challenge, ProviderChallenge)
            raise RpcError(400, "PHONE_CODE_INVALID")

    class RejectingRuntime:
        auth = RejectingAuthService()

        def close(self):
            pass

    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: RejectingRuntime(),
    )
    api = BridgeApplicationApi(config_path)
    try:
        requested = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        response = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={
                "challenge_id": requested.payload["challenge"]["challenge_id"],
                "code": "54321",
            },
        )

        assert response.status == 400
        assert response.payload["error"]["error_code"] == "auth_provider_code_invalid"
        assert "54321" not in json.dumps(response.payload, ensure_ascii=False)
        failure = _audit_rows(database, account.messenger_account_id)[-1]
        assert failure[2] == "provider_code_invalid"
        assert json.loads(failure[3]) == {
            "challenge_stage": "code",
            "error_type": "RpcError",
            "provider_error_kind": "invalid",
        }
    finally:
        api.close()


def test_account_login_network_failure_is_safe_and_audited(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)

    class FailingAuthService:
        def request_code(self, phone: str):
            assert phone == PHONE_A
            raise NetworkError(
                "provider endpoint unavailable",
                safe_context={"endpoint": "https://provider.invalid/api"},
            )

    class FailingRuntime:
        auth = FailingAuthService()

        def close(self):
            pass

    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: FailingRuntime(),
    )
    api = BridgeApplicationApi(config_path)
    log_file = api._runtime.ownership.worker_log_file
    try:
        response = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        assert response.status == 400
        assert (
            response.payload["error"]["error_code"]
            == "auth_provider_network_unreachable"
        )
        assert response.payload["error"]["safe_context"] == {
            "error_type": "NetworkError"
        }
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "absent"
        assert record.session_generation == 1

        rows = _audit_rows(database, account.messenger_account_id)
        failure_rows = [
            row
            for row in rows
            if row[0] == "eitaa.auth.request_code.failed"
        ]
        assert len(failure_rows) == 1
        assert failure_rows[0][1] == "failed"
        assert failure_rows[0][2] == "provider_network_unreachable"
        assert json.loads(failure_rows[0][3]) == {"error_type": "NetworkError"}
        serialized = json.dumps(response.payload, ensure_ascii=False)
        assert PHONE_A not in serialized
        assert "provider.invalid" not in serialized
    finally:
        api.close()
    assert log_file is not None
    log_text = log_file.read_text(encoding="utf-8")
    assert PHONE_A not in log_text
    assert "provider.invalid" not in log_text


def test_challenge_from_one_account_is_rejected_by_another_account(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    first = _bootstrap_account(database, "a")
    second = _bootstrap_account(database, "b")
    first_config = _write_config(root, first.messenger_account_id, name="bridge-a.json")
    second_config = _write_config(root, second.messenger_account_id, name="bridge-b.json")
    _install_phone_reveal(monkeypatch)
    _install_auth(monkeypatch)
    first_api = BridgeApplicationApi(first_config)
    second_api = BridgeApplicationApi(second_config)
    try:
        first_challenge = first_api.dispatch(
            "POST", "/api/v1/auth/request-code", body={}
        ).payload["challenge"]
        second_challenge = second_api.dispatch(
            "POST", "/api/v1/auth/request-code", body={}
        ).payload["challenge"]
        assert first_challenge["challenge_id"] != second_challenge["challenge_id"]

        crossed = second_api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={
                "challenge_id": first_challenge["challenge_id"],
                "code": "11111",
            },
        )
        assert crossed.status == 400
        assert crossed.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        second_record = database.messenger_account_runtime(second.messenger_account_id)
        assert second_record.auth_state == "challenge_pending"
        assert second_record.session_generation == 2
    finally:
        second_api.close()
        first_api.close()


def test_g03c_account_restart_reconciles_lost_challenge_to_expired(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)
    calls = _install_auth(monkeypatch)

    first_api = BridgeApplicationApi(config_path)
    requested = first_api.dispatch("POST", "/api/v1/auth/request-code", body={})
    challenge_id = requested.payload["challenge"]["challenge_id"]
    assert database.messenger_account_runtime(account.messenger_account_id).auth_state == "challenge_pending"
    first_api._close_auth_attempt()
    first_api.close()

    restarted = BridgeApplicationApi(config_path)
    try:
        stale = restarted.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "44444"},
        )
        assert stale.status == 400
        assert stale.payload["error"]["error_code"] == "api_auth_challenge_missing"
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "expired"
        assert record.session_generation == 2
        assert "codes" not in calls
        assert any(row[2] == "challenge_runtime_missing" for row in _audit_rows(database, account.messenger_account_id))
    finally:
        restarted.close()


def test_password_challenge_expires_and_cannot_be_reused(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)
    calls = _install_auth(monkeypatch, require_password=True)
    api = BridgeApplicationApi(config_path)
    try:
        requested = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        challenge_id = requested.payload["challenge"]["challenge_id"]
        password_step = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "22222"},
        )
        assert password_step.status == 200
        assert password_step.payload["step"] == "password"
        assert password_step.payload["challenge"]["challenge_id"] == challenge_id
        assert password_step.payload["challenge"]["stage"] == "password"
        api._auth_challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        expired = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "never-record-this"},
        )
        assert expired.status == 400
        assert expired.payload["error"]["error_code"] == "api_auth_challenge_expired"
        assert "passwords" not in calls
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "expired"
        assert record.session_generation == 2
    finally:
        api.close()


def test_password_challenge_completes_only_the_reserved_generation(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    config_path = _write_config(root, account.messenger_account_id)
    _install_phone_reveal(monkeypatch)
    calls = _install_auth(monkeypatch, require_password=True)
    api = BridgeApplicationApi(config_path)
    try:
        requested = api.dispatch("POST", "/api/v1/auth/request-code", body={})
        challenge_id = requested.payload["challenge"]["challenge_id"]
        password_step = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "33333"},
        )
        assert password_step.status == 200
        completed = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "account-only-password"},
        )
        assert completed.status == 200
        assert completed.payload["auth_state"] == "authenticated"
        assert completed.payload["session_generation"] == 2
        assert calls["passwords"] == ["account-only-password"]
        rows = _audit_rows(database, account.messenger_account_id)
        metadata = "\n".join(row[3] for row in rows)
        assert "account-only-password" not in metadata
        assert "33333" not in metadata
    finally:
        api.close()


def test_account_status_persists_remote_invalidation_once(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    class Core:
        session = SimpleNamespace(safe_summary=lambda: {"present": True})
        discovery = SimpleNamespace(
            list_dialogs=lambda **kwargs: (_ for _ in ()).throw(
                RpcError(401, "INVALID_LOGIN")
            )
        )

        def close(self):
            pass

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaCore.open", lambda *_a, **_k: Core())
    try:
        first = api.dispatch("GET", "/api/v1/auth/status")
        assert first.status == 200
        assert first.payload["session_invalid"] is True
        assert first.payload["auth_state"] == "invalid"
        assert first.payload["session_generation"] == 2

        second = api.dispatch("GET", "/api/v1/auth/status")
        assert second.status == 200
        assert second.payload["auth_state"] == "invalid"
        assert second.payload["session_generation"] == 2
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "invalid"
        assert record.session_generation == 2
    finally:
        api.close()


def test_account_invalid_session_can_be_recovered_automatically_without_confirmation(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")

    class Core:
        session = SimpleNamespace(safe_summary=lambda: {"present": True})
        discovery = SimpleNamespace(
            list_dialogs=lambda **kwargs: (_ for _ in ()).throw(
                RpcError(401, "INVALID_LOGIN")
            )
        )

        def close(self):
            pass

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaCore.open", lambda *_a, **_k: Core())
    try:
        invalid = api.dispatch("GET", "/api/v1/auth/status")
        assert invalid.status == 200
        assert invalid.payload["auth_state"] == "invalid"

        recovered = api.dispatch(
            "POST",
            "/api/v1/auth/reset-local-session",
            body={"automatic_recovery": True},
        )

        assert recovered.status == 200
        assert recovered.payload["login_ready"] is True
        assert recovered.payload["auth_state"] == "absent"
        assert recovered.payload["recovery_mode"] == "automatic"
        assert not session_file.exists()
        assert len(list(session_file.parent.glob(session_file.name + ".invalid.*.bak"))) == 1
        rows = _audit_rows(database, account.messenger_account_id)
        assert any(
            row[0] == "eitaa.auth.session.reset"
            and row[1] == "succeeded"
            and row[2] == "automatic_invalid_session_recovery"
            for row in rows
        )
    finally:
        api.close()


def test_account_automatic_recovery_never_archives_a_session_not_marked_invalid(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")
    try:
        denied = api.dispatch(
            "POST",
            "/api/v1/auth/reset-local-session",
            body={"automatic_recovery": True},
        )
        assert denied.status == 400
        assert denied.payload["error"]["error_code"] == (
            "api_session_automatic_recovery_not_allowed"
        )
        assert session_file.exists()
        assert not list(session_file.parent.glob(session_file.name + ".invalid.*.bak"))
    finally:
        api.close()


def test_account_logout_archives_invalid_session_and_revokes_generation(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text('{"token":"expired-secret"}', encoding="utf-8")

    class Account:
        def logout(self, *, archive_local_session):
            assert archive_local_session is True
            raise RpcError(401, "INVALID_LOGIN")

    class Bridge:
        core = SimpleNamespace(account=Account())

        def close(self):
            pass

    class Context:
        def __enter__(self):
            return Bridge()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(EitaaBridge, "open", lambda *_a, **_k: Context())
    try:
        response = api.dispatch("POST", "/api/v1/auth/logout")
        assert response.status == 200
        assert response.payload["auth_state"] == "revoked"
        assert response.payload["session_generation"] == 2
        assert response.payload["logout"]["remote_session_already_invalid"] is True
        assert not session_file.exists()
        assert len(list(session_file.parent.glob(session_file.name + ".invalid.*.bak"))) == 1
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "revoked"
        assert record.session_generation == 2
    finally:
        api.close()


def test_account_remote_logout_revokes_only_the_selected_generation(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text('{"token":"logout-secret"}', encoding="utf-8")

    class Account:
        def logout(self, *, archive_local_session):
            assert archive_local_session is True
            return SimpleNamespace(
                safe_summary=lambda: {
                    "remote_ok": True,
                    "local_session_archived": False,
                    "archived_path": None,
                }
            )

    class Bridge:
        core = SimpleNamespace(account=Account())

        def close(self):
            pass

    class Context:
        def __enter__(self):
            return Bridge()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(EitaaBridge, "open", lambda *_a, **_k: Context())
    try:
        response = api.dispatch("POST", "/api/v1/auth/logout")
        assert response.status == 200
        assert response.payload["logout"]["remote_ok"] is True
        assert response.payload["logout"]["local_session_archived"] is True
        assert response.payload["auth_state"] == "revoked"
        assert response.payload["session_generation"] == 2
        assert not session_file.exists()
        assert len(list(session_file.parent.glob(session_file.name + ".logout.*.bak"))) == 1
    finally:
        api.close()


def test_account_local_reset_archives_only_its_session_and_fences_generation(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="authenticated",
        increment_generation=False,
        reason_code="test_session_seeded",
        action="eitaa.auth.test.seeded",
    )
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    session_file = api._core_config().session_file
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text('{"token":"reset-secret"}', encoding="utf-8")
    lock_file = api._runtime.ownership.worker_lock_file
    try:
        reset = api.dispatch(
            "POST",
            "/api/v1/auth/reset-local-session",
            body={"confirm": True},
        )
        assert reset.status == 200
        assert reset.payload["auth_state"] == "absent"
        assert reset.payload["session_generation"] == 2
        assert reset.payload["archived"] is True
        assert not session_file.exists()
        assert len(list(session_file.parent.glob(session_file.name + ".invalid.*.bak"))) == 1
        record = database.messenger_account_runtime(account.messenger_account_id)
        assert record.auth_state == "absent"
        assert record.session_generation == 2
        assert lock_file is not None
        assert json.loads(lock_file.read_text(encoding="utf-8"))["session_generation"] == 2
    finally:
        api.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI is required")
def test_account_phone_identity_recovery_is_confirmed_backed_up_and_audited(tmp_path):
    root = tmp_path / "installation"
    database = CoordinatorDatabase(root / "data" / "coordinator" / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE phone_accounts SET display_hint=? WHERE id=?",
            ("+••••••••••67", account.phone_account_id),
        )
    key_file = root / "data" / "coordinator" / "identity.key.dpapi"
    key_file.write_bytes(b"unreadable-current-user-dpapi-key")
    config_path = _write_config(root, account.messenger_account_id)
    api = BridgeApplicationApi(config_path)
    try:
        unconfirmed = api.dispatch(
            "POST",
            "/api/v1/auth/recover-phone-identity",
            body={"phone": PHONE_A},
        )
        assert unconfirmed.status == 400
        assert unconfirmed.payload["error"]["error_code"] == (
            "api_phone_identity_recovery_confirmation_required"
        )

        recovered = api.dispatch(
            "POST",
            "/api/v1/auth/recover-phone-identity",
            body={"phone": PHONE_A, "confirm": True},
        )
        assert recovered.status == 200
        assert recovered.payload["recovered"] is True
        assert recovered.payload["login_ready"] is True
        recovery_root = key_file.parent / "identity-recovery"
        assert len(list(recovery_root.glob("identity.key.dpapi.*.bak"))) == 1
        assert len(list(recovery_root.glob("coordinator.*.bak.sqlite3"))) == 1
        identity = database.messenger_account_phone_identity(account.messenger_account_id)
        assert WindowsDpapiPhoneProtector(key_file).reveal(identity.protected_phone) == PHONE_A

        rows = _audit_rows(database, account.messenger_account_id)
        recovery_rows = [row for row in rows if row[0] == "eitaa.auth.phone_identity.recovered"]
        assert len(recovery_rows) == 1
        encoded_audit = json.dumps(recovery_rows, ensure_ascii=False)
        encoded_response = json.dumps(recovered.payload, ensure_ascii=False)
        log_text = (root / "runtime" / "logs" / "application.jsonl").read_text(
            encoding="utf-8"
        )
        assert PHONE_A not in encoded_audit
        assert PHONE_A not in encoded_response
        assert PHONE_A not in log_text
    finally:
        api.close()


def test_coordinator_auth_transition_is_compare_and_swap_with_atomic_audit(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    account = _bootstrap_account(database, "a")
    updated = database.transition_messenger_auth(
        account.messenger_account_id,
        expected_states={"absent"},
        expected_generation=1,
        new_state="challenge_pending",
        increment_generation=True,
        reason_code="login_challenge_issued",
        action="eitaa.auth.request_code.succeeded",
        actor_app_user_id=account.app_user_id,
        actor_global_role="admin",
        request_id=str(uuid4()),
        safe_metadata={"delivery_type": "app", "timeout_seconds": 120},
    )
    assert updated.auth_state == "challenge_pending"
    assert updated.session_generation == 2

    with pytest.raises(CoordinatorSchemaError) as raised:
        database.transition_messenger_auth(
            account.messenger_account_id,
            expected_states={"absent"},
            expected_generation=1,
            new_state="authenticated",
            increment_generation=False,
            reason_code="stale_completion",
            action="eitaa.auth.login.completed",
        )
    assert raised.value.code == "messenger_auth_transition_conflict"
    record = database.messenger_account_runtime(account.messenger_account_id)
    assert record.auth_state == "challenge_pending"
    assert record.session_generation == 2
    rows = _audit_rows(database, account.messenger_account_id)
    assert [row[0] for row in rows] == ["eitaa.auth.request_code.succeeded"]
    assert rows[0][4] is not None
    with sqlite3.connect(database.path) as connection:
        actor = connection.execute(
            """
            SELECT actor_type,actor_app_user_id,actor_global_role
            FROM audit_events
            WHERE messenger_account_id=? AND action='eitaa.auth.request_code.succeeded'
            """,
            (account.messenger_account_id,),
        ).fetchone()
    assert actor == ("app_user", account.app_user_id, "admin")

    with pytest.raises(CoordinatorSchemaError) as unsafe:
        database.audit_messenger_auth_event(
            account.messenger_account_id,
            action="eitaa.auth.test.denied",
            result="denied",
            reason_code="unsafe_metadata_test",
            safe_metadata={"phone": PHONE_A},
        )
    assert unsafe.value.code == "messenger_auth_audit_metadata_unsafe"
    assert len(_audit_rows(database, account.messenger_account_id)) == 1

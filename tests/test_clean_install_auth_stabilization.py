from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from eitaa_bridge.application.account_auth import LegacyAuthChallenge
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    PasswordHasher,
    StaticSubjectFingerprinter,
)


class _FastPasswordHasher(PasswordHasher):
    """Small deterministic test double; production password policy is tested elsewhere."""

    def hash_password(self, password: str):
        from eitaa_bridge.infrastructure.coordinator.app_auth import PasswordMaterial

        assert len(password) >= 4
        return PasswordMaterial(b"s" * 16, b"d" * 32, 600_000)

    def verify_password(self, password: str, **kwargs) -> bool:
        del kwargs
        return password == "synthetic-password"


class _ProviderChallenge:
    timeout_seconds = 120

    def safe_summary(self):
        return {
            "phone": "+••••••••67",
            "delivery_type": "app",
            "code_length": 5,
            "phone_code_hash": "must-never-leave-memory",
        }


class _ProviderResult:
    def __init__(self, *, completed: bool, password_required: bool) -> None:
        self.completed = completed
        self.password_required = password_required

    def safe_summary(self):
        return {
            "completed": self.completed,
            "password_required": self.password_required,
        }


class _AuthService:
    def __init__(self) -> None:
        self.challenge = _ProviderChallenge()
        self.code_calls: list[tuple[object, str]] = []
        self.password_calls: list[str] = []

    def request_code(self, phone: str):
        assert phone == "synthetic-phone"
        return self.challenge

    def submit_code(self, challenge: object, code: str):
        self.code_calls.append((challenge, code))
        return _ProviderResult(completed=False, password_required=True)

    def submit_password(self, password: str):
        self.password_calls.append(password)
        return _ProviderResult(completed=True, password_required=False)


class _AuthRuntime:
    def __init__(self) -> None:
        self.auth = _AuthService()
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _enable_fresh_app_auth(config_file, *, multi_session: bool) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["bridge"]["diagnostics_enabled"] = False
    payload["core"]["diagnostics_enabled"] = False
    payload["features"] = {
        "multi_session": {
            "enabled": multi_session,
            "legacy_default_messenger_account_id": None,
        },
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def test_empty_coordinator_can_atomically_bootstrap_first_local_admin(tmp_path):
    database_path = tmp_path / "missing-data" / "coordinator" / "coordinator.sqlite3"
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"synthetic-fingerprint-key"),
        password_hasher=_FastPasswordHasher(),
    )

    assert not database_path.exists()
    assert auth.setup_required() is True
    issued = auth.bootstrap_admin(
        username="local.admin",
        password="synthetic-password",
        display_name="Local administrator",
        client_kind="test",
        request_id="synthetic-bootstrap-request",
    )

    assert database_path.is_file()
    assert issued.principal.global_role == "admin"
    assert auth.setup_required() is False
    summary = auth.database.safe_summary()
    assert summary["counts"]["app_users"] == 1
    assert summary["counts"]["phone_accounts"] == 0
    assert summary["counts"]["messenger_accounts"] == 0


def test_fresh_multisession_app_auth_starts_in_empty_bootstrap_mode(
    config_file,
    monkeypatch,
):
    _enable_fresh_app_auth(config_file, multi_session=True)
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"

    assert not database_path.exists()
    api = BridgeApplicationApi(config_file)
    try:
        response = api.dispatch("GET", "/api/v2/app-auth/status")
        assert response.status == 200
        assert response.payload == {
            "ok": True,
            "enabled": True,
            "setup_required": True,
            "authenticated": False,
            "self_registration_enabled": False,
        }
        assert database_path.is_file()
    finally:
        api.close()


def test_legacy_auth_challenge_is_id_and_stage_bound(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtime = _AuthRuntime()
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: runtime,
    )
    api = BridgeApplicationApi(config_file)
    try:
        requested = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        assert requested.status == 200
        challenge = requested.payload["challenge"]
        challenge_id = challenge["challenge_id"]
        assert challenge["stage"] == "code"
        assert challenge["phone"] == "+••••••••67"
        assert "phone_code_hash" not in json.dumps(requested.payload)

        mismatched = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": "00000000-0000-4000-8000-000000000000", "code": "A1234"},
        )
        assert mismatched.status == 400
        assert mismatched.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        assert runtime.auth.code_calls == []

        password_step = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "A1234"},
        )
        assert password_step.status == 200
        assert password_step.payload["step"] == "password"
        assert password_step.payload["challenge"]["challenge_id"] == challenge_id
        assert password_step.payload["challenge"]["stage"] == "password"
        assert runtime.auth.code_calls == [(runtime.auth.challenge, "A1234")]

        stale_stage = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "A1234"},
        )
        assert stale_stage.status == 400
        assert stale_stage.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        assert len(runtime.auth.code_calls) == 1

        wrong_password_challenge = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={
                "challenge_id": "00000000-0000-4000-8000-000000000000",
                "password": "synthetic-password",
            },
        )
        assert wrong_password_challenge.status == 400
        assert (
            wrong_password_challenge.payload["error"]["error_code"]
            == "api_auth_challenge_mismatch"
        )
        assert runtime.auth.password_calls == []

        completed = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "synthetic-password"},
        )
        assert completed.status == 200
        assert completed.payload["step"] == "completed"
        assert runtime.auth.password_calls == ["synthetic-password"]
        assert runtime.closed is True
    finally:
        api.close()


def test_legacy_auth_challenge_expiry_is_fail_closed(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtime = _AuthRuntime()
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: runtime,
    )
    api = BridgeApplicationApi(config_file)
    try:
        requested = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        challenge_id = requested.payload["challenge"]["challenge_id"]
        stored = api._auth_challenge
        assert isinstance(stored, LegacyAuthChallenge)
        stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        expired = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "A1234"},
        )
        assert expired.status == 400
        assert expired.payload["error"]["error_code"] == "api_auth_challenge_expired"
        assert runtime.auth.code_calls == []
        assert runtime.closed is True
        assert api._auth_challenge is None
    finally:
        api.close()


def test_g03c_legacy_restart_discards_pending_challenge_and_runtime(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtimes: list[_AuthRuntime] = []

    def open_auth(*args, **kwargs):
        del args, kwargs
        runtime = _AuthRuntime()
        runtimes.append(runtime)
        return runtime

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaAuth.open", open_auth)
    api = BridgeApplicationApi(config_file)
    requested = api.dispatch(
        "POST",
        "/api/v1/auth/request-code",
        body={"phone": "synthetic-phone"},
    )
    stale_challenge_id = requested.payload["challenge"]["challenge_id"]
    api.close()

    assert len(runtimes) == 1
    assert runtimes[0].closed is True
    assert api._auth_runtime is None
    assert api._auth_challenge is None

    restarted = BridgeApplicationApi(config_file)
    try:
        replay = restarted.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": stale_challenge_id, "code": "A1234"},
        )
        assert replay.status == 400
        assert replay.payload["error"]["error_code"] == "api_auth_challenge_missing"
        assert len(runtimes) == 1
        assert runtimes[0].auth.code_calls == []
    finally:
        restarted.close()


def test_g03c_legacy_password_expiry_is_terminal_and_not_replayable(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtime = _AuthRuntime()
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: runtime,
    )
    api = BridgeApplicationApi(config_file)
    try:
        requested = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        challenge_id = requested.payload["challenge"]["challenge_id"]
        password_step = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": challenge_id, "code": "A1234"},
        )
        assert password_step.status == 200
        assert password_step.payload["challenge"]["stage"] == "password"
        assert isinstance(api._auth_challenge, LegacyAuthChallenge)
        api._auth_challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        expired = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "synthetic-password"},
        )
        assert expired.status == 400
        assert expired.payload["error"]["error_code"] == "api_auth_challenge_expired"
        assert runtime.auth.password_calls == []
        assert runtime.closed is True

        replay = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "synthetic-password"},
        )
        assert replay.status == 400
        assert replay.payload["error"]["error_code"] == "api_auth_challenge_missing"
        assert runtime.auth.password_calls == []
    finally:
        api.close()


def test_g03c_legacy_new_request_supersedes_old_challenge(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtimes: list[_AuthRuntime] = []

    def open_auth(*args, **kwargs):
        del args, kwargs
        runtime = _AuthRuntime()
        runtimes.append(runtime)
        return runtime

    monkeypatch.setattr("eitaa_bridge.application.api.EitaaAuth.open", open_auth)
    api = BridgeApplicationApi(config_file)
    try:
        first = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        second = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        first_id = first.payload["challenge"]["challenge_id"]
        second_id = second.payload["challenge"]["challenge_id"]

        assert first_id != second_id
        assert len(runtimes) == 2
        assert runtimes[0].closed is True
        stale = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": first_id, "code": "A1234"},
        )
        assert stale.status == 400
        assert stale.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        assert runtimes[1].auth.code_calls == []
        assert api._auth_challenge.challenge_id == second_id
    finally:
        api.close()


def test_g03c_legacy_wrong_stage_and_hostile_id_never_reach_provider(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    runtime = _AuthRuntime()
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: runtime,
    )
    api = BridgeApplicationApi(config_file)
    try:
        requested = api.dispatch(
            "POST",
            "/api/v1/auth/request-code",
            body={"phone": "synthetic-phone"},
        )
        challenge_id = requested.payload["challenge"]["challenge_id"]
        wrong_stage = api.dispatch(
            "POST",
            "/api/v1/auth/submit-password",
            body={"challenge_id": challenge_id, "password": "synthetic-password"},
        )
        assert wrong_stage.status == 400
        assert wrong_stage.payload["error"]["error_code"] == "api_auth_challenge_mismatch"

        hostile_id = "hostile-id-with-control-marker\r\nprivate-marker"
        hostile = api.dispatch(
            "POST",
            "/api/v1/auth/submit-code",
            body={"challenge_id": hostile_id, "code": "A1234"},
        )
        assert hostile.status == 400
        assert hostile.payload["error"]["error_code"] == "api_auth_challenge_mismatch"
        assert hostile_id not in json.dumps(hostile.payload)
        assert runtime.auth.code_calls == []
        assert runtime.auth.password_calls == []
    finally:
        api.close()


def test_g03e_empty_multisession_startup_is_repeatable(config_file, monkeypatch):
    _enable_fresh_app_auth(config_file, multi_session=True)
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("provider auth must not open during empty startup")
        ),
    )
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"

    first = BridgeApplicationApi(config_file)
    try:
        first_status = first.dispatch("GET", "/api/v2/app-auth/status")
        assert first_status.status == 200
        assert first_status.payload["setup_required"] is True
        assert first_status.payload["authenticated"] is False
        assert database_path.is_file()
    finally:
        first.close()

    second = BridgeApplicationApi(config_file)
    try:
        second_status = second.dispatch("GET", "/api/v2/app-auth/status")
        assert second_status.status == 200
        assert second_status.payload == first_status.payload
        assert database_path.is_file()
    finally:
        second.close()


def test_g03e_installer_config_copy_rehearsal_starts_offline_twice(
    tmp_path,
    monkeypatch,
):
    source_root = Path(__file__).resolve().parents[1]
    example = source_root / "bridge.example.json"
    installer = source_root / "installer" / "install_office_payload.cmd"
    installer_text = installer.read_text(encoding="utf-8")
    assert 'if not exist "%TARGET%\\bridge.json" copy /Y "%TARGET%\\bridge.example.json" "%TARGET%\\bridge.json" >nul' in installer_text

    install_root = tmp_path / "isolated-install"
    install_root.mkdir()
    config_file = install_root / "bridge.json"
    config_file.write_bytes(example.read_bytes())
    monkeypatch.setenv("EITAA_BRIDGE_WP_MEDICAL_SITE_USERNAME", "editor")
    monkeypatch.setenv("EITAA_BRIDGE_WP_MEDICAL_SITE_APP_PASSWORD", "password")
    monkeypatch.setattr(
        "eitaa_bridge.application.api.EitaaAuth.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("provider auth must not open during installer rehearsal")
        ),
    )

    for _ in range(2):
        api = BridgeApplicationApi(config_file)
        try:
            status = api.dispatch("GET", "/api/v1/auth/status")
            assert status.status == 200
            assert status.payload["authenticated"] is False
        finally:
            api.close()

    assert not (install_root / ".eitaa_session.json").exists()

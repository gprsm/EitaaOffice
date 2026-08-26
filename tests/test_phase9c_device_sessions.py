from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.errors import CoordinatorAuthenticationError, CoordinatorAuthorizationError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


def _database(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    CoordinatorDatabase(path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-session-phone",
            key_version=1,
            fingerprint="7" * 64,
            display_hint="+••••••••45",
        ),
        display_name="Session admin",
        backup_name="verified.zip",
        source_manifest_sha256="6" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    return path


def test_safe_session_list_revoke_and_ownership(tmp_path):
    now = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
    path = _database(tmp_path)
    auth = CoordinatorAppAuth(
        path,
        clock=lambda: now,
        fingerprinter=StaticSubjectFingerprinter(b"phase9-session-secret"),
    )
    first = auth.bootstrap_admin(
        username="session.admin",
        password="correct horse battery staple",
        display_name="مدیر نشست",
        client_kind="electron",
    )
    second = auth.authenticate(
        username="session.admin",
        password="correct horse battery staple",
        client_kind="browser",
        client_address="192.168.1.44",
    )
    second_session = auth.authorize(second.token)
    safe = auth.list_own_sessions(second_session)
    assert len(safe) == 2
    assert sum(bool(item["current"]) for item in safe) == 1
    assert {item["device_label"] for item in safe} == {
        "Windows desktop app",
        "Web browser",
    }
    encoded = json.dumps(safe)
    assert first.token not in encoded
    assert second.token not in encoded
    assert "token_hash" not in encoded
    assert "192.168.1.44" not in encoded
    assert any(item["recent_login"] for item in safe)

    assert auth.revoke_own_session(second_session, first.principal.session_id) is True
    with pytest.raises(CoordinatorAuthenticationError):
        auth.authorize(first.token)

    created = auth.create_user(
        second_session.principal,
        username="session.user",
        password="an ordinary session password",
        display_name="کاربر نشست",
        global_role="user",
    )
    ordinary = auth.authenticate(
        username="session.user",
        password="an ordinary session password",
        client_kind="browser",
    )
    with pytest.raises(CoordinatorAuthorizationError) as cross_user:
        auth.revoke_own_session(second_session, ordinary.principal.session_id)
    assert cross_user.value.code == "app_auth_session_not_found"
    assert created["app_user_id"] == ordinary.principal.app_user_id


def test_session_list_marks_effective_expiry_without_exposing_secrets(tmp_path):
    clock = [datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)]
    path = _database(tmp_path)
    auth = CoordinatorAppAuth(
        path,
        clock=lambda: clock[0],
        fingerprinter=StaticSubjectFingerprinter(b"phase9-expiry-secret"),
    )
    issued = auth.bootstrap_admin(
        username="expiry.admin",
        password="correct horse battery staple",
        display_name="مدیر انقضا",
        client_kind="electron",
    )
    authorized = auth.authorize(issued.token)
    clock[0] += timedelta(hours=13)
    listed = auth.list_own_sessions(authorized)
    assert listed[0]["status"] == "active"
    clock[0] += timedelta(days=365)
    listed = auth.list_own_sessions(authorized)
    assert listed[0]["status"] == "expired"
    assert listed[0]["expires_soon"] is False


def test_session_api_revokes_current_device_and_clears_cookie(config_file, monkeypatch):
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": False},
        "app_user_auth": {"enabled": True},
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    CoordinatorDatabase(database_path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-api-session-phone",
            key_version=1,
            fingerprint="5" * 64,
            display_hint="+••••••••23",
        ),
        display_name="Initial API admin",
        backup_name="verified.zip",
        source_manifest_sha256="4" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"phase9-api-session-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "server-only-password")
    api = BridgeApplicationApi(config_file)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "api.session",
                "password": "correct horse battery staple",
                "display_name": "مدیر API",
            },
            client_kind="test",
        )
        assert setup.status == 201, setup.payload
        token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
        csrf = setup.payload["csrf_token"]
        sessions = api.dispatch(
            "GET", "/api/v2/app-auth/sessions", app_session_token=token
        )
        assert sessions.status == 200
        current = next(item for item in sessions.payload["sessions"] if item["current"])
        revoked = api.dispatch(
            "POST",
            f"/api/v2/app-auth/sessions/{current['session_id']}/revoke",
            app_session_token=token,
            csrf_token=csrf,
        )
        assert revoked.status == 200
        assert revoked.payload["current_session_revoked"] is True
        assert revoked.payload["session_invalid"] is True
        assert "Max-Age=0" in revoked.headers["Set-Cookie"]
        denied = api.dispatch(
            "GET", "/api/v2/app-auth/sessions", app_session_token=token
        )
        assert denied.status == 401
        assert APP_USER_SESSION_COOKIE not in json.dumps(sessions.payload)
    finally:
        api.close()

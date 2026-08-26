from __future__ import annotations

import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


def _enable_app_auth(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": False},
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525_600,
            "absolute_timeout_hours": 8_760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _prepared_api(config_file: Path, monkeypatch) -> BridgeApplicationApi:
    _enable_app_auth(config_file)
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    CoordinatorDatabase(database_path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone",
            key_version=1,
            fingerprint="b" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"api-test-subject-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    return BridgeApplicationApi(config_file)


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    first = cookie.split(";", 1)[0]
    name, token = first.split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    assert token
    return token


def test_app_user_api_setup_session_csrf_roles_and_logout(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api(config_file, monkeypatch)
    try:
        status = api.dispatch("GET", "/api/v2/app-auth/status")
        assert status.status == 200
        assert status.payload["setup_required"] is True

        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "local.admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر محلی",
            },
            client_kind="test",
        )
        assert setup.status == 201
        assert "token" not in setup.payload
        assert "session_token" not in setup.payload
        assert "HttpOnly" in setup.headers["Set-Cookie"]
        assert "SameSite=Strict" in setup.headers["Set-Cookie"]
        assert "Max-Age=31536000" in setup.headers["Set-Cookie"]
        token = _cookie_token(setup)
        csrf = setup.payload["csrf_token"]
        first_refresh = api.dispatch(
            "GET",
            "/api/v2/app-auth/status",
            app_session_token=token,
        )
        second_refresh = api.dispatch(
            "GET",
            "/api/v2/app-auth/status",
            app_session_token=token,
        )
        assert first_refresh.payload["csrf_token"] == csrf
        assert second_refresh.payload["csrf_token"] == csrf
        assert second_refresh.payload["self_registration_enabled"] is True

        registered = api.dispatch(
            "POST",
            "/api/v2/app-auth/register",
            body={
                "username": "mobile.user",
                "password": "1234",
                "display_name": "کاربر موبایل",
            },
            client_kind="browser",
        )
        assert registered.status == 201
        assert registered.payload["principal"]["global_role"] == "user"
        assert registered.payload["principal"]["permissions"]["manage_users"] is False
        assert "Max-Age=31536000" in registered.headers["Set-Cookie"]
        registered_token = _cookie_token(registered)
        registered_csrf = registered.payload["csrf_token"]
        registered_me = api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=registered_token,
        )
        assert registered_me.status == 200
        assert registered_me.payload["principal"]["global_role"] == "user"

        network_for_user = api.dispatch(
            "GET",
            "/api/v2/settings/deployment",
            app_session_token=registered_token,
        )
        assert network_for_user.status == 200
        assert network_for_user.payload["can_manage"] is False
        denied_port_update = api.dispatch(
            "POST",
            "/api/v2/settings/deployment/port",
            app_session_token=registered_token,
            csrf_token=registered_csrf,
            body={"port": 9123, "confirm": True},
        )
        assert denied_port_update.status == 403
        assert denied_port_update.payload["error"]["error_code"] == "app_auth_admin_required"

        network_for_admin = api.dispatch(
            "GET",
            "/api/v2/settings/deployment",
            app_session_token=token,
        )
        assert network_for_admin.status == 200
        assert network_for_admin.payload["can_manage"] is True
        updated_port = api.dispatch(
            "POST",
            "/api/v2/settings/deployment/port",
            app_session_token=token,
            csrf_token=csrf,
            correlation_id="a" * 12,
            body={"port": 9123, "confirm": True},
        )
        assert updated_port.status == 200
        assert updated_port.payload["bind_port"] == 9123
        assert updated_port.payload["restart_required"] is True
        saved_config = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved_config["deployment"]["bind"]["port"] == 9123
        application_log = (
            config_file.parent / "runtime" / "logs" / "application.jsonl"
        ).read_text(encoding="utf-8")
        assert "deployment_port_update_succeeded" in application_log
        assert '"correlation_id":"aaaaaaaaaaaa"' in application_log

        denied = api.dispatch("GET", "/api/v1/scheduler/status")
        assert denied.status == 401
        allowed = api.dispatch(
            "GET",
            "/api/v1/scheduler/status",
            app_session_token=token,
        )
        assert allowed.status == 200

        missing_csrf = api.dispatch(
            "POST",
            "/api/v2/app-users",
            app_session_token=token,
            body={
                "username": "ordinary.user",
                "password": "an ordinary local password",
                "display_name": "کاربر عادی",
                "global_role": "user",
            },
        )
        assert missing_csrf.status == 403
        created = api.dispatch(
            "POST",
            "/api/v2/app-users",
            app_session_token=token,
            csrf_token=csrf,
            client_kind="test",
            body={
                "username": "ordinary.user",
                "password": "an ordinary local password",
                "display_name": "کاربر عادی",
                "global_role": "user",
            },
        )
        assert created.status == 201
        assert created.payload["user"]["global_role"] == "user"

        audit = api.dispatch(
            "GET",
            "/api/v2/audit?limit=10",
            app_session_token=token,
        )
        assert audit.status == 200
        assert audit.payload["events"]
        assert all("phone_account_id" not in event for event in audit.payload["events"])
        exported = api.dispatch(
            "POST",
            "/api/v2/audit/export",
            app_session_token=token,
            csrf_token=csrf,
            body={"max_events": 100},
        )
        assert exported.status == 200
        assert exported.payload["export"]["event_count"] >= 1
        assert len(exported.payload["export"]["sha256"]) == 64
        assert len(list((config_file.parent / "runtime" / "exports" / "audit").glob("*.jsonl"))) == 1

        logged_out = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=token,
            csrf_token=csrf,
        )
        assert logged_out.status == 200
        assert "Max-Age=0" in logged_out.headers["Set-Cookie"]
        after_logout = api.dispatch(
            "GET",
            "/api/v1/scheduler/status",
            app_session_token=token,
        )
        assert after_logout.status == 401

        log_text = (
            config_file.parent / "runtime" / "logs" / "application.jsonl"
        ).read_text(encoding="utf-8")
        assert "correct horse battery staple" not in log_text
        assert token not in log_text
        assert csrf not in log_text
    finally:
        api.close()


def test_http_cookie_protects_json_upload_and_media(
    config_file,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api(config_file, monkeypatch)
    media = tmp_path / "private.jpg"
    media.write_bytes(b"private-image")
    media_token = api.register_media_cache_file(media, "image/jpeg")
    server = BridgeApiHttpServer(
        ("127.0.0.1", 0),
        api,
        upload_root=tmp_path / "uploads",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        setup_request = Request(
            base + "/api/v2/app-auth/setup",
            data=json.dumps(
                {
                    "username": "http.admin",
                    "password": "correct horse battery staple",
                    "display_name": "مدیر HTTP",
                }
            ).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Eitaa-Client-Kind": "browser",
            },
        )
        with urlopen(setup_request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            cookie = response.headers["Set-Cookie"]
        token = cookie.split(";", 1)[0]
        csrf = payload["csrf_token"]
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        assert token.split("=", 1)[1] not in json.dumps(payload)

        with HTTPErrorContext(401):
            urlopen(base + f"/api/v1/media-cache/{media_token}", timeout=5)
        media_request = Request(
            base + f"/api/v1/media-cache/{media_token}",
            headers={"Cookie": token, "X-Eitaa-Client-Kind": "electron"},
        )
        with urlopen(media_request, timeout=5) as response:
            assert response.read() == b"private-image"

        upload_without_csrf = Request(
            base + "/api/v1/files/upload",
            data=b"private-upload",
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Cookie": token,
                "X-Eitaa-Filename": "private.txt",
            },
        )
        with HTTPErrorContext(403):
            urlopen(upload_without_csrf, timeout=5)
        upload = Request(
            base + "/api/v1/files/upload",
            data=b"private-upload",
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Cookie": token,
                "X-CSRF-Token": csrf,
                "X-Eitaa-Filename": "private.txt",
            },
        )
        with urlopen(upload, timeout=5) as response:
            uploaded = json.loads(response.read().decode("utf-8"))
        assert Path(uploaded["path"]).read_bytes() == b"private-upload"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


class HTTPErrorContext:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert isinstance(exc, HTTPError)
        assert exc.code == self.status
        return True

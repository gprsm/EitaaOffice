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


def _enable_app_auth(config_file: Path, *, web_multi_session: bool = False) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": web_multi_session},
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525_600,
            "absolute_timeout_hours": 8_760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    if web_multi_session:
        production = json.loads(
            (Path(__file__).parents[1] / "deploy" / "linux" / "bridge.production.json")
            .read_text(encoding="utf-8")
        )
        payload["deployment"] = production["deployment"]
    config_file.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _prepared_api_with_bearer(
    config_file: Path,
    monkeypatch,
    *,
    bearer_token: str = "configured-secret-token",
    web_multi_session: bool = False,
) -> BridgeApplicationApi:
    _enable_app_auth(config_file, web_multi_session=web_multi_session)
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    bootstrap = CoordinatorDatabase(database_path).bootstrap_legacy_account(
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
    if web_multi_session:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
        payload["features"]["multi_session"]["legacy_default_messenger_account_id"] = (
            bootstrap.messenger_account_id
        )
        config_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"api-test-subject-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    return BridgeApplicationApi(config_file, bearer_token=bearer_token)


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    first = cookie.split(";", 1)[0]
    name, token = first.split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    assert token
    return token


class HTTPErrorContext:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        assert isinstance(exc, HTTPError), f"Expected HTTPError({self.status}), got {exc}"
        assert exc.code == self.status, f"Expected status {self.status}, got {exc.code}"
        return True


def test_when_app_user_auth_enabled_pre_login_and_probes_do_not_require_bearer(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="secret-123")
    try:
        # 1. Health probe succeeds without Bearer header
        health = api.dispatch("GET", "/api/v1/health")
        assert health.status == 200
        assert health.payload["status"] == "alive"

        # 2. Readiness probe succeeds without Bearer header
        readiness = api.dispatch("GET", "/api/v1/readiness")
        assert readiness.status == 200
        assert readiness.payload["status"] == "ready"

        # 3. Schema probe succeeds without Bearer header
        schema = api.dispatch("GET", "/api/v1/schema")
        assert schema.status == 200
        assert "routes" in schema.payload

        # 4. App auth status succeeds without Bearer header
        status = api.dispatch("GET", "/api/v2/app-auth/status")
        assert status.status == 200
        assert status.payload["enabled"] is True
        assert status.payload["setup_required"] is True

        # 5. Bootstrap setup succeeds without Bearer header
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر سیستم",
            },
            client_kind="browser",
        )
        assert setup.status == 201
        session_token = _cookie_token(setup)

        # 6. Login succeeds without Bearer header
        login = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            body={
                "username": "admin",
                "password": "correct horse battery staple",
            },
            client_kind="browser",
        )
        assert login.status == 200
        assert _cookie_token(login)
    finally:
        api.close()


def test_when_app_user_auth_enabled_protected_endpoints_require_session_and_bearer_alone_is_rejected(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="secret-123")
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر سیستم",
            },
            client_kind="browser",
        )
        assert setup.status == 201
        session_token = _cookie_token(setup)

        # Protected route without session token -> 401 app_auth_required
        unauthenticated = api.dispatch("GET", "/api/v2/app-auth/me")
        assert unauthenticated.status == 401
        assert unauthenticated.payload["error"]["error_code"] == "app_auth_required"

        # Protected route with Bearer token alone (no session) -> STILL 401 app_auth_required!
        # This proves Bearer token alone does NOT grant access to user APIs.
        bearer_only = api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            authorization="Bearer secret-123",
        )
        assert bearer_only.status == 401
        assert bearer_only.payload["error"]["error_code"] == "app_auth_required"

        # Protected route with valid session token (and NO Bearer header) -> 200 OK!
        authenticated = api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=session_token,
        )
        assert authenticated.status == 200
        assert authenticated.payload["principal"]["global_role"] == "admin"
        assert authenticated.payload["principal"]["display_name"] == "مدیر سیستم"
    finally:
        api.close()


def test_when_app_user_auth_enabled_local_resource_and_media_cache_accessible_with_session_without_bearer(
    config_file,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="secret-123")
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر سیستم",
            },
            client_kind="browser",
        )
        session_token = _cookie_token(setup)

        # 1. authorize_local_resource with session and NO Bearer succeeds (204)
        allowed = api.authorize_local_resource(
            "GET",
            app_session_token=session_token,
        )
        assert allowed.status == 204

        # 2. authorize_local_resource with Bearer alone (no session) fails (401 app_auth_required)
        denied_bearer = api.authorize_local_resource(
            "GET",
            authorization="Bearer secret-123",
        )
        assert denied_bearer.status == 401
        assert denied_bearer.payload["error"]["error_code"] == "app_auth_required"

        # 3. authorize_local_resource with neither fails (401 app_auth_required)
        denied_none = api.authorize_local_resource("GET")
        assert denied_none.status == 401
        assert denied_none.payload["error"]["error_code"] == "app_auth_required"

        # 4. Media cache token authorization
        media = tmp_path / "test.jpg"
        media.write_bytes(b"test-content")
        media_token = api.register_media_cache_file(media, "image/jpeg")

        media_with_session = api.authorize_media_cache_token(
            media_token,
            app_session_token=session_token,
        )
        assert media_with_session.status == 204

        media_with_bearer_only = api.authorize_media_cache_token(
            media_token,
            authorization="Bearer secret-123",
        )
        assert media_with_bearer_only.status == 401
        assert media_with_bearer_only.payload["error"]["error_code"] == "app_auth_required"
    finally:
        api.close()


def test_when_app_user_auth_disabled_legacy_bearer_enforcement_strictly_preserved(
    config_file,
    monkeypatch,
):
    """When app_user_auth is disabled (single-tenant legacy mode), bearer auth must be enforced as before."""
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file, bearer_token="legacy-secret")
    try:
        assert api.app_user_auth_enabled is False

        # Health denied without Bearer
        assert api.dispatch("GET", "/api/v1/health").status == 401
        # Health allowed with Bearer
        assert api.dispatch("GET", "/api/v1/health", authorization="Bearer legacy-secret").status == 200

        # Readiness denied without Bearer
        assert api.dispatch("GET", "/api/v1/readiness").status == 401
        # Readiness allowed with Bearer
        assert api.dispatch("GET", "/api/v1/readiness", authorization="Bearer legacy-secret").status == 200

        # authorize_local_resource denied without Bearer
        assert api.authorize_local_resource("GET").status == 401
        # authorize_local_resource allowed with Bearer
        assert api.authorize_local_resource("GET", authorization="Bearer legacy-secret").status == 204
    finally:
        api.close()


def test_http_server_end_to_end_bearer_boundary_with_browser_session(
    config_file,
    tmp_path,
    monkeypatch,
):
    """Test full HTTP server lifecycle ensuring browser session succeeds without Bearer."""
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="super-secret-token")
    media = tmp_path / "private.jpg"
    media.write_bytes(b"media-bytes")
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

        # 1. Health and readiness over HTTP without Authorization header
        with urlopen(base + "/api/v1/health", timeout=5) as response:
            assert response.status == 200
            assert json.loads(response.read().decode("utf-8"))["status"] == "alive"

        with urlopen(base + "/api/v1/readiness", timeout=5) as response:
            assert response.status == 200
            assert json.loads(response.read().decode("utf-8"))["status"] == "ready"

        # 2. App auth status over HTTP without Authorization header
        with urlopen(base + "/api/v2/app-auth/status", timeout=5) as response:
            assert response.status == 200
            status_body = json.loads(response.read().decode("utf-8"))
            assert status_body["enabled"] is True
            assert status_body["setup_required"] is True

        # 3. Bootstrap setup over HTTP without Authorization header
        setup_req = Request(
            base + "/api/v2/app-auth/setup",
            data=json.dumps({
                "username": "sysadmin",
                "password": "correct horse battery staple",
                "display_name": "سیستم ادمین",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Eitaa-Client-Kind": "browser"},
            method="POST",
        )
        with urlopen(setup_req, timeout=5) as response:
            assert response.status == 201
            cookie = response.headers["Set-Cookie"]
            setup_payload = json.loads(response.read().decode("utf-8"))
        cookie_header = cookie.split(";", 1)[0]
        csrf_token = setup_payload["csrf_token"]

        # 4. Protected endpoint without session cookie -> 401
        with HTTPErrorContext(401):
            urlopen(base + "/api/v2/app-auth/me", timeout=5)

        # 5. Protected endpoint with Bearer header but no session cookie -> 401
        bearer_req = Request(
            base + "/api/v2/app-auth/me",
            headers={"Authorization": "Bearer super-secret-token"},
        )
        with HTTPErrorContext(401):
            urlopen(bearer_req, timeout=5)

        # 6. Protected endpoint with session cookie and NO Bearer header -> 200 OK
        session_req = Request(
            base + "/api/v2/app-auth/me",
            headers={"Cookie": cookie_header, "X-Eitaa-Client-Kind": "browser"},
        )
        with urlopen(session_req, timeout=5) as response:
            assert response.status == 200
            me_payload = json.loads(response.read().decode("utf-8"))
            assert me_payload["principal"]["global_role"] == "admin"
            assert me_payload["principal"]["display_name"] == "سیستم ادمین"

        # 7. Media cache item with session cookie and NO Bearer header -> 200 OK
        media_req = Request(
            base + f"/api/v1/media-cache/{media_token}",
            headers={"Cookie": cookie_header, "X-Eitaa-Client-Kind": "browser"},
        )
        with urlopen(media_req, timeout=5) as response:
            assert response.status == 200
            assert response.read() == b"media-bytes"

        # 8. File upload with session cookie and CSRF token and NO Bearer header -> 201 OK
        upload_req = Request(
            base + "/api/v1/files/upload",
            data=b"test-upload-payload",
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Cookie": cookie_header,
                "X-CSRF-Token": csrf_token,
                "X-Eitaa-Filename": "test.txt",
                "X-Eitaa-Client-Kind": "browser",
            },
        )
        with urlopen(upload_req, timeout=5) as response:
            assert response.status == 200
            uploaded = json.loads(response.read().decode("utf-8"))
        assert Path(uploaded["path"]).read_bytes() == b"test-upload-payload"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_bearer_alone_cannot_send_messages_when_app_user_auth_enabled(
    config_file,
    monkeypatch,
):
    """Verify that Bearer token alone NEVER allows message sending when app_user_auth is enabled."""
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="secret-token-xyz")
    try:
        # Caller supplies valid Bearer token but NO AppUser session
        response = api.dispatch(
            "POST",
            "/api/v1/messages/send",
            authorization="Bearer secret-token-xyz",
            body={
                "peer": "test_peer",
                "text": "Unauthorized machine message",
            },
        )
        assert response.status == 401
        assert response.payload["error"]["error_code"] == "app_auth_required"
    finally:
        api.close()


def test_http_server_preserves_origin_and_remote_setup_security(
    config_file,
    tmp_path,
    monkeypatch,
):
    """Verify that HTTP server preserves Origin restriction and remote bootstrap admin prohibition."""
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(config_file, monkeypatch, bearer_token="token-456")
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

        # 1. Disallowed Origin is rejected with 403
        bad_origin_req = Request(
            base + "/api/v2/app-auth/status",
            headers={"Origin": "https://malicious-attacker.com"},
        )
        with HTTPErrorContext(403):
            urlopen(bad_origin_req, timeout=5)

        # 2. Setup with disallowed Origin is rejected with 403
        bad_origin_setup = Request(
            base + "/api/v2/app-auth/setup",
            data=json.dumps({
                "username": "attacker",
                "password": "correct horse battery staple",
                "display_name": "مهاجم",
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Origin": "https://malicious-attacker.com",
            },
            method="POST",
        )
        with HTTPErrorContext(403):
            urlopen(bad_origin_setup, timeout=5)
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_production_web_profile_keeps_browser_login_open_and_protected_routes_closed(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = _prepared_api_with_bearer(
        config_file,
        monkeypatch,
        bearer_token="machine-only-test-secret",
        web_multi_session=True,
    )
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        forwarded = {
            "Host": "eitaa.farhangimaz.ir",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.10",
            "X-Eitaa-Client-Kind": "browser",
        }

        for path in ("/api/v1/readiness", "/api/v2/app-auth/status"):
            with urlopen(Request(base + path, headers=forwarded), timeout=5) as response:
                assert response.status == 200

        external_setup = Request(
            base + "/api/v2/app-auth/setup",
            data=b"{}",
            headers={**forwarded, "Origin": "https://eitaa.farhangimaz.ir", "Content-Type": "application/json"},
            method="POST",
        )
        with HTTPErrorContext(403):
            urlopen(external_setup, timeout=5)

        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "webadmin",
                "password": "correct horse battery staple",
                "display_name": "مدیر وب",
            },
            client_kind="browser",
        )
        assert setup.status == 201

        login = Request(
            base + "/api/v2/app-auth/login",
            data=json.dumps({
                "username": "webadmin",
                "password": "correct horse battery staple",
            }).encode("utf-8"),
            headers={**forwarded, "Origin": "https://eitaa.farhangimaz.ir", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(login, timeout=5) as response:
            assert response.status == 200
            cookie = response.headers["Set-Cookie"]
            assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
        cookie_header = cookie.split(";", 1)[0]

        with urlopen(Request(base + "/api/v2/app-auth/me", headers={**forwarded, "Cookie": cookie_header}), timeout=5) as response:
            assert response.status == 200

        with HTTPErrorContext(401):
            urlopen(Request(base + "/api/v2/app-auth/me", headers={**forwarded, "Authorization": "Bearer machine-only-test-secret"}), timeout=5)

        invalid_proxy = {**forwarded, "X-Forwarded-Proto": "http"}
        with HTTPErrorContext(403):
            urlopen(Request(base + "/api/v2/app-auth/status", headers=invalid_proxy), timeout=5)
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)

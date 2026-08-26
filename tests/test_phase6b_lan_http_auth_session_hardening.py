from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.config import (
    HttpDeploymentConfig,
    PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT,
    RemoteMessengerAuthPolicyConfig,
    TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT,
)
from eitaa_bridge.errors import (
    CoordinatorAuthenticationError,
    CoordinatorAuthorizationError,
    CoordinatorAuthRateLimitError,
)
from eitaa_bridge.infrastructure.coordinator import (
    AppAuthPolicy,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    PasswordHasher,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.coordinator.app_auth import PasswordMaterial
from eitaa_bridge.infrastructure.diagnostics import redact
from eitaa_bridge.interfaces.http_api import (
    BridgeApiHttpServer,
    DeploymentRequestPolicy,
    TrustedLanAbuseLimiter,
    _MAX_TRUSTED_LAN_UPLOAD_BYTES,
)


HOST = "192.168.1.20:8765"
ORIGIN = "http://192.168.1.20:8765"


class FastTestPasswordHasher(PasswordHasher):
    iterations = 600_000

    @staticmethod
    def _digest(password: str, salt: bytes) -> bytes:
        return hashlib.sha256(bytes(salt) + password.encode("utf-8")).digest()

    def hash_password(self, password: str) -> PasswordMaterial:
        if len(password) < 12:
            return super().hash_password(password)
        salt = os.urandom(16)
        return PasswordMaterial(salt, self._digest(password, salt), self.iterations)

    def verify_password(
        self,
        password: str,
        *,
        salt: bytes,
        expected_digest: bytes,
        iterations: int,
    ) -> bool:
        del iterations
        return hmac.compare_digest(
            self._digest(password, salt),
            bytes(expected_digest),
        )

    def dummy_material(self) -> PasswordMaterial:
        salt = b"d" * 16
        return PasswordMaterial(
            salt,
            self._digest("dummy-password-value", salt),
            self.iterations,
        )


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def _protected_phone() -> ProtectedPhone:
    return ProtectedPhone(
        ciphertext=b"protected-phone",
        key_version=1,
        fingerprint="b" * 64,
        display_hint="+••••••••67",
    )


def _coordinator_with_admin(
    path: Path,
    *,
    policy: AppAuthPolicy | None = None,
) -> tuple[CoordinatorDatabase, object, CoordinatorAppAuth, MutableClock]:
    database = CoordinatorDatabase(path)
    bootstrap = database.bootstrap_legacy_account(
        protected_phone=_protected_phone(),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    clock = MutableClock(datetime(2026, 8, 10, tzinfo=timezone.utc))
    auth = CoordinatorAppAuth(
        path,
        fingerprinter=StaticSubjectFingerprinter(b"phase6b-test-subject-secret"),
        password_hasher=FastTestPasswordHasher(),
        policy=policy
        or AppAuthPolicy(
            idle_timeout_minutes=30,
            absolute_timeout_hours=12,
            max_failed_attempts=3,
            lockout_minutes=15,
        ),
        clock=clock,
    )
    admin = auth.bootstrap_admin(
        username="local.admin",
        password="correct horse battery staple",
        display_name="مدیر محلی",
        client_kind="test",
    )
    return database, bootstrap, auth, clock


def _enable_trusted_lan(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": False},
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "trusted_lan_http",
        "bind": {"host": "192.168.1.20", "port": 8765},
        "allowed_hosts": [HOST],
        "allowed_origins": [ORIGIN],
        "allowed_private_client_cidrs": ["192.168.1.0/24"],
        "cleartext_http_risk_acknowledgement": TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT,
        "private_lan_only_acknowledgement": PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    config_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _prepared_lan_api(config_file: Path, monkeypatch):
    _enable_trusted_lan(config_file)
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    database = CoordinatorDatabase(database_path)
    bootstrap = database.bootstrap_legacy_account(
        protected_phone=_protected_phone(),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"phase6b-api-subject-secret"),
        password_hasher=FastTestPasswordHasher(),
        policy=AppAuthPolicy(
            idle_timeout_minutes=30,
            absolute_timeout_hours=12,
            max_failed_attempts=5,
            lockout_minutes=15,
        ),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    return BridgeApplicationApi(config_file), auth, bootstrap, database_path


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    name, token = cookie.split(";", 1)[0].split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    assert token
    return token


def _assert_invalid(auth: CoordinatorAppAuth, token: str) -> None:
    with pytest.raises(CoordinatorAuthenticationError) as error:
        auth.authorize(token)
    assert error.value.code == "app_auth_session_invalid"


def _setup_api_admin(api: BridgeApplicationApi):
    response = api.dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "local.admin",
            "password": "correct horse battery staple",
            "display_name": "مدیر محلی",
        },
        client_kind="test",
        client_address="127.0.0.1",
    )
    assert response.status == 201
    return response, _cookie_token(response), response.payload["csrf_token"]


def test_login_replaces_supplied_cookie_and_csrf_is_session_bound(
    config_file,
    monkeypatch,
):
    api, auth, _, _ = _prepared_lan_api(config_file, monkeypatch)
    try:
        _, admin_token, admin_csrf = _setup_api_admin(api)
        created = api.dispatch(
            "POST",
            "/api/v2/app-users",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            body={
                "username": "ordinary.user",
                "password": "an ordinary local password",
                "display_name": "کاربر عادی",
                "global_role": "user",
            },
        )
        assert created.status == 201

        first = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            client_address="192.168.1.41",
            body={
                "username": "ordinary.user",
                "password": "an ordinary local password",
            },
        )
        second = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            app_session_token=admin_token,
            client_address="192.168.1.42",
            body={
                "username": "ordinary.user",
                "password": "an ordinary local password",
            },
        )
        first_token = _cookie_token(first)
        second_token = _cookie_token(second)
        assert len({admin_token, first_token, second_token}) == 3
        assert first.payload["csrf_token"] != second.payload["csrf_token"]
        assert first.payload["principal"]["global_role"] == "user"

        cross_session = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=second_token,
            csrf_token=first.payload["csrf_token"],
        )
        assert cross_session.status == 403
        assert api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=second_token,
        ).payload["principal"]["display_name"] == "کاربر عادی"
        assert api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=admin_token,
        ).payload["principal"]["global_role"] == "admin"

        logged_out = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=first_token,
            csrf_token=first.payload["csrf_token"],
        )
        assert logged_out.status == 200
        replayed = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=first_token,
            csrf_token=first.payload["csrf_token"],
        )
        assert replayed.status == 401
        _assert_invalid(auth, first_token)
    finally:
        api.close()


def test_idle_and_absolute_timeouts_fail_closed_server_side(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, clock = _coordinator_with_admin(
        path,
        policy=AppAuthPolicy(
            idle_timeout_minutes=5,
            absolute_timeout_hours=1,
            max_failed_attempts=3,
            lockout_minutes=15,
        ),
    )
    idle = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    clock.advance(minutes=6)
    _assert_invalid(auth, idle.token)

    absolute = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    for _ in range(14):
        clock.advance(minutes=4)
        auth.authorize(absolute.token)
    clock.advance(minutes=4)
    _assert_invalid(auth, absolute.token)

    corrupt = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE app_user_sessions SET idle_expires_at='not-a-timestamp' WHERE id=?",
            (corrupt.principal.session_id,),
        )
        connection.commit()
    with pytest.raises(CoordinatorAuthenticationError) as corrupt_error:
        auth.authorize(corrupt.token)
    assert corrupt_error.value.code == "app_auth_session_check_failed"


def test_logout_all_admin_revoke_and_access_change_invalidate_sessions(tmp_path):
    _, _, auth, _ = _coordinator_with_admin(tmp_path / "coordinator.sqlite3")
    admin = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="test",
    )
    admin_session = auth.authorize(admin.token)
    created = auth.create_user(
        admin_session.principal,
        username="ordinary.user",
        password="an ordinary local password",
        display_name="کاربر عادی",
        global_role="user",
    )
    first = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )
    second = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="api",
    )
    assert auth.logout_all(auth.authorize(first.token)) == 2
    _assert_invalid(auth, first.token)
    _assert_invalid(auth, second.token)
    assert auth.authorize(admin.token).principal.global_role == "admin"

    third = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )
    fourth = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="api",
    )
    assert auth.revoke_user_sessions(
        admin_session.principal,
        str(created["app_user_id"]),
    ) == 2
    _assert_invalid(auth, third.token)
    _assert_invalid(auth, fourth.token)

    before_role_change = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )
    auth.update_user(
        admin_session.principal,
        str(created["app_user_id"]),
        global_role="admin",
    )
    _assert_invalid(auth, before_role_change.token)
    elevated = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )
    assert elevated.principal.global_role == "admin"
    auth.update_user(
        admin_session.principal,
        str(created["app_user_id"]),
        global_role="user",
    )
    _assert_invalid(auth, elevated.token)
    ordinary = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )
    with pytest.raises(CoordinatorAuthorizationError):
        auth.revoke_user_sessions(
            ordinary.principal,
            admin_session.principal.app_user_id,
        )


def test_lan_client_and_subject_login_throttles_cannot_be_bypassed(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, clock = _coordinator_with_admin(path)
    client = "192.168.1.55"
    for username in ("first.user", "second.user", "third.user"):
        with pytest.raises(CoordinatorAuthenticationError):
            auth.authenticate(
                username=username,
                password="wrong password value",
                client_kind="browser",
                client_address=client,
            )
    with pytest.raises(CoordinatorAuthRateLimitError):
        auth.authenticate(
            username="local.admin",
            password="correct horse battery staple",
            client_kind="browser",
            client_address=client,
        )
    assert auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="browser",
        client_address="192.168.1.56",
    ).principal.global_role == "admin"

    clock.advance(minutes=16)
    for address in ("192.168.1.61", "192.168.1.62", "192.168.1.63"):
        with pytest.raises(CoordinatorAuthenticationError):
            auth.authenticate(
                username="local.admin",
                password="wrong password value",
                client_kind="browser",
                client_address=address,
            )
    with pytest.raises(CoordinatorAuthRateLimitError):
        auth.authenticate(
            username="local.admin",
            password="correct horse battery staple",
            client_kind="browser",
            client_address="192.168.1.64",
        )
    raw = path.read_bytes()
    assert client.encode("ascii") not in raw
    assert b"local.admin" not in raw
    assert b"wrong password value" not in raw


def _ipv4_deployment() -> HttpDeploymentConfig:
    deployment = HttpDeploymentConfig(
        mode="trusted_lan_http",
        bind_host="192.168.1.20",
        bind_port=8765,
        allowed_hosts=(HOST,),
        allowed_origins=(ORIGIN,),
        allowed_private_client_cidrs=("192.168.1.0/24",),
        cleartext_http_risk_acknowledgement=TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT,
        private_lan_only_acknowledgement=PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT,
        bootstrap_admin_loopback_only=True,
        same_origin_only=True,
        remote_messenger_auth=RemoteMessengerAuthPolicyConfig(),
    )
    deployment.validate(app_user_auth_enabled=True)
    return deployment


def test_trusted_lan_host_origin_adversarial_ipv4_normalization():
    policy = DeploymentRequestPolicy(_ipv4_deployment(), 8765)
    base = {
        "path": "/api/v2/app-auth/login",
        "client_address": "192.168.1.42",
    }
    for forged in (
        None,
        "*",
        "example.com",
        "192.168.1.20:8765@evil.test",
        "192.168.1.20:8765,evil.test",
        "192.168.1.20:8765\\evil.test",
        "192.168.001.020:8765",
        "\x00multiple-header-values",
    ):
        assert policy.rejection_code(
            method="GET",
            host_header=forged,
            origin=None,
            **base,
        ) == "deployment_host_rejected"

    assert policy.rejection_code(
        method="POST",
        host_header="192.168.1.20",
        origin=ORIGIN,
        **base,
    ) is None
    assert policy.rejection_code(
        method="POST",
        host_header="192.168.1.20:08765",
        origin="http://192.168.1.20:08765",
        **base,
    ) is None
    assert policy.rejection_code(
        method="POST",
        host_header=HOST,
        origin=None,
        **base,
    ) == "deployment_origin_required"
    for forged_origin in (
        "null",
        "*",
        "http://example.com",
        "http://192.168.1.20:8765.evil.test",
        "http://user@192.168.1.20:8765",
        "http://192.168.1.20:8765, http://evil.test",
        "\x00multiple-header-values",
    ):
        assert policy.rejection_code(
            method="POST",
            host_header=HOST,
            origin=forged_origin,
            **base,
        ) == "deployment_origin_rejected"
    assert policy.rejection_code(
        method="GET",
        host_header=HOST,
        origin="http://example.com",
        **base,
    ) == "deployment_origin_rejected"
    assert policy.rejection_code(
        method="OPTIONS",
        host_header=HOST,
        origin=None,
        **base,
    ) is None


def test_trusted_lan_ipv6_host_origin_normalization():
    deployment = HttpDeploymentConfig(
        mode="trusted_lan_http",
        bind_host="fd12:3456::20",
        bind_port=8765,
        allowed_hosts=("[fd12:3456::20]:8765",),
        allowed_origins=("http://[fd12:3456::20]:8765",),
        allowed_private_client_cidrs=("fd12:3456::/64",),
        cleartext_http_risk_acknowledgement=TRUSTED_LAN_HTTP_ACKNOWLEDGEMENT,
        private_lan_only_acknowledgement=PRIVATE_LAN_ONLY_ACKNOWLEDGEMENT,
        bootstrap_admin_loopback_only=True,
        same_origin_only=True,
        remote_messenger_auth=RemoteMessengerAuthPolicyConfig(),
    )
    deployment.validate(app_user_auth_enabled=True)
    policy = DeploymentRequestPolicy(deployment, 8765)
    base = {
        "method": "POST",
        "path": "/api/v2/app-auth/login",
        "client_address": "fd12:3456::42",
    }
    assert policy.rejection_code(
        host_header="[fd12:3456:0:0:0:0:0:20]:8765",
        origin="http://[fd12:3456:0:0:0:0:0:20]:8765",
        **base,
    ) is None
    assert policy.rejection_code(
        host_header="fd12:3456::20:8765",
        origin="http://[fd12:3456::20]:8765",
        **base,
    ) == "deployment_host_rejected"
    assert policy.rejection_code(
        host_header="[fd12:3456::20]:8765",
        origin="http://[fd12:3456::20]",
        **base,
    ) == "deployment_origin_rejected"


def test_trusted_lan_rate_limiter_is_client_and_bucket_scoped():
    now = [100.0]
    limiter = TrustedLanAbuseLimiter(clock=lambda: now[0])
    assert limiter.allow("192.168.1.10", "all", limit=2)
    assert limiter.allow("192.168.1.10", "all", limit=2)
    assert not limiter.allow("192.168.1.10", "all", limit=2)
    assert limiter.allow("192.168.1.11", "all", limit=2)
    assert limiter.allow("192.168.1.10", "upload", limit=1)
    assert not limiter.allow("192.168.1.10", "upload", limit=1)
    assert not limiter.allow("not-an-ip", "all", limit=2)
    now[0] += 61.0
    assert limiter.allow("192.168.1.10", "all", limit=2)


def _urlopen_json(request: Request):
    with urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8")) if response.length != 0 else {}
        return response.status, payload, response.headers


def test_http_lan_headers_cookie_head_upload_controls_and_safe_logging(
    config_file,
    tmp_path,
    monkeypatch,
    capsys,
):
    api, _, _, _ = _prepared_lan_api(config_file, monkeypatch)
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
                    "username": "local.admin",
                    "password": "correct horse battery staple",
                    "display_name": "مدیر محلی",
                }
            ).encode("utf-8"),
            method="POST",
            headers={
                "Host": HOST,
                "Origin": ORIGIN,
                "Content-Type": "application/json",
            },
        )
        status, setup_payload, setup_headers = _urlopen_json(setup_request)
        assert status == 201
        cookie = setup_headers["Set-Cookie"]
        cookie_header = cookie.split(";", 1)[0]
        csrf = setup_payload["csrf_token"]
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        assert "Secure" not in cookie
        assert setup_headers["Cache-Control"].startswith("no-store")
        assert setup_headers["Content-Security-Policy"].startswith("default-src 'none'")
        assert setup_headers["X-Frame-Options"] == "DENY"
        assert setup_headers["Referrer-Policy"] == "no-referrer"
        assert "camera=()" in setup_headers["Permissions-Policy"]
        assert setup_headers["Access-Control-Allow-Origin"] is None

        missing_origin = Request(
            base + "/api/v2/app-auth/logout",
            data=b"",
            method="POST",
            headers={
                "Host": HOST,
                "Cookie": cookie_header,
                "X-CSRF-Token": csrf,
            },
        )
        with pytest.raises(HTTPError) as origin_error:
            urlopen(missing_origin, timeout=5)
        assert origin_error.value.code == 403

        head = Request(
            base + "/api/v2/app-auth/logout",
            method="HEAD",
            headers={"Host": HOST, "Cookie": cookie_header},
        )
        with pytest.raises(HTTPError) as head_error:
            urlopen(head, timeout=5)
        assert head_error.value.code == 405
        assert head_error.value.headers["Cache-Control"].startswith("no-store")
        me = Request(
            base + "/api/v2/app-auth/me",
            headers={"Host": HOST, "Cookie": cookie_header},
        )
        assert _urlopen_json(me)[1]["principal"]["global_role"] == "admin"

        get_logout = Request(
            base + "/api/v2/app-auth/logout",
            headers={"Host": HOST, "Cookie": cookie_header},
        )
        with pytest.raises(HTTPError) as get_logout_error:
            urlopen(get_logout, timeout=5)
        assert get_logout_error.value.code == 404
        assert _urlopen_json(me)[1]["principal"]["global_role"] == "admin"

        media_request = Request(
            base + f"/api/v1/media-cache/{media_token}",
            headers={"Host": HOST, "Cookie": cookie_header},
        )
        with urlopen(media_request, timeout=5) as response:
            assert response.read() == b"private-image"
            assert response.headers["Cache-Control"].startswith("no-store")
            assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"

        wrong_type = Request(
            base + "/api/v1/files/upload",
            data=b"not-an-upload",
            method="POST",
            headers={
                "Host": HOST,
                "Origin": ORIGIN,
                "Cookie": cookie_header,
                "X-CSRF-Token": csrf,
                "Content-Type": "text/plain",
            },
        )
        with pytest.raises(HTTPError) as content_type_error:
            urlopen(wrong_type, timeout=5)
        assert content_type_error.value.code == 415

        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.putrequest("POST", "/api/v1/files/upload", skip_host=True)
        connection.putheader("Host", HOST)
        connection.putheader("Origin", ORIGIN)
        connection.putheader("Cookie", cookie_header)
        connection.putheader("X-CSRF-Token", csrf)
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Content-Length", str(_MAX_TRUSTED_LAN_UPLOAD_BYTES + 1))
        connection.endheaders()
        oversized = connection.getresponse()
        assert oversized.status == 413
        oversized.read()
        connection.close()

        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.putrequest("POST", "/api/v1/files/upload", skip_host=True)
        connection.putheader("Host", HOST)
        connection.putheader("Origin", ORIGIN)
        connection.putheader("Cookie", cookie_header)
        connection.putheader("X-CSRF-Token", csrf)
        connection.putheader("Content-Type", "application/octet-stream")
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        transfer = connection.getresponse()
        assert transfer.status == 400
        transfer.read()
        connection.close()

        options = Request(
            base + "/api/v2/app-auth/login",
            method="OPTIONS",
            headers={"Host": HOST},
        )
        with urlopen(options, timeout=5) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] is None

        capsys.readouterr()
        secret = "this-is-a-secret-session-token-value"
        missing_media = Request(
            base + f"/api/v1/media-cache/{secret}?password=private-password",
            headers={"Host": HOST, "Cookie": cookie_header},
        )
        with pytest.raises(HTTPError):
            urlopen(missing_media, timeout=5)
        console = capsys.readouterr().err
        assert secret not in console
        assert "private-password" not in console

        private_message = "private message content must never be logged"
        private_phone = "+989121234567"
        unknown = Request(
            base + f"/api/v1/{secret}",
            data=json.dumps(
                {"message": private_message, "phone": private_phone}
            ).encode("utf-8"),
            method="POST",
            headers={
                "Host": HOST,
                "Origin": ORIGIN,
                "Cookie": cookie_header,
                "X-CSRF-Token": csrf,
                "Content-Type": "application/json",
            },
        )
        with pytest.raises(HTTPError):
            urlopen(unknown, timeout=5)
        log_text = (
            config_file.parent / "runtime" / "logs" / "application.jsonl"
        ).read_text(encoding="utf-8")
        for forbidden in (
            secret,
            private_message,
            private_phone,
            cookie_header,
            csrf,
            "correct horse battery staple",
        ):
            assert forbidden not in log_text
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_two_clients_cannot_cross_session_private_scope_or_impersonate(
    config_file,
    monkeypatch,
):
    api, _, bootstrap, database_path = _prepared_lan_api(config_file, monkeypatch)
    try:
        setup, admin_token, admin_csrf = _setup_api_admin(api)
        admin_user_id = setup.payload["principal"]["app_user_id"]
        created_users = {}
        for username, display_name in (
            ("alice.user", "کاربر الف"),
            ("bob.user", "کاربر ب"),
        ):
            created = api.dispatch(
                "POST",
                "/api/v2/app-users",
                app_session_token=admin_token,
                csrf_token=admin_csrf,
                body={
                    "username": username,
                    "password": f"a secure password for {username}",
                    "display_name": display_name,
                    "global_role": "user",
                },
            )
            assert created.status == 201
            created_users[username] = created.payload["user"]["app_user_id"]

        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO phone_account_memberships(
                    id,app_user_id,phone_account_id,role,status,
                    created_by_app_user_id,created_at,updated_at
                ) VALUES(?,?,?,'viewer','active',?,?,?)
                """,
                (
                    str(uuid4()),
                    created_users["alice.user"],
                    bootstrap.phone_account_id,
                    admin_user_id,
                    now,
                    now,
                ),
            )
            connection.commit()

        sessions = {}
        for username, address in (
            ("alice.user", "192.168.1.71"),
            ("bob.user", "192.168.1.72"),
        ):
            response = api.dispatch(
                "POST",
                "/api/v2/app-auth/login",
                client_address=address,
                body={
                    "username": username,
                    "password": f"a secure password for {username}",
                },
            )
            assert response.status == 200
            sessions[username] = (
                _cookie_token(response),
                response.payload["csrf_token"],
            )

        alice_token, alice_csrf = sessions["alice.user"]
        bob_token, bob_csrf = sessions["bob.user"]
        alice_me = api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=alice_token,
        )
        bob_me = api.dispatch(
            "GET",
            f"/api/v2/app-auth/me?app_user_id={created_users['alice.user']}",
            app_session_token=bob_token,
        )
        assert alice_me.payload["principal"]["app_user_id"] == created_users["alice.user"]
        assert bob_me.payload["principal"]["app_user_id"] == created_users["bob.user"]

        alice_accounts = api.dispatch(
            "GET",
            "/api/v2/messenger-accounts",
            app_session_token=alice_token,
        )
        bob_accounts = api.dispatch(
            "GET",
            "/api/v2/messenger-accounts",
            app_session_token=bob_token,
        )
        assert [item["messenger_account_id"] for item in alice_accounts.payload["accounts"]] == [
            bootstrap.messenger_account_id
        ]
        assert bob_accounts.payload["accounts"] == []
        denied_private_account = api.dispatch(
            "GET",
            f"/api/v2/messenger-accounts/{bootstrap.messenger_account_id}",
            app_session_token=bob_token,
        )
        assert denied_private_account.status == 403

        cross_csrf = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=bob_token,
            csrf_token=alice_csrf,
        )
        assert cross_csrf.status == 403
        assert api.dispatch(
            "GET",
            "/api/v2/app-auth/me",
            app_session_token=bob_token,
        ).status == 200
        assert api.dispatch(
            "GET",
            f"/api/v2/app-auth/me?{APP_USER_SESSION_COOKIE}={alice_token}",
        ).status == 401
        assert bob_csrf != alice_csrf
    finally:
        api.close()


def test_auth_audit_excludes_credentials_tokens_client_ip_and_private_content(tmp_path):
    path = tmp_path / "coordinator.sqlite3"
    _, _, auth, _ = _coordinator_with_admin(path)
    issued = auth.authenticate(
        username="local.admin",
        password="correct horse battery staple",
        client_kind="browser",
        client_address="192.168.1.81",
    )
    with pytest.raises(CoordinatorAuthenticationError):
        auth.authenticate(
            username="unknown.user",
            password="wrong password value",
            client_kind="browser",
            client_address="192.168.1.82",
            request_id="safe-request-id",
        )
    auth.logout_all(auth.authorize(issued.token), request_id="logout-all-request")
    raw = path.read_bytes()
    for forbidden in (
        b"local.admin",
        b"unknown.user",
        b"correct horse battery staple",
        b"wrong password value",
        b"192.168.1.81",
        b"192.168.1.82",
        issued.token.encode("ascii"),
        issued.csrf_token.encode("ascii"),
        b"private message content",
    ):
        assert forbidden not in raw


def test_runtime_redaction_covers_auth_material_phone_lists_and_private_messages():
    secrets = {
        "session_token": "session-secret-value",
        "csrf_token": "csrf-secret-value",
        "otp": "123456",
        "set-cookie": "eitaa_bridge_app_session=cookie-secret",
        "phones": ["+989121234567", "+989351112233"],
        "private_message": "private message content",
    }
    serialized = json.dumps(redact(secrets), ensure_ascii=False)
    for forbidden in (
        "session-secret-value",
        "csrf-secret-value",
        "123456",
        "cookie-secret",
        "+989121234567",
        "+989351112233",
        "private message content",
    ):
        assert forbidden not in serialized


def test_auth_material_is_not_persisted_in_browser_storage():
    ui_root = Path(__file__).resolve().parents[1] / "ui" / "src"
    forbidden = (
        "session_token",
        "app_session",
        "csrf_token",
        "password",
        "credential",
        "authorization",
    )
    for path in ui_root.rglob("*"):
        if path.suffix.lower() not in {".ts", ".tsx", ".js"}:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            lowered = line.lower()
            if "localstorage" not in lowered and "sessionstorage" not in lowered:
                continue
            assert not any(item in lowered for item in forbidden), (path, line)

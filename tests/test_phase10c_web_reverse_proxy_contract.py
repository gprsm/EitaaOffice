from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.errors import BridgeConfigurationError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.interfaces.http_api import (
    ApiResponse,
    BridgeApiHttpServer,
    DeploymentRequestPolicy,
    _resolve_server_bind,
)


PUBLIC_HOST = "bridge.example.test"
PUBLIC_ORIGIN = f"https://{PUBLIC_HOST}"
FORWARDED_CLIENT = "203.0.113.10"


def _web_payload(config_file: Path) -> dict:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        }
    }
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "web_reverse_proxy",
        "bind": {"host": "127.0.0.1", "port": 8765},
        "allowed_hosts": [PUBLIC_HOST],
        "allowed_origins": [PUBLIC_ORIGIN],
        "allowed_private_client_cidrs": [],
        "cleartext_http_risk_acknowledgement": None,
        "private_lan_only_acknowledgement": None,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "secure_cookie": True,
        "limits": {
            "max_json_body_bytes": 1024,
            "max_upload_bytes": 2048,
            "request_timeout_seconds": 5,
            "requests_per_minute": 240,
            "uploads_per_minute": 12,
            "shutdown_grace_seconds": 2,
        },
        "reverse_proxy": {
            "enabled": True,
            "trusted_proxy_cidrs": ["127.0.0.0/8", "::1/128"],
            "required_forwarded_proto": "https",
            "require_forwarded_for": True,
        },
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    return payload


def _write_payload(config_file: Path, payload: dict) -> None:
    config_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _load_web(config_file: Path):
    _write_payload(config_file, _web_payload(config_file))
    return BridgeConfigLoader.load(config_file)


def _desktop_port_payload(config_file: Path, port: int) -> dict:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    authority = f"127.0.0.1:{port}"
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "desktop_loopback",
        "bind": {"host": "127.0.0.1", "port": port},
        "allowed_hosts": [authority, f"localhost:{port}"],
        "allowed_origins": [f"http://{authority}", f"http://localhost:{port}"],
        "allowed_private_client_cidrs": ["127.0.0.0/8", "::1/128"],
        "cleartext_http_risk_acknowledgement": None,
        "private_lan_only_acknowledgement": None,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    return payload


def test_web_profile_loads_as_loopback_backend_with_external_https(config_file):
    config = _load_web(config_file)
    deployment = config.deployment
    assert deployment.mode == "web_reverse_proxy"
    assert deployment.bind_host == "127.0.0.1"
    assert deployment.bind_port == 8765
    assert deployment.secure_cookie is True
    assert deployment.request_host_default_port() == 443
    assert deployment.normalized_allowed_host_authorities() == {
        f"{PUBLIC_HOST}:443"
    }
    assert deployment.normalized_allowed_origins() == {
        f"{PUBLIC_ORIGIN}:443"
    }


def test_checked_in_web_example_is_valid_and_contains_no_machine_specific_address():
    example = Path(__file__).parents[1] / "bridge.web-reverse-proxy.example.json"
    config = BridgeConfigLoader.load(example)
    assert config.deployment.mode == "web_reverse_proxy"
    assert config.deployment.bind_host == "127.0.0.1"
    assert config.deployment.allowed_hosts == (PUBLIC_HOST,)
    assert config.deployment.allowed_origins == (PUBLIC_ORIGIN,)


def test_plain_http_port_80_is_configurable_without_binding_it(config_file):
    _write_payload(config_file, _desktop_port_payload(config_file, 80))
    deployment = BridgeConfigLoader.load(config_file).deployment
    assert _resolve_server_bind(
        deployment,
        host_override=None,
        port_override=None,
    ) == ("127.0.0.1", 80)


def test_plain_http_port_443_is_rejected_in_favor_of_tls_termination(config_file):
    _write_payload(config_file, _desktop_port_payload(config_file, 443))
    with pytest.raises(BridgeConfigurationError) as error:
        BridgeConfigLoader.load(config_file)
    assert error.value.code == "deployment_plain_http_443_forbidden"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("secure_cookie", "deployment_web_secure_cookie_required"),
        ("public_bind", "deployment_web_backend_not_loopback"),
        ("http_origin", "deployment_web_origin_not_https"),
        ("lan_client_cidr", "deployment_web_client_cidrs_ambiguous"),
        ("proxy_disabled", "deployment_web_proxy_required"),
        ("untrusted_proxy", "deployment_web_trusted_proxy_not_loopback"),
        ("forwarded_http", "deployment_web_forwarded_proto_invalid"),
        ("forwarded_for_optional", "deployment_web_forwarded_for_required"),
    ],
)
def test_web_profile_configuration_fails_closed(config_file, mutation, expected_code):
    payload = _web_payload(config_file)
    deployment = payload["deployment"]
    if mutation == "secure_cookie":
        deployment["secure_cookie"] = False
    elif mutation == "public_bind":
        deployment["bind"]["host"] = "0.0.0.0"
    elif mutation == "http_origin":
        deployment["allowed_origins"] = [f"http://{PUBLIC_HOST}"]
    elif mutation == "lan_client_cidr":
        deployment["allowed_private_client_cidrs"] = ["192.168.1.0/24"]
    elif mutation == "proxy_disabled":
        deployment["reverse_proxy"]["enabled"] = False
    elif mutation == "untrusted_proxy":
        deployment["reverse_proxy"]["trusted_proxy_cidrs"] = ["192.168.1.0/24"]
    elif mutation == "forwarded_http":
        deployment["reverse_proxy"]["required_forwarded_proto"] = "http"
    elif mutation == "forwarded_for_optional":
        deployment["reverse_proxy"]["require_forwarded_for"] = False
    _write_payload(config_file, payload)
    with pytest.raises(BridgeConfigurationError) as error:
        BridgeConfigLoader.load(config_file)
    assert error.value.code == expected_code


def test_web_request_policy_accepts_only_sanitized_trusted_proxy_context(config_file):
    deployment = _load_web(config_file).deployment
    policy = DeploymentRequestPolicy(deployment, 8765)
    valid = {
        "method": "POST",
        "path": "/api/v2/app-auth/login",
        "host_header": PUBLIC_HOST,
        "origin": PUBLIC_ORIGIN,
        "client_address": "127.0.0.1",
        "forwarded_proto": "https",
        "forwarded_for": FORWARDED_CLIENT,
    }
    context = policy.evaluate(**valid)
    assert context.rejection_code is None
    assert context.client_address == FORWARDED_CLIENT
    assert context.secure_request is True

    adversarial = [
        {"client_address": "192.168.1.50"},
        {"forwarded_proto": None},
        {"forwarded_proto": "http"},
        {"forwarded_for": None},
        {"forwarded_for": "203.0.113.10, 10.0.0.1"},
        {"forwarded_for": "203.0.113.10 10.0.0.1"},
        {"forwarded_for": "0.0.0.0"},
        {"host_header": "attacker.example"},
        {"origin": "https://attacker.example"},
        {"forwarded": "for=203.0.113.10"},
        {"forwarded_host": PUBLIC_HOST},
        {"forwarded_port": "443"},
    ]
    for override in adversarial:
        rejected = policy.evaluate(**(valid | override))
        assert rejected.rejection_code is not None


class _ContractApi:
    def __init__(self, config, upload_root: Path) -> None:
        self.config = config
        self.upload_root = upload_root
        self.last_client_address: str | None = None

    def dispatch(self, method: str, path: str, **kwargs) -> ApiResponse:
        self.last_client_address = kwargs.get("client_address")
        selected_path = path.split("?", 1)[0]
        if method == "GET" and selected_path in {
            "/api/v1/health",
            "/api/v1/readiness",
        }:
            return ApiResponse(200, {"ok": True, "status": "ready"})
        if method == "POST" and selected_path == "/api/v2/app-auth/login":
            cookie = BridgeApplicationApi._session_cookie(self, "synthetic-session")
            return ApiResponse(
                200,
                {"ok": True, "csrf_token": "synthetic-csrf"},
                {"Set-Cookie": cookie},
            )
        if method == "POST" and selected_path == "/api/v2/app-auth/logout":
            return ApiResponse(
                200,
                {"ok": True},
                {"Set-Cookie": BridgeApplicationApi._clear_session_cookie(self)},
            )
        return ApiResponse(404, {"ok": False})

    def authorize_local_resource(self, *_args, **_kwargs) -> ApiResponse:
        return ApiResponse(200, {"ok": True})

    def upload_root_for_account(self, _messenger_account_id):
        return self.upload_root


class _ProxyServer(ThreadingHTTPServer):
    daemon_threads = True


def _proxy_handler(backend_address: tuple[str, int]):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):  # noqa: N802
            self._forward()

        def do_POST(self):  # noqa: N802
            self._forward()

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length) if length else None
            headers = {
                "Host": PUBLIC_HOST,
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": FORWARDED_CLIENT,
            }
            for name in (
                "Origin",
                "Content-Type",
                "Cookie",
                "X-CSRF-Token",
                "X-Eitaa-Filename",
            ):
                value = self.headers.get(name)
                if value is not None:
                    headers[name] = value
            if body is not None:
                headers["Content-Length"] = str(len(body))
            connection = http.client.HTTPConnection(*backend_address, timeout=5)
            try:
                connection.request(self.command, self.path, body=body, headers=headers)
                response = connection.getresponse()
                data = response.read()
                self.send_response(response.status)
                for name, value in response.getheaders():
                    if name.lower() not in {
                        "connection",
                        "date",
                        "server",
                        "transfer-encoding",
                    }:
                        self.send_header(name, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            finally:
                connection.close()

        def log_message(self, _format, *_args) -> None:
            return

    return Handler


@contextmanager
def _web_fixture(config, tmp_path: Path):
    api = _ContractApi(config, tmp_path / "uploads")
    backend = BridgeApiHttpServer(("127.0.0.1", 0), api)
    backend_thread = threading.Thread(target=backend.serve_forever, daemon=True)
    backend_thread.start()
    proxy = _ProxyServer(
        ("127.0.0.1", 0),
        _proxy_handler(("127.0.0.1", int(backend.server_address[1]))),
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    try:
        yield api, backend, ("127.0.0.1", int(proxy.server_address[1]))
    finally:
        proxy.shutdown()
        proxy.server_close()
        proxy_thread.join(timeout=5)
        backend.shutdown()
        backend_thread.join(timeout=5)
        backend.server_close()


def _request(address, method, path, *, body=None, headers=None):
    connection = http.client.HTTPConnection(*address, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        return response.status, dict(response.getheaders()), data
    finally:
        connection.close()


def test_local_tls_terminator_contract_cookie_csrf_limits_health_and_shutdown(
    config_file,
    tmp_path,
):
    config = _load_web(config_file)
    with _web_fixture(config, tmp_path) as (api, backend, proxy_address):
        direct = _request(
            ("127.0.0.1", int(backend.server_address[1])),
            "GET",
            "/api/v1/health",
            headers={"Host": PUBLIC_HOST},
        )
        assert direct[0] == 403

        health_status, health_headers, _ = _request(
            proxy_address,
            "GET",
            "/api/v1/health",
            headers={"X-Forwarded-For": "198.51.100.99"},
        )
        assert health_status == 200
        assert health_headers["Strict-Transport-Security"].startswith("max-age=")
        assert api.last_client_address == FORWARDED_CLIENT

        login_status, login_headers, login_body = _request(
            proxy_address,
            "POST",
            "/api/v2/app-auth/login",
            body=b"{}",
            headers={"Content-Type": "application/json", "Origin": PUBLIC_ORIGIN},
        )
        assert login_status == 200
        cookie = login_headers["Set-Cookie"]
        assert cookie.startswith(f"{APP_USER_SESSION_COOKIE}=")
        assert "; HttpOnly" in cookie
        assert "; SameSite=Strict" in cookie
        assert "; Secure" in cookie
        csrf = json.loads(login_body)["csrf_token"]

        logout_status, logout_headers, _ = _request(
            proxy_address,
            "POST",
            "/api/v2/app-auth/logout",
            body=b"{}",
            headers={
                "Content-Type": "application/json",
                "Origin": PUBLIC_ORIGIN,
                "Cookie": cookie.split(";", 1)[0],
                "X-CSRF-Token": csrf,
            },
        )
        assert logout_status == 200
        assert "; Secure" in logout_headers["Set-Cookie"]

        oversized_json = _request(
            proxy_address,
            "POST",
            "/api/v2/app-auth/login",
            body=b"x" * 1025,
            headers={"Content-Type": "application/json", "Origin": PUBLIC_ORIGIN},
        )
        assert oversized_json[0] == 413

        oversized_upload = _request(
            proxy_address,
            "POST",
            "/api/v1/files/upload",
            body=b"x" * 2049,
            headers={
                "Content-Type": "application/octet-stream",
                "Origin": PUBLIC_ORIGIN,
                "Cookie": cookie.split(";", 1)[0],
                "X-CSRF-Token": csrf,
            },
        )
        assert oversized_upload[0] == 413

        backend.set_not_ready("maintenance")
        readiness = _request(proxy_address, "GET", "/api/v1/readiness")
        assert readiness[0] == 503
        health = _request(proxy_address, "GET", "/api/v1/health")
        assert health[0] == 200

    assert backend.last_shutdown_drained is True

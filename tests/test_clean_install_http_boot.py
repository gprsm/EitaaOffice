"""Regression: a clean process-isolated install must boot the HTTP server.

The RC5 delivery enables app_user_auth + multi_session + worker_process on a
fresh copy (empty coordinator database).  In that state no messenger account
runtime is bound by design, so the server must not resolve runtime-scoped
paths (upload_root) eagerly while starting.  Route handlers must keep
answering with safe JSON errors instead of crashing the process.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


def _write_clean_install_config(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "desktop_loopback",
        "bind": {"host": "127.0.0.1", "port": 8765},
        "allowed_hosts": ["127.0.0.1:8765", "localhost:8765"],
        "allowed_origins": ["http://127.0.0.1:8765", "http://localhost:8765"],
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
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525600,
            "absolute_timeout_hours": 8760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
        "multi_session": {
            "enabled": True,
            "legacy_default_messenger_account_id": None,
        },
        "worker_process": {
            "schema_version": 1,
            "enabled": True,
            "startup_timeout_seconds": 15,
            "request_timeout_seconds": 60,
            "heartbeat_interval_seconds": 5,
            "heartbeat_timeout_seconds": 15,
            "heartbeat_failure_threshold": 3,
            "restart_window_seconds": 300,
            "max_restarts": 3,
            "backoff_initial_seconds": 2,
            "backoff_max_seconds": 60,
            "quarantine_seconds": 300,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def _start_server(config_file: Path) -> tuple[BridgeApiHttpServer, BridgeApplicationApi]:
    api = BridgeApplicationApi(config_file)
    assert api.app_user_auth_enabled
    assert api.config.features.multi_session.enabled
    assert api.config.features.worker_process.enabled
    # A clean process-isolated install binds no runtime until the first
    # explicit account Start request; eager access here is the old bug.
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, api


def test_clean_install_server_boots_without_runtime(config_file: Path) -> None:
    _write_clean_install_config(config_file)
    server, api = _start_server(config_file)
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"

        with urlopen(base + "/api/v1/health", timeout=5) as response:
            assert response.status == 200
            body = json.loads(response.read().decode("utf-8"))
        assert body["ok"] is True

        # Onboarding must stay reachable: setup is reported as required.
        with urlopen(base + "/api/v2/app-auth/status", timeout=5) as response:
            assert response.status == 200
            status = json.loads(response.read().decode("utf-8"))
        assert status["setup_required"] is True
    finally:
        server.shutdown()
        server.server_close()
        api.close()


def test_clean_install_upload_returns_safe_error_not_crash(config_file: Path) -> None:
    _write_clean_install_config(config_file)
    server, api = _start_server(config_file)
    try:
        host, port = server.server_address
        request = Request(
            f"http://{host}:{port}/api/v1/files/upload",
            data=b"payload",
            method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            urlopen(request, timeout=5)
            raise AssertionError("upload without a session must be rejected")
        except Exception as exc:  # urllib raises HTTPError for 4xx statuses
            status = getattr(exc, "code", None) or getattr(
                getattr(exc, "reason", None), "code", 500
            )
            assert 400 <= int(status) < 500, status
            raw = getattr(exc, "read", lambda: b"{}")()
            body = json.loads(raw.decode("utf-8"))

        assert body["ok"] is False
        error = body["error"]
        assert error["component"] == "app_auth"
        assert error["error_code"] == "app_auth_required"

        # The server must survive the rejected upload and keep serving.
        with urlopen(
            f"http://{host}:{port}/api/v1/health", timeout=5
        ) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        api.close()

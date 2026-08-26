from __future__ import annotations

import errno
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import BridgeConfigurationError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.windows_lan import (
    WindowsLanInstanceLock,
    build_windows_firewall_plan,
)
from eitaa_bridge.interfaces import windows_lan as windows_lan_launcher
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer, _bind_error_code


CLEARTEXT_ACK = "I_ACCEPT_TRUSTED_LAN_HTTP_WITHOUT_TRANSPORT_SECURITY"
PRIVATE_LAN_ACK = "I_WILL_NOT_EXPOSE_THIS_SERVICE_TO_PUBLIC_OR_GUEST_NETWORKS"


def _trusted_config(config_file: Path) -> Path:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
        "multi_session": {
            "enabled": False,
            "legacy_default_messenger_account_id": None,
        },
    }
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "trusted_lan_http",
        "bind": {"host": "192.168.44.20", "port": 8765},
        "allowed_hosts": ["192.168.44.20:8765"],
        "allowed_origins": ["http://192.168.44.20:8765"],
        "allowed_private_client_cidrs": ["192.168.44.0/24"],
        "cleartext_http_risk_acknowledgement": CLEARTEXT_ACK,
        "private_lan_only_acknowledgement": PRIVATE_LAN_ACK,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    return config_file


def _json_url(url: str):
    with urlopen(url, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8")), response.headers


def test_health_and_readiness_are_separate_safe_operational_contracts(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        health_status, health, health_headers = _json_url(
            f"http://{host}:{port}/api/v1/health"
        )
        ready_status, readiness, ready_headers = _json_url(
            f"http://{host}:{port}/api/v1/readiness"
        )
        assert health_status == 200
        assert health == {
            "ok": True,
            "service": "eitaa-bridge-api",
            "status": "alive",
            "api_version": "v1",
            "bridge_version": health["bridge_version"],
            "core_product": "0.6.0-core7.4.5-gmi1",
            "core_package": "0.6.0.dev19",
        }
        assert ready_status == 200
        assert readiness == {
            "ok": True,
            "service": "eitaa-bridge-api",
            "status": "ready",
            "deployment_mode": "desktop_loopback",
            "reason": "ready",
        }
        serialized = json.dumps({"health": health, "readiness": readiness}).lower()
        for forbidden in (
            "default_site_key",
            "scheduler",
            "token",
            "cookie",
            "phone",
            "provider_session",
            "file_path",
        ):
            assert forbidden not in serialized
        assert health_headers["Cache-Control"].startswith("no-store")
        assert ready_headers["Cache-Control"].startswith("no-store")

        server.set_not_ready("maintenance")
        with pytest.raises(HTTPError) as not_ready_error:
            urlopen(f"http://{host}:{port}/api/v1/readiness", timeout=5)
        assert not_ready_error.value.code == 503
        not_ready = json.loads(not_ready_error.value.read().decode("utf-8"))
        assert not_ready == {
            "ok": False,
            "service": "eitaa-bridge-api",
            "status": "not_ready",
            "deployment_mode": "desktop_loopback",
            "reason": "maintenance",
        }
        assert _json_url(f"http://{host}:{port}/api/v1/health")[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_application_readiness_preserves_optional_bearer_boundary(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file, bearer_token="local-secret")
    try:
        assert api.dispatch("GET", "/api/v1/readiness").status == 401
        response = api.dispatch(
            "GET",
            "/api/v1/readiness",
            authorization="Bearer local-secret",
        )
        assert response.status == 200
        assert response.payload["status"] == "ready"
    finally:
        api.close()


def test_instance_lock_rejects_concurrency_and_replaces_stale_metadata(tmp_path):
    lock_path = tmp_path / "trusted-lan-http.lock"
    lock_path.write_text('{"status":"stale","pid":999999}\n', encoding="utf-8")
    first = WindowsLanInstanceLock(lock_path, deployment_mode="trusted_lan_http")
    first.acquire()
    try:
        running = json.loads(lock_path.read_text(encoding="utf-8"))
        assert running["status"] == "running"
        assert running["deployment_mode"] == "trusted_lan_http"
        with pytest.raises(BridgeConfigurationError) as duplicate:
            WindowsLanInstanceLock(
                lock_path,
                deployment_mode="trusted_lan_http",
            ).acquire()
        assert duplicate.value.code == "windows_lan_instance_running"
    finally:
        first.release()
    assert json.loads(lock_path.read_text(encoding="utf-8"))["status"] == "stopped"

    restarted = WindowsLanInstanceLock(lock_path, deployment_mode="trusted_lan_http")
    restarted.acquire()
    restarted.release()


def test_firewall_plan_is_private_exact_and_never_executes(config_file):
    config = BridgeConfigLoader.load(_trusted_config(config_file))
    payload = build_windows_firewall_plan(config).as_dict()
    assert payload["execution_performed"] is False
    assert payload["requires_explicit_administrator_confirmation"] is True
    assert payload["rule"] == {
        "display_name": "Eitaa Bridge Trusted LAN",
        "direction": "Inbound",
        "action": "Allow",
        "enabled": True,
        "profile": "Private",
        "protocol": "TCP",
        "edge_traversal": "Block",
        "local_address": "192.168.44.20",
        "local_port": 8765,
        "remote_addresses": ["192.168.44.0/24"],
    }
    preview = payload["powershell_preview"]
    assert "-Profile Private" in preview
    assert "-LocalAddress '192.168.44.20'" in preview
    assert "-LocalPort 8765" in preview
    assert "192.168.44.0/24" in preview
    assert "0.0.0.0/0" not in preview
    assert "-Profile Public" not in preview
    assert "RemoteAddress Any" not in preview


def test_firewall_plan_and_launcher_fail_closed_for_loopback(config_file, tmp_path):
    config = BridgeConfigLoader.load(config_file)
    with pytest.raises(BridgeConfigurationError) as firewall_error:
        build_windows_firewall_plan(config)
    assert firewall_error.value.code == "windows_firewall_plan_requires_trusted_lan_http"

    ui_root = tmp_path / "ui"
    ui_root.mkdir()
    (ui_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
    result = windows_lan_launcher.main(
        ["check", "--config", str(config_file), "--ui-root", str(ui_root)]
    )
    assert result == 1


def test_windows_launcher_uses_config_without_host_or_port_override(
    config_file,
    tmp_path,
    monkeypatch,
):
    _trusted_config(config_file)
    ui_root = tmp_path / "ui"
    ui_root.mkdir()
    (ui_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
    captured = {}

    def fake_http_main(argv):
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr(windows_lan_launcher, "http_main", fake_http_main)
    lock_path = tmp_path / "runtime" / "server.lock"
    result = windows_lan_launcher.main(
        [
            "start",
            "--config",
            str(config_file),
            "--ui-root",
            str(ui_root),
            "--lock-file",
            str(lock_path),
        ]
    )
    assert result == 0
    assert captured["argv"] == [
        "--config",
        str(config_file.resolve()),
        "--ui-root",
        str(ui_root.resolve()),
    ]
    assert "--host" not in captured["argv"]
    assert "--port" not in captured["argv"]
    assert json.loads(lock_path.read_text(encoding="utf-8"))["status"] == "stopped"


def test_bind_error_distinguishes_port_conflict_without_leaking_address():
    assert _bind_error_code(OSError(errno.EADDRINUSE, "address in use")) == "port_conflict"
    assert _bind_error_code(OSError(errno.EACCES, "denied")) == "bind_failed"

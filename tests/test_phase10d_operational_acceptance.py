from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
from zipfile import ZIP_DEFLATED, ZipFile

from eitaa_bridge.config import HttpDeploymentConfig
from eitaa_bridge.interfaces.http_api import ApiResponse, BridgeApiHttpServer


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_support_bundle_redacts_secret_phone_ip_and_user_path(tmp_path, monkeypatch):
    runtime_state = _load_script("phase10d_runtime_state", ROOT / "scripts" / "runtime_state.py")
    monkeypatch.setitem(sys.modules, "runtime_state", runtime_state)
    bundle_module = _load_script(
        "phase10d_create_bundle", ROOT / "scripts" / "create_diagnostics_bundle.py"
    )
    scanner = _load_script(
        "phase10d_scan_bundle", ROOT / "scripts" / "scan_diagnostics_bundle.py"
    )
    installation = tmp_path / "installation"
    log = installation / "runtime" / "logs" / "application.jsonl"
    log.parent.mkdir(parents=True)
    (installation / "bridge.json").write_text(
        json.dumps({"password": "private-value", "phone": "+989121234567"}),
        encoding="utf-8",
    )
    (installation / ".env").write_text("TOKEN=private-value", encoding="utf-8")
    log.write_text(
        json.dumps(
            {
                "phone": "+989121234567",
                "token": "A" * 40,
                "client": "192.168.10.20",
                "email": "private.person@example.test",
                "path": r"C:\Users\PrivateName\Documents\bridge",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "support.zip"
    monkeypatch.setattr(bundle_module, "project_root", lambda: installation)
    monkeypatch.setattr(bundle_module, "load_version", lambda _root: "test")
    monkeypatch.setattr(bundle_module, "run_doctor", lambda _root: "doctor-safe")
    monkeypatch.setattr(sys, "argv", ["create_diagnostics_bundle.py", "--output", str(output)])
    assert bundle_module.main() == 0
    result = scanner.scan_bundle(output)
    assert result["verified"] is True
    assert result["finding_count"] == 0
    with ZipFile(output) as archive:
        combined = "\n".join(
            archive.read(name).decode("utf-8") for name in archive.namelist()
        )
    for forbidden in (
        "private-value",
        "+989121234567",
        "192.168.10.20",
        "private.person@example.test",
        "PrivateName",
        "A" * 40,
    ):
        assert forbidden not in combined


def test_support_bundle_scanner_rejects_private_members_and_unredacted_values(tmp_path):
    scanner = _load_script(
        "phase10d_scan_bundle_adversarial",
        ROOT / "scripts" / "scan_diagnostics_bundle.py",
    )
    bundle = tmp_path / "unsafe-support.zip"
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(".eitaa_session.json", "private-session")
        archive.writestr(
            "logs/application.jsonl",
            json.dumps(
                {
                    "token": "unredacted-value",
                    "phone": "+989121234567",
                    "email": "private.person@example.test",
                    "path": r"C:\Users\PrivateName\Documents\bridge",
                }
            )
            + "\n",
        )
    result = scanner.scan_bundle(bundle)
    assert result["verified"] is False
    kinds = {item["kind"] for item in result["findings"]}
    assert {
        "private_state_member",
        "full_phone",
        "email_address",
        "windows_user_path",
        "unredacted_secret_assignment",
    } <= kinds


class _LifecycleApi:
    def __init__(self, upload_root: Path) -> None:
        self.config = SimpleNamespace(deployment=HttpDeploymentConfig.desktop_loopback())
        self.upload_root = upload_root

    def dispatch(self, method: str, path: str, **_kwargs) -> ApiResponse:
        if method == "GET" and path in {"/api/v1/health", "/api/v1/readiness"}:
            return ApiResponse(200, {"ok": True, "status": "ready"})
        return ApiResponse(404, {"ok": False})


def _request(port: int, path: str) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _start_server(api, port: int = 0):
    server = BridgeApiHttpServer(("127.0.0.1", port), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_server(server, thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    assert not thread.is_alive()
    assert server.last_shutdown_drained is True


def test_isolated_health_readiness_drain_and_same_port_restart(tmp_path):
    api = _LifecycleApi(tmp_path / "uploads")
    first, first_thread = _start_server(api)
    port = int(first.server_address[1])
    assert _request(port, "/api/v1/health")[0] == 200
    assert _request(port, "/api/v1/readiness")[0] == 200
    first.set_not_ready("maintenance")
    assert _request(port, "/api/v1/readiness")[0] == 503
    assert _request(port, "/api/v1/health")[0] == 200
    _stop_server(first, first_thread)

    restarted, restarted_thread = _start_server(api, port)
    try:
        assert _request(port, "/api/v1/health")[0] == 200
        assert _request(port, "/api/v1/readiness")[0] == 200
    finally:
        _stop_server(restarted, restarted_thread)

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer, RuntimeOwnership


def _request_json(url: str, *, method: str = "GET", token: str | None = None, body=None):
    headers = {"Accept": "application/json"}
    data = None
    if token is not None:
        headers["X-Eitaa-Runtime-Token"] = token
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_owned_runtime_identity_heartbeat_and_shutdown(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    state_file = tmp_path / "runtime" / "backend-state.json"
    ownership = RuntimeOwnership(
        install_id="install-123",
        owner_root=tmp_path.resolve(),
        owner_token="owner-secret",
        state_file=state_file,
        heartbeat_timeout=30,
    )
    server = BridgeApiHttpServer(("127.0.0.1", 0), api, runtime_ownership=ownership)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        status, payload = _request_json(base + "/api/v1/runtime/identity")
        assert status == 403
        assert payload["error"]["error_code"] == "runtime_owner_unauthorized"

        status, payload = _request_json(
            base + "/api/v1/runtime/identity", token="owner-secret"
        )
        assert status == 200
        assert payload["runtime_protocol"] == "1"
        assert payload["api_version"] == "v1"
        assert payload["install_id"] == "install-123"
        assert Path(payload["owner_root"]) == tmp_path.resolve()
        assert payload["pid"] > 0
        assert state_file.is_file()

        status, payload = _request_json(
            base + "/api/v1/runtime/heartbeat",
            method="POST",
            token="owner-secret",
            body={"install_id": "wrong"},
        )
        assert status == 409
        assert payload["error"]["error_code"] == "runtime_install_id_mismatch"

        status, payload = _request_json(
            base + "/api/v1/runtime/heartbeat",
            method="POST",
            token="owner-secret",
            body={"install_id": "install-123"},
        )
        assert status == 200
        assert payload["ok"] is True

        status, payload = _request_json(
            base + "/api/v1/runtime/shutdown",
            method="POST",
            token="owner-secret",
            body={"install_id": "install-123"},
        )
        assert status == 202
        assert payload["status"] == "shutting_down"
        thread.join(timeout=4)
        assert not thread.is_alive()
    finally:
        server.server_close()
        api.close()
        thread.join(timeout=2)
    assert not state_file.exists()


def test_unmanaged_runtime_endpoint_does_not_claim_ownership(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        status, payload = _request_json(
            f"http://{host}:{port}/api/v1/runtime/identity", token="anything"
        )
        assert status == 404
        assert payload["error"]["error_code"] == "runtime_ownership_disabled"
    finally:
        server.shutdown()
        server.server_close()
        api.close()
        thread.join(timeout=3)


def test_heartbeat_timeout_stops_owned_backend(config_file, tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    ownership = RuntimeOwnership(
        install_id="timeout-install",
        owner_root=tmp_path.resolve(),
        owner_token="timeout-secret",
        state_file=tmp_path / "backend-state.json",
        heartbeat_timeout=0.35,
    )
    server = BridgeApiHttpServer(("127.0.0.1", 0), api, runtime_ownership=ownership)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join(timeout=2.5)
        assert not thread.is_alive()
    finally:
        server.server_close()
        api.close()
        thread.join(timeout=2)


def _load_office_runtime(root: Path):
    path = root / "scripts" / "office_runtime.py"
    spec = importlib.util.spec_from_file_location("office_runtime_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_controller_requires_exact_handshake(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = tmp_path / "app"
    root.mkdir()
    (root / "VERSION.txt").write_text("0.7.0-ui-mvp6.1.1-runtime3\n", encoding="utf-8")
    controller = module.RuntimeController(root, port=18765)
    payload = {
        "ok": True,
        "runtime_protocol": "1",
        "api_version": "v1",
        "bridge_version": "0.7.0-ui-mvp6.1.1-runtime3",
        "install_id": controller.install_id,
        "owner_root": str(root.resolve()),
    }
    assert controller.identity_matches(payload)
    assert not controller.identity_matches({**payload, "install_id": "other"})
    assert not controller.identity_matches({**payload, "bridge_version": "old"})
    assert not controller.identity_matches({**payload, "owner_root": str(tmp_path / "other")})




def test_runtime_identity_files_are_race_safe(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    target = tmp_path / "runtime" / "install-id.txt"
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: module.ensure_secret_file(target, lambda: __import__("uuid").uuid4().hex), range(24)))
    assert len(set(values)) == 1
    assert target.read_text(encoding="utf-8").strip() == values[0]


def test_stop_script_never_kills_by_port():
    root = Path(__file__).resolve().parents[1]
    content = (root / "stop_eitaa_bridge.bat").read_text(encoding="utf-8").lower()
    assert "netstat" not in content
    assert "findstr \"listening\"" not in content
    assert "office_runtime.py\" stop" in content


def test_normal_setup_does_not_force_reinstall():
    root = Path(__file__).resolve().parents[1]
    content = (root / "setup_venv.bat").read_text(encoding="utf-8").lower()
    normal_section = content.split(":force_repair", 1)[0]
    assert "--force-reinstall" not in normal_section
    repair_section = content.split(":force_repair", 1)[1]
    assert "--force-reinstall" in repair_section


def test_edge_pid_handoff_uses_visible_owned_window(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = tmp_path / "app"
    root.mkdir()
    (root / "VERSION.txt").write_text("0.7.0-ui-mvp6.1.1-runtime3\n", encoding="utf-8")
    controller = module.RuntimeController(root, port=18766)
    controller._write_ui_state(111)
    monkeypatch.setattr(controller, "visible_owned_edge_pids", lambda: [222])
    assert controller.existing_owned_edge_pid() == 222
    state = module.read_json(controller.ui_state_file)
    assert state is not None
    assert state["edge_pid"] == 222


def test_office_runtime_does_not_end_when_initial_edge_pid_exits():
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts" / "office_runtime.py").read_text(encoding="utf-8")
    assert "while process_alive(edge_pid):" not in content
    assert "visible_owned_edge_pids" in content
    assert "Edge PID handoff" in content


def test_windows_process_query_uses_explicit_utf8(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    if os.name != "nt":
        return
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        payload = {
            "ProcessId": 7,
            "ExecutablePath": "msedge.exe",
            "CommandLine": "C:\\Users\\ExampleUser\\Documents\\Eitaa\\runtime\\edge-profile",
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    processes = module._windows_processes()
    assert processes is not None
    assert processes[0]["CommandLine"].endswith("ایتا\\runtime\\edge-profile")
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert "OutputEncoding" in captured["command"][-1]


def test_legacy_backend_rejects_prefix_sibling_path(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = (tmp_path / "EitaaBridge").resolve()
    sibling = root.with_name(root.name + "-Backup")
    sibling_config = sibling / "bridge.json"
    sibling_ui = sibling / "ui" / "dist"
    command = (
        f'python -m eitaa_bridge.interfaces.http_api --config "{sibling_config}" '
        f'--ui-root "{sibling_ui}"'
    )
    monkeypatch.setattr(module, "process_details", lambda _pid: {"ProcessId": 55, "CommandLine": command})
    assert not module.owned_backend_process(55, root, "owned-id", allow_legacy=True)


def test_legacy_backend_accepts_exact_absolute_root(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = (tmp_path / "EitaaBridge").resolve()
    root_config = root / "bridge.json"
    root_ui = root / "ui" / "dist"
    command = (
        f'python -m eitaa_bridge.interfaces.http_api --config "{root_config}" '
        f'--ui-root "{root_ui}"'
    )
    monkeypatch.setattr(module, "process_details", lambda _pid: {"ProcessId": 56, "CommandLine": command})
    assert module.owned_backend_process(56, root, "unused", allow_legacy=True)


def test_process_probe_error_is_not_treated_as_exit(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    if os.name == "nt":
        monkeypatch.setattr(module, "_windows_process_alive", lambda _pid: None)
        assert module.process_alive(99999)
    else:
        def denied(_pid, _signal):
            raise PermissionError("probe denied")

        monkeypatch.setattr(module.os, "kill", denied)
        assert module.process_alive(99999)


def test_office_installer_mirrors_managed_code_directories():
    root = Path(__file__).resolve().parents[1]
    content = (root / "installer" / "install_office_payload.cmd").read_text(encoding="utf-8").lower()
    assert "for %%d in (python python-packages dist vendor scripts docs ui)" in content
    assert 'robocopy "%tempstage%\\app\\%%d" "%target%\\%%d" /mir' in content
    assert "/xd python python-packages dist vendor scripts docs ui runtime backups data diagnostics" in content


def test_python_install_batches_force_utf8_for_unicode_paths():
    root = Path(__file__).resolve().parents[1]
    for name in ("install_app.bat", "setup_venv.bat", "build_wheel.bat", "BUILD_OFFICE_SETUP_EXE.bat"):
        content = (root / name).read_text(encoding="utf-8").lower()
        assert "chcp 65001" in content
        assert "pythonutf8=1" in content
        assert "pythonioencoding=utf-8" in content

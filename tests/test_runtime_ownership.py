from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

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


def test_source_runtime_version_matches_release_manifest():
    from eitaa_bridge.version import __version__

    root = Path(__file__).resolve().parents[1]
    assert _load_office_runtime(root).read_product_version(root) == __version__


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


def test_office_runtime_prefers_current_source_over_installed_package(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = tmp_path / "app"
    source_package = root / "src" / "eitaa_bridge"
    source_package.mkdir(parents=True)
    python = root / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    (root / "VERSION.txt").write_text("0.7.0-ui-mvp6.1.1-runtime3\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", "existing-packages")

    selected, environment = module.RuntimeController(root, port=18765).python_runtime()

    assert selected == python
    assert environment["PYTHONPATH"].split(os.pathsep) == [
        str(root / "src"),
        "existing-packages",
    ]


def test_electron_runtime_prefers_current_source_over_installed_package():
    root = Path(__file__).resolve().parents[1]
    content = (root / "ui" / "electron" / "main.cjs").read_text(encoding="utf-8")
    assert "function backendEnvironment(root)" in content
    assert "environment.PYTHONPATH = [sourcePackages, environment.PYTHONPATH]" in content
    assert "env: backendEnvironment(root)" in content


def test_electron_development_runtime_prefers_python_module_over_stale_entrypoint():
    root = Path(__file__).resolve().parents[1]
    content = (root / "ui" / "electron" / "main.cjs").read_text(encoding="utf-8")
    development_python = (
        "if (!app.isPackaged && fs.existsSync(python)) "
        "apiProcess = spawn(python, ['-m', "
        "'eitaa_bridge.interfaces.http_api', ...args], spawnOptions)"
    )
    packaged_entrypoint = (
        "else if (fs.existsSync(exe)) apiProcess = spawn(exe, args, spawnOptions)"
    )
    assert development_python in content
    assert packaged_entrypoint in content


def test_electron_expected_backend_version_comes_from_canonical_version_file():
    root = Path(__file__).resolve().parents[1]
    content = (root / "ui" / "electron" / "main.cjs").read_text(encoding="utf-8")
    assert "function expectedBridgeVersion(root = projectRoot())" in content
    assert "path.join(root, 'VERSION.txt')" in content
    assert "current?.bridge_version === expectedBridgeVersion()" in content
    assert "alive?.bridge_version === expectedBridgeVersion()" in content
    assert "const EXPECTED_BRIDGE_VERSION = '0.7.0-ui-mvp6.1.1-gmi4'" not in content


def test_office_runtime_derives_endpoint_from_desktop_deployment(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    module = _load_office_runtime(project_root)
    root = tmp_path / "portable-app"
    root.mkdir()
    (root / "bridge.json").write_text(
        json.dumps(
            {
                "deployment": {
                    "mode": "desktop_loopback",
                    "bind": {"host": "127.0.0.2", "port": 18767},
                }
            }
        ),
        encoding="utf-8",
    )
    controller = module.RuntimeController(root)
    assert controller.host == "127.0.0.2"
    assert controller.port == 18767
    assert controller.base_url == "http://127.0.0.2:18767"


def test_electron_endpoint_and_media_transport_are_config_driven():
    root = Path(__file__).resolve().parents[1]
    main = (root / "ui" / "electron" / "main.cjs").read_text(encoding="utf-8")
    app = ((root / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (root / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    csp = (root / "ui" / "index.html").read_text(encoding="utf-8")
    assert "function desktopEndpoint(root = projectRoot())" in main
    assert "const args = ['--config', 'bridge.json']" in main
    assert "'--host'" not in main
    assert "'--port'" not in main
    assert "eitaa-media://bridge" in app
    assert "LOCAL_MEDIA_BASE" not in app
    assert "eitaa-media:" in csp
    assert "http://127.0.0.1:8765" not in csp


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
    expected_command_line = (
        "C:\\Users\\کاربر\\Documents\\eitaa\\runtime\\edge-profile"
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        payload = {
            "ProcessId": 7,
            "ExecutablePath": "msedge.exe",
            "CommandLine": expected_command_line,
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    processes = module._windows_processes()
    assert processes is not None
    assert processes[0]["CommandLine"] == expected_command_line
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


def test_office_setup_is_self_contained_and_excludes_private_runtime_state():
    root = Path(__file__).resolve().parents[1]
    builder = (root / "BUILD_OFFICE_SETUP_EXE.bat").read_text(encoding="utf-8").lower()
    installer = (root / "installer" / "install_office_payload.cmd").read_text(
        encoding="utf-8"
    ).lower()

    assert "sys.base_prefix" in builder
    assert "build_wheel_stdlib.py" in builder
    assert "build_self_contained_setup.py" in builder
    assert "package_clean.py" in builder
    assert "python-packages" in builder
    assert "where node" not in builder
    assert "npm.cmd" not in builder
    assert "setup_ui.bat" not in builder
    assert "backup_runtime.py --output" not in builder
    assert "iexpress.exe" not in builder
    assert "transfer-backup.zip" not in installer
    assert 'if not exist "%target%\\data" mkdir "%target%\\data"' in installer
    assert 'if not exist "%target%\\diagnostics\\bundles" mkdir "%target%\\diagnostics\\bundles"' in installer


def test_office_setup_has_explicit_supported_windows_preflight():
    root = Path(__file__).resolve().parents[1]
    preflight = (root / "installer" / "check_windows_version.vbs").read_text(
        encoding="utf-8"
    ).lower()
    installer = (root / "installer" / "install_office_payload.cmd").read_text(
        encoding="utf-8"
    ).lower()
    sed_writer = (root / "scripts" / "write_iexpress_sed.py").read_text(
        encoding="utf-8"
    ).lower()

    assert "win32_operatingsystem" in preflight
    assert "windows 10 or newer" in preflight
    assert "64-bit" in preflight
    assert 'cscript.exe //nologo "%~dp0check_windows_version.vbs"' in installer
    assert "file2=check_windows_version.vbs" in sed_writer


def test_operator_batches_support_bundled_python_runtime():
    root = Path(__file__).resolve().parents[1]
    for name in ("backup_now.bat", "restore_backup.bat", "create_diagnostics.bat", "run_doctor.bat"):
        content = (root / name).read_text(encoding="utf-8").lower()
        assert 'if exist "python\\python.exe"' in content
        assert "python-packages" in content


def test_self_contained_setup_bootstrap_embeds_and_verifies_resources(tmp_path):
    if os.name != "nt":
        return
    from scripts.build_self_contained_setup import build_setup

    payload = tmp_path / "office_payload.zip"
    installer = tmp_path / "install_office_payload.cmd"
    preflight = tmp_path / "check_windows_version.vbs"
    icon = tmp_path / "EitaaBridge.ico"
    output = tmp_path / "EitaaBridge-Setup.exe"
    payload.write_bytes(b"synthetic-safe-payload")
    installer.write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
    preflight.write_text("WScript.Quit 0\r\n", encoding="ascii")
    _write_test_icon(icon)

    build_setup(
        payload=payload,
        installer=installer,
        preflight=preflight,
        icon=icon,
        output=output,
    )
    completed = subprocess.run(
        [str(output), "--verify-only"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0
    assert "resources verified" in completed.stdout.lower()

    source = (Path(__file__).resolve().parents[1] / "scripts" / "build_self_contained_setup.py").read_text(
        encoding="utf-8"
    )
    assert '"/target:winexe"' in source
    assert "System.Windows.Forms" in source
    assert "RightToLeftLayout = true" in source
    assert "نسخه اختصاصی Eitaa Bridge" in source
    assert '" /quiet\\\""' in source

    installer_content = (
        Path(__file__).resolve().parents[1] / "installer" / "install_office_payload.cmd"
    ).read_text(encoding="utf-8")
    assert 'if /I "%~1"=="/quiet"' in installer_content
    assert 'if "%NO_LAUNCH%"=="0" start' in installer_content


def _write_test_icon(path: Path) -> None:
    import struct

    width = 16
    height = 16
    xor_pixels = bytes((0x56, 0x34, 0x12, 0xFF)) * (width * height)
    and_mask = bytes(((width + 31) // 32) * 4 * height)
    bitmap = struct.pack(
        "<IIIHHIIIIII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(xor_pixels),
        0,
        0,
        0,
        0,
    ) + xor_pixels + and_mask
    header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack(
        "<BBBBHHII",
        width,
        height,
        0,
        0,
        1,
        32,
        len(bitmap),
        len(header) + 16,
    )
    path.write_bytes(header + directory + bitmap)


def test_branded_setup_rejects_missing_or_invalid_icon(tmp_path):
    from scripts.build_self_contained_setup import build_setup

    payload = tmp_path / "office_payload.zip"
    installer = tmp_path / "install_office_payload.cmd"
    preflight = tmp_path / "check_windows_version.vbs"
    output = tmp_path / "EitaaBridge-Setup.exe"
    payload.write_bytes(b"synthetic-safe-payload")
    installer.write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
    preflight.write_text("WScript.Quit 0\r\n", encoding="ascii")

    with pytest.raises(FileNotFoundError):
        build_setup(
            payload=payload,
            installer=installer,
            preflight=preflight,
            icon=tmp_path / "missing.ico",
            output=output,
        )

    invalid_icon = tmp_path / "invalid.ico"
    invalid_icon.write_bytes(b"not-an-icon")
    with pytest.raises(ValueError, match="Windows icon"):
        build_setup(
            payload=payload,
            installer=installer,
            preflight=preflight,
            icon=invalid_icon,
            output=output,
        )


def test_office_release_branding_and_signing_are_explicit_and_fail_closed():
    root = Path(__file__).resolve().parents[1]
    builder = (root / "BUILD_OFFICE_SETUP_EXE.bat").read_text(encoding="utf-8").lower()
    installer = (root / "installer" / "install_office_payload.cmd").read_text(
        encoding="utf-8"
    ).lower()
    shortcut_script = (root / "scripts" / "create_shortcuts.ps1").read_text(
        encoding="utf-8"
    ).lower()

    assert 'installer\\assets\\eitaabridge.ico' in builder
    assert '--icon "%setupicon%"' in builder
    assert 'copy /y "%setupicon%" "%app%\\assets\\eitaabridge.ico"' in builder
    assert 'sign_windows_release.ps1' in builder
    assert 'verify_windows_release_signature.ps1' in builder
    assert builder.index('sign_windows_release.ps1') < builder.index('verify_windows_release_signature.ps1')
    assert "iconlocation='%target%\\assets\\eitaabridge.ico,0'" in installer
    assert "assets\\eitaabridge.ico" in shortcut_script


def test_new_office_build_archives_previous_release_without_deleting_unrelated_files(tmp_path):
    if os.name != "nt":
        return

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "archive_previous_office_release.ps1"
    old_setup = tmp_path / "EitaaBridge-0.8.0-rc4-Activated-InternalSigned-GuiSetup-x64.exe"
    old_portable = tmp_path / "EitaaBridge-0.8.0-rc3-Activated-SelfContained-Portable.zip"
    old_hash = tmp_path / f"{old_setup.name}.sha256.txt"
    unrelated = tmp_path / "operator-note.txt"
    old_setup.write_bytes(b"previous-setup")
    old_portable.write_bytes(b"previous-portable")
    old_hash.write_text("hash", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ReleaseDirectory",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    archived_runs = [item for item in (tmp_path / "archive").iterdir() if item.is_dir()]
    assert len(archived_runs) == 1
    archived = archived_runs[0]
    assert (archived / old_setup.name).read_bytes() == b"previous-setup"
    assert (archived / old_portable.name).read_bytes() == b"previous-portable"
    assert (archived / old_hash.name).is_file()
    manifest = json.loads((archived / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8-sig"))
    assert manifest["format"] == "eitaa-bridge-office-release-archive-v1"
    assert len(manifest["artifacts"]) == 3
    assert unrelated.read_text(encoding="utf-8") == "keep"

    builder = (root / "BUILD_OFFICE_SETUP_EXE.bat").read_text(encoding="utf-8").lower()
    assert "archive_previous_office_release.ps1" in builder
    assert "0.8.0-rc6a-authchildrpc" in builder


def test_checked_in_windows_icon_is_multiresolution_and_source_is_rgba_png():
    import struct

    root = Path(__file__).resolve().parents[1]
    source = root / "installer" / "assets" / "EitaaBridge-source.png"
    icon = root / "installer" / "assets" / "EitaaBridge.ico"

    source_bytes = source.read_bytes()
    assert source_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", source_bytes[16:26])
    assert width == height
    assert width >= 512
    assert bit_depth == 8
    assert color_type == 6

    icon_bytes = icon.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", icon_bytes)
    assert (reserved, image_type, count) == (0, 1, 9)
    expected_sizes = {16, 20, 24, 32, 40, 48, 64, 128, 256}
    actual_sizes: set[int] = set()
    table_end = 6 + 16 * count
    for index in range(count):
        entry_offset = 6 + 16 * index
        width_byte, height_byte = struct.unpack_from("<BB", icon_bytes, entry_offset)
        frame_width = 256 if width_byte == 0 else width_byte
        frame_height = 256 if height_byte == 0 else height_byte
        planes, bits_per_pixel, frame_size, frame_offset = struct.unpack_from(
            "<HHII", icon_bytes, entry_offset + 4
        )
        assert frame_width == frame_height
        assert planes == 1
        assert bits_per_pixel == 32
        assert frame_offset >= table_end
        assert frame_offset + frame_size <= len(icon_bytes)
        assert icon_bytes[frame_offset : frame_offset + 8] == b"\x89PNG\r\n\x1a\n"
        actual_sizes.add(frame_width)
    assert actual_sizes == expected_sizes

    converter = (root / "scripts" / "build_windows_icon.ps1").read_text(
        encoding="utf-8"
    ).lower()
    assert "16, 20, 24, 32, 40, 48, 64, 128, 256" in converter
    assert "highqualitybicubic" in converter
    assert "sourcecopy" in converter


def test_internal_code_signing_keeps_private_key_outside_project_and_pins_trust():
    root = Path(__file__).resolve().parents[1]
    certificate_path = root / "scripts" / "new_internal_code_signing_certificate.ps1"
    certificate_bytes = certificate_path.read_bytes()
    certificate_script = certificate_bytes.decode("utf-8-sig").lower()
    signing_script = (root / "scripts" / "sign_windows_release.ps1").read_text(
        encoding="utf-8"
    ).lower()
    verification_script = (
        root / "scripts" / "verify_windows_release_signature.ps1"
    ).read_text(encoding="utf-8").lower()

    assert "cert:\\currentuser\\my" in certificate_script
    assert "nonexportable" in certificate_script
    assert "1.3.6.1.5.5.7.3.3" in certificate_script
    assert "export-certificate" in certificate_script
    assert "export-pfxcertificate" not in certificate_script
    assert "trustedpublisher" in certificate_script
    assert "expectedthumbprint" in certificate_script
    assert "$pshome" in signing_script
    assert "microsoft.powershell.security" in signing_script
    assert "microsoft.powershell.utility" in signing_script
    assert "$pshome" in verification_script
    assert "microsoft.powershell.security" in verification_script
    assert "microsoft.powershell.utility" in verification_script
    assert certificate_bytes.startswith(b"\xef\xbb\xbf")
    assert "__thumbprint__" in certificate_script
    assert "__cer_sha256__" in certificate_script
    assert "__not_after__" in certificate_script
    assert "utf8encoding]::new($true)" in certificate_script
    assert "`$thumbprint`" not in certificate_script
    assert "`$certificatehash`" not in certificate_script
    assert "set-authenticodesignature" in signing_script
    assert "sha256" in signing_script
    assert "thumbprint" in signing_script


def test_office_payload_privacy_scanner_rejects_private_key_material(tmp_path):
    root = Path(__file__).resolve().parents[1]
    scanner = root / "scripts" / "check_office_payload_privacy.py"
    payload = tmp_path / "payload"
    payload.mkdir()
    safe_file = payload / "application.txt"
    safe_file.write_text("public application material", encoding="utf-8")

    clean = subprocess.run(
        [sys.executable, str(scanner), "--root", str(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0
    assert json.loads(clean.stdout)["private_key_pem_findings"] == 0

    safe_file.write_text(
        "-----BEGIN " + "PRIVATE KEY-----\n"
        + ("A" * 80)
        + "\n-----END "
        + "PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    rejected = subprocess.run(
        [sys.executable, str(scanner), "--root", str(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["private_key_pem_findings"] == 1


def test_python_install_batches_force_utf8_for_unicode_paths():
    root = Path(__file__).resolve().parents[1]
    for name in ("install_app.bat", "setup_venv.bat", "build_wheel.bat", "BUILD_OFFICE_SETUP_EXE.bat"):
        content = (root / name).read_text(encoding="utf-8").lower()
        assert "chcp 65001" in content
        assert "pythonutf8=1" in content
        assert "pythonioencoding=utf-8" in content

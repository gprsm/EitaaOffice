from __future__ import annotations

import argparse
import ctypes
import hashlib
import ipaddress
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RUNTIME_PROTOCOL = "1"
API_VERSION = "v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
HEARTBEAT_INTERVAL_SECONDS = 2.0
HEARTBEAT_TIMEOUT_SECONDS = 30.0


class RuntimeConflict(RuntimeError):
    pass


class RuntimeFailure(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_path(path: Path | str) -> str:
    value = str(Path(path).expanduser().resolve())
    return os.path.normcase(os.path.normpath(value))


def read_product_version(root: Path) -> str:
    version_file = root / "VERSION.txt"
    if not version_file.is_file():
        return "unknown"
    for line in version_file.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped and "=" not in stripped:
            return stripped
    return "unknown"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def desktop_deployment_bind(root: Path) -> tuple[str, int]:
    """Resolve the desktop endpoint from installation Config without reading secrets."""

    config_path = root / "bridge.json"
    if not config_path.is_file():
        return DEFAULT_HOST, DEFAULT_PORT
    payload = read_json(config_path)
    if payload is None:
        raise RuntimeFailure("Desktop deployment configuration could not be read safely.")
    selected = payload.get("deployment")
    if selected is None:
        return DEFAULT_HOST, DEFAULT_PORT
    if not isinstance(selected, dict) or selected.get("mode") != "desktop_loopback":
        raise RuntimeFailure("The Office launcher requires desktop_loopback deployment mode.")
    bind = selected.get("bind")
    if not isinstance(bind, dict):
        raise RuntimeFailure("Desktop deployment bind configuration is incomplete.")
    host = str(bind.get("host") or "").strip().lower()
    port = bind.get("port")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise RuntimeFailure("Desktop deployment bind host is invalid.") from exc
    if not address.is_loopback:
        raise RuntimeFailure("Desktop deployment must remain on Loopback.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeFailure("Desktop deployment bind port is invalid.")
    return address.compressed, port


def ensure_secret_file(path: Path, factory) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        try:
            current = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            current = ""
        except OSError:
            current = ""
        if current:
            return current
        value = str(factory())
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            time.sleep(0.025)
            continue
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(value + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return value
    raise RuntimeFailure(f"Could not create or read runtime identity file: {path.name}")


def rotate_log(path: Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 3) -> None:
    try:
        if not path.is_file() or path.stat().st_size < max_bytes:
            return
        for index in range(backups - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            target = path.with_name(f"{path.name}.{index + 1}")
            if source.exists():
                source.replace(target)
        path.replace(path.with_name(f"{path.name}.1"))
    except OSError:
        pass


def append_launcher_log(root: Path, message: str) -> None:
    log = root / "runtime" / "logs" / "launcher.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(log)
    try:
        with log.open("a", encoding="utf-8") as stream:
            stream.write(f"{utc_now()} {message}\n")
    except OSError:
        pass


def show_message(title: str, message: str, *, error: bool = False) -> None:
    if os.name == "nt":
        flags = 0x10 if error else 0x40
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, flags)
            return
        except Exception:
            pass
    stream = sys.stderr if error else sys.stdout
    print(f"{title}: {message}", file=stream)


def _windows_process_alive(pid: int) -> bool | None:
    try:
        kernel32 = ctypes.windll.kernel32
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        open_process.restype = ctypes.c_void_p
        handle = open_process(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not handle:
            error = int(kernel32.GetLastError())
            if error in {87, 1168}:  # invalid PID / not found
                return False
            return None
        try:
            wait_result = int(kernel32.WaitForSingleObject(handle, 0))
            if wait_result == 0x00000102:  # WAIT_TIMEOUT: still running
                return True
            if wait_result == 0x00000000:  # WAIT_OBJECT_0: exited
                return False
            return None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        result = _windows_process_alive(pid)
        return True if result is None else result
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        # A failed access/probe is not proof that the process exited. Treat an
        # indeterminate result as alive so installers never race a live runtime.
        return True
    return True


def _windows_processes() -> list[dict[str, Any]] | None:
    if os.name != "nt":
        return []
    command = (
        "$utf8=New-Object System.Text.UTF8Encoding($false);"
        "[Console]::OutputEncoding=$utf8;"
        "$OutputEncoding=$utf8;"
        "$ErrorActionPreference='SilentlyContinue';"
        "$p=Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath,CommandLine;"
        "$p | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            return None
        if not completed.stdout.strip():
            return []
        payload = json.loads(completed.stdout)
        if isinstance(payload, dict):
            return [payload]
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
    except (OSError, UnicodeError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def process_details(pid: int) -> dict[str, Any] | None:
    if os.name == "nt":
        processes = _windows_processes()
        if processes is None:
            return None
        for item in processes:
            try:
                if int(item.get("ProcessId") or 0) == pid:
                    return item
            except (TypeError, ValueError):
                continue
        return None
    proc = Path("/proc") / str(pid)
    try:
        command_line = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        executable = os.readlink(proc / "exe")
    except OSError:
        return None
    return {"ProcessId": pid, "ExecutablePath": executable, "CommandLine": command_line}


def find_process_by_markers(*markers: str) -> int | None:
    normalized_markers = [marker.casefold() for marker in markers if marker]
    if not normalized_markers:
        return None
    if os.name == "nt":
        candidates = _windows_processes() or []
    else:
        candidates = []
        for child in Path("/proc").iterdir():
            if child.name.isdigit():
                detail = process_details(int(child.name))
                if detail:
                    candidates.append(detail)
    for item in candidates:
        command_line = str(item.get("CommandLine") or "").casefold()
        if all(marker in command_line for marker in normalized_markers):
            try:
                return int(item.get("ProcessId") or 0) or None
            except (TypeError, ValueError):
                continue
    return None


def command_line_arguments(command_line: str) -> list[str]:
    if not command_line:
        return []
    if os.name != "nt":
        try:
            return shlex.split(command_line)
        except ValueError:
            return []
    try:
        from ctypes import wintypes

        argc = ctypes.c_int()
        parser = ctypes.windll.shell32.CommandLineToArgvW
        parser.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        parser.restype = ctypes.POINTER(wintypes.LPWSTR)
        argv = parser(command_line, ctypes.byref(argc))
        if not argv:
            return []
        try:
            return [argv[index] for index in range(argc.value)]
        finally:
            local_free = ctypes.windll.kernel32.LocalFree
            local_free.argtypes = [ctypes.c_void_p]
            local_free.restype = ctypes.c_void_p
            local_free(argv)
    except Exception:
        return []


def _argument_value(arguments: list[str], flag: str) -> str | None:
    wanted = flag.casefold()
    for index, argument in enumerate(arguments[:-1]):
        if argument.casefold() == wanted:
            return arguments[index + 1]
    return None


def _absolute_argument_matches(arguments: list[str], flag: str, expected: Path) -> bool:
    value = _argument_value(arguments, flag)
    if not value or not Path(value).is_absolute():
        return False
    try:
        return canonical_path(value) == canonical_path(expected)
    except OSError:
        return False


def _owned_backend_details(
    detail: dict[str, Any],
    root: Path,
    install_id: str,
    *,
    allow_legacy: bool,
) -> bool:
    arguments = command_line_arguments(str(detail.get("CommandLine") or ""))
    module = "eitaa_bridge.interfaces.http_api"
    if not any(
        arguments[index] == "-m" and arguments[index + 1].casefold() == module
        for index in range(len(arguments) - 1)
    ):
        return False

    owner_root_matches = _absolute_argument_matches(arguments, "--runtime-owner-root", root)
    command_install_id = _argument_value(arguments, "--runtime-install-id")
    if owner_root_matches and command_install_id == install_id:
        return True
    if not allow_legacy:
        return False

    # Legacy launchers used absolute config/UI paths. Requiring an exact
    # canonical argument prevents C:\\App from matching C:\\App-Backup.
    return _absolute_argument_matches(arguments, "--config", root / "bridge.json") or _absolute_argument_matches(
        arguments, "--ui-root", root / "ui" / "dist"
    )


def owned_backend_process(pid: int, root: Path, install_id: str, *, allow_legacy: bool = False) -> bool:
    detail = process_details(pid)
    if not detail:
        return False
    return _owned_backend_details(detail, root, install_id, allow_legacy=allow_legacy)


def find_owned_backend_process(root: Path, install_id: str, *, allow_legacy: bool) -> int | None:
    if os.name == "nt":
        candidates = _windows_processes()
        if candidates is None:
            raise RuntimeFailure("Windows process ownership could not be inspected safely.")
    else:
        candidates = []
        for child in Path("/proc").iterdir():
            if child.name.isdigit():
                detail = process_details(int(child.name))
                if detail:
                    candidates.append(detail)
    for detail in candidates:
        if not _owned_backend_details(detail, root, install_id, allow_legacy=allow_legacy):
            continue
        try:
            pid = int(detail.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            return pid
    return None


def _normalized_command_line(value: str) -> str:
    return value.replace("/", "\\").casefold()


def owned_edge_processes(edge_profile: Path) -> list[dict[str, Any]] | None:
    """Return only Edge processes proven to use this installation's private profile."""
    if os.name != "nt":
        return []
    profile = _normalized_command_line(canonical_path(edge_profile))
    owned: list[dict[str, Any]] = []
    processes = _windows_processes()
    if processes is None:
        return None
    for item in processes:
        command_line = _normalized_command_line(str(item.get("CommandLine") or ""))
        executable = str(item.get("ExecutablePath") or "").casefold()
        if profile not in command_line:
            continue
        if "msedge" not in executable and "msedge" not in command_line:
            continue
        try:
            pid = int(item.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            owned.append({**item, "ProcessId": pid})
    return owned


def visible_window_pids(candidates: set[int]) -> list[int] | None:
    if os.name != "nt" or not candidates:
        return []
    visible: list[int] = []
    try:
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            pid = int(process_id.value)
            if pid in candidates and pid not in visible:
                visible.append(pid)
            return True

        user32.EnumWindows(callback_type(callback), 0)
    except Exception:
        return None
    return visible


def owned_edge_process(pid: int, edge_profile: Path) -> bool:
    processes = owned_edge_processes(edge_profile)
    return bool(processes) and any(int(item.get("ProcessId") or 0) == pid for item in processes)


def terminate_process(pid: int, *, force_after: float = 4.0) -> bool:
    if not process_alive(pid):
        return True
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return True
    deadline = time.monotonic() + force_after
    while time.monotonic() < deadline:
        if not process_alive(pid):
            return True
        time.sleep(0.15)
    if os.name == "nt":
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    time.sleep(0.2)
    return not process_alive(pid)


@contextmanager
def instance_lock(path: Path, *, blocking: bool) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            try:
                msvcrt.locking(handle.fileno(), mode, 1)
                acquired = True
            except OSError:
                acquired = False
        else:
            import fcntl

            flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            try:
                fcntl.flock(handle.fileno(), flags)
                acquired = True
            except OSError:
                acquired = False
        yield acquired
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 2.0,
) -> tuple[int | None, dict[str, Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Eitaa-Runtime-Token"] = token
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            body = json.loads(raw.decode("utf-8")) if raw else {}
            return int(response.status), body if isinstance(body, dict) else None
    except HTTPError as exc:
        try:
            raw = exc.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            body = None
        return int(exc.code), body if isinstance(body, dict) else None
    except (URLError, TimeoutError, OSError):
        return None, None


class RuntimeController:
    def __init__(
        self,
        root: Path,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.root = root.expanduser().resolve()
        configured_host, configured_port = desktop_deployment_bind(self.root)
        if host is not None and host != configured_host:
            raise RuntimeFailure("Office host override does not match deployment Config.")
        if port is not None and port != configured_port and (self.root / "bridge.json").is_file():
            raise RuntimeFailure("Office port override does not match deployment Config.")
        self.host = host or configured_host
        self.port = port or configured_port
        selected_address = ipaddress.ip_address(self.host)
        rendered_host = (
            f"[{selected_address.compressed}]"
            if selected_address.version == 6
            else selected_address.compressed
        )
        self.base_url = f"http://{rendered_host}:{self.port}"
        self.runtime = self.root / "runtime"
        self.logs = self.runtime / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.install_id_file = self.runtime / "install-id.txt"
        self.owner_token_file = self.runtime / "backend-owner.token"
        self.backend_state_file = self.runtime / "backend-state.json"
        self.ui_state_file = self.runtime / "ui-state.json"
        self.lock_file = self.runtime / "office-launcher.lock"
        self.edge_profile = self.runtime / "edge-profile"
        self.install_id = ensure_secret_file(self.install_id_file, lambda: uuid.uuid4().hex)
        self.owner_token = ensure_secret_file(self.owner_token_file, lambda: secrets.token_urlsafe(32))
        self.expected_bridge_version = read_product_version(self.root)
        self.backend_process: subprocess.Popen[bytes] | None = None
        self.backend_log_handle = None

    def identity(self, timeout: float = 1.5) -> tuple[int | None, dict[str, Any] | None]:
        return http_json(
            "GET",
            self.base_url + "/api/v1/runtime/identity",
            token=self.owner_token,
            timeout=timeout,
        )

    def identity_matches(self, payload: dict[str, Any] | None) -> bool:
        if not payload:
            return False
        return (
            payload.get("ok") is True
            and str(payload.get("runtime_protocol")) == RUNTIME_PROTOCOL
            and str(payload.get("api_version")) == API_VERSION
            and str(payload.get("bridge_version")) == self.expected_bridge_version
            and str(payload.get("install_id")) == self.install_id
            and canonical_path(str(payload.get("owner_root") or "")) == canonical_path(self.root)
        )

    def ensure_no_foreign_service(self) -> dict[str, Any] | None:
        status, payload = self.identity()
        if status is None:
            return None
        if status == 200 and self.identity_matches(payload):
            return payload
        bridge = payload.get("bridge_version") if payload else "unknown"
        raise RuntimeConflict(
            f"Port {self.port} is already used by a service that is not owned by this installation "
            f"(reported bridge version: {bridge}). No process was stopped."
        )

    def python_runtime(self) -> tuple[Path, dict[str, str]]:
        candidates = [
            self.root / "python" / "python.exe",
            self.root / ".venv" / "Scripts" / "python.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                environment = os.environ.copy()
                search_paths: list[str] = []
                source_packages = self.root / "src"
                if (source_packages / "eitaa_bridge").is_dir():
                    search_paths.append(str(source_packages))
                if candidate == candidates[0]:
                    packages = self.root / "python-packages"
                    search_paths.append(str(packages))
                existing = environment.get("PYTHONPATH", "")
                if existing:
                    search_paths.append(existing)
                if search_paths:
                    environment["PYTHONPATH"] = os.pathsep.join(search_paths)
                return candidate, environment
        raise RuntimeFailure("Backend Python runtime was not found. Run install_app.bat first.")

    def start_backend(self) -> None:
        python, environment = self.python_runtime()
        log = self.logs / "server-console.log"
        rotate_log(log)
        self.backend_log_handle = log.open("ab", buffering=0)
        command = [
            str(python),
            "-m",
            "eitaa_bridge.interfaces.http_api",
            "--config",
            str(self.root / "bridge.json"),
            "--ui-root",
            str(self.root / "ui" / "dist"),
            "--runtime-install-id",
            self.install_id,
            "--runtime-owner-root",
            str(self.root),
            "--runtime-state-file",
            str(self.backend_state_file),
            "--runtime-heartbeat-timeout",
            str(HEARTBEAT_TIMEOUT_SECONDS),
        ]
        environment["EITAA_BRIDGE_RUNTIME_OWNER_TOKEN"] = self.owner_token
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.backend_process = subprocess.Popen(
            command,
            cwd=self.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=self.backend_log_handle,
            stderr=self.backend_log_handle,
            creationflags=flags,
        )
        append_launcher_log(self.root, f"backend spawn pid={self.backend_process.pid}")

    def wait_for_backend(self, attempts: int = 80) -> dict[str, Any]:
        for _ in range(attempts):
            if self.backend_process is not None and self.backend_process.poll() is not None:
                raise RuntimeFailure("The owned backend exited during startup. Check runtime\\logs\\server-console.log.")
            status, payload = self.identity(timeout=1.0)
            if status == 200 and self.identity_matches(payload):
                return payload or {}
            if status is not None and status != 200:
                raise RuntimeConflict("A non-owned service responded while the backend was starting. No process was stopped.")
            time.sleep(0.25)
        raise RuntimeFailure("The owned backend did not become ready. Check runtime\\logs\\server-console.log.")

    def ensure_backend(self) -> dict[str, Any]:
        existing = self.ensure_no_foreign_service()
        if existing is not None:
            append_launcher_log(self.root, f"reusing owned backend pid={existing.get('pid', 'unknown')}")
            return existing
        self.start_backend()
        return self.wait_for_backend()

    def heartbeat(self) -> bool:
        status, payload = http_json(
            "POST",
            self.base_url + "/api/v1/runtime/heartbeat",
            token=self.owner_token,
            payload={"install_id": self.install_id},
            timeout=2.0,
        )
        return status == 200 and bool(payload and payload.get("ok"))

    def controlled_shutdown(self) -> bool:
        status, payload = self.identity(timeout=1.5)
        if status is None:
            return False
        if status != 200 or not self.identity_matches(payload):
            return False
        response_status, _ = http_json(
            "POST",
            self.base_url + "/api/v1/runtime/shutdown",
            token=self.owner_token,
            payload={"install_id": self.install_id},
            timeout=2.0,
        )
        if response_status not in {200, 202}:
            return False
        pid = int((payload or {}).get("pid") or 0)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            current_status, current_identity = self.identity(timeout=0.6)
            endpoint_is_owned = current_status == 200 and self.identity_matches(current_identity)
            state = read_json(self.backend_state_file)
            try:
                state_pid = int((state or {}).get("pid") or 0)
            except (TypeError, ValueError):
                state_pid = 0
            state_is_owned = state_pid == pid and pid > 0
            child_exited = self.backend_process is not None and self.backend_process.poll() is not None
            if not endpoint_is_owned and (not state_is_owned or child_exited or not process_alive(pid)):
                return True
            time.sleep(0.2)
        return False

    def verify_and_stop_owned_backend(self, *, allow_legacy: bool) -> bool:
        if self.controlled_shutdown():
            return True
        state = read_json(self.backend_state_file) or {}
        try:
            pid = int(state.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid and process_alive(pid):
            if not owned_backend_process(pid, self.root, self.install_id, allow_legacy=allow_legacy):
                raise RuntimeConflict("A backend PID was recorded, but its command line does not prove ownership. It was not stopped.")
            append_launcher_log(self.root, f"terminating verified owned backend pid={pid}")
            return terminate_process(pid)
        if allow_legacy:
            legacy_pid = find_owned_backend_process(self.root, self.install_id, allow_legacy=True)
            if legacy_pid:
                append_launcher_log(self.root, f"terminating verified legacy backend pid={legacy_pid}")
                return terminate_process(legacy_pid)
        return True

    def close_owned_ui(self) -> None:
        pids = self.owned_edge_pids()
        if pids is None:
            append_launcher_log(self.root, "Edge process query unavailable; no UI process was stopped")
            return
        for pid in pids:
            if process_alive(pid) and owned_edge_process(pid, self.edge_profile):
                append_launcher_log(self.root, f"closing verified owned edge pid={pid}")
                terminate_process(pid, force_after=3.0)

    def stop(self, *, allow_legacy: bool) -> bool:
        self.close_owned_ui()
        result = self.verify_and_stop_owned_backend(allow_legacy=allow_legacy)
        if result:
            for path in (self.backend_state_file, self.ui_state_file):
                try:
                    path.unlink()
                except OSError:
                    pass
        return result

    def locate_edge(self) -> Path | None:
        if os.name != "nt":
            return None
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def owned_edge_pids(self) -> list[int] | None:
        processes = owned_edge_processes(self.edge_profile)
        if processes is None:
            return None
        return sorted({int(item.get("ProcessId") or 0) for item in processes if int(item.get("ProcessId") or 0) > 0})

    def visible_owned_edge_pids(self) -> list[int] | None:
        pids = self.owned_edge_pids()
        if pids is None:
            return None
        return visible_window_pids(set(pids))

    def _write_ui_state(self, edge_pid: int) -> None:
        atomic_write_json(
            self.ui_state_file,
            {
                "format": "eitaa-bridge-ui-owner-v1",
                "install_id": self.install_id,
                "owner_root": str(self.root),
                "launcher_pid": os.getpid(),
                "edge_pid": edge_pid,
                "edge_profile": str(self.edge_profile),
                "bridge_version": self.expected_bridge_version,
                "started_at": utc_now(),
            },
        )

    def existing_owned_edge_pid(self) -> int | None:
        state = read_json(self.ui_state_file) or {}
        if str(state.get("install_id") or "") != self.install_id:
            return None
        if canonical_path(str(state.get("owner_root") or "")) != canonical_path(self.root):
            return None
        try:
            preferred = int(state.get("edge_pid") or 0)
        except (TypeError, ValueError):
            preferred = 0
        visible = self.visible_owned_edge_pids()
        if visible is None:
            append_launcher_log(self.root, "Edge visibility query unavailable while adopting existing UI")
            return preferred if preferred and process_alive(preferred) else None
        if preferred in visible:
            return preferred
        if visible:
            replacement = visible[0]
            self._write_ui_state(replacement)
            append_launcher_log(self.root, f"adopted Edge PID handoff old={preferred or 'none'} new={replacement}")
            return replacement
        return None

    def launch_edge(self) -> int:
        edge = self.locate_edge()
        if edge is None:
            raise RuntimeFailure("Microsoft Edge was not found. The lightweight Office launcher requires Edge on Windows 10/11.")
        self.edge_profile.mkdir(parents=True, exist_ok=True)
        command = [
            str(edge),
            f"--app={self.base_url}/",
            "--start-maximized",
            f"--user-data-dir={self.edge_profile}",
            "--disable-background-mode",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        process = subprocess.Popen(command, cwd=self.root)
        launch_pid = process.pid
        deadline = time.monotonic() + 15.0
        pid = 0
        successful_observations = 0
        while time.monotonic() < deadline:
            visible = self.visible_owned_edge_pids()
            if visible is None:
                time.sleep(0.2)
                continue
            successful_observations += 1
            if visible:
                pid = launch_pid if launch_pid in visible else visible[0]
                break
            time.sleep(0.2)
        if not pid:
            if successful_observations == 0:
                pid = launch_pid
                append_launcher_log(
                    self.root,
                    f"Edge visibility query unavailable; preserving backend with launch_pid={launch_pid}",
                )
            else:
                raise RuntimeFailure("Microsoft Edge did not create a visible owned application window.")
        self._write_ui_state(pid)
        append_launcher_log(self.root, f"edge app started launch_pid={launch_pid} visible_pid={pid}")
        return pid

    def run_office(self) -> int:
        with instance_lock(self.lock_file, blocking=False) as acquired:
            if not acquired:
                self.focus_existing_ui()
                return 0
            try:
                identity = self.ensure_backend()
                append_launcher_log(self.root, f"backend ready pid={identity.get('pid', 'unknown')}")
                if not self.heartbeat():
                    raise RuntimeFailure("The owned backend rejected its initial UI heartbeat.")
                edge_pid = self.existing_owned_edge_pid()
                if edge_pid is not None:
                    append_launcher_log(self.root, f"adopting existing owned edge pid={edge_pid}")
                    self.focus_existing_ui()
                else:
                    edge_pid = self.launch_edge()
                missed = 0
                missing_window_checks = 0
                observation_failures = 0
                while True:
                    visible = self.visible_owned_edge_pids()
                    if visible is None:
                        observation_failures += 1
                        if observation_failures == 1 or observation_failures % 15 == 0:
                            append_launcher_log(
                                self.root,
                                f"Edge visibility query unavailable count={observation_failures}; backend preserved",
                            )
                    elif visible:
                        observation_failures = 0
                        missing_window_checks = 0
                        replacement = edge_pid if edge_pid in visible else visible[0]
                        if replacement != edge_pid:
                            append_launcher_log(self.root, f"Edge PID handoff old={edge_pid} new={replacement}")
                            edge_pid = replacement
                            self._write_ui_state(edge_pid)
                    else:
                        observation_failures = 0
                        missing_window_checks += 1
                        append_launcher_log(self.root, f"owned Edge window missing count={missing_window_checks}")
                        if missing_window_checks >= 3:
                            break
                    if self.heartbeat():
                        missed = 0
                    else:
                        missed += 1
                        append_launcher_log(self.root, f"heartbeat failed count={missed}")
                        if missed >= 3:
                            show_message(
                                "Eitaa Bridge",
                                "The owned local service stopped responding. Check runtime\\logs before restarting.",
                                error=True,
                            )
                            break
                    time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            finally:
                try:
                    self.controlled_shutdown()
                except Exception:
                    pass
                if self.backend_log_handle is not None:
                    try:
                        self.backend_log_handle.close()
                    except OSError:
                        pass
                try:
                    self.ui_state_file.unlink()
                except OSError:
                    pass
                append_launcher_log(self.root, "office launcher exited")
        return 0

    def focus_existing_ui(self) -> None:
        visible = self.visible_owned_edge_pids()
        pids = set(visible or [])
        if visible is None:
            state = read_json(self.ui_state_file) or {}
            try:
                fallback_pid = int(state.get("edge_pid") or 0)
            except (TypeError, ValueError):
                fallback_pid = 0
            if fallback_pid:
                pids.add(fallback_pid)
        if os.name == "nt" and pids:
            try:
                user32 = ctypes.windll.user32
                windows: list[int] = []
                callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

                def callback(hwnd, _lparam):
                    process_id = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
                    if int(process_id.value) in pids and user32.IsWindowVisible(hwnd):
                        windows.append(hwnd)
                    return True

                user32.EnumWindows(callback_type(callback), 0)
                if windows:
                    user32.ShowWindow(windows[0], 9)
                    user32.SetForegroundWindow(windows[0])
                    return
            except Exception:
                pass
        append_launcher_log(self.root, "second launch detected; existing window could not be focused")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Own and control the lightweight Eitaa Bridge Office runtime.")
    parser.add_argument("action", choices=["launch", "stop", "prepare-install", "status"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--allow-legacy-owned", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = RuntimeController(args.root, host=args.host, port=args.port)
    try:
        if args.action == "launch":
            return controller.run_office()
        if args.action in {"stop", "prepare-install"}:
            stopped = controller.stop(allow_legacy=args.allow_legacy_owned)
            if not stopped:
                raise RuntimeFailure("The owned runtime did not stop cleanly.")
            if not args.quiet:
                print("Owned Eitaa Bridge runtime stopped.")
            return 0
        status, payload = controller.identity()
        result = {
            "ok": status == 200 and controller.identity_matches(payload),
            "http_status": status,
            "identity": payload,
            "expected": {
                "runtime_protocol": RUNTIME_PROTOCOL,
                "api_version": API_VERSION,
                "bridge_version": controller.expected_bridge_version,
                "install_id": controller.install_id,
                "owner_root_sha256": hashlib.sha256(canonical_path(controller.root).encode("utf-8")).hexdigest(),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except RuntimeConflict as exc:
        append_launcher_log(controller.root, f"runtime conflict: {exc}")
        if not args.quiet:
            show_message("Eitaa Bridge Runtime Conflict", str(exc), error=True)
        return 3
    except RuntimeFailure as exc:
        append_launcher_log(controller.root, f"runtime failure: {exc}")
        if not args.quiet:
            show_message("Eitaa Bridge", str(exc), error=True)
        return 1
    except Exception as exc:
        append_launcher_log(controller.root, f"unexpected runtime error type={type(exc).__name__}")
        if not args.quiet:
            show_message("Eitaa Bridge", f"Unexpected runtime error: {type(exc).__name__}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Eitaa Bridge persistent background server controller.

Manages running the HTTP API service in the background independently of
any desktop UI window, suitable for reverse-proxy setups (e.g. Apache in Laragon)
and Windows Startup.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
HEALTH_PATH = "/api/v1/health"
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3


def get_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_paths(root: Path | None = None) -> dict[str, Path]:
    r = root or get_root()
    runtime = r / "runtime"
    logs = runtime / "logs"
    return {
        "root": r,
        "runtime": runtime,
        "logs": logs,
        "pid_file": runtime / "background-server.pid",
        "log_file": logs / "background-server.log",
        "bridge_config": r / "bridge.json",
        "ui_root": r / "ui" / "dist",
        "src": r / "src",
        "vbs_launcher": r / "EitaaBridgeBackground.vbs",
    }


def find_python(root: Path) -> Path:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / "python" / "python.exe",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return Path(sys.executable).resolve()


def query_health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0) -> dict[str, Any] | None:
    url = f"http://{host}:{port}{HEALTH_PATH}"
    request = Request(url, headers={"User-Agent": "EitaaBridge-BackgroundController/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {"ok": True}
    except (URLError, OSError, json.JSONDecodeError):
        return None
    return None


def rotate_log_if_needed(log_path: Path) -> None:
    try:
        if not log_path.is_file() or log_path.stat().st_size < MAX_LOG_BYTES:
            return
        for i in range(LOG_BACKUPS - 1, 0, -1):
            src = log_path.with_name(f"{log_path.name}.{i}")
            dst = log_path.with_name(f"{log_path.name}.{i + 1}")
            if src.exists():
                src.replace(dst)
        log_path.replace(log_path.with_name(f"{log_path.name}.1"))
    except OSError:
        pass


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            kernel32.CloseHandle(handle)
            return False
        except Exception:
            pass
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def read_recorded_pid(pid_file: Path) -> int | None:
    try:
        if pid_file.is_file():
            raw = pid_file.read_text(encoding="utf-8").strip()
            val = int(raw)
            if val > 0:
                return val
    except (OSError, ValueError):
        pass
    return None


def action_status(paths: dict[str, Path]) -> int:
    health = query_health()
    pid = read_recorded_pid(paths["pid_file"])
    alive = is_process_alive(pid) if pid else False

    result = {
        "running": health is not None and health.get("ok") is True,
        "health": health,
        "recorded_pid": pid,
        "process_alive": alive,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["running"] else 1


def action_run(paths: dict[str, Path]) -> int:
    """Internal runner executed in background without console window."""
    root = paths["root"]
    paths["logs"].mkdir(parents=True, exist_ok=True)
    rotate_log_if_needed(paths["log_file"])

    # Record current process PID
    pid = os.getpid()
    paths["pid_file"].write_text(str(pid), encoding="utf-8")

    # Redirect stdout and stderr to the background server log
    log_handle = open(paths["log_file"], "a", encoding="utf-8", buffering=1)
    sys.stdout = log_handle
    sys.stderr = log_handle

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Starting Eitaa Bridge background HTTP API server (PID={pid})...")

    # Ensure src is in sys.path
    src_str = str(paths["src"].resolve())
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    try:
        from eitaa_bridge.interfaces.http_api import main as http_main
        args = [
            "--config",
            str(paths["bridge_config"]),
            "--ui-root",
            str(paths["ui_root"]),
        ]
        return http_main(args)
    except Exception as exc:
        print(f"[{timestamp}] Fatal error in background HTTP server: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            if paths["pid_file"].is_file():
                current_recorded = read_recorded_pid(paths["pid_file"])
                if current_recorded == pid:
                    paths["pid_file"].unlink()
        except OSError:
            pass
        log_handle.close()


def action_start(paths: dict[str, Path]) -> int:
    health = query_health()
    if health is not None and health.get("ok") is True:
        pid = read_recorded_pid(paths["pid_file"])
        print(f"Eitaa Bridge background server is already running on port {DEFAULT_PORT} (pid={pid or 'unknown'}).")
        return 0

    root = paths["root"]
    vbs = paths["vbs_launcher"]

    if os.name == "nt" and vbs.is_file():
        # Launch via wscript so the process is completely detached and survives console closes
        subprocess.run(["wscript.exe", str(vbs)], check=False)
    else:
        python_exe = find_python(root)
        flags = 0x08000008 if os.name == "nt" else 0  # CREATE_NO_WINDOW | DETACHED_PROCESS
        subprocess.Popen(
            [str(python_exe), str(Path(__file__).resolve()), "run"],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    print("Spawned background server. Waiting for readiness...")
    deadline = time.monotonic() + 10.0
    ready = False
    while time.monotonic() < deadline:
        h = query_health(timeout=0.6)
        if h and h.get("ok"):
            ready = True
            break
        time.sleep(0.3)

    if not ready:
        print("Timed out waiting for Eitaa Bridge background server to respond.", file=sys.stderr)
        print(f"Check logs at: {paths['log_file']}", file=sys.stderr)
        return 1

    pid = read_recorded_pid(paths["pid_file"])
    print(f"Eitaa Bridge background server is ready and listening on http://{DEFAULT_HOST}:{DEFAULT_PORT}/ (PID={pid or 'unknown'})")
    return 0


def action_stop(paths: dict[str, Path]) -> int:
    pid = read_recorded_pid(paths["pid_file"])

    if pid and is_process_alive(pid):
        print(f"Stopping Eitaa Bridge background server (pid={pid})...")
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        if query_health(timeout=0.5) is None:
            break
        time.sleep(0.3)

    if query_health(timeout=0.5) is not None:
        print("Process still answering on port 8765, attempting force termination...", file=sys.stderr)
        if os.name == "nt":
            cmd = "Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, check=False)
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.isdigit() and int(line) > 0:
                    subprocess.run(["taskkill", "/PID", line, "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    if paths["pid_file"].is_file():
        try:
            paths["pid_file"].unlink()
        except OSError:
            pass

    if query_health(timeout=0.5) is None:
        print("Eitaa Bridge background server stopped successfully.")
        return 0
    else:
        print("Could not verify that Eitaa Bridge server stopped.", file=sys.stderr)
        return 1


def action_restart(paths: dict[str, Path]) -> int:
    action_stop(paths)
    time.sleep(1.0)
    return action_start(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eitaa Bridge Background Server Manager")
    parser.add_argument("action", choices=["run", "start", "stop", "restart", "status"], default="status", nargs="?")
    args = parser.parse_args(argv)

    paths = get_paths()
    if args.action == "run":
        return action_run(paths)
    elif args.action == "start":
        return action_start(paths)
    elif args.action == "stop":
        return action_stop(paths)
    elif args.action == "restart":
        return action_restart(paths)
    elif args.action == "status":
        return action_status(paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())

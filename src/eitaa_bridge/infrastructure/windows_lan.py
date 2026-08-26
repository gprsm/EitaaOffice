from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import BinaryIO, Any
import uuid

from ..config import BridgeConfig
from ..errors import BridgeConfigurationError


_PROCESS_LOCKS: set[str] = set()
_PROCESS_LOCKS_GUARD = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_file(handle: BinaryIO) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class WindowsLanInstanceLock:
    """OS-backed single-instance lock that safely replaces stale metadata."""

    def __init__(self, path: str | Path, *, deployment_mode: str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.deployment_mode = deployment_mode
        self._handle: BinaryIO | None = None
        self._token = uuid.uuid4().hex
        self._guard_path = self.path.with_name(self.path.name + ".guard")
        self._registry_key = os.path.normcase(str(self.path))

    def acquire(self) -> WindowsLanInstanceLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _PROCESS_LOCKS_GUARD:
            if self._registry_key in _PROCESS_LOCKS:
                raise BridgeConfigurationError(
                    "The Windows LAN server is already running for this installation.",
                    code="windows_lan_instance_running",
                )
            _PROCESS_LOCKS.add(self._registry_key)
        handle: BinaryIO | None = None
        try:
            descriptor = os.open(self._guard_path, os.O_RDWR | os.O_CREAT, 0o600)
            handle = os.fdopen(descriptor, "r+b")
            _lock_file(handle)
            self._handle = handle
            self._write_metadata(status="running")
            return self
        except OSError as exc:
            if handle is not None:
                handle.close()
            with _PROCESS_LOCKS_GUARD:
                _PROCESS_LOCKS.discard(self._registry_key)
            raise BridgeConfigurationError(
                "The Windows LAN server is already running for this installation.",
                code="windows_lan_instance_running",
            ) from exc
        except Exception:
            if handle is not None:
                handle.close()
            with _PROCESS_LOCKS_GUARD:
                _PROCESS_LOCKS.discard(self._registry_key)
            raise

    def _write_metadata(self, *, status: str) -> None:
        if self._handle is None:
            return
        payload: dict[str, Any] = {
            "format": "eitaa-bridge-windows-lan-lock-v1",
            "status": status,
            "pid": os.getpid(),
            "deployment_mode": self.deployment_mode,
            "instance_token": self._token,
            "updated_at": _utc_now(),
        }
        temporary = self.path.with_name(
            f"{self.path.name}.{os.getpid()}.{self._token}.tmp"
        )
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            self._write_metadata(status="stopped")
            _unlock_file(handle)
        finally:
            handle.close()
            self._handle = None
            with _PROCESS_LOCKS_GUARD:
                _PROCESS_LOCKS.discard(self._registry_key)

    def __enter__(self) -> WindowsLanInstanceLock:
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


@dataclass(slots=True, frozen=True)
class WindowsFirewallPlan:
    rule_name: str
    local_address: str
    local_port: int
    remote_addresses: tuple[str, ...]

    def powershell_preview(self) -> str:
        def quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        remotes = "@(" + ", ".join(quote(value) for value in self.remote_addresses) + ")"
        return " ".join(
            (
                "New-NetFirewallRule",
                "-DisplayName",
                quote(self.rule_name),
                "-Direction Inbound",
                "-Action Allow",
                "-Enabled True",
                "-Profile Private",
                "-Protocol TCP",
                "-EdgeTraversalPolicy Block",
                "-LocalAddress",
                quote(self.local_address),
                "-LocalPort",
                str(self.local_port),
                "-RemoteAddress",
                remotes,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "eitaa-bridge-windows-firewall-plan-v1",
            "execution_performed": False,
            "requires_explicit_administrator_confirmation": True,
            "rule": {
                "display_name": self.rule_name,
                "direction": "Inbound",
                "action": "Allow",
                "enabled": True,
                "profile": "Private",
                "protocol": "TCP",
                "edge_traversal": "Block",
                "local_address": self.local_address,
                "local_port": self.local_port,
                "remote_addresses": list(self.remote_addresses),
            },
            "powershell_preview": self.powershell_preview(),
        }


def build_windows_firewall_plan(
    config: BridgeConfig,
    *,
    rule_name: str = "Eitaa Bridge Trusted LAN",
) -> WindowsFirewallPlan:
    deployment = config.deployment
    if deployment.mode != "trusted_lan_http":
        raise BridgeConfigurationError(
            "A Firewall plan is available only for trusted_lan_http.",
            code="windows_firewall_plan_requires_trusted_lan_http",
        )
    config.validate()
    selected_name = rule_name.strip()
    if not selected_name or len(selected_name) > 120 or any(ord(ch) < 32 for ch in selected_name):
        raise BridgeConfigurationError(
            "The Firewall rule display name is invalid.",
            code="windows_firewall_rule_name_invalid",
        )
    return WindowsFirewallPlan(
        rule_name=selected_name,
        local_address=deployment.bind_host,
        local_port=deployment.bind_port,
        remote_addresses=deployment.allowed_private_client_cidrs,
    )


def validate_windows_lan_runtime(config: BridgeConfig, ui_root: str | Path) -> dict[str, Any]:
    if config.deployment.mode != "trusted_lan_http":
        raise BridgeConfigurationError(
            "The Windows LAN launcher requires trusted_lan_http.",
            code="windows_lan_launcher_requires_trusted_lan_http",
        )
    config.validate()
    selected_ui_root = Path(ui_root).expanduser().resolve()
    if not (selected_ui_root / "index.html").is_file():
        raise BridgeConfigurationError(
            "The production UI build is missing.",
            code="windows_lan_ui_root_missing",
        )
    return {
        "ok": True,
        "status": "configuration_valid",
        "deployment_mode": config.deployment.mode,
        "bind_host": config.deployment.bind_host,
        "bind_port": config.deployment.bind_port,
        "ui_ready": True,
        "side_effects_performed": False,
    }

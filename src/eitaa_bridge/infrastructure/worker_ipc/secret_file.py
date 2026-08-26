"""Short-lived, current-user-only authentication material for worker IPC."""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import uuid

from ...errors import WorkerIpcError

_SCHEMA_VERSION = 1
_SECRET_BYTES = 32
_MAX_FILE_BYTES = 4096
_PROVIDER = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_uuid4(value: str, *, field: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise WorkerIpcError(
            "The worker IPC identity is invalid.",
            safe_context={"field": field},
            code="ipc_identity_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise WorkerIpcError(
            "The worker IPC identity is invalid.",
            safe_context={"field": field},
            code="ipc_identity_invalid",
        )
    return str(parsed)


def _canonical_provider(value: str) -> str:
    selected = str(value or "")
    if not _PROVIDER.fullmatch(selected):
        raise WorkerIpcError(
            "The worker provider identifier is invalid.",
            code="ipc_provider_invalid",
        )
    return selected


def _timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise WorkerIpcError(
            "The worker IPC secret timestamp is invalid.",
            safe_context={"field": field},
            code="ipc_secret_invalid",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkerIpcError(
            "The worker IPC secret timestamp is invalid.",
            safe_context={"field": field},
            code="ipc_secret_invalid",
        )
    return parsed.astimezone(timezone.utc)


def _restrict_windows_dacl(path: Path) -> None:
    """Replace inheritance with one full-control ACE for the current user."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.LPVOID]
    kernel32.LocalFree.restype = wintypes.LPVOID
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorDacl.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.BOOL),
    ]
    advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    token = wintypes.HANDLE()
    token_query = 0x0008
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), token_query, ctypes.byref(token)
    ):
        raise OSError(ctypes.get_last_error(), "OpenProcessToken failed")
    try:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(required))
        if not required.value:
            raise OSError(ctypes.get_last_error(), "GetTokenInformation failed")
        token_info = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token,
            1,
            token_info,
            required,
            ctypes.byref(required),
        ):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation failed")

        class _SidAndAttributes(ctypes.Structure):
            _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

        class _TokenUser(ctypes.Structure):
            _fields_ = [("User", _SidAndAttributes)]

        sid = ctypes.cast(token_info, ctypes.POINTER(_TokenUser)).contents.User.Sid
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
            raise OSError(ctypes.get_last_error(), "ConvertSidToStringSid failed")
        try:
            sddl = f"D:P(A;;FA;;;{sid_text.value})"
        finally:
            kernel32.LocalFree(ctypes.cast(sid_text, wintypes.LPVOID))

        descriptor = wintypes.LPVOID()
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl,
            1,
            ctypes.byref(descriptor),
            None,
        ):
            raise OSError(
                ctypes.get_last_error(),
                "ConvertStringSecurityDescriptorToSecurityDescriptor failed",
            )
        try:
            present = wintypes.BOOL()
            defaulted = wintypes.BOOL()
            dacl = wintypes.LPVOID()
            if not advapi32.GetSecurityDescriptorDacl(
                descriptor,
                ctypes.byref(present),
                ctypes.byref(dacl),
                ctypes.byref(defaulted),
            ) or not present.value:
                raise OSError(ctypes.get_last_error(), "GetSecurityDescriptorDacl failed")
            result = advapi32.SetNamedSecurityInfoW(
                str(path),
                1,
                0x00000004 | 0x80000000,
                None,
                None,
                dacl,
                None,
            )
            if result:
                raise OSError(result, "SetNamedSecurityInfo failed")
        finally:
            kernel32.LocalFree(descriptor)
    finally:
        kernel32.CloseHandle(token)


def _restrict_to_current_user(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        if os.name == "nt":
            _restrict_windows_dacl(path)
        else:
            permissions = stat.S_IMODE(path.stat().st_mode)
            if permissions & (stat.S_IRWXG | stat.S_IRWXO):
                raise OSError("secret file permissions are broader than 0600")
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise WorkerIpcError(
            "The worker IPC secret could not be restricted to the current user.",
            safe_context={"error_type": type(exc).__name__},
            code="ipc_secret_acl_failed",
        ) from exc


@dataclass(frozen=True, slots=True)
class WorkerIpcSecret:
    key_id: str
    secret: bytes = field(repr=False)
    messenger_account_id: str
    provider: str
    created_at: datetime
    expires_at: datetime

    def safe_summary(self) -> dict[str, object]:
        return {
            "key_id": self.key_id,
            "messenger_account_id": self.messenger_account_id,
            "provider": self.provider,
            "expires_at": self.expires_at.isoformat(timespec="seconds"),
        }


class WorkerIpcSecretFile:
    """Create and consume one-use worker authentication files."""

    @classmethod
    def create(
        cls,
        directory: str | Path,
        *,
        messenger_account_id: str,
        provider: str,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> tuple[WorkerIpcSecret, Path]:
        if not 5 <= ttl_seconds <= 300:
            raise WorkerIpcError(
                "The worker IPC secret lifetime is outside the safe range.",
                code="ipc_secret_ttl_invalid",
            )
        account_id = _canonical_uuid4(
            messenger_account_id,
            field="messenger_account_id",
        )
        selected_provider = _canonical_provider(provider)
        selected_now = (now or _utc_now()).astimezone(timezone.utc)
        created_at = selected_now.replace(
            microsecond=(selected_now.microsecond // 1000) * 1000
        )
        material = WorkerIpcSecret(
            key_id=str(uuid.uuid4()),
            secret=os.urandom(_SECRET_BYTES),
            messenger_account_id=account_id,
            provider=selected_provider,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
        )
        parent = Path(directory).expanduser().resolve()
        parent.mkdir(parents=True, exist_ok=True)
        path = parent / f"worker-ipc-{material.key_id}.json"
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "key_id": material.key_id,
            "secret": base64.urlsafe_b64encode(material.secret).decode("ascii"),
            "messenger_account_id": material.messenger_account_id,
            "provider": material.provider,
            "created_at": material.created_at.isoformat(timespec="milliseconds"),
            "expires_at": material.expires_at.isoformat(timespec="milliseconds"),
        }
        descriptor: int | None = None
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                stat.S_IRUSR | stat.S_IWUSR,
            )
            if os.name == "nt":
                os.close(descriptor)
                descriptor = None
                _restrict_to_current_user(path)
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0),
                )
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                descriptor = None
                json.dump(payload, stream, ensure_ascii=True, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != "nt":
                _restrict_to_current_user(path)
        except WorkerIpcError:
            raise
        except OSError as exc:
            if descriptor is not None:
                os.close(descriptor)
            path.unlink(missing_ok=True)
            raise WorkerIpcError(
                "The worker IPC secret could not be created.",
                safe_context={"error_type": type(exc).__name__},
                code="ipc_secret_create_failed",
            ) from exc
        return material, path

    @classmethod
    def consume(
        cls,
        path: str | Path,
        *,
        expected_messenger_account_id: str,
        expected_provider: str,
        now: datetime | None = None,
    ) -> WorkerIpcSecret:
        account_id = _canonical_uuid4(
            expected_messenger_account_id,
            field="messenger_account_id",
        )
        provider = _canonical_provider(expected_provider)
        source = Path(path).expanduser().absolute()
        consuming = source.with_name(
            f".{source.name}.consuming-{os.getpid()}-{uuid.uuid4()}"
        )
        try:
            os.replace(source, consuming)
        except OSError as exc:
            raise WorkerIpcError(
                "The worker IPC secret is unavailable.",
                safe_context={"error_type": type(exc).__name__},
                code="ipc_secret_unavailable",
            ) from exc
        try:
            details = consuming.lstat()
            if stat.S_ISLNK(details.st_mode) or details.st_size > _MAX_FILE_BYTES:
                raise WorkerIpcError(
                    "The worker IPC secret file is invalid.",
                    code="ipc_secret_invalid",
                )
            if os.name != "nt" and stat.S_IMODE(details.st_mode) & (
                stat.S_IRWXG | stat.S_IRWXO
            ):
                raise WorkerIpcError(
                    "The worker IPC secret file permissions are unsafe.",
                    code="ipc_secret_acl_invalid",
                )
            payload = json.loads(consuming.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                raise ValueError("schema")
            key_id = _canonical_uuid4(str(payload.get("key_id") or ""), field="key_id")
            selected_account = _canonical_uuid4(
                str(payload.get("messenger_account_id") or ""),
                field="messenger_account_id",
            )
            selected_provider = _canonical_provider(str(payload.get("provider") or ""))
            try:
                secret = base64.b64decode(
                    str(payload.get("secret") or ""),
                    altchars=b"-_",
                    validate=True,
                )
            except (ValueError, TypeError) as exc:
                raise ValueError("secret") from exc
            created_at = _timestamp(str(payload.get("created_at") or ""), field="created_at")
            expires_at = _timestamp(str(payload.get("expires_at") or ""), field="expires_at")
            current = (now or _utc_now()).astimezone(timezone.utc)
            if (
                len(secret) != _SECRET_BYTES
                or selected_account != account_id
                or selected_provider != provider
                or expires_at <= current
                or created_at > current + timedelta(seconds=5)
                or expires_at - created_at > timedelta(seconds=300)
            ):
                raise ValueError("contract")
            return WorkerIpcSecret(
                key_id=key_id,
                secret=secret,
                messenger_account_id=selected_account,
                provider=selected_provider,
                created_at=created_at,
                expires_at=expires_at,
            )
        except WorkerIpcError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise WorkerIpcError(
                "The worker IPC secret is invalid or expired.",
                safe_context={"error_type": type(exc).__name__},
                code="ipc_secret_invalid",
            ) from exc
        finally:
            consuming.unlink(missing_ok=True)

"""Protected phone identity primitives for the local Windows coordinator."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat
import sys
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...errors import CoordinatorIdentityError

_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
_KEY_BYTES = 32
_KEY_VERSION = 1
_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_CRYPTPROTECT_LOCAL_MACHINE = 0x4
_FILE_KEY_AAD = b"eitaa-bridge-phone-identity-v1"
_AES_GCM_NONCE_BYTES = 12


@dataclass(frozen=True, slots=True)
class ProtectedPhone:
    ciphertext: bytes
    key_version: int
    fingerprint: str
    display_hint: str


class PhoneProtector(Protocol):
    """Minimal injectable boundary used by onboarding and isolated tests."""

    def protect(self, canonical_e164: str) -> ProtectedPhone: ...


def validate_canonical_e164(value: str) -> str:
    """Require an already-canonical E.164 phone identity."""
    selected = str(value or "")
    if not _E164.fullmatch(selected):
        raise CoordinatorIdentityError(
            "The confirmed phone identity must be in canonical E.164 form.",
            code="confirmed_identity_invalid",
        )
    return selected


def masked_phone(value: str) -> str:
    return validate_canonical_e164(value)


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _input_blob(data: bytes) -> tuple[_DataBlob, object]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _windows_library(name: str) -> object:
    if sys.platform != "win32":
        raise CoordinatorIdentityError(
            "Protected phone storage requires Windows DPAPI.",
            code="phone_protection_platform_unsupported",
        )
    try:
        return ctypes.WinDLL(name, use_last_error=True)
    except OSError as exc:
        raise CoordinatorIdentityError(
            "Windows phone-protection services are unavailable.",
            safe_context={"error_type": type(exc).__name__},
            code="phone_protection_unavailable",
        ) from exc


def _protect_data(
    data: bytes,
    *,
    entropy: bytes | None,
    description: str,
    machine_scope: bool = False,
) -> bytes:
    crypt32 = _windows_library("crypt32")
    kernel32 = _windows_library("kernel32")
    source, source_buffer = _input_blob(data)
    entropy_blob = entropy_buffer = None
    if entropy is not None:
        entropy_blob, entropy_buffer = _input_blob(entropy)
    output = _DataBlob()
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    protect.restype = wintypes.BOOL
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    flags = _CRYPTPROTECT_UI_FORBIDDEN
    if machine_scope:
        flags |= _CRYPTPROTECT_LOCAL_MACHINE
    if not protect(
        ctypes.byref(source),
        description,
        entropy_pointer,
        None,
        None,
        flags,
        ctypes.byref(output),
    ):
        error = ctypes.get_last_error()
        raise CoordinatorIdentityError(
            "The phone identity could not be protected.",
            safe_context={"windows_error": error},
            code="phone_protection_failed",
        )
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def _unprotect_data(data: bytes, *, entropy: bytes | None) -> bytes:
    crypt32 = _windows_library("crypt32")
    kernel32 = _windows_library("kernel32")
    source, source_buffer = _input_blob(data)
    entropy_blob = entropy_buffer = None
    if entropy is not None:
        entropy_blob, entropy_buffer = _input_blob(entropy)
    output = _DataBlob()
    description = wintypes.LPWSTR()
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    unprotect.restype = wintypes.BOOL
    entropy_pointer = ctypes.byref(entropy_blob) if entropy_blob is not None else None
    if not unprotect(
        ctypes.byref(source),
        ctypes.byref(description),
        entropy_pointer,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output),
    ):
        error = ctypes.get_last_error()
        raise CoordinatorIdentityError(
            "The protected phone identity could not be opened.",
            safe_context={"windows_error": error},
            code="phone_unprotection_failed",
        )
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        if description:
            kernel32.LocalFree(description)
        del source_buffer, entropy_buffer


class WindowsDpapiPhoneProtector:
    """Encrypt phone values and HMAC fingerprints with a DPAPI-wrapped install key."""

    def __init__(self, wrapped_key_file: str | Path) -> None:
        self.wrapped_key_file = Path(wrapped_key_file).expanduser().resolve()

    def protect(self, canonical_e164: str) -> ProtectedPhone:
        phone = validate_canonical_e164(canonical_e164)
        secret = self._load_or_create_secret()
        fingerprint = hmac.new(secret, phone.encode("ascii"), hashlib.sha256).hexdigest()
        ciphertext = _protect_data(
            phone.encode("ascii"),
            entropy=secret,
            description="Eitaa Bridge coordinator phone identity",
            machine_scope=True,
        )
        return ProtectedPhone(
            ciphertext=ciphertext,
            key_version=_KEY_VERSION,
            fingerprint=fingerprint,
            display_hint=masked_phone(phone),
        )

    def reveal(self, protected: ProtectedPhone) -> str:
        if protected.key_version != _KEY_VERSION:
            raise CoordinatorIdentityError(
                "The protected phone uses an unsupported key version.",
                safe_context={"key_version": protected.key_version},
                code="phone_key_version_unsupported",
            )
        secret = self._load_secret()
        try:
            selected = _unprotect_data(protected.ciphertext, entropy=secret).decode("ascii")
        except UnicodeDecodeError as exc:
            raise CoordinatorIdentityError(
                "The protected phone payload is invalid.",
                code="protected_phone_payload_invalid",
            ) from exc
        return validate_canonical_e164(selected)

    def rewrap_install_key_for_machine_scope(self, backup_file: str | Path) -> Path:
        """Atomically rewrap an accessible legacy key for stable local execution."""

        backup = Path(backup_file).expanduser().resolve()
        if backup.exists():
            raise CoordinatorIdentityError(
                "The protected identity key backup already exists.",
                safe_context={"backup_name": backup.name},
                code="identity_key_backup_exists",
            )
        try:
            current_wrapped = self.wrapped_key_file.read_bytes()
            secret = self._load_secret()
            machine_wrapped = _protect_data(
                secret,
                entropy=None,
                description="Eitaa Bridge coordinator identity key",
                machine_scope=True,
            )
            if not hmac.compare_digest(
                _unprotect_data(machine_wrapped, entropy=None),
                secret,
            ):
                raise CoordinatorIdentityError(
                    "The machine-scoped identity key did not pass verification.",
                    code="identity_key_rewrap_verification_failed",
                )
            backup.parent.mkdir(parents=True, exist_ok=True)
            self._write_exclusive(backup, current_wrapped)
            temporary = self.wrapped_key_file.with_name(
                f"{self.wrapped_key_file.name}.next.{os.urandom(8).hex()}"
            )
            try:
                self._write_exclusive(temporary, machine_wrapped)
                os.replace(temporary, self.wrapped_key_file)
            finally:
                temporary.unlink(missing_ok=True)
            if not hmac.compare_digest(self._load_secret(), secret):
                raise CoordinatorIdentityError(
                    "The installed machine-scoped identity key did not pass verification.",
                    safe_context={"backup_name": backup.name},
                    code="identity_key_rewrap_final_verification_failed",
                )
            return backup
        except CoordinatorIdentityError:
            raise
        except OSError as exc:
            raise CoordinatorIdentityError(
                "The protected identity key could not be rewrapped.",
                safe_context={"error_type": type(exc).__name__},
                code="identity_key_rewrap_failed",
            ) from exc
        finally:
            if "secret" in locals():
                secret = b""

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def _load_or_create_secret(self) -> bytes:
        if self.wrapped_key_file.is_file():
            return self._load_secret()
        self.wrapped_key_file.parent.mkdir(parents=True, exist_ok=True)
        wrapped = _protect_data(
            os.urandom(_KEY_BYTES),
            entropy=None,
            description="Eitaa Bridge coordinator identity key",
            machine_scope=True,
        )
        try:
            descriptor = os.open(
                self.wrapped_key_file,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError:
            return self._load_secret()
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(wrapped)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(self.wrapped_key_file, 0o600)
            except OSError:
                pass
        except OSError as exc:
            self.wrapped_key_file.unlink(missing_ok=True)
            raise CoordinatorIdentityError(
                "The protected identity key could not be stored.",
                safe_context={"error_type": type(exc).__name__},
                code="identity_key_write_failed",
            ) from exc
        return self._load_secret()

    def _load_secret(self) -> bytes:
        try:
            wrapped = self.wrapped_key_file.read_bytes()
        except OSError as exc:
            raise CoordinatorIdentityError(
                "The protected identity key could not be read.",
                safe_context={"error_type": type(exc).__name__},
                code="identity_key_read_failed",
            ) from exc
        secret = _unprotect_data(wrapped, entropy=None)
        if len(secret) != _KEY_BYTES:
            raise CoordinatorIdentityError(
                "The protected identity key has an invalid length.",
                code="identity_key_invalid",
            )
        return secret


class FileKeyPhoneProtector:
    """Protect phone identities with a service-owned key on non-Windows hosts.

    The key file must be a regular, non-symlink file and is created with mode
    0600.  Its parent directory is restricted to 0700 on POSIX.  This keeps the
    Linux service deployable without weakening the existing Windows DPAPI path.
    """

    def __init__(self, key_file: str | Path) -> None:
        self.key_file = Path(key_file).expanduser().resolve()

    def protect(self, canonical_e164: str) -> ProtectedPhone:
        phone = validate_canonical_e164(canonical_e164)
        secret = self._load_or_create_secret()
        nonce = os.urandom(_AES_GCM_NONCE_BYTES)
        ciphertext = nonce + AESGCM(secret).encrypt(
            nonce,
            phone.encode("ascii"),
            _FILE_KEY_AAD,
        )
        return ProtectedPhone(
            ciphertext=ciphertext,
            key_version=_KEY_VERSION,
            fingerprint=hmac.new(
                secret,
                phone.encode("ascii"),
                hashlib.sha256,
            ).hexdigest(),
            display_hint=masked_phone(phone),
        )

    def reveal(self, protected: ProtectedPhone) -> str:
        if protected.key_version != _KEY_VERSION:
            raise CoordinatorIdentityError(
                "The protected phone uses an unsupported key version.",
                safe_context={"key_version": protected.key_version},
                code="phone_key_version_unsupported",
            )
        if len(protected.ciphertext) <= _AES_GCM_NONCE_BYTES:
            raise CoordinatorIdentityError(
                "The protected phone payload is invalid.",
                code="protected_phone_payload_invalid",
            )
        secret = self._load_secret()
        nonce = protected.ciphertext[:_AES_GCM_NONCE_BYTES]
        payload = protected.ciphertext[_AES_GCM_NONCE_BYTES:]
        try:
            selected = AESGCM(secret).decrypt(nonce, payload, _FILE_KEY_AAD).decode("ascii")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise CoordinatorIdentityError(
                "The protected phone payload is invalid.",
                code="protected_phone_payload_invalid",
            ) from exc
        return validate_canonical_e164(selected)

    def _load_or_create_secret(self) -> bytes:
        if self.key_file.exists() or self.key_file.is_symlink():
            return self._load_secret()
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self.key_file.parent, 0o700)
        secret = os.urandom(_KEY_BYTES)
        try:
            WindowsDpapiPhoneProtector._write_exclusive(self.key_file, secret)
        except FileExistsError:
            return self._load_secret()
        return self._load_secret()

    def _load_secret(self) -> bytes:
        try:
            metadata = self.key_file.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise CoordinatorIdentityError(
                    "The identity key path is not a regular file.",
                    code="identity_key_invalid",
                )
            if os.name != "nt" and stat.S_IMODE(metadata.st_mode) & 0o077:
                raise CoordinatorIdentityError(
                    "The identity key permissions are too broad.",
                    code="identity_key_permissions_invalid",
                )
            secret = self.key_file.read_bytes()
        except CoordinatorIdentityError:
            raise
        except OSError as exc:
            raise CoordinatorIdentityError(
                "The protected identity key could not be read.",
                safe_context={"error_type": type(exc).__name__},
                code="identity_key_read_failed",
            ) from exc
        if len(secret) != _KEY_BYTES:
            raise CoordinatorIdentityError(
                "The protected identity key has an invalid length.",
                code="identity_key_invalid",
            )
        return secret


def default_phone_protector(key_directory: str | Path) -> PhoneProtector:
    """Select the native at-rest protection mechanism for this host."""

    directory = Path(key_directory).expanduser().resolve()
    if sys.platform == "win32":
        return WindowsDpapiPhoneProtector(directory / "identity.key.dpapi")
    return FileKeyPhoneProtector(directory / "identity.key")

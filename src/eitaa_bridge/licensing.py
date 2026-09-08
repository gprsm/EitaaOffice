"""Offline, device-bound activation for packaged Eitaa Bridge installations.

The installed application contains only Ed25519 public keys.  Issuing licenses
requires a private key that is deliberately kept outside the repository and
outside every user-facing release artifact.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .errors import LicenseValidationError


PRODUCT_ID = "eitaa-bridge-office"
FINGERPRINT_VERSION = 1
REQUEST_PREFIX = "EBRQ1"
ACTIVATION_PREFIX = "EBLC1"
REQUEST_FORMAT = "eitaa-bridge-license-request-v1"
LICENSE_FORMAT = "eitaa-bridge-license-v1"
POLICY_FORMAT = "eitaa-bridge-license-policy-v1"
STORE_MAGIC = b"EBLS1\x00"
_HEX_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_MAX_CODE_LENGTH = 8192
_CLOCK_SKEW_SECONDS = 300

# Replaced by the branch signing-key generation step. Public verification keys
# are intentionally safe to distribute; private signing keys are never stored
# here. Keeping a mapping permits controlled key rotation without invalidating
# licenses issued by the immediately previous key.
DEFAULT_PUBLIC_KEYS: dict[str, bytes] = {
    "eb-03ccb9de2571321d": base64.b64decode(
        "xsxWrfxIKCcVdkdv3vpYGJUyrXfB5TIStgdapTpHjNk="
    ),
}


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64decode(value: str, *, code: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise LicenseValidationError("Activation data is malformed.", code=code)
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise LicenseValidationError("Activation data is malformed.", code=code) from exc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Timezone-aware UTC values are required.")
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: object, *, code: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise LicenseValidationError("Activation time is invalid.", code=code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LicenseValidationError("Activation time is invalid.", code=code) from exc
    if parsed.tzinfo is None:
        raise LicenseValidationError("Activation time is invalid.", code=code)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class LicenseRequest:
    product_id: str
    device_fingerprint: str
    fingerprint_version: int

    def safe_summary(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "device_fingerprint": self.device_fingerprint,
            "fingerprint_version": self.fingerprint_version,
        }


@dataclass(frozen=True, slots=True)
class VerifiedLicense:
    license_id: str
    key_id: str
    device_fingerprint: str
    issued_at: datetime
    expires_at: datetime | None
    edition: str
    features: tuple[str, ...]
    customer_reference: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "licensed": True,
            "license_id": self.license_id,
            "key_id": self.key_id,
            "edition": self.edition,
            "features": list(self.features),
            "issued_at": _format_time(self.issued_at),
            "expires_at": _format_time(self.expires_at) if self.expires_at else None,
        }


@dataclass(frozen=True, slots=True)
class LicenseStatus:
    licensed: bool
    reason_code: str
    license: VerifiedLicense | None = None

    def safe_summary(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "licensed": self.licensed,
            "reason_code": self.reason_code,
        }
        if self.license is not None:
            payload["license"] = self.license.safe_summary()
        return payload


def device_fingerprint_from_components(components: Mapping[str, str]) -> str:
    normalized: list[tuple[str, str]] = []
    for name, raw_value in components.items():
        key = str(name).strip().lower()
        value = str(raw_value).strip().lower()
        if not key or not value:
            continue
        normalized.append((key, hashlib.sha256(value.encode("utf-8")).hexdigest()))
    if len(normalized) < 2:
        raise LicenseValidationError(
            "The device identity could not be established safely.",
            code="license_device_identity_unavailable",
        )
    payload = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "components": sorted(normalized),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _windows_machine_guid() -> str:
    import winreg

    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Cryptography",
        0,
        access,
    ) as key:
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
    return str(value).strip()


def _windows_system_volume_serial() -> str:
    drive = (os.environ.get("SystemDrive") or "C:").rstrip("\\/") + "\\"
    serial = ctypes.c_uint32()
    maximum_component = ctypes.c_uint32()
    flags = ctypes.c_uint32()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive),
        None,
        0,
        ctypes.byref(serial),
        ctypes.byref(maximum_component),
        ctypes.byref(flags),
        None,
        0,
    )
    if not ok:
        raise OSError(int(ctypes.windll.kernel32.GetLastError()), "GetVolumeInformationW failed")
    return f"{serial.value:08x}"


def current_device_fingerprint() -> str:
    if os.name != "nt":
        raise LicenseValidationError(
            "Device activation is supported only on Windows.",
            code="license_platform_unsupported",
        )
    readers = {
        "machine_guid": _windows_machine_guid,
        "system_volume_serial": _windows_system_volume_serial,
    }
    components: dict[str, str] = {}
    for name, reader in readers.items():
        try:
            value = reader()
        except (OSError, PermissionError, ValueError):
            continue
        if value:
            components[name] = value
    return device_fingerprint_from_components(components)


def encode_request_code(device_fingerprint: str) -> str:
    if not _HEX_FINGERPRINT.fullmatch(device_fingerprint):
        raise LicenseValidationError("Device fingerprint is invalid.", code="license_device_invalid")
    payload = _canonical_json(
        {
            "device": device_fingerprint,
            "fingerprint_version": FINGERPRINT_VERSION,
            "format": REQUEST_FORMAT,
            "product": PRODUCT_ID,
        }
    )
    checksum = hashlib.sha256(payload).hexdigest()[:16]
    return f"{REQUEST_PREFIX}.{_b64encode(payload)}.{checksum}"


def decode_request_code(request_code: str) -> LicenseRequest:
    selected = str(request_code or "").strip()
    if len(selected) > _MAX_CODE_LENGTH:
        raise LicenseValidationError("Activation request is invalid.", code="license_request_invalid")
    pieces = selected.split(".")
    if len(pieces) != 3 or pieces[0] != REQUEST_PREFIX:
        raise LicenseValidationError("Activation request is invalid.", code="license_request_invalid")
    raw = _b64decode(pieces[1], code="license_request_invalid")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest()[:16], pieces[2].lower()):
        raise LicenseValidationError("Activation request checksum failed.", code="license_request_invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseValidationError("Activation request is invalid.", code="license_request_invalid") from exc
    if not isinstance(payload, dict) or _canonical_json(payload) != raw:
        raise LicenseValidationError("Activation request is invalid.", code="license_request_invalid")
    product = payload.get("product")
    device = payload.get("device")
    version = payload.get("fingerprint_version")
    if (
        payload.get("format") != REQUEST_FORMAT
        or product != PRODUCT_ID
        or not isinstance(device, str)
        or not _HEX_FINGERPRINT.fullmatch(device)
        or version != FINGERPRINT_VERSION
    ):
        raise LicenseValidationError("Activation request is invalid.", code="license_request_invalid")
    return LicenseRequest(product, device, version)


def issue_activation_code(
    request_code: str,
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    license_id: str | None = None,
    edition: str = "standard",
    features: tuple[str, ...] = ("desktop",),
    customer_reference: str | None = None,
) -> str:
    request = decode_request_code(request_code)
    if not _KEY_ID.fullmatch(key_id):
        raise ValueError("key_id is invalid")
    issued = _utc(issued_at or datetime.now(timezone.utc)).replace(microsecond=0)
    expiry = _utc(expires_at).replace(microsecond=0) if expires_at else None
    if expiry is not None and expiry <= issued:
        raise ValueError("expires_at must be later than issued_at")
    selected_license_id = str(license_id or uuid.uuid4()).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", selected_license_id):
        raise ValueError("license_id is invalid")
    selected_edition = str(edition).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,31}", selected_edition):
        raise ValueError("edition is invalid")
    selected_features = tuple(sorted({str(item).strip().lower() for item in features}))
    if not selected_features or any(not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,31}", item) for item in selected_features):
        raise ValueError("features are invalid")
    selected_customer = str(customer_reference).strip() if customer_reference is not None else None
    if selected_customer == "":
        selected_customer = None
    if selected_customer is not None and (
        len(selected_customer) > 128 or any(ord(character) < 32 for character in selected_customer)
    ):
        raise ValueError("customer_reference is invalid")
    payload = _canonical_json(
        {
            "customer_reference": selected_customer,
            "device": request.device_fingerprint,
            "edition": selected_edition,
            "expires_at": _format_time(expiry) if expiry else None,
            "features": list(selected_features),
            "fingerprint_version": request.fingerprint_version,
            "format": LICENSE_FORMAT,
            "issued_at": _format_time(issued),
            "key_id": key_id,
            "license_id": selected_license_id,
            "product": request.product_id,
        }
    )
    return f"{ACTIVATION_PREFIX}.{_b64encode(payload)}.{_b64encode(private_key.sign(payload))}"


def verify_activation_code(
    activation_code: str,
    *,
    expected_device_fingerprint: str,
    public_keys: Mapping[str, bytes],
    now: datetime | None = None,
) -> VerifiedLicense:
    selected = str(activation_code or "").strip()
    if len(selected) > _MAX_CODE_LENGTH:
        raise LicenseValidationError("Activation code is invalid.", code="license_code_invalid")
    pieces = selected.split(".")
    if len(pieces) != 3 or pieces[0] != ACTIVATION_PREFIX:
        raise LicenseValidationError("Activation code is invalid.", code="license_code_invalid")
    raw = _b64decode(pieces[1], code="license_code_invalid")
    signature = _b64decode(pieces[2], code="license_code_invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseValidationError("Activation code is invalid.", code="license_code_invalid") from exc
    if not isinstance(payload, dict) or _canonical_json(payload) != raw:
        raise LicenseValidationError("Activation code is invalid.", code="license_code_invalid")
    key_id = payload.get("key_id")
    if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
        raise LicenseValidationError("Activation signing key is invalid.", code="license_key_unknown")
    public_key_bytes = public_keys.get(key_id)
    if not isinstance(public_key_bytes, bytes) or len(public_key_bytes) != 32:
        raise LicenseValidationError("Activation signing key is unknown.", code="license_key_unknown")
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, raw)
    except (InvalidSignature, ValueError) as exc:
        raise LicenseValidationError("Activation signature is invalid.", code="license_signature_invalid") from exc
    if payload.get("format") != LICENSE_FORMAT or payload.get("product") != PRODUCT_ID:
        raise LicenseValidationError("Activation product is invalid.", code="license_product_invalid")
    fingerprint = payload.get("device")
    if not isinstance(fingerprint, str) or not _HEX_FINGERPRINT.fullmatch(fingerprint):
        raise LicenseValidationError("Activation device is invalid.", code="license_device_invalid")
    if not hmac.compare_digest(fingerprint, expected_device_fingerprint):
        raise LicenseValidationError("Activation belongs to another device.", code="license_device_mismatch")
    if payload.get("fingerprint_version") != FINGERPRINT_VERSION:
        raise LicenseValidationError("Activation fingerprint version is unsupported.", code="license_version_unsupported")
    issued_at = _parse_time(payload.get("issued_at"), code="license_time_invalid")
    expires_value = payload.get("expires_at")
    expires_at = _parse_time(expires_value, code="license_time_invalid") if expires_value is not None else None
    selected_now = _utc(now or datetime.now(timezone.utc))
    if issued_at.timestamp() > selected_now.timestamp() + _CLOCK_SKEW_SECONDS:
        raise LicenseValidationError("Activation time is not valid yet.", code="license_not_yet_valid")
    if expires_at is not None and selected_now >= expires_at:
        raise LicenseValidationError("Activation has expired.", code="license_expired")
    license_id = payload.get("license_id")
    edition = payload.get("edition")
    features = payload.get("features")
    customer = payload.get("customer_reference")
    if (
        not isinstance(license_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", license_id)
        or not isinstance(edition, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,31}", edition)
        or not isinstance(features, list)
        or not features
        or any(not isinstance(item, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,31}", item) for item in features)
        or (customer is not None and not isinstance(customer, str))
    ):
        raise LicenseValidationError("Activation claims are invalid.", code="license_claims_invalid")
    return VerifiedLicense(
        license_id=license_id,
        key_id=key_id,
        device_fingerprint=fingerprint,
        issued_at=issued_at,
        expires_at=expires_at,
        edition=edition,
        features=tuple(features),
        customer_reference=customer,
    )


class DataProtector(Protocol):
    def protect(self, payload: bytes) -> bytes: ...

    def unprotect(self, payload: bytes) -> bytes: ...


class WindowsDpapiProtector:
    """Windows user-scoped DPAPI wrapper for the signed activation code."""

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    def __init__(self, *, entropy: bytes = b"eitaa-bridge-office-license-v1") -> None:
        self.entropy = bytes(entropy)

    @classmethod
    def _blob(cls, payload: bytes) -> tuple["WindowsDpapiProtector._Blob", Any]:
        buffer = ctypes.create_string_buffer(payload)
        blob = cls._Blob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        return blob, buffer

    def protect(self, payload: bytes) -> bytes:
        if os.name != "nt":
            raise OSError("DPAPI is available only on Windows")
        source, source_buffer = self._blob(payload)
        entropy, entropy_buffer = self._blob(self.entropy)
        output = self._Blob()
        _ = (source_buffer, entropy_buffer)
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source),
            "Eitaa Bridge activation",
            ctypes.byref(entropy),
            None,
            None,
            0x1,
            ctypes.byref(output),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output.pbData)

    def unprotect(self, payload: bytes) -> bytes:
        if os.name != "nt":
            raise OSError("DPAPI is available only on Windows")
        source, source_buffer = self._blob(payload)
        entropy, entropy_buffer = self._blob(self.entropy)
        output = self._Blob()
        _ = (source_buffer, entropy_buffer)
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0x1,
            ctypes.byref(output),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output.pbData)


class LicenseStore:
    def __init__(self, path: Path, *, protector: DataProtector | None = None) -> None:
        self.path = Path(path)
        self.protector = protector or WindowsDpapiProtector()

    def save(self, activation_code: str) -> None:
        raw = str(activation_code).strip().encode("utf-8")
        if not raw or len(raw) > _MAX_CODE_LENGTH:
            raise LicenseValidationError("Activation code is invalid.", code="license_code_invalid")
        try:
            protected = self.protector.protect(raw)
        except Exception as exc:
            raise LicenseValidationError(
                "Activation could not be protected on this device.",
                code="license_store_write_failed",
            ) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        if temporary.exists():
            raise LicenseValidationError(
                "A previous activation write requires review.",
                code="license_store_temporary_exists",
            )
        try:
            with temporary.open("xb") as stream:
                stream.write(STORE_MAGIC + protected)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception as exc:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise LicenseValidationError(
                "Activation could not be saved.",
                code="license_store_write_failed",
            ) from exc

    def load(self) -> str:
        try:
            stored = self.path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise LicenseValidationError(
                "Activation storage could not be read.",
                code="license_store_unreadable",
            ) from exc
        if not stored.startswith(STORE_MAGIC):
            raise LicenseValidationError(
                "Activation storage belongs to another device or is damaged.",
                code="license_store_unreadable",
            )
        try:
            raw = self.protector.unprotect(stored[len(STORE_MAGIC) :])
            selected = raw.decode("utf-8").strip()
        except Exception as exc:
            raise LicenseValidationError(
                "Activation storage belongs to another device or is damaged.",
                code="license_store_unreadable",
            ) from exc
        if not selected or len(selected) > _MAX_CODE_LENGTH:
            raise LicenseValidationError("Activation storage is invalid.", code="license_store_unreadable")
        return selected


def installation_requires_license(root: Path) -> bool:
    selected_root = Path(root).expanduser().resolve()
    marker = selected_root / "license-policy.json"
    if marker.is_file():
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return True
        return not (
            isinstance(payload, dict)
            and payload.get("format") == POLICY_FORMAT
            and payload.get("required") is False
        )
    return (
        (selected_root / "python" / "python.exe").is_file()
        and (selected_root / "python-packages").is_dir()
    )


class LicenseManager:
    def __init__(
        self,
        root: Path,
        *,
        public_keys: Mapping[str, bytes] | None = None,
        fingerprint_provider=current_device_fingerprint,
        protector: DataProtector | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.public_keys = dict(DEFAULT_PUBLIC_KEYS if public_keys is None else public_keys)
        self.fingerprint_provider = fingerprint_provider
        self.store = LicenseStore(
            self.root / "data" / "licensing" / "activation.dat",
            protector=protector,
        )

    def request_code(self) -> str:
        return encode_request_code(self.fingerprint_provider())

    def status(self, *, now: datetime | None = None) -> LicenseStatus:
        if not self.public_keys:
            return LicenseStatus(False, "license_public_key_missing")
        try:
            activation_code = self.store.load()
        except FileNotFoundError:
            return LicenseStatus(False, "license_activation_required")
        except LicenseValidationError as exc:
            return LicenseStatus(False, exc.code)
        try:
            verified = verify_activation_code(
                activation_code,
                expected_device_fingerprint=self.fingerprint_provider(),
                public_keys=self.public_keys,
                now=now,
            )
        except LicenseValidationError as exc:
            return LicenseStatus(False, exc.code)
        return LicenseStatus(True, "license_valid", verified)

    def activate(self, activation_code: str, *, now: datetime | None = None) -> VerifiedLicense:
        if not self.public_keys:
            raise LicenseValidationError(
                "No product activation key is configured.",
                code="license_public_key_missing",
            )
        fingerprint = self.fingerprint_provider()
        verified = verify_activation_code(
            activation_code,
            expected_device_fingerprint=fingerprint,
            public_keys=self.public_keys,
            now=now,
        )
        self.store.save(activation_code)
        persisted = self.status(now=now)
        if not persisted.licensed or persisted.license is None:
            raise LicenseValidationError(
                "Activation could not be verified after saving.",
                code="license_store_verification_failed",
            )
        return persisted.license

    def enforce(self) -> VerifiedLicense | None:
        if not installation_requires_license(self.root):
            return None
        status = self.status()
        if not status.licensed or status.license is None:
            raise LicenseValidationError(
                "This installation requires device activation.",
                safe_context={"reason_code": status.reason_code},
                code=status.reason_code,
            )
        return status.license


def enforce_installed_license(root: Path) -> VerifiedLicense | None:
    return LicenseManager(root).enforce()

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _key_pair() -> tuple[Ed25519PrivateKey, bytes]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, public_key


class _TestProtector:
    prefix = b"protected-for-this-device:"

    def protect(self, payload: bytes) -> bytes:
        return self.prefix + base64.urlsafe_b64encode(payload)

    def unprotect(self, payload: bytes) -> bytes:
        if not payload.startswith(self.prefix):
            raise ValueError("wrong device")
        return base64.urlsafe_b64decode(payload[len(self.prefix) :])


def test_request_code_is_stable_and_does_not_expose_raw_hardware_values() -> None:
    from eitaa_bridge.licensing import (
        decode_request_code,
        device_fingerprint_from_components,
        encode_request_code,
    )

    components = {
        "machine_guid": "machine-guid-private-value",
        "system_volume_serial": "volume-private-value",
        "firmware_uuid": "firmware-private-value",
    }
    fingerprint = device_fingerprint_from_components(components)
    repeated = device_fingerprint_from_components(dict(reversed(tuple(components.items()))))
    request_code = encode_request_code(fingerprint)
    decoded = decode_request_code(request_code)

    assert repeated == fingerprint
    assert decoded.device_fingerprint == fingerprint
    assert decoded.product_id == "eitaa-bridge-office"
    assert decoded.fingerprint_version == 1
    for raw_value in components.values():
        assert raw_value not in request_code
        assert raw_value not in json.dumps(decoded.safe_summary())


def test_request_code_rejects_typo_or_tampering() -> None:
    from eitaa_bridge.licensing import LicenseValidationError, decode_request_code

    with pytest.raises(LicenseValidationError) as error:
        decode_request_code("EBRQ1.eyJkZXZpY2UiOiJmYWtlIn0.invalid")

    assert error.value.code == "license_request_invalid"


def test_signed_activation_is_device_bound_and_tamper_evident() -> None:
    from eitaa_bridge.licensing import (
        LicenseValidationError,
        encode_request_code,
        issue_activation_code,
        verify_activation_code,
    )

    private_key, public_key = _key_pair()
    now = datetime(2026, 8, 28, 8, 30, tzinfo=timezone.utc)
    request_code = encode_request_code("a" * 64)
    activation_code = issue_activation_code(
        request_code,
        private_key=private_key,
        key_id="test-key",
        issued_at=now,
        license_id="license-test-001",
        customer_reference="customer-opaque",
    )

    verified = verify_activation_code(
        activation_code,
        expected_device_fingerprint="a" * 64,
        public_keys={"test-key": public_key},
        now=now + timedelta(days=1),
    )
    assert verified.license_id == "license-test-001"
    assert verified.customer_reference == "customer-opaque"
    assert verified.expires_at is None

    with pytest.raises(LicenseValidationError) as moved:
        verify_activation_code(
            activation_code,
            expected_device_fingerprint="b" * 64,
            public_keys={"test-key": public_key},
            now=now,
        )
    assert moved.value.code == "license_device_mismatch"

    pieces = activation_code.split(".")
    pieces[1] = pieces[1][:-1] + ("A" if pieces[1][-1] != "A" else "B")
    with pytest.raises(LicenseValidationError):
        verify_activation_code(
            ".".join(pieces),
            expected_device_fingerprint="a" * 64,
            public_keys={"test-key": public_key},
            now=now,
        )


def test_expired_activation_is_rejected() -> None:
    from eitaa_bridge.licensing import (
        LicenseValidationError,
        encode_request_code,
        issue_activation_code,
        verify_activation_code,
    )

    private_key, public_key = _key_pair()
    issued_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    activation_code = issue_activation_code(
        encode_request_code("c" * 64),
        private_key=private_key,
        key_id="expiry-key",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(days=2),
    )

    with pytest.raises(LicenseValidationError) as expired:
        verify_activation_code(
            activation_code,
            expected_device_fingerprint="c" * 64,
            public_keys={"expiry-key": public_key},
            now=issued_at + timedelta(days=3),
        )
    assert expired.value.code == "license_expired"


def test_protected_license_store_is_atomic_and_rejects_copied_blob(tmp_path: Path) -> None:
    from eitaa_bridge.licensing import LicenseStore, LicenseValidationError

    path = tmp_path / "data" / "licensing" / "activation.dat"
    store = LicenseStore(path, protector=_TestProtector())
    activation_code = "EBLC1.payload.signature"
    store.save(activation_code)

    assert activation_code.encode("utf-8") not in path.read_bytes()
    assert store.load() == activation_code
    assert not path.with_suffix(".dat.tmp").exists()

    path.write_bytes(b"copied-from-another-device")
    with pytest.raises(LicenseValidationError) as copied:
        store.load()
    assert copied.value.code == "license_store_unreadable"


def test_installed_runtime_detection_is_fail_closed_without_license(tmp_path: Path) -> None:
    from eitaa_bridge.licensing import installation_requires_license

    assert installation_requires_license(tmp_path) is False
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "python.exe").write_bytes(b"")
    (tmp_path / "python-packages").mkdir()
    assert installation_requires_license(tmp_path) is True

    marker_root = tmp_path / "explicit"
    marker_root.mkdir()
    (marker_root / "license-policy.json").write_text(
        '{"format":"eitaa-bridge-license-policy-v1","required":true}\n',
        encoding="utf-8",
    )
    assert installation_requires_license(marker_root) is True


def test_application_api_fails_before_config_or_database_on_unlicensed_install(tmp_path: Path) -> None:
    from eitaa_bridge.application.api import BridgeApplicationApi
    from eitaa_bridge.licensing import LicenseValidationError

    (tmp_path / "license-policy.json").write_text(
        '{"format":"eitaa-bridge-license-policy-v1","required":true}\n',
        encoding="utf-8",
    )
    with pytest.raises(LicenseValidationError) as blocked:
        BridgeApplicationApi(tmp_path / "bridge.json")

    assert blocked.value.code == "license_activation_required"
    assert not (tmp_path / "data").exists()


def test_office_runtime_checks_activation_before_starting_backend() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts" / "office_runtime.py").read_text(encoding="utf-8")
    builder = (root / "BUILD_OFFICE_SETUP_EXE.bat").read_text(encoding="utf-8").lower()
    package = (root / "package_clean.py").read_text(encoding="utf-8").lower()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8").lower()

    activation_position = content.index("ensure_license_activation()")
    backend_position = content.index("identity = self.ensure_backend()")
    assert activation_position < backend_position
    assert "eitaa_bridge.interfaces.license_activation" in content
    assert "license-policy.json" in builder
    assert "cryptography==46.0.7" in builder
    assert "cryptography==46.0.7" in pyproject
    assert "cryptography-46.0.7-cp311-abi3-win_amd64.whl" in package
    assert "license-signing-key" not in builder


def test_activation_ui_normalizes_clipboard_formatting_and_has_layout_independent_controls() -> None:
    from eitaa_bridge.interfaces.license_activation import normalize_activation_code_input

    pasted = "\u200f EBLC1.payload.\r\n signature \u200c"
    assert normalize_activation_code_input(pasted) == "EBLC1.payload.signature"

    root = Path(__file__).resolve().parents[1]
    content = (root / "src" / "eitaa_bridge" / "interfaces" / "license_activation.py").read_text(
        encoding="utf-8"
    )
    assert "جای‌گذاری از کلیپ‌بورد" in content
    assert 'keycode == 86' in content
    assert 'keycode == 67' in content
    assert 'keycode == 65' in content
    assert '"<Button-3>"' in content


def test_release_scope_never_contains_admin_private_key_material() -> None:
    import package_clean

    root = Path(__file__).resolve().parents[1]
    selected = {path.relative_to(root).as_posix() for path in package_clean.collect_release_files(root)}

    assert not any(path.startswith("tools/") for path in selected)
    assert not any("private" in path.lower() and "key" in path.lower() for path in selected)


def test_packaged_verifier_contains_public_key_only() -> None:
    from eitaa_bridge.licensing import DEFAULT_PUBLIC_KEYS

    assert DEFAULT_PUBLIC_KEYS
    assert all(key_id.startswith("eb-") for key_id in DEFAULT_PUBLIC_KEYS)
    assert all(len(public_key) == 32 for public_key in DEFAULT_PUBLIC_KEYS.values())

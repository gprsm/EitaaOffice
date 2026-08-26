from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    ProtectedPhone,
    SafeCoordinatorAuditService,
)
from eitaa_bridge.infrastructure.diagnostics import (
    BridgeDiagnosticManager,
    RuntimeLogger,
)


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_E164 = "+999123456789"
SYNTHETIC_BEARER = "g04d" + "x" * 28


def _assert_private_markers_absent(encoded: str) -> None:
    if SYNTHETIC_E164 in encoded or SYNTHETIC_BEARER in encoded:
        pytest.fail(
            "A G-04-D privacy channel retained a synthetic private marker.",
            pytrace=False,
        )


def _hostile_fields() -> dict[str, object]:
    return {
        "phone_hint": SYNTHETIC_E164,
        "identity_hint": f"candidate={SYNTHETIC_E164}",
        "opaque_header": f"Bearer {SYNTHETIC_BEARER}",
        "nested": [{"unclassified_value": f"selected={SYNTHETIC_E164}"}],
    }


def _bootstrap(database: CoordinatorDatabase):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"g04d-protected-phone",
            key_version=1,
            fingerprint="d" * 64,
            display_hint=SYNTHETIC_E164,
        ),
        display_name="G-04-D administrator",
        backup_name="g04d-verified.zip",
        source_manifest_sha256="e" * 64,
        source_file_count=4,
        source_total_bytes=4096,
    )


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_g04d_runtime_log_redacts_nested_unknown_identity_and_bearer(tmp_path):
    path = tmp_path / "application.jsonl"
    logger = RuntimeLogger(path, source="test")
    try:
        logger.emit(
            "renderer_error_reported",
            level="error",
            result="failed",
            reason_code="renderer_unhandled_error",
            fields=_hostile_fields(),
        )
    finally:
        logger.close()

    _assert_private_markers_absent(path.read_text(encoding="utf-8"))


def test_g04d_diagnostic_redacts_nested_unknown_identity_and_bearer(tmp_path):
    manager = BridgeDiagnosticManager(tmp_path / "diagnostics")
    manager.emit(
        "application",
        "g04d_privacy_probe",
        level="warning",
        fields=_hostile_fields(),
    )

    _assert_private_markers_absent(
        manager.file_for("application").read_text(encoding="utf-8")
    )


def test_g04d_audit_persistence_query_and_export_redact_identity_hints(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    account = _bootstrap(database)
    database.audit_messenger_auth_event(
        account.messenger_account_id,
        action="eitaa.auth.g04d.denied",
        result="denied",
        reason_code="g04d_privacy_probe",
        actor_app_user_id=account.app_user_id,
        actor_global_role="admin",
        request_id=str(uuid4()),
        safe_metadata={
            "display_hint": SYNTHETIC_E164,
            "identity_hint": f"candidate={SYNTHETIC_E164}",
            "opaque_header": f"Bearer {SYNTHETIC_BEARER}",
        },
    )

    with sqlite3.connect(database.path) as connection:
        stored_metadata = connection.execute(
            "SELECT safe_metadata_json FROM audit_events "
            "WHERE action='eitaa.auth.g04d.denied'"
        ).fetchone()[0]
    service = SafeCoordinatorAuditService(database)
    page = service.query(
        app_user_id=account.app_user_id,
        global_role="admin",
        action_prefix="eitaa.auth.g04d",
    )
    exported = service.export_jsonl(
        app_user_id=account.app_user_id,
        global_role="admin",
        output_directory=tmp_path / "exports",
        action_prefix="eitaa.auth.g04d",
    )
    combined = "\n".join(
        (
            stored_metadata,
            json.dumps(page.safe_summary(), ensure_ascii=False),
            exported.path.read_text(encoding="utf-8"),
        )
    )
    _assert_private_markers_absent(combined)


def test_g04d_support_bundle_redacts_global_e164_across_all_inputs(
    tmp_path,
    monkeypatch,
):
    runtime_state = _load_script(
        "g04d_runtime_state",
        ROOT / "scripts" / "runtime_state.py",
    )
    monkeypatch.setitem(sys.modules, "runtime_state", runtime_state)
    bundle_module = _load_script(
        "g04d_create_bundle",
        ROOT / "scripts" / "create_diagnostics_bundle.py",
    )
    scanner = _load_script(
        "g04d_scan_bundle",
        ROOT / "scripts" / "scan_diagnostics_bundle.py",
    )
    installation = tmp_path / "installation"
    installation.mkdir()
    (installation / "bridge.json").write_text(
        json.dumps(_hostile_fields()),
        encoding="utf-8",
    )
    database = CoordinatorDatabase(
        installation / "data" / "coordinator" / "coordinator.sqlite3"
    )
    account = _bootstrap(database)
    runtime_log = installation / "runtime" / "logs" / "application.jsonl"
    runtime_log.parent.mkdir(parents=True)
    runtime_log.write_text(json.dumps(_hostile_fields()) + "\n", encoding="utf-8")
    diagnostic_log = (
        installation / "diagnostics" / "bridge" / "g04d" / "application.jsonl"
    )
    diagnostic_log.parent.mkdir(parents=True)
    diagnostic_log.write_text(
        json.dumps(_hostile_fields()) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "support.zip"
    monkeypatch.setattr(bundle_module, "project_root", lambda: installation)
    monkeypatch.setattr(bundle_module, "load_version", lambda _root: "test")
    monkeypatch.setattr(bundle_module, "run_doctor", lambda _root: "doctor-safe")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_diagnostics_bundle.py",
            "--output",
            str(output),
            "--messenger-account-id",
            account.messenger_account_id,
        ],
    )
    if bundle_module.main() != 0:
        pytest.fail("The isolated G-04-D support bundle was not created.", pytrace=False)
    result = scanner.scan_bundle(output)
    if not result["verified"]:
        pytest.fail("The isolated G-04-D support bundle did not pass its scanner.", pytrace=False)
    with ZipFile(output) as archive:
        combined = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in archive.namelist()
        )
    _assert_private_markers_absent(combined)


def test_g04d_support_bundle_scanner_detects_global_e164_under_unknown_key(tmp_path):
    scanner = _load_script(
        "g04d_scan_bundle_adversarial",
        ROOT / "scripts" / "scan_diagnostics_bundle.py",
    )
    unsafe = tmp_path / "unsafe-support.zip"
    with ZipFile(unsafe, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "logs/application.jsonl",
            json.dumps({"identity_hint": f"candidate={SYNTHETIC_E164}"}) + "\n",
        )
    result = scanner.scan_bundle(unsafe)
    kinds = {item["kind"] for item in result["findings"]}
    if "full_phone" not in kinds:
        pytest.fail(
            "The support-bundle scanner missed a global canonical phone value.",
            pytrace=False,
        )

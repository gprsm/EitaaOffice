from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import warnings
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_backup_verifies_manifest_and_excludes_staging(tmp_path, monkeypatch):
    scripts = PROJECT_ROOT / "scripts"
    runtime_state = load_script("runtime_state", scripts / "runtime_state.py")
    backup_runtime = load_script("backup_runtime_under_test", scripts / "backup_runtime.py")
    root = tmp_path / "installation"
    (root / "data" / "safe").mkdir(parents=True)
    (root / "data" / "safe" / "value.bin").write_bytes(b"safe")
    (root / "data" / "safe" / "ignored.tmp").write_bytes(b"temporary")
    (root / "data" / "accounts" / ".staging-test").mkdir(parents=True)
    (root / "data" / "accounts" / ".staging-test" / "secret.bin").write_bytes(b"staged")
    (root / "bridge.json").write_text("{}", encoding="utf-8")
    (root / "VERSION.txt").write_text("Product: test\n", encoding="utf-8")
    monkeypatch.setattr(backup_runtime, "project_root", lambda: root)

    backup = backup_runtime.create_backup(output=root / "backups" / "test")
    manifest = runtime_state.verify_backup(backup)
    paths = {item["path"] for item in manifest["files"]}
    assert "data/safe/value.bin" in paths
    assert "data/safe/ignored.tmp" not in paths
    assert not any(".staging-test" in path for path in paths)


def test_runtime_backup_verifier_rejects_modified_member(tmp_path):
    runtime_state = load_script(
        "runtime_state_tamper_test",
        PROJECT_ROOT / "scripts" / "runtime_state.py",
    )
    backup = tmp_path / "tampered.zip"
    manifest = {
        "format": runtime_state.PRODUCT_MARKER,
        "product_version": "test",
        "include_media": True,
        "include_logs": False,
        "file_count": 1,
        "files": [{"path": "data/value.bin", "size": 4, "sha256": "0" * 64}],
    }
    with ZipFile(backup, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("state/data/value.bin", b"safe")
        archive.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="checksum"):
        runtime_state.verify_backup(backup)


def test_runtime_backup_verifier_rejects_duplicate_archive_member(tmp_path):
    runtime_state = load_script(
        "runtime_state_duplicate_test",
        PROJECT_ROOT / "scripts" / "runtime_state.py",
    )
    backup = tmp_path / "duplicate.zip"
    payload = b"safe"
    import hashlib

    manifest = {
        "format": runtime_state.PRODUCT_MARKER,
        "product_version": "test",
        "include_media": False,
        "include_logs": False,
        "file_count": 1,
        "files": [
            {
                "path": "data/value.bin",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(backup, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("state/data/value.bin", payload)
            archive.writestr("state/data/value.bin", payload)
            archive.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="duplicate member"):
        runtime_state.verify_backup(backup)


def test_restore_dry_run_and_copy_rehearsal_are_verified_and_recoverable(tmp_path, monkeypatch):
    scripts = PROJECT_ROOT / "scripts"
    runtime_state = load_script("runtime_state_restore_test", scripts / "runtime_state.py")
    monkeypatch.setitem(sys.modules, "runtime_state", runtime_state)
    backup_runtime = load_script("backup_runtime_restore_test", scripts / "backup_runtime.py")
    restore_runtime = load_script("restore_runtime_under_test", scripts / "restore_runtime.py")
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "data" / "coordinator").mkdir(parents=True)
    target.mkdir()
    (source / "bridge.json").write_text('{"safe":"original"}', encoding="utf-8")
    (source / ".eitaa_session.json").write_text('{"format":1}', encoding="utf-8")
    (source / "data" / "contacts.sqlite3").write_bytes(b"contact-copy")
    (source / "data" / "coordinator" / "coordinator.sqlite3").write_bytes(b"coordinator-copy")
    (source / "VERSION.txt").write_text("Product: test\n", encoding="utf-8")
    monkeypatch.setattr(backup_runtime, "project_root", lambda: source)
    backup = backup_runtime.create_backup(output=tmp_path / "backup.zip")

    preview = restore_runtime.dry_run_backup(backup)
    result = restore_runtime.restore_backup(backup, root=target)

    assert preview["verified"] is True
    assert preview["file_count"] == 4
    assert result["restored"] is True
    assert result["file_count"] == preview["file_count"]
    assert (target / "bridge.json").read_text(encoding="utf-8") == '{"safe":"original"}'
    assert (target / ".eitaa_session.json").read_text(encoding="utf-8") == '{"format":1}'
    assert (target / "data" / "contacts.sqlite3").read_bytes() == b"contact-copy"
    assert (
        target / "data" / "coordinator" / "coordinator.sqlite3"
    ).read_bytes() == b"coordinator-copy"


def test_restore_failure_rolls_back_already_replaced_copy_files(tmp_path, monkeypatch):
    scripts = PROJECT_ROOT / "scripts"
    runtime_state = load_script("runtime_state_rollback_test", scripts / "runtime_state.py")
    monkeypatch.setitem(sys.modules, "runtime_state", runtime_state)
    backup_runtime = load_script("backup_runtime_rollback_test", scripts / "backup_runtime.py")
    restore_runtime = load_script("restore_runtime_rollback_test", scripts / "restore_runtime.py")
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "bridge.json").write_text('{"new":true}', encoding="utf-8")
    (source / ".eitaa_session.json").write_text('{"format":1}', encoding="utf-8")
    (source / "VERSION.txt").write_text("Product: test\n", encoding="utf-8")
    (target / "bridge.json").write_text('{"old":true}', encoding="utf-8")
    backup = backup_runtime.create_backup(output=tmp_path / "rollback.zip", root=source)
    original_copy2 = restore_runtime.shutil.copy2

    def fail_second_restore(source_path, destination_path, *args, **kwargs):
        if ".eitaa_session.json.restore-" in str(destination_path):
            raise OSError("injected copy failure")
        return original_copy2(source_path, destination_path, *args, **kwargs)

    monkeypatch.setattr(restore_runtime.shutil, "copy2", fail_second_restore)
    with pytest.raises(OSError, match="injected copy failure"):
        restore_runtime.restore_backup(backup, root=target)

    assert (target / "bridge.json").read_text(encoding="utf-8") == '{"old":true}'
    assert not (target / ".eitaa_session.json").exists()

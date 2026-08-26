from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from eitaa_bridge.errors import CoordinatorMigrationError, CoordinatorPreflightError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    LegacyMigrationService,
    ProtectedPhone,
)


def write_config(root: Path, *, enabled: bool = False, database: Path | None = None) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "test-site",
        "bridge": {
            "diagnostics_root": "diagnostics/bridge",
            "diagnostics_enabled": False,
        },
        "features": {"multi_session": {"enabled": enabled}},
        "core": {
            "session_file": ".eitaa_session.json",
            "database_file": (
                str(database) if database is not None else "data/eitaa_messages.sqlite3"
            ),
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": False,
            "timeout_seconds": 30,
        },
        "wordpress_sites": [
            {
                "site_key": "test-site",
                "base_url": "https://example.test",
                "default_status": "draft",
                "default_category_id": None,
                "verify_tls": True,
                "username_env": "TEST_WP_USER",
                "application_password_env": "TEST_WP_PASSWORD",
            }
        ],
    }
    path = root / "bridge.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def legacy_root(tmp_path: Path) -> tuple[Path, LegacyMigrationService]:
    root = tmp_path / "installation"
    data = root / "data"
    media = data / "media"
    media.mkdir(parents=True)
    (root / ".eitaa_session.json").write_text(
        json.dumps({"format": 1, "state": "test-only"}),
        encoding="utf-8",
    )
    with sqlite3.connect(data / "eitaa_messages.sqlite3") as connection:
        connection.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, safe_value TEXT)")
        connection.execute("INSERT INTO messages(safe_value) VALUES('test-only')")
    (media / "sample.bin").write_bytes(b"sample-media")
    (data / "ui-peers").mkdir()
    (data / "ui-peers" / "catalog.json").write_text("{}", encoding="utf-8")
    (data / "eitaa-contact-peers").mkdir()
    (data / "eitaa-contact-peers" / "peer.json").write_text("{}", encoding="utf-8")
    config_path = write_config(root)
    config = BridgeConfigLoader.load(config_path)
    return root, LegacyMigrationService(root, config)


def test_preflight_is_read_only_and_reports_safe_counts(tmp_path):
    root, service = legacy_root(tmp_path)
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    report = service.preflight()
    after = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert report.ok is True
    assert report.source_file_count >= 5
    assert report.source_total_bytes > 0
    assert before == after
    assert all("phone" not in item["name"] for item in report.safe_summary()["checks"])


def test_preflight_fails_closed_when_feature_is_enabled(tmp_path):
    root, _ = legacy_root(tmp_path)
    config_path = write_config(root, enabled=True)
    service = LegacyMigrationService(root, BridgeConfigLoader.load(config_path))
    report = service.preflight()
    assert report.ok is False
    assert "feature_flag_must_be_disabled" in {
        item.code for item in report.checks if not item.ok
    }


def test_preflight_fails_closed_when_runtime_is_active(tmp_path, monkeypatch):
    _, service = legacy_root(tmp_path)
    monkeypatch.setattr(service, "_runtime_active", lambda: True)
    report = service.preflight()
    assert report.ok is False
    assert "legacy_runtime_active" in {
        item.code for item in report.checks if not item.ok
    }


def test_preflight_rejects_core_database_outside_installation(tmp_path):
    root, _ = legacy_root(tmp_path)
    outside = tmp_path / "outside.sqlite3"
    with sqlite3.connect(outside) as connection:
        connection.execute("CREATE TABLE sample(id INTEGER)")
    config_path = write_config(root, database=outside)
    service = LegacyMigrationService(root, BridgeConfigLoader.load(config_path))
    with pytest.raises(CoordinatorPreflightError) as error:
        service.preflight()
    assert error.value.code == "legacy_source_outside_installation"


def test_migration_requires_explicit_operator_confirmation(tmp_path):
    _, service = legacy_root(tmp_path)
    with pytest.raises(CoordinatorMigrationError) as error:
        service.migrate(
            protected_phone=ProtectedPhone(b"cipher", 1, "1" * 64, "+••••67"),
            display_name="Administrator",
            backup_name="backup.zip",
            backup_manifest_sha256="a" * 64,
            operator_confirmed=False,
        )
    assert error.value.code == "legacy_account_confirmation_required"


def test_copy_verify_migration_preserves_legacy_and_keeps_feature_off(tmp_path):
    root, service = legacy_root(tmp_path)
    legacy_session = (root / ".eitaa_session.json").read_bytes()
    legacy_database = (root / "data" / "eitaa_messages.sqlite3").read_bytes()
    result = service.migrate(
        protected_phone=ProtectedPhone(b"ciphertext", 1, "1" * 64, "+••••67"),
        display_name="Administrator",
        backup_name="verified-backup.zip",
        backup_manifest_sha256="b" * 64,
        operator_confirmed=True,
    )

    assert (root / ".eitaa_session.json").read_bytes() == legacy_session
    assert (root / "data" / "eitaa_messages.sqlite3").read_bytes() == legacy_database
    account = result.account_directory
    assert (account / "provider" / "session" / "eitaa_session.json").read_bytes() == legacy_session
    assert (account / "core" / "messages.sqlite3").read_bytes() == legacy_database
    assert (account / "media" / "sample.bin").read_bytes() == b"sample-media"
    assert result.manifest_file.is_file()
    assert result.safe_summary()["feature_enabled"] is False
    summary = CoordinatorDatabase(result.coordinator_database).safe_summary()
    assert summary["latest_migration"]["status"] == "activated"
    assert summary["counts"]["messenger_accounts"] == 1
    assert not any(path.name.startswith(".staging-") for path in account.parent.iterdir())


def test_rollback_preserves_both_legacy_and_migrated_data(tmp_path):
    root, service = legacy_root(tmp_path)
    result = service.migrate(
        protected_phone=ProtectedPhone(b"ciphertext", 1, "1" * 64, "+••••67"),
        display_name="Administrator",
        backup_name="verified-backup.zip",
        backup_manifest_sha256="b" * 64,
        operator_confirmed=True,
    )
    rollback = service.rollback(
        result.bootstrap.migration_id,
        operator_confirmed=True,
    )
    assert rollback["data_deleted"] is False
    assert (root / ".eitaa_session.json").is_file()
    assert (root / "data" / "eitaa_messages.sqlite3").is_file()
    assert not result.account_directory.exists()
    assert (result.account_directory.parent / rollback["preserved_account_directory_name"]).is_dir()
    assert not result.coordinator_database.exists()
    assert (
        result.coordinator_database.parent / rollback["preserved_database_name"]
    ).is_file()

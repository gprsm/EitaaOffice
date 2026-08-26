from __future__ import annotations

import json

import pytest

import eitaa_bridge.infrastructure.config.deployment_settings as deployment_settings_module
from eitaa_bridge.errors import BridgeConfigurationError
from eitaa_bridge.infrastructure.config import (
    BridgeConfigLoader,
    DeploymentPortSettings,
)


def test_desktop_port_update_is_atomic_validated_and_keeps_one_source_of_truth(
    config_file,
):
    settings = DeploymentPortSettings(config_file)

    before = settings.details()
    assert before == {
        "mode": "desktop_loopback",
        "bind_host": "127.0.0.1",
        "bind_port": 8765,
        "restart_required": False,
        "proxy_update_required": False,
    }

    after = settings.update_port(9123, confirm=True)

    assert after["bind_port"] == 9123
    assert after["restart_required"] is True
    assert after["proxy_update_required"] is False
    persisted = json.loads(config_file.read_text(encoding="utf-8"))
    assert persisted["deployment"]["bind"]["port"] == 9123
    assert persisted["deployment"]["allowed_hosts"] == [
        "127.0.0.1:9123",
        "localhost:9123",
    ]
    assert persisted["deployment"]["allowed_origins"] == [
        "http://127.0.0.1:9123",
        "http://localhost:9123",
    ]
    assert BridgeConfigLoader.load(config_file).deployment.bind_port == 9123
    assert len(list((config_file.parent / "backups" / "settings").glob("bridge.*.json"))) == 1
    assert not config_file.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    ("port", "expected_code"),
    [
        (0, "deployment_bind_port_invalid"),
        (65536, "deployment_bind_port_invalid"),
        (443, "deployment_plain_http_443_forbidden"),
        (True, "deployment_bind_port_not_integer"),
    ],
)
def test_invalid_or_unconfirmed_port_never_changes_configuration(
    config_file,
    port,
    expected_code,
):
    settings = DeploymentPortSettings(config_file)
    original = config_file.read_bytes()

    with pytest.raises(BridgeConfigurationError) as error:
        settings.update_port(port, confirm=True)

    assert error.value.code == expected_code
    assert config_file.read_bytes() == original
    assert not (config_file.parent / "backups").exists()

    with pytest.raises(BridgeConfigurationError) as confirmation_error:
        settings.update_port(9123, confirm=False)
    assert confirmation_error.value.code == "deployment_port_confirmation_required"
    assert config_file.read_bytes() == original


def test_reverse_proxy_port_update_preserves_public_host_and_origin(
    config_file,
):
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 525_600,
            "absolute_timeout_hours": 8_760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        }
    }
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "web_reverse_proxy",
        "bind": {"host": "127.0.0.1", "port": 8765},
        "allowed_hosts": ["bridge.example.test"],
        "allowed_origins": ["https://bridge.example.test"],
        "allowed_private_client_cidrs": [],
        "cleartext_http_risk_acknowledgement": None,
        "private_lan_only_acknowledgement": None,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "secure_cookie": True,
        "limits": {
            "max_json_body_bytes": 1024,
            "max_upload_bytes": 2048,
            "request_timeout_seconds": 5,
            "requests_per_minute": 240,
            "uploads_per_minute": 12,
            "shutdown_grace_seconds": 2,
        },
        "reverse_proxy": {
            "enabled": True,
            "trusted_proxy_cidrs": ["127.0.0.0/8", "::1/128"],
            "required_forwarded_proto": "https",
            "require_forwarded_for": True,
        },
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    result = DeploymentPortSettings(config_file).update_port(9124, confirm=True)

    persisted = json.loads(config_file.read_text(encoding="utf-8"))["deployment"]
    assert result["proxy_update_required"] is True
    assert persisted["bind"]["port"] == 9124
    assert persisted["allowed_hosts"] == ["bridge.example.test"]
    assert persisted["allowed_origins"] == ["https://bridge.example.test"]
    assert BridgeConfigLoader.load(config_file).deployment.bind_port == 9124


def test_backup_failure_is_safe_and_never_changes_configuration(
    config_file,
    monkeypatch,
):
    original = config_file.read_bytes()

    def deny_backup(*_args, **_kwargs):
        raise PermissionError("simulated without exposing a path")

    monkeypatch.setattr(deployment_settings_module.shutil, "copy2", deny_backup)

    with pytest.raises(BridgeConfigurationError) as error:
        DeploymentPortSettings(config_file).update_port(9123, confirm=True)

    assert error.value.code == "deployment_settings_backup_failed"
    assert error.value.safe_context == {"error_type": "PermissionError"}
    assert config_file.read_bytes() == original

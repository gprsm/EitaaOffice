from __future__ import annotations

import json

import pytest

from eitaa_bridge.errors import BridgeConfigurationError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader


def test_loads_and_resolves_relative_paths(config_file):
    config = BridgeConfigLoader.load(config_file)
    assert config.schema_version == 1
    assert config.core.database_file.is_absolute()
    assert config.site().site_key == "medical-site"
    assert config.features.multi_session.enabled is False
    assert config.features.multi_session.fail_closed_reason is None
    assert config.features.app_user_auth.enabled is False
    assert config.features.app_user_auth.self_registration_enabled is True
    assert config.features.app_user_auth.idle_timeout_minutes == 525_600
    assert config.features.app_user_auth.absolute_timeout_hours == 8_760
    assert config.features.app_user_auth.fail_closed_reason is None
    assert config.deployment.mode == "desktop_loopback"
    assert config.deployment.bind_host == "127.0.0.1"
    assert config.deployment.bind_port == 8765


def test_unknown_site_key_is_typed(config_file):
    config = BridgeConfigLoader.load(config_file)
    with pytest.raises(BridgeConfigurationError):
        config.site("missing")


def test_rejects_duplicate_site_keys(config_file):
    payload = json.loads(config_file.read_text())
    payload["wordpress_sites"].append(dict(payload["wordpress_sites"][0]))
    config_file.write_text(json.dumps(payload))
    with pytest.raises(BridgeConfigurationError):
        BridgeConfigLoader.load(config_file)


def test_rejects_http_production_url(config_file):
    payload = json.loads(config_file.read_text())
    payload["wordpress_sites"][0]["base_url"] = "http://example.test"
    config_file.write_text(json.dumps(payload))
    with pytest.raises(BridgeConfigurationError):
        BridgeConfigLoader.load(config_file)


def test_allows_explicit_localhost_http(config_file):
    payload = json.loads(config_file.read_text())
    site = payload["wordpress_sites"][0]
    site["base_url"] = "http://localhost:8080"
    site["allow_insecure_http"] = True
    config_file.write_text(json.dumps(payload))
    assert BridgeConfigLoader.load(config_file).site().normalized_base_url == "http://localhost:8080"


def test_rejects_bad_schema(config_file):
    payload = json.loads(config_file.read_text())
    payload["schema_version"] = 99
    config_file.write_text(json.dumps(payload))
    with pytest.raises(BridgeConfigurationError):
        BridgeConfigLoader.load(config_file)


def test_allows_explicit_private_lan_http(config_file):
    payload = json.loads(config_file.read_text())
    site = payload["wordpress_sites"][0]
    site["base_url"] = "http://192.168.1.2/wordpress"
    site["allow_insecure_http"] = True
    site["verify_tls"] = False
    config_file.write_text(json.dumps(payload))
    loaded = BridgeConfigLoader.load(config_file).site()
    assert loaded.normalized_base_url == "http://192.168.1.2/wordpress"
    assert loaded.allow_insecure_http is True


def test_rejects_public_ip_http_even_when_explicitly_enabled(config_file):
    payload = json.loads(config_file.read_text())
    site = payload["wordpress_sites"][0]
    site["base_url"] = "http://8.8.8.8/wordpress"
    site["allow_insecure_http"] = True
    config_file.write_text(json.dumps(payload))
    with pytest.raises(BridgeConfigurationError):
        BridgeConfigLoader.load(config_file)


def test_multi_session_can_be_configured_but_defaults_to_disabled(config_file):
    payload = json.loads(config_file.read_text())
    payload["features"] = {
        "multi_session": {
            "enabled": True,
            "legacy_default_messenger_account_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        }
    }
    config_file.write_text(json.dumps(payload))
    loaded = BridgeConfigLoader.load(config_file)
    assert loaded.features.multi_session.enabled is True
    assert loaded.features.multi_session.legacy_default_messenger_account_id == (
        "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    )


@pytest.mark.parametrize(
    ("features", "reason"),
    [
        ("invalid", "features_not_object"),
        ({"multi_session": "invalid"}, "multi_session_not_object"),
        ({"multi_session": {"enabled": "yes"}}, "enabled_not_boolean"),
        (
            {
                "multi_session": {
                    "enabled": True,
                    "legacy_default_messenger_account_id": "not-a-uuid",
                }
            },
            "legacy_account_id_invalid",
        ),
    ],
)
def test_multi_session_malformed_configuration_fails_closed(config_file, features, reason):
    payload = json.loads(config_file.read_text())
    payload["features"] = features
    config_file.write_text(json.dumps(payload))
    loaded = BridgeConfigLoader.load(config_file)
    assert loaded.features.multi_session.enabled is False
    assert loaded.features.multi_session.fail_closed_reason == reason


def test_multi_session_environment_switch_can_only_disable(config_file, monkeypatch):
    payload = json.loads(config_file.read_text())
    payload["features"] = {"multi_session": {"enabled": True}}
    config_file.write_text(json.dumps(payload))
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_MULTI_SESSION", "1")
    loaded = BridgeConfigLoader.load(config_file)
    assert loaded.features.multi_session.enabled is False
    assert loaded.features.multi_session.fail_closed_reason == "environment_kill_switch"

    payload["features"]["multi_session"]["enabled"] = False
    config_file.write_text(json.dumps(payload))
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_MULTI_SESSION", "0")
    assert BridgeConfigLoader.load(config_file).features.multi_session.enabled is False


def test_app_user_auth_can_be_configured_but_defaults_to_disabled(config_file):
    payload = json.loads(config_file.read_text())
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": False,
            "idle_timeout_minutes": 45,
            "absolute_timeout_hours": 24,
            "max_failed_attempts": 4,
            "lockout_minutes": 20,
        }
    }
    config_file.write_text(json.dumps(payload))
    loaded = BridgeConfigLoader.load(config_file).features.app_user_auth
    assert loaded.enabled is True
    assert loaded.self_registration_enabled is False
    assert loaded.idle_timeout_minutes == 45
    assert loaded.absolute_timeout_hours == 24
    assert loaded.max_failed_attempts == 4
    assert loaded.lockout_minutes == 20


@pytest.mark.parametrize(
    ("selected", "reason"),
    [
        ("invalid", "app_user_auth_not_object"),
        ({"enabled": "yes"}, "enabled_not_boolean"),
        ({"enabled": True, "self_registration_enabled": "yes"}, "self_registration_enabled_not_boolean"),
        ({"enabled": True, "idle_timeout_minutes": 4}, "idle_timeout_minutes_invalid"),
        ({"enabled": True, "absolute_timeout_hours": 0}, "absolute_timeout_hours_invalid"),
        ({"enabled": True, "max_failed_attempts": 2}, "max_failed_attempts_invalid"),
        ({"enabled": True, "lockout_minutes": 0}, "lockout_minutes_invalid"),
    ],
)
def test_app_user_auth_malformed_configuration_fails_closed(
    config_file,
    selected,
    reason,
):
    payload = json.loads(config_file.read_text())
    payload["features"] = {"app_user_auth": selected}
    config_file.write_text(json.dumps(payload))
    loaded = BridgeConfigLoader.load(config_file).features.app_user_auth
    assert loaded.enabled is False
    assert loaded.fail_closed_reason == reason


def test_app_user_auth_environment_switch_can_only_disable(config_file, monkeypatch):
    payload = json.loads(config_file.read_text())
    payload["features"] = {"app_user_auth": {"enabled": True}}
    config_file.write_text(json.dumps(payload))
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_APP_USER_AUTH", "1")
    loaded = BridgeConfigLoader.load(config_file).features.app_user_auth
    assert loaded.enabled is False
    assert loaded.fail_closed_reason == "environment_kill_switch"

    payload["features"]["app_user_auth"]["enabled"] = False
    config_file.write_text(json.dumps(payload))
    monkeypatch.setenv("BRIDGE_FORCE_DISABLE_APP_USER_AUTH", "0")
    assert BridgeConfigLoader.load(config_file).features.app_user_auth.enabled is False

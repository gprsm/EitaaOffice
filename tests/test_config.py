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

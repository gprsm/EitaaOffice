from __future__ import annotations

import os

import pytest

from eitaa_bridge.errors import BridgeConfigurationError, CredentialError
from eitaa_bridge.infrastructure.config import BridgeConfigLoader, EnvLoader
from eitaa_bridge.infrastructure.wordpress import load_wordpress_credentials


def test_env_loader_reads_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("BRIDGE_TEST_VALUE", raising=False)
    path = tmp_path / ".env"
    path.write_text('BRIDGE_TEST_VALUE="hello world"\n', encoding="utf-8")
    loaded = EnvLoader.load(path)
    assert "BRIDGE_TEST_VALUE" in loaded
    assert os.environ["BRIDGE_TEST_VALUE"] == "hello world"


def test_env_loader_does_not_override_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIDGE_TEST_VALUE", "existing")
    path = tmp_path / ".env"
    path.write_text("BRIDGE_TEST_VALUE=new\n", encoding="utf-8")
    EnvLoader.load(path)
    assert os.environ["BRIDGE_TEST_VALUE"] == "existing"


def test_env_loader_rejects_invalid_line(tmp_path):
    path = tmp_path / ".env"
    path.write_text("not-valid\n", encoding="utf-8")
    with pytest.raises(BridgeConfigurationError):
        EnvLoader.load(path)


def test_credentials_are_loaded_by_configured_names(config_file, monkeypatch):
    config = BridgeConfigLoader.load(config_file)
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "app password")
    credentials = load_wordpress_credentials(config.site())
    assert credentials.username == "editor"


def test_missing_credentials_are_typed(config_file, monkeypatch):
    config = BridgeConfigLoader.load(config_file)
    monkeypatch.delenv("TEST_WP_USERNAME", raising=False)
    monkeypatch.delenv("TEST_WP_APP_PASSWORD", raising=False)
    with pytest.raises(CredentialError) as error:
        load_wordpress_credentials(config.site())
    assert "app password" not in str(error.value).lower()


def test_missing_credentials_can_be_loaded_for_eitaa_only_runtime(config_file, monkeypatch):
    config = BridgeConfigLoader.load(config_file)
    monkeypatch.delenv("TEST_WP_USERNAME", raising=False)
    monkeypatch.delenv("TEST_WP_APP_PASSWORD", raising=False)
    credentials = load_wordpress_credentials(config.site(), required=False)
    assert credentials.safe_summary() == {
        "username_present": False,
        "application_password_present": False,
    }

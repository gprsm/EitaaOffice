from __future__ import annotations

from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.eitaa import CoreBinding


def test_exact_grouped_media_core_contract_is_installed(config_file):
    config = BridgeConfigLoader.load(config_file)
    result = CoreBinding(config.core).assert_compatible()
    assert result.ok
    assert result.product_version == "0.6.0-core7.4.5-gmi1"
    assert result.package_version == "0.6.0.dev19"
    assert result.database_schema == 9
    assert "list_album" in result.message_methods
    assert result.sender_filter is True


def test_required_public_facade_services_are_present(config_file):
    config = BridgeConfigLoader.load(config_file)
    result = CoreBinding(config.core).inspect()
    assert {"messages", "retrieval", "media", "publications", "sync"}.issubset(result.facade_fields)


def test_publication_api_contract_is_present(config_file):
    config = BridgeConfigLoader.load(config_file)
    result = CoreBinding(config.core).inspect()
    required = {"get", "mark_pending", "mark_processing", "mark_published", "mark_failed", "mark_skipped", "list"}
    assert required.issubset(result.publication_methods)


def test_sender_filtered_retrieval_contract_is_present(config_file):
    config = BridgeConfigLoader.load(config_file)
    result = CoreBinding(config.core).inspect()
    assert result.sender_filter is True

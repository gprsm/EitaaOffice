from __future__ import annotations

import ast
from pathlib import Path
import re
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.application.provider_adapter import provider_adapter_catalog
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.providers import (
    ProviderAccountContext,
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    default_provider_registry,
)
from eitaa_bridge.providers.bale import bale_extension_registration
from eitaa_bridge.providers.testing import InMemoryProviderSessionStore


ROOT = Path(__file__).resolve().parents[1]


def _account() -> ProviderAccountContext:
    return ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider="bale",
        storage_revision=1,
        session_generation=1,
    )


def test_bale_manifest_preserves_authorization_decision_and_activates_contract() -> None:
    registration = bale_extension_registration()
    manifest = registration.manifest

    assert manifest.implementation_state is ProviderImplementationState.CONTRACT_VERIFIED
    assert manifest.authorization_basis is ProviderAuthorizationBasis.WRITTEN_PERMISSION
    assert manifest.authorization_reference == "document:F-046"
    assert manifest.configured is True
    assert manifest.runtime_enabled is True
    assert manifest.onboarding_enabled is True
    assert manifest.account_identity_kind == "phone_e164"
    assert ProviderAuthStage.IDENTITY in manifest.auth_steps
    assert ProviderCapability.DIALOGS_READ in manifest.capabilities
    assert manifest.reason_code is None
    assert registration.catalog_visible is True
    assert registration.adapter_factory is not None
    assert registration.worker_factory is not None


def test_bale_catalog_and_registry_expose_verified_contract_and_factories() -> None:
    descriptor = provider_adapter_catalog()["bale"]
    payload = descriptor.safe_payload()
    assert payload["provider"] == "bale"
    assert payload["display_name"] == "بله"
    assert payload["configured"] is True
    assert payload["runtime_enabled"] is True
    assert payload["onboarding_enabled"] is True
    assert payload["implementation_state"] == "contract_verified"
    assert "dialogs.read" in payload["capabilities"]
    assert "messages.send" in payload["capabilities"]
    assert payload.get("reason_code") is None

    registry = default_provider_registry()
    account = _account()
    store = InMemoryProviderSessionStore()
    adapter = registry.create_adapter("bale", account, store)
    assert adapter is not None

    worker = registry.create_worker("bale", str(uuid4()), None)
    assert worker is not None


def test_bale_application_adapter_rejects_mismatched_scope() -> None:
    manifest = bale_extension_registration().manifest
    mismatched = ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider="other",
        storage_revision=1,
        session_generation=1,
    )
    with pytest.raises(ProviderExtensionError) as rejected:
        BaleProviderApplicationAdapter(mismatched, manifest)

    assert rejected.value.code == "provider_extension_scope_invalid"


def test_bale_slot_and_adapter_module_have_no_bom_transport_or_secret_reveal() -> None:
    slot_path = ROOT / "src" / "eitaa_bridge" / "providers" / "bale" / "slot.py"
    adapter_path = ROOT / "src" / "eitaa_bridge" / "application" / "bale_provider_adapter.py"

    for path in (slot_path, adapter_path):
        payload = path.read_bytes()
        assert not payload.startswith(b"\xef\xbb\xbf")
        source = payload.decode("utf-8", errors="strict")
        ast.parse(source)
        assert "http://" not in source
        assert "https://" not in source
        assert "str(exc)" not in source
        assert "str(e)" not in source
    slot_source = slot_path.read_text(encoding="utf-8")
    assert "bale_client" not in slot_source
    assert "reveal_bytes" not in slot_source


def test_local_ui_fixture_advertises_bale_as_runnable() -> None:
    source = (ROOT / "ui" / "src" / "main.tsx").read_text(encoding="utf-8")
    descriptor = re.search(r"bale:\s*\{[^}]+\}", source)

    assert descriptor is not None
    payload = descriptor.group(0)
    assert "configured: true" in payload
    assert "runtime_enabled: true" in payload
    assert "onboarding_enabled: true" in payload
    assert "implementation_state: 'contract_verified'" in payload
    assert "'dialogs.read'" in payload

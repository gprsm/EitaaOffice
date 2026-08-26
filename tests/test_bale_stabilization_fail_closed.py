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
    ProviderAuthorizationBasis,
    ProviderImplementationState,
    SensitiveProviderValue,
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


def test_bale_manifest_preserves_authorization_decision_but_is_fail_closed() -> None:
    registration = bale_extension_registration()
    manifest = registration.manifest

    assert manifest.implementation_state is ProviderImplementationState.IMPLEMENTED
    assert manifest.authorization_basis is ProviderAuthorizationBasis.WRITTEN_PERMISSION
    assert manifest.authorization_reference == "document:F-046"
    assert manifest.configured is False
    assert manifest.runtime_enabled is False
    assert manifest.onboarding_enabled is False
    assert manifest.account_identity_kind is None
    assert manifest.auth_steps == ()
    assert manifest.capabilities == frozenset()
    assert manifest.reason_code == "provider_adapter_not_configured"
    assert registration.catalog_visible is True
    assert registration.adapter_factory is None
    assert registration.worker_factory is None


def test_bale_catalog_and_registry_reject_adapter_and_worker_before_factory() -> None:
    descriptor = provider_adapter_catalog()["bale"]
    assert descriptor.safe_payload() == {
        "provider": "bale",
        "display_name": "بله",
        "configured": False,
        "runtime_enabled": False,
        "onboarding_enabled": False,
        "account_identity_kind": None,
        "auth_steps": [],
        "account_kind": "personal",
        "implementation_state": "implemented",
        "capabilities": [],
        "reason_code": "provider_adapter_not_configured",
    }

    registry = default_provider_registry()
    account = _account()
    store = InMemoryProviderSessionStore()
    store.save(account, SensitiveProviderValue.from_text("synthetic-secret"))
    with pytest.raises(ProviderExtensionError) as adapter_rejected:
        registry.create_adapter("bale", account, store)
    assert adapter_rejected.value.code == "provider_adapter_not_configured"
    assert "synthetic-secret" not in str(adapter_rejected.value)

    with pytest.raises(ProviderExtensionError) as worker_rejected:
        registry.create_worker("bale", str(uuid4()), None)
    assert worker_rejected.value.code == "provider_worker_not_configured"


def test_incomplete_bale_application_adapter_is_quarantined_at_construction() -> None:
    with pytest.raises(ProviderExtensionError) as rejected:
        BaleProviderApplicationAdapter(_account(), InMemoryProviderSessionStore())

    assert rejected.value.code == "provider_adapter_not_configured"


def test_bale_slot_and_quarantine_module_have_no_bom_transport_or_secret_reveal() -> None:
    slot_path = ROOT / "src" / "eitaa_bridge" / "providers" / "bale" / "slot.py"
    adapter_path = ROOT / "src" / "eitaa_bridge" / "application" / "bale_provider_adapter.py"

    for path in (slot_path, adapter_path):
        payload = path.read_bytes()
        assert not payload.startswith(b"\xef\xbb\xbf")
        source = payload.decode("utf-8", errors="strict")
        ast.parse(source)
        assert "reveal_bytes" not in source
        assert "bale_client" not in source
        assert "http://" not in source
        assert "https://" not in source
        assert "str(exc)" not in source
        assert "str(e)" not in source


def test_local_ui_fixture_does_not_advertise_bale_as_runnable() -> None:
    source = (ROOT / "ui" / "src" / "main.tsx").read_text(encoding="utf-8")
    descriptor = re.search(r"bale:\s*\{[^}]+\}", source)

    assert descriptor is not None
    payload = descriptor.group(0)
    assert "configured: false" in payload
    assert "runtime_enabled: false" in payload
    assert "onboarding_enabled: false" in payload
    assert "implementation_state: 'implemented'" in payload
    assert "reason_code: 'provider_adapter_not_configured'" in payload
    assert "capabilities: []" in payload

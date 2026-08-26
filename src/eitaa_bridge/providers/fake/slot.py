"""Allowlisted Fake provider composition; never enabled in product catalogs."""

from __future__ import annotations

from ..contracts import (
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    ProviderManifest,
    ProviderRegistration,
)
from .adapter import FakeProviderAdapter


def fake_provider_manifest() -> ProviderManifest:
    return ProviderManifest(
        provider="fake",
        display_name="Fake Provider",
        account_kind="test",
        implementation_state=ProviderImplementationState.CONTRACT_VERIFIED,
        authorization_basis=ProviderAuthorizationBasis.TEST_ONLY,
        configured=True,
        runtime_enabled=True,
        onboarding_enabled=False,
        capabilities=frozenset(
            {
                ProviderCapability.DIALOGS_READ,
                ProviderCapability.HISTORY_READ,
                ProviderCapability.MESSAGES_SEND,
            }
        ),
    )


def _adapter_factory(context, session_store):
    return FakeProviderAdapter(context, session_store, fake_provider_manifest())


def _worker_factory(messenger_account_id: str, config_file: str | None):
    del config_file
    from ...application.fake_provider_worker import FakeProviderWorker

    return FakeProviderWorker(messenger_account_id)


def fake_extension_registration() -> ProviderRegistration:
    return ProviderRegistration(
        manifest=fake_provider_manifest(),
        catalog_visible=False,
        adapter_factory=_adapter_factory,
        worker_factory=_worker_factory,
    )

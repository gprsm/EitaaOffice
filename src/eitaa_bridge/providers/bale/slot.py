"""Bale personal provider: account-owned runtime and product API (ADR-60).
Offline contract verification is distinct from a generic product Live pilot.
"""

from __future__ import annotations

from ..contracts import (
    ProviderAdapter,
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    ProviderManifest,
    ProviderRegistration,
    ProviderSessionStore,
)


def bale_extension_registration() -> ProviderRegistration:
    manifest = ProviderManifest(
        provider="bale",
        display_name="بله",
        account_kind="personal",
        implementation_state=ProviderImplementationState.CONTRACT_VERIFIED,
        authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
        authorization_reference="document:F-086",
        configured=True,
        runtime_enabled=True,
        onboarding_enabled=True,
        account_identity_kind="phone_e164",
        auth_steps=(
            ProviderAuthStage.IDENTITY,
            ProviderAuthStage.CHALLENGE,
            ProviderAuthStage.SECOND_FACTOR_OPTIONAL,
        ),
        capabilities=frozenset(
            {
                ProviderCapability.AUTH_PHONE,
                ProviderCapability.DIALOGS_READ,
                ProviderCapability.HISTORY_READ,
                ProviderCapability.MESSAGES_SEND,
                ProviderCapability.MEDIA_READ,
                ProviderCapability.MEDIA_SEND,
                ProviderCapability.CONTACTS_READ,
                ProviderCapability.CONTACTS_WRITE,
                ProviderCapability.LIVE_UPDATES,
            }
        ),
        reason_code=None,
    )

    def adapter_factory(
        context,
        session_store: ProviderSessionStore,
    ) -> ProviderAdapter:
        # Lazy import: the application layer owns the client wiring and the
        # providers package must stay import-cycle free.
        from ...application.bale_provider_adapter import BaleProviderApplicationAdapter

        return BaleProviderApplicationAdapter(context, session_store, manifest)

    def worker_factory(messenger_account_id, config_file):
        from ...application.bale_provider_worker import BaleProviderProcessWorker
        return BaleProviderProcessWorker(messenger_account_id, config_file)

    return ProviderRegistration(
        manifest=manifest,
        catalog_visible=True,
        adapter_factory=adapter_factory,
        worker_factory=worker_factory,
        worker_config_required=True,
    )

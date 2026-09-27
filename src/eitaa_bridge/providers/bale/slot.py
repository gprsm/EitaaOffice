"""Bale personal provider registration (owner-authorized path).

The product decision recorded by F-086/ADR-60 (2026-09-27) authorizes the
Bale personal-account path as a first-class provider alongside the official
Bale Bot API scaffold, superseding the stabilization-era fail-closed reading
of F-046. The client implementation lives in ``application/bale_client``
(live-accepted for session operations on the Bale branch, V-194/F-072) and
this adapter is offline contract-verified; account onboarding and worker
runtime wiring remain the explicitly authorized next gated phase, so
``runtime_enabled``/``onboarding_enabled`` stay honestly ``False`` until that
phase passes its gates. Live provider operations still require same-moment
user authorization.
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
        implementation_state=ProviderImplementationState.IMPLEMENTED,
        authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
        authorization_reference="document:F-086",
        configured=True,
        runtime_enabled=False,
        onboarding_enabled=False,
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
        reason_code="provider_onboarding_wiring_pending",
    )

    def adapter_factory(
        context,
        session_store: ProviderSessionStore,
    ) -> ProviderAdapter:
        # Lazy import: the application layer owns the client wiring and the
        # providers package must stay import-cycle free.
        from ...application.bale_provider_adapter import BaleProviderApplicationAdapter

        return BaleProviderApplicationAdapter(context, session_store, manifest)

    return ProviderRegistration(
        manifest=manifest,
        catalog_visible=True,
        adapter_factory=adapter_factory,
        worker_factory=None,
    )

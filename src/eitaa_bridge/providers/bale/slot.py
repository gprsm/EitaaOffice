"""Activated Bale registration for multi-provider runtime."""

from __future__ import annotations

from ..contracts import (
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    ProviderManifest,
    ProviderRegistration,
)


def _bale_adapter_factory(context, session_store):
    from ...application.bale_provider_adapter import BaleProviderApplicationAdapter

    return BaleProviderApplicationAdapter(
        context,
        session_store=session_store,
    )


def _bale_worker_factory(messenger_account_id: str, config_file: str | None = None):
    from ...application.bale_provider_worker import BaleProviderProcessWorker

    return BaleProviderProcessWorker(messenger_account_id, config_file=config_file)


def bale_extension_registration() -> ProviderRegistration:
    return ProviderRegistration(
        manifest=ProviderManifest(
            provider="bale",
            display_name="بله",
            account_kind="personal",
            implementation_state=ProviderImplementationState.CONTRACT_VERIFIED,
            authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
            authorization_reference="document:F-046",
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
                    ProviderCapability.LOGOUT,
                }
            ),
        ),
        catalog_visible=True,
        adapter_factory=_bale_adapter_factory,
        worker_factory=_bale_worker_factory,
        worker_config_required=False,
    )

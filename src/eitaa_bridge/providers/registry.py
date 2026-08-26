"""Built-in allowlisted provider composition root."""

from __future__ import annotations

from .bale import bale_extension_registration
from .fake import fake_extension_registration
from .contracts import (
    ProviderAuthStage,
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    ProviderManifest,
    ProviderRegistration,
    ProviderRegistry,
)


def _eitaa_worker_factory(messenger_account_id: str, config_file: str | None):
    from ..application.eitaa_provider_worker import EitaaProviderProcessWorker

    if config_file is None:  # Registry validation normally rejects this first.
        raise ValueError("config_file is required")
    return EitaaProviderProcessWorker(messenger_account_id, config_file)


def default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(fake_extension_registration())
    registry.register(
        ProviderRegistration(
            manifest=ProviderManifest(
                provider="eitaa",
                display_name="ایتا",
                account_kind="personal",
                implementation_state=ProviderImplementationState.LIVE_ACCEPTED,
                authorization_basis=ProviderAuthorizationBasis.EXISTING_ACCEPTED_INTEGRATION,
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
                        ProviderCapability.LOGOUT,
                    }
                ),
            ),
            catalog_visible=True,
            worker_factory=_eitaa_worker_factory,
            worker_config_required=True,
        )
    )
    registry.register(bale_extension_registration())
    return registry

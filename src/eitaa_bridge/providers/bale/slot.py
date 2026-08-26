"""Fail-closed Bale registration for the stabilization baseline.

The user's later product/development decision remains recorded by F-046, but
the current adapter has not passed the provider contract and is not runnable.
Keep the provider visible for an honest UI descriptor while adapter, worker and
onboarding factories remain absent. This module must contain no endpoint,
credential, transport, session or provider-client implementation.
"""

from __future__ import annotations

from ..contracts import (
    ProviderAuthorizationBasis,
    ProviderImplementationState,
    ProviderManifest,
    ProviderRegistration,
)


def bale_extension_registration() -> ProviderRegistration:
    return ProviderRegistration(
        manifest=ProviderManifest(
            provider="bale",
            display_name="بله",
            account_kind="personal",
            implementation_state=ProviderImplementationState.IMPLEMENTED,
            authorization_basis=ProviderAuthorizationBasis.WRITTEN_PERMISSION,
            authorization_reference="document:F-046",
            configured=False,
            runtime_enabled=False,
            onboarding_enabled=False,
            account_identity_kind=None,
            auth_steps=(),
            capabilities=frozenset(),
            reason_code="provider_adapter_not_configured",
        ),
        catalog_visible=True,
        adapter_factory=None,
        worker_factory=None,
    )


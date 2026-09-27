from ..contracts import (
    ProviderAuthorizationBasis,
    ProviderCapability,
    ProviderImplementationState,
    ProviderManifest,
)

manifest = ProviderManifest(
    provider="bale_bot",
    display_name="Bale Bot",
    account_kind="bot",
    account_identity_kind="bot_token",
    authorization_basis=ProviderAuthorizationBasis.OFFICIAL_API,
    authorization_reference="https://docs.bale.ai/",
    capabilities=frozenset({ProviderCapability.MESSAGES_SEND}),
    implementation_state=ProviderImplementationState.SCAFFOLD,
    configured=False,
    runtime_enabled=False,
    onboarding_enabled=False,
)

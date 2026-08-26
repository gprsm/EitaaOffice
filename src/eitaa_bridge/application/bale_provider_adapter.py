"""Quarantine boundary for the incomplete Bale application adapter.

G-02 deliberately exposes no provider operations. The implementation that was
present in this module had not passed offline contract/adversarial validation
and could claim successful empty results, trust an unprobed session, or expose
provider exception text. Construction therefore fails before any client,
session, credential, transport or network access. Re-enablement requires a
separate, explicitly authorized development phase and the shared contract
suite; it is not part of stabilization.
"""

from __future__ import annotations

from ..errors import ProviderExtensionError
from ..providers.contracts import ProviderAccountContext, ProviderSessionStore


class BaleProviderApplicationAdapter:
    """Compatibility name that rejects every construction attempt safely."""

    def __init__(
        self,
        account_context: ProviderAccountContext,
        session_store: ProviderSessionStore,
    ) -> None:
        del account_context, session_store
        raise ProviderExtensionError(
            "The Bale provider adapter is not configured.",
            safe_context={"provider": "bale"},
            code="provider_adapter_not_configured",
        )


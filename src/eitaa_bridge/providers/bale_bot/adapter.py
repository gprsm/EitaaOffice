"""Bale Bot Provider Adapter (official Bot API, scaffold).

Limitation: The Bale Bot API cannot resolve phone numbers to chat_ids.
It can only send messages to chat_ids of users who have already started a
conversation with the bot. This adapter is NOT registered in the provider
registry and stays fail-closed until the live acceptance gates pass.
"""

from __future__ import annotations

import httpx

from ..contracts import (
    ProviderAccountContext,
    ProviderAuthOutcome,
    ProviderDialogPage,
    ProviderManifest,
    ProviderMessagePage,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    ProviderSessionState,
    ProviderSessionStore,
    SensitiveProviderValue,
)
from ...errors import ProviderExtensionError
from .errors import map_bale_error
from .manifest import manifest

_BALE_BOT_API_BASE = "https://tapi.bale.ai"


class BaleBotProviderAdapter:
    """Bale Bot API adapter (official Bot API only; no personal-account client)."""

    def __init__(
        self,
        context: ProviderAccountContext,
        session_store: ProviderSessionStore,
        provider_manifest: ProviderManifest = manifest,
    ) -> None:
        self.context = context
        self.session_store = session_store
        self._manifest = provider_manifest
        self._http_client = httpx.AsyncClient(timeout=10.0)

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    def _get_token(self) -> str:
        val = self.session_store.load(self.context)
        if not val:
            raise ProviderExtensionError("Bot token missing", code="provider_auth_missing")
        return val.reveal_bytes().decode("utf-8").strip()

    def _raise_unimplemented(self) -> None:
        raise ProviderExtensionError(
            "Capability not implemented for bot.",
            code="provider_capability_not_implemented"
        )

    async def request_challenge(self, context: ProviderOperationContext, identity: SensitiveProviderValue) -> ProviderAuthOutcome:
        self._raise_unimplemented()
        
    async def submit_challenge(self, context: ProviderOperationContext, challenge_state: SensitiveProviderValue, response: SensitiveProviderValue) -> ProviderAuthOutcome:
        self._raise_unimplemented()

    async def submit_second_factor(self, context: ProviderOperationContext, challenge_state: SensitiveProviderValue, response: SensitiveProviderValue) -> ProviderAuthOutcome:
        self._raise_unimplemented()

    async def validate_session(self, context: ProviderOperationContext, sealed_session: SensitiveProviderValue) -> ProviderAuthOutcome:
        context.require_live_deadline()
        # For bot, session is just the token. We consider it authenticated if present.
        return ProviderAuthOutcome(
            ProviderSessionState.AUTHENTICATED,
            sealed_session=sealed_session,
        )

    async def list_dialogs(self, context: ProviderOperationContext, *, cursor: str | None, limit: int) -> ProviderDialogPage:
        self._raise_unimplemented()

    async def load_history(self, context: ProviderOperationContext, *, peer: ProviderPeerReference, cursor: str | None, limit: int) -> ProviderMessagePage:
        self._raise_unimplemented()

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        context.require_live_deadline()
        
        # We need a chat_id. Peer must be bot or private.
        # But we assume the opaque_reference is the chat_id.
        chat_id = request.peer.opaque_reference
        
        token = self._get_token()
        # The Bot API auth model puts the token in the URL path; it must never
        # be logged or embedded in errors/receipts.
        url = f"{_BALE_BOT_API_BASE}/bot{token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": request.text
        }
        
        try:
            response = await self._http_client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                msg_id = str(data.get("result", {}).get("message_id", request.idempotency_key))
                return ProviderSendReceipt(
                    ProviderSendStatus.SUCCEEDED,
                    message_reference=msg_id
                )
            else:
                err_type = map_bale_error(response.status_code)
                if err_type in ("transient", "uncertain"):
                    return ProviderSendReceipt(ProviderSendStatus.UNCERTAIN, safe_reason_code=f"bale_{err_type}")
                else:
                    raise ProviderExtensionError("Failed to send message", code=f"bale_send_{err_type}")
        except httpx.RequestError:
            return ProviderSendReceipt(ProviderSendStatus.UNCERTAIN, safe_reason_code="bale_network_error")

    async def close(self) -> None:
        await self._http_client.aclose()

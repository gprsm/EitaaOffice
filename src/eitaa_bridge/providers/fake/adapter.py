"""Deterministic, network-free implementation of ProviderAdapter."""

from __future__ import annotations

from ..contracts import (
    ProviderAccountContext,
    ProviderAuthOutcome,
    ProviderDialogPage,
    ProviderDialogSummary,
    ProviderManifest,
    ProviderMessagePage,
    ProviderMessageSummary,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendReceipt,
    ProviderSendStatus,
    ProviderSendTextRequest,
    ProviderSessionState,
    ProviderSessionStore,
    SensitiveProviderValue,
)


class FakeProviderAdapter:
    """Bounded Fake: no sockets, endpoints, filesystem paths, or real identities."""

    def __init__(
        self,
        context: ProviderAccountContext,
        session_store: ProviderSessionStore,
        manifest: ProviderManifest,
    ) -> None:
        self.context = context
        self.session_store = session_store
        self._manifest = manifest

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    async def request_challenge(
        self,
        context: ProviderOperationContext,
        identity: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        del identity
        context.require_live_deadline()
        return ProviderAuthOutcome(
            ProviderSessionState.INVALID,
            safe_reason_code="fake_auth_not_supported",
        )

    async def submit_challenge(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        del context, challenge_state, response
        return ProviderAuthOutcome(
            ProviderSessionState.INVALID,
            safe_reason_code="fake_auth_not_supported",
        )

    async def submit_second_factor(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        return await self.submit_challenge(context, challenge_state, response)

    async def validate_session(
        self,
        context: ProviderOperationContext,
        sealed_session: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        context.require_live_deadline()
        return ProviderAuthOutcome(
            ProviderSessionState.AUTHENTICATED,
            sealed_session=sealed_session,
        )

    async def list_dialogs(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderDialogPage:
        del cursor
        context.require_live_deadline()
        if limit < 1:
            return ProviderDialogPage(())
        return ProviderDialogPage(
            (
                ProviderDialogSummary(
                    peer=ProviderPeerReference("fake:dialog:1", "private"),
                    title="Synthetic dialog",
                ),
            )
        )

    async def load_history(
        self,
        context: ProviderOperationContext,
        *,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage:
        del cursor
        context.require_live_deadline()
        if limit < 1:
            return ProviderMessagePage(())
        return ProviderMessagePage(
            (
                ProviderMessageSummary(
                    message_reference="fake:message:1",
                    peer=peer,
                    sender_reference="fake:sender:1",
                    sent_at_unix_ms=0,
                    text="Synthetic message",
                ),
            )
        )

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        context.require_live_deadline()
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference=f"fake:{request.idempotency_key[:24]}",
        )

    async def close(self) -> None:
        return None

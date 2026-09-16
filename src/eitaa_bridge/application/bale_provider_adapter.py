"""Bale application adapter conforming to provider extension contracts."""

from __future__ import annotations

import mimetypes
from pathlib import Path
import tempfile
from typing import Any

from ..errors import ProviderExtensionError
from ..providers.contracts import (
    ProviderAccountContext,
    ProviderAuthOutcome,
    ProviderCapability,
    ProviderContactAdapter,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactSummary,
    ProviderContactUpsertRequest,
    ProviderDialogPage,
    ProviderDialogSummary,
    ProviderManifest,
    ProviderMediaAdapter,
    ProviderMediaReadReceipt,
    ProviderMediaReadRequest,
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
from .bale_client.api import BaleApi, BaleApiError


class BaleProviderApplicationAdapter:
    """Bounded application adapter for the Bale messenger provider."""

    def __init__(
        self,
        account_context: ProviderAccountContext,
        manifest: ProviderManifest | None = None,
        *,
        api: BaleApi | Any | None = None,
        session_store: ProviderSessionStore | None = None,
        media_dir: Path | None = None,
    ) -> None:
        if manifest is not None and manifest.provider != account_context.provider:
            raise ProviderExtensionError(
                "The Bale adapter scope is invalid.",
                code="provider_extension_scope_invalid",
            )
        self._account = account_context
        self._manifest = manifest
        self._api = api
        self._session_store = session_store
        self._media_dir = media_dir

    @property
    def account(self) -> ProviderAccountContext:
        return self._account

    @property
    def manifest(self) -> ProviderManifest | None:
        return self._manifest

    def _require_scope(self, context: ProviderOperationContext) -> None:
        if context.account != self._account:
            raise ProviderExtensionError(
                "The Bale operation account scope changed.",
                code="provider_extension_scope_invalid",
            )
        context.require_live_deadline()

    def _ensure_api(self) -> BaleApi | Any:
        if self._api is not None:
            return self._api
        # Default lazy initialization of BaleApi with account-specific storage
        base_dir = Path("data") / "coordinator" / "accounts" / self._account.messenger_account_id
        base_dir.mkdir(parents=True, exist_ok=True)
        self._api = BaleApi.create(base_dir=base_dir)
        return self._api

    # --------------------------------- Auth ---------------------------------

    async def request_challenge(
        self,
        context: ProviderOperationContext,
        identity: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._require_scope(context)
        phone = identity.reveal_bytes().decode("utf-8")
        try:
            api = self._ensure_api()
            result = await api.auth_start(phone)
            tx = result.get("transaction_hash") or ""
            return ProviderAuthOutcome(
                ProviderSessionState.CHALLENGE_PENDING,
                challenge_kind="phone_code",
                challenge_state=SensitiveProviderValue.from_text(tx),
            )
        except BaleApiError as exc:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code=exc.code or "bale_auth_start_failed",
            )

    async def submit_challenge(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._require_scope(context)
        tx = challenge_state.reveal_bytes().decode("utf-8")
        code = response.reveal_bytes().decode("utf-8")
        try:
            api = self._ensure_api()
            result = await api.auth_code(tx, code)
            if result.get("authenticated"):
                user_id = str(result.get("user_id") or "")
                return ProviderAuthOutcome(
                    ProviderSessionState.AUTHENTICATED,
                    sealed_session=SensitiveProviderValue.from_text(user_id),
                )
            if result.get("next") == "password":
                return ProviderAuthOutcome(
                    ProviderSessionState.SECOND_FACTOR_PENDING,
                    challenge_kind="password",
                    challenge_state=SensitiveProviderValue.from_text(result.get("transaction_hash") or tx),
                )
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code="bale_auth_challenge_incomplete",
            )
        except BaleApiError as exc:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code=exc.code or "bale_auth_code_failed",
            )

    async def submit_second_factor(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._require_scope(context)
        tx = challenge_state.reveal_bytes().decode("utf-8")
        password = response.reveal_bytes().decode("utf-8")
        try:
            api = self._ensure_api()
            result = await api.auth_password(tx, password)
            user_id = str(result.get("user_id") or "")
            return ProviderAuthOutcome(
                ProviderSessionState.AUTHENTICATED,
                sealed_session=SensitiveProviderValue.from_text(user_id),
            )
        except BaleApiError as exc:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code=exc.code or "bale_auth_password_failed",
            )

    async def validate_session(
        self,
        context: ProviderOperationContext,
        sealed_session: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._require_scope(context)
        try:
            api = self._ensure_api()
            card = await api.account_card()
            if card.get("authenticated"):
                return ProviderAuthOutcome(
                    ProviderSessionState.AUTHENTICATED,
                    sealed_session=sealed_session,
                )
            return ProviderAuthOutcome(
                ProviderSessionState.EXPIRED,
                safe_reason_code="bale_session_expired",
            )
        except BaleApiError as exc:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code=exc.code or "bale_session_invalid",
            )

    # ------------------------------- Dialogs --------------------------------

    async def list_dialogs(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderDialogPage:
        del cursor
        self._require_scope(context)
        api = self._ensure_api()
        try:
            items = await api.list_dialogs(limit=min(max(limit, 1), 200))
        except BaleApiError as exc:
            raise ProviderExtensionError(
                f"Failed to list Bale dialogs: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_dialogs_failed",
            ) from exc

        dialogs: list[ProviderDialogSummary] = []
        for item in items:
            peer_data = item.get("peer") or {}
            peer_id = str(peer_data.get("id") or "")
            raw_type = peer_data.get("type", 1)
            kind = "group" if raw_type == 2 else ("channel" if raw_type == 3 else "private")
            dialogs.append(
                ProviderDialogSummary(
                    peer=ProviderPeerReference(peer_id, kind),
                    title=item.get("title") or "",
                    unread_count=int(item.get("unread_count") or 0),
                )
            )
        return ProviderDialogPage(tuple(dialogs))

    # ------------------------------- History --------------------------------

    async def load_history(
        self,
        context: ProviderOperationContext,
        *,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage:
        del cursor
        self._require_scope(context)
        api = self._ensure_api()
        try:
            user_id = int(peer.opaque_reference)
            messages_raw = await api.read_history(user_id=user_id, limit=min(max(limit, 1), 100))
        except BaleApiError as exc:
            raise ProviderExtensionError(
                f"Failed to load Bale history: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_history_failed",
            ) from exc

        messages: list[ProviderMessageSummary] = []
        for m in messages_raw:
            msg_ref = str(m.get("message_id") or m.get("id") or "")
            sender_ref = str(m.get("sender_id")) if m.get("sender_id") is not None else None
            date_s = int(m.get("date") or 0)
            sent_at_unix_ms = date_s * 1000
            messages.append(
                ProviderMessageSummary(
                    message_reference=msg_ref,
                    peer=peer,
                    sender_reference=sender_ref,
                    sent_at_unix_ms=sent_at_unix_ms,
                    text=m.get("text"),
                )
            )
        return ProviderMessagePage(tuple(messages))

    # ------------------------------ Messaging -------------------------------

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        self._require_scope(context)
        api = self._ensure_api()
        user_id = int(request.peer.opaque_reference)
        try:
            result = await api.send_text(user_id, request.text)
            msg_ref = str(
                result.get("message_id")
                or result.get("random_id")
                or result.get("id")
                or "sent"
            )
            return ProviderSendReceipt(
                status=ProviderSendStatus.SUCCEEDED,
                message_reference=msg_ref,
            )
        except BaleApiError as exc:
            return ProviderSendReceipt(
                status=ProviderSendStatus.UNCERTAIN,
                safe_reason_code=exc.code or "bale_send_failed",
            )

    # ------------------------------- Contacts -------------------------------

    async def list_contacts(
        self,
        context: ProviderOperationContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> ProviderContactPage:
        del cursor, limit
        self._require_scope(context)
        api = self._ensure_api()
        try:
            contacts_raw = await api.list_contacts()
        except BaleApiError as exc:
            raise ProviderExtensionError(
                f"Failed to list Bale contacts: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_contacts_failed",
            ) from exc

        contacts: list[ProviderContactSummary] = []
        for c in contacts_raw:
            peer_data = c.get("peer") or {}
            contact_ref = str(peer_data.get("id") or "")
            contacts.append(
                ProviderContactSummary(
                    contact_reference=contact_ref,
                    display_name=c.get("name") or "",
                    identity_hint=c.get("username") or None,
                )
            )
        return ProviderContactPage(tuple(contacts))

    async def upsert_contact(
        self,
        context: ProviderOperationContext,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt:
        self._require_scope(context)
        api = self._ensure_api()
        phone = request.identity.reveal_bytes().decode("utf-8")
        try:
            result = await api.add_contact_by_phone(phone, request.display_name)
            matched_users = result.get("users") or []
            if result.get("matched") and matched_users:
                user_id = str(matched_users[0].get("id") or "")
                return ProviderContactMutationReceipt(
                    contact_reference=user_id,
                    created=True,
                )
            cleaned_phone = str(result.get("phone") or phone)
            return ProviderContactMutationReceipt(
                contact_reference=cleaned_phone,
                created=False,
            )
        except BaleApiError as exc:
            raise ProviderExtensionError(
                f"Failed to upsert Bale contact: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_contact_upsert_failed",
            ) from exc

    # -------------------------------- Media ---------------------------------

    async def read_media(
        self,
        context: ProviderOperationContext,
        request: ProviderMediaReadRequest,
    ) -> ProviderMediaReadReceipt:
        self._require_scope(context)
        api = self._ensure_api()
        user_id = int(request.peer.opaque_reference)
        msg_id = int(request.message_reference)
        out_dir = self._media_dir or Path(tempfile.gettempdir())
        try:
            file_path = await api.read_message_media(user_id, msg_id, out_dir)
        except BaleApiError as exc:
            raise ProviderExtensionError(
                f"Failed to read Bale media: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_media_failed",
            ) from exc

        if file_path is None or not Path(file_path).exists():
            raise ProviderExtensionError(
                "Failed to read Bale message media: file not found",
                code="bale_media_not_found",
            )

        resolved_path = Path(file_path)
        guessed, _ = mimetypes.guess_type(resolved_path.name)
        mime = guessed or "application/octet-stream"
        byte_count = resolved_path.stat().st_size

        return ProviderMediaReadReceipt(
            media_reference=request.media_reference,
            content_reference=resolved_path.name,
            mime_type=mime,
            byte_count=byte_count,
        )

    async def close(self) -> None:
        if self._api is not None and hasattr(self._api, "close"):
            maybe_coro = self._api.close()
            if hasattr(maybe_coro, "__await__"):
                await maybe_coro

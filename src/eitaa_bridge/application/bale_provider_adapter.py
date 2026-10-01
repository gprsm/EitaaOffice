"""Bale personal provider adapter (owner-authorized path, F-086/ADR-60).

Maps the provider-neutral extension contract onto the Bale personal client
(``application/bale_client``), which is live-accepted for session operations
on the Bale branch (V-194/F-072). Rules that must not be weakened:

- Secrets (vault passphrase, OTP, password, phone, session material) are only
  ever ``reveal_bytes()``-ed to hand them to the client; they never reach
  logs, error text, receipts or auth outcomes.
- Client failures surface as stable ``bale_*`` codes from the client's own
  safe taxonomy; provider exception text is never passed through.
- The backend is injectable so the offline contract suite can verify this
  adapter without network or vault access. Production must inject the
  account-owned facade; a shared default vault is rejected.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, Callable

from ..errors import ProviderExtensionError
from ..providers.contracts import (
    ProviderAccountContext,
    ProviderAdapter,
    ProviderAuthOutcome,
    ProviderContactMutationReceipt,
    ProviderContactPage,
    ProviderContactSummary,
    ProviderContactUpsertRequest,
    ProviderContactRemoveRequest,
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
    ProviderSendMediaRequest,
    ProviderMediaReadRequest,
    ProviderMediaReadReceipt,
    ProviderSessionState,
    ProviderSessionStore,
    SensitiveProviderValue,
)

_CONTACT_FALLBACK_MAX_ITEMS = 5000
_CONTACT_FALLBACK_MAX_BYTES = 16 * 1024 * 1024
_CONTACT_FALLBACK_MAX_TEXT_CHARS = 8192

_PEER_KIND_BY_TYPE = {1: "private", 2: "group", 3: "channel"}
_PEER_TYPE_BY_KIND = {"private": "user", "group": "group", "channel": "channel"}
_UNCERTAIN_CODES = frozenset(
    {"bale_api_error", "bale_transport_error", "bale_rpc_error", "bale_not_connected", "bale_connect_failed", "bale_vault_missing", "bale_vault_locked", "bale_operation_timeout", "eitaa_process_request_timeout", "eitaa_process_exited"}
)


def _bale_peer_reference(peer_dict: Any) -> ProviderPeerReference:
    peer = peer_dict.get("peer") if isinstance(peer_dict, dict) else None
    if not isinstance(peer, dict):
        raise ProviderExtensionError(
            "The Bale dialog summary is invalid.",
            safe_context={"provider": "bale"},
            code="provider_operation_result_invalid",
        )
    peer_type = int(peer.get("type") or 0)
    peer_id = int(peer.get("id") or 0)
    if peer_id <= 0:
        raise ProviderExtensionError(
            "The Bale dialog summary is invalid.",
            safe_context={"provider": "bale"},
            code="provider_operation_result_invalid",
        )
    kind = _PEER_KIND_BY_TYPE.get(peer_type)
    if kind is None:
        raise ProviderExtensionError(
            "The Bale peer type is unsupported.", code="provider_peer_kind_unsupported"
        )
    return ProviderPeerReference(f"bale:{_PEER_TYPE_BY_KIND[kind]}:{peer_id}", kind)


def _user_id_from_reference(opaque_reference: str, kind: str = "private") -> int:
    selected = str(opaque_reference or "").strip()
    # Old untyped references can only be used as private peers; using them for
    # a group would silently direct a message to a different recipient.
    prefix = "bale:user:" if selected.startswith("bale:user:") else "bale:peer:"
    if kind != "private" and selected.startswith("bale:"):
        raise ProviderExtensionError(
            "The Bale peer kind is unsupported by this operation.",
            code="provider_peer_kind_unsupported",
        )
    if not selected.startswith(prefix) or not selected[len(prefix):].isdigit():
        raise ProviderExtensionError(
            "The Bale peer reference is invalid.",
            safe_context={"provider": "bale"},
            code="provider_peer_reference_invalid",
        )
    user_id = int(selected[len(prefix):])
    if user_id <= 0:
        raise ProviderExtensionError(
            "The Bale peer reference is invalid.", code="provider_peer_reference_invalid"
        )
    return user_id


def _normalized_unix_ms(value: Any) -> int:
    try:
        raw = int(value or 0)
    except (TypeError, ValueError):
        return 0
    if raw <= 0:
        return 0
    if raw < 10**12:  # Bale history dates are unix seconds.
        return raw * 1000
    return raw


def _date_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    selected = cursor.removeprefix("date:") if cursor.startswith("date:") else ""
    if not selected.isdigit() or not 0 < int(selected) < 2**63:
        raise ProviderExtensionError("Invalid Bale cursor.", code="provider_cursor_invalid")
    return int(selected)


def _parse_sensitive_json(value: SensitiveProviderValue) -> dict[str, Any]:
    try:
        parsed = json.loads(value.reveal_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class BaleProviderApplicationAdapter:
    """Provider-neutral adapter delegating to the Bale personal client."""

    def __init__(
        self,
        context: ProviderAccountContext,
        session_store: ProviderSessionStore,
        manifest: ProviderManifest,
        backend_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.context = context
        self.session_store = session_store
        self._manifest = manifest
        self._backend_factory = backend_factory
        self._backend: Any = None

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    def _get_backend(self) -> Any:
        if self._backend is None:
            if self._backend_factory is None:
                # The default BaleApi.create() uses a shared relative vault.
                # A production account owner must inject its own paths and
                # service-held secret, on the account's persistent event loop.
                raise ProviderExtensionError(
                    "The Bale account runtime is unavailable.",
                    code="provider_account_runtime_unavailable",
                )
            self._backend = self._backend_factory()
        return self._backend

    def _prepare(self, context: ProviderOperationContext) -> None:
        context.require_live_deadline()
        backend = self._get_backend()
        if hasattr(backend, "deadline_unix_ms"):
            backend.deadline_unix_ms = context.deadline_unix_ms

    def _safe_client_failure(self, exc: Exception) -> ProviderExtensionError:
        if isinstance(exc, ProviderExtensionError):
            return exc
        code = str(getattr(exc, "code", "bale_api_error"))
        safe_code = code if (code.startswith("bale_") or code.startswith("provider_")) else "bale_api_error"
        return ProviderExtensionError(
            "The Bale provider operation failed safely.",
            safe_context={"provider": "bale", "reason_code": safe_code},
            code=safe_code,
        )

    async def request_challenge(
        self,
        context: ProviderOperationContext,
        identity: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._prepare(context)
        phone = identity.reveal_bytes().decode("utf-8", errors="strict").strip()
        try:
            result = await self._get_backend().auth_start(phone)
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        finally:
            del phone
        transaction_hash = str(result.get("transaction_hash") or "")
        if not transaction_hash:
            raise ProviderExtensionError(
                "The Bale provider operation failed safely.",
                safe_context={"provider": "bale", "reason_code": "bale_auth_start_failed"},
                code="bale_auth_start_failed",
            )
        return ProviderAuthOutcome(
            ProviderSessionState.CHALLENGE_PENDING,
            challenge_state=SensitiveProviderValue.from_text(transaction_hash),
            challenge_kind="otp",
        )

    async def submit_challenge(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._prepare(context)
        payload = _parse_sensitive_json(response)
        code = str(payload.get("code") or "")
        transaction_hash = challenge_state.reveal_bytes().decode("utf-8", errors="strict")
        if not code:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code="bale_auth_payload_invalid",
            )
        try:
            result = await self._get_backend().auth_code(transaction_hash, code)
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        if result.get("authenticated") is True:
            return ProviderAuthOutcome(
                ProviderSessionState.AUTHENTICATED,
                sealed_session=SensitiveProviderValue.from_text("bale:vault:v1"),
            )
        if result.get("next") == "password":
            return ProviderAuthOutcome(
                ProviderSessionState.SECOND_FACTOR_PENDING,
                challenge_state=challenge_state,
                challenge_kind="password",
            )
        return ProviderAuthOutcome(
            ProviderSessionState.INVALID,
            safe_reason_code="bale_signup_required",
        )

    async def submit_second_factor(
        self,
        context: ProviderOperationContext,
        challenge_state: SensitiveProviderValue,
        response: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._prepare(context)
        payload = _parse_sensitive_json(response)
        password = str(payload.get("password") or "")
        transaction_hash = challenge_state.reveal_bytes().decode("utf-8", errors="strict")
        if not password:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code="bale_auth_payload_invalid",
            )
        try:
            result = await self._get_backend().auth_password(transaction_hash, password)
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        if result.get("authenticated") is True:
            return ProviderAuthOutcome(
                ProviderSessionState.AUTHENTICATED,
                sealed_session=SensitiveProviderValue.from_text("bale:vault:v1"),
            )
        return ProviderAuthOutcome(
            ProviderSessionState.INVALID,
            safe_reason_code="bale_auth_password_failed",
        )

    async def validate_session(
        self,
        context: ProviderOperationContext,
        sealed_session: SensitiveProviderValue,
    ) -> ProviderAuthOutcome:
        self._prepare(context)
        if sealed_session.reveal_bytes() != b"bale:vault:v1":
            return ProviderAuthOutcome(ProviderSessionState.INVALID, safe_reason_code="bale_session_reference_invalid")
        try:
            restored = await self._get_backend().connect(subscribe=False)
            if restored.get("connected") is not True:
                return ProviderAuthOutcome(ProviderSessionState.INVALID, safe_reason_code="bale_session_invalid")
        except Exception as exc:
            code = str(getattr(exc, "code", "bale_api_error"))
            state = ProviderSessionState.EXPIRED if code == "bale_vault_locked" else ProviderSessionState.INVALID
            return ProviderAuthOutcome(state, safe_reason_code=code)
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
        offset = _date_cursor(cursor)
        self._prepare(context)
        if limit < 1:
            return ProviderDialogPage(())
        try:
            summaries = await self._get_backend().list_dialogs(limit=limit, **({"offset_date": offset} if offset is not None else {}))
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        dialogs = []
        for item in summaries[:limit]:
            peer = _bale_peer_reference(item)
            dialogs.append(
                ProviderDialogSummary(
                    peer=peer,
                    title=str(item.get("title") or item.get("name") or peer.opaque_reference),
                    unread_count=int(item.get("unread_count") or 0),
                    last_text=str(item["last_text"]) if item.get("last_text") is not None else None,
                )
            )
        dates = [int(item["sort_date"]) for item in summaries[:limit] if item.get("sort_date") and int(item["sort_date"]) > 0]
        return ProviderDialogPage(tuple(dialogs), next_cursor=f"date:{min(dates)}" if len(summaries) >= limit and dates else None)

    async def load_history(
        self,
        context: ProviderOperationContext,
        *,
        peer: ProviderPeerReference,
        cursor: str | None,
        limit: int,
    ) -> ProviderMessagePage:
        offset = _date_cursor(cursor)
        self._prepare(context)
        if limit < 1:
            return ProviderMessagePage(())
        user_id = _user_id_from_reference(peer.opaque_reference, peer.kind)
        try:
            messages = await self._get_backend().read_history(user_id, limit=limit, **({"offset_date": offset} if offset is not None else {}))
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        page = []
        for item in messages[:limit]:
            sender_id = item.get("sender_id")
            page.append(
                ProviderMessageSummary(
                    message_reference=f"bale:message:{int(item.get('message_id') or 0)}",
                    peer=peer,
                    sender_reference=(
                        f"bale:user:{int(sender_id)}" if sender_id else None
                    ),
                    sent_at_unix_ms=_normalized_unix_ms(item.get("date")),
                    text=(str(item.get("text")) if item.get("text") else None),
                    media_reference=f"bale:media:{user_id}:{int(item.get('message_id') or 0)}" if item.get("media") else None,
                )
            )
        dates = [int(item["date"]) for item in messages[:limit] if item.get("date") and int(item["date"]) > 0]
        return ProviderMessagePage(tuple(sorted(page, key=lambda item: (item.sent_at_unix_ms, item.message_reference))),
            next_cursor=f"date:{min(dates)}" if len(messages) >= limit and dates else None)

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        self._prepare(context)
        user_id = _user_id_from_reference(request.peer.opaque_reference, request.peer.kind)
        try:
            result = await self._get_backend().send_text(user_id, request.text)
        except Exception as exc:
            code = str(getattr(exc, "code", "bale_api_error"))
            if code in _UNCERTAIN_CODES:
                return ProviderSendReceipt(
                    ProviderSendStatus.UNCERTAIN,
                    safe_reason_code=code,
                )
            raise self._safe_client_failure(exc) from None
        random_id = int(result.get("random_id") or 0)
        if not result.get("sent") or random_id <= 0:
            return ProviderSendReceipt(ProviderSendStatus.UNCERTAIN, safe_reason_code="bale_send_result_unknown")
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            # A random_id is only a local submission reference, never proof of
            # recipient delivery or a provider message_id.
            message_reference=f"bale:submission:{random_id}",
        )

    async def list_contacts(
        self, context: ProviderOperationContext, *, cursor: str | None, limit: int,
    ) -> ProviderContactPage:
        self._prepare(context)
        if not 1 <= limit <= 500:
            raise ProviderExtensionError("Invalid contact page size.", code="provider_page_limit_invalid")
        offset = 0
        if cursor is not None:
            selected = cursor.removeprefix("offset:") if cursor.startswith("offset:") else ""
            if not selected.isdigit() or int(selected) < 0:
                raise ProviderExtensionError("Unsupported contact cursor.", code="provider_cursor_invalid")
            offset = int(selected)
        backend = self._get_backend()
        try:
            if hasattr(backend, "list_contacts_page"):
                page_data = await backend.list_contacts_page(cursor=cursor, offset=offset, limit=limit)
                raw_items = page_data.get("contacts", [])
                next_cursor = page_data.get("next_cursor")
            else:
                items = await backend.list_contacts()
                if not isinstance(items, list) or len(items) > _CONTACT_FALLBACK_MAX_ITEMS:
                    raise ProviderExtensionError(
                        "The Bale contact snapshot exceeds the supported offline bound.",
                        code="provider_contact_snapshot_too_large",
                    )
                snapshot_bytes = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    peer = item.get("peer")
                    selected = {
                        "peer": {key: peer.get(key) for key in ("id", "type")} if isinstance(peer, dict) else None,
                        "name": item.get("name"),
                        "local_name": item.get("local_name"),
                    }
                    if any(isinstance(value, str) and len(value) > _CONTACT_FALLBACK_MAX_TEXT_CHARS
                           for value in (selected["name"], selected["local_name"])):
                        raise ProviderExtensionError(
                            "A Bale contact exceeds the supported snapshot text bound.",
                            code="provider_contact_snapshot_too_large",
                        )
                    snapshot_bytes += len(json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                    if snapshot_bytes > _CONTACT_FALLBACK_MAX_BYTES:
                        raise ProviderExtensionError(
                            "The Bale contact snapshot exceeds the supported byte bound.",
                            code="provider_contact_snapshot_too_large",
                        )
                raw_items = items[offset:offset + limit]
                next_offset = offset + len(raw_items)
                next_cursor = f"offset:{next_offset}" if next_offset < len(items) else None
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        contacts = []
        for item in raw_items:
            peer = item.get("peer") if isinstance(item, dict) else None
            if not isinstance(peer, dict) or int(peer.get("type") or 0) != 1:
                continue
            peer_id = int(peer.get("id") or 0)
            if peer_id <= 0:
                continue
            contacts.append(ProviderContactSummary(
                f"bale:user:{peer_id}",
                str(item.get("local_name") or item.get("name") or ""),
            ))
        return ProviderContactPage(tuple(contacts), next_cursor=next_cursor)

    async def upsert_contact(
        self,
        context: ProviderOperationContext,
        request: ProviderContactUpsertRequest,
    ) -> ProviderContactMutationReceipt:
        self._prepare(context)
        identity = request.identity.reveal_bytes().decode("utf-8", errors="strict").strip()
        created = True
        try:
            if identity.startswith("bale:user:"):
                peer_id = _user_id_from_reference(identity)
                backend = self._get_backend()
                if hasattr(backend, "contains_contact"):
                    created = not await backend.contains_contact(peer_id)
                else:
                    existing = await backend.list_contacts()
                    created = not any(
                        isinstance(item, dict)
                        and isinstance(item.get("peer"), dict)
                        and int(item["peer"].get("id") or 0) == peer_id
                        for item in existing
                    )
                if created:
                    result = await self._get_backend().add_contact(peer_id)
                    if not result.get("added"):
                        raise ProviderExtensionError("Contact result is unknown.", code="provider_contact_result_unknown")
            elif identity.startswith("+") and identity[1:].isdigit() and 8 <= len(identity) <= 16:
                result = await self._get_backend().add_contact_by_phone(identity, request.display_name)
                created = result.get("created") is not False
                matched = result.get("users") if result.get("matched") else None
                if not isinstance(matched, list) or len(matched) != 1:
                    raise ProviderExtensionError("Contact match is unresolved.", code="provider_contact_match_unresolved")
                first = matched[0]
                peer = first.get("peer") if isinstance(first, dict) else None
                peer_id = int((peer or first).get("id") or 0) if isinstance(first, dict) else 0
                if peer_id <= 0:
                    raise ProviderExtensionError("Contact match is unresolved.", code="provider_contact_match_unresolved")
            else:
                raise ProviderExtensionError("Contact identity is invalid.", code="provider_contact_identity_invalid")
        except ProviderExtensionError:
            raise
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        return ProviderContactMutationReceipt(f"bale:user:{peer_id}", created=created)

    async def remove_contact(self, context: ProviderOperationContext,
                             request: ProviderContactRemoveRequest) -> ProviderContactMutationReceipt:
        self._prepare(context)
        user_id = _user_id_from_reference(request.contact_reference)
        try:
            result = await self._get_backend().remove_contact(user_id)
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        if result.get("removed") is not True:
            raise ProviderExtensionError("Removal result is unknown.", code="provider_contact_result_unknown")
        return ProviderContactMutationReceipt(request.contact_reference, False)

    async def send_media(self, context: ProviderOperationContext, request: ProviderSendMediaRequest) -> ProviderSendReceipt:
        self._prepare(context)
        user_id = _user_id_from_reference(request.peer.opaque_reference, request.peer.kind)
        try:
            result = await self._get_backend().send_file_bytes(user_id, request.filename, request.data, caption=request.caption)
        except Exception as exc:
            code = getattr(exc, "code", "bale_api_error")
            if code in _UNCERTAIN_CODES:
                return ProviderSendReceipt(ProviderSendStatus.UNCERTAIN, safe_reason_code="bale_send_result_unknown")
            raise self._safe_client_failure(exc) from None
        if result.get("sent") is not True or not result.get("submission_reference"):
            return ProviderSendReceipt(ProviderSendStatus.UNCERTAIN, safe_reason_code="bale_send_result_unknown")
        return ProviderSendReceipt(ProviderSendStatus.SUCCEEDED, message_reference=result["submission_reference"])

    async def read_media(self, context: ProviderOperationContext, request: ProviderMediaReadRequest) -> ProviderMediaReadReceipt:
        self._prepare(context)
        user_id = _user_id_from_reference(request.peer.opaque_reference, request.peer.kind)
        selected = request.message_reference.removeprefix("bale:message:")
        if not selected.isdigit() or int(selected) <= 0 or request.media_reference != f"bale:media:{user_id}:{selected}":
            raise ProviderExtensionError("Media scope mismatch.", code="provider_media_reference_invalid")
        try:
            result = await self._get_backend().read_media(user_id, int(selected), max_bytes=min(request.max_bytes, 512 * 1024))
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        return ProviderMediaReadReceipt(request.media_reference, result["content_reference"],
            result["mime_type"], result["byte_count"])

    async def close(self) -> None:
        if self._backend is not None:
            with contextlib.suppress(Exception):
                await self._backend.close()
            self._backend = None

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
  adapter without any network or vault access; the production default
  constructs the real ``BaleApi`` lazily.
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

_PEER_KIND_BY_TYPE = {1: "private", 2: "group"}
_UNCERTAIN_CODES = frozenset(
    {"bale_not_connected", "bale_connect_failed", "bale_vault_missing", "bale_vault_locked"}
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
    return ProviderPeerReference(
        f"bale:peer:{peer_id}",
        _PEER_KIND_BY_TYPE.get(peer_type, "unknown"),
    )


def _user_id_from_reference(opaque_reference: str) -> int:
    selected = str(opaque_reference or "").strip()
    if not selected.startswith("bale:peer:") or not selected[len("bale:peer:"):].isdigit():
        raise ProviderExtensionError(
            "The Bale peer reference is invalid.",
            safe_context={"provider": "bale"},
            code="provider_peer_reference_invalid",
        )
    return int(selected[len("bale:peer:"):])


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
            if self._backend_factory is not None:
                self._backend = self._backend_factory()
            else:
                from .bale_client.api import BaleApi

                self._backend = BaleApi.create()
        return self._backend

    def _safe_client_failure(self, exc: Exception) -> ProviderExtensionError:
        code = str(getattr(exc, "code", "bale_api_error"))
        safe_code = code if code.startswith("bale_") else "bale_api_error"
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
        context.require_live_deadline()
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
        context.require_live_deadline()
        payload = _parse_sensitive_json(response)
        code = str(payload.get("code") or "")
        passphrase = str(payload.get("passphrase") or "")
        transaction_hash = challenge_state.reveal_bytes().decode("utf-8", errors="strict")
        if not code or not passphrase:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code="bale_auth_payload_invalid",
            )
        try:
            result = await self._get_backend().auth_code(
                transaction_hash, code, passphrase=passphrase
            )
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        if result.get("authenticated") is True:
            return ProviderAuthOutcome(
                ProviderSessionState.AUTHENTICATED,
                sealed_session=SensitiveProviderValue.from_text(passphrase),
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
        context.require_live_deadline()
        payload = _parse_sensitive_json(response)
        password = str(payload.get("password") or "")
        passphrase = str(payload.get("passphrase") or "")
        transaction_hash = challenge_state.reveal_bytes().decode("utf-8", errors="strict")
        if not password or not passphrase:
            return ProviderAuthOutcome(
                ProviderSessionState.INVALID,
                safe_reason_code="bale_auth_payload_invalid",
            )
        try:
            result = await self._get_backend().auth_password(
                transaction_hash, password, passphrase=passphrase
            )
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        if result.get("authenticated") is True:
            return ProviderAuthOutcome(
                ProviderSessionState.AUTHENTICATED,
                sealed_session=SensitiveProviderValue.from_text(passphrase),
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
        context.require_live_deadline()
        passphrase = sealed_session.reveal_bytes().decode("utf-8", errors="strict")
        try:
            await self._get_backend().connect(passphrase=passphrase, subscribe=False)
        except Exception as exc:
            code = str(getattr(exc, "code", "bale_api_error"))
            state = ProviderSessionState.EXPIRED if code == "bale_vault_locked" else ProviderSessionState.INVALID
            return ProviderAuthOutcome(state, safe_reason_code=code)
        finally:
            del passphrase
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
        try:
            summaries = await self._get_backend().list_dialogs(limit=limit)
        except Exception as exc:
            raise self._safe_client_failure(exc) from None
        dialogs = []
        for item in summaries[:limit]:
            dialogs.append(
                ProviderDialogSummary(
                    peer=_bale_peer_reference(item),
                    title="",
                    unread_count=int(item.get("unread_count") or 0),
                )
            )
        return ProviderDialogPage(tuple(dialogs))

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
        user_id = _user_id_from_reference(peer.opaque_reference)
        try:
            messages = await self._get_backend().read_history(user_id, limit=limit)
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
                        f"bale:peer:{int(sender_id)}" if sender_id else None
                    ),
                    sent_at_unix_ms=_normalized_unix_ms(item.get("date")),
                    text=(str(item.get("text")) if item.get("text") else None),
                )
            )
        return ProviderMessagePage(tuple(page))

    async def send_text(
        self,
        context: ProviderOperationContext,
        request: ProviderSendTextRequest,
    ) -> ProviderSendReceipt:
        context.require_live_deadline()
        user_id = _user_id_from_reference(request.peer.opaque_reference)
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
        return ProviderSendReceipt(
            ProviderSendStatus.SUCCEEDED,
            message_reference=f"bale:send:{random_id}",
        )

    async def upsert_contact(
        self,
        context: ProviderOperationContext,
        request: Any,
    ) -> ProviderContactMutationReceipt:
        del context, request
        raise ProviderExtensionError(
            "The Bale provider contact mutation is not wired yet.",
            safe_context={"provider": "bale"},
            code="provider_contact_operation_not_implemented",
        )

    async def close(self) -> None:
        if self._backend is not None:
            with contextlib.suppress(Exception):
                await self._backend.close()
            self._backend = None

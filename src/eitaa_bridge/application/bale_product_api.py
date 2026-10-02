"""Account-scoped product auth for the Bale worker; no legacy Eitaa state."""
from __future__ import annotations

from typing import Any, Mapping
import asyncio
import base64
import time

from ..errors import CompositionValidationError, ProviderExtensionError
from ..providers.contracts import ProviderCapability
from ..providers.contracts import ProviderContactRemoveRequest, ProviderPeerReference, ProviderSendMediaRequest
from .bale_runtime import BaleAccountRuntime


def dispatch_bale_auth(app: Any, session: Any, account_id: str, action: str,
                       payload: Mapping[str, Any], request_id: str) -> dict[str, object]:
    actor = app._provider_operation_actor(session)
    app._authorize_provider_operation_account(actor, account_id, "operate")
    app._require_provider_capability_service().require(account_id, ProviderCapability.AUTH_PHONE)
    runtime = app._runtime_registry.runtime_for_account(account_id)
    if not isinstance(runtime, BaleAccountRuntime):
        raise ProviderExtensionError("This account uses a different auth wizard.", code="provider_extension_scope_invalid")
    allowed = {"status": set(), "start": {"confirm"}, "code": {"challenge_id", "code"},
               "password": {"challenge_id", "password"}, "cancel": set(),
               "restore": {"confirm"}, "logout": {"confirm"}}
    app._require_provider_operation_fields(payload, allowed[action])
    if action in {"start", "logout", "restore"} and payload.get("confirm") is not True:
        raise CompositionValidationError("Confirm the session operation.", code="provider_auth_confirmation_required")
    with runtime._auth_lock:
        coordinator = app._require_coordinator()
        record = coordinator.messenger_account_runtime(account_id)
        if record.session_generation != runtime.runtime_record.session_generation:
            raise ProviderExtensionError("The account session changed.", code="provider_extension_scope_invalid")
        if action == "status":
            result = runtime.request("bale.auth.status")
            if result.get("session_invalid") is True and record.auth_state != "invalid":
                record = coordinator.transition_messenger_auth(account_id,
                    expected_states={record.auth_state}, expected_generation=record.session_generation,
                    new_state="invalid", increment_generation=False, reason_code="bale_session_invalid",
                    action="bale.auth.session_invalid", actor_app_user_id=actor.app_user_id,
                    actor_global_role=actor.global_role, request_id=request_id)
                runtime.runtime_record = record
            return {"ok": True, "messenger_account_id": account_id, "provider": "bale",
                    "auth_state": record.auth_state, **result}
        if action == "start":
            if record.auth_state == "authenticated":
                raise ProviderExtensionError("Log out before a new login.", code="bale_already_authenticated")
            identity = coordinator.messenger_account_phone_identity(account_id)
            if identity.provider != "bale":
                raise ProviderExtensionError("Account identity mismatch.", code="provider_extension_scope_invalid")
            phone = app._app_auth.phone_protector.reveal(identity.protected_phone)
            result = runtime.request("bale.auth.start", {"phone": phone}, timeout_seconds=30)
            target = "challenge_pending"
        elif action == "password":
            if record.auth_state != "challenge_pending":
                raise ProviderExtensionError("No active login challenge.", code="bale_challenge_invalid")
            result = runtime.request("bale.auth.password", {"challenge_id": payload.get("challenge_id"), "credential": payload.get("password")})
            target = "authenticated" if result.get("step") == "completed" else "challenge_pending"
        elif action == "code":
            if record.auth_state != "challenge_pending":
                raise ProviderExtensionError("No active login challenge.", code="bale_challenge_invalid")
            result = runtime.request("bale.auth.code", {"challenge_id": payload.get("challenge_id"), "code": payload.get("code")})
            target = "authenticated" if result.get("step") == "completed" else "challenge_pending"
        elif action == "restore":
            if record.auth_state in {"revoked", "invalid"}:
                raise ProviderExtensionError("Fresh login is required.", code="bale_session_invalid")
            try:
                result = runtime.request("bale.auth.restore", timeout_seconds=30)
            except Exception as exc:
                code = str(getattr(exc, "code", "") or "")
                if code in {"bale_session_invalid", "bale_vault_locked"}:
                    result = {"authenticated": False, "reason_code": "bale_session_invalid"}
                elif code == "bale_vault_missing":
                    result = {"authenticated": False, "reason_code": "bale_vault_missing"}
                else:
                    # Transport and timeout failures are not proof of session
                    # invalidity; the account keeps its auth state so a later
                    # restore attempt stays available to the user.
                    result = {"authenticated": False, "reason_code": "bale_restore_unavailable"}
            if result.get("reason_code") in {"bale_restore_unavailable", "bale_vault_missing"}:
                target = record.auth_state
            else:
                target = "authenticated" if result.get("authenticated") is True else "invalid"
        elif action == "cancel":
            result = runtime.request("bale.auth.cancel")
            target = "absent" if record.auth_state == "challenge_pending" else record.auth_state
        else:
            result = runtime.request("bale.auth.logout")
            target = "revoked"
        increment = target == "revoked" or (target == "authenticated" and record.auth_state != target)
        reason_code = str(result.get("reason_code")) if action == "restore" and result.get("reason_code") else f"bale_auth_{action}"
        updated = coordinator.transition_messenger_auth(
            account_id, expected_states={record.auth_state}, expected_generation=record.session_generation,
            new_state=target, increment_generation=increment, reason_code=reason_code,
            action=f"bale.auth.{action}", mark_validated=target == "authenticated",
            actor_app_user_id=actor.app_user_id, actor_global_role=actor.global_role, request_id=request_id,
        )
        if increment:
            runtime.request("bale.runtime.generation", {"new_session_generation": updated.session_generation})
        runtime.runtime_record = updated
        if runtime.client is not None:
            runtime.client._session_generation = updated.session_generation
        return {"ok": True, "messenger_account_id": account_id, "provider": "bale", "auth_state": target, **result}


def dispatch_product_extension(app: Any, session: Any, account_id: str, action: str,
                               payload: Mapping[str, Any], request_id: str) -> dict[str, object]:
    actor = app._provider_operation_actor(session)
    args = dict(actor=actor, messenger_account_id=account_id, correlation_id=request_id,
                deadline_unix_ms=int(time.time() * 1000) + 90_000)
    if action == "contacts/remove":
        app._require_provider_operation_fields(payload, {"contact_reference", "idempotency_key", "confirm"})
        if payload.get("confirm") is not True:
            raise CompositionValidationError("Confirm contact removal.", code="provider_contact_mutation_confirmation_required")
        receipt = asyncio.run(app._provider_orchestrator.remove_contact(**args,
            request=ProviderContactRemoveRequest(str(payload.get("contact_reference") or ""), str(payload.get("idempotency_key") or ""))))
        return {"ok": True, "messenger_account_id": account_id, "contact_reference": receipt.contact_reference, "removed": True}
    if action == "messages/send-media":
        app._require_provider_operation_fields(payload, {"peer_reference", "peer_kind", "filename", "data_base64", "caption", "idempotency_key", "confirm"})
        if payload.get("confirm") is not True:
            raise CompositionValidationError("Confirm media send.", code="provider_send_confirmation_required")
        if str(payload.get("peer_kind") or "").strip().lower() == "channel" and app._provider_operation_account_context(
            account_id
        ).provider == "bale":
            raise CompositionValidationError("Sending into Bale channels is not supported.", code="bale_channel_send_unsupported")
        try:
            data = base64.b64decode(payload.get("data_base64", ""), validate=True)
        except (ValueError, TypeError):
            raise CompositionValidationError("Invalid media encoding.", code="provider_media_bytes_invalid") from None
        receipt = asyncio.run(app._provider_orchestrator.send_media(**args, request=ProviderSendMediaRequest(
            ProviderPeerReference(str(payload.get("peer_reference") or ""), str(payload.get("peer_kind") or "private")),
            str(payload.get("filename") or ""), data, str(payload.get("idempotency_key") or ""), str(payload.get("caption") or ""))))
        return {"ok": True, "messenger_account_id": account_id, "status": receipt.status.value,
                "message_reference": receipt.message_reference, "reason_code": receipt.safe_reason_code}
    app._authorize_provider_operation_account(actor, account_id, "operate")
    app._require_provider_capability_service().require(account_id,
        ProviderCapability.MEDIA_READ if action == "media/content" else ProviderCapability.CONTACTS_READ)
    runtime = app._runtime_registry.runtime_for_account(account_id)
    if not isinstance(runtime, BaleAccountRuntime):
        raise ProviderExtensionError("Operation unavailable.", code="provider_operation_not_implemented")
    if action == "media/content":
        app._require_provider_operation_fields(payload, {"content_reference"})
        reference = str(payload.get("content_reference") or "")
        if not reference.startswith("bale:download:"):
            raise CompositionValidationError("Invalid media reference.", code="provider_media_reference_invalid")
        result = runtime.request("bale.provider.media.content", {"content_handle": reference.removeprefix("bale:download:")})
        return {"ok": True, "messenger_account_id": account_id, **result}
    app._require_provider_operation_fields(payload, {"query", "cursor", "limit"})
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 128:
        raise CompositionValidationError("Invalid contact search query.", code="provider_search_query_invalid")
    limit = app._integer(payload.get("limit", 100), "limit", minimum=1, maximum=500)
    cursor = payload.get("cursor")
    if cursor is not None and not isinstance(cursor, str):
        raise CompositionValidationError("Invalid contact cursor.", code="provider_cursor_invalid")
    result = runtime.request(
        "bale.provider.contacts.search",
        {"query": query, "limit": limit, **({"cursor": cursor} if cursor is not None else {})},
        timeout_seconds=90,
    )
    return {"ok": True, "messenger_account_id": account_id, "contacts": [
        {"contact_reference": f"bale:user:{item['peer']['id']}", "display_name": item.get("name") or item.get("local_name") or ""}
        for item in result["contacts"] if isinstance(item.get("peer"), dict) and item["peer"].get("type") == 1],
        "next_cursor": result.get("next_cursor")}

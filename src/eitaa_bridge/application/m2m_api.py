"""Machine-to-machine API surface for the education/exam system integration.

Contract: docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md

Rules enforced here (do not weaken):
- Only what the local system or the provider actually proves is reported.
  Recipient resolution is strictly read-only and never fabricates peer
  references; raw phone numbers are never used as peer references.
- Delivery status distinguishes accepted / provider_succeeded / uncertain /
  not_found. Automatic retry for `uncertain` is the caller's problem and is
  documented as forbidden without a safety witness.
- The service actor runs with the least privilege role ("user"), never "admin".
- A claimed chat attempt exits only resolved (F-091): the reply is stored
  atomically with its conversation (``record_exchange``) or the claim is
  failed with its real error code (``fail_reply``); waiters receive the same
  failure and a retry claims fresh. Save failures are never masked by
  cleanup errors.
"""

from typing import Any, Callable, Mapping

from .api import ApiResponse
from . import agent_gateway as agent_gateway_module
from .agent_gateway import AgentChatContext, TestAgentAdapter, session_store
from ..errors import BridgeError

import asyncio
import re
import time
import hashlib
from .provider_orchestration import ProviderApplicationOrchestrator, ProviderOperationActor
from ..providers.contracts import ProviderSendTextRequest, ProviderPeerReference, ProviderSendStatus
from ..infrastructure.coordinator import CoordinatorDatabase
from ..errors import ProviderExtensionError

_AGENT_MAX_MESSAGE_CHARS = 4096
_AGENT_MAX_ID_CHARS = 128
_AGENT_MESSAGE_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_DIALOG_REFERENCE = re.compile(r"^(?P<peer_type>user|chat|channel):(?P<peer_id>[0-9]{1,20})$")
_PEER_KIND_BY_TYPE = {"user": "private", "chat": "group", "channel": "channel"}

ResolveHandler = Callable[[list[Mapping[str, Any]], str], list[dict[str, Any]]]


def _value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def handle_agent_chat(body: Mapping[str, Any], service_auth_context: Any) -> ApiResponse:
    if "agent.chat" not in getattr(service_auth_context, "scopes", []):
        return ApiResponse(403, {"ok": False, "error": "agent_chat_forbidden"})

    web_user_id = body.get("web_user_id")
    session_id = body.get("session_id")
    message = body.get("message")
    message_id = body.get("message_id")

    if not web_user_id or not session_id or not message:
        return ApiResponse(400, {"ok": False, "error": "missing_parameters"})
    if not message_id or not _AGENT_MESSAGE_ID.fullmatch(str(message_id)):
        return ApiResponse(400, {"ok": False, "error": "agent_message_id_required"})
    if len(str(session_id)) > _AGENT_MAX_ID_CHARS or len(str(web_user_id)) > _AGENT_MAX_ID_CHARS:
        return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "identifier too long"})
    if len(str(message)) > _AGENT_MAX_MESSAGE_CHARS:
        return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "message too long"})

    store = agent_gateway_module.session_store
    context = AgentChatContext(
        web_user_id=str(web_user_id),
        session_id=str(session_id),
        service_name=getattr(service_auth_context, "service_name", "default_service")
    )
    # A message id is bound to the content of its request: the hash never
    # carries the message text into logs, audit or receipts.
    message_hash = hashlib.sha256(str(message).encode("utf-8")).hexdigest()

    try:
        # Atomic first-run/replay decision, safe against racing requests on
        # the same message id (in-process guarantee; see the contract).
        outcome, payload = store.claim_reply(context, str(message_id), message_hash)

        if outcome == "conflict":
            return ApiResponse(409, {"ok": False, "error": "agent_message_id_conflict"})

        if outcome == "replay":
            record = payload
            return ApiResponse(200, {
                "ok": True,
                "response": record.response,
                "session_id": context.session_id,
                "is_test_response": record.is_test_response,
                "replayed": True,
            })

        if outcome == "inflight":
            inflight = payload
            loop = asyncio.get_running_loop()
            wait_seconds = float(getattr(agent_gateway_module, "AGENT_INFLIGHT_WAIT_SECONDS", 30.0))
            finished = await loop.run_in_executor(
                None, lambda: inflight.event.wait(wait_seconds)
            )
            if not finished:
                # The first attempt is still running; nothing was retried and
                # nothing was double-charged to the agent.
                return ApiResponse(503, {"ok": False, "error": "agent_reply_pending"})
            if inflight.error_code is not None:
                code = inflight.error_code
                if code == "agent_communication_failed":
                    return ApiResponse(502, {"ok": False, "error": "agent_communication_failed"})
                return ApiResponse(400, {"ok": False, "error": code})
            record = inflight.result
            if record is None:
                return ApiResponse(503, {"ok": False, "error": "agent_reply_pending"})
            return ApiResponse(200, {
                "ok": True,
                "response": record.response,
                "session_id": context.session_id,
                "is_test_response": record.is_test_response,
                "replayed": True,
            })

        # This caller owns the first adapter attempt. Every exit below must
        # resolve the claim for this message id (F-091): the reply is either
        # stored for replay or the claim is failed with its real error code —
        # a failed save must never leave the id pending in-flight.
        current_adapter = agent_gateway_module.default_agent_adapter
        try:
            history = store.get_history(context)
        except BaseException:
            # Nothing has run yet and the claim is still ours; release it so
            # a retry can claim fresh.
            store.fail_reply(context, str(message_id), "agent_reply_not_stored")
            raise
        try:
            response = await current_adapter.chat(
                str(message), context.session_id, context, history=history
            )
        except BridgeError as e:
            code = getattr(e, "code", "agent_communication_failed")
            store.fail_reply(context, str(message_id), code)
            if code == "agent_communication_failed":
                return ApiResponse(502, {"ok": False, "error": "agent_communication_failed"})
            return ApiResponse(400, {"ok": False, "error": code})
        except Exception:
            # Any adapter-side failure is an upstream agent outage, not a
            # client error; fail honestly with 502.
            store.fail_reply(context, str(message_id), "agent_communication_failed")
            return ApiResponse(502, {"ok": False, "error": "agent_communication_failed"})
        except BaseException:
            # Cancellation (client disconnect, loop teardown) must release
            # racing waiters too; nothing is cached because nothing completed.
            store.fail_reply(context, str(message_id), "agent_first_attempt_cancelled")
            raise

        # The exchange — user message, agent message and the replayable reply
        # record — becomes visible atomically or not at all. On any failure
        # record_exchange rolls the partial state back, resolves the claim
        # with the real failure code (releasing waiters) and re-raises the
        # original error unmasked (F-091).
        store.record_exchange(
            context,
            str(message_id),
            message_hash,
            str(message),
            response.response,
            bool(response.is_test_response),
        )

        return ApiResponse(200, {
            "ok": True,
            "response": response.response,
            "session_id": response.session_id,
            "is_test_response": bool(response.is_test_response),
            "replayed": False,
        })
    except BridgeError as e:
        code = getattr(e, "code", "agent_error")
        if code == "agent_communication_failed":
            return ApiResponse(502, {"ok": False, "error": "agent_communication_failed"})
        return ApiResponse(400, {"ok": False, "error": code})
    except Exception:
        return ApiResponse(500, {"ok": False, "error": "internal_error"})

async def handle_agent_health() -> ApiResponse:
    current_adapter = agent_gateway_module.default_agent_adapter
    is_health = await current_adapter.health()
    adapter_type = "test" if isinstance(current_adapter, TestAgentAdapter) else "configurable"
    return ApiResponse(200, {
        "ok": True,
        "agent_available": is_health,
        "adapter_type": adapter_type
    })


_M2M_MESSAGE_STATUS_ROUTE = re.compile(r"^/api/v2/m2m/messages/(?P<idempotency_key>[A-Za-z0-9._:-]{16,128})/status$")

def _get_actor(service_auth_context: Any) -> ProviderOperationActor:
    actor_id = getattr(service_auth_context, "created_by_app_user_id", None)
    if not actor_id:
        actor_id = getattr(service_auth_context, "credential_id", None)
    if not actor_id:
        actor_id = getattr(service_auth_context, "id", "00000000-0000-4000-8000-000000000000")
    return ProviderOperationActor(
        app_user_id=str(actor_id),
        global_role="user",
        service_credential_id=str(getattr(service_auth_context, "id", "")) or None,
    )

def _check_scope(service_auth_context: Any, required_scope: str) -> None:
    scopes = getattr(service_auth_context, "scopes", [])
    if required_scope not in scopes:
        raise ProviderExtensionError("Insufficient scope.", code="m2m_scope_insufficient")

def _check_account_allowed(service_auth_context: Any, messenger_account_id: str) -> None:
    # Fail-closed: a credential without an explicit, non-empty account list
    # (legacy or malformed row) is allowed nothing.
    allowed = getattr(service_auth_context, "allowed_messenger_account_ids", None)
    if not allowed:
        raise ProviderExtensionError(
            "Service credential has no authorized messenger accounts.",
            code="m2m_account_not_allowed",
        )
    if messenger_account_id not in allowed:
        raise ProviderExtensionError("Account not allowed.", code="m2m_account_not_allowed")

def _validate_provider(service_auth_context: Any, coordinator: CoordinatorDatabase | None, messenger_account_id: str, requested_provider: str | None) -> str:
    if coordinator is None:
        if requested_provider:
            return requested_provider
        raise ProviderExtensionError(
            "The target provider could not be determined.",
            code="m2m_provider_mismatch",
        )
    try:
        runtime = coordinator.messenger_account_runtime(messenger_account_id)
    except Exception as exc:
        raise ProviderExtensionError("Account not found.", code="m2m_account_not_found") from exc
    account_provider = str(getattr(runtime, "provider", ""))
    if not account_provider:
        raise ProviderExtensionError("Account not found.", code="m2m_account_not_found")
    # Fail-closed: an empty or missing provider allowlist authorizes nothing.
    allowed_providers = getattr(service_auth_context, "allowed_providers", None)
    if not allowed_providers:
        raise ProviderExtensionError(
            "Service credential has no authorized providers.",
            code="m2m_provider_not_allowed",
        )
    if account_provider not in allowed_providers:
        raise ProviderExtensionError("Provider not allowed for this service.", code="m2m_provider_not_allowed")
    if requested_provider and runtime.provider != requested_provider:
        raise ProviderExtensionError("Provider mismatch.", code="m2m_provider_mismatch")
    return account_provider

def _error_response(exc: ProviderExtensionError, default_status: int = 400) -> ApiResponse:
    status = default_status
    if any(k in exc.code for k in ("forbidden", "not_allowed", "insufficient")):
        status = 403
    return ApiResponse(status, {
        "ok": False,
        "error": {"error_code": exc.code, "message": str(exc)},
        "reason": str(exc),
        "code": exc.code,
    })


async def handle_send_text(
    body: Mapping[str, Any],
    service_auth_context: Any,
    orchestrator: ProviderApplicationOrchestrator | None,
    coordinator: CoordinatorDatabase | None,
    request_id: str | None,
) -> ApiResponse:
    try:
        _check_scope(service_auth_context, "messages.send")
        messenger_account_id = str(body.get("messenger_account_id", "")).strip()
        if not messenger_account_id:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "messenger_account_id is required"})
        _check_account_allowed(service_auth_context, messenger_account_id)
        requested_provider = body.get("provider")
        if requested_provider is not None:
            requested_provider = str(requested_provider).strip()
        _validate_provider(service_auth_context, coordinator, messenger_account_id, requested_provider)

        message_type = str(body.get("message_type", "")).strip()
        if message_type not in ("otp", "notice"):
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "invalid message_type"})
        text = str(body.get("text", ""))
        if message_type == "otp" and len(text) > 256:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Text too long", "code": "m2m_text_too_long"})
        if message_type == "notice" and len(text) > 4096:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Text too long", "code": "m2m_text_too_long"})
        if body.get("confirm") is not True:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Confirm required", "code": "m2m_confirm_required"})

        peer_data = body.get("peer_reference")
        if not isinstance(peer_data, dict):
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Invalid peer_reference"})
        peer_kind = str(peer_data.get("kind", "")).strip()
        peer_value = str(peer_data.get("value", "")).strip()

        if peer_kind == "dialog":
            dialog_match = _DIALOG_REFERENCE.fullmatch(peer_value)
            if dialog_match is None:
                return ApiResponse(400, {
                    "ok": False,
                    "error": "validation_error",
                    "reason": "dialog peer_reference must look like '<user|chat|channel>:<id>'",
                    "code": "m2m_peer_reference_invalid",
                })
            peer_ref = ProviderPeerReference(
                opaque_reference=dialog_match.group("peer_type") + ":" + dialog_match.group("peer_id"),
                kind=_PEER_KIND_BY_TYPE[dialog_match.group("peer_type")],
            )
        elif peer_kind in ("phone", "username"):
            # A raw phone number or username is never used as a peer reference.
            # Callers must resolve it first via /api/v2/m2m/recipients/resolve.
            return ApiResponse(409, {
                "ok": False,
                "error": {"error_code": "m2m_recipient_unresolved", "message": "Resolve the recipient first."},
                "code": "m2m_recipient_unresolved",
            })
        else:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Unsupported peer kind", "code": "m2m_peer_unsupported"})

        idempotency_key = str(body.get("idempotency_key", "")).strip()
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            return ApiResponse(400, {
                "ok": False,
                "error": "validation_error",
                "reason": "idempotency_key must be 16-128 chars of [A-Za-z0-9._:-]",
                "code": "m2m_idempotency_key_invalid",
            })
        request = ProviderSendTextRequest(peer=peer_ref, text=text, idempotency_key=idempotency_key)

        if orchestrator is None:
            return ApiResponse(500, {"ok": False, "error": "internal_error", "reason": "no orchestrator"})

        actor = _get_actor(service_auth_context)
        receipt = await orchestrator.send_text(
            actor=actor,
            messenger_account_id=messenger_account_id,
            correlation_id=request_id or idempotency_key[:32],
            deadline_unix_ms=int(time.time() * 1000) + 15000,
            request=request,
        )

        delivery_status = "uncertain"
        if receipt.status is ProviderSendStatus.SUCCEEDED:
            delivery_status = "provider_succeeded"
        return ApiResponse(200, {"ok": True, "request_id": request_id, "delivery_status": delivery_status, "message_reference": receipt.message_reference, "safe_reason_code": receipt.safe_reason_code})
    except ProviderExtensionError as exc:
        return _error_response(exc)

def handle_resolve_recipients(
    body: Mapping[str, Any],
    service_auth_context: Any,
    coordinator: CoordinatorDatabase | None,
    resolver: ResolveHandler | None,
) -> ApiResponse:
    try:
        _check_scope(service_auth_context, "contacts.resolve")
        messenger_account_id = str(body.get("messenger_account_id", "")).strip()
        if not messenger_account_id:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "messenger_account_id is required"})
        _check_account_allowed(service_auth_context, messenger_account_id)
        requested_provider = body.get("provider")
        if requested_provider is not None:
            requested_provider = str(requested_provider).strip()
        _validate_provider(service_auth_context, coordinator, messenger_account_id, requested_provider)

        recipients = body.get("recipients", [])
        if not isinstance(recipients, list):
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "recipients must be a list"})
        if len(recipients) > 100:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Too many recipients", "code": "m2m_recipient_limit_exceeded"})

        normalized: list[dict[str, Any]] = []
        for rec in recipients:
            if not isinstance(rec, dict):
                return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "recipients must be objects"})
            kind = str(rec.get("kind", "")).strip()
            value = str(rec.get("value", "")).strip()
            if not value or len(value) > 256:
                return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "recipient value is missing or too long", "code": "m2m_recipient_value_invalid"})
            normalized.append({"kind": kind, "value": value})

        if resolver is not None:
            resolved_items = resolver(normalized, messenger_account_id)
        else:
            resolved_items = [
                {"kind": item["kind"], "status": "unsupported", "peer_reference": None, "reason": "resolve_unavailable"}
                for item in normalized
            ]

        results = []
        requires_import = False
        for item, resolved in zip(normalized, resolved_items):
            results.append({
                "kind": item["kind"],
                "value_hash": _value_hash(item["value"]),
                "status": resolved.get("status", "unresolved"),
                "peer_reference": resolved.get("peer_reference"),
                "reason": resolved.get("reason"),
            })
            if results[-1]["status"] == "unresolved":
                requires_import = True
        return ApiResponse(200, {"ok": True, "results": results, "requires_import": requires_import})
    except ProviderExtensionError as exc:
        return _error_response(exc)

def handle_message_status(
    idempotency_key: str,
    coordinator: CoordinatorDatabase | None,
    service_auth_context: Any | None = None,
) -> ApiResponse:
    if coordinator is None:
        return ApiResponse(200, {"ok": True, "delivery_status": "not_found", "message_reference": None, "timestamp": None})
    try:
        _check_scope(service_auth_context, "messages.status")
    except ProviderExtensionError as exc:
        return _error_response(exc, default_status=403)
    try:
        service_id = str(
            getattr(service_auth_context, "id", "")
            or getattr(service_auth_context, "credential_id", "")
            or ""
        )
        statement = (
            "SELECT outcome, result_reference, updated_at, messenger_account_id "
            "FROM provider_operation_receipts "
            "WHERE idempotency_key=? AND service_credential_id=?"
        )
        params: list[Any] = [
            idempotency_key,
            service_id,
        ]
        allowed = getattr(service_auth_context, "allowed_messenger_account_ids", None) if service_auth_context else None
        if allowed is not None:
            if not allowed:
                return ApiResponse(200, {"ok": True, "delivery_status": "not_found", "message_reference": None, "timestamp": None})
            statement += f" AND messenger_account_id IN ({','.join('?' for _ in allowed)})"
            params.extend(allowed)
        with coordinator._connect() as connection:
            row = connection.execute(statement, params).fetchone()
        if not row:
            # Not found covers unknown keys, other services' receipts and
            # legacy owner-less receipts alike; ownership is never guessed.
            return ApiResponse(200, {"ok": True, "delivery_status": "not_found", "message_reference": None, "timestamp": None})
        outcome = row["outcome"]
        delivery_status = "uncertain"
        if outcome == "succeeded":
            delivery_status = "provider_succeeded"
        elif outcome == "in_progress":
            delivery_status = "accepted"
        return ApiResponse(200, {"ok": True, "delivery_status": delivery_status, "message_reference": row["result_reference"], "timestamp": row["updated_at"]})
    except Exception:
        return ApiResponse(200, {"ok": True, "delivery_status": "not_found", "message_reference": None, "timestamp": None})

_M2M_ACCOUNT_SEND_TEXT_ROUTE = re.compile(r"^/api/v2/m2m/messenger-accounts/(?P<acc_id>[0-9a-fA-F-]{36})/messages/send-text$")

async def dispatch_m2m(
    method: str,
    path: str,
    body: Mapping[str, Any] | None,
    service_auth_context: Any,
    request_id: str | None,
    orchestrator: ProviderApplicationOrchestrator | None = None,
    coordinator: CoordinatorDatabase | None = None,
    resolve_handler: ResolveHandler | None = None,
) -> ApiResponse:
    account_send_match = _M2M_ACCOUNT_SEND_TEXT_ROUTE.fullmatch(path)
    if method == "POST" and (path == "/api/v2/m2m/messages/send-text" or account_send_match):
        payload = dict(body or {})
        if account_send_match:
            payload.setdefault("messenger_account_id", account_send_match.group("acc_id"))
            payload.setdefault("confirm", True)
            payload.setdefault("message_type", "notice")
            if "phone" in payload and "peer_reference" not in payload:
                payload["peer_reference"] = {"kind": "phone", "value": payload["phone"]}
            if "idempotency_key" not in payload:
                derived = re.sub(r"[^A-Za-z0-9._:-]", "0", str(request_id or ""))
                payload["idempotency_key"] = (f"compat_{derived}"[:32]).ljust(16, "0")
        return await handle_send_text(payload, service_auth_context, orchestrator, coordinator, request_id)
    elif method == "POST" and path == "/api/v2/m2m/recipients/resolve":
        return handle_resolve_recipients(body or {}, service_auth_context, coordinator, resolve_handler)

    status_match = _M2M_MESSAGE_STATUS_ROUTE.fullmatch(path)
    if method == "GET" and status_match:
        return handle_message_status(status_match.group("idempotency_key"), coordinator, service_auth_context)
    elif method == "POST" and path == "/api/v2/m2m/agent/chat":
        return await handle_agent_chat(body or {}, service_auth_context)
    elif method == "GET" and path == "/api/v2/m2m/agent/health":
        return await handle_agent_health()

    return ApiResponse(404, {"ok": False, "error": "not_found"})

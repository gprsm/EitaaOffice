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
from ..infrastructure.coordinator import sender_profiles as sender_profile_module
from ..infrastructure.coordinator import reservations as reservations_module
from ..errors import ProviderExtensionError

_AGENT_MAX_MESSAGE_CHARS = 4096
_AGENT_MAX_ID_CHARS = 128
_AGENT_MESSAGE_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_DIALOG_REFERENCE = re.compile(r"^(?:(?P<provider>bale):)?(?P<peer_type>user|chat|group|channel):(?P<peer_id>[0-9]{1,20})$")
_PEER_KIND_BY_TYPE = {"user": "private", "chat": "group", "group": "group", "channel": "channel"}

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

    current_adapter = agent_gateway_module.get_current_adapter()
    is_test = getattr(current_adapter, "is_test_adapter", True)
    policy_store = getattr(agent_gateway_module, "ai_data_policy_store", None)

    # Fail closed if live adapter is used without an available policy store (zero calls before gate)
    if not is_test and policy_store is None:
        return ApiResponse(503, {"ok": False, "error": "ai_policy_unavailable"})

    # Check service policy if policy_store is present
    if policy_store is not None:
        service_name = getattr(service_auth_context, "service_name", "default_service")
        policy = policy_store.get_policy(service_name)
        if not (is_test and policy.revision == 0):
            if policy.policy_level == "disabled":
                return ApiResponse(403, {"ok": False, "error": "ai_policy_disabled"})

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
        current_adapter = agent_gateway_module.get_current_adapter()
        try:
            history = store.get_history(context)
        except BaseException:
            # Nothing has run yet and the claim is still ours; release it so
            # a retry can claim fresh.
            store.fail_reply(context, str(message_id), "agent_reply_not_stored")
            raise

        # Phase 6: Apply server-side AI Data Policy & Egress Gate
        egress_msg = str(message)
        egress_history = history
        egress_context = context

        if getattr(agent_gateway_module, "ai_data_policy_store", None) is not None:
            policy = agent_gateway_module.ai_data_policy_store.get_policy(context.service_name)
            # If adapter is test adapter and policy is unconfigured (rev 0), allow default test fixture chat.
            # Otherwise, fail-closed and enforce policy strictly.
            if getattr(current_adapter, "is_test_adapter", True) and policy.revision == 0:
                pass
            else:
                from ..infrastructure.coordinator.ai_data_policy import build_outbound_egress
                try:
                    egress = build_outbound_egress(
                        policy=policy,
                        service_name=context.service_name,
                        web_user_id=context.web_user_id,
                        raw_message=str(message),
                        raw_history=history,
                    )
                    egress_msg = egress.message
                    egress_history = egress.history
                    egress_context = AgentChatContext(
                        web_user_id=egress.pseudonym_user_id,
                        session_id=context.session_id,
                        service_name=context.service_name,
                        max_message_length=context.max_message_length,
                        max_context_messages=context.max_context_messages,
                        session_ttl_seconds=context.session_ttl_seconds,
                    )
                except BridgeError as exc:
                    store.fail_reply(context, str(message_id), exc.code)
                    status_code = getattr(exc, "status_code", 403)
                    return ApiResponse(status_code, {"ok": False, "error": exc.code})

        try:
            response = await current_adapter.chat(
                egress_msg, egress_context.session_id, egress_context, history=egress_history
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

# P1 sender profiles: an external request names intent (+ optional explicit
# sender profile id) and never an arbitrary account as a bypass route.
_M2M_SENDER_INTENT_TO_TYPE = {"otp": "otp", "notification": "notice"}


def _resolve_sender_profile(
    body: Mapping[str, Any],
    service_auth_context: Any,
    coordinator: CoordinatorDatabase | None,
    intent: str | None,
) -> tuple[str | None, str | None]:
    """Resolve the sending account through the service's sender profile.

    Returns (messenger_account_id, error_response). Exactly one of the two is
    set. The legacy explicit ``messenger_account_id`` remains valid; when an
    enabled profile is configured for this intent it must match — an account
    id can never be used to bypass the pinned sender.
    """
    credential_id = str(
        getattr(service_auth_context, "service_id", None)
        or getattr(service_auth_context, "id", None)
        or getattr(service_auth_context, "credential_id", None)
        or ""
    )
    profile_store = (
        sender_profile_module.ServiceSenderProfileStore(coordinator)
        if coordinator is not None
        else None
    )
    sender_profile_id = str(body.get("sender_profile_id", "") or "").strip()
    if sender_profile_id:
        if profile_store is None:
            return None, _error_response(ProviderExtensionError(
                "Sender profiles are unavailable.", code="sender_profile_unavailable",
            ))
        profile = profile_store.get_profile(sender_profile_id)
        if (
            profile is None
            or not credential_id
            or profile.service_credential_id != credential_id
            or not profile.enabled
        ):
            return None, ApiResponse(400, {
                "ok": False,
                "error": {"error_code": "sender_not_configured",
                          "message": "No enabled sender profile is configured for this service and intent."},
                "reason": "sender profile not configured",
                "code": "sender_not_configured",
            })
        if not profile_store.account_available(profile.messenger_account_id):
            return None, _error_response(ProviderExtensionError(
                "The pinned sender account is unavailable.",
                code="account_unavailable",
            ))
        explicit_account = str(body.get("messenger_account_id", "") or "").strip()
        if explicit_account and explicit_account != profile.messenger_account_id:
            return None, _error_response(ProviderExtensionError(
                "The requested account does not match the sender profile.",
                code="sender_profile_mismatch",
            ))
        return profile.messenger_account_id, None

    messenger_account_id = str(body.get("messenger_account_id", "") or "").strip()
    if not messenger_account_id:
        return None, ApiResponse(400, {
            "ok": False,
            "error": {"error_code": "sender_not_configured",
                      "message": "Provide sender_profile_id or messenger_account_id."},
            "reason": "sender not configured",
            "code": "sender_not_configured",
        })
    # Anti-bypass: once an enabled profile pins this intent, a hand-picked
    # account_id cannot silently take another route.
    if profile_store is not None and intent:
        pinned = profile_store.try_get_enabled_profile(credential_id, intent)
        if pinned is not None and pinned.messenger_account_id != messenger_account_id:
            return None, _error_response(ProviderExtensionError(
                "A sender profile pins this intent to another account.",
                code="sender_profile_mismatch",
            ))
    return messenger_account_id, None


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
    elif exc.code in {"account_unavailable", "sender_profile_mismatch", "stale_revision"}:
        status = 409
    elif exc.code == "provider_operation_rate_limited":
        status = 429
    elif exc.code == "provider_operation_circuit_open":
        status = 503
    headers: dict[str, str] = {}
    retry_after_seconds = exc.safe_context.get("retry_after_seconds")
    if retry_after_seconds:
        # Whole seconds, rounded up; the caller must not retry sooner.
        headers["Retry-After"] = str(max(1, int(retry_after_seconds)))
    return ApiResponse(status, {
        "ok": False,
        "error": {"error_code": exc.code, "message": str(exc)},
        "reason": str(exc),
        "code": exc.code,
    }, headers=headers)


async def handle_send_text(
    body: Mapping[str, Any],
    service_auth_context: Any,
    orchestrator: ProviderApplicationOrchestrator | None,
    coordinator: CoordinatorDatabase | None,
    request_id: str | None,
) -> ApiResponse:
    try:
        _check_scope(service_auth_context, "messages.send")
        intent = str(body.get("intent", "") or "").strip()
        message_type = str(body.get("message_type", "")).strip()
        if intent:
            if intent not in _M2M_SENDER_INTENT_TO_TYPE:
                return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "invalid intent", "code": "m2m_sender_intent_invalid"})
            message_type = _M2M_SENDER_INTENT_TO_TYPE[intent]
        elif message_type == "otp":
            intent = "otp"
        elif message_type == "notice":
            intent = "notification"

        messenger_account_id, sender_error = _resolve_sender_profile(
            body, service_auth_context, coordinator, intent
        )
        if sender_error is not None:
            return sender_error
        _check_account_allowed(service_auth_context, messenger_account_id)
        requested_provider = body.get("provider")
        if requested_provider is not None:
            requested_provider = str(requested_provider).strip()
        account_provider = _validate_provider(service_auth_context, coordinator, messenger_account_id, requested_provider)

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
            if dialog_match is None or (
                (account_provider == "bale") != (dialog_match.group("provider") == "bale")
            ) or (account_provider != "bale" and dialog_match.group("peer_type") == "group") or (
                account_provider == "bale" and dialog_match.group("peer_type") == "chat"
            ):
                return ApiResponse(400, {
                    "ok": False,
                    "error": "validation_error",
                    "reason": "dialog peer_reference must look like '<user|chat|channel>:<id>'",
                    "code": "m2m_peer_reference_invalid",
                })
            peer_ref = ProviderPeerReference(
                opaque_reference=peer_value,
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

async def handle_delivery_preflight(
    body: Mapping[str, Any],
    service_auth_context: Any,
    coordinator: CoordinatorDatabase | None,
    request_quota_reader: Callable[[str], dict[str, Any]] | None = None,
) -> ApiResponse:
    """Read-only delivery preflight (P2).

    Answers whether the bridge is *locally* ready to attempt a new delivery
    for the pinned sender, with the observed reason and the earliest allowed
    retry. Nothing is resolved, imported, sent, reserved or mutated here:
    no orchestrator call, no worker RPC, no contact write, no token
    acquisition and no circuit change. ``ready`` never guarantees provider
    capacity or acceptance (``capacity_guaranteed`` is always false).
    """
    try:
        _check_scope(service_auth_context, "messages.send")
        from ..infrastructure.coordinator.rate_policy import AccountExecutionPolicyService
        from ..infrastructure.coordinator import sender_profiles as sender_profile_module

        intent = str(body.get("intent", "") or "").strip()
        if intent not in _M2M_SENDER_INTENT_TO_TYPE:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "invalid intent", "code": "m2m_sender_intent_invalid"})
        recipient_kind = str(body.get("recipient_kind", "") or "").strip()
        if recipient_kind not in ("existing", "new"):
            return ApiResponse(200, {
                "ok": True,
                "decision": "unsupported",
                "can_attempt": False,
                "retry_after_seconds": None,
                "sender_profile_revision": None,
                "observed_at": None,
                "valid_until": None,
                "steps": [],
                "constraints": [],
                "capacity_guaranteed": False,
            })

        messenger_account_id, sender_error = _resolve_sender_profile(
            body, service_auth_context, coordinator, intent
        )
        if sender_error is not None:
            return sender_error
        # Unauthorized callers learn nothing beyond the fence verdicts.
        _check_account_allowed(service_auth_context, messenger_account_id)
        _validate_provider(service_auth_context, coordinator, messenger_account_id, None)

        observed_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".000Z"
        valid_until = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 5)
        ) + ".000Z"
        steps = (
            ["resolve", "send"]
            if recipient_kind == "existing"
            else ["prepare_contact", "resolve", "send"]
        )

        def _constraint(
            *, scope: str, operation: str, source: str, certainty: str,
            reason: str | None, retry_after_seconds: int | None,
            updated_at: str | None,
        ) -> dict[str, Any]:
            return {
                "scope": scope,
                "operation": operation,
                "source": source,
                "certainty": certainty,
                "reason": reason,
                "retry_after_seconds": retry_after_seconds,
                "updated_at": updated_at,
            }

        profile_store = sender_profile_module.ServiceSenderProfileStore(coordinator)
        sender_profile_revision = None
        if coordinator is not None:
            credential_id = str(
                getattr(service_auth_context, "service_id", None)
                or getattr(service_auth_context, "id", None)
                or getattr(service_auth_context, "credential_id", None)
                or ""
            )
            pinned = profile_store.get_profile_for(credential_id, intent)
            if pinned is not None and pinned.enabled and pinned.messenger_account_id == messenger_account_id:
                sender_profile_revision = pinned.revision

        constraints: list[dict[str, Any]] = []
        blockers: list[int] = []
        decision = "ready"

        # 1. Local account+operation capacity (token bucket), computed
        #    without acquiring and without mutating any row.
        snapshot = None
        if coordinator is not None:
            snapshot = AccountExecutionPolicyService(coordinator).read_only_snapshot(
                messenger_account_id=messenger_account_id,
                operation_scope="messages.send_text",
            )
        if snapshot is not None and snapshot["blocked_reason"]:
            reason = str(snapshot["blocked_reason"])
            retry_after_seconds = max(1, int(snapshot["retry_after_ms"] or 1000) // 1000 + (
                1 if int(snapshot["retry_after_ms"] or 1000) % 1000 else 0
            ))
            source = "provider_observed" if reason == "retry_after" else "local_policy"
            if reason == "circuit_open" and snapshot.get("last_error_class"):
                source = "provider_observed"
            constraints.append(_constraint(
                scope="account", operation="messages.send_text", source=source,
                certainty="observed", reason=reason,
                retry_after_seconds=retry_after_seconds,
                updated_at=str(snapshot.get("updated_at")),
            ))
            blockers.append(retry_after_seconds)
            decision = "wait"
        elif snapshot is None:
            # No local limit has ever been applied: absence of a constraint
            # is not a capacity confirmation.
            constraints.append(_constraint(
                scope="account", operation="messages.send_text",
                source="local_policy", certainty="assumed", reason=None,
                retry_after_seconds=None, updated_at=observed_at,
            ))

        # 2. Credential request quota (separate from provider send capacity;
        #    status polling counts here and must never be read as messages).
        if request_quota_reader is not None:
            credential_id = str(
                getattr(service_auth_context, "service_id", None)
                or getattr(service_auth_context, "id", None)
                or getattr(service_auth_context, "credential_id", None)
                or ""
            )
            quota = request_quota_reader(credential_id)
            constraints.append(_constraint(
                scope="credential", operation="http.request",
                source="credential_quota", certainty=str(quota.get("certainty", "observed")),
                reason=None if quota.get("remaining") else "request_quota_exhausted",
                retry_after_seconds=int(quota.get("retry_after_seconds") or 0) or None,
                updated_at=str(quota.get("updated_at")),
            ))
            if not quota.get("remaining"):
                blockers.append(int(quota.get("retry_after_seconds") or 1))
                decision = "wait"

        # 3. Pinned account availability (honest snapshot, no substitution).
        if coordinator is not None and not profile_store.account_available(messenger_account_id):
            return ApiResponse(503, {
                "ok": False,
                "decision": "unavailable",
                "can_attempt": False,
                "retry_after_seconds": None,
                "sender_profile_revision": sender_profile_revision,
                "observed_at": observed_at,
                "valid_until": valid_until,
                "steps": steps,
                "constraints": constraints,
                "capacity_guaranteed": False,
            })

        return ApiResponse(200, {
            "ok": True,
            "decision": decision,
            "can_attempt": decision == "ready",
            "retry_after_seconds": max(blockers) if blockers else None,
            "sender_profile_revision": sender_profile_revision,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "steps": steps,
            "constraints": constraints,
            "capacity_guaranteed": False,
        })
    except ProviderExtensionError as exc:
        return _error_response(exc)


        return ApiResponse(200, {
            "ok": True,
            "decision": decision,
            "can_attempt": decision == "ready",
            "retry_after_seconds": max(blockers) if blockers else None,
            "sender_profile_revision": sender_profile_revision,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "steps": steps,
            "constraints": constraints,
            "capacity_guaranteed": False,
        })
    except ProviderExtensionError as exc:
        return _error_response(exc)


_M2M_DELIVERY_RESERVATION_ROUTE = re.compile(
    r"^/api/v2/m2m/delivery/reservations/(?P<res_id>[0-9a-fA-F-]{36})$"
)
_M2M_DELIVERY_RESERVATION_CANCEL_ROUTE = re.compile(
    r"^/api/v2/m2m/delivery/reservations/(?P<res_id>[0-9a-fA-F-]{36})/cancel$"
)
_PHONE_PATTERN = re.compile(r"\+[1-9][0-9]{7,14}")

_DELIVERY_RESERVATION_HTTP_STATUS = {
    "delivery_reservation_capacity_unavailable": 429,
    "delivery_reservation_rate_limited": 429,
    "delivery_reservation_outstanding_limit": 429,
    "delivery_reservation_circuit_open": 503,
    "delivery_reservation_conflict": 409,
    "delivery_reservation_already_consumed": 409,
    "delivery_reservation_expired": 409,
    "delivery_reservation_inactive": 409,
    "sender_profile_revision_changed": 409,
    "account_unavailable": 409,
}


def _reservation_error_response(exc: Any) -> ApiResponse:
    code = getattr(exc, "code", "delivery_reservation_error")
    status = _DELIVERY_RESERVATION_HTTP_STATUS.get(code, 400)
    headers: dict[str, str] = {}
    retry_after_seconds = (getattr(exc, "safe_context", {}) or {}).get(
        "retry_after_seconds"
    )
    if status == 429 and retry_after_seconds:
        headers["Retry-After"] = str(max(1, int(retry_after_seconds)))
    return ApiResponse(status, {
        "ok": False,
        "error": {"error_code": exc.code, "message": str(exc)},
        "reason": str(exc),
        "code": getattr(exc, "code", "delivery_reservation_error"),
    }, headers=headers)


def _reservation_credential_id(service_auth_context: Any) -> str:
    return str(
        getattr(service_auth_context, "service_id", None)
        or getattr(service_auth_context, "id", None)
        or getattr(service_auth_context, "credential_id", None)
        or ""
    )


def handle_delivery_reservation_cancel(
    reservation_id: str, service_auth_context: Any, reservation_store: Any | None
) -> ApiResponse:
    if reservation_store is None:
        return ApiResponse(503, {"ok": False, "error": {"error_code": "delivery_reservation_unavailable"}, "code": "delivery_reservation_unavailable"})
    _check_scope(service_auth_context, "messages.send")
    credential_id = str(
        getattr(service_auth_context, "service_id", None)
        or getattr(service_auth_context, "id", None)
        or getattr(service_auth_context, "credential_id", None)
        or ""
    )
    reservation = reservation_store.cancel(
        reservation_id=reservation_id,
        service_credential_id=credential_id,
    )
    if reservation is None:
        return ApiResponse(404, {
            "ok": False,
            "error": {"error_code": "delivery_reservation_not_found",
                      "message": "No such reservation for this service."},
            "code": "delivery_reservation_not_found",
        })
    return ApiResponse(200, {"ok": True, "reservation": _safe_reservation(reservation)})


def handle_delivery_reservation_status(
    reservation_id: str, service_auth_context: Any, reservation_store: Any | None
) -> ApiResponse:
    if reservation_store is None:
        return ApiResponse(503, {"ok": False, "error": {"error_code": "delivery_reservation_unavailable", "message": "Reservations are unavailable."}, "code": "delivery_reservation_unavailable"})
    _check_scope(service_auth_context, "messages.send")
    reservation = reservation_store.status(
        reservation_id=reservation_id,
        service_credential_id=str(
            getattr(service_auth_context, "service_id", None)
            or getattr(service_auth_context, "id", None)
            or getattr(service_auth_context, "credential_id", None)
            or ""
        ),
    )
    if reservation is None:
        return ApiResponse(404, {
            "ok": False,
            "error": {"error_code": "delivery_reservation_not_found",
                      "message": "No such reservation for this service."},
            "code": "delivery_reservation_not_found",
        })
    return ApiResponse(200, {"ok": True, "reservation": _safe_reservation(reservation)})


def _safe_reservation(reservation) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "service_credential_id": reservation.service_credential_id,
        "intent": reservation.intent,
        "provider": reservation.provider,
        "messenger_account_id": reservation.messenger_account_id,
        "sender_profile_id": reservation.sender_profile_id,
        "sender_profile_revision": reservation.sender_profile_revision,
        "state": reservation.state,
        "operation_costs": reservation.operation_costs,
        "token_reserved": reservation.token_reserved,
        "token_refunded": reservation.token_refunded,
        "send_started": reservation.send_started_at is not None,
        "operation_id": reservation.operation_id,
        "created_at": reservation.created_at,
        "updated_at": reservation.updated_at,
        "expires_at": reservation.expires_at,
    }


def handle_delivery_reservation_create(
    body: Mapping[str, Any],
    service_auth_context: Any,
    coordinator: CoordinatorDatabase | None,
    request_id: str | None,
    reservation_store: Any | None,
) -> ApiResponse:
    """Create a durable delivery reservation (P3).

    The recipient is named as a normalized E.164 phone and is only ever
    stored as a server-keyed HMAC binding; the raw value is dropped here.
    Capacity decision, bucket debit and the insert are one SQLite
    transaction — no await, no worker, no network inside it.
    """
    try:
        _check_scope(service_auth_context, "messages.send")
        if reservation_store is None or coordinator is None:
            return ApiResponse(503, {
                "ok": False,
                "error": {"error_code": "delivery_reservation_unavailable",
                          "message": "Reservations are unavailable."},
                "code": "delivery_reservation_unavailable",
            })
        intent = str(body.get("intent", "") or "").strip()
        if intent not in _M2M_SENDER_INTENT_TO_TYPE:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "invalid intent", "code": "m2m_sender_intent_invalid"})
        recipient = body.get("recipient")
        if not isinstance(recipient, dict) or str(recipient.get("kind", "")).strip() != "phone":
            return ApiResponse(400, {
                "ok": False,
                "error": "validation_error",
                "reason": "recipient must be {'kind': 'phone', 'value': '+E164'}",
                "code": "delivery_recipient_unsupported",
            })
        phone = str(recipient.get("value", "")).strip()
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
            return ApiResponse(400, {
                "ok": False,
                "error": {"error_code": "m2m_phone_invalid", "message": "Canonical E.164 phone required."},
                "code": "m2m_phone_invalid",
            })
        idempotency_key = str(body.get("idempotency_key", "")).strip()
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            return ApiResponse(400, {
                "ok": False,
                "error": "validation_error",
                "reason": "idempotency_key must be 16-128 chars of [A-Za-z0-9._:-]",
                "code": "m2m_idempotency_key_invalid",
            })

        messenger_account_id, sender_error = _resolve_sender_profile(
            body, service_auth_context, coordinator, intent
        )
        if sender_error is not None:
            return sender_error
        _check_account_allowed(service_auth_context, messenger_account_id)
        account_provider = _validate_provider(service_auth_context, coordinator, messenger_account_id, None)

        credential_id = _reservation_credential_id(service_auth_context)
        profile_store = sender_profile_module.ServiceSenderProfileStore(coordinator)
        profile_revision = None
        try:
            pinned = profile_store.get_profile_for(credential_id, intent)
        except Exception:
            pinned = None
        if pinned is not None and pinned.enabled and pinned.messenger_account_id == messenger_account_id:
            # A pinned sender is authoritative: the reservation records the
            # profile and its revision so consume can detect a later change.
            sender_profile_id = pinned.id
            profile_revision = pinned.revision
        else:
            sender_profile_id = None
            profile_revision = None

        binding = reservation_store.bind_recipient(
            normalized_value=phone, intent=intent, service_id=credential_id
        )
        reservation = reservation_store.create(
            service_credential_id=credential_id,
            actor_app_user_id=_get_actor(service_auth_context).app_user_id,
            intent=intent,
            provider=account_provider,
            messenger_account_id=messenger_account_id,
            recipient_binding=binding,
            idempotency_key=idempotency_key,
            sender_profile_id=sender_profile_id,
            sender_profile_revision=profile_revision,
            ttl_seconds=int(body.get("ttl_seconds") or 120),
        )
        return ApiResponse(201, {
            "ok": True,
            "request_id": request_id,
            "reservation": _safe_reservation(reservation),
        })
    except reservations_module.DeliveryReservationError as exc:
        return _reservation_error_response(exc)
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
            "WHERE operation IN ('messages.send_text','messages.send_media') AND idempotency_key=? AND service_credential_id=?"
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
    request_quota_reader: Callable[[str], dict[str, Any]] | None = None,
    reservation_store: Any | None = None,
    otp_delivery_store: Any | None = None,
) -> ApiResponse:
    account_send_match = _M2M_ACCOUNT_SEND_TEXT_ROUTE.fullmatch(path)
    if method == "POST" and (path == "/api/v2/m2m/messages/send-text" or account_send_match):
        payload = dict(body or {})
        if account_send_match:
            payload.setdefault("messenger_account_id", account_send_match.group("acc_id"))
            # Explicit confirmation stays mandatory on the account-scoped
            # compatibility route, exactly like the canonical M2M send route.
            payload.setdefault("message_type", "notice")
            if "phone" in payload and "peer_reference" not in payload:
                payload["peer_reference"] = {"kind": "phone", "value": payload["phone"]}
            if "idempotency_key" not in payload:
                derived = re.sub(r"[^A-Za-z0-9._:-]", "0", str(request_id or ""))
                payload["idempotency_key"] = (f"compat_{derived}"[:32]).ljust(16, "0")
        return await handle_send_text(payload, service_auth_context, orchestrator, coordinator, request_id)
    elif method == "POST" and path == "/api/v2/m2m/recipients/prepare":
        return await handle_prepare_recipient(body or {}, service_auth_context, orchestrator, coordinator, request_id)
    elif method == "POST" and path == "/api/v2/m2m/recipients/resolve":
        return handle_resolve_recipients(body or {}, service_auth_context, coordinator, resolve_handler)
    elif method == "POST" and path == "/api/v2/m2m/delivery/preflight":
        return await handle_delivery_preflight(
            body or {}, service_auth_context, coordinator, request_quota_reader
        )
    elif method == "POST" and path == "/api/v2/m2m/delivery/reservations":
        return handle_delivery_reservation_create(
            body or {}, service_auth_context, coordinator, request_id, reservation_store
        )
    elif method == "POST" and path == "/api/v2/m2m/otp/deliveries":
        from .otp_delivery_pipeline import handle_otp_delivery_create
        return await handle_otp_delivery_create(
            body or {},
            service_auth_context,
            orchestrator=orchestrator,
            coordinator=coordinator,
            reservation_store=reservation_store,
            otp_store=otp_delivery_store,
            resolve_handler=resolve_handler,
            request_id=request_id,
        )
    cancel_match = _M2M_DELIVERY_RESERVATION_CANCEL_ROUTE.fullmatch(path)
    if cancel_match and method == "POST":
        return handle_delivery_reservation_cancel(
            cancel_match.group("res_id"), service_auth_context, reservation_store
        )

    reservation_match = _M2M_DELIVERY_RESERVATION_ROUTE.fullmatch(path)
    if reservation_match and method == "GET":
        return handle_delivery_reservation_status(
            reservation_match.group("res_id"), service_auth_context, reservation_store
        )

    otp_status_match = re.fullmatch(r"^/api/v2/m2m/otp/deliveries/(?P<delivery_id>[0-9a-fA-F-]{36})$", path)
    if method == "GET" and otp_status_match:
        from .otp_delivery_pipeline import handle_otp_delivery_status
        return handle_otp_delivery_status(
            otp_status_match.group("delivery_id"),
            service_auth_context,
            otp_delivery_store,
        )

    status_match = _M2M_MESSAGE_STATUS_ROUTE.fullmatch(path)
    if method == "GET" and status_match:
        return handle_message_status(status_match.group("idempotency_key"), coordinator, service_auth_context)
    elif method == "POST" and path == "/api/v2/m2m/agent/chat":
        return await handle_agent_chat(body or {}, service_auth_context)
    elif method == "GET" and path == "/api/v2/m2m/agent/health":
        return await handle_agent_health()

    return ApiResponse(404, {"ok": False, "error": "not_found"})


async def handle_prepare_recipient(body, service_auth_context, orchestrator, coordinator, request_id):
    """Explicit contact import primitive; never issues or sends an OTP itself."""
    from ..providers.contracts import ProviderContactUpsertRequest, SensitiveProviderValue
    from ..errors import BridgeError
    try:
        _check_scope(service_auth_context, "contacts.import")
        account_id = str(body.get("messenger_account_id") or "")
        _check_account_allowed(service_auth_context, account_id)
        provider = _validate_provider(service_auth_context, coordinator, account_id, body.get("provider"))
        if set(body) - {"messenger_account_id", "provider", "phone", "display_name", "idempotency_key", "confirm"}:
            raise ProviderExtensionError("Unsupported prepare fields.", code="m2m_fields_rejected")
        if body.get("confirm") is not True:
            raise ProviderExtensionError("Confirm contact import.", code="m2m_confirm_required")
        phone = str(body.get("phone") or "")
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
            raise ProviderExtensionError("Canonical phone required.", code="m2m_phone_invalid")
        if orchestrator is None:
            raise ProviderExtensionError("Provider unavailable.", code="provider_operation_not_implemented")
        receipt = await orchestrator.upsert_contact(actor=_get_actor(service_auth_context),
            messenger_account_id=account_id, correlation_id=request_id,
            deadline_unix_ms=int(time.time() * 1000) + 90_000,
            request=ProviderContactUpsertRequest(SensitiveProviderValue.from_text(phone),
                str(body.get("display_name") or ""), str(body.get("idempotency_key") or "")))
        reference = receipt.contact_reference
        if provider == "eitaa" and reference.startswith("contact:"):
            reference = "user:" + reference.removeprefix("contact:")
        return ApiResponse(200, {"ok": True, "status": "matched", "created": receipt.created,
            "messenger_account_id": account_id, "provider": provider,
            "peer_reference": {"kind": "dialog", "value": reference}})
    except ProviderExtensionError as exc:
        return _error_response(exc)
    except BridgeError as exc:
        return ApiResponse(400, {"ok": False, "status": "unresolved", "peer_reference": None,
            "error": {"error_code": exc.code, "message": "Contact preparation did not complete."}})

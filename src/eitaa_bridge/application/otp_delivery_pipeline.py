"""Stage-aware OTP delivery pipeline (P4).

Implements the composite, durable flow:
admit -> resolve -> import (if new) -> send -> receipt / status.

Follows the contract in docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import re
import time
from typing import Any, Mapping

from ..errors import BridgeError, ProviderExtensionError
from ..providers.contracts import (
    ProviderContactUpsertRequest,
    ProviderPeerReference,
    ProviderSendStatus,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)
from ..infrastructure.coordinator import reservations as reservations_module
from ..infrastructure.coordinator import otp_deliveries as otp_deliveries_module
from .api import ApiResponse
from .provider_orchestration import ProviderApplicationOrchestrator, ProviderOperationActor

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_PHONE_PATTERN = re.compile(r"\+[1-9][0-9]{7,14}")
_DIALOG_REFERENCE = re.compile(
    r"^(?:(?P<provider>bale):)?(?P<peer_type>user|chat|group|channel):(?P<peer_id>[0-9]{1,20})$"
)
_PEER_KIND_BY_TYPE = {
    "user": "private",
    "chat": "group",
    "group": "group",
    "channel": "channel",
}

_OTP_HTTP_STATUS = {
    "otp_delivery_conflict": 409,
    "otp_delivery_not_found": 404,
    "delivery_reservation_not_found": 404,
    "delivery_reservation_expired": 409,
    "delivery_reservation_inactive": 409,
    "delivery_reservation_already_consumed": 409,
    "delivery_recipient_mismatch": 400,
    "m2m_phone_invalid": 400,
    "m2m_idempotency_key_invalid": 400,
    "m2m_scope_insufficient": 403,
    "m2m_account_not_allowed": 403,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _current_time(otp_store: Any) -> datetime:
    if otp_store is not None and hasattr(otp_store, "_clock") and callable(otp_store._clock):
        try:
            val = otp_store._clock()
            if isinstance(val, datetime):
                return val
        except Exception:
            pass
    return _now()


def _safe_otp_delivery(record: otp_deliveries_module.OtpDeliveryRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "service_credential_id": record.service_credential_id,
        "reservation_id": record.reservation_id,
        "messenger_account_id": record.messenger_account_id,
        "provider": record.provider,
        "intent": record.intent,
        "challenge_ref": record.challenge_ref,
        "stage": record.stage,
        "state": record.state,
        "contact_status": record.contact_status,
        "send_status": record.send_status,
        "safe_reason_code": record.safe_reason_code,
        "provider_message_id": record.provider_message_id,
        "retryable": record.retryable,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "completed_at": record.completed_at,
        "expires_at": record.expires_at,
    }


def _error_response(exc: Any) -> ApiResponse:
    code = getattr(exc, "code", "otp_delivery_error")
    status = _OTP_HTTP_STATUS.get(code, 400)
    return ApiResponse(
        status,
        {
            "ok": False,
            "error": {"error_code": code, "message": str(exc)},
            "code": code,
            "reason": str(exc),
        },
    )


def _check_otp_delivery_scope(service_auth_context: Any) -> None:
    scopes = set(getattr(service_auth_context, "scopes", []) or [])
    if "otp.deliver" in scopes:
        return
    if "messages.send" in scopes and "contacts.import" in scopes:
        return
    raise ProviderExtensionError(
        "Scope 'otp.deliver' or both 'messages.send' and 'contacts.import' required.",
        code="m2m_scope_insufficient",
    )


def _check_otp_status_scope(service_auth_context: Any) -> None:
    scopes = set(getattr(service_auth_context, "scopes", []) or [])
    if any(s in scopes for s in ("otp.deliver", "messages.status", "messages.send")):
        return
    raise ProviderExtensionError(
        "Scope 'otp.deliver', 'messages.status' or 'messages.send' required.",
        code="m2m_scope_insufficient",
    )


def _credential_id(service_auth_context: Any) -> str:
    return str(
        getattr(service_auth_context, "service_id", None)
        or getattr(service_auth_context, "id", None)
        or getattr(service_auth_context, "credential_id", None)
        or ""
    )


def _get_actor(service_auth_context: Any) -> ProviderOperationActor:
    from .m2m_api import _get_actor as get_m2m_actor
    return get_m2m_actor(service_auth_context)


async def handle_otp_delivery_create(
    body: Mapping[str, Any],
    service_auth_context: Any,
    orchestrator: ProviderApplicationOrchestrator | None,
    coordinator: Any | None,
    reservation_store: Any | None,
    otp_store: otp_deliveries_module.ServiceOtpDeliveryStore | None,
    resolve_handler: Any | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Execute or replay an OTP delivery through the stage-aware pipeline (P4)."""
    try:
        _check_otp_delivery_scope(service_auth_context)
        if otp_store is None or reservation_store is None:
            return ApiResponse(
                503,
                {
                    "ok": False,
                    "error": {"error_code": "otp_delivery_unavailable", "message": "Service unavailable."},
                    "code": "otp_delivery_unavailable",
                },
            )

        cred_id = _credential_id(service_auth_context)

        # 1. Validate inputs
        reservation_id = str(body.get("reservation_id", "") or "").strip()
        if not reservation_id:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "reservation_id required", "code": "m2m_reservation_id_missing"})

        idempotency_key = str(body.get("idempotency_key", "") or "").strip()
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "idempotency_key must be 16-128 chars", "code": "m2m_idempotency_key_invalid"})

        recipient = body.get("recipient")
        if not isinstance(recipient, dict):
            # Accept flat phone if provided
            phone_val = str(body.get("phone", "") or "").strip()
            display_name = str(body.get("display_name", "") or "").strip()
        else:
            phone_val = str(recipient.get("value", "") or "").strip()
            display_name = str(recipient.get("display_name", "") or "").strip()

        if not _PHONE_PATTERN.fullmatch(phone_val):
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "Valid E.164 phone required", "code": "m2m_phone_invalid"})

        challenge_ref = str(body.get("challenge_ref", "") or "").strip()
        if not challenge_ref:
            challenge_ref = f"chal_{idempotency_key[:16]}"

        message_text = str(body.get("message_text", "") or body.get("otp_code", "") or "").strip()
        if not message_text:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "message_text or otp_code required", "code": "m2m_message_empty"})
        if len(message_text) > 500:
            return ApiResponse(400, {"ok": False, "error": "validation_error", "reason": "OTP message too long (max 500 chars)", "code": "m2m_text_too_long"})

        # 2. Check reservation
        reservation = reservation_store.status(
            reservation_id=reservation_id,
            service_credential_id=cred_id,
        )
        if reservation is None:
            return ApiResponse(404, {"ok": False, "error": {"error_code": "delivery_reservation_not_found", "message": "Reservation not found for this service."}, "code": "delivery_reservation_not_found"})

        # 3. Check recipient HMAC binding matches the reservation!
        expected_binding = reservation_store.bind_recipient(
            normalized_value=phone_val,
            intent=reservation.intent,
            service_id=cred_id,
        )
        if reservation.recipient_binding != expected_binding:
            return ApiResponse(400, {
                "ok": False,
                "error": {"error_code": "delivery_recipient_mismatch", "message": "Recipient phone does not match reservation binding."},
                "code": "delivery_recipient_mismatch",
            })

        # 4. Check account allowlist on the credential
        allowed_accounts = getattr(service_auth_context, "allowed_messenger_account_ids", []) or []
        if allowed_accounts and reservation.messenger_account_id not in allowed_accounts:
            return ApiResponse(403, {"ok": False, "error": {"error_code": "m2m_account_not_allowed", "message": "Account not allowed."}, "code": "m2m_account_not_allowed"})

        # 5. Calculate payload fingerprint
        message_digest = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
        request_fingerprint = otp_store.fingerprint_payload(
            idempotency_key=idempotency_key,
            reservation_id=reservation_id,
            recipient_binding=expected_binding,
            challenge_ref=challenge_ref,
            message_digest=message_digest,
        )

        delivery_id = str(reservations_module.uuid4())
        expires_at = reservation.expires_at

        # 6. Admit into persistent store (idempotency check)
        record, is_fresh = otp_store.admit(
            delivery_id=delivery_id,
            service_credential_id=cred_id,
            reservation_id=reservation_id,
            messenger_account_id=reservation.messenger_account_id,
            provider=reservation.provider,
            intent=reservation.intent,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            challenge_ref=challenge_ref,
            recipient_binding=expected_binding,
            expires_at=expires_at,
        )

        if not is_fresh:
            # Replay of existing delivery
            return ApiResponse(200, {
                "ok": True,
                "delivery": _safe_otp_delivery(record),
                "replayed": True,
            })

        # 7. Consume reservation atomically
        try:
            reservation_store.consume(
                reservation_id=reservation_id,
                service_credential_id=cred_id,
                operation_id=record.id,
            )
        except reservations_module.DeliveryReservationError as res_err:
            otp_store.update_stage(
                record.id,
                stage="completed",
                state="rejected",
                safe_reason_code=res_err.code,
                completed=True,
            )
            return ApiResponse(
                409,
                {
                    "ok": False,
                    "error": {"error_code": res_err.code, "message": str(res_err)},
                    "code": res_err.code,
                },
            )

        # 8. Check expiry before attempting pipeline
        now_dt = _current_time(otp_store)
        exp_dt = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        if now_dt >= exp_dt:
            rec = otp_store.update_stage(
                record.id,
                stage="completed",
                state="expired",
                send_status="expired",
                safe_reason_code="otp_expired_before_dispatch",
                completed=True,
            )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})

        # 9. Pipeline Step: Resolve Contact
        otp_store.update_stage(record.id, stage="resolving", state="running")

        peer_ref: ProviderPeerReference | None = None
        contact_status = None

        if resolve_handler is not None:
            try:
                resolved = resolve_handler([{"kind": "phone", "value": phone_val}], reservation.messenger_account_id)
                if resolved and resolved[0].get("status") == "matched" and resolved[0].get("peer_reference"):
                    raw_peer = resolved[0]["peer_reference"]
                    peer_val = str(raw_peer.get("value", "") or "")
                    dialog_match = _DIALOG_REFERENCE.fullmatch(peer_val)
                    if dialog_match:
                        peer_ref = ProviderPeerReference(
                            opaque_reference=peer_val,
                            kind=_PEER_KIND_BY_TYPE[dialog_match.group("peer_type")],
                        )
                        contact_status = "existing"
            except Exception:
                peer_ref = None

        # 10. Pipeline Step: Import Contact if not already existing
        if peer_ref is None:
            if orchestrator is None:
                rec = otp_store.update_stage(
                    record.id,
                    stage="completed",
                    state="rejected",
                    contact_status="failed",
                    safe_reason_code="orchestrator_unavailable",
                    completed=True,
                )
                return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})

            otp_store.update_stage(record.id, stage="importing_contact", state="running")
            try:
                upsert_receipt = await orchestrator.upsert_contact(
                    actor=_get_actor(service_auth_context),
                    messenger_account_id=reservation.messenger_account_id,
                    correlation_id=request_id,
                    deadline_unix_ms=int(time.time() * 1000) + 90_000,
                    request=ProviderContactUpsertRequest(
                        SensitiveProviderValue.from_text(phone_val),
                        display_name or f"User {phone_val[-4:]}",
                        f"otp_import_{record.id}",
                    ),
                )
                contact_status = "created"
                ref = upsert_receipt.contact_reference
                if reservation.provider == "eitaa" and ref.startswith("contact:"):
                    ref = "user:" + ref.removeprefix("contact:")
                elif reservation.provider == "bale" and not ref.startswith("bale:"):
                    if ref.startswith("contact:"):
                        ref = "bale:user:" + ref.removeprefix("contact:")
                    elif ref.startswith("user:"):
                        ref = "bale:" + ref
                peer_ref = ProviderPeerReference(opaque_reference=ref, kind="private")
            except Exception as exc:
                err_code = getattr(exc, "code", "contact_import_failed")
                rec = otp_store.update_stage(
                    record.id,
                    stage="completed",
                    state="rejected",
                    contact_status="failed",
                    safe_reason_code=str(err_code),
                    retryable=True,
                    completed=True,
                )
                return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})

        # 11. Check expiry before sending message
        now_dt = _current_time(otp_store)
        if now_dt >= exp_dt:
            rec = otp_store.update_stage(
                record.id,
                stage="completed",
                state="expired",
                contact_status=contact_status,
                send_status="expired",
                safe_reason_code="otp_expired_before_send",
                completed=True,
            )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})

        reservation_store.mark_send_started(
            reservation_id=reservation.id, operation_id=record.id
        )

        otp_store.update_stage(
            record.id,
            stage="sending_message",
            state="running",
            contact_status=contact_status,
        )

        # 13. Pipeline Step: Send message
        try:
            send_req = ProviderSendTextRequest(
                peer=peer_ref,
                text=message_text,
                idempotency_key=f"otp_send_{record.id}",
            )
            send_receipt = await orchestrator.send_text(
                actor=_get_actor(service_auth_context),
                messenger_account_id=reservation.messenger_account_id,
                request=send_req,
                correlation_id=request_id,
                deadline_unix_ms=int(time.time() * 1000) + 90_000,
                skip_admission=True,
            )
            if send_receipt.status == ProviderSendStatus.UNCERTAIN:
                rec = otp_store.update_stage(
                    record.id,
                    stage="uncertain",
                    state="uncertain",
                    contact_status=contact_status,
                    send_status="uncertain",
                    safe_reason_code=send_receipt.safe_reason_code or "provider_send_uncertain",
                    retryable=False,
                    completed=True,
                )
            else:
                rec = otp_store.update_stage(
                    record.id,
                    stage="completed",
                    state="accepted",
                    contact_status=contact_status,
                    send_status="accepted",
                    provider_message_id=(
                        getattr(send_receipt, "message_reference", None)
                        or getattr(send_receipt, "result_reference", None)
                    ),
                    retryable=False,
                    completed=True,
                )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})
        except ProviderExtensionError as p_err:
            # Definite rejection from provider: contact was created, but send was rejected
            rec = otp_store.update_stage(
                record.id,
                stage="completed",
                state="rejected",
                contact_status=contact_status,
                send_status="rejected",
                safe_reason_code=p_err.code,
                retryable=False,
                completed=True,
            )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})
        except asyncio.TimeoutError:
            # Send started but timed out: uncertain outcome! NEVER auto-retry or fallback!
            rec = otp_store.update_stage(
                record.id,
                stage="uncertain",
                state="uncertain",
                contact_status=contact_status,
                send_status="uncertain",
                safe_reason_code="send_timed_out",
                retryable=False,
                completed=True,
            )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})
        except Exception as exc:
            # Unknown error after send_started: mark uncertain
            rec = otp_store.update_stage(
                record.id,
                stage="uncertain",
                state="uncertain",
                contact_status=contact_status,
                send_status="uncertain",
                safe_reason_code="send_uncertain",
                retryable=False,
                completed=True,
            )
            return ApiResponse(201, {"ok": True, "delivery": _safe_otp_delivery(rec)})

    except otp_deliveries_module.OtpDeliveryError as exc:
        return _error_response(exc)
    except ProviderExtensionError as exc:
        return _error_response(exc)
    except BridgeError as exc:
        return _error_response(exc)


def handle_otp_delivery_status(
    delivery_id: str,
    service_auth_context: Any,
    otp_store: otp_deliveries_module.ServiceOtpDeliveryStore | None,
) -> ApiResponse:
    """Owner-scoped query for OTP delivery status (P4)."""
    try:
        _check_otp_status_scope(service_auth_context)
        if otp_store is None:
            return ApiResponse(
                503,
                {
                    "ok": False,
                    "error": {"error_code": "otp_delivery_unavailable", "message": "Service unavailable."},
                    "code": "otp_delivery_unavailable",
                },
            )
        cred_id = _credential_id(service_auth_context)
        record = otp_store.get_by_id(delivery_id, service_credential_id=cred_id)
        if record is None:
            return ApiResponse(
                404,
                {
                    "ok": False,
                    "error": {"error_code": "otp_delivery_not_found", "message": "Delivery not found for this service."},
                    "code": "otp_delivery_not_found",
                },
            )
        return ApiResponse(200, {"ok": True, "delivery": _safe_otp_delivery(record)})
    except ProviderExtensionError as exc:
        return _error_response(exc)
    except BridgeError as exc:
        return _error_response(exc)

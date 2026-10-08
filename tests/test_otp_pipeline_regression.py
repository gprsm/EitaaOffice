"""Regression tests for OTP delivery pipeline (defect 5).

Covers:
- Receipt with ProviderSendStatus.UNCERTAIN mapped to terminal uncertain (not accepted).
- Reservation capacity debit not double-charged in orchestrator.
- Step idempotency keys built from durable unique operation ID (not idempotency_key[:32]).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from eitaa_bridge.application.otp_delivery_pipeline import handle_otp_delivery_create
from eitaa_bridge.providers.contracts import ProviderSendReceipt, ProviderSendStatus


def test_uncertain_provider_receipt_is_mapped_to_terminal_uncertain_not_accepted():
    service_auth = MagicMock()
    service_auth.scopes = ["otp.deliver"]
    service_auth.service_id = "svc-1"
    service_auth.allowed_messenger_account_ids = ["acc-1"]

    reservation_store = MagicMock()
    mock_res = MagicMock()
    mock_res.id = "11111111-2222-3333-4444-555555555555"
    mock_res.messenger_account_id = "acc-1"
    mock_res.provider = "eitaa"
    mock_res.intent = "otp"
    mock_res.expires_at = "2026-09-29T13:00:00Z"
    mock_res.recipient_binding = "bind-1"
    reservation_store.status.return_value = mock_res
    reservation_store.bind_recipient.return_value = "bind-1"

    otp_store = MagicMock()
    mock_rec = MagicMock()
    mock_rec.id = "rec-op-id-12345678"
    mock_rec.expires_at = "2026-09-29T13:00:00Z"
    mock_rec.state = "uncertain"
    mock_rec.send_status = "uncertain"
    mock_rec.stage = "uncertain"
    mock_rec.retryable = False
    otp_store.admit.return_value = (mock_rec, True)
    # Freeze the pipeline clock through the same hook the real store exposes
    # (ServiceOtpDeliveryStore._clock), so the fixed reservation window is
    # still open and the flow reaches the provider's UNCERTAIN receipt.
    otp_store._clock = lambda: datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

    def fake_update_stage(rec_id, **kwargs):
        for k, v in kwargs.items():
            setattr(mock_rec, k, v)
        return mock_rec
    otp_store.update_stage.side_effect = fake_update_stage

    orchestrator = MagicMock()
    # Provider returns UNCERTAIN
    uncertain_receipt = ProviderSendReceipt(
        status=ProviderSendStatus.UNCERTAIN,
        message_reference=None,
        safe_reason_code="provider_timeout_uncertain",
    )
    orchestrator.send_text = AsyncMock(return_value=uncertain_receipt)

    resp = asyncio.run(handle_otp_delivery_create(
        body={
            "reservation_id": mock_res.id,
            "idempotency_key": "otp-key-unique-00000000001",
            "phone": "+989120000001",
            "display_name": "Test User",
            "message_text": "Code 123456",
        },
        service_auth_context=service_auth,
        orchestrator=orchestrator,
        coordinator=None,
        reservation_store=reservation_store,
        otp_store=otp_store,
        resolve_handler=lambda items, acc: [{"kind": "phone", "value": "+989120000001", "status": "matched", "peer_reference": {"value": "user:123"}}],
        request_id="req-1",
    ))

    # Assert that the outcome is terminal uncertain, NOT accepted!
    assert resp.status == 201
    delivery = resp.payload["delivery"]
    assert delivery["state"] == "uncertain", f"Expected uncertain state, got {delivery['state']}"
    assert delivery["send_status"] == "uncertain", f"Expected uncertain send_status, got {delivery['send_status']}"
    assert delivery["retryable"] is False

    # Check the call to orchestrator.send_text:
    call_kwargs = orchestrator.send_text.call_args.kwargs
    # Step key must use durable unique operation ID (rec-op-id-12345678), NOT truncated idempotency_key[:32]
    req = call_kwargs["request"]
    assert "rec-op-id-12345678" in req.idempotency_key
    assert not req.idempotency_key.startswith("otp_send_otp-key-unique-")

    # orchestrator.send_text must be told to skip capacity admission because reservation was already debited!
    assert call_kwargs.get("skip_admission") is True

    # Provider call count: exactly ONE real provider send attempt for this delivery.
    orchestrator.send_text.assert_awaited_once()


def test_challenge_expiry_before_send():
    service_auth = MagicMock()
    service_auth.scopes = ["otp.deliver"]
    service_auth.service_id = "svc-1"
    service_auth.allowed_messenger_account_ids = ["acc-1"]

    reservation_store = MagicMock()
    mock_res = MagicMock()
    mock_res.id = "11111111-2222-3333-4444-555555555555"
    mock_res.messenger_account_id = "acc-1"
    mock_res.provider = "eitaa"
    mock_res.intent = "otp"
    # Already expired in the past!
    mock_res.expires_at = "2020-01-01T00:00:00Z"
    mock_res.recipient_binding = "bind-1"
    reservation_store.status.return_value = mock_res
    reservation_store.bind_recipient.return_value = "bind-1"

    otp_store = MagicMock()
    mock_rec = MagicMock()
    mock_rec.id = "rec-expired-123"
    mock_rec.expires_at = "2020-01-01T00:00:00Z"
    mock_rec.state = "expired"
    mock_rec.send_status = "expired"
    mock_rec.stage = "completed"
    mock_rec.retryable = False
    otp_store.admit.return_value = (mock_rec, True)

    def fake_update_stage(rec_id, **kwargs):
        for k, v in kwargs.items():
            setattr(mock_rec, k, v)
        return mock_rec
    otp_store.update_stage.side_effect = fake_update_stage

    orchestrator = MagicMock()

    resp = asyncio.run(handle_otp_delivery_create(
        body={
            "reservation_id": mock_res.id,
            "idempotency_key": "otp-key-expired-00000001",
            "phone": "+989120000001",
            "message_text": "Code 123456",
        },
        service_auth_context=service_auth,
        orchestrator=orchestrator,
        coordinator=None,
        reservation_store=reservation_store,
        otp_store=otp_store,
    ))

    assert resp.status == 201
    delivery = resp.payload["delivery"]
    assert delivery["state"] == "expired"
    assert delivery["send_status"] == "expired"
    # Never called orchestrator because challenge had expired
    orchestrator.send_text.assert_not_called()


def test_permission_and_account_fencing():
    service_auth = MagicMock()
    service_auth.scopes = ["otp.deliver"]
    service_auth.service_id = "svc-1"
    # Allowed only acc-2, but reservation is on acc-1!
    service_auth.allowed_messenger_account_ids = ["acc-2"]

    reservation_store = MagicMock()
    mock_res = MagicMock()
    mock_res.id = "11111111-2222-3333-4444-555555555555"
    mock_res.messenger_account_id = "acc-1"
    mock_res.recipient_binding = "bind-1"
    reservation_store.status.return_value = mock_res
    reservation_store.bind_recipient.return_value = "bind-1"

    otp_store = MagicMock()

    resp = asyncio.run(handle_otp_delivery_create(
        body={
            "reservation_id": mock_res.id,
            "idempotency_key": "otp-key-fenced-00000001",
            "phone": "+989120000001",
            "message_text": "Code 123456",
        },
        service_auth_context=service_auth,
        orchestrator=None,
        coordinator=None,
        reservation_store=reservation_store,
        otp_store=otp_store,
    ))

    # Must be 403 Forbidden due to account fencing mismatch!
    assert resp.status == 403
    assert resp.payload["code"] == "m2m_account_not_allowed"

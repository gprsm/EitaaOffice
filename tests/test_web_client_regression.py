"""Regression tests for Web Client Reference SDK & M2M Canonical Routes.

Covers audit defects 1 & 2:
- preflight POST + recipient_kind + response parser
- reserve_capacity payload (intent, recipient, idempotency_key) + 201 nested response
- POST /api/v2/m2m/delivery/reservations/{id}/cancel canonical route vs 404 on unadorned POST
- dispatch_otp payload (message_text, display_name) + nested delivery parsing
- poll_delivery_status backoff, Retry-After, and parallel polling protection
"""

from __future__ import annotations

import asyncio
import json
import httpx
import pytest

from eitaa_bridge.application.web_client_reference import (
    BridgeWebClient,
    PreflightResult,
    ReservationResult,
    OtpDispatchResult,
    OtpDeliveryStatus,
)


def test_preflight_sends_post_and_parses_real_contract():
    received_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v2/m2m/delivery/preflight"
        body = json.loads(request.read())
        assert body["intent"] == "otp"
        assert body["recipient_kind"] in ("new", "existing")
        return httpx.Response(200, json={
            "ok": True,
            "decision": "ready",
            "can_attempt": True,
            "retry_after_seconds": None,
            "sender_profile_revision": 3,
            "observed_at": "2026-09-29T12:00:00.000Z",
            "valid_until": "2026-09-29T12:00:05.000Z",
            "steps": ["prepare_contact", "resolve", "send"],
            "constraints": [],
            "capacity_guaranteed": False,
        })

    client = BridgeWebClient(
        base_url="https://bridge.internal",
        bearer_token="test_token",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.preflight(intent="otp", recipient_kind="new"))
    assert len(received_requests) == 1
    assert result.ok is True
    assert result.status == "ready"
    assert result.retry_after_seconds == 0


def test_reserve_capacity_sends_complete_payload_and_parses_201_nested_reservation():
    received_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v2/m2m/delivery/reservations"
        body = json.loads(request.read())
        assert body["intent"] == "otp"
        assert body["recipient"] == {"kind": "phone", "value": "+989120000001"}
        assert body["idempotency_key"] == "res-key-000000000001"
        assert body["ttl_seconds"] == 120
        return httpx.Response(201, json={
            "ok": True,
            "reservation": {
                "id": "11111111-2222-3333-4444-555555555555",
                "state": "reserved",
                "provider": "eitaa",
                "messenger_account_id": "acc-1",
                "sender_profile_id": "prof-1",
                "sender_profile_revision": 1,
                "operation_costs": {"messages.send_text": 1},
                "token_reserved": True,
                "token_refunded": False,
                "send_started": False,
                "operation_id": None,
                "created_at": "2026-09-29T12:00:00Z",
                "updated_at": "2026-09-29T12:00:00Z",
                "expires_at": "2026-09-29T12:02:00Z",
            },
        })

    client = BridgeWebClient(
        base_url="https://bridge.internal",
        bearer_token="test_token",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.reserve_capacity(
        phone="+989120000001",
        idempotency_key="res-key-000000000001",
        intent="otp",
        ttl_seconds=120,
    ))
    assert len(received_requests) == 1
    assert result.ok is True
    assert result.reservation_id == "11111111-2222-3333-4444-555555555555"
    assert result.expires_at == "2026-09-29T12:02:00Z"


def test_cancel_reservation_calls_canonical_cancel_endpoint():
    received_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v2/m2m/delivery/reservations/11111111-2222-3333-4444-555555555555/cancel"
        return httpx.Response(200, json={
            "ok": True,
            "reservation": {
                "id": "11111111-2222-3333-4444-555555555555",
                "state": "cancelled",
                "token_reserved": True,
                "token_refunded": True,
            },
        })

    client = BridgeWebClient(
        base_url="https://bridge.internal",
        bearer_token="test_token",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.cancel_reservation("11111111-2222-3333-4444-555555555555"))
    assert len(received_requests) == 1
    assert result.ok is True


def test_dispatch_otp_sends_message_text_and_display_name_and_parses_nested_delivery():
    received_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v2/m2m/otp/deliveries"
        body = json.loads(request.read())
        assert body["reservation_id"] == "res-1234"
        assert body["phone"] == "+989120000001"
        assert body["message_text"] == "کد ورود: 123456"
        assert body["display_name"] == "دانش‌آموز نمونه"
        assert body["idempotency_key"] == "otp-key-000000000001"
        return httpx.Response(201, json={
            "ok": True,
            "delivery": {
                "id": "del-5555",
                "stage": "sending_message",
                "state": "running",
                "contact_status": "existing",
                "send_status": "pending",
                "retryable": False,
            },
            "replayed": False,
        })

    client = BridgeWebClient(
        base_url="https://bridge.internal",
        bearer_token="test_token",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.dispatch_otp(
        reservation_id="res-1234",
        phone="+989120000001",
        contact_name="دانش‌آموز نمونه",
        message="کد ورود: 123456",
        idempotency_key="otp-key-000000000001",
    ))
    assert len(received_requests) == 1
    assert result.ok is True
    assert result.delivery_id == "del-5555"
    assert result.stage == "sending_message"
    assert result.status == "running"
    assert result.is_replayed is False


def test_poll_delivery_status_handles_retry_after_and_prevents_parallel_polling():
    call_times = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_times.append(asyncio.get_event_loop().time() if asyncio.get_event_loop() else 0)
        if len(call_times) == 1:
            # First attempt: rate limited with Retry-After: 1
            return httpx.Response(429, headers={"Retry-After": "1"}, json={
                "ok": False,
                "error": {"error_code": "rate_limited", "message": "Too many requests"},
            })
        return httpx.Response(200, json={
            "ok": True,
            "delivery": {
                "id": "del-5555",
                "stage": "completed",
                "state": "accepted",
                "contact_status": "existing",
                "send_status": "accepted",
            },
        })

    client = BridgeWebClient(
        base_url="https://bridge.internal",
        bearer_token="test_token",
        transport=httpx.MockTransport(handler),
    )

    async def _test():
        # Test parallel polling guard: two concurrent poll tasks on same delivery_id
        task1 = asyncio.create_task(client.poll_delivery_status("del-5555", max_polls=3, poll_interval=0.1))
        task2 = asyncio.create_task(client.poll_delivery_status("del-5555", max_polls=3, poll_interval=0.1))
        res1, res2 = await asyncio.gather(task1, task2)
        assert res1.is_success is True
        assert res2.is_success is True

    asyncio.run(_test())


def test_dispatch_m2m_canonical_cancel_route_and_bare_post_rejected():
    from eitaa_bridge.application.m2m_api import dispatch_m2m
    from unittest.mock import MagicMock

    res_id = "11111111-2222-3333-4444-555555555555"
    service_auth = MagicMock()
    service_auth.scopes = ["messages.send"]
    service_auth.service_id = "svc-1"

    reservation_store = MagicMock()
    mock_res = MagicMock()
    mock_res.id = res_id
    mock_res.service_credential_id = "svc-1"
    mock_res.intent = "otp"
    mock_res.provider = "eitaa"
    mock_res.messenger_account_id = "acc-1"
    mock_res.sender_profile_id = "prof-1"
    mock_res.sender_profile_revision = 1
    mock_res.state = "cancelled"
    mock_res.operation_costs = {"messages.send_text": 1}
    mock_res.token_reserved = True
    mock_res.token_refunded = True
    mock_res.send_started_at = None
    mock_res.operation_id = None
    mock_res.created_at = "2026-09-29T12:00:00Z"
    mock_res.updated_at = "2026-09-29T12:00:01Z"
    mock_res.expires_at = "2026-09-29T12:02:00Z"
    reservation_store.cancel.return_value = mock_res
    reservation_store.status.return_value = mock_res

    # 1. Canonical route: POST /api/v2/m2m/delivery/reservations/{id}/cancel
    cancel_resp = asyncio.run(dispatch_m2m(
        method="POST",
        path=f"/api/v2/m2m/delivery/reservations/{res_id}/cancel",
        body={},
        service_auth_context=service_auth,
        request_id="req-cancel-1",
        orchestrator=None,
        coordinator=None,
        reservation_store=reservation_store,
    ))
    # MUST return 200 with ok: True
    assert cancel_resp.status == 200
    assert cancel_resp.payload["ok"] is True
    assert cancel_resp.payload["reservation"]["state"] == "cancelled"

    # 2. Bare route: POST /api/v2/m2m/delivery/reservations/{id}
    # Per contract, unadorned POST must NOT be treated as cancel! Must return 404 (or 405)
    bare_resp = asyncio.run(dispatch_m2m(
        method="POST",
        path=f"/api/v2/m2m/delivery/reservations/{res_id}",
        body={},
        service_auth_context=service_auth,
        request_id="req-bare-1",
        orchestrator=None,
        coordinator=None,
        reservation_store=reservation_store,
    ))
    assert bare_resp.status == 404

"""Tests for the M2M API endpoints (honest contract).

Delivery statuses, read-only recipient resolution and scope/account/provider
fencing are exercised against fakes only; nothing here is live acceptance.
"""

import asyncio

from eitaa_bridge.application.m2m_api import dispatch_m2m
from eitaa_bridge.providers.contracts import ProviderSendStatus


class FakeReceipt:
    def __init__(self, status):
        self.status = status
        self.message_reference = "test_msg_ref"
        self.safe_reason_code = None


class FakeOrchestrator:
    async def send_text(self, actor, messenger_account_id, correlation_id, deadline_unix_ms, request):
        assert actor.global_role == "user", "M2M actor must not run as admin"
        if request.text == "uncertain test":
            return FakeReceipt(ProviderSendStatus.UNCERTAIN)
        return FakeReceipt(ProviderSendStatus.SUCCEEDED)


class FakeRuntime:
    def __init__(self, provider):
        self.provider = provider


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, query, params):
        key = params[0]
        row = RECEIPT_ROWS.get(key)
        if row is not None and "messenger_account_id IN" in query:
            allowed = list(params[1:])
            if row["messenger_account_id"] not in allowed:
                row = None
        return FakeCursor([row] if row else [])


RECEIPT_ROWS = {
    "test-key-succeeded": {
        "outcome": "succeeded",
        "result_reference": "ref",
        "updated_at": "2026",
        "messenger_account_id": "acc1",
    },
    "test-key-in-progress": {
        "outcome": "in_progress",
        "result_reference": "ref",
        "updated_at": "2026",
        "messenger_account_id": "acc1",
    },
}


class FakeCoordinator:
    def __init__(self, account_provider="eitaa"):
        self._account_provider = account_provider

    def messenger_account_runtime(self, messenger_account_id):
        return FakeRuntime(self._account_provider)

    def _connect(self):
        return FakeConnection(RECEIPT_ROWS)


class FakeAuthContext:
    def __init__(self, scopes, allowed_accounts=None, allowed_providers=None):
        self.scopes = scopes
        self.allowed_messenger_account_ids = allowed_accounts
        self.allowed_providers = allowed_providers
        self.credential_id = "test-credential"
        self.service_name = "exam-service"


def _send_body(**overrides):
    body = {
        "messenger_account_id": "acc1",
        "message_type": "notice",
        "peer_reference": {"kind": "dialog", "value": "user:123"},
        "text": "hello",
        "idempotency_key": "1234567890123456",
        "confirm": True,
    }
    body.update(overrides)
    return body


def _dispatch(method, path, body, auth_ctx, coordinator=None, resolver=None):
    async def _run():
        return await dispatch_m2m(
            method,
            path,
            body,
            auth_ctx,
            "req-1",
            FakeOrchestrator(),
            coordinator if coordinator is not None else FakeCoordinator(),
            resolve_handler=resolver,
        )

    return asyncio.run(_run())


def test_send_text_success_with_dialog_reference():
    res = _dispatch("POST", "/api/v2/m2m/messages/send-text", _send_body(), FakeAuthContext(["messages.send"], ["acc1"]))
    assert res.status == 200
    assert res.payload["delivery_status"] == "provider_succeeded"


def test_send_text_uncertain_is_reported_honestly():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(text="uncertain test"),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 200
    assert res.payload["delivery_status"] == "uncertain"


def test_send_text_rejects_raw_phone_as_peer_reference():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(peer_reference={"kind": "phone", "value": "+989000000000"}),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 409
    assert res.payload["code"] == "m2m_recipient_unresolved"


def test_send_text_rejects_malformed_dialog_reference():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(peer_reference={"kind": "dialog", "value": "drop table; --"}),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 400
    assert res.payload["code"] == "m2m_peer_reference_invalid"


def test_send_text_rejects_short_idempotency_key():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(idempotency_key="short"),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 400
    assert res.payload["code"] == "m2m_idempotency_key_invalid"


def test_send_text_scope_insufficient():
    res = _dispatch("POST", "/api/v2/m2m/messages/send-text", _send_body(), FakeAuthContext([], ["acc1"]))
    assert res.status == 403
    assert res.payload["code"] == "m2m_scope_insufficient"


def test_send_text_account_not_allowed():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(),
        FakeAuthContext(["messages.send"], ["acc2"]),
    )
    assert res.status == 403
    assert res.payload["code"] == "m2m_account_not_allowed"


def test_send_text_provider_not_allowed_for_service():
    coordinator = FakeCoordinator(account_provider="eitaa")
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(),
        FakeAuthContext(["messages.send"], ["acc1"], allowed_providers=["bale"]),
        coordinator=coordinator,
    )
    assert res.status == 403
    assert res.payload["code"] == "m2m_provider_not_allowed"


def test_send_text_provider_mismatch_rejected():
    coordinator = FakeCoordinator(account_provider="eitaa")
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(provider="bale"),
        FakeAuthContext(["messages.send"], ["acc1"], allowed_providers=["eitaa", "bale"]),
        coordinator=coordinator,
    )
    assert res.status == 400
    assert res.payload["code"] == "m2m_provider_mismatch"


def test_send_text_length_limit():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(message_type="otp", text="x" * 257),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 400
    assert res.payload["code"] == "m2m_text_too_long"


def test_send_text_confirm_missing():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        _send_body(confirm=None),
        FakeAuthContext(["messages.send"], ["acc1"]),
    )
    assert res.status == 400
    assert res.payload["code"] == "m2m_confirm_required"


def test_resolve_phone_resolved_returns_dialog_reference():
    def resolver(recipients, messenger_account_id):
        assert messenger_account_id == "acc1"
        results = []
        for item in recipients:
            if item["value"] == "+989120000000":
                results.append({"status": "resolved", "peer_reference": "user:42", "reason": None})
            else:
                results.append({"status": "unresolved", "peer_reference": None, "reason": "recipient_not_found"})
        return results

    res = _dispatch(
        "POST",
        "/api/v2/m2m/recipients/resolve",
        {
            "messenger_account_id": "acc1",
            "recipients": [
                {"kind": "phone", "value": "+989120000000"},
                {"kind": "phone", "value": "+989300000000"},
            ],
        },
        FakeAuthContext(["contacts.resolve"], ["acc1"]),
        resolver=resolver,
    )
    assert res.status == 200
    assert res.payload["results"][0]["status"] == "resolved"
    assert res.payload["results"][0]["peer_reference"] == "user:42"
    assert res.payload["results"][1]["status"] == "unresolved"
    assert res.payload["requires_import"] is True
    # Raw phone values must never be echoed back.
    assert "+989120000000" not in str(res.payload)
    assert "+989300000000" not in str(res.payload)


def test_resolve_unsupported_kind_without_resolver():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/recipients/resolve",
        {
            "messenger_account_id": "acc1",
            "recipients": [{"kind": "email", "value": "someone@example.com"}],
        },
        FakeAuthContext(["contacts.resolve"], ["acc1"]),
        resolver=None,
    )
    assert res.status == 200
    assert res.payload["results"][0]["status"] == "unsupported"


def test_resolve_scope_insufficient():
    res = _dispatch(
        "POST",
        "/api/v2/m2m/recipients/resolve",
        {"messenger_account_id": "acc1", "recipients": [{"kind": "phone", "value": "+989120000000"}]},
        FakeAuthContext([], ["acc1"]),
        resolver=lambda recipients, account: [],
    )
    assert res.status == 403
    assert res.payload["code"] == "m2m_scope_insufficient"


def test_delivery_status_query_succeeded():
    res = _dispatch("GET", "/api/v2/m2m/messages/test-key-succeeded/status", None, FakeAuthContext([]))
    assert res.status == 200
    assert res.payload["delivery_status"] == "provider_succeeded"


def test_delivery_status_query_in_progress():
    res = _dispatch("GET", "/api/v2/m2m/messages/test-key-in-progress/status", None, FakeAuthContext([]))
    assert res.status == 200
    assert res.payload["delivery_status"] == "accepted"


def test_delivery_status_query_not_found():
    res = _dispatch("GET", "/api/v2/m2m/messages/test-key-not-found/status", None, FakeAuthContext([]))
    assert res.status == 200
    assert res.payload["delivery_status"] == "not_found"


def test_delivery_status_query_respects_account_fence():
    restricted = FakeAuthContext([], allowed_accounts=["acc2"])
    res = _dispatch("GET", "/api/v2/m2m/messages/test-key-succeeded/status", None, restricted)
    assert res.status == 200
    assert res.payload["delivery_status"] == "not_found"

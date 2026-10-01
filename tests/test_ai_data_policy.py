"""Tests for Server-Side AI Data Policy & Egress Gate (Phase 6).

Covers:
- P6-A01: Multi-level policy enforcement (disabled, current_message, limited_history, approved_context).
- P6-A02: Zero raw phone numbers, OTP codes, bearer tokens, or user IDs entering context.
- P6-A03: Cross-service isolation, fail-closed handling, F-090/F-091 claim resolution.
- P6-A04: Request body capture and semantic assertion without PII leakage.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from eitaa_bridge.application import agent_gateway
from eitaa_bridge.application.agent_gateway import (
    AgentChatContext,
    AgentChatResponse,
    LiveAiAgentAdapter,
)
from eitaa_bridge.application.m2m_api import dispatch_m2m
from eitaa_bridge.errors import BridgeError
from eitaa_bridge.infrastructure.coordinator.ai_connection import AiConnectionStore
from eitaa_bridge.infrastructure.coordinator.ai_data_policy import (
    AiDataPolicyError,
    AiDataPolicyStore,
    build_outbound_egress,
    pseudonymize_user_id,
    sanitize_text,
)


class MockDatabase:
    def __init__(self):
        self._conn = sqlite3.connect(":memory:")

    def _connect(self):
        return self._conn


class MockProtector:
    def hmac_hex(self, data: bytes) -> str:
        import hashlib, hmac
        return hmac.new(b"test-protector-key", data, hashlib.sha256).hexdigest()


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture(autouse=True)
def cleanup_gateway_stores():
    orig_conn = agent_gateway.ai_connection_store
    orig_pol = agent_gateway.ai_data_policy_store
    yield
    agent_gateway.ai_connection_store = orig_conn
    agent_gateway.ai_data_policy_store = orig_pol


@pytest.fixture
def policy_store(mock_db):
    return AiDataPolicyStore(mock_db)


def test_ai_data_policy_store_default_fail_closed(policy_store):
    policy = policy_store.get_policy("unknown_service")
    assert policy.policy_level == "disabled"
    assert policy.max_history_turns == 0
    assert policy.allowed_context_types == ()
    assert policy.revision == 0


def test_ai_data_policy_store_crud_and_validation(policy_store):
    # Set valid policy
    pol = policy_store.set_policy(
        service_id="service_alpha",
        policy_level="limited_history",
        max_history_turns=10,
        allowed_context_types=["faq_article", "user_tier"],
    )
    assert pol.policy_level == "limited_history"
    assert pol.max_history_turns == 10
    assert "faq_article" in pol.allowed_context_types
    assert pol.revision == 1

    # Fetch policy
    fetched = policy_store.get_policy("service_alpha")
    assert fetched.policy_level == "limited_history"
    assert fetched.revision == 1

    # Stale revision rejection
    with pytest.raises(AiDataPolicyError) as exc:
        policy_store.set_policy(
            service_id="service_alpha",
            policy_level="current_message",
            expected_revision=0,
        )
    assert exc.value.code == "stale_revision"

    # Disallowed levels like full_database or unrestricted
    with pytest.raises(AiDataPolicyError) as exc:
        policy_store.set_policy(
            service_id="service_alpha",
            policy_level="full_database",
        )
    assert exc.value.code == "ai_policy_level_invalid"

    with pytest.raises(AiDataPolicyError) as exc:
        policy_store.set_policy(
            service_id="service_alpha",
            policy_level="unrestricted",
        )
    assert exc.value.code == "ai_policy_level_invalid"


def test_sanitize_text_redacts_sensitive_data():
    raw = (
        "سلام، شماره من 09123456789 و کد تأیید من: 849201 است. "
        "توکن من Bearer my-secret-token-123456 است. همچنین شماره +989351234567."
    )
    scrubbed = sanitize_text(raw)
    assert "09123456789" not in scrubbed
    assert "+989351234567" not in scrubbed
    assert "849201" not in scrubbed
    assert "my-secret-token-123456" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "[REDACTED_OTP]" in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_pseudonymize_user_id_is_stable_and_isolated():
    p1 = pseudonymize_user_id("service_a", "user_1001")
    p2 = pseudonymize_user_id("service_a", "user_1001")
    p3 = pseudonymize_user_id("service_b", "user_1001")

    assert p1 == p2
    assert p1 != p3
    assert "user_1001" not in p1
    assert p1.startswith("usr_")


def test_build_outbound_egress_levels(policy_store):
    policy_store.set_policy(
        service_id="svc_test",
        policy_level="current_message",
        max_history_turns=5,
    )
    pol_cur = policy_store.get_policy("svc_test")

    history = [
        {"role": "user", "content": "turn 1: 09121111111"},
        {"role": "agent", "content": "reply 1"},
    ]

    # current_message: history is completely cleared
    egress = build_outbound_egress(
        policy=pol_cur,
        service_name="svc_test",
        web_user_id="user_real_99",
        raw_message="Hi my phone is 09122222222",
        raw_history=history,
    )
    assert egress.history == []
    assert "09122222222" not in egress.message
    assert "[REDACTED_PHONE]" in egress.message
    assert egress.pseudonym_user_id != "user_real_99"

    # limited_history: bounds and scrubs history
    pol_hist = policy_store.set_policy(
        service_id="svc_test",
        policy_level="limited_history",
        max_history_turns=1,
    )
    egress_hist = build_outbound_egress(
        policy=pol_hist,
        service_name="svc_test",
        web_user_id="user_real_99",
        raw_message="Next message",
        raw_history=history,
    )
    assert len(egress_hist.history) == 1
    assert egress_hist.history[0]["content"] == "reply 1"

    # disabled: fails closed
    pol_dis = policy_store.set_policy(
        service_id="svc_test",
        policy_level="disabled",
    )
    with pytest.raises(BridgeError) as exc:
        build_outbound_egress(
            policy=pol_dis,
            service_name="svc_test",
            web_user_id="user_real_99",
            raw_message="Hi",
            raw_history=[],
        )
    assert exc.value.code == "ai_policy_disabled"


def test_m2m_chat_data_policy_disabled_returns_403(policy_store):
    policy_store.set_policy(service_id="svc_blocked", policy_level="disabled")
    agent_gateway.ai_data_policy_store = policy_store

    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "svc_blocked"

        body = {
            "web_user_id": "u1",
            "session_id": "s1",
            "message": "hello",
            "message_id": "msg-pol-0001",
        }
        resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body, DummyAuth(), "req1")
        assert resp.status == 403
        assert resp.payload["error"] == "ai_policy_disabled"

    asyncio.run(_run())


def test_m2m_chat_egress_scrubbing_and_pseudonymization_with_live_adapter(policy_store, mock_db):
    conn_store = AiConnectionStore(mock_db, protector=MockProtector())
    conn_store.update_settings(
        enabled=True,
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        secret_key="sk-test-live",
    )
    policy_store.set_policy(
        service_id="svc_allowed",
        policy_level="current_message",
    )
    agent_gateway.ai_connection_store = conn_store
    agent_gateway.ai_data_policy_store = policy_store

    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Safe answer"}}]})

    transport = httpx.MockTransport(handler)
    live_adapter = LiveAiAgentAdapter(conn_store, transport=transport)

    # Patch get_current_adapter to use our mocked live adapter
    with patch.object(agent_gateway, "get_current_adapter", return_value=live_adapter):
        async def _run():
            class DummyAuth:
                scopes = ["agent.chat"]
                service_name = "svc_allowed"

            body = {
                "web_user_id": "real_raw_user_12345",
                "session_id": "session_99",
                "message": "شماره من 09121234567 است و رمز من 654321",
                "message_id": "msg-safe-0001",
            }
            resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body, DummyAuth(), "req1")
            assert resp.status == 200
            assert resp.payload["response"] == "Safe answer"
            assert resp.payload["is_test_response"] is False

        asyncio.run(_run())

    assert len(captured_requests) == 1
    outbound = json.loads(captured_requests[0].read())
    # Verify raw user ID is NOT present, pseudonym is used instead
    assert outbound["user"] != "real_raw_user_12345"
    assert outbound["user"].startswith("usr_")
    # Verify raw phone and OTP are NOT in outbound messages
    msg_content = outbound["messages"][-1]["content"]
    assert "09121234567" not in msg_content
    assert "654321" not in msg_content
    assert "[REDACTED_PHONE]" in msg_content
    assert "[REDACTED_OTP]" in msg_content


def test_cross_service_data_policy_isolation(policy_store):
    policy_store.set_policy(service_id="service_a", policy_level="disabled")
    policy_store.set_policy(service_id="service_b", policy_level="current_message")
    agent_gateway.ai_data_policy_store = policy_store

    async def _run():
        class AuthA:
            scopes = ["agent.chat"]
            service_name = "service_a"

        class AuthB:
            scopes = ["agent.chat"]
            service_name = "service_b"

        body_a = {
            "web_user_id": "u1",
            "session_id": "s1",
            "message": "hello from a",
            "message_id": "msg-iso-0001",
        }
        body_b = {
            "web_user_id": "u1",
            "session_id": "s1",
            "message": "hello from b",
            "message_id": "msg-iso-0002",
        }

        # Service A should be blocked
        resp_a = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body_a, AuthA(), "req_a")
        assert resp_a.status == 403
        assert resp_a.payload["error"] == "ai_policy_disabled"

        # Service B should be allowed
        resp_b = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body_b, AuthB(), "req_b")
        assert resp_b.status == 200
        assert resp_b.payload["ok"] is True

    asyncio.run(_run())

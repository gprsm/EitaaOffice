import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from eitaa_bridge.application.agent_gateway import (
    AgentChatContext,
    TestAgentAdapter,
    ConfigurableAgentAdapter,
    AgentChatSessionStore,
)
from eitaa_bridge.application.m2m_api import dispatch_m2m
from eitaa_bridge.errors import BridgeError

@pytest.fixture
def context():
    return AgentChatContext(
        web_user_id="user123",
        session_id="session123",
        service_name="service_a"
    )

@pytest.fixture
def store():
    return AgentChatSessionStore()

def test_test_agent_adapter(context):
    async def _run():
        adapter = TestAgentAdapter()
        resp = await adapter.chat("hello", "session123", context, history=[])
        assert resp.is_test_response is True
        assert "آزمایشی" in resp.response
        assert await adapter.health() is True
    asyncio.run(_run())

def test_configurable_agent_adapter_success(context):
    async def _run():
        adapter = ConfigurableAgentAdapter("http://fake.agent/api", "fake-key", "gpt-test")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "agent reply"}}]
            }
            mock_post.return_value = mock_resp
            
            resp = await adapter.chat("hello", "session123", context, history=[])
            assert resp.is_test_response is False
            assert resp.response == "agent reply"
    asyncio.run(_run())

def test_configurable_agent_adapter_health():
    async def _run():
        adapter = ConfigurableAgentAdapter("http://fake.agent/api", "fake-key", "gpt-test")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            
            assert await adapter.health() is True
    asyncio.run(_run())

def test_session_store_creation_and_ttl(context, store):
    store.add_message(context, "user", "hi")
    msgs = store.get_messages(context)
    assert len(msgs) == 1
    assert msgs[0].content == "hi"
    
    # TTL expiry
    context.session_ttl_seconds = -1
    store.add_message(context, "user", "expired")
    msgs = store.get_messages(context)
    assert len(msgs) == 1
    assert msgs[0].content == "expired"

def test_session_store_max_sessions(context, store):
    context.session_ttl_seconds = 3600
    for i in range(100):
        ctx = AgentChatContext(f"user{i}", f"sess{i}", "service_a")
        store.add_message(ctx, "user", "hi")
        
    ctx = AgentChatContext("user101", "sess101", "service_a")
    with pytest.raises(BridgeError) as exc:
        store.add_message(ctx, "user", "hi")
    assert exc.value.code == "agent_too_many_sessions"

def test_m2m_endpoint_chat():
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "test_service"

        auth = DummyAuth()
        body = {
            "web_user_id": "u1",
            "session_id": "s1",
            "message": "hello",
            "message_id": "msg-00000001",
        }
        resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body, auth, "req1")
        assert resp.status == 200
        assert resp.payload["ok"] is True
        assert resp.payload["is_test_response"] is True
        assert resp.payload["replayed"] is False
    asyncio.run(_run())

def test_m2m_endpoint_chat_unauthorized():
    async def _run():
        class DummyAuth:
            scopes = []
            service_name = "unauthorized_service"

        auth = DummyAuth()
        body = {
            "web_user_id": "u1",
            "session_id": "s1",
            "message": "hello"
        }
        resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body, auth, "req1")
        assert resp.status == 403
        assert resp.payload["error"] == "agent_chat_forbidden"
    asyncio.run(_run())

def test_m2m_endpoint_health():
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "test_service"

        resp = await dispatch_m2m("GET", "/api/v2/m2m/agent/health", None, DummyAuth(), "req1")
        assert resp.status == 200
        assert resp.payload["ok"] is True
        assert resp.payload["adapter_type"] == "test"
    asyncio.run(_run())


def _chat_body(**overrides):
    body = {
        "web_user_id": "u1",
        "session_id": "s1",
        "message": "hello",
        "message_id": "msg-0000-0001",
    }
    body.update(overrides)
    return body


def test_m2m_endpoint_chat_requires_message_id():
    """F-085 gap #4 reproducer: chat requests must carry a message id."""
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "test_service"

        resp = await dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat",
            {k: v for k, v in _chat_body().items() if k != "message_id"},
            DummyAuth(), "req1",
        )
        assert resp.status == 400
        assert resp.payload["error"] == "agent_message_id_required"

    asyncio.run(_run())


def test_m2m_endpoint_chat_replays_same_message_id():
    """A retried chat request with the same message id returns the same reply
    without invoking the adapter again."""
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "replay_service"

        calls = []

        class CountingAdapter:
            async def chat(self, message, session_id, context, *, history):
                calls.append(message)
                from eitaa_bridge.application.agent_gateway import AgentChatResponse
                return AgentChatResponse(
                    response=f"reply-{len(calls)}", session_id=session_id,
                    is_test_response=False,
                )

            async def health(self):
                return True

        from eitaa_bridge.application import agent_gateway
        previous = agent_gateway.default_agent_adapter
        agent_gateway.default_agent_adapter = CountingAdapter()
        try:
            first = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "req1")
            retry = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "req2")
            fresh = await dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-0000-0002"), DummyAuth(), "req3",
            )
        finally:
            agent_gateway.default_agent_adapter = previous

        assert first.payload["response"] == "reply-1"
        assert retry.payload["response"] == "reply-1"
        assert retry.payload["replayed"] is True
        assert fresh.payload["response"] == "reply-2"
        assert fresh.payload.get("replayed") is False
        assert len(calls) == 2

    asyncio.run(_run())


def test_m2m_endpoint_chat_passes_bounded_history_to_adapter():
    """Conversation continuation must actually use the stored history."""
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "history_service"

        seen_histories = []

        class RecordingAdapter:
            async def chat(self, message, session_id, context, *, history):
                seen_histories.append(list(history))
                from eitaa_bridge.application.agent_gateway import AgentChatResponse
                return AgentChatResponse(
                    response="ok", session_id=session_id, is_test_response=False,
                )

            async def health(self):
                return True

        from eitaa_bridge.application import agent_gateway
        previous = agent_gateway.default_agent_adapter
        agent_gateway.default_agent_adapter = RecordingAdapter()
        try:
            await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-h-00001"), DummyAuth(), "r1")
            await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(message="second", message_id="msg-h-00002"), DummyAuth(), "r2")
        finally:
            agent_gateway.default_agent_adapter = previous

        assert seen_histories[0] == []
        assert {"role": "user", "content": "hello"} in seen_histories[1]
        assert seen_histories[1][-1] == {"role": "agent", "content": "ok"}
        assert any(item.get("role") == "agent" for item in seen_histories[1])

    asyncio.run(_run())


def test_m2m_endpoint_chat_session_isolated_per_service():
    """Same web user/session id under different services never share history."""
    async def _run():
        from eitaa_bridge.application.agent_gateway import AgentChatContext, session_store

        class DummyAuth:
            scopes = ["agent.chat"]

        auth_a = type("A", (), {**{"scopes": ["agent.chat"]}, "service_name": "svc-a"})()
        auth_b = type("B", (), {**{"scopes": ["agent.chat"]}, "service_name": "svc-b"})()

        await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-i-0001"), auth_a, "r1")
        await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-i-0001"), auth_b, "r2")

        ctx_a = AgentChatContext("u1", "s1", "svc-a")
        ctx_b = AgentChatContext("u1", "s1", "svc-b")
        history_a = [{"role": m.role, "content": m.content} for m in session_store.get_messages(ctx_a)]
        history_b = [{"role": m.role, "content": m.content} for m in session_store.get_messages(ctx_b)]
        assert len(history_a) == 2
        assert len(history_b) == 2

        # Cross-service message id replay must not hit the other service's cache.
        resp_b = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-i-0001"), auth_b, "r3")
        assert resp_b.payload.get("replayed") is True
        assert resp_b.payload["session_id"] == "s1"

    asyncio.run(_run())


def test_m2m_endpoint_agent_outage_maps_to_502():
    """An unreachable agent must surface as a gateway failure, not a 4xx."""
    async def _run():
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "outage_service"

        import httpx

        class DownAdapter:
            async def chat(self, message, session_id, context, *, history):
                raise httpx.ConnectError("connection refused")

            async def health(self):
                return False

        from eitaa_bridge.application import agent_gateway
        previous = agent_gateway.default_agent_adapter
        agent_gateway.default_agent_adapter = DownAdapter()
        try:
            resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1")
        finally:
            agent_gateway.default_agent_adapter = previous

        assert resp.status == 502
        assert resp.payload["error"] == "agent_communication_failed"

    asyncio.run(_run())


def test_agent_adapter_configuration_is_explicit_and_fail_closed():
    """F-085 gap #4: the real adapter is only wired from an explicit, valid
    configuration; nothing is guessed and secrets stay in the environment."""
    import pytest
    from eitaa_bridge.application import agent_gateway

    with pytest.raises(BridgeError) as missing:
        agent_gateway.configure_default_adapter({"enabled": True})
    assert missing.value.code == "agent_gateway_config_invalid"

    with pytest.raises(BridgeError) as bad_url:
        agent_gateway.configure_default_adapter(
            {"enabled": True, "url": "ftp://x", "model": "m", "api_key_env": "K"}
        )
    assert bad_url.value.code == "agent_gateway_config_invalid"

    with pytest.raises(BridgeError) as bad_key:
        agent_gateway.configure_default_adapter(
            {"enabled": True, "url": "https://agent.example", "model": "m",
             "api_key_env": "AGENT_TEST_KEY_MISSING"}
        )
    assert bad_key.value.code == "agent_gateway_config_invalid"

    import os
    os.environ["AGENT_TEST_KEY_PRESENT"] = "synthetic"
    try:
        kind = agent_gateway.configure_default_adapter(
            {"enabled": True, "url": "https://agent.example", "model": "m",
             "api_key_env": "AGENT_TEST_KEY_PRESENT"}
        )
        assert kind == "configurable"
    finally:
        del os.environ["AGENT_TEST_KEY_PRESENT"]
        agent_gateway.configure_default_adapter(None)

    kind = agent_gateway.configure_default_adapter(None)
    assert kind == "test"


def test_agent_gateway_has_no_messaging_or_data_powers():
    """The agent surface must stay chat-only: no provider orchestration, no
    coordinator access, no send capabilities."""
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "eitaa_bridge" / "application" / "agent_gateway.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "eitaa_bridge.application.provider_orchestration",
        "eitaa_bridge.infrastructure.coordinator",
        "eitaa_bridge.infrastructure.contact_store",
        "eitaa_bridge.application.m2m_api",
    }
    assert imported.isdisjoint(forbidden)
    assert "send_text" not in source
    assert "orchestrator" not in source

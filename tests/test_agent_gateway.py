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
        resp = await adapter.chat("hello", "session123", context)
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
            
            resp = await adapter.chat("hello", "session123", context)
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
            "message": "hello"
        }
        resp = await dispatch_m2m("POST", "/api/v2/m2m/agent/chat", body, auth, "req1")
        assert resp.status == 200
        assert resp.payload["ok"] is True
        assert resp.payload["is_test_response"] is True
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

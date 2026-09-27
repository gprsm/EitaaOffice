import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from eitaa_bridge.application.agent_gateway import (
    AgentChatContext,
    AgentChatResponse,
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

def test_session_store_creation_and_ttl(context):
    """F-090 semantics: expiry is enforced on reads with an exact TTL
    boundary (a session is still readable exactly at the TTL)."""
    class FakeClock:
        def __init__(self):
            self.now = 500_000.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    store = AgentChatSessionStore(clock=clock)
    store.add_message(context, "user", "hi")
    msgs = store.get_messages(context)
    assert len(msgs) == 1
    assert msgs[0].content == "hi"

    clock.now += context.session_ttl_seconds  # exactly at the TTL boundary
    assert len(store.get_messages(context)) == 1

    clock.now += 1  # beyond the TTL: the session is gone on the next read
    assert store.get_messages(context) == []
    assert store.service_session_counts[context.service_name] == 0

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


# ---------------------------------------------------------------------------
# F-090 reproduction tests (RED before the fix)
# ---------------------------------------------------------------------------

def _ensure_default_adapter():
    """Harness-only setup: the default adapter binding is created by
    configure_default_adapter; direct-dispatch tests must not confuse a
    missing harness setup with a product failure."""
    from eitaa_bridge.application import agent_gateway
    if not hasattr(agent_gateway, "default_agent_adapter"):
        agent_gateway.configure_default_adapter(None)

def _fresh_store(clock=None):
    from eitaa_bridge.application.agent_gateway import AgentChatSessionStore
    return AgentChatSessionStore(clock=clock) if clock else AgentChatSessionStore()


def _install_store(store):
    from eitaa_bridge.application import agent_gateway
    previous = agent_gateway.session_store
    agent_gateway.session_store = store
    # m2m_api must see the swap too; the handler reads through the module.
    return previous


class _BarrierAdapter:
    """Counts real adapter invocations; blocks until released."""

    is_test_adapter = False

    def __init__(self, reply="agent-reply"):
        self.calls = 0
        self._reply = reply
        self._gate = None

    def arm_gate(self, count):
        self._gate = threading.Barrier(count, timeout=5)

    async def chat(self, message, session_id, context, *, history):
        self.calls += 1
        if self._gate is not None:
            try:
                self._gate.wait()
            except threading.BrokenBarrierError:
                pass
        await asyncio.sleep(0.05)
        return AgentChatResponse(response=self._reply, session_id=session_id, is_test_response=False)

    async def health(self):
        return True


def test_f090_concurrent_same_message_id_runs_adapter_once_in_one_loop():
    """Two coroutines racing on one message id must not both reach the agent."""
    _ensure_default_adapter()
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    adapter = _BarrierAdapter()
    agent_gateway.default_agent_adapter = adapter
    agent_gateway.session_store = _fresh_store()
    try:
        async def _run():
            class DummyAuth:
                scopes = ["agent.chat"]
                service_name = "f090-race-loop"

            results = await asyncio.gather(
                dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1"),
                dispatch_m2m("POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2"),
            )
            return results

        results = asyncio.run(_run())
        assert adapter.calls == 1, f"adapter invoked {adapter.calls} times"
        payloads = [item.payload for item in results]
        assert payloads[0]["response"] == payloads[1]["response"] == "agent-reply"
        assert sorted(item["replayed"] for item in payloads) == [False, True]
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


def test_f090_concurrent_same_message_id_runs_adapter_once_across_threads():
    """The HTTP path runs one asyncio.run per request in its own thread; the
    atomic first-run/replay decision must hold across threads too."""
    _ensure_default_adapter()
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    adapter = _BarrierAdapter()
    adapter.arm_gate(2)  # if both run, the barrier proves the overlap
    agent_gateway.default_agent_adapter = adapter
    agent_gateway.session_store = _fresh_store()
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-race-threads"

        def _request():
            return asyncio.run(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r",
            ))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_request), pool.submit(_request)]
            results = [future.result(timeout=15) for future in futures]

        assert adapter.calls == 1, f"adapter invoked {adapter.calls} times"
        payloads = [item.payload for item in results]
        assert payloads[0]["response"] == payloads[1]["response"] == "agent-reply"
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


def test_f090_expired_session_is_invisible_on_read_and_never_reaches_agent():
    """TTL must be enforced on every read: history, reply cache and the
    conversation sent to the adapter all forget expired content."""
    _ensure_default_adapter()
    import time as time_module

    from eitaa_bridge.application import agent_gateway

    class FakeClock:
        def __init__(self):
            self.now = 1_000_000.0

        def __call__(self):
            return self.now

    clock = FakeClock()
    store = _fresh_store(clock=clock)

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    seen_histories = []

    class RecordingAdapter:
        is_test_adapter = False

        async def chat(self, message, session_id, context, *, history):
            seen_histories.append(list(history))
            return AgentChatResponse(response="fresh", session_id=session_id, is_test_response=False)

        async def health(self):
            return True

    agent_gateway.default_agent_adapter = RecordingAdapter()
    agent_gateway.session_store = store
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-ttl"

        ctx = AgentChatContext("u1", "s1", "f090-ttl")
        resp1 = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="ttl-00000001"), DummyAuth(), "r1",
        ))
        assert resp1.status == 200
        assert store.get_reply(ctx, "ttl-00000001") is not None
        assert len(store.get_history(ctx)) == 2

        clock.now += 3601  # beyond the one-hour TTL

        assert store.get_history(ctx) == []
        assert store.get_reply(ctx, "ttl-00000001") is None

        resp2 = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat",
            _chat_body(message="second", message_id="ttl-00000002"), DummyAuth(), "r2",
        ))
        assert resp2.status == 200
        assert seen_histories[-1] == [], "expired history reached the adapter"

        # The expired reply must not replay after expiry either.
        resp3 = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="ttl-00000001"), DummyAuth(), "r3",
        ))
        assert resp3.payload.get("replayed") is False

        # Session accounting dropped the expired session.
        assert agent_gateway.session_store.service_session_counts.get("f090-ttl", 0) == 1
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


def test_f090_replay_preserves_stored_is_test_response_across_adapter_swap():
    """A cached reply keeps its own test flag; the current adapter never
    re-labels it."""
    _ensure_default_adapter()
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    agent_gateway.default_agent_adapter = TestAgentAdapter()
    agent_gateway.session_store = _fresh_store()
    try:
        class FakeRealAdapter:
            is_test_adapter = False

            async def chat(self, message, session_id, context, *, history):
                return AgentChatResponse(response="real-answer", session_id=session_id, is_test_response=False)

            async def health(self):
                return True

        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-flag"

        first = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
        ))
        assert first.payload["is_test_response"] is True

        agent_gateway.default_agent_adapter = FakeRealAdapter()
        replay = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
        ))
        assert replay.payload["replayed"] is True
        assert replay.payload["response"] == first.payload["response"]
        assert replay.payload["is_test_response"] is True, (
            "stored test reply must not be relabelled by the current adapter"
        )

        # Reverse direction: a real reply stays real when the test adapter
        # is back in place.
        real_first = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-r-00002"), DummyAuth(), "r3",
        ))
        assert real_first.payload["is_test_response"] is False
        agent_gateway.default_agent_adapter = TestAgentAdapter()
        real_replay = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(message_id="msg-r-00002"), DummyAuth(), "r4",
        ))
        assert real_replay.payload["replayed"] is True
        assert real_replay.payload["is_test_response"] is False
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


def test_f090_replayed_message_id_with_different_text_is_rejected():
    """A message id is bound to its request content; reuse with different
    text is a conflict, never the old reply."""
    _ensure_default_adapter()
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    agent_gateway.default_agent_adapter = TestAgentAdapter()
    agent_gateway.session_store = _fresh_store()
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-conflict"

        first = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
        ))
        assert first.status == 200

        conflict = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat",
            _chat_body(message="different text"), DummyAuth(), "r2",
        ))
        assert conflict.status == 409
        assert conflict.payload["error"] == "agent_message_id_conflict"
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


def test_f090_external_http_agent_url_is_rejected_but_loopback_is_allowed():
    """F-090: external agent endpoints must be HTTPS; plain HTTP stays an
    explicit loopback-only exception."""
    _ensure_default_adapter()
    import pytest
    from eitaa_bridge.application import agent_gateway

    import os
    os.environ["AGENT_F090_KEY"] = "synthetic"
    try:
        # Scheme is the only invalid part: the credential variable exists.
        with pytest.raises(BridgeError) as external:
            agent_gateway.configure_default_adapter(
                {"enabled": True, "url": "http://agent.example/chat", "model": "m",
                 "api_key_env": "AGENT_F090_KEY"}
            )
        assert external.value.code == "agent_gateway_config_invalid"

        assert agent_gateway.configure_default_adapter(
            {"enabled": True, "url": "https://agent.example/chat", "model": "m",
             "api_key_env": "AGENT_F090_KEY"}
        ) == "configurable"
        assert agent_gateway.configure_default_adapter(
            {"enabled": True, "url": "http://127.0.0.1:8901/chat", "model": "m",
             "api_key_env": "AGENT_F090_KEY"}
        ) == "configurable"
    finally:
        agent_gateway.configure_default_adapter(None)
        del os.environ["AGENT_F090_KEY"]


def test_f090_waiter_times_out_then_replays_once_first_completes():
    """A bounded wait must not hang forever; the first attempt still stores
    its reply, so a later retry replays instead of re-running the agent."""
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    previous_wait = agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS
    agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS = 0.2

    class SlowAdapter:
        is_test_adapter = False

        async def chat(self, message, session_id, context, *, history):
            await asyncio.sleep(0.6)
            return AgentChatResponse(response="slow-reply", session_id=session_id, is_test_response=False)

        async def health(self):
            return True

    class FastReplayCheck:
        calls = 0

        async def chat(self, message, session_id, context, *, history):
            FastReplayCheck.calls += 1
            return AgentChatResponse(response="should-not-run", session_id=session_id, is_test_response=False)

        async def health(self):
            return True

    agent_gateway.default_agent_adapter = SlowAdapter()
    agent_gateway.session_store = _fresh_store()
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-wait"

        async def _pair():
            first = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.sleep(0.1)  # first owns the inflight slot
            waiter = await dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            )
            first_reply = await first
            return waiter, first_reply

        pending, first_reply = asyncio.run(_pair())
        assert pending.status == 503, pending.payload
        assert pending.payload["error"] == "agent_reply_pending"
        assert first_reply.status == 200
        assert first_reply.payload["response"] == "slow-reply"

        # First attempt completed and stored its reply; a later retry replays.
        agent_gateway.default_agent_adapter = FastReplayCheck()
        third = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r3",
        ))
        assert third.payload["replayed"] is True
        assert third.payload["response"] == "slow-reply"
        assert FastReplayCheck.calls == 0
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store
        agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS = previous_wait


def test_f090_cancelled_first_request_releases_waiter_with_failure():
    """Cancellation of the first attempt must release waiters with a defined
    failure and leave nothing cached, so a later retry runs fresh."""
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store
    previous_wait = agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS
    agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS = 5.0

    class HangingAdapter:
        calls = 0

        async def chat(self, message, session_id, context, *, history):
            HangingAdapter.calls += 1
            await asyncio.sleep(10)

        async def health(self):
            return True

    class FreshAdapter:
        calls = 0

        async def chat(self, message, session_id, context, *, history):
            FreshAdapter.calls += 1
            return AgentChatResponse(response="fresh-run", session_id=session_id, is_test_response=False)

        async def health(self):
            return True

    hanging = HangingAdapter()
    agent_gateway.default_agent_adapter = hanging
    agent_gateway.session_store = _fresh_store()
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-cancel"

        async def _pair():
            first_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.sleep(0.1)  # let the first claim the inflight slot
            waiter = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            ))
            await asyncio.sleep(0.1)
            first_task.cancel()
            return await waiter, first_task

        waiter_response, first_task = asyncio.run(_pair())
        try:
            await_first = None
        except Exception:
            await_first = None
        assert waiter_response.status in (400, 502), waiter_response.payload
        assert waiter_response.payload["error"] == "agent_first_attempt_cancelled"

        agent_gateway.default_agent_adapter = FreshAdapter()
        fresh = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r3",
        ))
        assert fresh.status == 200
        assert fresh.payload["response"] == "fresh-run"
        assert fresh.payload["replayed"] is False
        assert HangingAdapter.calls == 1
        assert FreshAdapter.calls == 1
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store
        agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS = previous_wait


def test_f090_first_attempt_failure_releases_waiter_with_same_error():
    """When the first adapter attempt fails, a racing waiter receives the
    same defined failure and nothing is cached."""
    from eitaa_bridge.application import agent_gateway

    previous_adapter = agent_gateway.default_agent_adapter
    previous_store = agent_gateway.session_store

    class DownAdapter:
        is_test_adapter = False

        async def chat(self, message, session_id, context, *, history):
            import httpx
            raise httpx.ConnectError("down")

        async def health(self):
            return False

    agent_gateway.default_agent_adapter = DownAdapter()
    agent_gateway.session_store = _fresh_store()
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f090-err"

        async def _pair():
            first = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.sleep(0.05)
            waiter = await dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            )
            first_response = await first
            return first_response, waiter

        first_response, waiter = asyncio.run(_pair())
        assert first_response.status == 502
        assert waiter.status == 502
        assert waiter.payload["error"] == "agent_communication_failed"
    finally:
        agent_gateway.default_agent_adapter = previous_adapter
        agent_gateway.session_store = previous_store


# ---------------------------------------------------------------------------
# F-091 reproduction tests (RED before the fix): a claimed first attempt
# stays owned until the reply is fully stored or the claim is explicitly
# failed — a failed save must never leave the message id pending in-flight.
# ---------------------------------------------------------------------------

class _FakeClock:
    def __init__(self, start=2_000_000.0):
        self.now = start

    def __call__(self):
        return self.now


class _GatedAdapter:
    """Counts real adapter invocations; while gated, the call blocks until
    the test releases it, so the store state can change mid-adapter-run."""

    is_test_adapter = False

    def __init__(self, reply="late-reply"):
        self.calls = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.gate = True
        self._reply = reply

    async def chat(self, message, session_id, context, *, history):
        self.calls += 1
        if self.gate:
            self.entered.set()
            await self.release.wait()
        return AgentChatResponse(
            response=self._reply, session_id=session_id, is_test_response=False,
        )

    async def health(self):
        return True


def _fill_service_capacity(store, service_name, total=100):
    """Fill the per-service session cap through the real store path."""
    for i in range(total):
        store.add_message(
            AgentChatContext(f"fill-user-{i}", f"fill-session-{i}", service_name),
            "user",
            "capacity-fill",
        )


def _install_f091_harness(store, adapter, wait_seconds=2.0):
    from eitaa_bridge.application import agent_gateway

    previous = (
        agent_gateway.default_agent_adapter,
        agent_gateway.session_store,
        agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS,
    )
    agent_gateway.default_agent_adapter = adapter
    agent_gateway.session_store = store
    agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS = wait_seconds
    return previous


def _restore_f091_harness(previous):
    from eitaa_bridge.application import agent_gateway

    (
        agent_gateway.default_agent_adapter,
        agent_gateway.session_store,
        agent_gateway.AGENT_INFLIGHT_WAIT_SECONDS,
    ) = previous


def test_f091_session_expiry_and_full_capacity_during_adapter_run_resolve_claim():
    """V-223/F-091 reproduction: the session expires while the adapter runs
    and the per-service capacity fills up, so storing the reply fails with
    agent_too_many_sessions. The claim must still be resolved: no in-flight
    entry may stay behind and a same-id retry must never come back as
    agent_reply_pending."""
    from eitaa_bridge.application import agent_gateway

    clock = _FakeClock()
    store = _fresh_store(clock=clock)
    adapter = _GatedAdapter()
    previous = _install_f091_harness(store, adapter)
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f091-capacity"

        ctx = AgentChatContext("u1", "s1", "f091-capacity")
        message_id = _chat_body()["message_id"]

        async def _run():
            first_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.wait_for(adapter.entered.wait(), timeout=5)
            clock.now += 3601  # the session expires mid-adapter-run
            _fill_service_capacity(store, "f091-capacity")
            assert store.service_session_counts["f091-capacity"] == 100
            adapter.release.set()
            first = await asyncio.wait_for(first_task, timeout=5)
            retry = await asyncio.wait_for(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            ), timeout=5)
            return first, retry

        first, retry = asyncio.run(_run())

        assert first.status == 400, first.payload
        assert first.payload["error"] == "agent_too_many_sessions"

        # The failed save must not leave the claim behind (F-091).
        assert len(store._inflight) == 0, (
            f"in-flight left behind: {sorted(store._inflight)}"
        )

        # The retry gets a real, fresh decision — never agent_reply_pending.
        assert retry.status == 400, retry.payload
        assert retry.payload["error"] == "agent_too_many_sessions"
        # Capacity is still exhausted, so the retry is rejected at claim time
        # without charging the agent again.
        assert adapter.calls == 1, f"adapter invoked {adapter.calls} times"

        # No half-recorded history or reply anywhere.
        assert store.get_history(ctx) == []
        assert store.get_reply(ctx, message_id) is None
    finally:
        _restore_f091_harness(previous)


def test_f091_waiter_receives_same_save_failure_and_claim_is_resolved():
    """A racing waiter must receive the same defined failure as the first
    request when the reply cannot be stored — never agent_reply_pending —
    and the in-flight entry must be resolved."""
    from eitaa_bridge.application import agent_gateway

    clock = _FakeClock()
    store = _fresh_store(clock=clock)
    adapter = _GatedAdapter()
    previous = _install_f091_harness(store, adapter, wait_seconds=5.0)
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f091-waiter"

        async def _run():
            first_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.wait_for(adapter.entered.wait(), timeout=5)
            waiter_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            ))
            await asyncio.sleep(0.1)  # the waiter joins the in-flight wait
            clock.now += 3601
            _fill_service_capacity(store, "f091-waiter")
            adapter.release.set()
            first = await asyncio.wait_for(first_task, timeout=10)
            waiter = await asyncio.wait_for(waiter_task, timeout=10)
            return first, waiter

        first, waiter = asyncio.run(_run())

        assert first.status == 400, first.payload
        assert first.payload["error"] == "agent_too_many_sessions"
        assert waiter.status == 400, waiter.payload
        assert waiter.payload["error"] == "agent_too_many_sessions"
        assert waiter.payload["error"] != "agent_reply_pending"
        assert len(store._inflight) == 0, (
            f"in-flight left behind: {sorted(store._inflight)}"
        )
        assert adapter.calls == 1, f"adapter invoked {adapter.calls} times"
    finally:
        _restore_f091_harness(previous)


def test_f091_retry_after_save_failure_takes_fresh_claim_and_can_succeed():
    """After a failed save, the next same-id attempt must take a fresh claim:
    once capacity is available again the adapter runs again, the reply is
    stored, and a third call replays it without the adapter (F-090 kept)."""
    from eitaa_bridge.application import agent_gateway

    clock = _FakeClock()
    store = _fresh_store(clock=clock)
    adapter = _GatedAdapter()
    previous = _install_f091_harness(store, adapter)
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f091-retry"

        ctx = AgentChatContext("u1", "s1", "f091-retry")
        message_id = _chat_body()["message_id"]

        async def _run():
            first_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.wait_for(adapter.entered.wait(), timeout=5)
            clock.now += 3601
            _fill_service_capacity(store, "f091-retry")
            adapter.release.set()
            first = await asyncio.wait_for(first_task, timeout=5)
            # Free the capacity the honest way: the fill sessions expire too.
            adapter.gate = False
            clock.now += 3601
            retry = await asyncio.wait_for(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            ), timeout=5)
            third = await asyncio.wait_for(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r3",
            ), timeout=5)
            return first, retry, third

        first, retry, third = asyncio.run(_run())

        assert first.status == 400, first.payload
        assert first.payload["error"] == "agent_too_many_sessions"
        assert len(store._inflight) == 0, (
            f"in-flight left behind: {sorted(store._inflight)}"
        )

        assert retry.status == 200, retry.payload
        assert retry.payload["replayed"] is False
        assert retry.payload["response"] == "late-reply"
        assert adapter.calls == 2, f"adapter invoked {adapter.calls} times"
        assert len(store._inflight) == 0
        stored = store.get_reply(ctx, message_id)
        assert stored is not None and stored.response == "late-reply"

        # The stored reply replays without a third adapter call.
        assert third.payload["replayed"] is True
        assert third.payload["response"] == "late-reply"
        assert adapter.calls == 2, f"adapter invoked {adapter.calls} times"
    finally:
        _restore_f091_harness(previous)


def test_f091_mid_save_failure_rolls_back_partial_history_and_releases_claim():
    """A failure between storing the user message and the agent message must
    leave no half-recorded history or reply; the claim is released with the
    real failure code for the first request and every waiter, and a retry
    with the failure disarmed succeeds."""
    from eitaa_bridge.application import agent_gateway

    class FailingAppendStore(AgentChatSessionStore):
        def __init__(self):
            super().__init__()
            self.fail_agent_append = False

        def _append_message_locked(self, context, session_data, now, role, content):
            if self.fail_agent_append and role == "agent":
                raise BridgeError(
                    "synthetic history storage failure", code="agent_storage_failed"
                )
            return super()._append_message_locked(context, session_data, now, role, content)

    store = FailingAppendStore()
    adapter = _GatedAdapter()
    previous = _install_f091_harness(store, adapter, wait_seconds=5.0)
    try:
        class DummyAuth:
            scopes = ["agent.chat"]
            service_name = "f091-rollback"

        ctx = AgentChatContext("u1", "s1", "f091-rollback")
        message_id = _chat_body()["message_id"]

        async def _run():
            first_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r1",
            ))
            await asyncio.wait_for(adapter.entered.wait(), timeout=5)
            waiter_task = asyncio.ensure_future(dispatch_m2m(
                "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r2",
            ))
            await asyncio.sleep(0.1)
            store.fail_agent_append = True
            adapter.release.set()
            first = await asyncio.wait_for(first_task, timeout=10)
            waiter = await asyncio.wait_for(waiter_task, timeout=10)
            return first, waiter

        first, waiter = asyncio.run(_run())

        assert first.status == 400, first.payload
        assert first.payload["error"] == "agent_storage_failed"
        assert waiter.status == 400, waiter.payload
        assert waiter.payload["error"] == "agent_storage_failed"
        # No half-recorded exchange: no user message, no reply, no claim.
        assert store.get_history(ctx) == []
        assert store.get_reply(ctx, message_id) is None
        assert len(store._inflight) == 0, (
            f"in-flight left behind: {sorted(store._inflight)}"
        )
        # The session predates the failed exchange and stays; capacity
        # accounting stays consistent (no leak, no double release).
        assert store.service_session_counts["f091-rollback"] == 1
        assert adapter.calls == 1, f"adapter invoked {adapter.calls} times"

        # Recovery: with the failure disarmed, a same-id retry claims fresh,
        # runs the adapter again and stores the full exchange.
        store.fail_agent_append = False
        adapter.gate = False
        recovered = asyncio.run(dispatch_m2m(
            "POST", "/api/v2/m2m/agent/chat", _chat_body(), DummyAuth(), "r3",
        ))
        assert recovered.status == 200, recovered.payload
        assert recovered.payload["replayed"] is False
        assert adapter.calls == 2, f"adapter invoked {adapter.calls} times"
        assert [item["role"] for item in store.get_history(ctx)] == ["user", "agent"]
        assert store.get_reply(ctx, message_id) is not None
        assert len(store._inflight) == 0
    finally:
        _restore_f091_harness(previous)


def test_f091_claim_stays_registered_until_the_exchange_failure_is_resolved():
    """The claim must cover the full exchange transaction, including its
    rollback.  Removing it before a failing write leaves a window in which a
    competing same-id request can take a second first-attempt claim."""

    class ClaimVisibleFailureStore(AgentChatSessionStore):
        def __init__(self):
            super().__init__()
            self.claim_was_held_during_failure = False

        def _append_message_locked(self, context, session_data, now, role, content):
            if role == "agent":
                inflight_key = (
                    context.service_name,
                    context.web_user_id,
                    context.session_id,
                    "f091-transaction-claim",
                )
                self.claim_was_held_during_failure = inflight_key in self._inflight
                raise BridgeError(
                    "synthetic exchange storage failure", code="agent_storage_failed"
                )
            return super()._append_message_locked(context, session_data, now, role, content)

    store = ClaimVisibleFailureStore()
    context = AgentChatContext("u1", "s1", "f091-transaction")
    message_id = "f091-transaction-claim"
    message_hash = "f091-hash"

    outcome, _ = store.claim_reply(context, message_id, message_hash)
    assert outcome == "run"
    with pytest.raises(BridgeError, match="synthetic exchange storage failure"):
        store.record_exchange(
            context,
            message_id,
            message_hash,
            "request",
            "response",
            False,
        )

    # A claim must remain registered until the transaction either publishes a
    # full exchange or has rolled it back and told all waiters about failure.
    assert store.claim_was_held_during_failure is True
    assert store.get_history(context) == []
    assert store.get_reply(context, message_id) is None
    assert store._inflight == {}

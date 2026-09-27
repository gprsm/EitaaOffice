"""AI Agent Chat Gateway (chat-only surface).

Rules that must not be weakened (F-085 gap #4):
- The agent can only chat. It gets no provider orchestration, no coordinator
  access, no messaging-send powers and no free user-data reads; this module
  must not import them (enforced by tests).
- Session identity is the triple (service_name, web_user_id, session_id);
  two services never share a conversation or a reply cache.
- A chat message carries a service-scoped ``message_id``; retrying the same
  id returns the stored reply without calling the adapter again.
- The real adapter is wired only from an explicit, valid configuration
  (url/model/api_key_env). Nothing is guessed; an invalid configuration is an
  error, and without configuration the marked test adapter answers.
"""

from __future__ import annotations

import os
import time
import httpx
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from ..errors import BridgeConfigurationError, BridgeError


@dataclass
class AgentChatContext:
    web_user_id: str
    session_id: str
    service_name: str
    max_message_length: int = 4096
    max_context_messages: int = 20
    session_ttl_seconds: int = 3600


@dataclass
class AgentChatResponse:
    response: str
    session_id: str
    is_test_response: bool


@runtime_checkable
class AgentAdapter(Protocol):
    async def chat(
        self,
        message: str,
        session_id: str,
        context: AgentChatContext,
        *,
        history: list[dict[str, str]],
    ) -> AgentChatResponse: ...

    async def health(self) -> bool: ...


class TestAgentAdapter:
    """For development only. Not for production."""

    is_test_adapter = True

    async def chat(
        self,
        message: str,
        session_id: str,
        context: AgentChatContext,
        *,
        history: list[dict[str, str]],
    ) -> AgentChatResponse:
        del history
        if len(message) > context.max_message_length:
            raise BridgeError("Message too long", code="agent_message_too_long")

        return AgentChatResponse(
            response="این یک پاسخ آزمایشی است. عامل هوشمند واقعی هنوز متصل نشده است.",
            session_id=session_id,
            is_test_response=True
        )

    async def health(self) -> bool:
        return True


class ConfigurableAgentAdapter:
    """Explicitly configured bridge to an external agent service.

    The API key is read from the named environment variable at construction
    time and is never logged, echoed or persisted.
    """

    is_test_adapter = False

    def __init__(self, agent_url: str, agent_api_key: str, model_name: str):
        self.agent_url = agent_url
        self.agent_api_key = agent_api_key
        self.model_name = model_name
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def chat(
        self,
        message: str,
        session_id: str,
        context: AgentChatContext,
        *,
        history: list[dict[str, str]],
    ) -> AgentChatResponse:
        if len(message) > context.max_message_length:
            raise BridgeError("Message too long", code="agent_message_too_long")

        conversation = [
            {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")}
            for item in history[-context.max_context_messages:]
        ]
        conversation.append({"role": "user", "content": message})
        payload = {
            "model": self.model_name,
            "messages": conversation,
            "user": context.web_user_id,
            "session_id": session_id
        }
        headers = {
            "Authorization": f"Bearer {self.agent_api_key}",
            "Content-Type": "application/json"
        }

        try:
            resp = await self.http_client.post(self.agent_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not reply:
                raise BridgeError("Invalid response from agent", code="agent_invalid_response")

            return AgentChatResponse(
                response=reply,
                session_id=session_id,
                is_test_response=False
            )
        except BridgeError:
            raise
        except Exception as e:
            raise BridgeError("Agent communication failed", code="agent_communication_failed") from e

    async def health(self) -> bool:
        try:
            resp = await self.http_client.get(f"{self.agent_url}/health")
            return resp.status_code == 200
        except Exception:
            return False


def configure_default_adapter(settings: Mapping[str, Any] | None) -> str:
    """Wire the process-wide chat adapter from an explicit configuration.

    ``None`` (or a disabled section) selects the marked test adapter. A
    present section must be complete and valid — url must be http(s), the
    model non-empty and ``api_key_env`` must name a set environment
    variable — otherwise this raises; nothing is guessed.
    """
    global default_agent_adapter
    if not settings or not settings.get("enabled"):
        default_agent_adapter = TestAgentAdapter()
        return "test"

    url = str(settings.get("url") or "").strip()
    model = str(settings.get("model") or "").strip()
    api_key_env = str(settings.get("api_key_env") or "").strip()
    if not url.startswith(("https://", "http://")) or not model or not api_key_env:
        raise BridgeConfigurationError(
            "The agent gateway configuration is incomplete.",
            code="agent_gateway_config_invalid",
        )
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise BridgeConfigurationError(
            "The agent gateway credential environment variable is not set.",
            code="agent_gateway_config_invalid",
        )
    default_agent_adapter = ConfigurableAgentAdapter(url, api_key, model)
    return "configurable"


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float


class AgentChatSessionStore:
    def __init__(self):
        # Key: (service_name, web_user_id, session_id)
        self.sessions = {}
        self.service_session_counts = defaultdict(int)

    def _cleanup_expired(self, now: float, context: AgentChatContext):
        expired_keys = []
        for key, data in self.sessions.items():
            if now - data['last_accessed'] > context.session_ttl_seconds:
                expired_keys.append(key)
        for key in expired_keys:
            self._remove_session(key)

    def _remove_session(self, key):
        if key in self.sessions:
            service = key[0]
            del self.sessions[key]
            self.service_session_counts[service] -= 1

    def add_message(self, context: AgentChatContext, role: str, content: str):
        now = time.time()
        self._cleanup_expired(now, context)

        key = (context.service_name, context.web_user_id, context.session_id)

        if key not in self.sessions:
            if self.service_session_counts[context.service_name] >= 100:
                raise BridgeError("Too many active sessions for service", code="agent_too_many_sessions")
            self.sessions[key] = {
                'messages': [],
                'replies': {},
                'last_accessed': now
            }
            self.service_session_counts[context.service_name] += 1

        session_data = self.sessions[key]
        session_data['last_accessed'] = now
        session_data['messages'].append(ChatMessage(role=role, content=content, timestamp=now))

        # Keep only last N messages
        if len(session_data['messages']) > context.max_context_messages:
            session_data['messages'] = session_data['messages'][-context.max_context_messages:]

    def get_messages(self, context: AgentChatContext):
        key = (context.service_name, context.web_user_id, context.session_id)
        if key in self.sessions:
            return self.sessions[key]['messages']
        return []

    def get_history(self, context: AgentChatContext) -> list[dict[str, str]]:
        """Bounded prior conversation, oldest first, for the adapter."""
        return [
            {"role": message.role, "content": message.content}
            for message in self.get_messages(context)
        ]

    def store_reply(self, context: AgentChatContext, message_id: str, reply: str):
        key = (context.service_name, context.web_user_id, context.session_id)
        if key not in self.sessions:
            return
        replies = self.sessions[key].setdefault('replies', {})
        replies[str(message_id)] = str(reply)
        # Bound the reply cache alongside the conversation window.
        if len(replies) > 256:
            replies.pop(next(iter(replies)))

    def get_reply(self, context: AgentChatContext, message_id: str) -> str | None:
        key = (context.service_name, context.web_user_id, context.session_id)
        if key not in self.sessions:
            return None
        return self.sessions[key].get('replies', {}).get(str(message_id))


# Singleton session store
session_store = AgentChatSessionStore()

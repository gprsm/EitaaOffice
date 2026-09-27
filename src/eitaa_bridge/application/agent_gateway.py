"""AI Agent Chat Gateway."""

from __future__ import annotations

import time
import httpx
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..errors import BridgeError


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
    async def chat(self, message: str, session_id: str, context: AgentChatContext) -> AgentChatResponse: ...
    async def health(self) -> bool: ...


class TestAgentAdapter:
    """For development only. Not for production."""
    
    async def chat(self, message: str, session_id: str, context: AgentChatContext) -> AgentChatResponse:
        # Sanitize input roughly (though we don't use it, it's a good practice here)
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
    def __init__(self, agent_url: str, agent_api_key: str, model_name: str):
        self.agent_url = agent_url
        self.agent_api_key = agent_api_key
        self.model_name = model_name
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def chat(self, message: str, session_id: str, context: AgentChatContext) -> AgentChatResponse:
        if len(message) > context.max_message_length:
            raise BridgeError("Message too long", code="agent_message_too_long")

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": message}],
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
        except Exception as e:
            raise BridgeError("Agent communication failed", code="agent_communication_failed") from e

    async def health(self) -> bool:
        try:
            resp = await self.http_client.get(f"{self.agent_url}/health")
            return resp.status_code == 200
        except Exception:
            return False


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float

class AgentChatSessionStore:
    def __init__(self):
        # Key: (service_name, web_user_id, session_id)
        # Value: dict containing 'messages', 'last_accessed'
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

# Singleton session store
session_store = AgentChatSessionStore()

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

F-090 hardening (2026-09-27):
- The first-run/replay decision for a message id is atomic per
  (service, web user, session, message_id) inside this process, guarded by a
  process-wide lock and an in-flight registry: racing requests wait for the
  first adapter call instead of repeating it. This guarantee is in-memory and
  per-process; after a restart, or across multiple backend processes, a
  repeated id may run the adapter again — the contract states this bound and
  no exactly-once claim is made beyond it.
- Replies are cached together with their ``is_test_response`` flag and their
  request-content hash; replay never re-labels a stored reply from the
  current adapter and never returns a stored reply for different content.
- Session expiry is enforced on every read, not only on writes.

F-091 hardening (2026-09-27):
- A claimed first attempt stays owned until the reply is fully stored or the
  claim is explicitly failed. The user message, the agent message and the
  reply record are stored atomically (``record_exchange``); every failure —
  including a save failure after the adapter answered (e.g. the session
  expired mid-run and the per-service capacity is exhausted) and a
  cancellation — resolves the in-flight entry with the real error code, so
  waiters are released and a retry takes a fresh claim. No half-recorded
  history or partial reply is ever visible.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import httpx
from urllib.parse import urlsplit
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

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
    parsed_host = ""
    if url.startswith(("https://", "http://")):
        try:
            parsed_host = (urlsplit(url).hostname or "").strip().lower()
        except ValueError:
            parsed_host = ""
        # External endpoints must be HTTPS; plain HTTP is an explicit
        # loopback-only exception for same-host internal agents.
        loopback = {"127.0.0.1", "::1", "localhost"}
        if url.startswith("http://") and parsed_host not in loopback:
            raise BridgeConfigurationError(
                "External agent endpoints must use HTTPS.",
                code="agent_gateway_config_invalid",
            )
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


@dataclass(frozen=True, slots=True)
class ReplyRecord:
    """A cached agent reply and everything needed to replay it faithfully."""

    response: str
    is_test_response: bool
    message_hash: str
    stored_at: float


@dataclass
class InflightCall:
    """A first adapter attempt in progress for a message id.

    Racing requests wait on ``event``; the runner always resolves the call
    (result or error) in a ``finally`` block, so no abandoned entry can block
    later requests forever.
    """

    message_hash: str
    event: threading.Event = field(default_factory=threading.Event)
    result: ReplyRecord | None = None
    error_code: str | None = None


class AgentChatSessionStore:
    """Thread-safe chat session store with expiry-on-read semantics.

    All reads apply the session TTL first, so expired history or replies are
    never returned and never reach the adapter. The first-run/replay decision
    for a (session, message_id) pair is atomic under the store lock across
    threads and event loops within this process.
    """

    MAX_REPLIES_PER_SESSION = 256

    def __init__(self, clock: Callable[[], float] = time.time):
        # Key: (service_name, web_user_id, session_id)
        self.sessions = {}
        self.service_session_counts = defaultdict(int)
        self._clock = clock
        self._lock = threading.RLock()
        self._inflight: dict[tuple[str, str, str, str], InflightCall] = {}

    def _cleanup_expired_locked(self, context: AgentChatContext):
        now = self._clock()
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

    def _ensure_session_locked(self, context: AgentChatContext):
        now = self._clock()
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
        return key, self.sessions[key], now

    def _append_message_locked(
        self,
        context: AgentChatContext,
        session_data: dict,
        now: float,
        role: str,
        content: str,
    ) -> None:
        """Append one message under the store lock and enforce the cap.

        Shared by ``add_message`` and ``record_exchange``; callers must hold
        the lock and pass an ensured session.
        """
        session_data['messages'].append(ChatMessage(role=role, content=content, timestamp=now))

        # Keep only last N messages
        if len(session_data['messages']) > context.max_context_messages:
            session_data['messages'] = session_data['messages'][-context.max_context_messages:]

    def add_message(self, context: AgentChatContext, role: str, content: str):
        with self._lock:
            self._cleanup_expired_locked(context)
            key, session_data, now = self._ensure_session_locked(context)
            session_data['last_accessed'] = now
            self._append_message_locked(context, session_data, now, role, content)

    def get_messages(self, context: AgentChatContext):
        with self._lock:
            self._cleanup_expired_locked(context)
            key = (context.service_name, context.web_user_id, context.session_id)
            if key in self.sessions:
                return list(self.sessions[key]['messages'])
            return []

    def get_history(self, context: AgentChatContext) -> list[dict[str, str]]:
        """Bounded prior conversation, oldest first, for the adapter.

        Expiry is applied before the read: an expired session yields an empty
        history and never leaks stale content to the adapter.
        """
        with self._lock:
            self._cleanup_expired_locked(context)
            key = (context.service_name, context.web_user_id, context.session_id)
            if key in self.sessions:
                return [
                    {"role": message.role, "content": message.content}
                    for message in self.sessions[key]['messages']
                ]
            return []

    def claim_reply(
        self,
        context: AgentChatContext,
        message_id: str,
        message_hash: str,
    ) -> tuple[str, Any]:
        """Atomically decide first-run vs replay for one message id.

        Returns ``("replay", ReplyRecord)`` when a matching reply is cached,
        ``("conflict", None)`` when the id is bound to different content, and
        ``("inflight", InflightCall)`` when a first attempt is already
        running; otherwise ``("run", None)`` and this caller owns the first
        attempt and must finish it with ``record_exchange`` (reply stored
        atomically with the conversation) or ``fail_reply``.
        """
        with self._lock:
            self._cleanup_expired_locked(context)
            key = (context.service_name, context.web_user_id, context.session_id)
            inflight_key = (*key, str(message_id))
            session = self.sessions.get(key)
            if session is not None:
                record = session['replies'].get(str(message_id))
                if record is not None:
                    if record.message_hash != message_hash:
                        return ("conflict", None)
                    return ("replay", record)
            inflight = self._inflight.get(inflight_key)
            if inflight is not None:
                if inflight.message_hash != message_hash:
                    return ("conflict", None)
                return ("inflight", inflight)
            self._ensure_session_locked(context)
            self._inflight[inflight_key] = InflightCall(message_hash=message_hash)
            return ("run", None)

    def record_exchange(
        self,
        context: AgentChatContext,
        message_id: str,
        message_hash: str,
        user_message: str,
        agent_message: str,
        is_test_response: bool,
    ) -> ReplyRecord | None:
        """Store one full exchange atomically and resolve its claim (F-091).

        The user message, the agent message and the replayable reply record
        for ``message_id`` become visible to other requests together, or not
        at all. On any failure the partial mutations are rolled back, the
        in-flight claim started by ``claim_reply`` is resolved with the real
        failing error code (releasing waiters), and the original failure is
        re-raised unmasked. A failed save therefore never leaves a
        half-recorded history, a partial reply or a pending claim behind.
        """
        key = (context.service_name, context.web_user_id, context.session_id)
        inflight_key = (*key, str(message_id))
        inflight: InflightCall | None = None
        record: ReplyRecord | None = None
        snapshot: dict[str, Any] | None = None
        try:
            with self._lock:
                # Resolve the claim entry first: everything below can fail,
                # and this call must stay able to release the claim.
                inflight = self._inflight.pop(inflight_key, None)
                session = self.sessions.get(key)
                if session is not None:
                    snapshot = {
                        "session": session,
                        "last_accessed": session['last_accessed'],
                        "messages": list(session['messages']),
                        "replies": dict(session['replies']),
                    }
                self._cleanup_expired_locked(context)
                _, session_data, now = self._ensure_session_locked(context)
                session_data['last_accessed'] = now
                self._append_message_locked(context, session_data, now, "user", str(user_message))
                self._append_message_locked(context, session_data, now, "agent", str(agent_message))
                record = ReplyRecord(
                    response=str(agent_message),
                    is_test_response=bool(is_test_response),
                    message_hash=message_hash,
                    stored_at=now,
                )
                session_data['replies'][str(message_id)] = record
                if len(session_data['replies']) > self.MAX_REPLIES_PER_SESSION:
                    session_data['replies'].pop(next(iter(session_data['replies'])))
        except BaseException as exc:
            with self._lock:
                current = self.sessions.get(key)
                if snapshot is not None:
                    if current is snapshot["session"]:
                        # Undo this call's mutations; the session predates it.
                        current['last_accessed'] = snapshot["last_accessed"]
                        current['messages'] = snapshot["messages"]
                        current['replies'] = snapshot["replies"]
                    elif current is not None:
                        # This call re-created the session after expiry; the
                        # failed exchange must not leave it behind.
                        self._remove_session(key)
                elif current is not None:
                    # The session was created by this call.
                    self._remove_session(key)
            if inflight is not None:
                code = str(getattr(exc, "code", "") or "agent_reply_not_stored")
                inflight.error_code = code
                inflight.event.set()
            raise
        if inflight is not None:
            # Publish outside the lock: waiters read the inflight object
            # directly and must never block on the store lock at wake-up.
            inflight.result = record
            inflight.event.set()
        return record

    def complete_reply(
        self,
        context: AgentChatContext,
        message_id: str,
        message_hash: str,
        response: str,
        is_test_response: bool,
    ) -> None:
        """Store the first attempt's reply and wake any racing requests.

        Lower-level primitive: it stores only the reply record. The handler
        path must use ``record_exchange`` instead, which additionally stores
        the conversation atomically and resolves the claim on every failure
        (F-091).
        """
        with self._lock:
            key = (context.service_name, context.web_user_id, context.session_id)
            inflight_key = (*key, str(message_id))
            inflight = self._inflight.pop(inflight_key, None)
            session = self.sessions.get(key)
            record = None
            if session is not None:
                record = ReplyRecord(
                    response=str(response),
                    is_test_response=bool(is_test_response),
                    message_hash=message_hash,
                    stored_at=self._clock(),
                )
                session['last_accessed'] = self._clock()
                session['replies'][str(message_id)] = record
                if len(session['replies']) > self.MAX_REPLIES_PER_SESSION:
                    session['replies'].pop(next(iter(session['replies'])))
        if inflight is not None:
            # Publish outside the lock: waiters read the inflight object
            # directly and must never block on the store lock at wake-up.
            inflight.result = record
            if record is None:
                inflight.error_code = "agent_reply_not_stored"
            inflight.event.set()

    def fail_reply(
        self,
        context: AgentChatContext,
        message_id: str,
        error_code: str = "agent_communication_failed",
    ) -> None:
        """Resolve a first attempt with a failure so waiters are released."""
        with self._lock:
            key = (context.service_name, context.web_user_id, context.session_id)
            inflight_key = (*key, str(message_id))
            inflight = self._inflight.pop(inflight_key, None)
        if inflight is not None:
            inflight.error_code = error_code
            inflight.event.set()

    def get_reply(self, context: AgentChatContext, message_id: str):
        with self._lock:
            self._cleanup_expired_locked(context)
            key = (context.service_name, context.web_user_id, context.session_id)
            if key not in self.sessions:
                return None
            return self.sessions[key].get('replies', {}).get(str(message_id))


# Process-wide chat adapter. The initial binding is the marked test adapter;
# configure_default_adapter replaces it from an explicit configuration.
default_agent_adapter: AgentAdapter = TestAgentAdapter()

# How long a racing request waits for the first adapter attempt of the same
# message id before failing with agent_reply_pending. Module attribute so
# tests can shrink it.
AGENT_INFLIGHT_WAIT_SECONDS = 30.0

# Singleton session store
session_store = AgentChatSessionStore()

"""Reference Web Backend Client / SDK Module (Phase 7).

Designed for secure backend integration (e.g., Python FastAPI/Django, Node/Express, Java/Go).
Enforces:
1. Zero secrets in browser: Bridge M2M credentials and AI keys remain on backend.
2. Preflight check: Verify bridge and account readiness before displaying OTP page.
3. Capacity reservation: Reserve delivery slot with HMAC-SHA256 recipient binding.
4. Stage-aware OTP dispatch: Stable idempotency key, stage tracking.
5. Bounded status polling: Backoff and retry-after aware, avoids quota exhaustion.
6. Server-side OTP verification: Constant-time comparison, TTL, attempt bounds, single-use.
7. AI Chat Proxy: Level-aware and pseudonymized communication with Agent Gateway.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import hmac
import secrets
import time
from typing import Any, Mapping
import uuid

import httpx

from ..errors import BridgeError


class WebClientError(BridgeError):
    """Base error for web client reference SDK."""

    def __init__(self, message: str, code: str = "web_client_error", status_code: int = 400):
        super().__init__(message, code=code)
        self.status_code = status_code


@dataclasses.dataclass(frozen=True)
class PreflightResult:
    ok: bool
    status: str  # ready, wait, unavailable, unknown
    retry_after_seconds: int
    message: str
    raw_payload: Mapping[str, Any]


@dataclasses.dataclass(frozen=True)
class ReservationResult:
    ok: bool
    reservation_id: str | None
    expires_at: str | None
    ttl_seconds: int
    error: str | None = None
    raw_payload: Mapping[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ReservationCancelResult:
    ok: bool
    reservation: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    error: str | None = None
    raw_payload: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def status(self) -> str:
        return str(self.reservation.get("state", self.reservation.get("status", "cancelled" if self.ok else "error")))


@dataclasses.dataclass(frozen=True)
class OtpDispatchResult:
    ok: bool
    delivery_id: str | None
    stage: str | None
    status: str | None
    is_replayed: bool = False
    error: str | None = None
    raw_payload: Mapping[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class OtpDeliveryStatus:
    delivery_id: str
    status: str  # pending, running, accepted, rejected, uncertain, expired
    stage: str  # admitted, resolving, importing_contact, sending_message, completed, uncertain
    contact_status: str
    send_status: str
    raw_payload: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in {"accepted", "rejected", "uncertain", "expired"}

    @property
    def is_success(self) -> bool:
        return self.status == "accepted"

    @property
    def is_uncertain(self) -> bool:
        return self.status == "uncertain"


@dataclasses.dataclass(frozen=True)
class AgentChatResult:
    ok: bool
    response: str | None
    session_id: str | None = None
    is_test_response: bool = False
    replayed: bool = False
    error: str | None = None
    raw_payload: Mapping[str, Any] = dataclasses.field(default_factory=dict)


class WebOtpSession:
    """Server-side OTP challenge manager.

    Ensures:
    - Constant-time secret comparison (anti-timing attacks).
    - Expiration TTL.
    - Max attempt bounds (anti-brute-force).
    - Single-use consumption (anti-replay).
    """

    def __init__(
        self,
        phone_number: str,
        ttl_seconds: int = 180,
        max_attempts: int = 3,
        otp_len: int = 6,
    ):
        self.session_id = str(uuid.uuid4())
        self.phone_number = phone_number
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.max_attempts = max_attempts
        self.attempts = 0
        self.consumed = False
        self._salt = secrets.token_hex(16)

        # Generate numeric OTP
        digits = "0123456789"
        self._raw_otp = "".join(secrets.choice(digits) for _ in range(otp_len))
        self._hashed_otp = self._hash_code(self._raw_otp)

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(f"{self._salt}:{code}".encode("utf-8")).hexdigest()

    def get_challenge_code_for_dispatch(self) -> str:
        """Only used once on backend to construct outgoing SMS/message."""
        return self._raw_otp

    def verify(self, candidate_code: str) -> tuple[bool, str]:
        """Verifies candidate code with timing-safe comparison."""
        now = time.time()
        if self.consumed:
            return False, "otp_already_consumed"
        if now > self.expires_at:
            return False, "otp_expired"
        if self.attempts >= self.max_attempts:
            return False, "otp_max_attempts_exceeded"

        self.attempts += 1
        candidate_hash = self._hash_code(candidate_code.strip())
        if hmac.compare_digest(self._hashed_otp, candidate_hash):
            self.consumed = True
            return True, "verified"
        return False, "otp_invalid"


def compute_recipient_binding(server_secret: str, phone: str) -> str:
    """Computes stable HMAC-SHA256 binding for recipient phone."""
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    return hmac.new(
        server_secret.encode("utf-8"),
        clean_phone.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class BridgeWebClient:
    """Backend client to communicate with Eitaa Bridge M2M API."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sender_profile_id: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout = timeout
        self._transport = transport
        self.sender_profile_id = sender_profile_id
        self._poll_locks: dict[str, asyncio.Lock] = {}

    async def aclose(self) -> None:
        """Closes any underlying resources."""
        if self._transport is not None and hasattr(self._transport, "aclose"):
            await self._transport.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def _get_headers(self, request_id: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "X-Request-Id": request_id or str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def preflight(
        self,
        intent: str = "otp",
        recipient_kind: str = "new",
        sender_profile_id: str | None = None,
    ) -> PreflightResult:
        """Checks if bridge is ready to deliver messages for the given intent."""
        url = f"{self.base_url}/api/v2/m2m/delivery/preflight"
        payload: dict[str, Any] = {"intent": intent, "recipient_kind": recipient_kind}
        target_profile_id = sender_profile_id or self.sender_profile_id
        if target_profile_id:
            payload["sender_profile_id"] = target_profile_id
        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.content else {}
            decision = data.get("decision", data.get("status", "unknown"))
            retry_after = data.get("retry_after_seconds")
            if retry_after is None:
                retry_after = 0
            if resp.status_code == 200 and data.get("ok"):
                return PreflightResult(
                    ok=True,
                    status=decision,
                    retry_after_seconds=int(retry_after),
                    message=data.get("message", ""),
                    raw_payload=data,
                )
            return PreflightResult(
                ok=False,
                status=data.get("status", "unavailable"),
                retry_after_seconds=int(retry_after or 60),
                message=data.get("message", f"HTTP {resp.status_code}"),
                raw_payload=data,
            )

    async def reserve_capacity(
        self,
        phone: str = "",
        idempotency_key: str = "",
        intent: str = "otp",
        sender_profile_id: str | None = None,
        ttl_seconds: int = 120,
        recipient_binding: str | None = None,
    ) -> ReservationResult:
        """Reserves a delivery capacity slot in Bridge Coordinator."""
        url = f"{self.base_url}/api/v2/m2m/delivery/reservations"
        payload: dict[str, Any] = {
            "intent": intent,
            "ttl_seconds": ttl_seconds,
        }
        if phone:
            payload["recipient"] = {"kind": "phone", "value": phone}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        target_profile_id = sender_profile_id or self.sender_profile_id
        if target_profile_id:
            payload["sender_profile_id"] = target_profile_id
        if recipient_binding:
            payload["recipient_binding"] = recipient_binding

        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code in {200, 201} and data.get("ok"):
                res_obj = data.get("reservation") or data
                return ReservationResult(
                    ok=True,
                    reservation_id=res_obj.get("id") or res_obj.get("reservation_id"),
                    expires_at=res_obj.get("expires_at"),
                    ttl_seconds=int(res_obj.get("ttl_seconds", ttl_seconds)),
                    raw_payload=data,
                )
            return ReservationResult(
                ok=False,
                reservation_id=None,
                expires_at=None,
                ttl_seconds=0,
                error=data.get("error", f"HTTP {resp.status_code}"),
                raw_payload=data,
            )

    async def cancel_reservation(self, reservation_id: str) -> ReservationCancelResult:
        """Cancels a capacity reservation using canonical POST .../cancel route."""
        url = f"{self.base_url}/api/v2/m2m/delivery/reservations/{reservation_id}/cancel"
        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.post(url, json={}, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get("ok"):
                return ReservationCancelResult(
                    ok=True,
                    reservation=data.get("reservation", {}),
                    raw_payload=data,
                )
            return ReservationCancelResult(
                ok=False,
                error=data.get("error", f"HTTP {resp.status_code}"),
                raw_payload=data,
            )

    async def dispatch_otp(
        self,
        reservation_id: str,
        phone: str,
        message: str | None = None,
        contact_name: str | None = None,
        idempotency_key: str = "",
        *,
        message_text: str | None = None,
        display_name: str | None = None,
    ) -> OtpDispatchResult:
        """Dispatches OTP delivery through composite pipeline."""
        final_message = message_text or message or ""
        final_display_name = display_name or contact_name or ""
        url = f"{self.base_url}/api/v2/m2m/otp/deliveries"
        payload = {
            "reservation_id": reservation_id,
            "phone": phone,
            "display_name": final_display_name,
            "message_text": final_message,
            "idempotency_key": idempotency_key,
        }
        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code in {200, 201} and data.get("ok"):
                delivery = data.get("delivery") or data
                return OtpDispatchResult(
                    ok=True,
                    delivery_id=delivery.get("id") or delivery.get("delivery_id"),
                    stage=delivery.get("stage"),
                    status=delivery.get("state") or delivery.get("status"),
                    is_replayed=bool(data.get("replayed", delivery.get("is_replayed", False))),
                    raw_payload=data,
                )
            return OtpDispatchResult(
                ok=False,
                delivery_id=None,
                stage=None,
                status=None,
                error=data.get("error", f"HTTP {resp.status_code}"),
                raw_payload=data,
            )

    async def get_delivery_status(self, delivery_id: str) -> OtpDeliveryStatus:
        """Queries the status of an OTP delivery."""
        url = f"{self.base_url}/api/v2/m2m/otp/deliveries/{delivery_id}"
        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json() if resp.content else {}
            delivery = data.get("delivery") or data
            status_val = delivery.get("state") or delivery.get("status") or ("rate_limited" if resp.status_code == 429 else "unknown")
            retry_after = 0
            if "Retry-After" in resp.headers:
                try:
                    retry_after = int(resp.headers["Retry-After"])
                except ValueError:
                    retry_after = 1
            raw_payload = dict(data)
            if retry_after:
                raw_payload["retry_after_seconds"] = retry_after
            return OtpDeliveryStatus(
                delivery_id=delivery_id,
                status=status_val,
                stage=delivery.get("stage", "unknown"),
                contact_status=delivery.get("contact_status", "unknown"),
                send_status=delivery.get("send_status", "unknown"),
                raw_payload=raw_payload,
            )

    async def poll_delivery_status(
        self,
        delivery_id: str,
        max_polls: int = 10,
        poll_interval: float = 0.5,
    ) -> OtpDeliveryStatus:
        """Polls status with bounded loop, backoff, Retry-After compliance, and parallel polling protection."""
        if delivery_id not in self._poll_locks:
            self._poll_locks[delivery_id] = asyncio.Lock()

        async with self._poll_locks[delivery_id]:
            last_status = None
            current_interval = poll_interval
            for i in range(max_polls):
                last_status = await self.get_delivery_status(delivery_id)
                if last_status.is_terminal:
                    return last_status
                if i < max_polls - 1:
                    retry_after = int(last_status.raw_payload.get("retry_after_seconds", 0))
                    if retry_after > 0:
                        sleep_time = float(retry_after)
                    else:
                        sleep_time = current_interval
                        current_interval = min(current_interval * 1.5, 5.0)
                    await asyncio.sleep(sleep_time)
            return last_status or OtpDeliveryStatus(
                delivery_id=delivery_id,
                status="uncertain",
                stage="uncertain",
                contact_status="unknown",
                send_status="unknown",
            )


    async def chat(
        self,
        web_user_id: str,
        session_id: str,
        message: str,
        message_id: str,
    ) -> AgentChatResult:
        """Proxies chat request to Bridge Agent Gateway."""
        url = f"{self.base_url}/api/v2/m2m/agent/chat"
        payload = {
            "web_user_id": web_user_id,
            "session_id": session_id,
            "message": message,
            "message_id": message_id,
        }
        headers = self._get_headers()

        async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get("ok"):
                return AgentChatResult(
                    ok=True,
                    response=data.get("response"),
                    session_id=data.get("session_id", session_id),
                    is_test_response=bool(data.get("is_test_response", False)),
                    replayed=bool(data.get("replayed", False)),
                    raw_payload=data,
                )
            return AgentChatResult(
                ok=False,
                response=None,
                error=data.get("error", f"HTTP {resp.status_code}"),
                raw_payload=data,
            )

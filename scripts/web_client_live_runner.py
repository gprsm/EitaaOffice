"""Web Client & M2M Live Warm Acceptance Runner (Phase 8).

Default-off, owner-confirmed runner.
Features:
- Safe dry-plan mode by default (zero network traffic, zero credentials requested).
- Requires explicit --allow-live flag and loopback origin (http://127.0.0.1:PORT).
- Requires explicit operator confirmation; impactful actions must be confirmed
  for THAT SAME action (non-interactive: ``--confirm <action>``).
- No token, phone number, or private message text is accepted from argv.
  Secrets and targets come from the environment (secure settings/secret store)
  or from hidden in-memory prompts, never from the command line.
- Executes real API calls via BridgeWebClient against live loopback instance.
- ``warm_verified`` is reported ONLY with an authenticated session witness and
  a real connect count (TCP connects observed by the transport); a successful
  preflight or reservation response alone never proves warmth.
- Bounded safe error codes, zero raw AI responses or exception payloads in
  output, and recovery guidance.
- Prohibits automated retries on uncertain results.
"""

from __future__ import annotations

import argparse
import asyncio
from getpass import getpass
import json
import os
import sys
from urllib.parse import urlsplit
import uuid

import httpcore
import httpx

from eitaa_bridge.application.web_client_reference import BridgeWebClient

M2M_TOKEN_ENV = "BRIDGE_M2M_TOKEN"
ADMIN_SESSION_TOKEN_ENV = "BRIDGE_ADMIN_SESSION_TOKEN"
ADMIN_CSRF_TOKEN_ENV = "BRIDGE_ADMIN_CSRF_TOKEN"
TARGET_PHONE_ENV = "BRIDGE_OTP_TARGET_PHONE"
CONTACT_NAME_ENV = "BRIDGE_OTP_CONTACT_NAME"
OTP_MESSAGE_ENV = "BRIDGE_OTP_MESSAGE_TEXT"
AI_MESSAGE_ENV = "BRIDGE_AI_MESSAGE_TEXT"

READ_ONLY_ACTIONS = frozenset({"preflight", "otp-status", "ai-probe"})
IMPACTFUL_ACTIONS = frozenset({"reserve", "otp-dispatch", "ai-chat"})

PLAN = {
    "runner": "web_client_live_runner",
    "mode": "OFFLINE_PLAN",
    "description": "Default-off acceptance runner for Web Client, OTP Delivery Pipeline, and AI Gateway.",
    "input_policy": {
        "tokens": "BRIDGE_M2M_TOKEN / BRIDGE_ADMIN_SESSION_TOKEN + BRIDGE_ADMIN_CSRF_TOKEN env or hidden prompt; never argv.",
        "targets": "Phone/message/contact/AI text via BRIDGE_OTP_TARGET_PHONE / BRIDGE_OTP_MESSAGE_TEXT / BRIDGE_OTP_CONTACT_NAME / BRIDGE_AI_MESSAGE_TEXT env or hidden prompt; never argv, logs, or tracked files.",
        "confirmation": "Impactful actions (reserve, otp-dispatch, ai-chat) require confirmation of the same operation: interactive yes-prompt naming the action, or --confirm <action> in non-interactive mode.",
    },
    "supported_actions": [
        {
            "action": "preflight",
            "provider": "eitaa / bale",
            "capability": "read_only",
            "safety_limit": "Rate limited to 60 req/min per credential",
            "required_inputs": ["origin", "m2m_token"],
        },
        {
            "action": "reserve",
            "provider": "coordinator",
            "capability": "durable_capacity_reservation",
            "safety_limit": "TTL bounded (default 300s), HMAC binding only",
            "required_inputs": ["origin", "m2m_token", "target_phone (explicit, no default)"],
        },
        {
            "action": "otp-dispatch",
            "provider": "eitaa / bale",
            "capability": "contact_resolve_import_send",
            "safety_limit": "Max 1 message per run, stable idempotency key",
            "required_inputs": [
                "origin",
                "m2m_token",
                "target_phone (explicit, no default)",
                "message_text (explicit, no default)",
                "reservation_id",
                "idempotency_key",
            ],
        },
        {
            "action": "otp-status",
            "provider": "coordinator",
            "capability": "status_poll",
            "safety_limit": "Read-only, max 10 polls with backoff",
            "required_inputs": ["origin", "m2m_token", "delivery_id"],
        },
        {
            "action": "ai-probe",
            "provider": "ai_gateway",
            "capability": "admin_synthetic_probe",
            "safety_limit": "Zero user context, synthetic ping only",
            "required_inputs": [
                "origin",
                "admin_session_token + admin_csrf_token (real admin route auth; an M2M Bearer is never admin)",
            ],
        },
        {
            "action": "ai-chat",
            "provider": "ai_gateway",
            "capability": "scrubbed_egress_chat",
            "safety_limit": "Server-side egress gate, user pseudonymization, zero PII; raw model response is never printed",
            "required_inputs": ["origin", "m2m_token", "web_user_id", "session_id", "message_text (explicit)", "message_id"],
        },
    ],
    "guarantees": [
        "Zero raw phone numbers, OTP codes, message texts, or AI responses printed in output or written to disk.",
        "Zero automatic retry on uncertain delivery outcomes.",
        "Strict loopback endpoint enforcement (127.0.0.1:PORT).",
        "warm_verified only with an authenticated session witness and a real connect count; preflight/reserve success alone never proves warmth.",
    ],
}


def validate_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or not parsed.port
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("A loopback origin (http://127.0.0.1:PORT) is strictly required.")
    return value.rstrip("/")


def execute_dry_plan() -> int:
    print(json.dumps(PLAN, indent=2, ensure_ascii=False))
    return 0


class _ConnectCountingBackend(httpcore.AsyncNetworkBackend):
    """Counts real TCP connects so warm metadata is measured, not asserted."""

    def __init__(self) -> None:
        self._inner = _default_network_backend()
        self.connects = 0

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connects += 1
        return await self._inner.connect_tcp(
            host, port, timeout=timeout, local_address=local_address, socket_options=socket_options
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        return await self._inner.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    async def sleep(self, seconds):
        await self._inner.sleep(seconds)


def _default_network_backend() -> httpcore.AsyncNetworkBackend:
    from httpcore._backends.auto import AutoBackend

    return AutoBackend()


class _CountingTransport(httpx.AsyncHTTPTransport):
    """Shared transport: counts real connects (via httpcore backend) and
    every HTTP round trip performed during the run."""

    def __init__(self, telemetry: "_RunTelemetry") -> None:
        super().__init__()
        self._telemetry = telemetry
        if telemetry.backend is not None:
            self._pool = httpcore.AsyncConnectionPool(network_backend=telemetry.backend)

    async def handle_async_request(self, request):
        self._telemetry.round_trips += 1
        return await super().handle_async_request(request)


class _RunTelemetry:
    """Transport-level connect/round-trip counters shared by one runner run."""

    def __init__(self) -> None:
        self.round_trips = 0
        self.backend: _ConnectCountingBackend | None = None
        try:
            self.backend = _ConnectCountingBackend()
        except Exception:
            self.backend = None

    def build_transport(self) -> httpx.AsyncHTTPTransport:
        return _CountingTransport(self)

    @property
    def connects(self) -> int | None:
        return self.backend.connects if self.backend is not None else None

    @property
    def connects_observed(self) -> bool:
        return self.backend is not None

    def witness(self, *, session_ok: bool, session_kind: str, session_reason: str) -> dict:
        connects = self.connects
        return {
            "session_ok": session_ok,
            "session_kind": session_kind,
            "session_reason": session_reason,
            "connects": connects,
            "connects_observed": self.connects_observed,
            "round_trips": self.round_trips,
        }

    @staticmethod
    def warm_verified(witness: dict) -> bool:
        return bool(
            witness["session_ok"]
            and witness["connects_observed"]
            and isinstance(witness["connects"], int)
            and witness["connects"] >= 1
        )


def _json_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-Id": str(uuid.uuid4()),
    }


def _admin_cookie_headers(session_token: str, csrf_token: str | None) -> dict[str, str]:
    headers = {
        "Cookie": f"eitaa_bridge_app_session={session_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-Id": str(uuid.uuid4()),
    }
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers


async def _m2m_session_witness(endpoint: str, token: str, telemetry: _RunTelemetry) -> tuple[bool, str]:
    """Read-only, authenticated probe proving the credential session is alive.

    This witness is deliberately independent of preflight/reserve results: it
    exercises the authenticated session on a read-only surface instead of
    inferring warmth from a successful business response.
    """
    transport = telemetry.build_transport()
    try:
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            resp = await client.get(f"{endpoint}/api/v2/m2m/agent/health", headers=_json_headers(token))
    except Exception:
        return False, "session_probe_failed"
    if resp.status_code in (401, 403):
        return False, "session_rejected"
    data = resp.json() if resp.content else {}
    if resp.status_code == 200 and data.get("ok") is True:
        return True, "authenticated_session_alive"
    return False, "session_unexpected_response"


async def _admin_session_witness(endpoint: str, session_token: str, telemetry: _RunTelemetry) -> tuple[bool, str]:
    """Prove a live ADMIN app session (cookie) before any admin route call.

    An M2M service Bearer is never admin: the witness inspects the real
    app-session principal and requires the admin global role.
    """
    transport = telemetry.build_transport()
    try:
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            resp = await client.get(
                f"{endpoint}/api/v2/app-auth/me",
                headers=_admin_cookie_headers(session_token, None),
            )
    except Exception:
        return False, "session_probe_failed"
    data = resp.json() if resp.content else {}
    if data.get("authenticated") is False:
        # The anonymous /me variant: no usable session was presented.
        return False, "session_rejected"
    if resp.status_code == 200:
        principal = data.get("principal") or {}
        if principal.get("global_role") == "admin":
            return True, "admin_session_alive"
        return False, "admin_role_required"
    if resp.status_code in (401, 403):
        return False, "session_rejected"
    return False, "session_unexpected_response"


def _safe_probe_fields(probe: dict) -> dict:
    allowed = ("ok", "reachable", "status_code", "error", "latency_ms")
    return {key: probe.get(key) for key in allowed if key in probe}


async def _run_live_action(endpoint: str, args: argparse.Namespace, token: str, admin_csrf_token: str = "") -> tuple[int, dict]:
    telemetry = _RunTelemetry()
    transport = telemetry.build_transport()
    client = BridgeWebClient(
        base_url=endpoint,
        bearer_token=token if args.action != "ai-probe" else "",
        sender_profile_id=args.sender_profile_id or None,
        transport=transport,
    )
    action = args.action

    try:
        if action == "ai-probe":
            session_token = token
            csrf_token = admin_csrf_token
            witness_ok, witness_reason = await _admin_session_witness(endpoint, session_token, telemetry)
            if not witness_ok:
                return 1, {
                    "ok": False,
                    "action": action,
                    "error": witness_reason,
                    "detail": (
                        "ai-probe requires a real admin app session (cookie + CSRF); "
                        "an M2M service Bearer is not admin authorization."
                    ),
                    "warm_verified": False,
                    "warm_witness": telemetry.witness(
                        session_ok=False, session_kind="admin_session", session_reason=witness_reason
                    ),
                }
            async with httpx.AsyncClient(transport=transport, timeout=10.0) as http_c:
                probe_url = f"{endpoint}/api/v2/admin/ai-connection/probe"
                resp = await http_c.post(probe_url, json={}, headers=_admin_cookie_headers(session_token, csrf_token))
                data = resp.json() if resp.content else {}
            probe = data.get("probe") if isinstance(data.get("probe"), dict) else {}
            is_ok = bool(resp.status_code == 200 and data.get("ok", False))
            witness = telemetry.witness(
                session_ok=True, session_kind="admin_session", session_reason="admin_session_alive"
            )
            return (0 if is_ok else 1), {
                "ok": is_ok,
                "action": action,
                "status_code": resp.status_code,
                "probe_result": _safe_probe_fields(probe),
                "warm_verified": _RunTelemetry.warm_verified(witness),
                "warm_witness": witness,
            }

        if action in READ_ONLY_ACTIONS or action in IMPACTFUL_ACTIONS:
            witness_ok, witness_reason = await _m2m_session_witness(endpoint, token, telemetry)
            witness = telemetry.witness(
                session_ok=witness_ok,
                session_kind="m2m_credential",
                session_reason=witness_reason,
            )
            warm_verified = _RunTelemetry.warm_verified(witness)
            if not witness_ok:
                return 1, {
                    "ok": False,
                    "action": action,
                    "error": witness_reason,
                    "warm_verified": False,
                    "warm_witness": witness,
                }
        else:
            witness = {"session_ok": False, "session_kind": "none", "session_reason": "no_witness",
                       "connects": telemetry.connects, "connects_observed": telemetry.connects_observed,
                       "round_trips": telemetry.round_trips}
            warm_verified = False

        if action == "preflight":
            res = await client.preflight(
                intent=args.intent,
                recipient_kind=args.recipient_kind,
                sender_profile_id=args.sender_profile_id or None,
            )
            return (0 if res.ok else 1), {
                "ok": res.ok,
                "action": "preflight",
                "status": res.status,
                "retry_after_seconds": res.retry_after_seconds,
                "message": res.message,
                "warm_verified": warm_verified,
                "warm_witness": witness,
            }

        elif action == "reserve":
            idemp = args.idempotency_key or f"idemp-res-{uuid.uuid4().hex[:16]}"
            res = await client.reserve_capacity(
                phone=args.target_phone,
                idempotency_key=idemp,
                intent=args.intent,
                ttl_seconds=args.ttl_seconds,
                sender_profile_id=args.sender_profile_id or None,
            )
            return (0 if res.ok else 1), {
                "ok": res.ok,
                "action": "reserve",
                "reservation_id": res.reservation_id,
                "expires_at": res.expires_at,
                "ttl_seconds": res.ttl_seconds,
                "warm_verified": warm_verified,
                "warm_witness": witness,
                "error": res.error,
            }

        elif action == "otp-dispatch":
            res_id = args.reservation_id
            if not res_id:
                # Auto-reserve capacity first
                res_step = await client.reserve_capacity(
                    phone=args.target_phone,
                    idempotency_key=f"idemp-res-{uuid.uuid4().hex[:16]}",
                    intent=args.intent,
                    ttl_seconds=args.ttl_seconds,
                    sender_profile_id=args.sender_profile_id or None,
                )
                if not res_step.ok:
                    return 1, {
                        "ok": False,
                        "action": "otp-dispatch",
                        "stage": "reservation",
                        "error": res_step.error,
                        "warm_verified": warm_verified,
                        "warm_witness": witness,
                    }
                res_id = str(res_step.reservation_id)

            idemp_send = args.idempotency_key or f"idemp-send-{uuid.uuid4().hex[:16]}"
            disp = await client.dispatch_otp(
                reservation_id=res_id,
                phone=args.target_phone,
                message_text=args.target_message,
                display_name=args.contact_name or None,
                idempotency_key=idemp_send,
            )
            return (0 if disp.ok else 1), {
                "ok": disp.ok,
                "action": "otp-dispatch",
                "delivery_id": disp.delivery_id,
                "stage": disp.stage,
                "status": disp.status,
                "is_replayed": disp.is_replayed,
                "warm_verified": warm_verified,
                "warm_witness": witness,
                "error": disp.error,
            }

        elif action == "otp-status":
            if not args.delivery_id:
                return 1, {
                    "ok": False,
                    "action": "otp-status",
                    "error": "missing_delivery_id",
                    "detail": "--delivery-id is required for otp-status.",
                    "warm_verified": warm_verified,
                    "warm_witness": witness,
                }
            stat = await client.get_delivery_status(args.delivery_id)
            return (0 if stat.ok else 1), {
                "ok": stat.ok,
                "action": "otp-status",
                "delivery_id": stat.delivery_id,
                "stage": stat.stage,
                "status": stat.status,
                "is_terminal": stat.is_terminal,
                "is_success": stat.is_success,
                "warm_verified": warm_verified,
                "warm_witness": witness,
                "error": stat.error,
            }

        elif action == "ai-chat":
            msg_id = args.message_id or f"msg-{uuid.uuid4().hex[:16]}"
            chat_res = await client.chat(
                web_user_id=args.web_user_id,
                session_id=args.session_id,
                message=args.target_message,
                message_id=msg_id,
            )
            # The raw model response is intentionally never printed; only its
            # size and scrubbing metadata leave the process boundary.
            return (0 if chat_res.ok else 1), {
                "ok": chat_res.ok,
                "action": "ai-chat",
                "response_length": len(chat_res.response or ""),
                "session_id": chat_res.session_id,
                "is_test_response": chat_res.is_test_response,
                "replayed": chat_res.replayed,
                "warm_verified": warm_verified,
                "warm_witness": witness,
                "error": chat_res.error,
            }

        else:
            return 1, {
                "ok": False,
                "action": action,
                "error": "unsupported_action",
                "warm_verified": False,
                "warm_witness": witness,
            }
    except Exception:
        # Exception text may embed URLs, credentials, or provider payloads:
        # only a bounded safe code and generic guidance leave the runner.
        return 1, {
            "ok": False,
            "action": action,
            "error": "transport_error",
            "recovery_guidance": "Check bridge coordinator logs and verify loopback connection.",
            "warm_verified": False,
            "warm_witness": telemetry.witness(
                session_ok=False, session_kind="unknown", session_reason="transport_error"
            ),
        }
    finally:
        await client.aclose()


def _resolve_secret(env_names: list[str], prompt: str) -> str:
    for name in env_names:
        value = os.environ.get(name, "")
        if value:
            return value
    if sys.stdin.isatty():
        try:
            value = getpass(prompt).strip()
        except Exception:
            # A broken/absent console must fail closed to an empty secret,
            # never crash or echo the prompt answer.
            return ""
        if value:
            return value
    return ""


def _resolve_private_text(env_names: list[str], prompt: str) -> str:
    for name in env_names:
        value = os.environ.get(name, "")
        if value:
            return value
    if sys.stdin.isatty():
        try:
            value = getpass(prompt).strip()
        except Exception:
            # Same fail-closed rule as secrets: a failed hidden read yields an
            # empty target, which the required-field checks reject.
            return ""
        if value:
            return value
    return ""


def _fail(payload: dict) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1


def main(argv: list[str] | None = None) -> int:
    # allow_abbrev=False: exact flags only — a sensitive-looking prefix like
    # ``--message`` must never silently resolve to ``--message-id``.
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--dry-plan", action="store_true", help="Print dry-plan execution matrix and exit safely.")
    parser.add_argument("--allow-live", action="store_true", help="Opt-in flag for owner-approved live execution.")
    parser.add_argument("--origin", default="", help="Loopback server origin (e.g. http://127.0.0.1:8000)")
    parser.add_argument(
        "--action",
        choices=["dry-plan", "preflight", "reserve", "otp-dispatch", "otp-status", "ai-probe", "ai-chat"],
        default="dry-plan",
        help="Action to execute.",
    )
    parser.add_argument(
        "--confirm",
        nargs="?",
        const="*",
        default=None,
        metavar="ACTION",
        help="Operator confirmation. Impactful actions require confirmation of the SAME operation: --confirm otp-dispatch. A bare --confirm only authorizes read-only actions.",
    )
    parser.add_argument("--sender-profile-id", default="", help="Optional sender profile id.")
    parser.add_argument("--intent", default="otp", choices=["otp", "notification"], help="Sender intent.")
    parser.add_argument("--recipient-kind", default="new", choices=["new", "existing"], help="Recipient kind for preflight.")
    parser.add_argument("--reservation-id", default="", help="Reservation ID.")
    parser.add_argument("--delivery-id", default="", help="Delivery ID.")
    parser.add_argument("--idempotency-key", default="", help="Idempotency key.")
    parser.add_argument("--ttl-seconds", type=int, default=120, help="Reservation TTL in seconds.")
    parser.add_argument("--web-user-id", default="usr_acceptance", help="Web user id for AI chat.")
    parser.add_argument("--session-id", default="ses_acceptance", help="Session id for AI chat.")
    parser.add_argument("--message-id", default="", help="Message id for AI chat.")

    args = parser.parse_args(argv)

    if args.dry_plan or not args.allow_live or args.action == "dry-plan":
        return execute_dry_plan()

    # Live execution requested: validate origin
    try:
        endpoint = validate_origin(args.origin)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": "invalid_origin", "detail": str(exc)}))
        return 2

    # Explicit target resolution BEFORE confirmation (fail-closed, no defaults):
    # impactful operations must name their target, never reuse a built-in one.
    args.target_phone = ""
    args.target_message = ""
    args.contact_name = ""
    if args.action in {"reserve", "otp-dispatch"}:
        args.target_phone = _resolve_private_text(
            [TARGET_PHONE_ENV],
            "Target phone (E.164, hidden input): ",
        )
        if not args.target_phone:
            return _fail({
                "ok": False,
                "error": "dispatch_target_required",
                "detail": (
                    "An explicit target is required: set BRIDGE_OTP_TARGET_PHONE "
                    "or run interactively. Default or argv targets are not accepted."
                ),
                "action": args.action,
            })
    if args.action == "otp-dispatch":
        args.target_message = _resolve_private_text(
            [OTP_MESSAGE_ENV],
            "Private message text (hidden input): ",
        )
        if not args.target_message:
            return _fail({
                "ok": False,
                "error": "dispatch_message_required",
                "detail": "An explicit private message is required: set BRIDGE_OTP_MESSAGE_TEXT or run interactively.",
                "action": args.action,
            })
        args.contact_name = _resolve_private_text(
            [CONTACT_NAME_ENV],
            "Contact display name (optional, hidden input): ",
        )
    if args.action == "ai-chat":
        args.target_message = _resolve_private_text(
            [AI_MESSAGE_ENV],
            "Private AI message text (hidden input): ",
        )
        if not args.target_message:
            return _fail({
                "ok": False,
                "error": "dispatch_message_required",
                "detail": "An explicit private message is required: set BRIDGE_AI_MESSAGE_TEXT or run interactively.",
                "action": args.action,
            })

    # Operator Confirmation Check — confirmation must name the SAME operation.
    # Read-only actions may be confirmed with a bare --confirm; impactful
    # actions (reserve, otp-dispatch, ai-chat) require --confirm <action> in
    # non-interactive mode, or an interactive yes on a prompt naming the action
    # (a bare --confirm alone never authorizes an impactful action silently).
    def _interactive_confirm() -> bool:
        try:
            ans = input(f"Confirm execution of live action '{args.action}' on {endpoint}? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return ans in ("yes", "y")

    if not args.confirm:
        if sys.stdin.isatty():
            if not _interactive_confirm():
                return _fail({
                    "ok": False,
                    "status": "aborted",
                    "reason": "operator_confirmation_rejected",
                    "action": args.action,
                })
        else:
            return _fail({
                "ok": False,
                "status": "aborted",
                "reason": "operator_confirmation_required",
                "detail": "Action requires interactive operator confirmation or explicit --confirm <action> flag.",
                "action": args.action,
            })
    elif args.confirm != "*" and args.confirm != args.action:
        return _fail({
            "ok": False,
            "status": "aborted",
            "reason": "same_operation_confirmation_required",
            "detail": f"--confirm named '{args.confirm}' but the requested action is '{args.action}'.",
            "action": args.action,
        })
    elif args.confirm == "*" and args.action in IMPACTFUL_ACTIONS:
        if sys.stdin.isatty():
            if not _interactive_confirm():
                return _fail({
                    "ok": False,
                    "status": "aborted",
                    "reason": "operator_confirmation_rejected",
                    "action": args.action,
                })
        else:
            return _fail({
                "ok": False,
                "status": "aborted",
                "reason": "same_operation_confirmation_required",
                "detail": f"Impactful action '{args.action}' requires --confirm {args.action} in non-interactive mode.",
                "action": args.action,
            })

    # Token Resolution: environment (secure settings) or hidden prompt; argv
    # never carries credentials.
    admin_csrf_token = ""
    if args.action == "ai-probe":
        token = _resolve_secret(
            [ADMIN_SESSION_TOKEN_ENV],
            "Admin app session token (hidden input): ",
        )
        admin_csrf_token = _resolve_secret(
            [ADMIN_CSRF_TOKEN_ENV],
            "Admin CSRF token (hidden input): ",
        )
        if not admin_csrf_token:
            return _fail({
                "ok": False,
                "error": "missing_csrf_token",
                "detail": "Admin routes require the X-CSRF-Token header for POST (probe).",
                "action": args.action,
            })
    else:
        token = _resolve_secret(
            [M2M_TOKEN_ENV],
            "M2M Bearer token (hidden input): ",
        )
    if not token:
        return _fail({
            "ok": False,
            "error": "missing_token",
            "detail": "Bearer token is required for live execution.",
            "action": args.action,
        })

    # Execute action via real HTTP loopback
    exit_code, result = asyncio.run(_run_live_action(endpoint, args, token, admin_csrf_token))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

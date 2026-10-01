"""Server-Side AI Data Policy & Egress Gate (P6).

Enforces strict, multi-level egress control on user data entering external AI models:
- 4 explicit levels: disabled, current_message, limited_history, approved_context.
- No full_database, unrestricted, or implicit bypass levels.
- Zero raw phone numbers, OTP codes, bearer tokens, or session secrets in outbound prompts.
- Pseudonymized user identities per-service using keyed HMAC (no raw web_user_id).
- Fail-closed enforcement on unauthorized, missing, or invalid policies.
- Request context snapshots ensuring in-flight policy changes do not corrupt active turns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import sqlite3
from typing import Any, Callable

from ...errors import BridgeError

VALID_POLICY_LEVELS = frozenset({
    "disabled",
    "current_message",
    "limited_history",
    "approved_context",
})

_PHONE_PATTERN = re.compile(r"(?:\+?98|0)?9\d{9}\b|\+?[1-9]\d{7,14}\b")
_OTP_PATTERN = re.compile(
    r"(?i)(?:code|otp|رمز|کد|تأیید|تایید)[\s\w\u0600-\u06FF]{0,20}[:\s=]+\s*([0-9]{4,8})\b"
)
_SECRET_PATTERN = re.compile(r"(?i)(?:Bearer|token|secret|password|key)\s+[\w\-._~+/]+=*")
_SALT_PSEUDONYM = b"eitaa-bridge/ai-egress/pseudonym/v1"


class AiDataPolicyError(BridgeError):
    component = "ai_data_policy"
    code = "ai_data_policy_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        safe_context: dict[str, Any] | None = None,
        debug_file: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message, safe_context=safe_context, debug_file=debug_file, code=code)
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class AiDataPolicyRecord:
    service_id: str
    policy_level: str
    max_history_turns: int
    allowed_context_types: tuple[str, ...]
    revision: int
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "policy_level": self.policy_level,
            "max_history_turns": self.max_history_turns,
            "allowed_context_types": list(self.allowed_context_types),
            "revision": self.revision,
            "updated_at": self.updated_at,
        }


def sanitize_text(text: str) -> str:
    """Scrub raw phone numbers, OTP codes, and credential tokens from outbound text."""
    if not text:
        return ""
    scrubbed = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    scrubbed = _SECRET_PATTERN.sub("[REDACTED_SECRET]", scrubbed)
    scrubbed = _OTP_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED_OTP]"), scrubbed)
    return scrubbed


def pseudonymize_user_id(service_name: str, web_user_id: str) -> str:
    """Derive a stable, service-scoped pseudonym from web_user_id without exposing raw ID."""
    raw = f"{service_name}:{web_user_id}".encode("utf-8")
    return "usr_" + hmac.new(_SALT_PSEUDONYM, raw, hashlib.sha256).hexdigest()[:24]


class AiDataPolicyStore:
    """Persistent store for per-service AI data egress policies."""

    def __init__(
        self,
        database: Any,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._db = database
        self._clock = clock or _now_iso
        self._init_schema()

    def _init_schema(self) -> None:
        with self._db._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS service_ai_data_policies (
                    service_id TEXT PRIMARY KEY,
                    policy_level TEXT NOT NULL CHECK(policy_level IN ('disabled','current_message','limited_history','approved_context')),
                    max_history_turns INTEGER NOT NULL DEFAULT 5 CHECK(max_history_turns BETWEEN 0 AND 50),
                    allowed_context_types TEXT NOT NULL DEFAULT '[]',
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.commit()

    def get_policy(self, service_id: str) -> AiDataPolicyRecord:
        """Fetch policy for service. If unconfigured, returns default disabled policy (fail-closed)."""
        with self._db._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM service_ai_data_policies WHERE service_id = ?", (service_id,))
            row = cursor.fetchone()
            if not row:
                return AiDataPolicyRecord(
                    service_id=service_id,
                    policy_level="disabled",
                    max_history_turns=0,
                    allowed_context_types=(),
                    revision=0,
                    updated_at=self._clock(),
                )

            try:
                allowed_ctx = tuple(json.loads(str(row["allowed_context_types"])))
            except Exception:
                allowed_ctx = ()

            return AiDataPolicyRecord(
                service_id=str(row["service_id"]),
                policy_level=str(row["policy_level"]),
                max_history_turns=int(row["max_history_turns"]),
                allowed_context_types=allowed_ctx,
                revision=int(row["revision"]),
                updated_at=str(row["updated_at"]),
            )

    def set_policy(
        self,
        *,
        service_id: str,
        policy_level: str,
        max_history_turns: int = 5,
        allowed_context_types: list[str] | tuple[str, ...] | None = None,
        expected_revision: int | None = None,
    ) -> AiDataPolicyRecord:
        """Create or update policy for a service with optimistic locking."""
        clean_service = str(service_id or "").strip()
        if not clean_service:
            raise AiDataPolicyError("Service ID cannot be empty.", code="service_id_empty", status_code=400)

        clean_level = str(policy_level or "").strip().lower()
        if clean_level not in VALID_POLICY_LEVELS:
            raise AiDataPolicyError(
                f"Invalid policy level '{clean_level}'. Must be one of: {sorted(VALID_POLICY_LEVELS)}",
                code="ai_policy_level_invalid",
                status_code=400,
            )

        if not (0 <= max_history_turns <= 50):
            raise AiDataPolicyError(
                "max_history_turns must be between 0 and 50.",
                code="ai_max_history_invalid",
                status_code=400,
            )

        ctx_types = list(allowed_context_types or [])
        encoded_ctx = json.dumps(ctx_types)
        now_str = self._clock()

        with self._db._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM service_ai_data_policies WHERE service_id = ?", (clean_service,))
            row = cursor.fetchone()

            if row:
                current_rev = int(row["revision"])
                if expected_revision is not None and expected_revision != current_rev:
                    raise AiDataPolicyError(
                        f"Stale revision: expected {expected_revision}, current {current_rev}",
                        code="stale_revision",
                        status_code=409,
                    )
                new_rev = current_rev + 1
                cursor.execute(
                    """
                    UPDATE service_ai_data_policies
                    SET policy_level = ?,
                        max_history_turns = ?,
                        allowed_context_types = ?,
                        revision = ?,
                        updated_at = ?
                    WHERE service_id = ?
                    """,
                    (clean_level, max_history_turns, encoded_ctx, new_rev, now_str, clean_service),
                )
            else:
                if expected_revision is not None and expected_revision != 0:
                    raise AiDataPolicyError(
                        f"Stale revision: expected {expected_revision}, current 0 (new policy)",
                        code="stale_revision",
                        status_code=409,
                    )
                new_rev = 1
                cursor.execute(
                    """
                    INSERT INTO service_ai_data_policies(
                        service_id, policy_level, max_history_turns, allowed_context_types, revision, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (clean_service, clean_level, max_history_turns, encoded_ctx, new_rev, now_str),
                )

            connection.commit()
            return AiDataPolicyRecord(
                service_id=clean_service,
                policy_level=clean_level,
                max_history_turns=max_history_turns,
                allowed_context_types=tuple(ctx_types),
                revision=new_rev,
                updated_at=now_str,
            )


@dataclass(frozen=True, slots=True)
class OutboundEgressPayload:
    pseudonym_user_id: str
    message: str
    history: list[dict[str, str]]
    approved_context: list[dict[str, Any]]
    policy_revision: int


def build_outbound_egress(
    policy: AiDataPolicyRecord,
    service_name: str,
    web_user_id: str,
    raw_message: str,
    raw_history: list[dict[str, str]],
    raw_additional_context: list[dict[str, Any]] | None = None,
) -> OutboundEgressPayload:
    """Server-side gate: transforms user request into sanitized outbound egress payload.

    Raises BridgeError if policy is disabled or unauthorized.
    """
    if policy.policy_level == "disabled":
        raise AiDataPolicyError(
            "AI chat is disabled for this service by server-side policy.",
            code="ai_policy_disabled",
            status_code=403,
        )

    # 1. Pseudonymize user ID
    user_pseudonym = pseudonymize_user_id(service_name, web_user_id)

    # 2. Sanitize user message
    clean_message = sanitize_text(str(raw_message or ""))

    # 3. Filter history
    clean_history: list[dict[str, str]] = []
    if policy.policy_level in ("limited_history", "approved_context"):
        turns = policy.max_history_turns
        if turns > 0 and raw_history:
            selected_history = raw_history[-turns:]
            for item in selected_history:
                clean_history.append({
                    "role": str(item.get("role") or "user"),
                    "content": sanitize_text(str(item.get("content") or "")),
                })

    # 4. Filter additional context
    clean_context: list[dict[str, Any]] = []
    if policy.policy_level == "approved_context" and raw_additional_context:
        allowed = set(policy.allowed_context_types)
        for item in raw_additional_context:
            c_type = str(item.get("type") or "")
            if c_type in allowed:
                c_data = sanitize_text(str(item.get("content") or ""))
                clean_context.append({"type": c_type, "content": c_data})

    return OutboundEgressPayload(
        pseudonym_user_id=user_pseudonym,
        message=clean_message,
        history=clean_history,
        approved_context=clean_context,
        policy_revision=policy.revision,
    )

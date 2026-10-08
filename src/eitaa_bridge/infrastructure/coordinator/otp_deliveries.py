"""Durable, stage-aware OTP delivery storage and pipeline tracking (P4).

Implements the persistent delivery pipeline for one-time passcodes and
critical notices where recipient resolution, contact import (if needed),
and message dispatch form a traceable, auditable, crash-resilient flow.

Privacy guarantees:
- Raw phone numbers are NEVER stored in this table. Recipient binding is
  an HMAC-SHA256 under the server identity key.
- OTP codes and plain message bodies are NEVER persisted in this table,
  audit logs, or receipts.
- Status and readback endpoints are strictly owner-scoped and return only
  stage, state, timing, and insensitive references.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import sqlite3
from typing import Any, Callable
from uuid import uuid4

from ...errors import BridgeError

_DELIVERY_BINDING_DOMAIN = b"eitaa-bridge/otp-delivery/binding/v1"
_DELIVERY_FINGERPRINT_DOMAIN = b"eitaa-bridge/otp-delivery/fingerprint/v1"

VALID_STAGES = frozenset({
    "admitted",
    "resolving",
    "importing_contact",
    "sending_message",
    "completed",
    "uncertain",
})

VALID_STATES = frozenset({
    "pending",
    "running",
    "accepted",
    "rejected",
    "uncertain",
    "expired",
})


class OtpDeliveryError(BridgeError):
    component = "otp_deliveries"
    code = "otp_delivery_error"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class OtpDeliveryRecord:
    id: str
    service_credential_id: str
    reservation_id: str
    messenger_account_id: str
    provider: str
    intent: str
    idempotency_key: str
    request_fingerprint: str
    challenge_ref: str
    recipient_binding: str
    stage: str
    state: str
    contact_status: str | None
    send_status: str | None
    safe_reason_code: str | None
    provider_message_id: str | None
    retryable: bool
    created_at: str
    updated_at: str
    completed_at: str | None
    expires_at: str


def _row_to_record(row: sqlite3.Row) -> OtpDeliveryRecord:
    return OtpDeliveryRecord(
        id=str(row["id"]),
        service_credential_id=str(row["service_credential_id"]),
        reservation_id=str(row["reservation_id"]),
        messenger_account_id=str(row["messenger_account_id"]),
        provider=str(row["provider"]),
        intent=str(row["intent"]),
        idempotency_key=str(row["idempotency_key"]),
        request_fingerprint=str(row["request_fingerprint"]),
        challenge_ref=str(row["challenge_ref"]),
        recipient_binding=str(row["recipient_binding"]),
        stage=str(row["stage"]),
        state=str(row["state"]),
        contact_status=str(row["contact_status"]) if row["contact_status"] is not None else None,
        send_status=str(row["send_status"]) if row["send_status"] is not None else None,
        safe_reason_code=str(row["safe_reason_code"]) if row["safe_reason_code"] is not None else None,
        provider_message_id=str(row["provider_message_id"]) if row["provider_message_id"] is not None else None,
        retryable=bool(row["retryable"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
        expires_at=str(row["expires_at"]),
    )


class ServiceOtpDeliveryStore:
    """Persistent storage for stage-aware OTP deliveries."""

    def __init__(
        self,
        database: Any,
        binding_mac: Callable[[bytes], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = database
        self._binding_mac = binding_mac or self._default_binding_mac
        self._clock = clock or _now
        self._init_schema()

    def _default_binding_mac(self, payload: bytes) -> str:
        # Fallback for isolated tests if protector isn't injected
        return hmac.new(b"insecure-default-binding-key", payload, hashlib.sha256).hexdigest()

    def _init_schema(self) -> None:
        with self._db._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS service_otp_deliveries (
                    id TEXT PRIMARY KEY CHECK(length(id) = 36),
                    service_credential_id TEXT NOT NULL,
                    reservation_id TEXT NOT NULL,
                    messenger_account_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    intent TEXT NOT NULL DEFAULT 'otp',
                    idempotency_key TEXT NOT NULL CHECK(length(idempotency_key) BETWEEN 16 AND 128),
                    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
                    challenge_ref TEXT NOT NULL,
                    recipient_binding TEXT NOT NULL,
                    stage TEXT NOT NULL CHECK(stage IN ('admitted','resolving','importing_contact','sending_message','completed','uncertain')),
                    state TEXT NOT NULL CHECK(state IN ('pending','running','accepted','rejected','uncertain','expired')),
                    contact_status TEXT CHECK(contact_status IS NULL OR contact_status IN ('existing','created','failed')),
                    send_status TEXT CHECK(send_status IS NULL OR send_status IN ('pending','accepted','rejected','uncertain','expired')),
                    safe_reason_code TEXT,
                    provider_message_id TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0 CHECK(retryable IN (0,1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    expires_at TEXT NOT NULL,
                    UNIQUE(service_credential_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS idx_otp_deliv_res ON service_otp_deliveries(reservation_id);
                CREATE INDEX IF NOT EXISTS idx_otp_deliv_expires ON service_otp_deliveries(expires_at, state);
                """
            )

    def bind_recipient(
        self,
        *,
        normalized_value: str,
        intent: str = "otp",
        service_id: str = "",
    ) -> str:
        canonical = f"{intent.strip()}:{service_id.strip()}:{normalized_value.strip()}".encode("utf-8")
        payload = _DELIVERY_BINDING_DOMAIN + b"\x00" + canonical
        return self._binding_mac(payload)

    def fingerprint_payload(
        self,
        *,
        idempotency_key: str,
        reservation_id: str,
        recipient_binding: str,
        challenge_ref: str,
        message_digest: str,
    ) -> str:
        data = json.dumps(
            {
                "idempotency_key": idempotency_key,
                "reservation_id": reservation_id,
                "recipient_binding": recipient_binding,
                "challenge_ref": challenge_ref,
                "message_digest": message_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(_DELIVERY_FINGERPRINT_DOMAIN + b"\x00" + data).hexdigest()

    def get_by_id(
        self, delivery_id: str, service_credential_id: str | None = None
    ) -> OtpDeliveryRecord | None:
        with self._db._connect() as connection:
            if service_credential_id is not None:
                row = connection.execute(
                    """
                    SELECT * FROM service_otp_deliveries
                    WHERE id=? AND service_credential_id=?
                    """,
                    (str(delivery_id), str(service_credential_id)),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM service_otp_deliveries WHERE id=?",
                    (str(delivery_id),),
                ).fetchone()
        return _row_to_record(row) if row is not None else None

    def get_by_idempotency_key(
        self, service_credential_id: str, idempotency_key: str
    ) -> OtpDeliveryRecord | None:
        with self._db._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM service_otp_deliveries
                WHERE service_credential_id=? AND idempotency_key=?
                """,
                (str(service_credential_id), str(idempotency_key)),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def admit(
        self,
        *,
        delivery_id: str,
        service_credential_id: str,
        reservation_id: str,
        messenger_account_id: str,
        provider: str,
        intent: str,
        idempotency_key: str,
        request_fingerprint: str,
        challenge_ref: str,
        recipient_binding: str,
        expires_at: str,
    ) -> tuple[OtpDeliveryRecord, bool]:
        """Admit a delivery request into the persistent queue.

        Returns (record, is_fresh). If an entry exists for the same
        idempotency_key:
        - If fingerprint matches -> (existing_record, False)
        - If fingerprint differs -> raises OtpDeliveryError(code='otp_delivery_conflict')
        """
        now = _stamp(self._clock())
        with self._db._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM service_otp_deliveries
                WHERE service_credential_id=? AND idempotency_key=?
                """,
                (str(service_credential_id), str(idempotency_key)),
            ).fetchone()

            if existing is not None:
                record = _row_to_record(existing)
                if record.request_fingerprint != request_fingerprint:
                    connection.execute("ROLLBACK")
                    raise OtpDeliveryError(
                        "Idempotency key reuse with different payload.",
                        code="otp_delivery_conflict",
                        safe_context={"idempotency_key": idempotency_key},
                    )
                connection.execute("COMMIT")
                return record, False

            connection.execute(
                """
                INSERT INTO service_otp_deliveries (
                    id, service_credential_id, reservation_id,
                    messenger_account_id, provider, intent,
                    idempotency_key, request_fingerprint, challenge_ref,
                    recipient_binding, stage, state, contact_status,
                    send_status, safe_reason_code, provider_message_id,
                    retryable, created_at, updated_at, completed_at,
                    expires_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'admitted', 'pending',
                    NULL, 'pending', NULL, NULL, 0, ?, ?, NULL, ?
                )
                """,
                (
                    str(delivery_id),
                    str(service_credential_id),
                    str(reservation_id),
                    str(messenger_account_id),
                    str(provider),
                    str(intent),
                    str(idempotency_key),
                    str(request_fingerprint),
                    str(challenge_ref),
                    str(recipient_binding),
                    now,
                    now,
                    str(expires_at),
                ),
            )
            inserted = connection.execute(
                "SELECT * FROM service_otp_deliveries WHERE id=?",
                (str(delivery_id),),
            ).fetchone()
            connection.execute("COMMIT")
            return _row_to_record(inserted), True

    def update_stage(
        self,
        delivery_id: str,
        *,
        stage: str,
        state: str,
        contact_status: str | None = None,
        send_status: str | None = None,
        safe_reason_code: str | None = None,
        provider_message_id: str | None = None,
        retryable: bool = False,
        completed: bool = False,
    ) -> OtpDeliveryRecord:
        """Advance the delivery stage and record state transition."""
        if stage not in VALID_STAGES:
            raise OtpDeliveryError(f"Invalid delivery stage: {stage}", code="invalid_stage")
        if state not in VALID_STATES:
            raise OtpDeliveryError(f"Invalid delivery state: {state}", code="invalid_state")

        now = _stamp(self._clock())
        completed_at = now if completed else None

        with self._db._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM service_otp_deliveries WHERE id=?",
                (str(delivery_id),),
            ).fetchone()
            if current is None:
                connection.execute("ROLLBACK")
                raise OtpDeliveryError(f"Delivery not found: {delivery_id}", code="otp_delivery_not_found")

            # Preserve prior contact_status or send_status if not explicitly provided
            final_contact = contact_status if contact_status is not None else current["contact_status"]
            final_send = send_status if send_status is not None else current["send_status"]
            final_reason = safe_reason_code if safe_reason_code is not None else current["safe_reason_code"]
            final_msg_id = provider_message_id if provider_message_id is not None else current["provider_message_id"]
            final_completed = completed_at if completed_at is not None else current["completed_at"]

            connection.execute(
                """
                UPDATE service_otp_deliveries SET
                    stage=?, state=?, contact_status=?, send_status=?,
                    safe_reason_code=?, provider_message_id=?, retryable=?,
                    updated_at=?, completed_at=?
                WHERE id=?
                """,
                (
                    str(stage),
                    str(state),
                    final_contact,
                    final_send,
                    final_reason,
                    final_msg_id,
                    1 if retryable else 0,
                    now,
                    final_completed,
                    str(delivery_id),
                ),
            )
            updated = connection.execute(
                "SELECT * FROM service_otp_deliveries WHERE id=?",
                (str(delivery_id),),
            ).fetchone()
            connection.execute("COMMIT")
            return _row_to_record(updated)

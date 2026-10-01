"""Durable, atomic delivery capacity reservations (P3).

A reservation pins a short-lived local capacity slot to one sender profile
and one recipient binding so two requests can take the last slot at the
same time. The reservation makes no provider promise and never guarantees
message delivery: it only fixes local admission accounting.

Durability and atomicity come from the coordinator SQLite database with
``BEGIN IMMEDIATE`` — the capacity decision, the bucket debit and the row
insert are one transaction, and no network/await happens inside it. The
same guarantee is cross-connection and cross-process; it is NOT extended
to the in-memory agent.chat machinery (F-090/F-091 scope stays unchanged).

The recipient binding is an HMAC-SHA256 under the server identity key over
(normalized phone, intent, service) — a bare hash of a phone would be
searchable in reverse, so it is never stored. Raw numbers and OTPs never
enter this table, logs or receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import sqlite3
from typing import Any, Callable
from uuid import uuid4

from ...errors import BridgeError

RESERVATION_OPERATION_SCOPE = "messages.send_text"
RESERVED_INTENTS = ("otp", "notification")

# Abuse limits: one service can never hoard an account's capacity forever.
MAX_OUTSTANDING_PER_CREDENTIAL = 4
MAX_CREATES_PER_WINDOW = 12
CREATE_WINDOW_SECONDS = 60.0
DEFAULT_TTL_SECONDS = 120
MIN_TTL_SECONDS = 30
MAX_TTL_SECONDS = 600
_DEFAULT_CAPACITY = 5
_DEFAULT_REFILL_PER_SECOND = 1.0

_UNAVAILABLE_LIFECYCLE_STATES = frozenset({"archived", "disabled", "quarantined"})
_UNAVAILABLE_PHONE_STATES = frozenset({"archived", "disabled"})

_BINDING_DOMAIN = b"eitaa-bridge/delivery-reservation/binding/v1"
_FINGERPRINT_DOMAIN = b"eitaa-bridge/delivery-reservation/fingerprint/v1"
_IDEMPOTENCY_DOMAIN = b"eitaa-bridge/delivery-reservation/idempotency/v1"


class DeliveryReservationError(BridgeError):
    component = "delivery_reservations"
    code = "delivery_reservation_error"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(timezone.utc)


def _ceil_seconds(milliseconds: int) -> int:
    return max(1, math.ceil(milliseconds / 1000))


@dataclass(frozen=True, slots=True)
class DeliveryReservation:
    id: str
    service_credential_id: str
    intent: str
    provider: str
    messenger_account_id: str
    sender_profile_id: str | None
    sender_profile_revision: int | None
    state: str
    operation_costs: dict[str, Any]
    token_reserved: bool
    token_refunded: bool
    send_started_at: str | None
    operation_id: str | None
    recipient_binding: str
    created_at: str
    updated_at: str
    expires_at: str

    def safe_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "service_credential_id": self.service_credential_id,
            "intent": self.intent,
            "provider": self.provider,
            "messenger_account_id": self.messenger_account_id,
            "state": self.state,
            "operation_costs": self.operation_costs,
            "token_reserved": self.token_reserved,
            "token_refunded": self.token_refunded,
            "send_started": self.send_started_at is not None,
            "operation_id": self.operation_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


def _row_to_reservation(row: sqlite3.Row) -> DeliveryReservation:
    return DeliveryReservation(
        id=str(row["id"]),
        service_credential_id=str(row["service_credential_id"]),
        intent=str(row["intent"]),
        provider=str(row["provider"]),
        messenger_account_id=str(row["messenger_account_id"]),
        sender_profile_id=(
            str(row["sender_profile_id"]) if row["sender_profile_id"] else None
        ),
        sender_profile_revision=(
            int(row["sender_profile_revision"])
            if row["sender_profile_revision"] is not None
            else None
        ),
        state=str(row["state"]),
        operation_costs=json.loads(row["operation_costs"]),
        token_reserved=bool(row["token_reserved"]),
        token_refunded=bool(row["token_refunded"]),
        send_started_at=(
            str(row["send_started_at"]) if row["send_started_at"] else None
        ),
        operation_id=str(row["operation_id"]) if row["operation_id"] else None,
        recipient_binding=str(row["recipient_binding"]) if "recipient_binding" in row.keys() else "",
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        expires_at=str(row["expires_at"]),
    )


class ServiceDeliveryReservationStore:
    """Atomic accounting and lifecycle for delivery reservations."""

    def __init__(
        self,
        database: Any,
        *,
        binding_mac: Callable[[bytes], str],
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._db = database
        self._binding_mac = binding_mac
        self._now = now

    # -- opaque identifiers -------------------------------------------------

    def bind_recipient(
        self, *, normalized_value: str, intent: str, service_id: str
    ) -> str:
        """HMAC binding over the normalized recipient; never reversible-safe.

        A bare hash of a phone number is searchable in reverse, so the
        binding is always keyed by the server identity secret and includes
        the intent and the service.
        """
        payload = (
            intent.strip()
            + "|"
            + service_id.strip()
            + "|"
            + str(normalized_value).strip()
        ).encode("utf-8")
        return self._binding_mac(_BINDING_DOMAIN + b"|" + payload)

    def _idempotency_fingerprint(self, *, idempotency_key: str) -> str:
        """The fingerprint covers ONLY the idempotency key: reusing a key
        with a different payload is detected as a conflict, never as a new
        logical request."""
        payload = str(idempotency_key).strip().encode("utf-8")
        return self._binding_mac(_IDEMPOTENCY_DOMAIN + b"|" + payload)

    def _request_fingerprint(
        self,
        *,
        binding: str,
        idempotency_key: str,
        intent: str,
        account_id: str,
        costs: dict[str, Any],
    ) -> str:
        payload = (
            f"{binding}|{str(idempotency_key).strip()}|{intent.strip()}|"
            f"{account_id.strip()}|{json.dumps(costs, sort_keys=True)}"
        ).encode("utf-8")
        return self._binding_mac(_FINGERPRINT_DOMAIN + b"|" + payload)

    # -- internal helpers ---------------------------------------------------

    def _connect(self):
        return self._db._connect()

    def _account_available(self, connection: sqlite3.Connection, account_id: str) -> bool:
        row = connection.execute(
            """
            SELECT ma.lifecycle_state AS lifecycle_state, pa.status AS phone_status
            FROM messenger_accounts ma
            JOIN phone_accounts pa ON pa.id=ma.phone_account_id
            WHERE ma.id=?
            """,
            (str(account_id),),
        ).fetchone()
        if row is None:
            return False
        if str(row["lifecycle_state"]) in _UNAVAILABLE_LIFECYCLE_STATES:
            return False
        if str(row["phone_status"]) in _UNAVAILABLE_PHONE_STATES:
            return False
        return True

    def _bucket_refill_and_cost(
        self,
        connection: sqlite3.Connection,
        *,
        account_id: str,
        provider: str,
        now: datetime,
        cost: float = 1.0,
    ) -> tuple[sqlite3.Row, float]:
        """Return the refilled bucket row and its available tokens (no debit)."""
        timestamp = _stamp(now)
        connection.execute(
            """
            INSERT INTO account_execution_limits(
                messenger_account_id,provider,operation_scope,capacity,
                refill_per_second,available_tokens,last_refill_at,circuit_state,
                consecutive_failures,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,'closed',0,?,?)
            ON CONFLICT(messenger_account_id,operation_scope) DO NOTHING
            """,
            (
                str(account_id),
                provider,
                RESERVATION_OPERATION_SCOPE,
                _DEFAULT_CAPACITY,
                _DEFAULT_REFILL_PER_SECOND,
                float(_DEFAULT_CAPACITY),
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        row = connection.execute(
            """
            SELECT * FROM account_execution_limits
            WHERE messenger_account_id=? AND operation_scope=?
            """,
            (str(account_id), RESERVATION_OPERATION_SCOPE),
        ).fetchone()
        assert row is not None
        elapsed = max(
            0.0, (now - _parse(str(row["last_refill_at"]))).total_seconds()
        )
        available = min(
            float(row["capacity"]),
            float(row["available_tokens"]) + elapsed * float(row["refill_per_second"]),
        )
        return row, available

    def _expire_due_locked(
        self, connection: sqlite3.Connection, *, now: datetime
    ) -> None:
        """One atomic expiry transition shared by lazy expiry and the janitor.

        Due reserved rows move to ``expired`` and refund their token once —
        the send has certainly not started (consume never happened), which
        is the only case a refund is ever allowed in.
        """
        due = connection.execute(
            """
            SELECT id, messenger_account_id, provider, operation_costs,
                   token_reserved, token_refunded, send_started_at
            FROM service_delivery_reservations
            WHERE state='reserved' AND expires_at <= ?
            """,
            (_stamp(now),),
        ).fetchall()
        timestamp = _stamp(now)
        for row in due:
            connection.execute(
                """
                UPDATE service_delivery_reservations
                SET state='expired', updated_at=?
                WHERE id=? AND state='reserved'
                """,
                (timestamp, str(row["id"])),
            )
            if (
                int(row["token_reserved"]) == 1
                and int(row["token_refunded"]) == 0
                and row["send_started_at"] is None
            ):
                limit_row, available = self._bucket_refill_and_cost(
                    connection,
                    account_id=str(row["messenger_account_id"]),
                    provider=str(row["provider"]),
                    now=now,
                )
                cost = float(json.loads(row["operation_costs"]).get("reserve", 1.0))
                capacity = float(limit_row["capacity"])
                connection.execute(
                    """
                    UPDATE account_execution_limits
                    SET available_tokens=?, last_refill_at=?, updated_at=?
                    WHERE messenger_account_id=? AND operation_scope=?
                    """,
                    (
                        min(capacity, available + cost),
                        _stamp(now),
                        timestamp,
                        str(row["messenger_account_id"]),
                        RESERVATION_OPERATION_SCOPE,
                    ),
                )
                connection.execute(
                    """
                    UPDATE service_delivery_reservations
                    SET token_refunded=1, updated_at=?
                    WHERE id=?
                    """,
                    (timestamp, str(row["id"])),
                )

    def expire_due(self, *, now: datetime | None = None) -> int:
        """Janitor entry point: same atomic transition as lazy expiry."""
        selected_now = now or self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                before = connection.execute(
                    "SELECT COUNT(*) FROM service_delivery_reservations WHERE state='expired'"
                ).fetchone()[0]
                self._expire_due_locked(connection, now=selected_now)
                after = connection.execute(
                    "SELECT COUNT(*) FROM service_delivery_reservations WHERE state='expired'"
                ).fetchone()[0]
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return int(after) - int(before)

    # -- public lifecycle ---------------------------------------------------

    def create(
        self,
        *,
        service_credential_id: str,
        actor_app_user_id: str,
        intent: str,
        provider: str,
        messenger_account_id: str,
        recipient_binding: str,
        idempotency_key: str,
        sender_profile_id: str | None = None,
        sender_profile_revision: int | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        costs: dict[str, Any] | None = None,
    ) -> DeliveryReservation:
        """Accept one capacity slot atomically: decision + debit + insert.

        Retrying the same idempotency key with the same payload returns the
        existing reservation; the same key with a different payload is a
        conflict. A full local bucket answers ``capacity_unavailable`` with
        the refill-based retry time; nothing is inserted then.
        """
        if intent not in RESERVED_INTENTS:
            raise DeliveryReservationError(
                "The delivery reservation intent is invalid.",
                code="delivery_reservation_intent_invalid",
            )
        if not str(recipient_binding).strip():
            raise DeliveryReservationError(
                "The delivery reservation requires a recipient binding.",
                code="delivery_recipient_binding_required",
            )
        if not str(idempotency_key).strip():
            raise DeliveryReservationError(
                "The delivery reservation requires an idempotency key.",
                code="delivery_reservation_idempotency_required",
            )
        selected_costs = costs or {"reserve": 1, "send": 1}
        if float(selected_costs.get("reserve", 1)) != 1.0:
            raise DeliveryReservationError(
                "Only one reserved token per reservation is supported.",
                code="delivery_reservation_cost_invalid",
            )
        ttl = int(ttl_seconds)
        if not MIN_TTL_SECONDS <= ttl <= MAX_TTL_SECONDS:
            raise DeliveryReservationError(
                "The delivery reservation TTL is out of bounds.",
                code="delivery_reservation_ttl_invalid",
            )
        selected_now = self._now()
        expires_at = selected_now + timedelta(seconds=ttl)
        binding = str(recipient_binding).strip()
        idempotency_fingerprint = self._idempotency_fingerprint(
            idempotency_key=idempotency_key
        )
        request_fingerprint = self._request_fingerprint(
            binding=binding,
            idempotency_key=idempotency_key,
            intent=intent,
            account_id=messenger_account_id,
            costs=selected_costs,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                # Terminal reservations never come back; due ones expire here.
                self._expire_due_locked(connection, now=selected_now)

                existing = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations
                    WHERE service_credential_id=? AND idempotency_fingerprint=?
                    """,
                    (str(service_credential_id), idempotency_fingerprint),
                ).fetchone()
                if existing is not None:
                    if str(existing["request_fingerprint"]) == request_fingerprint:
                        connection.commit()
                        return _row_to_reservation(existing)
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The idempotency key was reused with a different payload.",
                        code="delivery_reservation_conflict",
                    )

                outstanding = connection.execute(
                    """
                    SELECT COUNT(*) FROM service_delivery_reservations
                    WHERE service_credential_id=? AND state='reserved' AND expires_at > ?
                    """,
                    (str(service_credential_id), _stamp(selected_now)),
                ).fetchone()[0]
                if int(outstanding) >= MAX_OUTSTANDING_PER_CREDENTIAL:
                    connection.rollback()
                    raise DeliveryReservationError(
                        "Too many outstanding reservations for this service.",
                        code="delivery_reservation_outstanding_limit",
                    )
                window_start = selected_now - timedelta(
                    seconds=CREATE_WINDOW_SECONDS
                )
                created_recently = connection.execute(
                    """
                    SELECT COUNT(*) FROM service_delivery_reservations
                    WHERE service_credential_id=? AND created_at >= ?
                    """,
                    (str(service_credential_id), _stamp(window_start)),
                ).fetchone()[0]
                if int(created_recently) >= MAX_CREATES_PER_WINDOW:
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The reservation creation rate limit is exhausted.",
                        code="delivery_reservation_rate_limited",
                    )

                limit_row, available = self._bucket_refill_and_cost(
                    connection,
                    account_id=messenger_account_id,
                    provider=provider,
                    now=selected_now,
                )
                # An open circuit refuses new reservations like a refused send.
                circuit_state = str(limit_row["circuit_state"])
                if circuit_state == "open":
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The sender account circuit is open.",
                        code="delivery_reservation_circuit_open",
                    )
                cost = float(selected_costs.get("reserve", 1))
                if available < cost:
                    delay_ms = max(
                        1,
                        math.ceil(
                            (cost - available)
                            / float(limit_row["refill_per_second"])
                            * 1000
                        ),
                    )
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The sender account has no free capacity slot.",
                        safe_context={
                            "retry_after_seconds": _ceil_seconds(int(delay_ms)),
                        },
                        code="delivery_reservation_capacity_unavailable",
                    )

                profile_revision = (
                    int(sender_profile_revision)
                    if sender_profile_revision is not None
                    else None
                )
                connection.execute(
                    """
                    UPDATE account_execution_limits
                    SET available_tokens=?, last_refill_at=?, updated_at=?
                    WHERE messenger_account_id=? AND operation_scope=?
                    """,
                    (
                        max(0.0, available - cost),
                        _stamp(selected_now),
                        _stamp(selected_now),
                        str(messenger_account_id),
                        RESERVATION_OPERATION_SCOPE,
                    ),
                )
                reservation_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO service_delivery_reservations(
                        id, service_credential_id, intent, provider,
                        messenger_account_id, sender_profile_id,
                        sender_profile_revision, recipient_binding,
                        idempotency_fingerprint, request_fingerprint,
                        operation_costs, token_reserved, token_refunded,
                        state, created_by_app_user_id, created_at,
                        updated_at, expires_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,0,'reserved',?,?,?,?)
                    """,
                    (
                        reservation_id,
                        str(service_credential_id),
                        intent,
                        str(provider),
                        str(messenger_account_id),
                        sender_profile_id,
                        profile_revision,
                        binding,
                        idempotency_fingerprint,
                        request_fingerprint,
                        json.dumps(selected_costs, sort_keys=True),
                        str(actor_app_user_id),
                        _stamp(selected_now),
                        _stamp(selected_now),
                        _stamp(expires_at),
                    ),
                )
                row = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (reservation_id,),
                ).fetchone()
                connection.commit()
                return _row_to_reservation(row)
            except Exception:
                connection.rollback()
                raise

    def status(
        self, *, reservation_id: str, service_credential_id: str
    ) -> DeliveryReservation | None:
        """Owner-only status read with lazy expiry; foreign ids answer None."""
        selected_now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._expire_due_locked(connection, now=selected_now)
                row = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                if row is None or str(row["service_credential_id"]) != str(
                    service_credential_id
                ):
                    connection.commit()
                    return None
                result = _row_to_reservation(row)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    def cancel(
        self, *, reservation_id: str, service_credential_id: str
    ) -> DeliveryReservation | None:
        """Owner-only, idempotent cancel; only a certain-not-started send refunds.

        A cancelled reservation is never revived. Cancelling twice answers
        the same terminal record without another refund.
        """
        selected_now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._expire_due_locked(connection, now=selected_now)
                row = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                if row is None or str(row["service_credential_id"]) != str(
                    service_credential_id
                ):
                    connection.commit()
                    return None
                if str(row["state"]) == "cancelled":
                    connection.commit()
                    return _row_to_reservation(row)
                if str(row["state"]) != "reserved":
                    connection.commit()
                    return _row_to_reservation(row)
                connection.execute(
                    """
                    UPDATE service_delivery_reservations
                    SET state='cancelled', updated_at=?
                    WHERE id=? AND state='reserved'
                    """,
                    (_stamp(selected_now), str(reservation_id)),
                )
                if (
                    int(row["token_reserved"]) == 1
                    and int(row["token_refunded"]) == 0
                    and row["send_started_at"] is None
                ):
                    limit_row, available = self._bucket_refill_and_cost(
                        connection,
                        account_id=str(row["messenger_account_id"]),
                        provider=str(row["provider"]),
                        now=selected_now,
                    )
                    cost = float(json.loads(row["operation_costs"]).get("reserve", 1.0))
                    capacity = float(limit_row["capacity"])
                    connection.execute(
                        """
                        UPDATE account_execution_limits
                        SET available_tokens=?, last_refill_at=?, updated_at=?
                        WHERE messenger_account_id=? AND operation_scope=?
                        """,
                        (
                            min(capacity, available + cost),
                            _stamp(selected_now),
                            _stamp(selected_now),
                            str(row["messenger_account_id"]),
                            RESERVATION_OPERATION_SCOPE,
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE service_delivery_reservations
                        SET token_refunded=1, updated_at=?
                        WHERE id=?
                        """,
                        (_stamp(selected_now), str(reservation_id)),
                    )
                updated = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                connection.commit()
                return _row_to_reservation(updated)
            except Exception:
                connection.rollback()
                raise

    def consume(
        self,
        *,
        reservation_id: str,
        service_credential_id: str,
        operation_id: str,
        sender_profile_revision: int | None = None,
    ) -> DeliveryReservation:
        """Attach the send to the slot atomically; never re-acquire.

        Membership/revocation is enforced by the caller's authentication and
        the account lifecycle is re-checked here. A profile whose revision
        changed since the reservation answers ``revision_changed`` and the
        caller must reserve fresh — the pinned account is never switched
        silently. The same operation id is idempotent.
        """
        if not str(operation_id).strip():
            raise DeliveryReservationError(
                "Consumption requires a durable operation id.",
                code="delivery_reservation_operation_required",
            )
        selected_now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._expire_due_locked(connection, now=selected_now)
                row = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                if row is None or str(row["service_credential_id"]) != str(
                    service_credential_id
                ):
                    raise DeliveryReservationError(
                        "The delivery reservation was not found.",
                        code="delivery_reservation_not_found",
                    )
                if str(row["state"]) == "consumed":
                    if str(row["operation_id"]) == str(operation_id).strip():
                        connection.commit()
                        return _row_to_reservation(row)
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The reservation was already consumed by another operation.",
                        code="delivery_reservation_already_consumed",
                    )
                if str(row["state"]) != "reserved":
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The delivery reservation is not active.",
                        code="delivery_reservation_inactive",
                    )
                # Consume must wait at most until expires_at: a queue longer
                # than the slot lifetime never starts a send.
                if _parse(str(row["expires_at"])) < selected_now:
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The delivery reservation has expired.",
                        code="delivery_reservation_expired",
                    )
                if not self._account_available(connection, row["messenger_account_id"]):
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The pinned sender account is unavailable.",
                        code="account_unavailable",
                    )
                if (
                    row["sender_profile_id"]
                    and sender_profile_revision is not None
                    and int(row["sender_profile_revision"] or 0)
                    != int(sender_profile_revision)
                ):
                    connection.rollback()
                    raise DeliveryReservationError(
                        "The sender profile revision changed since the reservation.",
                        code="sender_profile_revision_changed",
                    )
                connection.execute(
                    """
                    UPDATE service_delivery_reservations
                    SET state='consumed', operation_id=?, updated_at=?
                    WHERE id=? AND state='reserved'
                    """,
                    (
                        str(operation_id).strip(),
                        _stamp(selected_now),
                        str(reservation_id),
                    ),
                )
                updated = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                connection.commit()
                return _row_to_reservation(updated)
            except Exception:
                connection.rollback()
                raise

    def mark_send_started(
        self, *, reservation_id: str, operation_id: str
    ) -> DeliveryReservation:
        """Record that the provider RPC began: from here a refund is forbidden
        even if the result is later uncertain."""
        selected_now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                if row is None or str(row["operation_id"]) != str(operation_id).strip():
                    raise DeliveryReservationError(
                        "The delivery reservation was not found.",
                        code="delivery_reservation_not_found",
                    )
                if str(row["send_started_at"]) not in (None, "None") and row["send_started_at"]:
                    connection.commit()
                    return _row_to_reservation(row)
                if str(row["state"]) != "consumed":
                    connection.rollback()
                    raise DeliveryReservationError(
                        "Only a consumed reservation can start its send.",
                        code="delivery_reservation_inactive",
                    )
                connection.execute(
                    """
                    UPDATE service_delivery_reservations
                    SET send_started_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (_stamp(selected_now), _stamp(selected_now), str(reservation_id)),
                )
                updated = connection.execute(
                    """
                    SELECT * FROM service_delivery_reservations WHERE id=?
                    """,
                    (str(reservation_id),),
                ).fetchone()
                connection.commit()
                return _row_to_reservation(updated)
            except Exception:
                connection.rollback()
                raise

    def outstanding_count(
        self, *, service_credential_id: str
    ) -> int:
        selected_now = self._now()
        with self._connect() as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM service_delivery_reservations
                    WHERE service_credential_id=? AND state='reserved' AND expires_at > ?
                    """,
                    (str(service_credential_id), _stamp(selected_now)),
                ).fetchone()[0]
            )


__all__ = [
    "DeliveryReservation",
    "DeliveryReservationError",
    "ServiceDeliveryReservationStore",
    "RESERVATION_OPERATION_SCOPE",
    "MAX_OUTSTANDING_PER_CREDENTIAL",
    "DEFAULT_TTL_SECONDS",
]

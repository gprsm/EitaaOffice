"""Versioned per-service sender profiles (P1 sender contract).

A sender profile pins one intent of one service credential to exactly one
messenger account of one provider. The admin chooses it explicitly; nothing
becomes a default sender by being first in a list or by being the most
recently used account. Writes are versioned and atomic: concurrent edits
collide on ``expected_revision`` and lose with ``stale_revision`` instead of
silently overwriting each other.

The profile table never substitutes the service credential fences — it is an
additional, narrower fence on top of the credential's own account/provider
allowlists, enforced again at send time in the M2M surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from ...errors import BridgeError

SENDER_INTENTS = ("otp", "notification")

_UNAVAILABLE_LIFECYCLE_STATES = frozenset({"archived", "disabled", "quarantined"})
_UNAVAILABLE_PHONE_STATES = frozenset({"archived", "disabled"})


class SenderProfileError(BridgeError):
    component = "sender_profiles"
    code = "sender_profile_error"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class ServiceSenderProfile:
    id: str
    service_credential_id: str
    intent: str
    provider: str
    messenger_account_id: str
    enabled: bool
    revision: int
    created_at: str
    updated_at: str


def _row_to_profile(row: sqlite3.Row) -> ServiceSenderProfile:
    return ServiceSenderProfile(
        id=str(row["id"]),
        service_credential_id=str(row["service_credential_id"]),
        intent=str(row["intent"]),
        provider=str(row["provider"]),
        messenger_account_id=str(row["messenger_account_id"]),
        enabled=bool(row["enabled"]),
        revision=int(row["revision"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class ServiceSenderProfileStore:
    """Versioned, atomic storage for per-service sender profiles."""

    def __init__(self, database) -> None:
        self._db = database

    def list_profiles(self) -> list[ServiceSenderProfile]:
        with self._db._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, service_credential_id, intent, provider,
                       messenger_account_id, enabled, revision,
                       created_at, updated_at
                FROM service_sender_profiles
                ORDER BY created_at, id
                """
            ).fetchall()
        return [_row_to_profile(row) for row in rows]

    def get_profile(self, profile_id: str) -> ServiceSenderProfile | None:
        with self._db._connect() as connection:
            row = connection.execute(
                """
                SELECT id, service_credential_id, intent, provider,
                       messenger_account_id, enabled, revision,
                       created_at, updated_at
                FROM service_sender_profiles
                WHERE id=?
                """,
                (str(profile_id),),
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def get_profile_for(self, service_credential_id: str, intent: str) -> ServiceSenderProfile | None:
        with self._db._connect() as connection:
            row = connection.execute(
                """
                SELECT id, service_credential_id, intent, provider,
                       messenger_account_id, enabled, revision,
                       created_at, updated_at
                FROM service_sender_profiles
                WHERE service_credential_id=? AND intent=?
                """,
                (str(service_credential_id), str(intent)),
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def try_get_enabled_profile(self, service_credential_id: str, intent: str):
        """Best-effort lookup for the legacy-path bypass guard.

        Returns None both when no enabled profile is configured and when the
        store is not readable (a test fixture without the table). The account
        and provider fences remain authoritative either way; only the extra
        anti-bypass check is skipped when the profile store cannot answer.
        """
        try:
            profile = self.get_profile_for(service_credential_id, intent)
        except Exception:
            return None
        if profile is None or not profile.enabled:
            return None
        return profile

    def upsert_profile(
        self,
        service_credential_id: str,
        intent: str,
        provider: str,
        messenger_account_id: str,
        *,
        enabled: bool,
        expected_revision: int | None,
        actor_app_user_id: str,
    ) -> ServiceSenderProfile:
        if intent not in SENDER_INTENTS:
            raise SenderProfileError(
                "Sender profile intent is invalid.",
                code="sender_profile_intent_invalid",
            )
        profile_id = str(uuid4())
        now = _now()
        with self._db._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT id, revision FROM service_sender_profiles
                    WHERE service_credential_id=? AND intent=?
                    """,
                    (str(service_credential_id), str(intent)),
                ).fetchone()
                if row is None:
                    if expected_revision is not None:
                        raise SenderProfileError(
                            "The sender profile revision is stale.",
                            code="stale_revision",
                        )
                    connection.execute(
                        """
                        INSERT INTO service_sender_profiles(
                            id,service_credential_id,intent,provider,
                            messenger_account_id,enabled,revision,
                            created_by_app_user_id,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,1,?,?,?)
                        """,
                        (
                            profile_id,
                            str(service_credential_id),
                            str(intent),
                            str(provider),
                            str(messenger_account_id),
                            1 if enabled else 0,
                            str(actor_app_user_id),
                            now,
                            now,
                        ),
                    )
                    created_id = profile_id
                else:
                    current_revision = int(row["revision"])
                    if expected_revision is None:
                        raise SenderProfileError(
                            "An explicit sender profile revision is required for updates.",
                            code="sender_profile_revision_required",
                        )
                    if int(expected_revision) != current_revision:
                        raise SenderProfileError(
                            "The sender profile revision is stale.",
                            code="stale_revision",
                        )
                    created_id = str(row["id"])
                    connection.execute(
                        """
                        UPDATE service_sender_profiles
                        SET provider=?, messenger_account_id=?, enabled=?,
                            revision=revision+1, created_by_app_user_id=?, updated_at=?
                        WHERE id=?
                        """,
                        (
                            str(provider),
                            str(messenger_account_id),
                            1 if enabled else 0,
                            str(actor_app_user_id),
                            now,
                            created_id,
                        ),
                    )
                updated = connection.execute(
                    """
                    SELECT id, service_credential_id, intent, provider,
                           messenger_account_id, enabled, revision,
                           created_at, updated_at
                    FROM service_sender_profiles WHERE id=?
                    """,
                    (created_id,),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return _row_to_profile(updated)

    def delete_profile(self, profile_id: str) -> None:
        with self._db._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM service_sender_profiles WHERE id=?",
                (str(profile_id),),
            )
            deleted = cursor.rowcount == 1
            connection.commit()
        if not deleted:
            raise SenderProfileError(
                "The sender profile was not found.",
                code="sender_profile_not_found",
            )

    def account_available(self, messenger_account_id: str) -> bool:
        """Honest availability snapshot for a pinned account.

        Missing account rows, archived/disabled/quarantined messenger
        accounts and archived/disabled phone accounts are unavailable.
        This is a snapshot only; the provider may still refuse later.
        """
        with self._db._connect() as connection:
            row = connection.execute(
                """
                SELECT ma.lifecycle_state AS lifecycle_state, pa.status AS phone_status
                FROM messenger_accounts ma
                JOIN phone_accounts pa ON pa.id=ma.phone_account_id
                WHERE ma.id=?
                """,
                (str(messenger_account_id),),
            ).fetchone()
        if row is None:
            return False
        if str(row["lifecycle_state"]) in _UNAVAILABLE_LIFECYCLE_STATES:
            return False
        if str(row["phone_status"]) in _UNAVAILABLE_PHONE_STATES:
            return False
        return True

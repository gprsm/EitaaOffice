"""Persistent, privacy-safe idempotency claims for provider mutations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from uuid import UUID

from ...errors import CoordinatorSchemaError
from .store import CoordinatorDatabase


_OPERATIONS = frozenset({"messages.send_text", "messages.send_media", "contacts.upsert", "contacts.remove"})
_OUTCOMES = frozenset({"in_progress", "succeeded", "uncertain"})
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _uuid4(value: object, *, code: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorSchemaError(
            "A provider receipt identity is invalid.",
            code=code,
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise CoordinatorSchemaError(
            "A provider receipt identity is invalid.",
            code=code,
        )
    return str(parsed)


@dataclass(frozen=True, slots=True)
class ProviderOperationReceiptRecord:
    messenger_account_id: str
    actor_app_user_id: str
    service_credential_id: str | None
    provider: str
    operation: str
    idempotency_key: str
    request_fingerprint: str
    claim_deadline_unix_ms: int
    outcome: str
    result_reference: str | None
    contact_created: bool | None
    safe_reason_code: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class ProviderOperationClaim:
    receipt: ProviderOperationReceiptRecord
    claimed: bool


class ProviderOperationReceiptStore:
    """Atomically reserve and complete one account-scoped mutation key."""

    def __init__(self, database: CoordinatorDatabase) -> None:
        self.database = database
        self.database.initialize()

    def claim(
        self,
        *,
        messenger_account_id: str,
        actor_app_user_id: str,
        actor_global_role: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        claim_deadline_unix_ms: int,
        service_credential_id: str | None = None,
    ) -> ProviderOperationClaim:
        account_id, actor_id, selected_operation, selected_key, fingerprint = (
            self._validate_identity(
                messenger_account_id=messenger_account_id,
                actor_app_user_id=actor_app_user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
        )
        if actor_global_role not in {"admin", "user"}:
            raise CoordinatorSchemaError(
                "The provider receipt actor role is invalid.",
                code="provider_receipt_actor_invalid",
            )
        if (
            isinstance(claim_deadline_unix_ms, bool)
            or not isinstance(claim_deadline_unix_ms, int)
            or claim_deadline_unix_ms <= 0
        ):
            raise CoordinatorSchemaError(
                "The provider receipt claim deadline is invalid.",
                code="provider_receipt_deadline_invalid",
            )
        try:
            with self.database._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._select(
                    connection,
                    account_id,
                    selected_operation,
                    selected_key,
                )
                if existing is not None:
                    self._assert_request_match(
                        existing,
                        actor_id,
                        fingerprint,
                        service_credential_id=service_credential_id,
                    )
                    connection.commit()
                    return ProviderOperationClaim(self._record(existing), False)
                scope = connection.execute(
                    """
                    SELECT ma.provider,ma.lifecycle_state,au.status AS actor_status,
                           au.global_role,pm.status AS membership_status
                    FROM messenger_accounts ma
                    JOIN app_users au ON au.id=?
                    LEFT JOIN phone_account_memberships pm
                      ON pm.phone_account_id=ma.phone_account_id
                     AND pm.app_user_id=au.id
                    WHERE ma.id=?
                    """,
                    (actor_id, account_id),
                ).fetchone()
                bound_service = str(service_credential_id or "").strip() or None
                if bound_service is not None:
                    # Service (M2M) receipts are anchored to the credential's
                    # creator; membership is intentionally not consulted here
                    # because service access is fenced by the credential itself.
                    allowed = bool(
                        scope is not None
                        and str(scope["actor_status"]) == "active"
                        and str(scope["global_role"]) == "admin"
                        and str(scope["lifecycle_state"]) != "archived"
                    )
                else:
                    allowed = bool(
                        scope is not None
                        and str(scope["actor_status"]) == "active"
                        and str(scope["global_role"]) == actor_global_role
                        and str(scope["lifecycle_state"]) != "archived"
                        and (
                            actor_global_role == "admin"
                            or str(scope["membership_status"] or "") == "active"
                        )
                    )
                if not allowed:
                    raise CoordinatorSchemaError(
                        "The provider receipt actor cannot operate this account.",
                        code="provider_receipt_access_denied",
                    )
                now = _timestamp()
                connection.execute(
                    """
                    INSERT INTO provider_operation_receipts(
                        messenger_account_id,actor_app_user_id,service_credential_id,provider,operation,
                        idempotency_key,request_fingerprint,claim_deadline_unix_ms,
                        outcome,result_reference,
                        contact_created,safe_reason_code,created_at,updated_at,completed_at
                    ) VALUES(?,?,?,?,?,?,?,?,'in_progress',NULL,NULL,NULL,?,?,NULL)
                    """,
                    (
                        account_id,
                        actor_id,
                        bound_service,
                        str(scope["provider"]),
                        selected_operation,
                        selected_key,
                        fingerprint,
                        claim_deadline_unix_ms,
                        now,
                        now,
                    ),
                )
                row = self._select(
                    connection,
                    account_id,
                    selected_operation,
                    selected_key,
                )
                connection.commit()
                assert row is not None
                return ProviderOperationClaim(self._record(row), True)
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The provider operation claim could not be persisted.",
                safe_context={"error_type": type(exc).__name__},
                code="provider_receipt_claim_failed",
            ) from exc

    def complete(
        self,
        *,
        messenger_account_id: str,
        actor_app_user_id: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
        outcome: str,
        result_reference: str | None,
        contact_created: bool | None,
        safe_reason_code: str | None,
        service_credential_id: str | None = None,
    ) -> ProviderOperationReceiptRecord:
        account_id, actor_id, selected_operation, selected_key, fingerprint = (
            self._validate_identity(
                messenger_account_id=messenger_account_id,
                actor_app_user_id=actor_app_user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
        )
        selected_outcome = str(outcome or "").strip().lower()
        reference = str(result_reference or "").strip() or None
        reason = str(safe_reason_code or "").strip().lower() or None
        if selected_outcome not in {"succeeded", "uncertain"}:
            raise CoordinatorSchemaError(
                "The provider receipt outcome is invalid.",
                code="provider_receipt_outcome_invalid",
            )
        if reference is not None and not _REFERENCE.fullmatch(reference):
            raise CoordinatorSchemaError(
                "The provider receipt reference is invalid.",
                code="provider_receipt_result_invalid",
            )
        if reason is not None and not _SAFE_CODE.fullmatch(reason):
            raise CoordinatorSchemaError(
                "The provider receipt reason is invalid.",
                code="provider_receipt_result_invalid",
            )
        if selected_operation in {"messages.send_text", "messages.send_media"}:
            if contact_created is not None or (
                selected_outcome == "succeeded" and reference is None
            ):
                raise CoordinatorSchemaError(
                    "The provider send receipt is invalid.",
                    code="provider_receipt_result_invalid",
                )
        elif selected_outcome == "succeeded":
            if reference is None or not isinstance(contact_created, bool):
                raise CoordinatorSchemaError(
                    "The provider contact receipt is invalid.",
                    code="provider_receipt_result_invalid",
                )
        elif reference is not None or contact_created is not None:
            raise CoordinatorSchemaError(
                "The uncertain provider contact receipt is invalid.",
                code="provider_receipt_result_invalid",
            )
        try:
            with self.database._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = self._select(
                    connection,
                    account_id,
                    selected_operation,
                    selected_key,
                )
                if existing is None:
                    raise CoordinatorSchemaError(
                        "The provider operation claim was not found.",
                        code="provider_receipt_claim_missing",
                    )
                self._assert_request_match(
                    existing,
                    actor_id,
                    fingerprint,
                    service_credential_id=service_credential_id,
                )
                if str(existing["outcome"]) != "in_progress":
                    self._assert_result_match(
                        existing,
                        outcome=selected_outcome,
                        result_reference=reference,
                        contact_created=contact_created,
                        safe_reason_code=reason,
                    )
                    connection.commit()
                    return self._record(existing)
                now = _timestamp()
                connection.execute(
                    """
                    UPDATE provider_operation_receipts
                    SET outcome=?,result_reference=?,contact_created=?,
                        safe_reason_code=?,updated_at=?,completed_at=?
                    WHERE messenger_account_id=? AND operation=? AND idempotency_key=?
                      AND outcome='in_progress'
                    """,
                    (
                        selected_outcome,
                        reference,
                        (
                            int(contact_created)
                            if contact_created is not None
                            else None
                        ),
                        reason,
                        now,
                        now,
                        account_id,
                        selected_operation,
                        selected_key,
                    ),
                )
                updated = self._select(
                    connection,
                    account_id,
                    selected_operation,
                    selected_key,
                )
                connection.commit()
                assert updated is not None
                return self._record(updated)
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The provider operation receipt could not be persisted.",
                safe_context={"error_type": type(exc).__name__},
                code="provider_receipt_complete_failed",
            ) from exc

    @staticmethod
    def _validate_identity(
        *,
        messenger_account_id: str,
        actor_app_user_id: str,
        operation: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> tuple[str, str, str, str, str]:
        account_id = _uuid4(
            messenger_account_id,
            code="provider_receipt_account_invalid",
        )
        actor_id = _uuid4(
            actor_app_user_id,
            code="provider_receipt_actor_invalid",
        )
        selected_operation = str(operation or "").strip()
        selected_key = str(idempotency_key or "").strip()
        fingerprint = str(request_fingerprint or "").strip().lower()
        if selected_operation not in _OPERATIONS:
            raise CoordinatorSchemaError(
                "The provider receipt operation is invalid.",
                code="provider_receipt_operation_invalid",
            )
        if not _IDEMPOTENCY.fullmatch(selected_key):
            raise CoordinatorSchemaError(
                "The provider receipt idempotency key is invalid.",
                code="provider_receipt_idempotency_invalid",
            )
        if not _SHA256.fullmatch(fingerprint):
            raise CoordinatorSchemaError(
                "The provider receipt request fingerprint is invalid.",
                code="provider_receipt_fingerprint_invalid",
            )
        return account_id, actor_id, selected_operation, selected_key, fingerprint

    @staticmethod
    def _select(
        connection: sqlite3.Connection,
        account_id: str,
        operation: str,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM provider_operation_receipts
            WHERE messenger_account_id=? AND operation=? AND idempotency_key=?
            """,
            (account_id, operation, idempotency_key),
        ).fetchone()

    @staticmethod
    def _assert_request_match(
        row: sqlite3.Row,
        actor_id: str,
        request_fingerprint: str,
        *,
        service_credential_id: str | None = None,
    ) -> None:
        if str(row["actor_app_user_id"]) != actor_id:
            raise CoordinatorSchemaError(
                "The provider idempotency key belongs to another AppUser.",
                code="provider_idempotency_owner_mismatch",
            )
        if str(row["request_fingerprint"]) != request_fingerprint:
            raise CoordinatorSchemaError(
                "The provider idempotency key belongs to another request.",
                code="provider_idempotency_payload_mismatch",
            )
        stored_service = (
            str(row["service_credential_id"])
            if row["service_credential_id"] is not None
            else None
        )
        if stored_service != (str(service_credential_id) if service_credential_id else None):
            # Never attribute a legacy (owner-less) or another service's
            # receipt to this caller: ownership must be proven, not guessed.
            raise CoordinatorSchemaError(
                "The provider idempotency key belongs to another service.",
                code="provider_idempotency_owner_mismatch",
            )

    @staticmethod
    def _assert_result_match(
        row: sqlite3.Row,
        *,
        outcome: str,
        result_reference: str | None,
        contact_created: bool | None,
        safe_reason_code: str | None,
    ) -> None:
        stored_created = (
            bool(row["contact_created"])
            if row["contact_created"] is not None
            else None
        )
        if (
            str(row["outcome"]) != outcome
            or (str(row["result_reference"]) if row["result_reference"] else None)
            != result_reference
            or stored_created != contact_created
            or (str(row["safe_reason_code"]) if row["safe_reason_code"] else None)
            != safe_reason_code
        ):
            raise CoordinatorSchemaError(
                "The provider receipt result conflicts with its terminal state.",
                code="provider_receipt_result_mismatch",
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> ProviderOperationReceiptRecord:
        return ProviderOperationReceiptRecord(
            messenger_account_id=str(row["messenger_account_id"]),
            actor_app_user_id=str(row["actor_app_user_id"]),
            service_credential_id=(
                str(row["service_credential_id"])
                if row["service_credential_id"] is not None
                else None
            ),
            provider=str(row["provider"]),
            operation=str(row["operation"]),
            idempotency_key=str(row["idempotency_key"]),
            request_fingerprint=str(row["request_fingerprint"]),
            claim_deadline_unix_ms=int(row["claim_deadline_unix_ms"]),
            outcome=str(row["outcome"]),
            result_reference=(
                str(row["result_reference"])
                if row["result_reference"] is not None
                else None
            ),
            contact_created=(
                bool(row["contact_created"])
                if row["contact_created"] is not None
                else None
            ),
            safe_reason_code=(
                str(row["safe_reason_code"])
                if row["safe_reason_code"] is not None
                else None
            ),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            completed_at=(
                str(row["completed_at"])
                if row["completed_at"] is not None
                else None
            ),
        )


__all__ = [
    "ProviderOperationClaim",
    "ProviderOperationReceiptRecord",
    "ProviderOperationReceiptStore",
]

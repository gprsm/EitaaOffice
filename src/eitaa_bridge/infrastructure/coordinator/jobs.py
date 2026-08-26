"""Persistent, account-scoped operation jobs owned by the Coordinator."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import sqlite3
from typing import Any
from uuid import UUID, uuid4

from ...errors import CoordinatorSchemaError
from .store import CoordinatorDatabase


_OPERATION = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9_.:-]{1,240}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")
_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "uncertain"})


def _now_datetime() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now_datetime()).isoformat(timespec="milliseconds")


def _uuid(value: str, *, code: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorSchemaError(
            "A persistent job identifier is invalid.", code=code
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise CoordinatorSchemaError(
            "A persistent job identifier is invalid.", code=code
        )
    return value


@dataclass(frozen=True, slots=True)
class OperationJobRecord:
    job_id: str
    actor_app_user_id: str
    phone_account_id: str
    messenger_account_id: str
    provider: str
    operation: str
    status: str
    idempotency_key: str
    safe_payload_ref: str | None
    correlation_id: str
    attempt_count: int
    scheduled_at: str | None
    lease_owner: str | None
    lease_generation: int | None
    lease_expires_at: str | None
    cancel_requested_at: str | None
    completed_at: str | None
    last_error_class: str | None
    last_error_code: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "actor_app_user_id": self.actor_app_user_id,
            "phone_account_id": self.phone_account_id,
            "messenger_account_id": self.messenger_account_id,
            "provider": self.provider,
            "operation": self.operation,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "attempt_count": self.attempt_count,
            "scheduled_at": self.scheduled_at,
            "lease_owner": self.lease_owner,
            "lease_generation": self.lease_generation,
            "lease_expires_at": self.lease_expires_at,
            "cancel_requested": self.cancel_requested_at is not None,
            "completed_at": self.completed_at,
            "last_error_class": self.last_error_class,
            "last_error_code": self.last_error_code,
            "payload_reference_present": self.safe_payload_ref is not None,
        }


@dataclass(frozen=True, slots=True)
class JobAttemptRecord:
    attempt_id: str
    job_id: str
    attempt_number: int
    worker_id: str
    worker_generation: int
    lease_id: str | None
    correlation_id: str | None
    result: str | None
    error_class: str | None
    error_code: str | None
    retry_after_ms: int | None
    started_at: str
    completed_at: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "job_id": self.job_id,
            "attempt_number": self.attempt_number,
            "worker_id": self.worker_id,
            "worker_generation": self.worker_generation,
            "lease_id": self.lease_id,
            "correlation_id": self.correlation_id,
            "result": self.result,
            "error_class": self.error_class,
            "error_code": self.error_code,
            "retry_after_ms": self.retry_after_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True, slots=True)
class CreateJobResult:
    job: OperationJobRecord
    reused: bool


@dataclass(frozen=True, slots=True)
class JobLeaseRecord:
    lease_id: str
    job_id: str
    worker_id: str
    worker_generation: int
    correlation_id: str
    status: str
    acquired_at: str
    expires_at: str
    released_at: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "lease_id": self.lease_id,
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "worker_generation": self.worker_generation,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "released_at": self.released_at,
        }


@dataclass(frozen=True, slots=True)
class JobRecoverySummary:
    pending_recovered: int
    cancelled_recovered: int
    uncertain_recovered: int

    def safe_summary(self) -> dict[str, int]:
        return {
            "pending_recovered": self.pending_recovered,
            "cancelled_recovered": self.cancelled_recovered,
            "uncertain_recovered": self.uncertain_recovered,
        }


class PersistentOperationJobService:
    """Transactional job/lease/attempt state with crash-safe fencing."""

    def __init__(self, database: CoordinatorDatabase) -> None:
        self.database = database
        self.database.initialize()

    def create_job(
        self,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
        messenger_account_id: str,
        operation: str,
        idempotency_key: str,
        correlation_id: str | None = None,
        safe_payload_ref: str | None = None,
        recipient_ref_hashes: Collection[str] = (),
        scheduled_at: str | None = None,
    ) -> CreateJobResult:
        actor_id = _uuid(actor_app_user_id, code="operation_job_actor_invalid")
        account_id = _uuid(
            messenger_account_id, code="operation_job_account_invalid"
        )
        selected_operation = str(operation or "").strip()
        selected_idempotency = str(idempotency_key or "").strip()
        if not _OPERATION.fullmatch(selected_operation):
            raise CoordinatorSchemaError(
                "The operation job type is invalid.", code="operation_job_type_invalid"
            )
        if not _IDEMPOTENCY.fullmatch(selected_idempotency):
            raise CoordinatorSchemaError(
                "The operation idempotency key is invalid.",
                code="operation_job_idempotency_invalid",
            )
        payload_ref = str(safe_payload_ref).strip() if safe_payload_ref else None
        if payload_ref and (
            not _SAFE_REFERENCE.fullmatch(payload_ref)
            or any(part in payload_ref.casefold() for part in ("password", "secret", "token", "otp"))
        ):
            raise CoordinatorSchemaError(
                "The operation payload reference is unsafe.",
                code="operation_job_payload_ref_invalid",
            )
        recipients = tuple(sorted(set(str(item).strip().lower() for item in recipient_ref_hashes)))
        if any(not _SHA256.fullmatch(item) for item in recipients) or len(recipients) > 10_000:
            raise CoordinatorSchemaError(
                "The operation recipient references are invalid.",
                code="operation_job_recipients_invalid",
            )
        selected_correlation = _uuid(
            correlation_id or str(uuid4()), code="operation_job_correlation_invalid"
        )
        schedule = self._validate_schedule(scheduled_at)
        try:
            with self.database._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                account = self._require_actor_account(
                    connection,
                    actor_id=actor_id,
                    actor_global_role=actor_global_role,
                    account_id=account_id,
                )
                existing = connection.execute(
                    """
                    SELECT * FROM operation_jobs
                    WHERE messenger_account_id=? AND operation=? AND idempotency_key=?
                    """,
                    (account_id, selected_operation, selected_idempotency),
                ).fetchone()
                if existing is not None:
                    if str(existing["actor_app_user_id"] or "") != actor_id:
                        raise CoordinatorSchemaError(
                            "The idempotency key belongs to another AppUser.",
                            code="operation_job_idempotency_owner_mismatch",
                        )
                    existing_recipients = {
                        str(row["recipient_ref_hash"])
                        for row in connection.execute(
                            "SELECT recipient_ref_hash FROM operation_job_recipients WHERE job_id=?",
                            (str(existing["id"]),),
                        ).fetchall()
                    }
                    if existing_recipients != set(recipients) or str(existing["safe_payload_ref"] or "") != str(payload_ref or ""):
                        raise CoordinatorSchemaError(
                            "The idempotent request payload does not match the original job.",
                            code="operation_job_idempotency_payload_mismatch",
                        )
                    connection.commit()
                    return CreateJobResult(self._job(existing), reused=True)
                now = _timestamp()
                job_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO operation_jobs(
                        id,actor_app_user_id,phone_account_id,messenger_account_id,
                        provider,operation,status,idempotency_key,safe_payload_ref,
                        correlation_id,scheduled_at,attempt_count,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,'pending',?,?,?,?,0,?,?)
                    """,
                    (
                        job_id,
                        actor_id,
                        str(account["phone_account_id"]),
                        account_id,
                        str(account["provider"]),
                        selected_operation,
                        selected_idempotency,
                        payload_ref,
                        selected_correlation,
                        schedule or now,
                        now,
                        now,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO operation_job_recipients(
                        job_id,recipient_ref_hash,status,attempt_count,created_at,updated_at
                    ) VALUES(?,?,'pending',0,?,?)
                    """,
                    [(job_id, item, now, now) for item in recipients],
                )
                self._audit(
                    connection,
                    action="operation_job.created",
                    actor_id=actor_id,
                    actor_role=actor_global_role,
                    row={
                        "id": job_id,
                        "phone_account_id": str(account["phone_account_id"]),
                        "messenger_account_id": account_id,
                        "provider": str(account["provider"]),
                    },
                    result="succeeded",
                    safe_metadata={
                        "operation": selected_operation,
                        "recipient_count": len(recipients),
                    },
                    correlation_id=selected_correlation,
                )
                row = connection.execute(
                    "SELECT * FROM operation_jobs WHERE id=?", (job_id,)
                ).fetchone()
                connection.commit()
                return CreateJobResult(self._job(row), reused=False)
        except CoordinatorSchemaError:
            raise
        except sqlite3.Error as exc:
            raise CoordinatorSchemaError(
                "The persistent operation job could not be created.",
                safe_context={"error_type": type(exc).__name__},
                code="operation_job_create_failed",
            ) from exc

    def lease_next_job(
        self,
        *,
        messenger_account_id: str,
        worker_id: str,
        worker_generation: int,
        lease_seconds: int = 30,
    ) -> OperationJobRecord | None:
        account_id = _uuid(messenger_account_id, code="operation_job_account_invalid")
        selected_worker = _uuid(worker_id, code="operation_job_worker_invalid")
        if not isinstance(worker_generation, int) or worker_generation <= 0:
            raise CoordinatorSchemaError(
                "The job worker generation is invalid.",
                code="operation_job_worker_generation_invalid",
            )
        if not 1 <= lease_seconds <= 300:
            raise CoordinatorSchemaError(
                "The operation job lease duration is invalid.",
                code="operation_job_lease_duration_invalid",
            )
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now_dt = _now_datetime()
            self._recover_expired(connection, account_id=account_id, now=now_dt)
            now = _timestamp(now_dt)
            row = connection.execute(
                """
                SELECT * FROM operation_jobs
                WHERE messenger_account_id=? AND status='pending'
                  AND cancel_requested_at IS NULL
                  AND (scheduled_at IS NULL OR scheduled_at<=?)
                ORDER BY scheduled_at,created_at,id
                LIMIT 1
                """,
                (account_id, now),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            expires = _timestamp(now_dt + timedelta(seconds=lease_seconds))
            lease_id = str(uuid4())
            lease_correlation_id = str(uuid4())
            cursor = connection.execute(
                """
                UPDATE operation_jobs
                SET status='leased',lease_owner=?,lease_generation=?,
                    lease_expires_at=?,updated_at=?
                WHERE id=? AND status='pending'
                """,
                (selected_worker, worker_generation, expires, now, str(row["id"])),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            connection.execute(
                """
                INSERT INTO job_leases(
                    id,job_id,worker_id,worker_generation,correlation_id,status,
                    acquired_at,expires_at,created_at,updated_at
                ) VALUES(?,?,?,?,?,'active',?,?,?,?)
                """,
                (
                    lease_id,
                    str(row["id"]),
                    selected_worker,
                    worker_generation,
                    lease_correlation_id,
                    now,
                    expires,
                    now,
                    now,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (str(row["id"]),)
            ).fetchone()
            self._audit(
                connection,
                action="operation_job.leased",
                actor_id=None,
                actor_role=None,
                row=updated,
                result="succeeded",
                safe_metadata={
                    "worker_generation": worker_generation,
                    "lease_id": lease_id,
                    "lease_correlation_id": lease_correlation_id,
                },
                correlation_id=str(updated["correlation_id"]),
            )
            connection.commit()
            return self._job(updated)

    def lease_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        worker_generation: int,
        lease_seconds: int = 30,
    ) -> OperationJobRecord:
        """Lease one exact queued job; a worker may never consume another account job."""

        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        selected_worker = _uuid(worker_id, code="operation_job_worker_invalid")
        if not isinstance(worker_generation, int) or worker_generation <= 0:
            raise CoordinatorSchemaError(
                "The job worker generation is invalid.",
                code="operation_job_worker_generation_invalid",
            )
        if not 1 <= lease_seconds <= 300:
            raise CoordinatorSchemaError(
                "The operation job lease duration is invalid.",
                code="operation_job_lease_duration_invalid",
            )
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now_dt = _now_datetime()
            now = _timestamp(now_dt)
            row = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            if row is None:
                raise CoordinatorSchemaError(
                    "The operation job was not found.", code="operation_job_not_found"
                )
            if (
                str(row["status"]) != "pending"
                or row["cancel_requested_at"] is not None
                or (row["scheduled_at"] is not None and str(row["scheduled_at"]) > now)
            ):
                raise CoordinatorSchemaError(
                    "The operation job is not available for leasing.",
                    code="operation_job_not_leaseable",
                )
            expires = _timestamp(now_dt + timedelta(seconds=lease_seconds))
            lease_id = str(uuid4())
            lease_correlation_id = str(uuid4())
            connection.execute(
                """
                UPDATE operation_jobs SET status='leased',lease_owner=?,lease_generation=?,
                    lease_expires_at=?,updated_at=? WHERE id=? AND status='pending'
                """,
                (selected_worker, worker_generation, expires, now, selected_job),
            )
            connection.execute(
                """
                INSERT INTO job_leases(
                    id,job_id,worker_id,worker_generation,correlation_id,status,
                    acquired_at,expires_at,created_at,updated_at
                ) VALUES(?,?,?,?,?,'active',?,?,?,?)
                """,
                (
                    lease_id,
                    selected_job,
                    selected_worker,
                    worker_generation,
                    lease_correlation_id,
                    now,
                    expires,
                    now,
                    now,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            self._audit(
                connection,
                action="operation_job.leased",
                actor_id=None,
                actor_role=None,
                row=updated,
                result="succeeded",
                safe_metadata={
                    "worker_generation": worker_generation,
                    "lease_id": lease_id,
                    "lease_correlation_id": lease_correlation_id,
                },
                correlation_id=str(updated["correlation_id"]),
            )
            connection.commit()
            return self._job(updated)

    def start_attempt(
        self,
        job_id: str,
        *,
        worker_id: str,
        worker_generation: int,
    ) -> tuple[OperationJobRecord, JobAttemptRecord]:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        selected_worker = _uuid(worker_id, code="operation_job_worker_invalid")
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._leased_job(
                connection,
                job_id=selected_job,
                worker_id=selected_worker,
                worker_generation=worker_generation,
                allowed_statuses={"leased"},
            )
            if row["cancel_requested_at"] is not None:
                now = _timestamp()
                connection.execute(
                    """
                    UPDATE operation_jobs SET status='cancelled',cancelled_at=?,completed_at=?,
                        lease_owner=NULL,lease_generation=NULL,lease_expires_at=NULL,updated_at=?
                    WHERE id=?
                    """,
                    (now, now, now, selected_job),
                )
                connection.execute(
                    "UPDATE operation_job_recipients SET status='cancelled',updated_at=? WHERE job_id=? AND status='pending'",
                    (now, selected_job),
                )
                connection.commit()
                raise CoordinatorSchemaError(
                    "The operation job was cancelled before execution.",
                    code="operation_job_cancel_requested",
                )
            now = _timestamp()
            attempt_number = int(row["attempt_count"]) + 1
            attempt_id = str(uuid4())
            attempt_correlation_id = str(uuid4())
            lease = connection.execute(
                """
                SELECT * FROM job_leases
                WHERE job_id=? AND worker_id=? AND worker_generation=? AND status='active'
                """,
                (selected_job, selected_worker, worker_generation),
            ).fetchone()
            if lease is None:
                raise CoordinatorSchemaError(
                    "The current operation lease journal is missing.",
                    code="operation_job_lease_journal_missing",
                )
            connection.execute(
                """
                INSERT INTO job_attempts(
                    id,job_id,attempt_number,worker_id,worker_generation,
                    lease_id,correlation_id,started_at,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    attempt_id,
                    selected_job,
                    attempt_number,
                    selected_worker,
                    worker_generation,
                    str(lease["id"]),
                    attempt_correlation_id,
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                "UPDATE operation_jobs SET status='running',attempt_count=?,updated_at=? WHERE id=?",
                (attempt_number, now, selected_job),
            )
            connection.execute(
                """
                UPDATE operation_job_recipients
                SET status='running',attempt_count=attempt_count+1,updated_at=?
                WHERE job_id=? AND status='pending'
                """,
                (now, selected_job),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            attempt = connection.execute(
                "SELECT * FROM job_attempts WHERE id=?", (attempt_id,)
            ).fetchone()
            self._audit(
                connection,
                action="operation_job.attempt_started",
                actor_id=None,
                actor_role=None,
                row=updated,
                result="succeeded",
                safe_metadata={
                    "attempt_number": attempt_number,
                    "lease_id": str(lease["id"]),
                    "lease_correlation_id": str(lease["correlation_id"]),
                    "attempt_correlation_id": attempt_correlation_id,
                },
                correlation_id=str(updated["correlation_id"]),
            )
            connection.commit()
            return self._job(updated), self._attempt(attempt)

    def complete_attempt(
        self,
        job_id: str,
        *,
        worker_id: str,
        worker_generation: int,
        result: str,
        error_class: str | None = None,
        error_code: str | None = None,
        retry_after_ms: int | None = None,
    ) -> OperationJobRecord:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        selected_worker = _uuid(worker_id, code="operation_job_worker_invalid")
        selected_result = str(result or "").strip()
        if selected_result not in _TERMINAL:
            raise CoordinatorSchemaError(
                "The operation attempt result is invalid.",
                code="operation_job_result_invalid",
            )
        selected_error_class = self._safe_code(error_class, "operation_job_error_class_invalid")
        selected_error_code = self._safe_code(error_code, "operation_job_error_code_invalid")
        if retry_after_ms is not None and (
            not isinstance(retry_after_ms, int) or not 0 <= retry_after_ms <= 86_400_000
        ):
            raise CoordinatorSchemaError(
                "The operation retry delay is invalid.",
                code="operation_job_retry_after_invalid",
            )
        if retry_after_ms is not None and selected_result != "failed":
            raise CoordinatorSchemaError(
                "Only a failed attempt can be scheduled for retry.",
                code="operation_job_retry_result_invalid",
            )
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._leased_job(
                connection,
                job_id=selected_job,
                worker_id=selected_worker,
                worker_generation=worker_generation,
                allowed_statuses={"running"},
            )
            attempt = connection.execute(
                """
                SELECT * FROM job_attempts
                WHERE job_id=? AND completed_at IS NULL
                ORDER BY attempt_number DESC LIMIT 1
                """,
                (selected_job,),
            ).fetchone()
            if attempt is None or int(attempt["attempt_number"]) != int(row["attempt_count"]):
                raise CoordinatorSchemaError(
                    "The current operation attempt is missing.",
                    code="operation_job_attempt_missing",
                )
            now_dt = _now_datetime()
            now = _timestamp(now_dt)
            connection.execute(
                """
                UPDATE job_attempts
                SET result=?,error_class=?,error_code=?,retry_after_ms=?,
                    completed_at=?,updated_at=?
                WHERE id=?
                """,
                (
                    selected_result,
                    selected_error_class,
                    selected_error_code,
                    retry_after_ms,
                    now,
                    now,
                    str(attempt["id"]),
                ),
            )
            connection.execute(
                """
                UPDATE job_leases SET status='released',released_at=?,updated_at=?
                WHERE id=? AND status='active'
                """,
                (now, now, str(attempt["lease_id"])),
            )
            retrying = retry_after_ms is not None
            status = "pending" if retrying else selected_result
            scheduled_at = (
                _timestamp(now_dt + timedelta(milliseconds=retry_after_ms or 0))
                if retrying
                else row["scheduled_at"]
            )
            completed_at = None if retrying else now
            cancelled_at = now if status == "cancelled" else row["cancelled_at"]
            connection.execute(
                """
                UPDATE operation_jobs
                SET status=?,scheduled_at=?,completed_at=?,cancelled_at=?,
                    last_error_class=?,last_error_code=?,lease_owner=NULL,
                    lease_generation=NULL,lease_expires_at=NULL,updated_at=?
                WHERE id=?
                """,
                (
                    status,
                    scheduled_at,
                    completed_at,
                    cancelled_at,
                    selected_error_class,
                    selected_error_code,
                    now,
                    selected_job,
                ),
            )
            recipient_status = "pending" if retrying else selected_result
            connection.execute(
                """
                UPDATE operation_job_recipients
                SET status=?,last_error_class=?,last_error_code=?,updated_at=?
                WHERE job_id=? AND status='running'
                """,
                (
                    recipient_status,
                    selected_error_class,
                    selected_error_code,
                    now,
                    selected_job,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            self._audit(
                connection,
                action="operation_job.retry_scheduled" if retrying else f"operation_job.{status}",
                actor_id=None,
                actor_role=None,
                row=updated,
                result="succeeded",
                safe_metadata={
                    "attempt_number": int(attempt["attempt_number"]),
                    "attempt_result": selected_result,
                    "retry_after_ms": retry_after_ms,
                    "lease_id": str(attempt["lease_id"]),
                    "attempt_correlation_id": str(attempt["correlation_id"]),
                },
                correlation_id=str(updated["correlation_id"]),
            )
            connection.commit()
            return self._job(updated)

    def request_cancel(
        self,
        job_id: str,
        *,
        actor_app_user_id: str,
        actor_global_role: str,
    ) -> OperationJobRecord:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        actor_id = _uuid(actor_app_user_id, code="operation_job_actor_invalid")
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            if row is None:
                raise CoordinatorSchemaError(
                    "The operation job was not found.", code="operation_job_not_found"
                )
            actor = connection.execute(
                "SELECT status,global_role FROM app_users WHERE id=?", (actor_id,)
            ).fetchone()
            if (
                actor is None
                or str(actor["status"]) != "active"
                or str(actor["global_role"]) != actor_global_role
                or (actor_id != str(row["actor_app_user_id"]) and actor_global_role != "admin")
            ):
                raise CoordinatorSchemaError(
                    "The AppUser cannot cancel this operation job.",
                    code="operation_job_cancel_denied",
                )
            status = str(row["status"])
            if status in _TERMINAL:
                connection.commit()
                return self._job(row)
            now = _timestamp()
            if status in {"pending", "leased"}:
                connection.execute(
                    """
                    UPDATE operation_jobs
                    SET status='cancelled',cancel_requested_at=?,cancelled_at=?,completed_at=?,
                        lease_owner=NULL,lease_generation=NULL,lease_expires_at=NULL,updated_at=?
                    WHERE id=?
                    """,
                    (now, now, now, now, selected_job),
                )
                connection.execute(
                    "UPDATE operation_job_recipients SET status='cancelled',updated_at=? WHERE job_id=? AND status='pending'",
                    (now, selected_job),
                )
                connection.execute(
                    """
                    UPDATE job_leases SET status='released',released_at=?,updated_at=?
                    WHERE job_id=? AND status='active'
                    """,
                    (now, now, selected_job),
                )
            else:
                connection.execute(
                    "UPDATE operation_jobs SET cancel_requested_at=COALESCE(cancel_requested_at,?),updated_at=? WHERE id=?",
                    (now, now, selected_job),
                )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            self._audit(
                connection,
                action="operation_job.cancel_requested",
                actor_id=actor_id,
                actor_role=actor_global_role,
                row=updated,
                result="succeeded",
                safe_metadata={"immediate": status in {"pending", "leased"}},
                correlation_id=str(updated["correlation_id"]),
            )
            connection.commit()
            return self._job(updated)

    def renew_lease(
        self,
        job_id: str,
        *,
        worker_id: str,
        worker_generation: int,
        lease_seconds: int = 30,
    ) -> OperationJobRecord:
        if not 1 <= lease_seconds <= 300:
            raise CoordinatorSchemaError(
                "The operation job lease duration is invalid.",
                code="operation_job_lease_duration_invalid",
            )
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        selected_worker = _uuid(worker_id, code="operation_job_worker_invalid")
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._leased_job(
                connection,
                job_id=selected_job,
                worker_id=selected_worker,
                worker_generation=worker_generation,
                allowed_statuses={"leased", "running"},
            )
            now_dt = _now_datetime()
            expires = _timestamp(now_dt + timedelta(seconds=lease_seconds))
            connection.execute(
                "UPDATE operation_jobs SET lease_expires_at=?,updated_at=? WHERE id=?",
                (expires, _timestamp(now_dt), selected_job),
            )
            connection.execute(
                """
                UPDATE job_leases SET expires_at=?,updated_at=?
                WHERE job_id=? AND worker_id=? AND worker_generation=? AND status='active'
                """,
                (
                    expires,
                    _timestamp(now_dt),
                    selected_job,
                    selected_worker,
                    worker_generation,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
            connection.commit()
            return self._job(updated)

    def recover_expired_jobs(
        self, *, messenger_account_id: str | None = None
    ) -> JobRecoverySummary:
        account_id = (
            _uuid(messenger_account_id, code="operation_job_account_invalid")
            if messenger_account_id
            else None
        )
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            summary = self._recover_expired(
                connection, account_id=account_id, now=_now_datetime()
            )
            connection.commit()
            return summary

    def get_job(self, job_id: str) -> OperationJobRecord:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        with self.database._connect() as connection:
            row = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (selected_job,)
            ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The operation job was not found.", code="operation_job_not_found"
            )
        return self._job(row)

    def attempts(self, job_id: str) -> tuple[JobAttemptRecord, ...]:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        with self.database._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_attempts WHERE job_id=? ORDER BY attempt_number",
                (selected_job,),
            ).fetchall()
        return tuple(self._attempt(row) for row in rows)

    def leases(self, job_id: str) -> tuple[JobLeaseRecord, ...]:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        with self.database._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_leases WHERE job_id=? ORDER BY acquired_at,id",
                (selected_job,),
            ).fetchall()
        return tuple(self._lease(row) for row in rows)

    def recipients(self, job_id: str) -> tuple[dict[str, object], ...]:
        selected_job = _uuid(job_id, code="operation_job_identifier_invalid")
        with self.database._connect() as connection:
            rows = connection.execute(
                """
                SELECT recipient_ref_hash,status,attempt_count,last_error_class,last_error_code
                FROM operation_job_recipients WHERE job_id=? ORDER BY recipient_ref_hash
                """,
                (selected_job,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    @staticmethod
    def _validate_schedule(value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise CoordinatorSchemaError(
                "The operation schedule is invalid.",
                code="operation_job_schedule_invalid",
            ) from exc
        if parsed.tzinfo is None:
            raise CoordinatorSchemaError(
                "The operation schedule requires a timezone.",
                code="operation_job_schedule_invalid",
            )
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")

    @staticmethod
    def _safe_code(value: str | None, code: str) -> str | None:
        if value is None:
            return None
        selected = str(value).strip().lower()
        if not _SAFE_CODE.fullmatch(selected):
            raise CoordinatorSchemaError("A safe operation code is invalid.", code=code)
        return selected

    @staticmethod
    def _require_actor_account(
        connection: sqlite3.Connection,
        *,
        actor_id: str,
        actor_global_role: str,
        account_id: str,
    ) -> sqlite3.Row:
        if actor_global_role not in {"admin", "user"}:
            raise CoordinatorSchemaError(
                "The operation job actor role is invalid.",
                code="operation_job_actor_role_invalid",
            )
        row = connection.execute(
            """
            SELECT ma.phone_account_id,ma.provider,ma.lifecycle_state,
                   pa.status AS phone_status,au.status AS actor_status,
                   au.global_role,pm.role AS membership_role,pm.status AS membership_status
            FROM messenger_accounts ma
            JOIN phone_accounts pa ON pa.id=ma.phone_account_id
            JOIN app_users au ON au.id=?
            LEFT JOIN phone_account_memberships pm
              ON pm.phone_account_id=ma.phone_account_id AND pm.app_user_id=au.id
            WHERE ma.id=?
            """,
            (actor_id, account_id),
        ).fetchone()
        allowed = bool(
            row is not None
            and str(row["actor_status"]) == "active"
            and str(row["global_role"]) == actor_global_role
            and str(row["phone_status"]) == "active"
            and str(row["lifecycle_state"]) != "archived"
            and (
                actor_global_role == "admin"
                or (
                    str(row["membership_status"] or "") == "active"
                    and str(row["membership_role"] or "") in {"owner", "operator"}
                )
            )
        )
        if not allowed:
            raise CoordinatorSchemaError(
                "The AppUser cannot create a job for this MessengerAccount.",
                code="operation_job_account_access_denied",
            )
        return row

    @staticmethod
    def _leased_job(
        connection: sqlite3.Connection,
        *,
        job_id: str,
        worker_id: str,
        worker_generation: int,
        allowed_statuses: set[str],
    ) -> sqlite3.Row:
        if not isinstance(worker_generation, int) or worker_generation <= 0:
            raise CoordinatorSchemaError(
                "The job worker generation is invalid.",
                code="operation_job_worker_generation_invalid",
            )
        row = connection.execute(
            "SELECT * FROM operation_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if row is None:
            raise CoordinatorSchemaError(
                "The operation job was not found.", code="operation_job_not_found"
            )
        if (
            str(row["status"]) not in allowed_statuses
            or str(row["lease_owner"] or "") != worker_id
            or int(row["lease_generation"] or 0) != worker_generation
            or not row["lease_expires_at"]
            or str(row["lease_expires_at"]) <= _timestamp()
        ):
            raise CoordinatorSchemaError(
                "The operation job lease is stale or belongs to another worker.",
                code="operation_job_lease_lost",
            )
        lease = connection.execute(
            """
            SELECT id,expires_at FROM job_leases
            WHERE job_id=? AND worker_id=? AND worker_generation=? AND status='active'
            """,
            (job_id, worker_id, worker_generation),
        ).fetchone()
        if lease is None or str(lease["expires_at"]) <= _timestamp():
            raise CoordinatorSchemaError(
                "The operation job lease journal is stale.",
                code="operation_job_lease_lost",
            )
        return row

    def _recover_expired(
        self,
        connection: sqlite3.Connection,
        *,
        account_id: str | None,
        now: datetime,
    ) -> JobRecoverySummary:
        timestamp = _timestamp(now)
        clause = "AND messenger_account_id=?" if account_id else ""
        parameters: tuple[Any, ...] = (timestamp, account_id) if account_id else (timestamp,)
        rows = connection.execute(
            f"""
            SELECT * FROM operation_jobs
            WHERE status IN ('leased','running') AND lease_expires_at<=? {clause}
            ORDER BY created_at,id
            """,
            parameters,
        ).fetchall()
        pending = cancelled = uncertain = 0
        for row in rows:
            job_id = str(row["id"])
            status = str(row["status"])
            connection.execute(
                """
                UPDATE job_leases SET status='expired',released_at=?,updated_at=?
                WHERE job_id=? AND status='active'
                """,
                (timestamp, timestamp, job_id),
            )
            if status == "running":
                next_status = "uncertain"
                uncertain += 1
                connection.execute(
                    """
                    UPDATE job_attempts SET result='uncertain',error_class='uncertain',
                        error_code='worker_lease_expired',completed_at=?,updated_at=?
                    WHERE job_id=? AND completed_at IS NULL
                    """,
                    (timestamp, timestamp, job_id),
                )
                connection.execute(
                    """
                    UPDATE operation_job_recipients SET status='uncertain',
                        last_error_class='uncertain',last_error_code='worker_lease_expired',updated_at=?
                    WHERE job_id=? AND status='running'
                    """,
                    (timestamp, job_id),
                )
            elif row["cancel_requested_at"] is not None:
                next_status = "cancelled"
                cancelled += 1
                connection.execute(
                    "UPDATE operation_job_recipients SET status='cancelled',updated_at=? WHERE job_id=? AND status='pending'",
                    (timestamp, job_id),
                )
            else:
                next_status = "pending"
                pending += 1
            connection.execute(
                """
                UPDATE operation_jobs
                SET status=?,completed_at=?,cancelled_at=?,last_error_class=?,
                    last_error_code=?,lease_owner=NULL,lease_generation=NULL,
                    lease_expires_at=NULL,updated_at=?
                WHERE id=?
                """,
                (
                    next_status,
                    timestamp if next_status in _TERMINAL else None,
                    timestamp if next_status == "cancelled" else row["cancelled_at"],
                    "uncertain" if next_status == "uncertain" else row["last_error_class"],
                    "worker_lease_expired" if next_status == "uncertain" else row["last_error_code"],
                    timestamp,
                    job_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM operation_jobs WHERE id=?", (job_id,)
            ).fetchone()
            self._audit(
                connection,
                action=f"operation_job.recovered_{next_status}",
                actor_id=None,
                actor_role=None,
                row=updated,
                result="succeeded",
                safe_metadata={"previous_status": status},
                correlation_id=str(updated["correlation_id"]),
            )
        return JobRecoverySummary(pending, cancelled, uncertain)

    @staticmethod
    def _job(row: sqlite3.Row) -> OperationJobRecord:
        return OperationJobRecord(
            job_id=str(row["id"]),
            actor_app_user_id=str(row["actor_app_user_id"]),
            phone_account_id=str(row["phone_account_id"]),
            messenger_account_id=str(row["messenger_account_id"]),
            provider=str(row["provider"]),
            operation=str(row["operation"]),
            status=str(row["status"]),
            idempotency_key=str(row["idempotency_key"]),
            safe_payload_ref=str(row["safe_payload_ref"]) if row["safe_payload_ref"] else None,
            correlation_id=str(row["correlation_id"]),
            attempt_count=int(row["attempt_count"]),
            scheduled_at=str(row["scheduled_at"]) if row["scheduled_at"] else None,
            lease_owner=str(row["lease_owner"]) if row["lease_owner"] else None,
            lease_generation=int(row["lease_generation"]) if row["lease_generation"] is not None else None,
            lease_expires_at=str(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            cancel_requested_at=str(row["cancel_requested_at"]) if row["cancel_requested_at"] else None,
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
            last_error_class=str(row["last_error_class"]) if row["last_error_class"] else None,
            last_error_code=str(row["last_error_code"]) if row["last_error_code"] else None,
        )

    @staticmethod
    def _attempt(row: sqlite3.Row) -> JobAttemptRecord:
        return JobAttemptRecord(
            attempt_id=str(row["id"]),
            job_id=str(row["job_id"]),
            attempt_number=int(row["attempt_number"]),
            worker_id=str(row["worker_id"]),
            worker_generation=int(row["worker_generation"]),
            lease_id=str(row["lease_id"]) if row["lease_id"] else None,
            correlation_id=str(row["correlation_id"]) if row["correlation_id"] else None,
            result=str(row["result"]) if row["result"] else None,
            error_class=str(row["error_class"]) if row["error_class"] else None,
            error_code=str(row["error_code"]) if row["error_code"] else None,
            retry_after_ms=int(row["retry_after_ms"]) if row["retry_after_ms"] is not None else None,
            started_at=str(row["started_at"]),
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
        )

    @staticmethod
    def _lease(row: sqlite3.Row) -> JobLeaseRecord:
        return JobLeaseRecord(
            lease_id=str(row["id"]),
            job_id=str(row["job_id"]),
            worker_id=str(row["worker_id"]),
            worker_generation=int(row["worker_generation"]),
            correlation_id=str(row["correlation_id"]),
            status=str(row["status"]),
            acquired_at=str(row["acquired_at"]),
            expires_at=str(row["expires_at"]),
            released_at=str(row["released_at"]) if row["released_at"] else None,
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        *,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        row: Any,
        result: str,
        safe_metadata: dict[str, object],
        correlation_id: str,
    ) -> None:
        CoordinatorDatabase._append_audit(
            connection,
            actor_type="app_user" if actor_id else "system",
            actor_app_user_id=actor_id,
            actor_global_role=actor_role if actor_id else None,
            action=action,
            target_type="operation_job",
            target_id=str(row["id"]),
            phone_account_id=str(row["phone_account_id"]),
            messenger_account_id=str(row["messenger_account_id"]),
            provider=str(row["provider"]),
            result=result,
            reason_code=None,
            safe_metadata=safe_metadata,
            request_id=correlation_id,
        )


__all__ = [
    "CreateJobResult",
    "JobAttemptRecord",
    "JobLeaseRecord",
    "JobRecoverySummary",
    "OperationJobRecord",
    "PersistentOperationJobService",
]

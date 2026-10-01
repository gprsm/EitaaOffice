"""Persisted per-account execution limits, backoff, and circuit breaking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
import re
import sqlite3
from uuid import UUID, uuid4

from ...errors import CoordinatorSchemaError
from .store import CoordinatorDatabase


_OPERATION_SCOPE = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")
_SAFE_ERROR = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")


class ExecutionErrorClass(str, Enum):
    TRANSIENT = "transient"
    AUTH = "auth"
    PRIVACY = "privacy"
    PERMANENT = "permanent"
    UNCERTAIN = "uncertain"
    INTERNAL = "internal"


def _uuid(value: str, *, code: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorSchemaError(
            "An execution-policy identifier is invalid.", code=code
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise CoordinatorSchemaError(
            "An execution-policy identifier is invalid.", code=code
        )
    return value


def _utc(value: datetime | None = None) -> datetime:
    selected = value or datetime.now(timezone.utc)
    if selected.tzinfo is None:
        raise CoordinatorSchemaError(
            "Execution-policy time requires a timezone.",
            code="execution_policy_time_invalid",
        )
    return selected.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="milliseconds")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ClassifiedFailure:
    error_class: ExecutionErrorClass
    error_code: str
    retry_after_ms: int | None

    @property
    def retryable(self) -> bool:
        return self.error_class in {
            ExecutionErrorClass.TRANSIENT,
            ExecutionErrorClass.INTERNAL,
        }


@dataclass(frozen=True, slots=True)
class ExecutionPermit:
    allowed: bool
    messenger_account_id: str
    provider: str
    operation_scope: str
    claim_id: str
    retry_after_ms: int | None
    blocked_reason: str | None
    circuit_state: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "messenger_account_id": self.messenger_account_id,
            "provider": self.provider,
            "operation_scope": self.operation_scope,
            "claim_id": self.claim_id,
            "retry_after_ms": self.retry_after_ms,
            "blocked_reason": self.blocked_reason,
            "circuit_state": self.circuit_state,
        }


@dataclass(frozen=True, slots=True)
class FailureDecision:
    messenger_account_id: str
    operation_scope: str
    error_class: ExecutionErrorClass
    error_code: str
    retryable: bool
    retry_after_ms: int | None
    circuit_state: str
    job_result: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "messenger_account_id": self.messenger_account_id,
            "operation_scope": self.operation_scope,
            "error_class": self.error_class.value,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "retry_after_ms": self.retry_after_ms,
            "circuit_state": self.circuit_state,
            "job_result": self.job_result,
        }


def classify_failure(
    error_code: str,
    *,
    http_status: int | None = None,
    retry_after_ms: int | None = None,
    effect_may_have_occurred: bool = False,
    explicit_class: ExecutionErrorClass | str | None = None,
) -> ClassifiedFailure:
    """Classify only safe codes/status; raw provider errors never enter storage."""

    code = str(error_code or "internal_error").strip().lower()
    if not _SAFE_ERROR.fullmatch(code):
        code = "internal_error"
    if retry_after_ms is not None and (
        not isinstance(retry_after_ms, int) or not 0 <= retry_after_ms <= 86_400_000
    ):
        raise CoordinatorSchemaError(
            "The provider retry_after value is invalid.",
            code="execution_policy_retry_after_invalid",
        )
    if explicit_class is not None:
        try:
            selected = (
                explicit_class
                if isinstance(explicit_class, ExecutionErrorClass)
                else ExecutionErrorClass(str(explicit_class))
            )
        except ValueError as exc:
            raise CoordinatorSchemaError(
                "The execution error class is invalid.",
                code="execution_policy_error_class_invalid",
            ) from exc
    elif effect_may_have_occurred:
        selected = ExecutionErrorClass.UNCERTAIN
    else:
        tokens = set(code.replace("-", "_").replace(".", "_").split("_"))
        if (
            http_status == 401
            or tokens & {"auth", "unauthorized", "session", "login", "otp", "password"}
            or code == "not_authorized"
            or code.endswith("_not_authorized")
        ):
            selected = ExecutionErrorClass.AUTH
        elif http_status == 403 or tokens & {"privacy", "forbidden", "permission", "blocked"}:
            selected = ExecutionErrorClass.PRIVACY
        elif (
            http_status == 429
            or (http_status is not None and 500 <= http_status <= 599)
            or tokens & {"timeout", "connection", "unavailable", "busy", "server", "flood", "rate", "throttle"}
        ):
            selected = ExecutionErrorClass.TRANSIENT
        elif (
            http_status in {400, 404, 409, 410, 422}
            or tokens & {"invalid", "unsupported", "notfound", "badrequest"}
            or "not_found" in code
        ):
            selected = ExecutionErrorClass.PERMANENT
        else:
            selected = ExecutionErrorClass.INTERNAL
    return ClassifiedFailure(selected, code, retry_after_ms)


class AccountExecutionPolicyService:
    """Token bucket and circuit state keyed by one exact account and operation."""

    def __init__(
        self,
        database: CoordinatorDatabase,
        *,
        default_capacity: int = 5,
        default_refill_per_second: float = 1.0,
        circuit_failure_threshold: int = 5,
    ) -> None:
        if not 1 <= default_capacity <= 10_000:
            raise ValueError("default_capacity must be between 1 and 10000")
        if not 0 < default_refill_per_second <= 10_000:
            raise ValueError("default_refill_per_second must be positive")
        if not 2 <= circuit_failure_threshold <= 100:
            raise ValueError("circuit_failure_threshold must be between 2 and 100")
        self.database = database
        self.default_capacity = default_capacity
        self.default_refill_per_second = float(default_refill_per_second)
        self.circuit_failure_threshold = circuit_failure_threshold
        self.database.initialize()

    def acquire(
        self,
        *,
        messenger_account_id: str,
        operation_scope: str,
        claim_id: str | None = None,
        cost: float = 1.0,
        now: datetime | None = None,
    ) -> ExecutionPermit:
        account_id = _uuid(
            messenger_account_id, code="execution_policy_account_invalid"
        )
        operation = self._operation(operation_scope)
        selected_claim = _uuid(
            claim_id or str(uuid4()), code="execution_policy_claim_invalid"
        )
        if not 0 < cost <= self.default_capacity:
            raise CoordinatorSchemaError(
                "The execution-policy token cost is invalid.",
                code="execution_policy_cost_invalid",
            )
        selected_now = _utc(now)
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            provider = self._account_provider(connection, account_id)
            row = self._state_row(
                connection,
                account_id=account_id,
                provider=provider,
                operation=operation,
                now=selected_now,
            )
            state = str(row["circuit_state"])
            retry_not_before = _parse(row["retry_not_before"])
            circuit_until = _parse(row["circuit_open_until"])
            if state == "open":
                if circuit_until is None:
                    connection.commit()
                    return self._permit(
                        False, account_id, provider, operation, selected_claim,
                        None, "circuit_manual_reset_required", "open",
                    )
                effective_until = max(
                    item for item in (circuit_until, retry_not_before) if item is not None
                )
                if effective_until > selected_now:
                    delay = self._milliseconds(effective_until - selected_now)
                    connection.commit()
                    return self._permit(
                        False, account_id, provider, operation, selected_claim,
                        delay, "circuit_open", "open",
                    )
                connection.execute(
                    """
                    UPDATE account_execution_limits
                    SET circuit_state='half_open',half_open_claim_id=?,updated_at=?
                    WHERE messenger_account_id=? AND operation_scope=?
                    """,
                    (selected_claim, _stamp(selected_now), account_id, operation),
                )
                state = "half_open"
            elif state == "half_open":
                current_claim = str(row["half_open_claim_id"] or "")
                if current_claim and current_claim != selected_claim:
                    connection.commit()
                    return self._permit(
                        False, account_id, provider, operation, selected_claim,
                        1000, "half_open_probe_in_progress", "half_open",
                    )
                if not current_claim:
                    connection.execute(
                        """
                        UPDATE account_execution_limits SET half_open_claim_id=?,updated_at=?
                        WHERE messenger_account_id=? AND operation_scope=?
                        """,
                        (selected_claim, _stamp(selected_now), account_id, operation),
                    )
            if retry_not_before and retry_not_before > selected_now and state != "half_open":
                connection.commit()
                return self._permit(
                    False, account_id, provider, operation, selected_claim,
                    self._milliseconds(retry_not_before - selected_now),
                    "retry_after", state,
                )
            elapsed = max(0.0, (selected_now - _parse(str(row["last_refill_at"]))).total_seconds())
            available = min(
                float(row["capacity"]),
                float(row["available_tokens"]) + elapsed * float(row["refill_per_second"]),
            )
            if available < cost and state != "half_open":
                delay = max(
                    1,
                    math.ceil((cost - available) / float(row["refill_per_second"]) * 1000),
                )
                connection.execute(
                    """
                    UPDATE account_execution_limits SET available_tokens=?,last_refill_at=?,updated_at=?
                    WHERE messenger_account_id=? AND operation_scope=?
                    """,
                    (available, _stamp(selected_now), _stamp(selected_now), account_id, operation),
                )
                connection.commit()
                return self._permit(
                    False, account_id, provider, operation, selected_claim,
                    delay, "rate_limited", state,
                )
            connection.execute(
                """
                UPDATE account_execution_limits
                SET available_tokens=?,last_refill_at=?,updated_at=?
                WHERE messenger_account_id=? AND operation_scope=?
                """,
                (max(0.0, available - cost), _stamp(selected_now), _stamp(selected_now), account_id, operation),
            )
            connection.commit()
            return self._permit(
                True, account_id, provider, operation, selected_claim,
                None, None, state,
            )

    def record_success(
        self,
        *,
        messenger_account_id: str,
        operation_scope: str,
        claim_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        self._record(
            messenger_account_id=messenger_account_id,
            operation_scope=operation_scope,
            claim_id=claim_id,
            failure=None,
            now=now,
        )

    def record_failure(
        self,
        *,
        messenger_account_id: str,
        operation_scope: str,
        failure: ClassifiedFailure,
        claim_id: str | None = None,
        now: datetime | None = None,
    ) -> FailureDecision:
        decision = self._record(
            messenger_account_id=messenger_account_id,
            operation_scope=operation_scope,
            claim_id=claim_id,
            failure=failure,
            now=now,
        )
        assert decision is not None
        return decision

    def state(
        self, *, messenger_account_id: str, operation_scope: str
    ) -> dict[str, object] | None:
        account_id = _uuid(
            messenger_account_id, code="execution_policy_account_invalid"
        )
        operation = self._operation(operation_scope)
        with self.database._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM account_execution_limits
                WHERE messenger_account_id=? AND operation_scope=?
                """,
                (account_id, operation),
            ).fetchone()
        if row is None:
            return None
        return {
            "messenger_account_id": account_id,
            "provider": str(row["provider"]),
            "operation_scope": operation,
            "capacity": int(row["capacity"]),
            "refill_per_second": float(row["refill_per_second"]),
            "available_tokens": float(row["available_tokens"]),
            "retry_not_before": str(row["retry_not_before"]) if row["retry_not_before"] else None,
            "circuit_state": str(row["circuit_state"]),
            "consecutive_failures": int(row["consecutive_failures"]),
            "circuit_open_until": str(row["circuit_open_until"]) if row["circuit_open_until"] else None,
            "half_open_claim_present": row["half_open_claim_id"] is not None,
            "last_error_class": str(row["last_error_class"]) if row["last_error_class"] else None,
            "last_error_code": str(row["last_error_code"]) if row["last_error_code"] else None,
        }

    def read_only_snapshot(
        self,
        *,
        messenger_account_id: str,
        operation_scope: str,
        now: datetime | None = None,
        cost: float = 1.0,
    ) -> dict[str, object] | None:
        """Honest no-write snapshot of one (account, operation) limit.

        Computes the token refill up to ``now`` without acquiring, without
        mutating any row (``_state_row`` never runs), without touching the
        circuit state and without any worker/network call. A missing row
        means no local limit has ever been applied — reported as ``None``
        and never as unlimited capacity. This is a snapshot only: a later
        real acquire can still refuse (preflight race) or the provider can
        refuse for its own reasons.
        """
        account_id = _uuid(
            messenger_account_id, code="execution_policy_account_invalid"
        )
        operation = self._operation(operation_scope)
        selected_now = _utc(now)
        if not 0 < cost <= self.default_capacity:
            raise CoordinatorSchemaError(
                "The execution-policy token cost is invalid.",
                code="execution_policy_cost_invalid",
            )
        with self.database._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM account_execution_limits
                WHERE messenger_account_id=? AND operation_scope=?
                """,
                (account_id, operation),
            ).fetchone()
        if row is None:
            return None
        available = min(
            float(row["capacity"]),
            float(row["available_tokens"])
            + max(
                0.0,
                (selected_now - _parse(str(row["last_refill_at"]))).total_seconds(),
            )
            * float(row["refill_per_second"]),
        )
        retry_not_before = _parse(row["retry_not_before"])
        circuit_until = _parse(row["circuit_open_until"])
        circuit_state = str(row["circuit_state"])
        blocked_reason: str | None = None
        retry_after_ms: int | None = None
        if circuit_state == "open":
            effective_until = max(
                item for item in (circuit_until, retry_not_before) if item is not None
            )
            if effective_until > selected_now:
                blocked_reason = "circuit_open"
                retry_after_ms = self._milliseconds(effective_until - selected_now)
        elif circuit_state == "half_open":
            blocked_reason = "half_open_probe_in_progress"
            retry_after_ms = 1000
        elif retry_not_before is not None and retry_not_before > selected_now:
            blocked_reason = "retry_after"
            retry_after_ms = self._milliseconds(retry_not_before - selected_now)
        elif available < cost:
            blocked_reason = "rate_limited"
            retry_after_ms = max(
                1,
                math.ceil((cost - available) / float(row["refill_per_second"]) * 1000),
            )
        return {
            "messenger_account_id": account_id,
            "provider": str(row["provider"]),
            "operation_scope": operation,
            "available_tokens": available,
            "capacity": int(row["capacity"]),
            "circuit_state": circuit_state,
            "blocked_reason": blocked_reason,
            "retry_after_ms": retry_after_ms,
            "retry_not_before": (
                str(row["retry_not_before"]) if row["retry_not_before"] else None
            ),
            "last_error_class": (
                str(row["last_error_class"]) if row["last_error_class"] else None
            ),
            "last_error_code": (
                str(row["last_error_code"]) if row["last_error_code"] else None
            ),
            "updated_at": str(row["updated_at"]),
        }

    def _record(
        self,
        *,
        messenger_account_id: str,
        operation_scope: str,
        claim_id: str | None,
        failure: ClassifiedFailure | None,
        now: datetime | None,
    ) -> FailureDecision | None:
        account_id = _uuid(
            messenger_account_id, code="execution_policy_account_invalid"
        )
        operation = self._operation(operation_scope)
        selected_claim = (
            _uuid(claim_id, code="execution_policy_claim_invalid") if claim_id else None
        )
        selected_now = _utc(now)
        with self.database._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            provider = self._account_provider(connection, account_id)
            row = self._state_row(
                connection,
                account_id=account_id,
                provider=provider,
                operation=operation,
                now=selected_now,
            )
            if str(row["circuit_state"]) == "half_open":
                active_claim = str(row["half_open_claim_id"] or "")
                if not selected_claim or active_claim != selected_claim:
                    raise CoordinatorSchemaError(
                        "The half-open circuit result has a stale claim.",
                        code="execution_policy_probe_claim_lost",
                    )
            timestamp = _stamp(selected_now)
            if failure is None:
                connection.execute(
                    """
                    UPDATE account_execution_limits
                    SET retry_not_before=NULL,circuit_state='closed',consecutive_failures=0,
                        circuit_open_until=NULL,half_open_claim_id=NULL,last_error_class=NULL,
                        last_error_code=NULL,updated_at=?
                    WHERE messenger_account_id=? AND operation_scope=?
                    """,
                    (timestamp, account_id, operation),
                )
                self._audit(
                    connection, account_id, provider, operation,
                    action="execution_policy.success", error_class=None,
                    error_code=None, retry_after_ms=None,
                )
                connection.commit()
                return None
            error_class = failure.error_class
            failures = int(row["consecutive_failures"])
            retryable = failure.retryable
            retry_ms: int | None = None
            circuit_state = "closed"
            circuit_until: datetime | None = None
            if error_class in {ExecutionErrorClass.TRANSIENT, ExecutionErrorClass.INTERNAL}:
                failures += 1
                base = 500 if error_class is ExecutionErrorClass.TRANSIENT else 1000
                retry_ms = min(60_000, base * (2 ** min(failures - 1, 10)))
                if failure.retry_after_ms is not None:
                    retry_ms = max(retry_ms, failure.retry_after_ms)
                if (
                    failures >= self.circuit_failure_threshold
                    or str(row["circuit_state"]) == "half_open"
                ):
                    circuit_state = "open"
                    open_ms = min(
                        300_000,
                        30_000 * (2 ** min(max(0, failures - self.circuit_failure_threshold), 4)),
                    )
                    retry_ms = max(retry_ms, open_ms)
                    circuit_until = selected_now + timedelta(milliseconds=open_ms)
            elif error_class in {ExecutionErrorClass.AUTH, ExecutionErrorClass.PRIVACY}:
                failures += 1
                circuit_state = "open"
                retryable = False
            elif error_class is ExecutionErrorClass.UNCERTAIN:
                failures += 1
                circuit_state = "open"
                retryable = False
            else:
                failures = 0
                retryable = False
            retry_not_before = (
                selected_now + timedelta(milliseconds=retry_ms)
                if retry_ms is not None
                else circuit_until
            )
            connection.execute(
                """
                UPDATE account_execution_limits
                SET retry_not_before=?,circuit_state=?,consecutive_failures=?,
                    circuit_open_until=?,half_open_claim_id=NULL,last_error_class=?,
                    last_error_code=?,updated_at=?
                WHERE messenger_account_id=? AND operation_scope=?
                """,
                (
                    _stamp(retry_not_before) if retry_not_before else None,
                    circuit_state,
                    failures,
                    _stamp(circuit_until) if circuit_until else None,
                    error_class.value,
                    failure.error_code,
                    timestamp,
                    account_id,
                    operation,
                ),
            )
            self._audit(
                connection,
                account_id,
                provider,
                operation,
                action="execution_policy.failure",
                error_class=error_class,
                error_code=failure.error_code,
                retry_after_ms=retry_ms,
            )
            connection.commit()
            return FailureDecision(
                messenger_account_id=account_id,
                operation_scope=operation,
                error_class=error_class,
                error_code=failure.error_code,
                retryable=retryable,
                retry_after_ms=retry_ms if retryable else None,
                circuit_state=circuit_state,
                job_result="uncertain" if error_class is ExecutionErrorClass.UNCERTAIN else "failed",
            )

    def _state_row(
        self,
        connection: sqlite3.Connection,
        *,
        account_id: str,
        provider: str,
        operation: str,
        now: datetime,
    ) -> sqlite3.Row:
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
                account_id,
                provider,
                operation,
                self.default_capacity,
                self.default_refill_per_second,
                float(self.default_capacity),
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
            (account_id, operation),
        ).fetchone()
        assert row is not None
        if str(row["provider"]) != provider:
            raise CoordinatorSchemaError(
                "The execution-policy account provider changed unexpectedly.",
                code="execution_policy_provider_mismatch",
            )
        return row

    @staticmethod
    def _account_provider(connection: sqlite3.Connection, account_id: str) -> str:
        row = connection.execute(
            """
            SELECT ma.provider,ma.lifecycle_state,pa.status AS phone_status
            FROM messenger_accounts ma
            JOIN phone_accounts pa ON pa.id=ma.phone_account_id
            WHERE ma.id=?
            """,
            (account_id,),
        ).fetchone()
        if (
            row is None
            or str(row["lifecycle_state"]) == "archived"
            or str(row["phone_status"]) != "active"
        ):
            raise CoordinatorSchemaError(
                "The execution-policy MessengerAccount is unavailable.",
                code="execution_policy_account_unavailable",
            )
        return str(row["provider"])

    @staticmethod
    def _operation(value: str) -> str:
        selected = str(value or "").strip().lower()
        if not _OPERATION_SCOPE.fullmatch(selected):
            raise CoordinatorSchemaError(
                "The execution-policy operation scope is invalid.",
                code="execution_policy_operation_invalid",
            )
        return selected

    @staticmethod
    def _milliseconds(delta: timedelta) -> int:
        return max(1, math.ceil(delta.total_seconds() * 1000))

    @staticmethod
    def _permit(
        allowed: bool,
        account_id: str,
        provider: str,
        operation: str,
        claim_id: str,
        retry_after_ms: int | None,
        blocked_reason: str | None,
        circuit_state: str,
    ) -> ExecutionPermit:
        return ExecutionPermit(
            allowed,
            account_id,
            provider,
            operation,
            claim_id,
            retry_after_ms,
            blocked_reason,
            circuit_state,
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        account_id: str,
        provider: str,
        operation: str,
        *,
        action: str,
        error_class: ExecutionErrorClass | None,
        error_code: str | None,
        retry_after_ms: int | None,
    ) -> None:
        CoordinatorDatabase._append_audit(
            connection,
            actor_type="system",
            actor_app_user_id=None,
            actor_global_role=None,
            action=action,
            target_type="account_execution_limit",
            target_id=None,
            phone_account_id=None,
            messenger_account_id=account_id,
            provider=provider,
            result="recorded",
            reason_code=error_code,
            safe_metadata={
                "operation_scope": operation,
                "error_class": error_class.value if error_class else None,
                "retry_after_ms": retry_after_ms,
            },
        )


__all__ = [
    "AccountExecutionPolicyService",
    "ClassifiedFailure",
    "ExecutionErrorClass",
    "ExecutionPermit",
    "FailureDecision",
    "classify_failure",
]

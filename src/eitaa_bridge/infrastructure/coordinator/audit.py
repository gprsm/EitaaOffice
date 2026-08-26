"""Authorized, tamper-evident Coordinator audit query and JSONL export."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import UUID, uuid4

from ...errors import CoordinatorSchemaError
from ..diagnostics.redaction import redact
from .store import CoordinatorDatabase


_ACTION_PREFIX = re.compile(r"^[a-z][a-z0-9_.-]{0,80}$")
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_UNSAFE_KEYS = ("password", "secret", "token", "otp", "ciphertext", "access_hash", "raw_phone")


def _uuid(value: str, *, code: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise CoordinatorSchemaError("An audit identifier is invalid.", code=code) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise CoordinatorSchemaError("An audit identifier is invalid.", code=code)
    return value


def _time(value: str | None, *, code: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise CoordinatorSchemaError("An audit time filter is invalid.", code=code) from exc
    if parsed.tzinfo is None:
        raise CoordinatorSchemaError("An audit time filter requires a timezone.", code=code)
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _safe_json(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if depth > 10:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        selected = redact(value, key=key)
        return selected[:500] if isinstance(selected, str) else selected
    if isinstance(value, list):
        return [_safe_json(item, key=key, depth=depth + 1) for item in value[:100]]
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            selected = str(key)[:80]
            if any(part in selected.casefold() for part in _UNSAFE_KEYS):
                safe[selected] = "[redacted]"
            else:
                safe[selected] = _safe_json(item, key=selected, depth=depth + 1)
        return safe
    return str(type(value).__name__)


@dataclass(frozen=True, slots=True)
class SafeAuditEvent:
    event_id: str
    at: str
    actor_type: str
    actor_app_user_id: str | None
    actor_global_role: str | None
    action: str
    target_type: str
    target_id: str | None
    messenger_account_id: str | None
    provider: str | None
    result: str
    reason_code: str | None
    correlation_id: str | None
    safe_metadata: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "at": self.at,
            "actor_type": self.actor_type,
            "actor_app_user_id": self.actor_app_user_id,
            "actor_global_role": self.actor_global_role,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "messenger_account_id": self.messenger_account_id,
            "provider": self.provider,
            "result": self.result,
            "reason_code": self.reason_code,
            "correlation_id": self.correlation_id,
            "safe_metadata": self.safe_metadata,
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
        }


@dataclass(frozen=True, slots=True)
class AuditPage:
    events: tuple[SafeAuditEvent, ...]
    next_cursor: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "events": [event.safe_summary() for event in self.events],
            "next_cursor": self.next_cursor,
        }


@dataclass(frozen=True, slots=True)
class AuditVerificationReport:
    valid: bool
    event_count: int
    first_invalid_event_id: str | None

    def safe_summary(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "event_count": self.event_count,
            "first_invalid_event_id": self.first_invalid_event_id,
        }


@dataclass(frozen=True, slots=True)
class AuditExportResult:
    path: Path
    event_count: int
    sha256: str

    def safe_summary(self) -> dict[str, object]:
        return {
            "file_name": self.path.name,
            "event_count": self.event_count,
            "sha256": self.sha256,
        }


class SafeCoordinatorAuditService:
    def __init__(self, database: CoordinatorDatabase) -> None:
        self.database = database
        self.database.initialize()

    def query(
        self,
        *,
        app_user_id: str,
        global_role: str,
        messenger_account_id: str | None = None,
        provider: str | None = None,
        action_prefix: str | None = None,
        result: str | None = None,
        correlation_id: str | None = None,
        from_at: str | None = None,
        to_at: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> AuditPage:
        actor_id = _uuid(app_user_id, code="audit_actor_invalid")
        account_id = (
            _uuid(messenger_account_id, code="audit_account_invalid")
            if messenger_account_id
            else None
        )
        selected_correlation = (
            _uuid(correlation_id, code="audit_correlation_invalid")
            if correlation_id
            else None
        )
        selected_provider = str(provider).strip().lower() if provider else None
        if selected_provider is not None and not _PROVIDER_ID.fullmatch(selected_provider):
            raise CoordinatorSchemaError("The audit provider filter is invalid.", code="audit_provider_invalid")
        selected_action = str(action_prefix).strip().lower() if action_prefix else None
        if selected_action and not _ACTION_PREFIX.fullmatch(selected_action):
            raise CoordinatorSchemaError("The audit action filter is invalid.", code="audit_action_invalid")
        selected_result = str(result).strip().lower() if result else None
        if selected_result and not _ACTION_PREFIX.fullmatch(selected_result):
            raise CoordinatorSchemaError("The audit result filter is invalid.", code="audit_result_invalid")
        if not 1 <= limit <= 1000:
            raise CoordinatorSchemaError("The audit page limit is invalid.", code="audit_limit_invalid")
        start = _time(from_at, code="audit_from_invalid")
        end = _time(to_at, code="audit_to_invalid")
        cursor_at, cursor_id = self._decode_cursor(cursor) if cursor else (None, None)

        with self.database._connect() as connection:
            role = self._authorize_actor(
                connection,
                actor_id=actor_id,
                global_role=global_role,
                account_id=account_id,
            )
            if selected_provider is not None:
                registered = connection.execute(
                    "SELECT 1 FROM provider_registrations WHERE provider=?",
                    (selected_provider,),
                ).fetchone()
                if registered is None:
                    raise CoordinatorSchemaError(
                        "The audit provider filter is invalid.",
                        code="audit_provider_invalid",
                    )
            conditions: list[str] = []
            parameters: list[object] = []
            if role != "admin":
                conditions.append(
                    """
                    (
                        ae.actor_app_user_id=?
                        OR (
                            ae.target_type='operation_job'
                            AND EXISTS(
                                SELECT 1 FROM operation_jobs oj
                                WHERE oj.id=ae.target_id AND oj.actor_app_user_id=?
                            )
                        )
                    )
                    """
                )
                parameters.extend((actor_id, actor_id))
            if account_id:
                conditions.append("ae.messenger_account_id=?")
                parameters.append(account_id)
            if selected_provider:
                conditions.append("ae.provider=?")
                parameters.append(selected_provider)
            if selected_action:
                conditions.append("ae.action LIKE ? ESCAPE '\\'")
                parameters.append(selected_action.replace("%", "\\%").replace("_", "\\_") + "%")
            if selected_result:
                conditions.append("ae.result=?")
                parameters.append(selected_result)
            if selected_correlation:
                conditions.append("ae.request_id=?")
                parameters.append(selected_correlation)
            if start:
                conditions.append("ae.at>=?")
                parameters.append(start)
            if end:
                conditions.append("ae.at<=?")
                parameters.append(end)
            if cursor_at and cursor_id:
                conditions.append("(ae.at<? OR (ae.at=? AND ae.id<?))")
                parameters.extend((cursor_at, cursor_at, cursor_id))
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            rows = connection.execute(
                f"""
                SELECT ae.* FROM audit_events ae
                {where}
                ORDER BY ae.at DESC,ae.id DESC
                LIMIT ?
                """,
                (*parameters, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        selected_rows = rows[:limit]
        events = tuple(self._event(row) for row in selected_rows)
        next_cursor = (
            self._encode_cursor(str(selected_rows[-1]["at"]), str(selected_rows[-1]["id"]))
            if has_more and selected_rows
            else None
        )
        return AuditPage(events, next_cursor)

    def verify_chain(self) -> AuditVerificationReport:
        with self.database._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY rowid"
            ).fetchall()
        previous: str | None = None
        for index, row in enumerate(rows):
            if (str(row["previous_event_hash"]) if row["previous_event_hash"] else None) != previous:
                return AuditVerificationReport(False, index, str(row["id"]))
            payload = {
                "id": str(row["id"]),
                "schema_version": int(row["schema_version"]),
                "at": str(row["at"]),
                "actor_type": str(row["actor_type"]),
                "actor_app_user_id": str(row["actor_app_user_id"]) if row["actor_app_user_id"] else None,
                "actor_global_role": str(row["actor_global_role"]) if row["actor_global_role"] else None,
                "action": str(row["action"]),
                "target_type": str(row["target_type"]),
                "target_id": str(row["target_id"]) if row["target_id"] else None,
                "phone_account_id": str(row["phone_account_id"]) if row["phone_account_id"] else None,
                "messenger_account_id": str(row["messenger_account_id"]) if row["messenger_account_id"] else None,
                "provider": str(row["provider"]) if row["provider"] else None,
                "result": str(row["result"]),
                "reason_code": str(row["reason_code"]) if row["reason_code"] else None,
                "request_id": str(row["request_id"]) if row["request_id"] else None,
                "safe_metadata_json": str(row["safe_metadata_json"]),
                "previous_event_hash": previous,
            }
            stored = str(row["event_hash"])
            candidates = [payload]
            # Early coordinator builds omitted the optional request_id key entirely
            # when it was null. Preserve verification of those immutable histories;
            # a non-null request id must always use the current contract.
            if payload["request_id"] is None:
                candidates.append({key: value for key, value in payload.items() if key != "request_id"})
            if not any(self._canonical_hash(candidate) == stored for candidate in candidates):
                return AuditVerificationReport(False, index, str(row["id"]))
            previous = stored
        return AuditVerificationReport(True, len(rows), None)

    @staticmethod
    def _canonical_hash(payload: dict[str, object]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def export_jsonl(
        self,
        *,
        app_user_id: str,
        global_role: str,
        output_directory: str | Path,
        messenger_account_id: str | None = None,
        action_prefix: str | None = None,
        max_events: int = 10_000,
    ) -> AuditExportResult:
        if not 1 <= max_events <= 100_000:
            raise CoordinatorSchemaError("The audit export limit is invalid.", code="audit_export_limit_invalid")
        root = Path(output_directory).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / f"audit-export-{uuid4()}.jsonl").resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise CoordinatorSchemaError("The audit export path is invalid.", code="audit_export_path_invalid") from exc
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="audit-export-", suffix=".tmp", dir=root
        )
        digest = hashlib.sha256()
        count = 0
        cursor: str | None = None
        try:
            with os.fdopen(descriptor, "wb") as stream:
                while count < max_events:
                    page = self.query(
                        app_user_id=app_user_id,
                        global_role=global_role,
                        messenger_account_id=messenger_account_id,
                        action_prefix=action_prefix,
                        cursor=cursor,
                        limit=min(1000, max_events - count),
                    )
                    if not page.events:
                        break
                    for event in page.events:
                        line = (
                            json.dumps(
                                event.safe_summary(),
                                ensure_ascii=True,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        stream.write(line)
                        digest.update(line)
                        count += 1
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return AuditExportResult(target, count, digest.hexdigest())

    @staticmethod
    def _authorize_actor(
        connection: Any,
        *,
        actor_id: str,
        global_role: str,
        account_id: str | None,
    ) -> str:
        if global_role not in {"admin", "user"}:
            raise CoordinatorSchemaError("The audit actor role is invalid.", code="audit_actor_role_invalid")
        actor = connection.execute(
            "SELECT status,global_role FROM app_users WHERE id=?", (actor_id,)
        ).fetchone()
        if actor is None or str(actor["status"]) != "active" or str(actor["global_role"]) != global_role:
            raise CoordinatorSchemaError("The audit actor is inactive.", code="audit_actor_inactive")
        if account_id and global_role != "admin":
            allowed = connection.execute(
                """
                SELECT 1 FROM messenger_accounts ma
                JOIN phone_account_memberships pm
                  ON pm.phone_account_id=ma.phone_account_id
                WHERE ma.id=? AND pm.app_user_id=? AND pm.status='active'
                """,
                (account_id, actor_id),
            ).fetchone()
            if allowed is None:
                raise CoordinatorSchemaError("The audit account is not accessible.", code="audit_account_access_denied")
        return global_role

    @staticmethod
    def _event(row: Any) -> SafeAuditEvent:
        try:
            metadata = json.loads(str(row["safe_metadata_json"]))
        except json.JSONDecodeError:
            metadata = {"metadata_error": "invalid_json"}
        return SafeAuditEvent(
            event_id=str(row["id"]),
            at=str(row["at"]),
            actor_type=str(row["actor_type"]),
            actor_app_user_id=str(row["actor_app_user_id"]) if row["actor_app_user_id"] else None,
            actor_global_role=str(row["actor_global_role"]) if row["actor_global_role"] else None,
            action=str(row["action"]),
            target_type=str(row["target_type"]),
            target_id=str(row["target_id"]) if row["target_id"] else None,
            messenger_account_id=str(row["messenger_account_id"]) if row["messenger_account_id"] else None,
            provider=str(row["provider"]) if row["provider"] else None,
            result=str(row["result"]),
            reason_code=str(row["reason_code"]) if row["reason_code"] else None,
            correlation_id=str(row["request_id"]) if row["request_id"] else None,
            safe_metadata=_safe_json(metadata) if isinstance(metadata, dict) else {},
            previous_event_hash=str(row["previous_event_hash"]) if row["previous_event_hash"] else None,
            event_hash=str(row["event_hash"]),
        )

    @staticmethod
    def _encode_cursor(at: str, event_id: str) -> str:
        payload = json.dumps({"at": at, "id": event_id}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, str]:
        try:
            selected = str(cursor).strip()
            padding = "=" * (-len(selected) % 4)
            payload = json.loads(base64.urlsafe_b64decode(selected + padding).decode("utf-8"))
            at = _time(str(payload["at"]), code="audit_cursor_invalid")
            event_id = _uuid(str(payload["id"]), code="audit_cursor_invalid")
            assert at is not None
            return at, event_id
        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            binascii.Error,
            AssertionError,
        ) as exc:
            raise CoordinatorSchemaError("The audit cursor is invalid.", code="audit_cursor_invalid") from exc


__all__ = [
    "AuditExportResult",
    "AuditPage",
    "AuditVerificationReport",
    "SafeAuditEvent",
    "SafeCoordinatorAuditService",
]

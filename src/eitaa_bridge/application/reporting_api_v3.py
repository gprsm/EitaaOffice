"""HTTP handlers for /api/v3/reporting/* — phase 2 transactional core.

Pure handler functions returning (status, payload, headers) tuples; api.py
adapts them into ApiResponse. Deliberately no imports from the application
package to keep this module free of circular dependencies.
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any, Mapping

from eitaa_bridge.reporting.model import ProgramKind, ReportedEvent, UnitScope
from eitaa_bridge.reporting.store import (
    EtagConflictError,
    EventNotFoundError,
    InvalidStatusTransitionError,
    ReportingStore,
    ReportingStoreError,
    WitnessConflictError,
)

_EVENTS_ROUTE = re.compile(r"^/api/v3/reporting/events$")
_EVENT_ID_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)$")
_EVENT_SUBMIT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/submit-review$")
_EVENT_APPROVE_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/approve$")
_EVENT_CONFLICT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/mark-conflict$")
_EVENT_REOPEN_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/reopen$")
_EVENT_WITNESSES_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/witnesses$")
_LINK_DETACH_ROUTE = re.compile(r"^/api/v3/reporting/witness-links/(?P<link_id>[A-Za-z0-9_-]+)/detach$")


def _ok(payload: dict, status: int = 200, headers: dict | None = None):
    return (status, {"ok": True, **payload}, headers or {})


def _error(status: int, message: str, **extra):
    """Uniform v3 error payload matching the client ApiError contract."""
    error_code = extra.pop("error_code", "reporting_v3_error")
    return (
        status,
        {"ok": False, "error": {"message": message, "error_code": error_code, "safe_context": extra}},
        {},
    )


def _forbidden(roles, needed: str):
    """Return a 403 response when the role is missing, else None."""
    if needed in roles:
        return None
    return _error(403, f"role '{needed}' required")


def _mapped_error(exc: Exception):
    """Map store exceptions to HTTP responses; None when not a store error."""
    if isinstance(exc, EtagConflictError):
        return _error(409, str(exc), current_etag=exc.current_etag, event_id=exc.event_id)
    if isinstance(exc, WitnessConflictError):
        return _error(409, str(exc), **(exc.details or {}))
    if isinstance(exc, EventNotFoundError):
        return _error(404, str(exc))
    if isinstance(exc, InvalidStatusTransitionError):
        return _error(409, str(exc))
    if isinstance(exc, ReportingStoreError):
        return _error(400, str(exc))
    return None


def _build_event_payload(payload: Mapping[str, Any]):
    raw = payload.get("occurred_on")
    try:
        occurred = date.fromisoformat(str(raw)) if raw else date.today()
    except ValueError:
        return _error(400, "occurred_on must be an ISO date")
    try:
        kinds = tuple(
            ProgramKind(str(k)) for k in (payload.get("program_kinds") or ["ceremony"])
        )
    except ValueError:
        return _error(400, "unknown program kind")
    unit_str = str(payload.get("unit", "provincial_hq"))
    if unit_str not in {u.value for u in UnitScope}:
        return _error(400, "unknown unit scope")
    event = ReportedEvent(
        event_id=str(payload.get("event_id") or f"evt-{uuid.uuid4().hex[:10]}"),
        program_kinds=kinds,
        occurred_on=occurred,
        unit=UnitScope(unit_str),
        unit_name=str(payload.get("unit_name", "")),
        occasion=str(payload.get("occasion", "")),
        notes=str(payload.get("notes", "")),
        created_by="",
    )
    return event


def create_event(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    built = _build_event_payload(payload)
    if isinstance(built, tuple):
        return built
    try:
        event_id, etag = store.create_event_draft(built, actor=actor)
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"event_id": event_id, "etag": etag}, status=201)


def update_event(store: ReportingStore, actor: str, event_id: str,
                 payload: Mapping[str, Any]):
    expected_etag = str(payload.get("if_match", ""))
    fields = payload.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return _error(400, "fields mapping is required")
    try:
        etag = store.update_event_fields(
            event_id, actor=actor, expected_etag=expected_etag, fields=dict(fields)
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"event_id": event_id, "etag": etag})


def get_event_file(store: ReportingStore, event_id: str):
    file = store.get_event_file(event_id)
    if file is None:
        return _error(404, "event not found")
    return _ok({"event": file})


def transition_event(store: ReportingStore, actor: str, event_id: str, action: str,
                     payload: Mapping[str, Any], roles):
    needed = "approver" if action in {"approve", "mark_conflict"} else "editor"
    denied = _forbidden(roles, needed)
    if denied:
        return denied
    try:
        etag = store.transition_event_status(
            event_id, action=action, actor=actor, reason=str(payload.get("reason", ""))
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"event_id": event_id, "etag": etag})


def link_witness(store: ReportingStore, actor: str, event_id: str,
                 payload: Mapping[str, Any]):
    try:
        result = store.link_witness(
            event_id,
            peer_id=str(payload.get("peer_id", "")),
            message_id=str(payload.get("message_id", "")),
            provider=str(payload.get("provider", "eitaa")),
            messenger_account=str(payload.get("messenger_account", "")),
            role=str(payload.get("role", "primary")),
            note=str(payload.get("note", "")),
            actor=actor,
            observed_at=payload.get("observed_at"),
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok(result, status=201)


def detach_link(store: ReportingStore, actor: str, link_id: str,
                payload: Mapping[str, Any]):
    reason = str(payload.get("reason", ""))
    if not reason.strip():
        return _error(400, "reason is required to detach a witness link")
    try:
        detached = store.detach_witness_link(link_id, reason=reason, actor=actor)
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    if not detached:
        return _error(404, "active link not found")
    return _ok({"link_id": link_id, "detached": True})


_QUEUE_ROUTE = re.compile(r"^/api/v3/reporting/review-queue$")
_QUEUE_RESOLVE_ROUTE = re.compile(
    r"^/api/v3/reporting/review-queue/(?P<queue_id>[A-Za-z0-9_-]+)/resolve$"
)
_ROLES_ROUTE = re.compile(r"^/api/v3/reporting/users/roles$")
_EVENT_AUDIT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/audit$")


def list_queue(store: ReportingStore, query: Mapping[str, Any] | None):
    status = (query or {}).get("status")
    item_type = (query or {}).get("item_type")
    items = store.list_review_queue(status=status, item_type=item_type)
    return _ok({"items": items})


def resolve_queue_item(store: ReportingStore, actor: str, roles,
                       queue_id: str, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    try:
        resolved = store.resolve_review_item(
            queue_id,
            actor=actor,
            decision=str(payload.get("decision", "resolved")),
            note=str(payload.get("note", "")),
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    if not resolved:
        return _error(404, "open queue item not found")
    return _ok({"queue_id": queue_id, "resolved": True})


def set_roles(store: ReportingStore, actor: str, roles,
              payload: Mapping[str, Any]):
    target = str(payload.get("user_id", ""))
    if not target.strip():
        return _error(400, "user_id is required")
    requested = payload.get("roles")
    if not isinstance(requested, (list, tuple)) or not requested:
        return _error(400, "roles list is required")
    has_admin = "admin" in roles
    table_empty = not store.list_user_role_entries()
    if not has_admin and not table_empty:
        return _error(403, "role 'admin' required")
    try:
        store.set_user_roles(target, {str(r) for r in requested}, actor=actor)
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"user_id": target, "roles": sorted(set(map(str, requested)))},
               status=201 if table_empty else 200)


def get_event_audit(store: ReportingStore, actor: str, roles, event_id: str):
    denied = _forbidden(roles, "approver")
    if denied:
        return denied
    return _ok({"event_id": event_id, "audit": store.get_event_audit(event_id)})


_WITNESS_STATUS_ROUTE = re.compile(r"^/api/v3/reporting/witness-status$")


def witness_status(store: ReportingStore, query: Mapping[str, Any] | None):
    """Batched per-message report-registration status for the chat surface."""
    peer_id = str((query or {}).get("peer_id", "")).strip()
    raw_ids = str((query or {}).get("message_id", ""))
    message_ids = [part.strip() for part in raw_ids.split(",") if part.strip()]
    if not peer_id or not message_ids:
        return _error(400, "peer_id and message_id (comma separated) are required")
    statuses = store.find_witness_status(peer_id, message_ids)
    return _ok({"statuses": statuses})


def dispatch(store: ReportingStore, actor: str, roles, method: str, path: str,
             payload: Mapping[str, Any] | None = None,
             query: Mapping[str, Any] | None = None):
    """Route /api/v3/reporting/* requests; None when the path is unknown."""
    payload = payload or {}
    query = query or {}
    if method == "POST" and _EVENTS_ROUTE.match(path):
        denied = _forbidden(roles, "editor")
        return denied if denied else create_event(store, actor, payload)
    match = _EVENT_ID_ROUTE.match(path)
    if match:
        event_id = match.group("event_id")
        if method == "GET":
            return get_event_file(store, event_id)
        if method == "PUT":
            denied = _forbidden(roles, "editor")
            if denied:
                return denied
            return update_event(store, actor, event_id, payload)
    if method == "POST":
        submit = _EVENT_SUBMIT_ROUTE.match(path)
        if submit:
            return transition_event(store, actor, submit.group("event_id"),
                                    "submit_review", payload, roles)
        approve = _EVENT_APPROVE_ROUTE.match(path)
        if approve:
            return transition_event(store, actor, approve.group("event_id"),
                                    "approve", payload, roles)
        conflict = _EVENT_CONFLICT_ROUTE.match(path)
        if conflict:
            return transition_event(store, actor, conflict.group("event_id"),
                                    "mark_conflict", payload, roles)
        reopen = _EVENT_REOPEN_ROUTE.match(path)
        if reopen:
            return transition_event(store, actor, reopen.group("event_id"),
                                    "reopen", payload, roles)
        witnesses = _EVENT_WITNESSES_ROUTE.match(path)
        if witnesses:
            denied = _forbidden(roles, "editor")
            if denied:
                return denied
            return link_witness(store, actor, witnesses.group("event_id"), payload)
        detach = _LINK_DETACH_ROUTE.match(path)
        if detach:
            denied = _forbidden(roles, "editor")
            if denied:
                return denied
            return detach_link(store, actor, detach.group("link_id"), payload)
        resolve = _QUEUE_RESOLVE_ROUTE.match(path)
        if resolve:
            return resolve_queue_item(store, actor, roles,
                                      resolve.group("queue_id"), payload)
        if _ROLES_ROUTE.match(path):
            return set_roles(store, actor, roles, payload)
    if method == "GET":
        if _WITNESS_STATUS_ROUTE.match(path):
            return witness_status(store, query)
        if _QUEUE_ROUTE.match(path):
            return list_queue(store, query)
        audit = _EVENT_AUDIT_ROUTE.match(path)
        if audit:
            return get_event_audit(store, actor, roles, audit.group("event_id"))
    return None


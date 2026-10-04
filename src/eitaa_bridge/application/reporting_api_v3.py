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
_EVENT_DOCUMENTS_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents$")
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
                 payload: Mapping[str, Any], if_match: str | None = None):
    expected_etag = (if_match or str(payload.get("if_match", ""))).strip('"')
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
    return _ok({"event_id": event_id, "etag": etag}, headers={"ETag": f'"{etag}"'})


def get_event_file(store: ReportingStore, event_id: str):
    file = store.get_event_file(event_id)
    if file is None:
        return _error(404, "event not found")
    etag = file.get("etag", "")
    headers = {"ETag": f'"{etag}"'} if etag else {}
    return _ok({"event": file}, headers=headers)


def attach_document(store: ReportingStore, actor: str, roles, event_id: str,
                    payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    media_id = str(payload.get("media_id", "")).strip()
    if not media_id:
        return _error(400, "media_id is required")
    try:
        doc = store.attach_document(
            event_id,
            media_id=media_id,
            sha256=str(payload.get("sha256", "")),
            kind=str(payload.get("kind", "")),
            size_bytes=payload.get("size_bytes"),
            display_order=int(payload.get("display_order", 0)),
            is_cover=bool(payload.get("is_cover", False)),
            added_by=actor,
        )
        return _ok({"document": doc}, status=201)
    except Exception as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))


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


_ASSISTANT_FEEDBACK_ROUTE = re.compile(r"^/api/v3/reporting/assistant/feedback$")
_ASSISTANT_FEEDBACK_REVOKE_ROUTE = re.compile(
    r"^/api/v3/reporting/assistant/feedback/(?P<feedback_id>[a-zA-Z0-9_-]+)/revoke$"
)
_ASSISTANT_ALIASES_ROUTE = re.compile(r"^/api/v3/reporting/assistant/aliases$")
_ASSISTANT_ALIAS_REVOKE_ROUTE = re.compile(
    r"^/api/v3/reporting/assistant/aliases/(?P<alias_id>[a-zA-Z0-9_-]+)/revoke$"
)


def record_feedback(store: ReportingStore, actor: str, roles, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    candidate_id = str(payload.get("candidate_id") or "").strip()
    action = str(payload.get("action") or "").strip()
    if not candidate_id or not action:
        return _error(400, "candidate_id and action are required")
    try:
        rec = store.record_assistant_feedback(
            candidate_id=candidate_id,
            actor=actor,
            action=action,
            scope_kind=str(payload.get("scope_kind") or "local"),
            scope_target=str(payload.get("scope_target") or ""),
            suggested_program=str(payload.get("suggested_program") or ""),
            suggested_unit=str(payload.get("suggested_unit") or ""),
            chosen_program=str(payload.get("chosen_program") or ""),
            chosen_unit=str(payload.get("chosen_unit") or ""),
            rule_version=str(payload.get("rule_version") or "1.0"),
            notes=str(payload["notes"]) if "notes" in payload else None,
        )
    except (ValueError, ReportingStoreError) as exc:
        return _error(400, str(exc))
    return _ok(rec, status=201)


def revoke_feedback(store: ReportingStore, actor: str, roles, feedback_id: str):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    try:
        store.revoke_assistant_feedback(feedback_id, actor=actor)
    except LookupError as exc:
        return _error(404, str(exc))
    except (ValueError, ReportingStoreError) as exc:
        return _error(400, str(exc))
    return _ok({"revoked": True, "feedback_id": feedback_id})


def list_feedback(store: ReportingStore, query: Mapping[str, Any] | None):
    q = query or {}
    candidate_id = q.get("candidate_id")
    scope_kind = q.get("scope_kind")
    include_revoked = q.get("include_revoked") in ("1", "true", "True")
    items = store.list_assistant_feedback(
        candidate_id=candidate_id,
        scope_kind=scope_kind,
        include_revoked=include_revoked,
    )
    return _ok({"feedback": items})


def add_alias(store: ReportingStore, actor: str, roles, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    alias_text = str(payload.get("alias_text") or "").strip()
    target = str(payload.get("canonical_target") or "").strip()
    target_type = str(payload.get("target_type") or "program").strip()
    scope_kind = str(payload.get("scope_kind") or "local").strip()
    if scope_kind == "global":
        admin_denied = _forbidden(roles, "admin")
        if admin_denied:
            return admin_denied
    try:
        res = store.add_scoped_alias(
            alias_text=alias_text,
            canonical_target=target,
            target_type=target_type,
            approved_by=actor,
            scope_kind=scope_kind,
            scope_target=str(payload.get("scope_target") or ""),
            weight=float(payload.get("weight", 1.0)),
        )
    except (ValueError, ReportingStoreError) as exc:
        return _error(400, str(exc))
    return _ok(res, status=201)


def revoke_alias(store: ReportingStore, actor: str, roles, alias_id: str):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    try:
        store.revoke_scoped_alias(alias_id, actor=actor)
    except LookupError as exc:
        return _error(404, str(exc))
    except (ValueError, ReportingStoreError) as exc:
        return _error(400, str(exc))
    return _ok({"revoked": True, "alias_id": alias_id})


def list_aliases(store: ReportingStore, query: Mapping[str, Any] | None):
    q = query or {}
    items = store.list_scoped_aliases(
        scope_kind=q.get("scope_kind"),
        scope_target=q.get("scope_target"),
        target_type=q.get("target_type"),
        status=q.get("status", "active"),
    )
    return _ok({"aliases": items})


def dispatch(store: ReportingStore, actor: str, roles, method: str, path: str,
             payload: Mapping[str, Any] | None = None,
             query: Mapping[str, Any] | None = None,
             if_match: str | None = None):
    """Route /api/v3/reporting/* requests; None when the path is unknown."""
    payload = payload or {}
    query = query or {}
    if method == "POST" and _EVENTS_ROUTE.match(path):
        denied = _forbidden(roles, "editor")
        return denied if denied else create_event(store, actor, payload)
    doc_match = _EVENT_DOCUMENTS_ROUTE.match(path)
    if doc_match and method in {"POST", "PUT"}:
        return attach_document(store, actor, roles, doc_match.group("event_id"), payload)
    match = _EVENT_ID_ROUTE.match(path)
    if match:
        event_id = match.group("event_id")
        if method == "GET":
            return get_event_file(store, event_id)
        if method == "PUT":
            denied = _forbidden(roles, "editor")
            if denied:
                return denied
            return update_event(store, actor, event_id, payload, if_match=if_match)
    if method == "POST":
        if _ASSISTANT_FEEDBACK_ROUTE.match(path):
            return record_feedback(store, actor, roles, payload)
        fb_revoke_match = _ASSISTANT_FEEDBACK_REVOKE_ROUTE.match(path)
        if fb_revoke_match:
            return revoke_feedback(store, actor, roles, fb_revoke_match.group("feedback_id"))
        if _ASSISTANT_ALIASES_ROUTE.match(path):
            return add_alias(store, actor, roles, payload)
        alias_revoke_match = _ASSISTANT_ALIAS_REVOKE_ROUTE.match(path)
        if alias_revoke_match:
            return revoke_alias(store, actor, roles, alias_revoke_match.group("alias_id"))
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
        if _ASSISTANT_FEEDBACK_ROUTE.match(path):
            return list_feedback(store, query)
        if _ASSISTANT_ALIASES_ROUTE.match(path):
            return list_aliases(store, query)
        if _WITNESS_STATUS_ROUTE.match(path):
            return witness_status(store, query)
        if _QUEUE_ROUTE.match(path):
            return list_queue(store, query)
        audit = _EVENT_AUDIT_ROUTE.match(path)
        if audit:
            return get_event_audit(store, actor, roles, audit.group("event_id"))
    return None


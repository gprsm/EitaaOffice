"""HTTP handlers for /api/v3/reporting/* — phase 2 transactional core.

Pure handler functions returning (status, payload, headers) tuples; api.py
adapts them into ApiResponse. Deliberately no imports from the application
package to keep this module free of circular dependencies.
"""
import json
import re
import uuid
from datetime import date
from typing import Any, Mapping

from eitaa_bridge.reporting.model import (
    Fact,
    FactValueKind,
    OccasionClass,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from eitaa_bridge.reporting.registry import LiaisonRecord, UnitRecord
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
_EVENT_REVISION_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/request-revision$")
_EVENT_DEFECTS_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/defects$")
_EVENT_CONFLICT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/mark-conflict$")
_EVENT_REOPEN_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/reopen$")
_EVENT_WITNESSES_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/witnesses$")
_EVENT_DOCUMENTS_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents$")
_LINK_DETACH_ROUTE = re.compile(r"^/api/v3/reporting/witness-links/(?P<link_id>[A-Za-z0-9_-]+)/detach$")
_UNITS_ROUTE = re.compile(r"^/api/v3/reporting/units$")
_UNIT_ID_ROUTE = re.compile(r"^/api/v3/reporting/units/(?P<unit_id>[A-Za-z0-9_-]+)$")
_UNIT_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/units/(?P<unit_id>[A-Za-z0-9_-]+)/delete$")
_LIAISONS_ROUTE = re.compile(r"^/api/v3/reporting/liaisons$")
_LIAISONS_ASSIGN_AUTHOR_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/assign-author$")
_LIAISONS_UNLINK_AUTHOR_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/unlink-author$")
_LIAISONS_LOOKUP_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/lookup$")
_LIAISONS_PROFILE_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/profile$")
_LIAISON_ID_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/(?P<liaison_id>[A-Za-z0-9_-]+)$")
_LIAISON_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/(?P<liaison_id>[A-Za-z0-9_-]+)/delete$")
_LIAISONS_RESOLVE_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/resolve$")
_INDICATORS_MACRO_ROUTE = re.compile(r"^/api/v3/reporting/indicators/macro$")
_INDICATORS_MICRO_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro$")
_INDICATORS_MICRO_ID_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro/(?P<indicator_id>[A-Za-z0-9_-]+)$")
_INDICATORS_MICRO_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro/(?P<indicator_id>[A-Za-z0-9_-]+)/delete$")
_INDICATORS_MESSAGES_ROUTE = re.compile(r"^/api/v3/reporting/indicators/messages$")
_INDICATORS_MESSAGES_ASSIGN_ROUTE = re.compile(r"^/api/v3/reporting/indicators/messages/assign$")
_MESSAGE_SPLITS_ROUTE = re.compile(r"^/api/v3/reporting/splits$")



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
    reg_id = str(payload.get("registered_by_id", "") or "").strip()
    reg_name = str(payload.get("registered_by_name", "") or "").strip()
    status_str = str(payload.get("review_status", "") or "draft").strip()

    facts_list: list[Fact] = []
    raw_facts = payload.get("facts")
    if isinstance(raw_facts, (list, tuple)):
        for f in raw_facts:
            if isinstance(f, Mapping):
                metric = str(f.get("metric", "")).strip()
                if not metric:
                    continue
                try:
                    val = float(f.get("value", 0.0))
                except (ValueError, TypeError):
                    return _error(400, f"invalid numeric value for fact {metric}")
                vk_str = str(f.get("value_kind", "verified")).strip()
                vk = FactValueKind(vk_str) if vk_str in {v.value for v in FactValueKind} else FactValueKind.VERIFIED
                uom = str(f.get("unit_of_measure", "count")).strip() or "count"
                source_str = str(f.get("source", "manual")).strip()
                src = ValueSource(source_str) if source_str in {s.value for s in ValueSource} else ValueSource.MANUAL
                fact_obj = Fact(
                    metric=metric,
                    value=val,
                    value_kind=vk,
                    unit_of_measure=uom,
                    scope=str(f.get("scope", "province")),
                    evidence_refs=tuple(str(r) for r in f.get("evidence_refs", ())),
                    source=src,
                    created_by=reg_id or reg_name or "",
                    note=str(f.get("note", "")),
                )
                try:
                    fact_obj.validate()
                except ValueError as exc:
                    return _error(400, f"fact validation error: {exc}")
                facts_list.append(fact_obj)

    occ_class_raw = payload.get("occasion_class")
    occ_class = (
        OccasionClass(str(occ_class_raw))
        if occ_class_raw and str(occ_class_raw) in {o.value for o in OccasionClass}
        else None
    )

    official_raw = payload.get("official_present")
    official_present = bool(official_raw) if official_raw is not None else None

    duration_raw = payload.get("duration_minutes")
    duration_val = None
    if duration_raw is not None:
        try:
            duration_val = int(duration_raw)
        except (ValueError, TypeError):
            duration_val = None

    macro_cat = str(payload.get("macro_category", "workbook_approved") or "workbook_approved").strip()
    macro_category = "other_cultural" if macro_cat == "other_cultural" else "workbook_approved"
    custom_topic = str(payload.get("custom_topic", "") or "").strip()
    macro_indicator = str(payload.get("macro_indicator", "") or "").strip()
    raw_micros = payload.get("micro_indicators", [])
    if isinstance(raw_micros, str):
        try:
            raw_micros = json.loads(raw_micros)
        except Exception:
            raw_micros = [s.strip() for s in raw_micros.split(",") if s.strip()]
    micro_indicators = [str(m).strip() for m in raw_micros if str(m).strip()] if isinstance(raw_micros, (list, tuple)) else []

    event = ReportedEvent(
        event_id=str(payload.get("event_id") or f"evt-{uuid.uuid4().hex[:10]}"),
        program_kinds=kinds,
        occurred_on=occurred,
        unit=UnitScope(unit_str),
        unit_name=str(payload.get("unit_name", "")),
        occasion=str(payload.get("occasion", "")),
        occasion_class=occ_class,
        macro_category=macro_category,
        custom_topic=custom_topic,
        macro_indicator=macro_indicator,
        micro_indicators=micro_indicators,
        facts=facts_list,
        official_present=official_present,
        is_standalone_titled=bool(payload.get("is_standalone_titled", True)),
        duration_minutes=duration_val,
        prior_announcement=bool(payload.get("prior_announcement", False)),
        had_reception=bool(payload.get("had_reception", False)),
        is_ashura_pilgrimage=bool(payload.get("is_ashura_pilgrimage", False)),
        contains_inner_contest=bool(payload.get("contains_inner_contest", False)),
        campaign=str(payload.get("campaign", "")),
        notes=str(payload.get("notes", "")),
        created_by=reg_id or reg_name or "",
        review_status=status_str,
        registered_by_id=reg_id,
        registered_by_name=reg_name,
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
    needed = "approver" if action in {"approve", "mark_conflict", "request_revision"} else "editor"
    denied = _forbidden(roles, needed)
    if denied:
        return denied

    if action == "approve":
        force_approve = bool(payload.get("force_approve", False))
        if not force_approve:
            from eitaa_bridge.reporting.defect_scanner import scan_event_defects
            ev = store.get_event(event_id)
            if ev is not None:
                with store._connect() as conn:
                    witness_cnt = conn.execute(
                        "SELECT COUNT(*) FROM reporting_event_witness_links WHERE event_id = ? AND detached_at IS NULL",
                        (event_id,),
                    ).fetchone()[0]
                    doc_cnt = conn.execute(
                        "SELECT COUNT(*) FROM event_documents WHERE event_id = ?",
                        (event_id,),
                    ).fetchone()[0]
                defects = scan_event_defects(ev, witnesses_count=witness_cnt, documents_count=doc_cnt)
                blockers = [d for d in defects if d.severity == "blocker"]
                if blockers:
                    return _error(
                        422,
                        f"approval blocked by {len(blockers)} blocker defect(s)",
                        error_code="approval_blocked_by_defects",
                        blockers=[d.to_dict() for d in blockers],
                    )

    try:
        defects_val = payload.get("defects")
        defects_json_str = json.dumps(defects_val, ensure_ascii=False) if isinstance(defects_val, list) else None
        etag = store.transition_event_status(
            event_id,
            action=action,
            actor=actor,
            reason=str(payload.get("reason") or payload.get("notes") or ""),
            actor_id=str(payload.get("actor_id") or actor),
            actor_name=str(payload.get("actor_name") or actor),
            actor_role=str(payload.get("actor_role") or ""),
            defects_json=defects_json_str,
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"event_id": event_id, "etag": etag})


def get_event_defects(store: ReportingStore, event_id: str):
    from eitaa_bridge.reporting.defect_scanner import scan_event_defects
    ev = store.get_event(event_id)
    if ev is None:
        return _error(404, f"event {event_id} not found")
    with store._connect() as conn:
        witness_cnt = conn.execute(
            "SELECT COUNT(*) FROM reporting_event_witness_links WHERE event_id = ? AND detached_at IS NULL",
            (event_id,),
        ).fetchone()[0]
        doc_cnt = conn.execute(
            "SELECT COUNT(*) FROM event_documents WHERE event_id = ?",
            (event_id,),
        ).fetchone()[0]
    defects = scan_event_defects(ev, witnesses_count=witness_cnt, documents_count=doc_cnt)
    return _ok({
        "event_id": event_id,
        "defects": [d.to_dict() for d in defects],
        "defects_count": len(defects),
        "has_blockers": any(d.severity == "blocker" for d in defects),
    })


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


def list_events_v3(store: ReportingStore, query: Mapping[str, Any] | None):
    q = query or {}
    try:
        limit = int(q.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    review_status = str(q.get("review_status", "")).strip() or None
    registered_by_id = str(q.get("registered_by_id", "")).strip() or None
    events = store.list_events(limit=limit, review_status=review_status, registered_by_id=registered_by_id)
    return _ok({
        "events": [
            {
                "event_id": ev.event_id,
                "program_kinds": [k.value for k in ev.program_kinds],
                "occurred_on": ev.occurred_on.isoformat(),
                "unit": ev.unit.value,
                "unit_name": ev.unit_name,
                "occasion": ev.occasion,
                "review_status": ev.review_status,
                "registered_by_id": ev.registered_by_id,
                "registered_by_name": ev.registered_by_name,
                "reviewed_by_id": ev.reviewed_by_id,
                "reviewed_by_name": ev.reviewed_by_name,
                "defects_json": ev.defects_json,
                "facts_count": len(ev.facts),
            }
            for ev in events
        ]
    })


def list_units(store: ReportingStore, query: Mapping[str, Any]):
    county = str(query.get("county") or "").strip() if query else None
    units = store.list_units(county=county or None)
    counties = store.list_counties()
    return _ok({
        "units": [u.to_dict() for u in units],
        "counties": counties,
    })


def save_unit(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    unit_id = str(payload.get("unit_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    county = str(payload.get("county") or "").strip()
    unit_type = str(payload.get("unit_type") or "").strip()
    display_name = str(payload.get("display_name") or "").strip()
    kind = str(payload.get("kind") or "judicial_domain").strip()
    notes = str(payload.get("notes") or "").strip()

    if not name and county and unit_type:
        name = f"{county} - {unit_type}"
    if not display_name:
        if county and unit_type:
            display_name = f"{county} - {unit_type}"
        else:
            display_name = name

    if not name:
        return _error(400, "نام واحد یا شهرستان و نوع واحد الزامی است.")

    unit = UnitRecord(
        unit_id=unit_id,
        name=name,
        county=county,
        unit_type=unit_type,
        display_name=display_name,
        kind=kind,
        notes=notes,
    )
    saved = store.save_unit(unit)
    return _ok({"unit": saved.to_dict()})


def delete_unit(store: ReportingStore, actor: str, unit_id: str):
    success = store.delete_unit(unit_id)
    if not success:
        return _error(404, f"واحد قضایی با شناسه {unit_id} یافت نشد.")
    return _ok({"deleted": True, "unit_id": unit_id})


def list_liaisons(store: ReportingStore, query: Mapping[str, Any]):
    unit_id = str(query.get("unit_id") or "").strip() if query else None
    liaisons = store.list_liaisons(unit_id=unit_id or None)
    all_units_by_id = {u.unit_id: u for u in store.list_units()}
    res = []
    for l in liaisons:
        d = l.to_dict()
        u = all_units_by_id.get(l.unit_id)
        d["unit_display_name"] = u.display_name if u else ""
        d["county"] = u.county if u else ""
        res.append(d)
    return _ok({"liaisons": res})


def save_liaison(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    liaison_id = str(payload.get("liaison_id") or "").strip()
    unit_id = str(payload.get("unit_id") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    eitaa_username = str(payload.get("eitaa_username") or "").strip()
    eitaa_user_id = str(payload.get("eitaa_user_id") or "").strip()
    sender_key = str(payload.get("sender_key") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    match_keywords = str(payload.get("match_keywords") or "").strip()
    notes = str(payload.get("notes") or "").strip()

    if not unit_id:
        return _error(400, "انتخاب واحد یا حوزه قضایی برای رابط الزامی است.")
    if not full_name:
        return _error(400, "نام و نام خانوادگی رابط فرهنگی الزامی است.")

    liaison = LiaisonRecord(
        liaison_id=liaison_id,
        unit_id=unit_id,
        full_name=full_name,
        eitaa_username=eitaa_username,
        eitaa_user_id=eitaa_user_id,
        sender_key=sender_key,
        phone=phone,
        match_keywords=match_keywords,
        notes=notes,
    )
    saved = store.save_liaison(liaison)
    unit = store.get_unit(saved.unit_id)
    res = saved.to_dict()
    res["unit_display_name"] = unit.display_name if unit else ""
    return _ok({"liaison": res})


def delete_liaison(store: ReportingStore, actor: str, liaison_id: str):
    success = store.delete_liaison(liaison_id)
    if not success:
        return _error(404, f"رابط فرهنگی با شناسه {liaison_id} یافت نشد.")
    return _ok({"deleted": True, "liaison_id": liaison_id})


def resolve_liaison(store: ReportingStore, payload: Mapping[str, Any]):
    sender_key = str(payload.get("sender_key") or "")
    username = str(payload.get("username") or "")
    full_name = str(payload.get("full_name") or "")
    text = str(payload.get("text") or "")

    liaison, unit = store.resolve_liaison_and_unit(
        sender_key=sender_key,
        username=username,
        full_name=full_name,
        text=text,
    )
    return _ok({
        "matched": liaison is not None or unit is not None,
        "liaison": liaison.to_dict() if liaison else None,
        "unit": unit.to_dict() if unit else None,
    })


def assign_author_liaison(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    unit_id = str(payload.get("unit_id") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    sender_key = str(payload.get("sender_key") or "").strip()
    eitaa_username = str(payload.get("eitaa_username") or "").strip()
    eitaa_user_id = str(payload.get("eitaa_user_id") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    notes = str(payload.get("notes") or "").strip()
    match_keywords = str(payload.get("match_keywords") or "").strip()

    if not unit_id:
        return _error(400, "انتخاب حوزه قضایی الزامی است.")
    if not full_name and not eitaa_username and not sender_key and not eitaa_user_id:
        return _error(400, "اطلاعات نام یا شناسه نویسنده الزامی است.")

    try:
        liaison, unit = store.assign_author_as_liaison(
            unit_id=unit_id,
            full_name=full_name,
            sender_key=sender_key,
            eitaa_username=eitaa_username,
            eitaa_user_id=eitaa_user_id,
            phone=phone,
            notes=notes,
            match_keywords=match_keywords,
        )
        res = liaison.to_dict()
        res["unit_display_name"] = unit.display_name
        res["county"] = unit.county
        return _ok({"liaison": res, "unit": unit.to_dict()})
    except Exception as exc:
        return _error(400, str(exc))


def unlink_author_liaison(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    sender_key = str(payload.get("sender_key") or "").strip()
    liaison_id = str(payload.get("liaison_id") or "").strip()
    if not sender_key and not liaison_id:
        return _error(400, "sender_key یا liaison_id الزامی است.")
    success = store.unlink_author_liaison(sender_key=sender_key, liaison_id=liaison_id)
    return _ok({"unlinked": success})


def lookup_liaison(store: ReportingStore, query: Mapping[str, Any]):
    sender_key = str(query.get("sender_key") or "").strip()
    username = str(query.get("username") or "").strip()
    user_id = str(query.get("user_id") or "").strip()
    full_name = str(query.get("full_name") or "").strip()

    liaison, unit = store.find_liaison_by_sender(
        sender_key=sender_key,
        username=username,
        user_id=user_id,
        full_name=full_name,
    )
    res_liaison = liaison.to_dict() if liaison else None
    if res_liaison and unit:
        res_liaison["unit_display_name"] = unit.display_name
        res_liaison["county"] = unit.county
    return _ok({
        "matched": liaison is not None,
        "liaison": res_liaison,
        "unit": unit.to_dict() if unit else None,
    })


def get_liaison_profile(store: ReportingStore, query: Mapping[str, Any]):
    liaison_id = str(query.get("liaison_id") or "").strip()
    unit_id = str(query.get("unit_id") or "").strip()
    sender_key = str(query.get("sender_key") or "").strip()
    user_id = str(query.get("user_id") or "").strip()
    username = str(query.get("username") or "").strip()
    full_name = str(query.get("full_name") or "").strip()
    try:
        days = int(query.get("days", 365))
    except (ValueError, TypeError):
        days = 365

    profile = store.get_liaison_profile_analytics(
        liaison_id=liaison_id,
        unit_id=unit_id,
        sender_key=sender_key,
        user_id=user_id,
        username=username,
        full_name=full_name,
        days=days,
    )
    return _ok({"profile": profile})


def list_macro_indicators(store: ReportingStore):
    return _ok({"macro_indicators": store.list_macro_indicators()})


def list_micro_indicators(store: ReportingStore):
    return _ok({"micro_indicators": store.list_micro_indicators()})


def save_micro_indicator(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    title = str(payload.get("title", "") or "").strip()
    category = str(payload.get("category", "") or "").strip()
    color = str(payload.get("color", "") or "").strip()
    if not title:
        return _error(400, "عنوان شاخصه جزئی نمی‌تواند خالی باشد.")
    try:
        ind = store.save_micro_indicator(title, category=category, color=color)
        return _ok({"indicator": ind}, status=201)
    except Exception as exc:
        return _error(400, str(exc))


def update_micro_indicator(store: ReportingStore, actor: str, indicator_id: str, payload: Mapping[str, Any]):
    title = payload.get("title")
    category = payload.get("category")
    color = payload.get("color")
    try:
        ind = store.update_micro_indicator(indicator_id, title=title, category=category, color=color)
        return _ok({"indicator": ind})
    except Exception as exc:
        return _error(400, str(exc))


def delete_micro_indicator(store: ReportingStore, actor: str, indicator_id: str):
    success = store.delete_micro_indicator(indicator_id)
    return _ok({"deleted": success, "indicator_id": indicator_id})


def get_message_indicators(store: ReportingStore, query: Mapping[str, Any]):
    peer_key = str(query.get("peer_key", "") or "").strip()
    if not peer_key:
        return _error(400, "peer_key is required")
    raw_mids = query.get("message_ids")
    message_ids = None
    if raw_mids:
        try:
            if isinstance(raw_mids, str):
                message_ids = [int(x.strip()) for x in raw_mids.split(",") if x.strip()]
            elif isinstance(raw_mids, (list, tuple)):
                message_ids = [int(x) for x in raw_mids]
        except (ValueError, TypeError):
            message_ids = None
    indicators = store.get_message_indicators(peer_key, message_ids)
    str_indicators = {str(k): v for k, v in indicators.items()}
    return _ok({"indicators": str_indicators})


def assign_message_indicators(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    peer_key = str(payload.get("peer_key", "") or "").strip()
    if not peer_key:
        return _error(400, "peer_key is required")
    message_ids = payload.get("message_ids", [])
    if not isinstance(message_ids, (list, tuple)) or not message_ids:
        return _error(400, "message_ids list is required")
    macro_indicator = str(payload.get("macro_indicator", "") or "").strip()
    raw_micros = payload.get("micro_indicators", [])
    if isinstance(raw_micros, str):
        try:
            raw_micros = json.loads(raw_micros)
        except Exception:
            raw_micros = [s.strip() for s in raw_micros.split(",") if s.strip()]
    micro_indicators = [str(m).strip() for m in raw_micros if str(m).strip()] if isinstance(raw_micros, (list, tuple)) else []
    int_mids = [int(m) for m in message_ids]
    store.set_message_indicators(peer_key, int_mids, macro_indicator, micro_indicators, updated_by=actor)
    return _ok({
        "peer_key": peer_key,
        "message_ids": int_mids,
        "macro_indicator": macro_indicator,
        "micro_indicators": micro_indicators,
    })


def get_message_splits(store: ReportingStore, query: Mapping[str, Any]):
    peer_key = str(query.get("peer_key", "") or "").strip()
    if not peer_key:
        return _error(400, "peer_key is required")
    detached = store.get_detached_message_ids(peer_key)
    return _ok({"peer_key": peer_key, "detached_message_ids": detached})


def set_message_splits(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    peer_key = str(payload.get("peer_key", "") or "").strip()
    if not peer_key:
        return _error(400, "peer_key is required")
    raw_detached = payload.get("detached_ids", [])
    detached_ids = [int(x) for x in raw_detached] if isinstance(raw_detached, (list, tuple)) else []
    raw_unified = payload.get("unified_ids", [])
    unified_ids = [int(x) for x in raw_unified] if isinstance(raw_unified, (list, tuple)) else []
    res = store.set_message_splits(peer_key, detached_ids, unified_ids)
    return _ok({"peer_key": peer_key, "detached_message_ids": res})


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
    if method == "PUT":
        micro_put = _INDICATORS_MICRO_ID_ROUTE.match(path)
        if micro_put:
            return update_micro_indicator(store, actor, micro_put.group("indicator_id"), payload)
    if method == "POST":
        micro_post_del = _INDICATORS_MICRO_DELETE_POST_ROUTE.match(path)
        if micro_post_del:
            return delete_micro_indicator(store, actor, micro_post_del.group("indicator_id"))
        if _INDICATORS_MICRO_ROUTE.match(path):
            return save_micro_indicator(store, actor, payload)
        if _INDICATORS_MESSAGES_ASSIGN_ROUTE.match(path):
            return assign_message_indicators(store, actor, payload)
        if _MESSAGE_SPLITS_ROUTE.match(path):
            return set_message_splits(store, actor, payload)
        unit_post_del = _UNIT_DELETE_POST_ROUTE.match(path)
        if unit_post_del:
            return delete_unit(store, actor, unit_post_del.group("unit_id"))
        liaison_post_del = _LIAISON_DELETE_POST_ROUTE.match(path)
        if liaison_post_del:
            return delete_liaison(store, actor, liaison_post_del.group("liaison_id"))
        if _UNITS_ROUTE.match(path):
            return save_unit(store, actor, payload)
        if _LIAISONS_ASSIGN_AUTHOR_ROUTE.match(path):
            return assign_author_liaison(store, actor, payload)
        if _LIAISONS_UNLINK_AUTHOR_ROUTE.match(path):
            return unlink_author_liaison(store, actor, payload)
        if _LIAISONS_ROUTE.match(path):
            return save_liaison(store, actor, payload)
        if _LIAISONS_RESOLVE_ROUTE.match(path):
            return resolve_liaison(store, payload)
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
        revision = _EVENT_REVISION_ROUTE.match(path)
        if revision:
            return transition_event(store, actor, revision.group("event_id"),
                                    "request_revision", payload, roles)
        defects_post = _EVENT_DEFECTS_ROUTE.match(path)
        if defects_post:
            return get_event_defects(store, defects_post.group("event_id"))
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
        if _INDICATORS_MACRO_ROUTE.match(path):
            return list_macro_indicators(store)
        if _INDICATORS_MICRO_ROUTE.match(path):
            return list_micro_indicators(store)
        if _INDICATORS_MESSAGES_ROUTE.match(path):
            return get_message_indicators(store, query)
        if _MESSAGE_SPLITS_ROUTE.match(path):
            return get_message_splits(store, query)
        if _LIAISONS_LOOKUP_ROUTE.match(path):
            return lookup_liaison(store, query)
        if _LIAISONS_PROFILE_ROUTE.match(path):
            return get_liaison_profile(store, query)
        if _UNITS_ROUTE.match(path):
            return list_units(store, query)
        if _LIAISONS_ROUTE.match(path):
            return list_liaisons(store, query)
        if _EVENTS_ROUTE.match(path):
            return list_events_v3(store, query)
        defects_get = _EVENT_DEFECTS_ROUTE.match(path)
        if defects_get:
            return get_event_defects(store, defects_get.group("event_id"))
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
    if method == "DELETE":
        micro_del = _INDICATORS_MICRO_ID_ROUTE.match(path)
        if micro_del:
            return delete_micro_indicator(store, actor, micro_del.group("indicator_id"))
        unit_del = _UNIT_ID_ROUTE.match(path)
        if unit_del:
            return delete_unit(store, actor, unit_del.group("unit_id"))
        liaison_del = _LIAISON_ID_ROUTE.match(path)
        if liaison_del:
            return delete_liaison(store, actor, liaison_del.group("liaison_id"))
    return None



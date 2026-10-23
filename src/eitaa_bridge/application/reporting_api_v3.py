"""HTTP handlers for /api/v3/reporting/* — phase 2 transactional core.

Pure handler functions returning (status, payload, headers) tuples; api.py
adapts them into ApiResponse. Deliberately no imports from the application
package to keep this module free of circular dependencies.
"""
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import uuid
from datetime import date
from typing import Any, Mapping

from eitaa_bridge.reporting.jalali_dates import normalize_to_iso_date
from eitaa_bridge.reporting.model import (
    Fact,
    FactValueKind,
    OccasionClass,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from eitaa_bridge.reporting.registry import ImamRecord, LiaisonRecord, PersonRecord, UnitRecord, VenueRecord
from eitaa_bridge.reporting.store import (
    EtagConflictError,
    EventNotFoundError,
    InvalidStatusTransitionError,
    ReportingStore,
    ReportingStoreError,
    WitnessConflictError,
)

_EVENTS_EXPORT_ROUTE = re.compile(r"^/api/v3/reporting/events/export-excel$")
_EVENTS_DOSSIER_BUNDLE_ROUTE = re.compile(r"^/api/v3/reporting/events/export-dossier-bundle$")
_EVENTS_ROUTE = re.compile(r"^/api/v3/reporting/events$")
_EVENT_ID_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)$")
_EVENT_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/delete$")
_EVENT_SUBMIT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/submit-review$")
_EVENT_APPROVE_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/approve$")
_EVENT_REVISION_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/request-revision$")
_EVENT_DEFECTS_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/defects$")
_EVENT_CONFLICT_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/mark-conflict$")
_EVENT_REOPEN_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/reopen$")
_EVENT_WITNESSES_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/witnesses$")
_EVENT_DOCUMENTS_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents$")
_EVENT_DOCUMENTS_UPLOAD_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents/upload$")
_EVENT_DOCUMENT_ID_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents/(?P<doc_id>[A-Za-z0-9_-]+)$")
_EVENT_DOCUMENT_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents/(?P<doc_id>[A-Za-z0-9_-]+)/delete$")
_EVENT_DOCUMENT_COVER_POST_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents/(?P<doc_id>[A-Za-z0-9_-]+)/cover$")
_EVENT_DOCUMENT_VIEW_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/documents/(?P<doc_id>[A-Za-z0-9_-]+)/view$")
_EVENT_MERGE_CANDIDATES_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/merge-candidates$")
_EVENT_MERGE_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/merge$")
_EVENT_NORMALIZATION_ROUTE = re.compile(r"^/api/v3/reporting/events/(?P<event_id>[A-Za-z0-9_-]+)/normalization$")
_UNIT_BASELINE_ROUTE = re.compile(r"^/api/v3/reporting/units/(?P<unit_id>[^/]+)/baseline$")
_UNIT_BASELINES_LIST_ROUTE = re.compile(r"^/api/v3/reporting/units/baselines$")
_IMAMS_ROUTE = re.compile(r"^/api/v3/reporting/imams$")
_IMAM_ID_ROUTE = re.compile(r"^/api/v3/reporting/imams/(?P<imam_id>[A-Za-z0-9_-]+)$")
_IMAM_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/imams/(?P<imam_id>[A-Za-z0-9_-]+)/delete$")
_VENUES_ROUTE = re.compile(r"^/api/v3/reporting/venues$")
_VENUE_ID_ROUTE = re.compile(r"^/api/v3/reporting/venues/(?P<venue_id>[A-Za-z0-9_-]+)$")
_VENUE_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/venues/(?P<venue_id>[A-Za-z0-9_-]+)/delete$")
_PERSONS_ROUTE = re.compile(r"^/api/v3/reporting/persons$")
_PERSON_ID_ROUTE = re.compile(r"^/api/v3/reporting/persons/(?P<person_id>[A-Za-z0-9_-]+)$")
_PERSON_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/persons/(?P<person_id>[A-Za-z0-9_-]+)/delete$")
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
_LIAISON_SYNC_EITAA_CONTACT_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/(?P<liaison_id>[A-Za-z0-9_-]+)/sync-eitaa-contact$")
_LIAISONS_SYNC_ALL_EITAA_CONTACTS_ROUTE = re.compile(r"^/api/v3/reporting/liaisons/sync-all-eitaa-contacts$")
_INDICATORS_MACRO_ROUTE = re.compile(r"^/api/v3/reporting/indicators/macro$")
_INDICATORS_MICRO_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro$")
_INDICATORS_MICRO_ID_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro/(?P<indicator_id>[A-Za-z0-9_-]+)$")
_INDICATORS_MICRO_DELETE_POST_ROUTE = re.compile(r"^/api/v3/reporting/indicators/micro/(?P<indicator_id>[A-Za-z0-9_-]+)/delete$")
_INDICATORS_MESSAGES_ROUTE = re.compile(r"^/api/v3/reporting/indicators/messages$")
_INDICATORS_MESSAGES_ASSIGN_ROUTE = re.compile(r"^/api/v3/reporting/indicators/messages/assign$")
_MESSAGE_SPLITS_ROUTE = re.compile(r"^/api/v3/reporting/splits$")
_PROGRAM_CATALOG_ROUTE = re.compile(r"^/api/v3/reporting/catalog/programs$")
_PROGRAM_CATALOG_TOGGLE_ROUTE = re.compile(r"^/api/v3/reporting/catalog/programs/toggle-active$")



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


def _build_event_payload(payload: Mapping[str, Any], store: ReportingStore | None = None):
    raw = payload.get("occurred_on")
    try:
        norm = normalize_to_iso_date(raw) if raw else date.today().isoformat()
        occurred = date.fromisoformat(norm)
    except ValueError:
        return _error(400, "occurred_on must be an ISO or Jalali date")

    macro_cat = str(payload.get("macro_category", "workbook_approved") or "workbook_approved").strip()
    macro_category = "other_cultural" if macro_cat == "other_cultural" else "workbook_approved"
    custom_topic = str(payload.get("custom_topic", "") or "").strip()
    macro_indicator = str(payload.get("macro_indicator", "") or "").strip()

    raw_kinds = payload.get("program_kinds")
    if raw_kinds and isinstance(raw_kinds, (list, tuple)) and len(raw_kinds) > 0:
        try:
            kinds = tuple(ProgramKind(str(k)) for k in raw_kinds)
        except ValueError:
            return _error(400, "unknown program kind")
    else:
        derived_kind = None
        if store and macro_indicator:
            try:
                catalog = store.list_program_catalog()
                norm_macro = macro_indicator.replace("\u200c", "").replace(" ", "").strip()
                for p in catalog:
                    p_canon = (p.get("canonical_macro") if isinstance(p, dict) else getattr(p, "canonical_macro", "")) or ""
                    p_title = (p.get("title") if isinstance(p, dict) else getattr(p, "title", "")) or ""
                    p_kind = (p.get("kind") if isinstance(p, dict) else getattr(p, "kind", "")) or ""
                    if p_kind and (norm_macro in p_canon.replace("\u200c", "").replace(" ", "").strip() or norm_macro in p_title.replace("\u200c", "").replace(" ", "").strip()):
                        derived_kind = ProgramKind(str(p_kind))
                        break
            except Exception:
                pass

        if not derived_kind and macro_indicator:
            norm = macro_indicator.replace("\u200c", "").replace(" ", "").strip()
            if "تجلیل" in norm or "تکریم" in norm:
                derived_kind = ProgramKind.HONOR
            elif "نماز" in norm:
                derived_kind = ProgramKind.PRAYER
            elif "مسابق" in norm:
                derived_kind = ProgramKind.CONTEST
            elif "اردو" in norm:
                derived_kind = ProgramKind.TRIP
            elif "ارباب" in norm or "مشتری" in norm:
                derived_kind = ProgramKind.CUSTOMER_CARE
            elif "منشور" in norm:
                derived_kind = ProgramKind.CHARTER
            elif "آموزش" in norm:
                derived_kind = ProgramKind.TRAINING
            elif "غیربرنامه" in norm:
                derived_kind = ProgramKind.NON_PROGRAMMATIC

        if derived_kind:
            kinds = (derived_kind,)
        elif macro_category == "other_cultural" or "غیر" in macro_indicator:
            kinds = (ProgramKind.NON_PROGRAMMATIC,)
        else:
            kinds = (ProgramKind.CEREMONY,)
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
        occasion=str(payload.get("occasion") or payload.get("topic") or "").strip(),
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
    built = _build_event_payload(payload, store=store)
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
    if not expected_etag:
        expected_etag = store.get_event_etag(event_id) or ""
    fields = payload.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return _error(400, "fields mapping is required")
    fields_dict = dict(fields)
    if "micro_indicators" in fields_dict and "micro_indicators_json" not in fields_dict:
        fields_dict["micro_indicators_json"] = json.dumps(fields_dict.pop("micro_indicators"), ensure_ascii=False)
    if "program_kinds" in fields_dict and "program_kinds_json" not in fields_dict:
        fields_dict["program_kinds_json"] = json.dumps(fields_dict.pop("program_kinds"), ensure_ascii=False)
    try:
        etag = store.update_event_fields(
            event_id, actor=actor, expected_etag=expected_etag, fields=fields_dict
        )
    except (ReportingStoreError, ValueError) as exc:
        mapped = _mapped_error(exc)
        return mapped if mapped else _error(400, str(exc))
    return _ok({"event_id": event_id, "etag": etag}, headers={"ETag": f'"{etag}"'})


def delete_event(store: ReportingStore, actor: str, roles, event_id: str):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    deleted = store.delete_event(event_id, actor=actor)
    if not deleted:
        return _error(404, f"event {event_id} not found", error_code="event_not_found")
    return _ok({"deleted": True, "event_id": event_id})


def get_event_file(store: ReportingStore, event_id: str, bridge_api: Any = None):
    file = store.get_event_file(event_id)
    if file is None:
        return _error(404, "event not found")
    etag = file.get("etag", "")
    headers = {"ETag": f'"{etag}"'} if etag else {}
    for doc in file.get("documents", []):
        storage_ref = doc.get("storage_ref")
        if storage_ref and os.path.exists(storage_ref) and bridge_api and hasattr(bridge_api, "register_media_cache_file"):
            try:
                path = Path(storage_ref)
                mime = mimetypes.guess_type(path.name)[0] or ("image/jpeg" if doc.get("kind") == "image" else "application/octet-stream")
                token = bridge_api.register_media_cache_file(path, mime)
                doc["media_url"] = f"/api/v1/media-cache/{token}"
            except Exception:
                pass
    for w in file.get("witnesses", []):
        storage_ref = w.get("storage_ref")
        if storage_ref and os.path.exists(storage_ref) and bridge_api and hasattr(bridge_api, "register_media_cache_file"):
            try:
                path = Path(storage_ref)
                mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                token = bridge_api.register_media_cache_file(path, mime)
                w["media_url"] = f"/api/v1/media-cache/{token}"
            except Exception:
                pass
    return _ok({"event": file}, headers=headers)


def upload_document(store: ReportingStore, actor: str, roles, event_id: str, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    filename = str(payload.get("filename") or "document.bin").strip()
    data_b64 = str(payload.get("content_base64") or "")
    if not data_b64:
        return _error(400, "content_base64 is required", error_code="missing_file_content")
    try:
        content_bytes = base64.b64decode(data_b64)
    except Exception as exc:
        return _error(400, f"invalid base64 content: {exc}", error_code="invalid_base64")

    kind = str(payload.get("kind") or "")
    is_cover = bool(payload.get("is_cover", False))
    doc = store.upload_and_attach_document(
        event_id,
        filename=filename,
        content_bytes=content_bytes,
        kind=kind,
        is_cover=is_cover,
        added_by=actor,
    )
    return _ok({"document": doc}, status=201)


def delete_document(store: ReportingStore, actor: str, roles, event_id: str, doc_id: str):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    deleted = store.delete_document(event_id, doc_id, actor=actor)
    if not deleted:
        return _error(404, f"document {doc_id} not found", error_code="document_not_found")
    return _ok({"deleted": True, "event_id": event_id, "document_id": doc_id})


def set_document_cover(store: ReportingStore, actor: str, roles, event_id: str, doc_id: str, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    is_cover = bool(payload.get("is_cover", True))
    ok = store.set_document_cover(event_id, doc_id, is_cover=is_cover, actor=actor)
    return _ok({"ok": ok, "document_id": doc_id, "is_cover": is_cover})


def view_document(store: ReportingStore, event_id: str, doc_id: str, bridge_api: Any = None):
    file = store.get_event_file(event_id)
    if not file:
        return _error(404, f"event {event_id} not found", error_code="event_not_found")
    doc = next((d for d in file.get("documents", []) if d.get("document_id") == doc_id), None)
    if not doc:
        return _error(404, f"document {doc_id} not found", error_code="document_not_found")
    storage_ref = doc.get("storage_ref")
    if storage_ref and os.path.exists(storage_ref):
        path = Path(storage_ref)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        media_url = ""
        if bridge_api and hasattr(bridge_api, "register_media_cache_file"):
            try:
                token = bridge_api.register_media_cache_file(path, mime)
                media_url = f"/api/v1/media-cache/{token}"
            except Exception:
                pass
        data_bytes = path.read_bytes()
        data_b64 = base64.b64encode(data_bytes).decode("ascii")
        return _ok({
            "document_id": doc_id,
            "filename": doc.get("media_id") or path.name,
            "mime_type": mime,
            "size_bytes": len(data_bytes),
            "media_url": media_url,
            "content_base64": data_b64,
        })
    return _error(404, "physical file not found on disk", error_code="file_missing")


def list_merge_candidates(store: ReportingStore, event_id: str):
    candidates = store.find_merge_candidates(event_id)
    return _ok({"candidates": candidates, "count": len(candidates)})


def execute_merge(store: ReportingStore, actor: str, roles, target_event_id: str, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    source_event_id = str(payload.get("source_event_id") or "").strip()
    if not source_event_id:
        return _error(400, "source_event_id is required", error_code="missing_source_event_id")
    try:
        res = store.merge_events(target_event_id, source_event_id, actor=actor)
        return _ok(res)
    except Exception as exc:
        return _error(400, str(exc), error_code="merge_failed")


def get_unit_baseline(store: ReportingStore, unit_id: str):
    from urllib.parse import unquote
    b = store.get_unit_baseline(unquote(unit_id))
    return _ok({"baseline": b})


def save_unit_baseline(store: ReportingStore, actor: str, roles, unit_id: str, payload: Mapping[str, Any]):
    denied = _forbidden(roles, "editor")
    if denied:
        return denied
    from urllib.parse import unquote
    b = store.save_unit_baseline(
        unquote(unit_id),
        staff_count=int(payload.get("staff_count", 0)),
        family_multiplier=float(payload.get("family_multiplier", 2.5)),
        imams_count=int(payload.get("imams_count", 0)),
        prayer_rooms_count=int(payload.get("prayer_rooms_count", 0)),
        honored_count=int(payload.get("honored_count", 0)),
        notes=str(payload.get("notes") or ""),
    )
    return _ok({"baseline": b})


def list_unit_baselines(store: ReportingStore):
    return _ok({"baselines": store.list_unit_baselines()})


def list_imams(store: ReportingStore, query: Mapping[str, Any]):
    unit_id = query.get("unit_id") or None
    imams = store.list_imams(unit_id=unit_id)
    return _ok({"imams": [i.to_dict() for i in imams]})


def save_imam(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    imam_id = str(payload.get("imam_id") or "").strip() or f"imam_{uuid.uuid4().hex[:8]}"
    unit_id = str(payload.get("unit_id") or "").strip()
    if not unit_id:
        return _error(400, "unit_id is required")
    units = store.list_units()
    matched = next((u for u in units if u.unit_id == unit_id or u.display_name == unit_id or u.name == unit_id), None)
    if matched:
        unit_id = matched.unit_id
    record = ImamRecord(
        imam_id=imam_id,
        unit_id=unit_id,
        full_name=str(payload.get("full_name") or ""),
        position=str(payload.get("position") or ""),
        source_kind=str(payload.get("source_kind") or "none"),
        status=str(payload.get("status") or "employed"),
        personnel_no=str(payload.get("personnel_no") or ""),
        notes=str(payload.get("notes") or ""),
    )
    store.save_imam(record)
    return _ok({"imam": record.to_dict()})


def delete_imam(store: ReportingStore, imam_id: str):
    success = store.delete_imam(imam_id)
    if not success:
        return _error(404, "imam not found")
    return _ok({"deleted": True, "imam_id": imam_id})


def list_venues(store: ReportingStore, query: Mapping[str, Any]):
    unit_id = query.get("unit_id") or None
    venues = store.list_venues(unit_id=unit_id)
    return _ok({"venues": [v.to_dict() for v in venues]})


def save_venue(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    venue_id = str(payload.get("venue_id") or "").strip() or f"venue_{uuid.uuid4().hex[:8]}"
    unit_id = str(payload.get("unit_id") or "").strip()
    if not unit_id:
        return _error(400, "unit_id is required")
    units = store.list_units()
    matched = next((u for u in units if u.unit_id == unit_id or u.display_name == unit_id or u.name == unit_id), None)
    if matched:
        unit_id = matched.unit_id
    record = VenueRecord(
        venue_id=venue_id,
        unit_id=unit_id,
        name=str(payload.get("name") or ""),
        notes=str(payload.get("notes") or ""),
    )
    store.save_venue(record)
    return _ok({"venue": record.to_dict()})


def delete_venue(store: ReportingStore, venue_id: str):
    success = store.delete_venue(venue_id)
    if not success:
        return _error(404, "venue not found")
    return _ok({"deleted": True, "venue_id": venue_id})


def list_persons(store: ReportingStore, query: Mapping[str, Any]):
    kind = query.get("kind") or None
    unit_id = query.get("unit_id") or None
    persons = store.list_persons(kind=kind, unit_id=unit_id)
    return _ok({"persons": [p.to_dict() for p in persons]})


def save_person(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    person_id = str(payload.get("person_id") or "").strip() or f"person_{uuid.uuid4().hex[:8]}"
    record = PersonRecord(
        person_id=person_id,
        kind=str(payload.get("kind") or "employee"),
        full_name=str(payload.get("full_name") or ""),
        personnel_no=str(payload.get("personnel_no") or ""),
        national_id=str(payload.get("national_id") or ""),
        phone=str(payload.get("phone") or ""),
        relation=str(payload.get("relation") or ""),
        related_personnel_no=str(payload.get("related_personnel_no") or ""),
        unit_id=str(payload.get("unit_id") or ""),
        gender=str(payload.get("gender") or ""),
        birth_year=str(payload.get("birth_year") or ""),
        notes=str(payload.get("notes") or ""),
    )
    store.save_person(record)
    return _ok({"person": record.to_dict()})


def delete_person(store: ReportingStore, person_id: str):
    success = store.delete_person(person_id)
    if not success:
        return _error(404, "person not found")
    return _ok({"deleted": True, "person_id": person_id})


def get_event_normalization(store: ReportingStore, event_id: str):
    try:
        res = store.normalize_event_statistics(event_id)
        return _ok(res)
    except Exception as exc:
        return _error(404, str(exc), error_code="normalization_failed")


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
        limit = int(q.get("limit", 200))
    except (ValueError, TypeError):
        limit = 200
    review_status = str(q.get("review_status", "")).strip() or None
    registered_by_id = str(q.get("registered_by_id", "")).strip() or None
    macro_category = str(q.get("macro_category", "")).strip() or None
    micro_indicator = str(q.get("micro_indicator", "")).strip() or None
    macro_indicator = str(q.get("macro_indicator", "")).strip() or None
    unit_name = str(q.get("unit_name", "")).strip() or None
    program_code = str(q.get("program_code", "")).strip() or None
    search = str(q.get("search", "")).strip() or None

    events = store.list_events(
        limit=limit,
        review_status=review_status,
        registered_by_id=registered_by_id,
        macro_category=macro_category,
        micro_indicator=micro_indicator,
        macro_indicator=macro_indicator,
        unit_name=unit_name,
        program_code=program_code,
        search_query=search,
    )
    return _ok({
        "events": [
            {
                "event_id": ev.event_id,
                "program_kinds": [k.value for k in ev.program_kinds],
                "occurred_on": ev.occurred_on.isoformat(),
                "unit": ev.unit.value,
                "unit_name": ev.unit_name,
                "occasion": ev.occasion,
                "macro_category": ev.macro_category,
                "custom_topic": ev.custom_topic,
                "macro_indicator": ev.macro_indicator,
                "micro_indicators": ev.micro_indicators,
                "notes": ev.notes,
                "review_status": ev.review_status,
                "registered_by_id": ev.registered_by_id,
                "registered_by_name": ev.registered_by_name,
                "reviewed_by_id": ev.reviewed_by_id,
                "reviewed_by_name": ev.reviewed_by_name,
                "reviewed_at": ev.reviewed_at.isoformat() if ev.reviewed_at else None,
                "review_notes": ev.review_notes,
                "revision_count": ev.revision_count,
                "defects_json": ev.defects_json,
                "defects": json.loads(ev.defects_json) if ev.defects_json else [],
                "facts_count": len(ev.facts),
                "facts": [
                    {
                        "metric": f.metric,
                        "value": f.value,
                        "unit_of_measure": f.unit_of_measure,
                        "value_kind": f.value_kind.value,
                    }
                    for f in ev.facts
                ],
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ]
    })


def export_filtered_events(store: ReportingStore, actor: str, payload: Mapping[str, Any], bridge_api: Any = None):
    from ..reporting.excel_export import export_events_list_to_excel
    import uuid
    from datetime import datetime

    review_status = str(payload.get("review_status", "")).strip() or None
    micro_indicator = str(payload.get("micro_indicator", "")).strip() or None
    macro_indicator = str(payload.get("macro_indicator", "")).strip() or None
    unit_name = str(payload.get("unit_name", "")).strip() or None
    program_code = str(payload.get("program_code", "")).strip() or None
    search = str(payload.get("search", "")).strip() or None

    events = store.list_events(
        limit=5000,
        review_status=review_status,
        micro_indicator=micro_indicator,
        macro_indicator=macro_indicator,
        unit_name=unit_name,
        program_code=program_code,
        search_query=search,
    )
    dest_dir = store.db_path.parent / "reporting"
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"events_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.xlsx"
    dest_file = dest_dir / filename
    export_events_list_to_excel(events, dest_file, province_name="مازندران", title="گزارش رویدادها و فعالیت‌های فرهنگی")
    media_url = ""
    if bridge_api and hasattr(bridge_api, "register_media_cache_file"):
        try:
            token = bridge_api.register_media_cache_file(dest_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            media_url = f"/api/v1/media-cache/{token}"
        except Exception:
            pass
    return _ok({
        "file_name": filename,
        "path": str(dest_file),
        "count": len(events),
        "media_url": media_url,
    })


def export_dossier_bundle_api(store: ReportingStore, actor: str, payload: Mapping[str, Any], bridge_api: Any = None):
    from eitaa_bridge.reporting.excel_export import create_dossier_bundle
    review_status = payload.get("review_status") or None
    registered_by_id = payload.get("registered_by_id") or None
    macro_category = payload.get("macro_category") or None
    micro_indicator = payload.get("micro_indicator") or None
    macro_indicator = payload.get("macro_indicator") or None
    unit_name = payload.get("unit_name") or None
    program_code = payload.get("program_code") or None
    search = payload.get("search") or None

    events = store.list_events(
        limit=int(payload.get("limit", 500)),
        review_status=review_status,
        registered_by_id=registered_by_id,
        macro_category=macro_category,
        micro_indicator=micro_indicator,
        macro_indicator=macro_indicator,
        unit_name=unit_name,
        program_code=program_code,
        search_query=search,
    )
    if not events:
        return _error(400, "هیچ رویدادی با فیلترهای انتخابی یافت نشد.", error_code="no_events_found")

    dest_dir = store.db_path.parent / "reporting"
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"dossier_bundle_{date.today().isoformat()}_{uuid.uuid4().hex[:6]}.zip"
    dest_file = dest_dir / filename

    bundle_info = create_dossier_bundle(
        store,
        events,
        dest_file,
        province_name="مازندران",
        title="بسته جامع اسناد و رویدادهای فرهنگی",
    )

    media_url = ""
    if bridge_api and hasattr(bridge_api, "register_media_cache_file"):
        try:
            token = bridge_api.register_media_cache_file(dest_file, "application/zip")
            media_url = f"/api/v1/media-cache/{token}"
        except Exception:
            pass

    return _ok({
        **bundle_info,
        "file_name": filename,
        "path": str(dest_file),
        "media_url": media_url,
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


def sync_liaison_eitaa_contact(store: ReportingStore, liaison_id: str, payload: Mapping[str, Any], bridge_api: Any = None):
    try:
        phone = str(payload.get("phone", "") or "").strip()
        result = store.sync_liaison_to_eitaa_contact(liaison_id, phone=phone, bridge_api=bridge_api)
        return _ok(result)
    except ValueError as ve:
        return _error(400, str(ve))
    except Exception as exc:
        return _error(500, f"خطا در ثبت مخاطب در ایتا: {exc}")


def sync_all_liaisons_eitaa_contacts(store: ReportingStore, bridge_api: Any = None):
    try:
        result = store.sync_all_liaisons_to_eitaa_contacts(bridge_api=bridge_api)
        return _ok(result)
    except Exception as exc:
        return _error(500, f"خطا در ثبت گروهی مخاطبین در ایتا: {exc}")


def list_program_catalog(store: ReportingStore, query: Mapping[str, Any] | None):
    q = query or {}
    year = None
    if q.get("year"):
        try:
            year = int(q["year"])
        except (ValueError, TypeError):
            year = None
    include_inactive = q.get("include_inactive") in ("1", "true", "True")
    programs = store.list_program_catalog(year=year, include_inactive=include_inactive)
    return _ok({"programs": programs})


def save_program_catalog_item(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    program_code = str(payload.get("program_code", "") or "").strip()
    title = str(payload.get("title", "") or "").strip()
    canonical_macro = str(payload.get("canonical_macro", "") or "").strip()
    kind = str(payload.get("kind", "custom") or "custom").strip()
    workbook_sheet = str(payload.get("workbook_sheet", "") or "").strip()
    description = str(payload.get("description", "") or "").strip()
    try:
        valid_from_year = int(payload.get("valid_from_year", 1403))
    except (ValueError, TypeError):
        valid_from_year = 1403
    raw_to_year = payload.get("valid_to_year")
    valid_to_year = int(raw_to_year) if raw_to_year not in (None, "") else None
    is_active = bool(payload.get("is_active", True))
    try:
        display_order = int(payload.get("display_order", 0))
    except (ValueError, TypeError):
        display_order = 0

    if not program_code or not title:
        return _error(400, "کد برنامه و عنوان برنامه الزامی است.")
    try:
        item = store.save_program_catalog_item(
            program_code=program_code,
            title=title,
            canonical_macro=canonical_macro,
            kind=kind,
            workbook_sheet=workbook_sheet,
            valid_from_year=valid_from_year,
            valid_to_year=valid_to_year,
            is_active=is_active,
            display_order=display_order,
            description=description,
        )
        return _ok({"program": item}, status=201)
    except Exception as exc:
        return _error(400, str(exc))


def toggle_program_active(store: ReportingStore, actor: str, payload: Mapping[str, Any]):
    program_code = str(payload.get("program_code", "") or "").strip()
    if not program_code:
        return _error(400, "کد برنامه الزامی است.")
    is_active = bool(payload.get("is_active", True))
    try:
        item = store.toggle_program_active(program_code, is_active=is_active)
        return _ok({"program": item})
    except Exception as exc:
        return _error(400, str(exc))


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
             if_match: str | None = None,
             bridge_api: Any = None):
    """Route /api/v3/reporting/* requests; None when the path is unknown."""
    payload = payload or {}
    query = query or {}
    if method == "POST" and _EVENTS_ROUTE.match(path):
        denied = _forbidden(roles, "editor")
        return denied if denied else create_event(store, actor, payload)
    if method == "POST" and _EVENTS_EXPORT_ROUTE.match(path):
        return export_filtered_events(store, actor, payload, bridge_api=bridge_api)
    if method == "POST" and _EVENTS_DOSSIER_BUNDLE_ROUTE.match(path):
        return export_dossier_bundle_api(store, actor, payload, bridge_api=bridge_api)
    doc_match = _EVENT_DOCUMENTS_ROUTE.match(path)
    if doc_match and method in {"POST", "PUT"}:
        return attach_document(store, actor, roles, doc_match.group("event_id"), payload)
    match = _EVENT_ID_ROUTE.match(path)
    if match:
        event_id = match.group("event_id")
        if method == "GET":
            return get_event_file(store, event_id, bridge_api=bridge_api)
        if method == "PUT":
            denied = _forbidden(roles, "editor")
            if denied:
                return denied
            return update_event(store, actor, event_id, payload, if_match=if_match)
        if method == "DELETE":
            return delete_event(store, actor, roles, event_id)
    if method == "PUT":
        micro_put = _INDICATORS_MICRO_ID_ROUTE.match(path)
        if micro_put:
            return update_micro_indicator(store, actor, micro_put.group("indicator_id"), payload)
    if method == "POST":
        event_del_match = _EVENT_DELETE_POST_ROUTE.match(path)
        if event_del_match:
            return delete_event(store, actor, roles, event_del_match.group("event_id"))
        upload_match = _EVENT_DOCUMENTS_UPLOAD_ROUTE.match(path)
        if upload_match:
            return upload_document(store, actor, roles, upload_match.group("event_id"), payload)
        doc_del_match = _EVENT_DOCUMENT_DELETE_POST_ROUTE.match(path)
        if doc_del_match:
            return delete_document(store, actor, roles, doc_del_match.group("event_id"), doc_del_match.group("doc_id"))
        doc_cover_match = _EVENT_DOCUMENT_COVER_POST_ROUTE.match(path)
        if doc_cover_match:
            return set_document_cover(store, actor, roles, doc_cover_match.group("event_id"), doc_cover_match.group("doc_id"), payload)
        merge_match = _EVENT_MERGE_ROUTE.match(path)
        if merge_match:
            return execute_merge(store, actor, roles, merge_match.group("event_id"), payload)
        base_match = _UNIT_BASELINE_ROUTE.match(path)
        if base_match:
            return save_unit_baseline(store, actor, roles, base_match.group("unit_id"), payload)
        if _IMAMS_ROUTE.match(path):
            return save_imam(store, actor, payload)
        imam_post_del = _IMAM_DELETE_POST_ROUTE.match(path)
        if imam_post_del:
            return delete_imam(store, imam_post_del.group("imam_id"))
        if _VENUES_ROUTE.match(path):
            return save_venue(store, actor, payload)
        venue_post_del = _VENUE_DELETE_POST_ROUTE.match(path)
        if venue_post_del:
            return delete_venue(store, venue_post_del.group("venue_id"))
        if _PERSONS_ROUTE.match(path):
            return save_person(store, actor, payload)
        person_post_del = _PERSON_DELETE_POST_ROUTE.match(path)
        if person_post_del:
            return delete_person(store, person_post_del.group("person_id"))
        micro_post_del = _INDICATORS_MICRO_DELETE_POST_ROUTE.match(path)
        if micro_post_del:
            return delete_micro_indicator(store, actor, micro_post_del.group("indicator_id"))
        if _PROGRAM_CATALOG_ROUTE.match(path):
            return save_program_catalog_item(store, actor, payload)
        if _PROGRAM_CATALOG_TOGGLE_ROUTE.match(path):
            return toggle_program_active(store, actor, payload)
        if _INDICATORS_MICRO_ROUTE.match(path):
            return save_micro_indicator(store, actor, payload)
        if _INDICATORS_MESSAGES_ASSIGN_ROUTE.match(path):
            return assign_message_indicators(store, actor, payload)
        if _MESSAGE_SPLITS_ROUTE.match(path):
            return set_message_splits(store, actor, payload)
        sync_contact_match = _LIAISON_SYNC_EITAA_CONTACT_ROUTE.match(path)
        if sync_contact_match:
            return sync_liaison_eitaa_contact(store, sync_contact_match.group("liaison_id"), payload, bridge_api=bridge_api)
        if _LIAISONS_SYNC_ALL_EITAA_CONTACTS_ROUTE.match(path):
            return sync_all_liaisons_eitaa_contacts(store, bridge_api=bridge_api)
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
        if _PROGRAM_CATALOG_ROUTE.match(path):
            return list_program_catalog(store, query)
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
        merge_cand_match = _EVENT_MERGE_CANDIDATES_ROUTE.match(path)
        if merge_cand_match:
            return list_merge_candidates(store, merge_cand_match.group("event_id"))
        doc_view_match = _EVENT_DOCUMENT_VIEW_ROUTE.match(path)
        if doc_view_match:
            return view_document(store, doc_view_match.group("event_id"), doc_view_match.group("doc_id"), bridge_api=bridge_api)
        norm_match = _EVENT_NORMALIZATION_ROUTE.match(path)
        if norm_match:
            return get_event_normalization(store, norm_match.group("event_id"))
        if _UNIT_BASELINES_LIST_ROUTE.match(path):
            return list_unit_baselines(store)
        base_match = _UNIT_BASELINE_ROUTE.match(path)
        if base_match:
            return get_unit_baseline(store, base_match.group("unit_id"))
        if _IMAMS_ROUTE.match(path):
            return list_imams(store, query)
        if _VENUES_ROUTE.match(path):
            return list_venues(store, query)
        if _PERSONS_ROUTE.match(path):
            return list_persons(store, query)
        audit = _EVENT_AUDIT_ROUTE.match(path)
        if audit:
            return get_event_audit(store, actor, roles, audit.group("event_id"))
    if method == "DELETE":
        doc_del_match = _EVENT_DOCUMENT_ID_ROUTE.match(path)
        if doc_del_match:
            return delete_document(store, actor, roles, doc_del_match.group("event_id"), doc_del_match.group("doc_id"))
        micro_del = _INDICATORS_MICRO_ID_ROUTE.match(path)
        if micro_del:
            return delete_micro_indicator(store, actor, micro_del.group("indicator_id"))
        unit_del = _UNIT_ID_ROUTE.match(path)
        if unit_del:
            return delete_unit(store, actor, unit_del.group("unit_id"))
        liaison_del = _LIAISON_ID_ROUTE.match(path)
        if liaison_del:
            return delete_liaison(store, actor, liaison_del.group("liaison_id"))
        imam_del = _IMAM_ID_ROUTE.match(path)
        if imam_del:
            return delete_imam(store, imam_del.group("imam_id"))
        venue_del = _VENUE_ID_ROUTE.match(path)
        if venue_del:
            return delete_venue(store, venue_del.group("venue_id"))
        person_del = _PERSON_ID_ROUTE.match(path)
        if person_del:
            return delete_person(store, person_del.group("person_id"))
    return None



"""SQLite persistent storage for the 1405 reporting core and indexing queue.

Stores watch targets, index decisions, event candidates, human review records,
confirmed ReportedEvents with Facts, filled forms, and export audit trails.
Never contains raw message texts or sensitive credentials (ADR-47/governance).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Iterator, Mapping, Sequence
import uuid

from .eitaa_extraction import EventCandidate
from .forms import FORMS_BY_PROGRAM, FilledForm, FormAnswer
from .indexer import IndexDecision
from .metrics import METRIC_DICTIONARY
from .model import (
    Fact,
    FactValueKind,
    OccasionClass,
    ProgramId,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from .monitor import DialogWatchConfig
from .plans import Mandate, PlanItem
from .registry import EntityFact, ImamRecord, NomokalafRecord, UnitRecord, VenueRecord

REPORTING_SCHEMA_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReportingStoreError(Exception):
    """Base error for reporting storage operations."""


class ReportingStore:
    """Thread-safe SQLite store for reporting entities and candidate workflows."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()
        self._local = threading.local()
        self.initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create tables and initialize default watch targets if fresh."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reporting_schema (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reporting_targets (
                    target_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL UNIQUE,
                    match_keywords_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS index_decisions (
                    decision_id TEXT PRIMARY KEY,
                    message_ref TEXT NOT NULL,
                    dialog_label TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    score REAL NOT NULL,
                    matched_programs_json TEXT NOT NULL,
                    matched_execution_json TEXT NOT NULL,
                    matched_units_json TEXT NOT NULL,
                    matched_occasions_json TEXT NOT NULL,
                    attendee_count INTEGER,
                    occasion_class TEXT,
                    is_ashura_pilgrimage INTEGER NOT NULL DEFAULT 0,
                    decided_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_decisions_ref ON index_decisions(message_ref);
                CREATE INDEX IF NOT EXISTS idx_decisions_intent ON index_decisions(intent);

                CREATE TABLE IF NOT EXISTS event_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    event_key TEXT NOT NULL,
                    suggested_kinds_json TEXT NOT NULL,
                    extracted_attendees INTEGER,
                    extracted_date TEXT,
                    occasion_class TEXT,
                    is_ashura_pilgrimage INTEGER NOT NULL DEFAULT 0,
                    sender_hint TEXT,
                    dialog_label TEXT,
                    source_message_refs_json TEXT NOT NULL,
                    confidence_note TEXT,
                    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending', 'approved', 'rejected')),
                    promoted_event_id TEXT,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    rejection_reason TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidates_status ON event_candidates(review_status);
                CREATE INDEX IF NOT EXISTS idx_candidates_key ON event_candidates(event_key);

                CREATE TABLE IF NOT EXISTS reported_events (
                    event_id TEXT PRIMARY KEY,
                    program_kinds_json TEXT NOT NULL,
                    occurred_on TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    unit_name TEXT NOT NULL,
                    occasion TEXT,
                    occasion_class TEXT,
                    official_present INTEGER,
                    is_standalone_titled INTEGER NOT NULL DEFAULT 1,
                    duration_minutes INTEGER,
                    prior_announcement INTEGER NOT NULL DEFAULT 0,
                    had_reception INTEGER NOT NULL DEFAULT 0,
                    is_ashura_pilgrimage INTEGER NOT NULL DEFAULT 0,
                    contains_inner_contest INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT
                );

                CREATE TABLE IF NOT EXISTS event_facts (
                    fact_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES reported_events(event_id) ON DELETE CASCADE,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    value_kind TEXT NOT NULL,
                    unit_of_measure TEXT NOT NULL DEFAULT 'count',
                    scope TEXT NOT NULL DEFAULT 'province',
                    evidence_refs_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    note TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_event_facts_event ON event_facts(event_id);

                CREATE TABLE IF NOT EXISTS filled_forms (
                    program_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    answers_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT
                );

                CREATE TABLE IF NOT EXISTS report_exports (
                    export_id TEXT PRIMARY KEY,
                    export_path TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    province_name TEXT NOT NULL,
                    total_events INTEGER NOT NULL,
                    exported_at TEXT NOT NULL,
                    exported_by TEXT
                );

                CREATE TABLE IF NOT EXISTS reporting_config (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reporting_units (
                    unit_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL DEFAULT 'judicial_domain',
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS registry_imams (
                    imam_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL REFERENCES reporting_units(unit_id) ON DELETE CASCADE,
                    full_name TEXT NOT NULL DEFAULT '',
                    position TEXT NOT NULL DEFAULT '',
                    source_kind TEXT NOT NULL DEFAULT 'none',
                    status TEXT NOT NULL DEFAULT 'employed',
                    since TEXT,
                    personnel_no TEXT NOT NULL DEFAULT '',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_imams_unit ON registry_imams(unit_id);

                CREATE TABLE IF NOT EXISTS registry_venues (
                    venue_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL REFERENCES reporting_units(unit_id) ON DELETE CASCADE,
                    name TEXT NOT NULL DEFAULT '',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_venues_unit ON registry_venues(unit_id);

                CREATE TABLE IF NOT EXISTS registry_nomokalaf (
                    nom_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL REFERENCES reporting_units(unit_id) ON DELETE CASCADE,
                    year TEXT NOT NULL,
                    grain TEXT NOT NULL CHECK(grain IN ('person', 'aggregate')),
                    person_count INTEGER,
                    full_name TEXT NOT NULL DEFAULT '',
                    gender TEXT NOT NULL DEFAULT '',
                    age INTEGER,
                    taklif_year TEXT NOT NULL DEFAULT '',
                    parents TEXT NOT NULL DEFAULT '',
                    personnel_no TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    linked_event_ids_json TEXT NOT NULL DEFAULT '[]',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_nomokalaf_unit_year ON registry_nomokalaf(unit_id, year);
                -- PII notice: person columns above stay inside the local store;
                -- projections aggregate to counts only (F-075 privacy rule).

                CREATE TABLE IF NOT EXISTS entity_facts (
                    fact_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'venue', 'imam', 'nomokalaf')),
                    entity_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL DEFAULT 0.0,
                    text_value TEXT NOT NULL DEFAULT '',
                    value_kind TEXT NOT NULL DEFAULT 'reported_by_unit',
                    unit_of_measure TEXT NOT NULL DEFAULT 'count',
                    period TEXT NOT NULL DEFAULT '1405',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT 'manual',
                    note TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_entity_facts_entity ON entity_facts(entity_type, entity_id, period);
                CREATE INDEX IF NOT EXISTS idx_entity_facts_metric ON entity_facts(metric, period);

                CREATE TABLE IF NOT EXISTS normalization_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    batch_key TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT 'unit',
                    unit_name TEXT NOT NULL DEFAULT '',
                    metric TEXT NOT NULL,
                    raw_text TEXT NOT NULL DEFAULT '',
                    proposed_value TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.3,
                    source_column TEXT,
                    source_ref TEXT,
                    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending', 'approved', 'rejected')),
                    promoted_fact_id TEXT,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    rejection_reason TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_norm_candidates_status ON normalization_candidates(review_status);

                CREATE TABLE IF NOT EXISTS program_plans (
                    plan_id TEXT NOT NULL,
                    period TEXT NOT NULL DEFAULT '1405',
                    section TEXT NOT NULL DEFAULT 'prayer',
                    strategy TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    plan_type TEXT NOT NULL DEFAULT 'central_mandated',
                    targets_json TEXT NOT NULL DEFAULT '{}',
                    campaign_tag TEXT NOT NULL DEFAULT '',
                    mandate_ids_json TEXT NOT NULL DEFAULT '[]',
                    needs_confirmation INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, period)
                );

                CREATE TABLE IF NOT EXISTS mandates (
                    mandate_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    number TEXT NOT NULL DEFAULT '',
                    issued_on TEXT NOT NULL DEFAULT '',
                    document_ref TEXT NOT NULL DEFAULT '',
                    notes TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

            # Migration v1→v2: the campaign (طرح) dimension on events.
            event_columns = {row[1] for row in conn.execute("PRAGMA table_info(reported_events)")}
            if "campaign" not in event_columns:
                conn.execute("ALTER TABLE reported_events ADD COLUMN campaign TEXT NOT NULL DEFAULT ''")

            # Seed schema version if not recorded
            cur = conn.execute("SELECT version FROM reporting_schema WHERE version = ?", (REPORTING_SCHEMA_VERSION,))
            if not cur.fetchone():
                conn.execute(
                    "INSERT INTO reporting_schema (version, applied_at) VALUES (?, ?)",
                    (REPORTING_SCHEMA_VERSION, _utc_now()),
                )

            # Seed default watch targets if none exist
            count_targets = conn.execute("SELECT COUNT(*) FROM reporting_targets").fetchone()[0]
            if count_targets == 0:
                now = _utc_now()
                defaults = (
                    ("tgt-1", "مدیریت امور فرهنگی دادگستری", json.dumps(["امور فرهنگی", "فرهنگی"], ensure_ascii=False), 1, now, now),
                    ("tgt-2", "رابطان فرهنگی دادگستری", json.dumps(["رابطان فرهنگی", "رابطان"], ensure_ascii=False), 1, now, now),
                )
                conn.executemany(
                    "INSERT INTO reporting_targets (target_id, label, match_keywords_json, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    defaults,
                )

            # Seed default reporting settings if empty
            count_config = conn.execute("SELECT COUNT(*) FROM reporting_config").fetchone()[0]
            if count_config == 0:
                now = _utc_now()
                initial_config = {
                    "report_period": "۱۴۰۵",
                    "province_name": "مازندران",
                    "template_path": "",
                    "output_dir": "",
                }
                for k, v in initial_config.items():
                    conn.execute(
                        "INSERT INTO reporting_config (key, value_json, updated_at) VALUES (?, ?, ?)",
                        (k, json.dumps(v, ensure_ascii=False), now),
                    )

    # ----------------------------------------------------------------------
    # Watch Targets
    # ----------------------------------------------------------------------
    def list_targets(self) -> list[DialogWatchConfig]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT label, match_keywords_json, enabled FROM reporting_targets ORDER BY created_at"
            ).fetchall()
            return [
                DialogWatchConfig(
                    label=row["label"],
                    match_keywords=tuple(json.loads(row["match_keywords_json"])),
                    enabled=bool(row["enabled"]),
                )
                for row in rows
            ]

    def save_target(self, target: DialogWatchConfig) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_targets (target_id, label, match_keywords_json, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(label) DO UPDATE SET
                    match_keywords_json = excluded.match_keywords_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    f"tgt-{uuid.uuid4().hex[:8]}",
                    target.label,
                    json.dumps(list(target.match_keywords), ensure_ascii=False),
                    1 if target.enabled else 0,
                    now,
                    now,
                ),
            )

    def delete_target(self, label: str) -> bool:
        with self._connect() as conn:
            res = conn.execute("DELETE FROM reporting_targets WHERE label = ?", (label,))
            return res.rowcount > 0

    # ----------------------------------------------------------------------
    # Index Decisions
    # ----------------------------------------------------------------------
    def record_decision(self, decision: IndexDecision) -> None:
        now = _utc_now()
        decision_id = f"dec-{uuid.uuid4().hex[:12]}"
        decided_at_str = (
            decision.indexed_at.isoformat()
            if hasattr(decision, "indexed_at") and hasattr(decision.indexed_at, "isoformat")
            else now
        )
        unit_hints = getattr(decision, "unit_hints", ())
        matched_occasions = (
            list(decision.matched_occasions)
            if hasattr(decision, "matched_occasions")
            else ([decision.occasion_matched] if getattr(decision, "occasion_matched", "") else [])
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO index_decisions (
                    decision_id, message_ref, dialog_label, intent, score,
                    matched_programs_json, matched_execution_json, matched_units_json,
                    matched_occasions_json, attendee_count, occasion_class,
                    is_ashura_pilgrimage, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    decision.message_ref,
                    decision.dialog_label,
                    decision.intent,
                    float(decision.score),
                    json.dumps(list(decision.matched_programs), ensure_ascii=False),
                    json.dumps(list(decision.matched_execution), ensure_ascii=False),
                    json.dumps(list(unit_hints), ensure_ascii=False),
                    json.dumps(matched_occasions, ensure_ascii=False),
                    decision.attendee_count,
                    decision.occasion_class.value if decision.occasion_class else None,
                    1 if getattr(decision, "is_ashura_pilgrimage", False) else 0,
                    decided_at_str,
                ),
            )

    def list_decisions(self, *, limit: int = 100, intent: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if intent:
                rows = conn.execute(
                    """
                    SELECT decision_id, message_ref, dialog_label, intent, score,
                           matched_programs_json, matched_execution_json, matched_units_json,
                           matched_occasions_json, attendee_count, occasion_class,
                           is_ashura_pilgrimage, decided_at
                    FROM index_decisions WHERE intent = ?
                    ORDER BY decided_at DESC LIMIT ?
                    """,
                    (intent, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT decision_id, message_ref, dialog_label, intent, score,
                           matched_programs_json, matched_execution_json, matched_units_json,
                           matched_occasions_json, attendee_count, occasion_class,
                           is_ashura_pilgrimage, decided_at
                    FROM index_decisions
                    ORDER BY decided_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [
                {
                    "decision_id": row["decision_id"],
                    "message_ref": row["message_ref"],
                    "dialog_label": row["dialog_label"],
                    "intent": row["intent"],
                    "score": row["score"],
                    "matched_programs": json.loads(row["matched_programs_json"]),
                    "matched_execution": json.loads(row["matched_execution_json"]),
                    "matched_units": json.loads(row["matched_units_json"]),
                    "matched_occasions": json.loads(row["matched_occasions_json"]),
                    "attendee_count": row["attendee_count"],
                    "occasion_class": row["occasion_class"],
                    "is_ashura_pilgrimage": bool(row["is_ashura_pilgrimage"]),
                    "decided_at": row["decided_at"],
                }
                for row in rows
            ]

    # ----------------------------------------------------------------------
    # Event Candidates (Staff Review Queue)
    # ----------------------------------------------------------------------
    def save_candidate(self, candidate: EventCandidate, *, dialog_label: str = "") -> str:
        with self._connect() as conn:
            # Dedup check: if an existing candidate has this event_key and is still pending
            cur = conn.execute(
                "SELECT candidate_id FROM event_candidates WHERE event_key = ? AND review_status = 'pending'",
                (candidate.event_key,),
            )
            row = cur.fetchone()
            if row:
                return str(row["candidate_id"])

            candidate_id = f"cand-{uuid.uuid4().hex[:10]}"
            now = _utc_now()
            kinds = [k.value if hasattr(k, "value") else str(k) for k in candidate.suggested_kinds]
            conn.execute(
                """
                INSERT INTO event_candidates (
                    candidate_id, event_key, suggested_kinds_json, extracted_attendees,
                    extracted_date, occasion_class, is_ashura_pilgrimage, sender_hint,
                    dialog_label, source_message_refs_json, confidence_note, review_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    candidate_id,
                    candidate.event_key,
                    json.dumps(kinds, ensure_ascii=False),
                    candidate.extracted_attendees,
                    candidate.extracted_date,
                    candidate.occasion_class.value if candidate.occasion_class else None,
                    1 if candidate.is_ashura_pilgrimage else 0,
                    candidate.sender_hint,
                    dialog_label,
                    json.dumps(list(candidate.source_message_refs), ensure_ascii=False),
                    candidate.confidence_note,
                    now,
                ),
            )
            return candidate_id

    def list_candidates(self, *, status: str | None = "pending", limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT candidate_id, event_key, suggested_kinds_json, extracted_attendees,
                           extracted_date, occasion_class, is_ashura_pilgrimage, sender_hint,
                           dialog_label, source_message_refs_json, confidence_note, review_status,
                           promoted_event_id, reviewed_by, reviewed_at, rejection_reason, created_at
                    FROM event_candidates WHERE review_status = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT candidate_id, event_key, suggested_kinds_json, extracted_attendees,
                           extracted_date, occasion_class, is_ashura_pilgrimage, sender_hint,
                           dialog_label, source_message_refs_json, confidence_note, review_status,
                           promoted_event_id, reviewed_by, reviewed_at, rejection_reason, created_at
                    FROM event_candidates
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [
                {
                    "candidate_id": row["candidate_id"],
                    "event_key": row["event_key"],
                    "suggested_kinds": json.loads(row["suggested_kinds_json"]),
                    "extracted_attendees": row["extracted_attendees"],
                    "extracted_date": row["extracted_date"],
                    "occasion_class": row["occasion_class"],
                    "is_ashura_pilgrimage": bool(row["is_ashura_pilgrimage"]),
                    "sender_hint": row["sender_hint"],
                    "dialog_label": row["dialog_label"],
                    "source_message_refs": json.loads(row["source_message_refs_json"]),
                    "confidence_note": row["confidence_note"],
                    "review_status": row["review_status"],
                    "promoted_event_id": row["promoted_event_id"],
                    "reviewed_by": row["reviewed_by"],
                    "reviewed_at": row["reviewed_at"],
                    "rejection_reason": row["rejection_reason"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM event_candidates WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "candidate_id": row["candidate_id"],
                "event_key": row["event_key"],
                "suggested_kinds": json.loads(row["suggested_kinds_json"]),
                "extracted_attendees": row["extracted_attendees"],
                "extracted_date": row["extracted_date"],
                "occasion_class": row["occasion_class"],
                "is_ashura_pilgrimage": bool(row["is_ashura_pilgrimage"]),
                "sender_hint": row["sender_hint"],
                "dialog_label": row["dialog_label"],
                "source_message_refs": json.loads(row["source_message_refs_json"]),
                "confidence_note": row["confidence_note"],
                "review_status": row["review_status"],
                "promoted_event_id": row["promoted_event_id"],
                "reviewed_by": row["reviewed_by"],
                "reviewed_at": row["reviewed_at"],
                "rejection_reason": row["rejection_reason"],
                "created_at": row["created_at"],
            }

    def approve_candidate(self, candidate_id: str, *, event_id: str, reviewed_by: str) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE event_candidates
                SET review_status = 'approved',
                    promoted_event_id = ?,
                    reviewed_by = ?,
                    reviewed_at = ?
                WHERE candidate_id = ?
                """,
                (event_id, reviewed_by, now, candidate_id),
            )

    def reject_candidate(self, candidate_id: str, *, reviewed_by: str, reason: str = "") -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE event_candidates
                SET review_status = 'rejected',
                    reviewed_by = ?,
                    reviewed_at = ?,
                    rejection_reason = ?
                WHERE candidate_id = ?
                """,
                (reviewed_by, now, reason, candidate_id),
            )

    # ----------------------------------------------------------------------
    # Reported Events & Facts
    # ----------------------------------------------------------------------
    def save_event(self, event: ReportedEvent) -> None:
        event.validate()
        now = _utc_now()
        kinds = [k.value if hasattr(k, "value") else str(k) for k in event.program_kinds]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reported_events (
                    event_id, program_kinds_json, occurred_on, unit, unit_name,
                    occasion, occasion_class, official_present, is_standalone_titled,
                    duration_minutes, prior_announcement, had_reception,
                    is_ashura_pilgrimage, contains_inner_contest, campaign, notes, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    program_kinds_json = excluded.program_kinds_json,
                    occurred_on = excluded.occurred_on,
                    unit = excluded.unit,
                    unit_name = excluded.unit_name,
                    occasion = excluded.occasion,
                    occasion_class = excluded.occasion_class,
                    official_present = excluded.official_present,
                    is_standalone_titled = excluded.is_standalone_titled,
                    duration_minutes = excluded.duration_minutes,
                    prior_announcement = excluded.prior_announcement,
                    had_reception = excluded.had_reception,
                    is_ashura_pilgrimage = excluded.is_ashura_pilgrimage,
                    contains_inner_contest = excluded.contains_inner_contest,
                    campaign = excluded.campaign,
                    notes = excluded.notes,
                    created_by = excluded.created_by
                """,
                (
                    event.event_id,
                    json.dumps(kinds, ensure_ascii=False),
                    event.occurred_on.isoformat(),
                    event.unit.value if hasattr(event.unit, "value") else str(event.unit),
                    event.unit_name,
                    event.occasion,
                    event.occasion_class.value if event.occasion_class else None,
                    1 if event.official_present is True else (0 if event.official_present is False else None),
                    1 if event.is_standalone_titled else 0,
                    event.duration_minutes,
                    1 if event.prior_announcement else 0,
                    1 if event.had_reception else 0,
                    1 if event.is_ashura_pilgrimage else 0,
                    1 if event.contains_inner_contest else 0,
                    event.campaign,
                    event.notes,
                    event.created_at.isoformat() if hasattr(event.created_at, "isoformat") else now,
                    event.created_by,
                ),
            )

            # Re-sync facts for this event
            conn.execute("DELETE FROM event_facts WHERE event_id = ?", (event.event_id,))
            for fact in event.facts:
                fact.validate()
                fact_id = f"fact-{uuid.uuid4().hex[:10]}"
                conn.execute(
                    """
                    INSERT INTO event_facts (
                        fact_id, event_id, metric, value, value_kind, unit_of_measure,
                        scope, evidence_refs_json, source, created_at, created_by, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact_id,
                        event.event_id,
                        fact.metric,
                        float(fact.value),
                        fact.value_kind.value if hasattr(fact.value_kind, "value") else str(fact.value_kind),
                        fact.unit_of_measure,
                        fact.scope,
                        json.dumps(list(fact.evidence_refs), ensure_ascii=False),
                        fact.source.value if hasattr(fact.source, "value") else str(fact.source),
                        fact.created_at.isoformat() if hasattr(fact.created_at, "isoformat") else now,
                        fact.created_by,
                        fact.note,
                    ),
                )

    def list_events(self, *, limit: int = 100) -> list[ReportedEvent]:
        with self._connect() as conn:
            event_rows = conn.execute(
                "SELECT * FROM reported_events ORDER BY occurred_on DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            results: list[ReportedEvent] = []
            for row in event_rows:
                fact_rows = conn.execute(
                    "SELECT * FROM event_facts WHERE event_id = ?", (row["event_id"],)
                ).fetchall()

                facts = [
                    Fact(
                        metric=fr["metric"],
                        value=float(fr["value"]),
                        value_kind=FactValueKind(fr["value_kind"]),
                        unit_of_measure=fr["unit_of_measure"],
                        scope=fr["scope"],
                        evidence_refs=tuple(json.loads(fr["evidence_refs_json"])),
                        source=ValueSource(fr["source"]),
                        created_at=datetime.fromisoformat(fr["created_at"]),
                        created_by=fr["created_by"] or "",
                        note=fr["note"] or "",
                    )
                    for fr in fact_rows
                ]

                occurred = (
                    date.fromisoformat(row["occurred_on"])
                    if isinstance(row["occurred_on"], str)
                    else row["occurred_on"]
                )

                kinds = tuple(ProgramKind(k) for k in json.loads(row["program_kinds_json"]))
                unit = UnitScope(row["unit"]) if row["unit"] in {u.value for u in UnitScope} else UnitScope.PROVINCIAL_HQ
                occasion_class = OccasionClass(row["occasion_class"]) if row["occasion_class"] else None
                official_present = (
                    True if row["official_present"] == 1 else (False if row["official_present"] == 0 else None)
                )

                event = ReportedEvent(
                    event_id=row["event_id"],
                    program_kinds=kinds,
                    occurred_on=occurred,
                    unit=unit,
                    unit_name=row["unit_name"] or "",
                    occasion=row["occasion"] or "",
                    occasion_class=occasion_class,
                    facts=facts,
                    official_present=official_present,
                    is_standalone_titled=bool(row["is_standalone_titled"]),
                    duration_minutes=row["duration_minutes"],
                    prior_announcement=bool(row["prior_announcement"]),
                    had_reception=bool(row["had_reception"]),
                    is_ashura_pilgrimage=bool(row["is_ashura_pilgrimage"]),
                    contains_inner_contest=bool(row["contains_inner_contest"]),
                    campaign=row["campaign"] or "" if "campaign" in row.keys() else "",
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
                    created_by=row["created_by"] or "",
                )
                results.append(event)
            return results

    def get_event(self, event_id: str) -> ReportedEvent | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reported_events WHERE event_id = ?", (event_id,)).fetchone()
            if not row:
                return None
            fact_rows = conn.execute("SELECT * FROM event_facts WHERE event_id = ?", (event_id,)).fetchall()
            facts = [
                Fact(
                    metric=fr["metric"],
                    value=float(fr["value"]),
                    value_kind=FactValueKind(fr["value_kind"]),
                    unit_of_measure=fr["unit_of_measure"],
                    scope=fr["scope"],
                    evidence_refs=tuple(json.loads(fr["evidence_refs_json"])),
                    source=ValueSource(fr["source"]),
                    created_at=datetime.fromisoformat(fr["created_at"]),
                    created_by=fr["created_by"] or "",
                    note=fr["note"] or "",
                )
                for fr in fact_rows
            ]
            occurred = (
                date.fromisoformat(row["occurred_on"])
                if isinstance(row["occurred_on"], str)
                else row["occurred_on"]
            )
            kinds = tuple(ProgramKind(k) for k in json.loads(row["program_kinds_json"]))
            unit = UnitScope(row["unit"]) if row["unit"] in {u.value for u in UnitScope} else UnitScope.PROVINCIAL_HQ
            occasion_class = OccasionClass(row["occasion_class"]) if row["occasion_class"] else None
            official_present = (
                True if row["official_present"] == 1 else (False if row["official_present"] == 0 else None)
            )

            return ReportedEvent(
                event_id=row["event_id"],
                program_kinds=kinds,
                occurred_on=occurred,
                unit=unit,
                unit_name=row["unit_name"] or "",
                occasion=row["occasion"] or "",
                occasion_class=occasion_class,
                facts=facts,
                official_present=official_present,
                is_standalone_titled=bool(row["is_standalone_titled"]),
                duration_minutes=row["duration_minutes"],
                prior_announcement=bool(row["prior_announcement"]),
                had_reception=bool(row["had_reception"]),
                is_ashura_pilgrimage=bool(row["is_ashura_pilgrimage"]),
                contains_inner_contest=bool(row["contains_inner_contest"]),
                campaign=(row["campaign"] or "") if "campaign" in row.keys() else "",
                notes=row["notes"] or "",
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
                created_by=row["created_by"] or "",
            )

    def delete_event(self, event_id: str) -> bool:
        with self._connect() as conn:
            res = conn.execute("DELETE FROM reported_events WHERE event_id = ?", (event_id,))
            return res.rowcount > 0

    # ----------------------------------------------------------------------
    # Filled Forms
    # ----------------------------------------------------------------------
    def save_filled_form(self, form: FilledForm, *, updated_by: str = "") -> None:
        now = _utc_now()
        program_id_str = form.program_id.value if hasattr(form.program_id, "value") else str(form.program_id)
        title = FORMS_BY_PROGRAM[program_id_str].title if program_id_str in FORMS_BY_PROGRAM else program_id_str

        answers_dict: dict[str, Any] = {}
        for k, ans in form.answers.items():
            if isinstance(ans, FormAnswer):
                answers_dict[k] = {
                    "question_key": ans.question_key,
                    "value": ans.value,
                    "value_kind": ans.value_kind.value if hasattr(ans.value_kind, "value") else str(ans.value_kind),
                    "source": ans.source.value if hasattr(ans.source, "value") else str(ans.source),
                    "answered_by": ans.answered_by,
                    "note": ans.note,
                }
            else:
                answers_dict[k] = {"question_key": k, "value": ans}

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO filled_forms (program_id, title, answers_json, context_json, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(program_id) DO UPDATE SET
                    title = excluded.title,
                    answers_json = excluded.answers_json,
                    context_json = excluded.context_json,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    program_id_str,
                    title,
                    json.dumps(answers_dict, ensure_ascii=False),
                    json.dumps({}, ensure_ascii=False),
                    now,
                    updated_by,
                ),
            )

    def get_filled_form(self, program_id: ProgramId | str) -> FilledForm | None:
        pid_str = program_id.value if hasattr(program_id, "value") else str(program_id)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM filled_forms WHERE program_id = ?", (pid_str,)).fetchone()
            if not row:
                return None
            answers_dict = json.loads(row["answers_json"])
            answers: dict[str, FormAnswer] = {}
            for k, raw in answers_dict.items():
                if isinstance(raw, dict) and "value" in raw:
                    vk_str = raw.get("value_kind", "reported_by_unit")
                    vk = (
                        FactValueKind(vk_str)
                        if vk_str in {v.value for v in FactValueKind}
                        else FactValueKind.REPORTED_BY_UNIT
                    )
                    src_str = raw.get("source", "manual")
                    src = (
                        ValueSource(src_str)
                        if src_str in {s.value for s in ValueSource}
                        else ValueSource.MANUAL
                    )
                    answers[k] = FormAnswer(
                        question_key=k,
                        value=raw["value"],
                        value_kind=vk,
                        source=src,
                        answered_by=raw.get("answered_by", ""),
                        note=raw.get("note", ""),
                    )
                else:
                    answers[k] = FormAnswer(question_key=k, value=raw)

            return FilledForm(
                program_id=ProgramId(row["program_id"]),
                answers=answers,
            )

    def list_filled_forms(self) -> dict[str, FilledForm]:
        with self._connect() as conn:
            rows = conn.execute("SELECT program_id FROM filled_forms").fetchall()
            result: dict[str, FilledForm] = {}
            for row in rows:
                form = self.get_filled_form(row["program_id"])
                if form:
                    result[form.program_id.value] = form
            return result

    # ----------------------------------------------------------------------
    # Exports Audit
    # ----------------------------------------------------------------------
    def record_export(
        self,
        *,
        export_path: str | Path,
        file_sha256: str,
        report_period: str,
        province_name: str,
        total_events: int,
        exported_by: str = "",
    ) -> str:
        export_id = f"exp-{uuid.uuid4().hex[:10]}"
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_exports (
                    export_id, export_path, file_sha256, report_period,
                    province_name, total_events, exported_at, exported_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    str(export_path),
                    file_sha256,
                    report_period,
                    province_name,
                    total_events,
                    now,
                    exported_by,
                ),
            )
        return export_id

    def list_exports(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM report_exports ORDER BY exported_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    # ----------------------------------------------------------------------
    # Reporting Configuration
    # ----------------------------------------------------------------------
    def get_config(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value_json FROM reporting_config").fetchall()
            return {row["key"]: json.loads(row["value_json"]) for row in rows}

    def set_config(self, settings: Mapping[str, Any]) -> None:
        now = _utc_now()
        with self._connect() as conn:
            for k, v in settings.items():
                conn.execute(
                    """
                    INSERT INTO reporting_config (key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        updated_at = excluded.updated_at
                    """,
                    (k, json.dumps(v, ensure_ascii=False), now),
                )

    # ----------------------------------------------------------------------
    # Registry: Units (shell phase 1, F-075)
    # ----------------------------------------------------------------------
    def find_unit_by_name(self, name: str) -> UnitRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reporting_units WHERE name = ?", (name,)).fetchone()
            if not row:
                return None
            return UnitRecord(
                unit_id=row["unit_id"],
                name=row["name"],
                kind=row["kind"],
                source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                notes=row["notes"] or "",
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def save_unit(self, unit: UnitRecord) -> UnitRecord:
        unit.validate()
        now = _utc_now()
        with self._connect() as conn:
            existing = conn.execute("SELECT unit_id FROM reporting_units WHERE name = ?", (unit.name,)).fetchone()
            if existing:
                unit.unit_id = str(existing["unit_id"])
                conn.execute(
                    "UPDATE reporting_units SET kind = ?, source = ?, notes = ? WHERE unit_id = ?",
                    (unit.kind, unit.source.value, unit.notes, unit.unit_id),
                )
            else:
                if not unit.unit_id:
                    unit.unit_id = f"unit-{uuid.uuid4().hex[:10]}"
                conn.execute(
                    """
                    INSERT INTO reporting_units (unit_id, name, kind, source, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(unit_id) DO UPDATE SET
                        name = excluded.name, kind = excluded.kind,
                        source = excluded.source, notes = excluded.notes
                    """,
                    (unit.unit_id, unit.name, unit.kind, unit.source.value, unit.notes, now),
                )
        return unit

    def list_units(self) -> list[UnitRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reporting_units ORDER BY name").fetchall()
            return [
                UnitRecord(
                    unit_id=row["unit_id"],
                    name=row["name"],
                    kind=row["kind"],
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    # ----------------------------------------------------------------------
    # Registry: Imams, Venues, نومکلف bank
    # ----------------------------------------------------------------------
    def save_imam(self, imam: ImamRecord) -> None:
        imam.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_imams (
                    imam_id, unit_id, full_name, position, source_kind, status, since,
                    personnel_no, evidence_refs_json, version, source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(imam_id) DO UPDATE SET
                    unit_id = excluded.unit_id,
                    full_name = excluded.full_name,
                    position = excluded.position,
                    source_kind = excluded.source_kind,
                    status = excluded.status,
                    since = excluded.since,
                    personnel_no = excluded.personnel_no,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source = excluded.source,
                    notes = excluded.notes,
                    version = registry_imams.version + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    imam.imam_id,
                    imam.unit_id,
                    imam.full_name,
                    imam.position,
                    imam.source_kind,
                    imam.status,
                    imam.since.isoformat() if imam.since else None,
                    imam.personnel_no,
                    json.dumps(list(imam.evidence_refs), ensure_ascii=False),
                    imam.version,
                    imam.source.value,
                    imam.notes,
                    now,
                    now,
                ),
            )

    def list_imams(self, *, unit_id: str | None = None) -> list[ImamRecord]:
        with self._connect() as conn:
            if unit_id:
                rows = conn.execute("SELECT * FROM registry_imams WHERE unit_id = ? ORDER BY created_at", (unit_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM registry_imams ORDER BY created_at").fetchall()
            return [
                ImamRecord(
                    imam_id=row["imam_id"],
                    unit_id=row["unit_id"],
                    full_name=row["full_name"] or "",
                    position=row["position"] or "",
                    source_kind=row["source_kind"],
                    status=row["status"],
                    since=date.fromisoformat(row["since"]) if row["since"] else None,
                    personnel_no=row["personnel_no"] or "",
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                    version=row["version"],
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    def save_venue(self, venue: VenueRecord) -> None:
        venue.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_venues (
                    venue_id, unit_id, name, evidence_refs_json, version, source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(venue_id) DO UPDATE SET
                    unit_id = excluded.unit_id,
                    name = excluded.name,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source = excluded.source,
                    notes = excluded.notes,
                    version = registry_venues.version + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    venue.venue_id,
                    venue.unit_id,
                    venue.name,
                    json.dumps(list(venue.evidence_refs), ensure_ascii=False),
                    venue.version,
                    venue.source.value,
                    venue.notes,
                    now,
                    now,
                ),
            )

    def list_venues(self, *, unit_id: str | None = None) -> list[VenueRecord]:
        with self._connect() as conn:
            if unit_id:
                rows = conn.execute("SELECT * FROM registry_venues WHERE unit_id = ? ORDER BY created_at", (unit_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM registry_venues ORDER BY created_at").fetchall()
            return [
                VenueRecord(
                    venue_id=row["venue_id"],
                    unit_id=row["unit_id"],
                    name=row["name"] or "",
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                    version=row["version"],
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    def save_nomokalaf(self, record: NomokalafRecord) -> None:
        record.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_nomokalaf (
                    nom_id, unit_id, year, grain, person_count, full_name, gender, age,
                    taklif_year, parents, personnel_no, phone, linked_event_ids_json,
                    evidence_refs_json, version, source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(nom_id) DO UPDATE SET
                    unit_id = excluded.unit_id,
                    year = excluded.year,
                    grain = excluded.grain,
                    person_count = excluded.person_count,
                    full_name = excluded.full_name,
                    gender = excluded.gender,
                    age = excluded.age,
                    taklif_year = excluded.taklif_year,
                    parents = excluded.parents,
                    personnel_no = excluded.personnel_no,
                    phone = excluded.phone,
                    linked_event_ids_json = excluded.linked_event_ids_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source = excluded.source,
                    notes = excluded.notes,
                    version = registry_nomokalaf.version + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    record.nom_id,
                    record.unit_id,
                    record.year,
                    record.grain,
                    record.person_count,
                    record.full_name,
                    record.gender,
                    record.age,
                    record.taklif_year,
                    record.parents,
                    record.personnel_no,
                    record.phone,
                    json.dumps(list(record.linked_event_ids), ensure_ascii=False),
                    json.dumps(list(record.evidence_refs), ensure_ascii=False),
                    record.version,
                    record.source.value,
                    record.notes,
                    now,
                    now,
                ),
            )

    def list_nomokalaf(self, *, unit_id: str | None = None, year: str | None = None) -> list[NomokalafRecord]:
        query = "SELECT * FROM registry_nomokalaf"
        clauses: list[str] = []
        params: list[Any] = []
        if unit_id:
            clauses.append("unit_id = ?")
            params.append(unit_id)
        if year:
            clauses.append("year = ?")
            params.append(year)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                NomokalafRecord(
                    nom_id=row["nom_id"],
                    unit_id=row["unit_id"],
                    year=row["year"],
                    grain=row["grain"],
                    person_count=row["person_count"],
                    full_name=row["full_name"] or "",
                    gender=row["gender"] or "",
                    age=row["age"],
                    taklif_year=row["taklif_year"] or "",
                    parents=row["parents"] or "",
                    personnel_no=row["personnel_no"] or "",
                    phone=row["phone"] or "",
                    linked_event_ids=tuple(json.loads(row["linked_event_ids_json"])),
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                    version=row["version"],
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    # ----------------------------------------------------------------------
    # Entity Facts (registry-scoped, وضعیت‌سنجی)
    # ----------------------------------------------------------------------
    def save_entity_fact(self, fact: EntityFact, *, created_by: str = "") -> EntityFact:
        fact.validate(METRIC_DICTIONARY)
        now = _utc_now()
        if created_by:
            fact.created_by = created_by
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO entity_facts (
                    fact_id, entity_type, entity_id, metric, value, text_value,
                    value_kind, unit_of_measure, period, evidence_refs_json, source,
                    note, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    entity_id = excluded.entity_id,
                    metric = excluded.metric,
                    value = excluded.value,
                    text_value = excluded.text_value,
                    value_kind = excluded.value_kind,
                    unit_of_measure = excluded.unit_of_measure,
                    period = excluded.period,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source = excluded.source,
                    note = excluded.note,
                    created_by = excluded.created_by
                """,
                (
                    fact.fact_id,
                    fact.entity_type,
                    fact.entity_id,
                    fact.metric,
                    float(fact.value),
                    fact.text_value,
                    fact.value_kind,
                    fact.unit_of_measure,
                    fact.period,
                    json.dumps(list(fact.evidence_refs), ensure_ascii=False),
                    fact.source.value,
                    fact.note,
                    fact.created_at.isoformat() if hasattr(fact.created_at, "isoformat") else now,
                    fact.created_by,
                ),
            )
        return fact

    def list_entity_facts(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        period: str | None = None,
        metric: str | None = None,
    ) -> list[EntityFact]:
        query = "SELECT * FROM entity_facts"
        clauses: list[str] = []
        params: list[Any] = []
        if entity_type:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if period:
            clauses.append("period = ?")
            params.append(period)
        if metric:
            clauses.append("metric = ?")
            params.append(metric)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                EntityFact(
                    fact_id=row["fact_id"],
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    metric=row["metric"],
                    value=float(row["value"]),
                    text_value=row["text_value"] or "",
                    value_kind=row["value_kind"],
                    unit_of_measure=row["unit_of_measure"],
                    period=row["period"],
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    note=row["note"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                    created_by=row["created_by"] or "",
                )
                for row in rows
            ]

    # ----------------------------------------------------------------------
    # Normalization Candidates (free text → coded value, human approved)
    # ----------------------------------------------------------------------
    def save_normalization_candidate(
        self,
        *,
        batch_key: str,
        entity_type: str,
        unit_name: str,
        metric: str,
        raw_text: str,
        proposed_value: str,
        confidence: float,
        source_column: str = "",
        source_ref: str = "",
    ) -> str:
        now = _utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT candidate_id FROM normalization_candidates
                WHERE batch_key = ? AND metric = ? AND unit_name = ? AND review_status = 'pending'
                """,
                (batch_key, metric, unit_name),
            ).fetchone()
            if existing:
                return str(existing["candidate_id"])
            candidate_id = f"ncand-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO normalization_candidates (
                    candidate_id, batch_key, entity_type, unit_name, metric, raw_text,
                    proposed_value, confidence, source_column, source_ref, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    candidate_id,
                    batch_key,
                    entity_type,
                    unit_name,
                    metric,
                    raw_text,
                    proposed_value,
                    float(confidence),
                    source_column,
                    source_ref,
                    now,
                ),
            )
            return candidate_id

    def list_normalization_candidates(self, *, status: str | None = "pending", limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM normalization_candidates WHERE review_status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM normalization_candidates ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    def approve_normalization_candidate(
        self,
        candidate_id: str,
        *,
        coded_value: str,
        reviewed_by: str,
        fact_id: str = "",
        value_kind: str = "reported_by_unit",
    ) -> EntityFact:
        """Human coding of a free-text answer; writes the entity fact and closes
        the candidate. The approved value must be a valid choice of the metric."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM normalization_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if not row:
                raise ReportingStoreError(f"Normalization candidate not found: {candidate_id}")
            metric_key = row["metric"]
            definition = METRIC_DICTIONARY.get(metric_key)
            if definition.unit == "choice" and coded_value not in definition.choices:
                raise ReportingStoreError(f"{coded_value!r} is not a choice of {metric_key!r}.")
            entity_type = row["entity_type"] or "unit"
            entity_id = f"unit:{row['unit_name']}" if entity_type == "unit" and row["unit_name"] else row["source_ref"] or ""
            fact = EntityFact(
                fact_id=fact_id or f"entf-{uuid.uuid4().hex[:10]}",
                entity_type=entity_type,
                entity_id=entity_id,
                metric=metric_key,
                text_value=coded_value if definition.unit in {"choice", "text"} else "",
                value=float(coded_value) if definition.unit in {"count", "currency", "percent"} else 0.0,
                value_kind=value_kind,
                unit_of_measure=definition.unit,
                evidence_refs=(row["source_ref"],) if row["source_ref"] else (),
                source=ValueSource.MANUAL,
                note=f"normalized from: {row['raw_text']}",
            )
            now = _utc_now()
            conn.execute(
                """
                INSERT INTO entity_facts (
                    fact_id, entity_type, entity_id, metric, value, text_value,
                    value_kind, unit_of_measure, period, evidence_refs_json, source,
                    note, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact.fact_id,
                    fact.entity_type,
                    fact.entity_id,
                    fact.metric,
                    fact.value,
                    fact.text_value,
                    fact.value_kind,
                    fact.unit_of_measure,
                    "1405",
                    json.dumps(list(fact.evidence_refs), ensure_ascii=False),
                    fact.source.value,
                    fact.note,
                    now,
                    reviewed_by,
                ),
            )
            conn.execute(
                """
                UPDATE normalization_candidates
                SET review_status = 'approved', promoted_fact_id = ?, reviewed_by = ?, reviewed_at = ?
                WHERE candidate_id = ?
                """,
                (fact.fact_id, reviewed_by, now, candidate_id),
            )
        return fact

    def reject_normalization_candidate(self, candidate_id: str, *, reviewed_by: str, reason: str = "") -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE normalization_candidates
                SET review_status = 'rejected', reviewed_by = ?, reviewed_at = ?, rejection_reason = ?
                WHERE candidate_id = ?
                """,
                (reviewed_by, now, reason, candidate_id),
            )

    def approve_imam_candidate(self, candidate_id: str, imam: ImamRecord, *, reviewed_by: str) -> None:
        """Human confirmation of an imam extracted from an assessment row.

        The operator may edit the record before confirming; the candidate is
        closed only after the record is persisted.
        """
        imam.validate()
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT candidate_id FROM normalization_candidates WHERE candidate_id = ? AND metric = 'imam_record'",
                (candidate_id,),
            ).fetchone()
            if not row:
                raise ReportingStoreError(f"Imam candidate not found: {candidate_id}")
        self.save_imam(imam)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE normalization_candidates
                SET review_status = 'approved', reviewed_by = ?, reviewed_at = ?
                WHERE candidate_id = ?
                """,
                (reviewed_by, now, candidate_id),
            )

    # ----------------------------------------------------------------------
    # Program Plans & Mandates
    # ----------------------------------------------------------------------
    def save_plan_item(self, item: PlanItem) -> None:
        item.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO program_plans (
                    plan_id, period, section, strategy, title, plan_type, targets_json,
                    campaign_tag, mandate_ids_json, needs_confirmation, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id, period) DO UPDATE SET
                    section = excluded.section,
                    strategy = excluded.strategy,
                    title = excluded.title,
                    plan_type = excluded.plan_type,
                    targets_json = excluded.targets_json,
                    campaign_tag = excluded.campaign_tag,
                    mandate_ids_json = excluded.mandate_ids_json,
                    needs_confirmation = excluded.needs_confirmation,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    item.plan_id,
                    item.period,
                    item.section,
                    item.strategy,
                    item.title,
                    item.plan_type,
                    json.dumps(dict(item.targets), ensure_ascii=False),
                    item.campaign_tag,
                    json.dumps(list(item.mandate_ids), ensure_ascii=False),
                    1 if item.needs_confirmation else 0,
                    item.notes,
                    now,
                    now,
                ),
            )

    def list_plan_items(self, *, period: str = "1405", section: str = "prayer") -> list[PlanItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM program_plans WHERE period = ? AND section = ? ORDER BY created_at",
                (period, section),
            ).fetchall()
            return [
                PlanItem(
                    plan_id=row["plan_id"],
                    period=row["period"],
                    section=row["section"],
                    strategy=row["strategy"] or "",
                    title=row["title"] or "",
                    plan_type=row["plan_type"],
                    targets=json.loads(row["targets_json"]),
                    campaign_tag=row["campaign_tag"] or "",
                    mandate_ids=tuple(json.loads(row["mandate_ids_json"])),
                    needs_confirmation=bool(row["needs_confirmation"]),
                    notes=row["notes"] or "",
                )
                for row in rows
            ]

    def save_mandate(self, mandate: Mandate) -> None:
        mandate.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mandates (mandate_id, kind, title, number, issued_on, document_ref, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mandate_id) DO UPDATE SET
                    kind = excluded.kind, title = excluded.title, number = excluded.number,
                    issued_on = excluded.issued_on, document_ref = excluded.document_ref, notes = excluded.notes
                """,
                (
                    mandate.mandate_id,
                    mandate.kind,
                    mandate.title,
                    mandate.number,
                    mandate.issued_on,
                    mandate.document_ref,
                    mandate.notes,
                    now,
                ),
            )

    def list_mandates(self) -> list[Mandate]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM mandates ORDER BY created_at").fetchall()
            return [
                Mandate(
                    mandate_id=row["mandate_id"],
                    kind=row["kind"],
                    title=row["title"] or "",
                    number=row["number"] or "",
                    issued_on=row["issued_on"] or "",
                    document_ref=row["document_ref"] or "",
                    notes=row["notes"] or "",
                )
                for row in rows
            ]

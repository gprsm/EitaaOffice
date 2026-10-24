"""SQLite persistent storage for the 1405 reporting core and indexing queue.

Stores watch targets, index decisions, event candidates, human review records,
confirmed ReportedEvents with Facts, filled forms, and export audit trails.
Never contains raw message texts or sensitive credentials (ADR-47/governance).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
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
from .registry import EntityFact, ImamRecord, LiaisonRecord, NomokalafRecord, PersonRecord, UnitRecord, VenueRecord
from .sections import OFFICE_SECTIONS
from .wp_links import WpPostLink
from .jalali_dates import normalize_to_iso_date

REPORTING_SCHEMA_VERSION = 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_date_from_row(val: Any, fallback: date | None = None) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    val_str = str(val or "").strip()
    if not val_str:
        return fallback or date.today()
    try:
        iso_str = normalize_to_iso_date(val_str)
        return date.fromisoformat(iso_str)
    except Exception:
        return fallback or date.today()


def _safe_datetime_from_row(val: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(val, datetime):
        return val
    val_str = str(val or "").strip()
    if not val_str:
        return fallback or datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(val_str)
    except Exception:
        return fallback or datetime.now(timezone.utc)


def _safe_program_kind(k: Any) -> ProgramKind:
    try:
        return ProgramKind(k)
    except ValueError:
        code_map = {
            "80401": ProgramKind.TRIP,
            "80402": ProgramKind.CONTEST,
            "80403": ProgramKind.CEREMONY,
            "80501": ProgramKind.PRAYER,
            "80406": ProgramKind.HONOR,
            "80601": ProgramKind.CUSTOMER_CARE,
            "80202": ProgramKind.CHARTER,
        }
        return code_map.get(str(k), ProgramKind.CEREMONY)


def _safe_json_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, (tuple, set)):
        return list(val)
    val_str = str(val or "").strip()
    if not val_str:
        return []
    try:
        res = json.loads(val_str)
        return res if isinstance(res, list) else []
    except Exception:
        return []


class ReportingStoreError(Exception):
    """Base error for reporting storage operations."""


class EventNotFoundError(ReportingStoreError):
    """Raised when an event id does not exist."""


class EtagConflictError(ReportingStoreError):
    """Raised when an etag does not match the stored version."""

    def __init__(self, event_id: str, current_etag: str) -> None:
        super().__init__(f"etag conflict on event {event_id}; current etag {current_etag}")
        self.event_id = event_id
        self.current_etag = current_etag


class InvalidStatusTransitionError(ReportingStoreError):
    """Raised for illegal review-status transitions."""


class WitnessConflictError(ReportingStoreError):
    """Raised when a witness identity or link conflicts with stored rows."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


# Process-wide registry so several ReportingStore instances for the same
# database inside one process share a single ownership lease (multi-account
# installations construct multiple BridgeApplicationApi instances against one
# reporting DB). Cross-process single-writer exclusivity is still enforced by
# the lease file itself.
_SHARED_REPORTING_LEASES: dict[str, list[Any]] = {}
_SHARED_LEASES_LOCK = threading.Lock()

_DEFAULT_JUDICIAL_UNITS: list[tuple[str, str, str, str]] = [
    # 1. اداره کل
    ("ساری", "اداره کل", "ساری - اداره کل", "provincial_hq"),
    # 2. ساری (دادگستری، دادسرا، شورای حل اختلاف)
    ("ساری", "دادگستری", "ساری - دادگستری", "judicial_domain"),
    ("ساری", "دادسرا", "ساری - دادسرا", "judicial_domain"),
    ("ساری", "شورای حل اختلاف", "ساری - شورای حل اختلاف", "judicial_domain"),
    # 3. بابل (دادگستری، دادسرا)
    ("بابل", "دادگستری", "بابل - دادگستری", "judicial_domain"),
    ("بابل", "دادسرا", "بابل - دادسرا", "judicial_domain"),
    # 4. قائمشهر (دادگستری، دادسرا)
    ("قائمشهر", "دادگستری", "قائمشهر - دادگستری", "judicial_domain"),
    ("قائمشهر", "دادسرا", "قائمشهر - دادسرا", "judicial_domain"),
    # 5. الباقی ۳۰ حوزه قضایی (تک‌واحدی)
    ("آمل", "دادگستری", "آمل - دادگستری", "judicial_domain"),
    ("بابلسر", "دادگستری", "بابلسر - دادگستری", "judicial_domain"),
    ("بندپی شرقی", "دادگاه عمومی بخش", "بندپی شرقی - دادگاه عمومی بخش", "judicial_domain"),
    ("بهشهر", "دادگستری", "بهشهر - دادگستری", "judicial_domain"),
    ("تنکابن", "دادگستری", "تنکابن - دادگستری", "judicial_domain"),
    ("جویبار", "دادگستری", "جویبار - دادگستری", "judicial_domain"),
    ("چالوس", "دادگستری", "چالوس - دادگستری", "judicial_domain"),
    ("چمستان", "دادگاه عمومی بخش", "چمستان - دادگاه عمومی بخش", "judicial_domain"),
    ("چهاردانگه", "دادگاه عمومی بخش", "چهاردانگه - دادگاه عمومی بخش", "judicial_domain"),
    ("خرم آباد", "دادگاه عمومی بخش", "خرم آباد - دادگاه عمومی بخش", "judicial_domain"),
    ("دابودشت", "دادگاه عمومی بخش", "دابودشت - دادگاه عمومی بخش", "judicial_domain"),
    ("رامسر", "دادگستری", "رامسر - دادگستری", "judicial_domain"),
    ("سرخرود", "دادگاه عمومی بخش", "سرخرود - دادگاه عمومی بخش", "judicial_domain"),
    ("سوادکوه", "دادگستری", "سوادکوه - دادگستری", "judicial_domain"),
    ("سوادکوه شمالی", "دادگستری", "سوادکوه شمالی - دادگستری", "judicial_domain"),
    ("سیمرغ", "دادگستری", "سیمرغ - دادگستری", "judicial_domain"),
    ("عباس آباد", "دادگستری", "عباس آباد - دادگستری", "judicial_domain"),
    ("فریدونکنار", "دادگستری", "فریدونکنار - دادگستری", "judicial_domain"),
    ("کجور", "دادگاه عمومی بخش", "کجور - دادگاه عمومی بخش", "judicial_domain"),
    ("کلاردشت", "دادگستری", "کلاردشت - دادگستری", "judicial_domain"),
    ("گتاب", "دادگاه عمومی بخش", "گتاب - دادگاه عمومی بخش", "judicial_domain"),
    ("گلوگاه", "دادگستری", "گلوگاه - دادگستری", "judicial_domain"),
    ("لاریجان", "دادگاه عمومی بخش", "لاریجان - دادگاه عمومی بخش", "judicial_domain"),
    ("محمودآباد", "دادگستری", "محمودآباد - دادگستری", "judicial_domain"),
    ("مرزن آباد", "دادگاه عمومی بخش", "مرزن آباد - دادگاه عمومی بخش", "judicial_domain"),
    ("میاندورود", "دادگستری", "میاندورود - دادگستری", "judicial_domain"),
    ("نشتارود", "دادگاه عمومی بخش", "نشتارود - دادگاه عمومی بخش", "judicial_domain"),
    ("نکا", "دادگستری", "نکا - دادگستری", "judicial_domain"),
    ("نور", "دادگستری", "نور - دادگستری", "judicial_domain"),
    ("نوشهر", "دادگستری", "نوشهر - دادگستری", "judicial_domain"),
]

# 8 Official program titles + 1 non-programmatic title (کاربر: عیناً ۸ عنوان سرفصل + غیر برنامه‌ای)
MACRO_INDICATORS: tuple[str, ...] = (
    "برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی",
    "ترویج و توسعه فرهنگ اقامه نماز",
    "تکریم و تجلیل از همکاران و خانواده",
    "برگزاری مسابقات استانی فرهنگی، قرآنی و ورزشی",
    "برگزاری اردوهای فرهنگی زیارتی برای کارکنان و خانواده",
    "تشویق کارمندان و تکریم ارباب رجوع",
    "اجرای منشور اخلاقی و رفتار حرفه‌ای",
    "دوره‌های آموزشی، توانمندسازی و تولیدات فرهنگی",
    "غیر برنامه‌ای",
)

# Initial seeded micro indicators
_DEFAULT_MICRO_INDICATORS: list[tuple[str, str, str]] = [
    ("زیارت عاشورا", "مراسم", "#0284c7"),
    ("ایستگاه صلواتی و موکب", "مراسم", "#0d9488"),
    ("مسابقات قرآنی و حفظ", "مسابقات", "#16a34a"),
    ("مسابقات ورزشی و فوتسال", "مسابقات", "#ca8a04"),
    ("پویش فرزندآوری و ازدواج", "خانواده", "#ea580c"),
    ("محفل انس با قرآن", "نماز و قرآن", "#15803d"),
    ("تکریم بازنشستگان و پیشکسوتان", "تکریم", "#7c3aed"),
    ("میز خدمت جهادی و پاسخگویی", "ارباب رجوع", "#2563eb"),
    ("کارگاه خانواده مهدوی و اخلاق", "آموزش", "#c026d3"),
    ("تولید کلیپ، موشن‌گرافی و پوستر", "رسانه", "#db2777"),
]

# Canonical operational programs catalog with multi-year lifecycle and soft-deprecation support
_CANONICAL_PROGRAM_CATALOG: list[dict[str, Any]] = [
    {
        "program_code": "80403",
        "title": "برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی",
        "canonical_macro": "برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی",
        "kind": "ceremony",
        "workbook_sheet": "مراسم  مذهبی",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 1,
        "description": "برگزاری مراسم در مناسبت‌های مذهبی، ملی و انقلابی و بزرگداشت‌ها",
    },
    {
        "program_code": "80501",
        "title": "ترویج و توسعه فرهنگ اقامه نماز",
        "canonical_macro": "ترویج و توسعه فرهنگ اقامه نماز",
        "kind": "prayer",
        "workbook_sheet": "ترویج و توسعه فرهنگ اقامه نماز",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 2,
        "description": "اقامه نماز جماعت، تجهیز نمازخانه‌ها و مسابقات احکام و خادمیاری نماز",
    },
    {
        "program_code": "80406",
        "title": "تکریم و تجلیل از همکاران و خانواده",
        "canonical_macro": "تکریم و تجلیل از همکاران و خانواده",
        "kind": "honor",
        "workbook_sheet": "تکریم و تجلیل",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 3,
        "description": "تجلیل از همکاران ساعی، بازنشستگان، جانبازان و خانواده‌ها",
    },
    {
        "program_code": "80402",
        "title": "برگزاری مسابقات استانی فرهنگی، قرآنی و ورزشی",
        "canonical_macro": "برگزاری مسابقات استانی فرهنگی، قرآنی و ورزشی",
        "kind": "contest",
        "workbook_sheet": "مسابقات",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 4,
        "description": "مسابقات قرآن، کتابخوانی و مسابقات ورزشی کارکنان و فرزندان",
    },
    {
        "program_code": "80401",
        "title": "برگزاری اردوهای فرهنگی زیارتی برای کارکنان و خانواده",
        "canonical_macro": "برگزاری اردوهای فرهنگی زیارتی برای کارکنان و خانواده",
        "kind": "trip",
        "workbook_sheet": "اردو",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 5,
        "description": "اردوهای زیارتی مشهد، قم و بازدیدهای فرهنگی خانواده و پرسنل",
    },
    {
        "program_code": "80601",
        "title": "تشویق کارمندان و تکریم ارباب رجوع",
        "canonical_macro": "تشویق کارمندان و تکریم ارباب رجوع",
        "kind": "customer_care",
        "workbook_sheet": "تشویق ارباب رجوع",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 6,
        "description": "طرح‌های تکریم مراجعان، میز خدمت و تشویق کارکنان با بیشترین رضایت ارباب رجوع",
    },
    {
        "program_code": "80202",
        "title": "اجرای منشور اخلاقی و رفتار حرفه‌ای",
        "canonical_macro": "اجرای منشور اخلاقی و رفتار حرفه‌ای",
        "kind": "charter",
        "workbook_sheet": "منشور",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 7,
        "description": "نظارت بر اجرای منشور اخلاق و رفتار سازمانی و ارتقای سلامت اداری",
    },
    {
        "program_code": "80301",
        "title": "دوره‌های آموزشی، توانمندسازی و تولیدات فرهنگی",
        "canonical_macro": "دوره‌های آموزشی، توانمندسازی و تولیدات فرهنگی",
        "kind": "training",
        "workbook_sheet": "آموزش",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 8,
        "description": "کارگاه‌های مهارتی، اخلاقی، فرزندآوری و تولیدات رسانه‌ای و مکتوب",
    },
    {
        "program_code": "00000",
        "title": "غیر برنامه‌ای",
        "canonical_macro": "غیر برنامه‌ای",
        "kind": "non_programmatic",
        "workbook_sheet": "",
        "valid_from_year": 1403,
        "valid_to_year": None,
        "is_active": 1,
        "display_order": 9,
        "description": "فعالیت‌های فرهنگی آزاد خارج از شیت‌های هشت‌گانه مصوب",
    },
]


class ReportingStore:
    """Thread-safe SQLite store for reporting entities and candidate workflows."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        acquire_lease: bool = False,
        runtime_dir: Path | None = None,
        owner_label: str = "",
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self._local = threading.local()
        self._lease: Any = None
        self._lease_key: str = ""
        if acquire_lease:
            from .ownership import StoreOwnershipLease
            key = str(self.db_path)
            with _SHARED_LEASES_LOCK:
                entry = _SHARED_REPORTING_LEASES.get(key)
                if entry is None:
                    lease = StoreOwnershipLease(
                        self.db_path,
                        runtime_dir=runtime_dir,
                        owner_label=owner_label or "ReportingStore",
                    )
                    lease.acquire()
                    lease.start_heartbeat()
                    entry = [lease, 0]
                    _SHARED_REPORTING_LEASES[key] = entry
                entry[1] += 1
                self._lease = entry[0]
                self._lease_key = key
        self.initialize()

    def close(self) -> None:
        """Release the process-shared ownership lease (refcounted)."""
        if getattr(self, "_lease", None) is None:
            return
        with _SHARED_LEASES_LOCK:
            entry = _SHARED_REPORTING_LEASES.get(self._lease_key)
            if entry is not None and entry[0] is self._lease:
                entry[1] -= 1
                if entry[1] <= 0:
                    try:
                        entry[0].release()
                    except Exception:
                        pass
                    _SHARED_REPORTING_LEASES.pop(self._lease_key, None)
        self._lease = None

    @property
    def ownership_lease(self) -> Any:
        return getattr(self, "_lease", None)

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
                    macro_category TEXT NOT NULL DEFAULT 'workbook_approved',
                    custom_topic TEXT NOT NULL DEFAULT '',
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
                    county TEXT NOT NULL DEFAULT '',
                    unit_type TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'judicial_domain',
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS reporting_liaisons (
                    liaison_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL REFERENCES reporting_units(unit_id) ON DELETE CASCADE,
                    full_name TEXT NOT NULL,
                    eitaa_username TEXT NOT NULL DEFAULT '',
                    eitaa_user_id TEXT NOT NULL DEFAULT '',
                    sender_key TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    match_keywords TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_liaisons_unit ON reporting_liaisons(unit_id);
                CREATE INDEX IF NOT EXISTS idx_liaisons_username ON reporting_liaisons(eitaa_username);
                CREATE INDEX IF NOT EXISTS idx_liaisons_sender_key ON reporting_liaisons(sender_key);
                CREATE INDEX IF NOT EXISTS idx_liaisons_name ON reporting_liaisons(full_name);

                CREATE TABLE IF NOT EXISTS reporting_micro_indicators (
                    indicator_id TEXT PRIMARY KEY,
                    title TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '',
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_micro_indicators_title ON reporting_micro_indicators(title);

                CREATE TABLE IF NOT EXISTS reporting_message_indicators (
                    peer_key TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    macro_indicator TEXT NOT NULL DEFAULT '',
                    micro_indicators_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT 'user',
                    PRIMARY KEY (peer_key, message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_msg_indicators_peer ON reporting_message_indicators(peer_key);

                CREATE TABLE IF NOT EXISTS reporting_message_splits (
                    peer_key TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    is_detached INTEGER NOT NULL DEFAULT 1,
                    group_key TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (peer_key, message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_msg_splits_peer ON reporting_message_splits(peer_key);

                -- Unified Operational Programs Catalog (multi-year lifecycle & soft-deprecation)
                CREATE TABLE IF NOT EXISTS reporting_program_catalog (
                    program_code TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    canonical_macro TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    workbook_sheet TEXT NOT NULL DEFAULT '',
                    valid_from_year INTEGER NOT NULL DEFAULT 1403,
                    valid_to_year INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_program_catalog_active
                    ON reporting_program_catalog(is_active, valid_from_year);

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
                -- projections aggregate to counts only (F-088 privacy rule).

                CREATE TABLE IF NOT EXISTS entity_facts (
                    fact_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'venue', 'imam', 'nomokalaf', 'section')),
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
                    action_class TEXT NOT NULL DEFAULT '',
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
                    program_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                -- Questionnaire projection (F-094/F-095): the operational
                -- description, monitoring criteria and per-sheet question
                -- structure of each official form are projected here so
                -- read-only consumers (the cultural portal) render policy
                -- changes from the same SQLite without code access.
                CREATE TABLE IF NOT EXISTS form_definitions (
                    program_code TEXT PRIMARY KEY,
                    program_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    operational_description TEXT NOT NULL DEFAULT '',
                    monitoring_criteria_json TEXT NOT NULL DEFAULT '[]',
                    policy_framework TEXT NOT NULL DEFAULT '',
                    questions_json TEXT NOT NULL DEFAULT '[]',
                    version TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                -- Section registry (F-088 §4): sections are data rows, not
                -- code enums; adding a report topic means adding a row.
                CREATE TABLE IF NOT EXISTS reporting_sections (
                    section_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    workbook_code TEXT NOT NULL DEFAULT '',
                    workbook_sheet TEXT NOT NULL DEFAULT '',
                    visit_label TEXT NOT NULL DEFAULT '',
                    kinds_json TEXT NOT NULL DEFAULT '[]',
                    notes TEXT,
                    created_at TEXT NOT NULL
                );

                -- Comprehensive person base: employees and their family
                -- members. PII columns below (national_id/phone) stay local;
                -- projections aggregate to counts only.
                CREATE TABLE IF NOT EXISTS registry_persons (
                    person_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL DEFAULT 'employee' CHECK(kind IN ('employee', 'family')),
                    full_name TEXT NOT NULL DEFAULT '',
                    personnel_no TEXT NOT NULL DEFAULT '',
                    national_id TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    relation TEXT NOT NULL DEFAULT '',
                    related_personnel_no TEXT NOT NULL DEFAULT '',
                    unit_id TEXT NOT NULL DEFAULT '',
                    gender TEXT NOT NULL DEFAULT '',
                    birth_year TEXT NOT NULL DEFAULT '',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_persons_personnel ON registry_persons(personnel_no);
                CREATE INDEX IF NOT EXISTS idx_persons_related ON registry_persons(related_personnel_no);

                -- WordPress post ↔ event links (F-088 §2): the missing
                -- connection between published news and the event corpus.
                CREATE TABLE IF NOT EXISTS wp_post_links (
                    link_id TEXT PRIMARY KEY,
                    post_slug TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL DEFAULT '',
                    section TEXT NOT NULL DEFAULT '',
                    published_on TEXT,
                    event_id TEXT NOT NULL DEFAULT '',
                    match_status TEXT NOT NULL DEFAULT 'unmatched'
                        CHECK(match_status IN ('unmatched', 'auto', 'candidate', 'confirmed')),
                    confidence REAL NOT NULL DEFAULT 0.0,
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_wp_links_status ON wp_post_links(match_status);
                CREATE INDEX IF NOT EXISTS idx_wp_links_section ON wp_post_links(section);
                """
            )

            # Migration v1→v2: the campaign (طرح) dimension on events.
            event_columns = {row[1] for row in conn.execute("PRAGMA table_info(reported_events)")}
            if "campaign" not in event_columns:
                conn.execute("ALTER TABLE reported_events ADD COLUMN campaign TEXT NOT NULL DEFAULT ''")

            # Migration v2→v3: the section entity kind (program-period facts)
            # and the plan action_class (قالب گزارش عملکرد classification).
            entity_facts_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='entity_facts'"
            ).fetchone()
            if entity_facts_sql and entity_facts_sql[0] and "'section'" not in entity_facts_sql[0]:
                conn.executescript(
                    """
                    CREATE TABLE entity_facts_v3 (
                        fact_id TEXT PRIMARY KEY,
                        entity_type TEXT NOT NULL CHECK(entity_type IN ('unit', 'venue', 'imam', 'nomokalaf', 'section')),
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
                    INSERT INTO entity_facts_v3
                        SELECT fact_id, entity_type, entity_id, metric, value, text_value,
                               value_kind, unit_of_measure, period, evidence_refs_json, source,
                               note, created_at, created_by
                        FROM entity_facts;
                    DROP TABLE entity_facts;
                    ALTER TABLE entity_facts_v3 RENAME TO entity_facts;
                    CREATE INDEX IF NOT EXISTS idx_entity_facts_entity ON entity_facts(entity_type, entity_id, period);
                    CREATE INDEX IF NOT EXISTS idx_entity_facts_metric ON entity_facts(metric, period);
                    """
                )
            plan_columns = {row[1] for row in conn.execute("PRAGMA table_info(program_plans)")}
            if plan_columns and "action_class" not in plan_columns:
                conn.execute("ALTER TABLE program_plans ADD COLUMN action_class TEXT NOT NULL DEFAULT ''")

            # Migration: ensure program_code exists on mandates
            mandate_columns = {row[1] for row in conn.execute("PRAGMA table_info(mandates)")}
            if mandate_columns and "program_code" not in mandate_columns:
                conn.execute("ALTER TABLE mandates ADD COLUMN program_code TEXT NOT NULL DEFAULT ''")

            # Migration v4→v5: witness/evidence layer, typed facts, review
            # lifecycle (phase 1 of the unified reporting strategy; design doc
            # docs/specifications/REPORTING_DOMAIN_MODEL_MIGRATION_2026-10-03.md).
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reporting_message_witnesses (
                    witness_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL DEFAULT 'eitaa',
                    messenger_account TEXT NOT NULL DEFAULT '',
                    peer_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    observed_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_witness_identity
                    ON reporting_message_witnesses(provider, COALESCE(messenger_account, ''), peer_id, message_id);
                CREATE INDEX IF NOT EXISTS idx_witness_peer_msg
                    ON reporting_message_witnesses(peer_id, message_id);

                CREATE TABLE IF NOT EXISTS reporting_event_witness_links (
                    link_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    witness_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('primary', 'supporting')),
                    linked_by TEXT,
                    linked_at TEXT NOT NULL,
                    note TEXT,
                    detached_at TEXT,
                    detached_reason TEXT,
                    FOREIGN KEY (event_id) REFERENCES reported_events(event_id) ON DELETE CASCADE,
                    FOREIGN KEY (witness_id) REFERENCES reporting_message_witnesses(witness_id) ON DELETE RESTRICT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_witness_active_primary
                    ON reporting_event_witness_links(witness_id) WHERE role = 'primary' AND detached_at IS NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS uq_event_witness
                    ON reporting_event_witness_links(event_id, witness_id) WHERE detached_at IS NULL;
                CREATE INDEX IF NOT EXISTS idx_links_event_id ON reporting_event_witness_links(event_id);
                CREATE INDEX IF NOT EXISTS idx_links_witness_id ON reporting_event_witness_links(witness_id);

                CREATE TABLE IF NOT EXISTS reporting_review_queue (
                    queue_id TEXT PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    ref_table TEXT NOT NULL,
                    ref_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'resolved', 'dismissed')),
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_review_queue_lookup
                    ON reporting_review_queue(ref_table, ref_id, status);
                CREATE INDEX IF NOT EXISTS idx_review_queue_status
                    ON reporting_review_queue(status, item_type);

                CREATE TABLE IF NOT EXISTS event_documents (
                    document_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_cover INTEGER NOT NULL DEFAULT 0,
                    added_by TEXT,
                    added_at TEXT NOT NULL,
                    storage_ref TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (event_id) REFERENCES reported_events(event_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_documents_event ON event_documents(event_id, display_order);
                CREATE INDEX IF NOT EXISTS idx_documents_media_sha ON event_documents(media_id, sha256);
                """
            )

            # Typed-fact columns: value_kind already carries the quality axis
            # (FactValueKind); v5 adds the data-type axis and exact decimals.
            for _typed_table in ("event_facts", "entity_facts"):
                _typed_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({_typed_table})")}
                if _typed_cols and "value_type" not in _typed_cols:
                    conn.execute(
                        f"ALTER TABLE {_typed_table} ADD COLUMN value_type TEXT NOT NULL DEFAULT 'unknown' "
                        "CHECK(value_type IN ('integer', 'decimal', 'text', 'bool', 'unknown'))"
                    )
                if _typed_cols and "value_decimal" not in _typed_cols:
                    conn.execute(f"ALTER TABLE {_typed_table} ADD COLUMN value_decimal TEXT")

            # Event review lifecycle: new column; legacy rows land on
            # needs_review (conservative, no guessing) — design doc §1.3.
            _event_cols = {row[1] for row in conn.execute("PRAGMA table_info(reported_events)")}
            if _event_cols and "review_status" not in _event_cols:
                conn.execute(
                    "ALTER TABLE reported_events ADD COLUMN review_status TEXT NOT NULL DEFAULT 'needs_review' "
                    "CHECK(review_status IN ('draft', 'needs_review', 'approved', 'conflict'))"
                )

            # Legacy reconciliation: one review-queue item per unreviewed
            # historical event; deterministic id keeps re-init idempotent.
            _v5_now = _utc_now()
            for _legacy_row in conn.execute(
                "SELECT event_id FROM reported_events WHERE review_status = 'needs_review'"
            ).fetchall():
                _legacy_event_id = _legacy_row["event_id"]
                _unknown_facts = conn.execute(
                    "SELECT COUNT(*) FROM event_facts WHERE event_id = ?",
                    (_legacy_event_id,),
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO reporting_review_queue (
                        queue_id, item_type, ref_table, ref_id, reason, status, created_at
                    ) VALUES (?, 'legacy_event_review', 'reported_events', ?, ?, 'open', ?)
                    """,
                    (
                        f"rq-legacy-{_legacy_event_id}",
                        _legacy_event_id,
                        (
                            "رویداد تاریخی بدون شاهد پیام ثبتشده؛ وضعیت تأیید نیازمند تأیید انسانی؛ "
                            f"{_unknown_facts} فکت با value_type=unknown"
                        ),
                        _v5_now,
                    ),
                )

            # Migration v5→v6: roles, audit trail and event versioning
            # (phase 2 of the unified reporting strategy; design doc
            # docs/specifications/REPORTING_TRANSACTIONAL_CORE_2026-10-03.md).
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reporting_user_roles (
                    user_id TEXT PRIMARY KEY,
                    roles_json TEXT NOT NULL DEFAULT '[]',
                    updated_by TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reporting_audit_log (
                    audit_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    diff_json TEXT NOT NULL DEFAULT '{}',
                    etag_before TEXT,
                    etag_after TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_entity
                    ON reporting_audit_log(entity_type, entity_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_audit_actor
                    ON reporting_audit_log(actor, created_at);
                """
            )

            # Event version column for etag concurrency (design doc §3).
            _v6_event_cols = {row[1] for row in conn.execute("PRAGMA table_info(reported_events)")}
            if _v6_event_cols and "version" not in _v6_event_cols:
                conn.execute(
                    "ALTER TABLE reported_events ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
                )

            # Migration v6→v7: versioned official exports (phase 4 of the
            # unified reporting strategy; design doc
            # docs/specifications/REPORTING_OFFICIAL_OUTPUT_2026-10-03.md).
            _v7_export_cols = {row[1] for row in conn.execute("PRAGMA table_info(report_exports)")}
            if _v7_export_cols:
                if "template_version" not in _v7_export_cols:
                    conn.execute("ALTER TABLE report_exports ADD COLUMN template_version TEXT NOT NULL DEFAULT '1'")
                if "rules_version" not in _v7_export_cols:
                    conn.execute("ALTER TABLE report_exports ADD COLUMN rules_version TEXT NOT NULL DEFAULT '1'")
                if "traceability_json" not in _v7_export_cols:
                    conn.execute("ALTER TABLE report_exports ADD COLUMN traceability_json TEXT")
                if "wp_opt_in" not in _v7_export_cols:
                    conn.execute("ALTER TABLE report_exports ADD COLUMN wp_opt_in INTEGER NOT NULL DEFAULT 0")

            # Migration v7→v8: Assistant scoped feedback and aliases
            # (phase 5 of the unified reporting strategy; design doc
            # docs/specifications/REPORTING_ASSISTANT_PHASE5_2026-10-03.md).
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assistant_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    scope_kind TEXT NOT NULL CHECK(scope_kind IN ('local', 'program', 'unit', 'global')),
                    scope_target TEXT NOT NULL DEFAULT '',
                    suggested_program TEXT NOT NULL DEFAULT '',
                    suggested_unit TEXT NOT NULL DEFAULT '',
                    chosen_program TEXT NOT NULL DEFAULT '',
                    chosen_unit TEXT NOT NULL DEFAULT '',
                    rule_version TEXT NOT NULL DEFAULT '1.0',
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('accept', 'correct', 'reject', 'abstain')),
                    revoked_at TEXT,
                    revoked_by TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_candidate ON assistant_feedback(candidate_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_scope ON assistant_feedback(scope_kind, scope_target);

                CREATE TABLE IF NOT EXISTS assistant_scoped_aliases (
                    alias_id TEXT PRIMARY KEY,
                    alias_text TEXT NOT NULL,
                    canonical_target TEXT NOT NULL,
                    target_type TEXT NOT NULL CHECK(target_type IN ('program', 'unit', 'occasion')),
                    scope_kind TEXT NOT NULL CHECK(scope_kind IN ('local', 'program', 'unit', 'global')),
                    scope_target TEXT NOT NULL DEFAULT '',
                    weight REAL NOT NULL DEFAULT 1.0,
                    approved_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'revoked'))
                );
                CREATE INDEX IF NOT EXISTS idx_alias_lookup ON assistant_scoped_aliases(alias_text, scope_kind, status);
                """
            )

            # Migration v8→v9: Staff attribution, defect auditing & workflow tracking
            _v9_event_cols = {row[1] for row in conn.execute("PRAGMA table_info(reported_events)")}
            if _v9_event_cols:
                if "registered_by_id" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN registered_by_id TEXT NOT NULL DEFAULT ''")
                if "registered_by_name" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN registered_by_name TEXT NOT NULL DEFAULT ''")
                if "reviewed_by_id" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN reviewed_by_id TEXT NOT NULL DEFAULT ''")
                if "reviewed_by_name" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN reviewed_by_name TEXT NOT NULL DEFAULT ''")
                if "reviewed_at" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN reviewed_at TEXT")
                if "review_notes" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN review_notes TEXT NOT NULL DEFAULT ''")
                if "revision_count" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN revision_count INTEGER NOT NULL DEFAULT 0")
                if "defects_json" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN defects_json TEXT NOT NULL DEFAULT '[]'")
                if "macro_category" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN macro_category TEXT NOT NULL DEFAULT 'workbook_approved'")
                if "custom_topic" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN custom_topic TEXT NOT NULL DEFAULT ''")
                if "macro_indicator" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN macro_indicator TEXT NOT NULL DEFAULT ''")
                if "micro_indicators_json" not in _v9_event_cols:
                    conn.execute("ALTER TABLE reported_events ADD COLUMN micro_indicators_json TEXT NOT NULL DEFAULT '[]'")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reported_events_staff ON reported_events(registered_by_id, review_status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reported_events_reviewed ON reported_events(reviewed_by_id, reviewed_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reported_events_macro ON reported_events(macro_category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reported_events_macro_ind ON reported_events(macro_indicator)")

            # Seed initial micro indicators if empty
            existing_micro_count = conn.execute("SELECT COUNT(*) FROM reporting_micro_indicators").fetchone()[0]
            if existing_micro_count == 0:
                now_ind = _utc_now()
                for ind_title, ind_cat, ind_clr in _DEFAULT_MICRO_INDICATORS:
                    new_ind_id = f"ind-micro-{uuid.uuid4().hex[:10]}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO reporting_micro_indicators (
                            indicator_id, title, category, color, usage_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?)
                        """,
                        (new_ind_id, ind_title, ind_cat, ind_clr, now_ind, now_ind),
                    )

            # Self-healing seed for reporting_program_catalog
            now_prog = _utc_now()
            for prog in _CANONICAL_PROGRAM_CATALOG:
                conn.execute(
                    """
                    INSERT INTO reporting_program_catalog (
                        program_code, title, canonical_macro, kind, workbook_sheet,
                        valid_from_year, valid_to_year, is_active, display_order,
                        description, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(program_code) DO UPDATE SET
                        canonical_macro = excluded.canonical_macro,
                        kind = excluded.kind,
                        workbook_sheet = excluded.workbook_sheet,
                        display_order = excluded.display_order,
                        updated_at = excluded.updated_at
                    """,
                    (
                        prog["program_code"],
                        prog["title"],
                        prog["canonical_macro"],
                        prog["kind"],
                        prog["workbook_sheet"],
                        prog["valid_from_year"],
                        prog["valid_to_year"],
                        prog["is_active"],
                        prog["display_order"],
                        prog["description"],
                        now_prog,
                        now_prog,
                    ),
                )

            # Self-healing seed (F-096): canonical mandates upsert on every
            # init so corrected titles/numbers/codes from the official
            # visit-worksheet source reach the operational DB. Operator- and
            # portal-created mandates carry random ids and are never touched.
            from .plans import CANONICAL_MANDATES
            now_mnd = _utc_now()
            for mandate in CANONICAL_MANDATES:
                mandate.validate()
                conn.execute(
                    """
                    INSERT INTO mandates (
                        mandate_id, kind, title, number, issued_on, document_ref, notes, program_code, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mandate_id) DO UPDATE SET
                        kind = excluded.kind,
                        title = excluded.title,
                        number = excluded.number,
                        issued_on = excluded.issued_on,
                        document_ref = excluded.document_ref,
                        notes = excluded.notes,
                        program_code = excluded.program_code
                    """,
                    (
                        mandate.mandate_id,
                        mandate.kind,
                        mandate.title,
                        mandate.number,
                        mandate.issued_on,
                        mandate.document_ref,
                        mandate.notes,
                        mandate.program_code,
                        now_mnd,
                    ),
                )

            # Upsert questionnaire definitions on every init: policy text
            # edited in forms.py must reach the portal on next store open
            # (idempotent, no operator data involved).
            from .forms import EXTENDED_FORMS
            now_forms = _utc_now()
            for form_def in EXTENDED_FORMS:
                if not form_def.program_code:
                    continue
                questions_payload = [
                    {
                        "key": question.key,
                        "label": question.label,
                        "qtype": question.qtype,
                        "star": question.star,
                        "choices": list(question.choices),
                        "auto_from": question.auto_from,
                        "human_gate": question.human_gate,
                    }
                    for question in form_def.questions
                ]
                conn.execute(
                    """
                    INSERT INTO form_definitions (
                        program_code, program_id, title, operational_description,
                        monitoring_criteria_json, policy_framework, questions_json,
                        version, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(program_code) DO UPDATE SET
                        program_id = excluded.program_id,
                        title = excluded.title,
                        operational_description = excluded.operational_description,
                        monitoring_criteria_json = excluded.monitoring_criteria_json,
                        policy_framework = excluded.policy_framework,
                        questions_json = excluded.questions_json,
                        version = excluded.version,
                        updated_at = excluded.updated_at
                    """,
                    (
                        form_def.program_code,
                        getattr(form_def.program_id, "value", str(form_def.program_id)),
                        form_def.title,
                        form_def.operational_description,
                        json.dumps(list(form_def.monitoring_criteria), ensure_ascii=False),
                        form_def.policy_framework,
                        json.dumps(questions_payload, ensure_ascii=False),
                        form_def.version,
                        now_forms,
                    ),
                )

            # Seed schema version if not recorded
            cur = conn.execute("SELECT version FROM reporting_schema WHERE version = ?", (REPORTING_SCHEMA_VERSION,))
            if not cur.fetchone():
                conn.execute(
                    "INSERT INTO reporting_schema (version, applied_at) VALUES (?, ?)",
                    (REPORTING_SCHEMA_VERSION, _utc_now()),
                )

            # Seed the section registry from the canonical definitions (only
            # when empty — operator-added sections are never overwritten).
            count_sections = conn.execute("SELECT COUNT(*) FROM reporting_sections").fetchone()[0]
            if count_sections == 0:
                now = _utc_now()
                for section in OFFICE_SECTIONS:
                    section.validate()
                    conn.execute(
                        """
                        INSERT INTO reporting_sections (
                            section_id, title, source, workbook_code, workbook_sheet,
                            visit_label, kinds_json, notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            section.section_id,
                            section.title,
                            section.source,
                            section.workbook_code,
                            section.workbook_sheet,
                            section.visit_label,
                            json.dumps(list(section.kinds), ensure_ascii=False),
                            section.notes,
                            now,
                        ),
                    )
            else:
                for section in OFFICE_SECTIONS:
                    conn.execute(
                        "UPDATE reporting_sections SET kinds_json = ?, visit_label = ? WHERE section_id = ?",
                        (json.dumps(list(section.kinds), ensure_ascii=False), section.visit_label, section.section_id),
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

            # Migrate and seed judicial units and liaisons
            self._migrate_and_seed_judicial_units_and_liaisons(conn)

            # Ensure storage_ref exists on event_documents
            _doc_cols = {row[1] for row in conn.execute("PRAGMA table_info(event_documents)")}
            if _doc_cols and "storage_ref" not in _doc_cols:
                conn.execute("ALTER TABLE event_documents ADD COLUMN storage_ref TEXT NOT NULL DEFAULT ''")

            # Ensure reporting_unit_baselines table exists
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reporting_unit_baselines (
                    unit_id TEXT PRIMARY KEY,
                    staff_count INTEGER NOT NULL DEFAULT 0,
                    family_multiplier REAL NOT NULL DEFAULT 2.5,
                    imams_count INTEGER NOT NULL DEFAULT 0,
                    prayer_rooms_count INTEGER NOT NULL DEFAULT 0,
                    honored_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                """
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
    _TRANSIENT_LOCK_ATTEMPTS = 3
    _EDITABLE_EVENT_FIELDS = frozenset({
        "unit_name", "occasion", "occasion_class", "notes", "campaign",
        "duration_minutes", "official_present", "prior_announcement",
        "had_reception", "is_ashura_pilgrimage", "contains_inner_contest",
        "macro_category", "custom_topic", "macro_indicator", "micro_indicators_json",
        "occurred_on", "unit", "program_kinds_json", "micro_indicators", "program_kinds", "facts", "is_standalone_titled",
    })

    def _run_in_transaction(self, operation):
        """Run operation(conn) inside BEGIN IMMEDIATE with bounded lock retry."""
        last_exc: sqlite3.OperationalError | None = None
        for attempt in range(self._TRANSIENT_LOCK_ATTEMPTS):
            try:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    return operation(conn)
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < self._TRANSIENT_LOCK_ATTEMPTS - 1:
                    last_exc = exc
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise
        raise last_exc

    @staticmethod
    def _compute_etag(event_id: str, version: int) -> str:
        """Etag = short hash of event id plus monotonic version."""
        return hashlib.sha256(f"{event_id}:{version}".encode()).hexdigest()[:16]

    def _append_audit(self, conn, *, actor: str, action: str, entity_type: str,
                      entity_id: str, diff: dict, etag_before: str | None = None,
                      etag_after: str | None = None) -> None:
        conn.execute(
            """
            INSERT INTO reporting_audit_log (
                audit_id, actor, action, entity_type, entity_id, diff_json,
                etag_before, etag_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"audit-{uuid.uuid4().hex[:12]}", actor, action, entity_type, entity_id,
                json.dumps(diff, ensure_ascii=False), etag_before, etag_after, _utc_now(),
            ),
        )

    def get_event_etag(self, event_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT version FROM reported_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        if row is None:
            return None
        return self._compute_etag(event_id, int(row["version"]))

    def create_event_draft(self, event: ReportedEvent, *, actor: str) -> tuple[str, str]:
        self.save_event(event)

        def _op(conn):
            row = conn.execute(
                "SELECT version FROM reported_events WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()
            if row is None:
                raise EventNotFoundError(f"event {event.event_id} not found")
            etag = self._compute_etag(event.event_id, int(row["version"]))
            self._append_audit(
                conn, actor=actor, action="event.create_draft",
                entity_type="reported_events", entity_id=event.event_id,
                diff={"event_id": event.event_id}, etag_after=etag,
            )
            return (event.event_id, etag)

        return self._run_in_transaction(_op)

    def update_event_fields(self, event_id: str, *, actor: str, expected_etag: str,
                            fields: dict) -> str:
        fields = dict(fields)
        facts_to_update = fields.pop("facts", None)
        if "micro_indicators" in fields:
            micros = fields.pop("micro_indicators")
            if "micro_indicators_json" not in fields:
                fields["micro_indicators_json"] = json.dumps(micros, ensure_ascii=False)
            if any("عاشورا" in str(m) for m in (micros or [])) and "is_ashura_pilgrimage" not in fields:
                fields["is_ashura_pilgrimage"] = 1
        elif "micro_indicators_json" in fields and "is_ashura_pilgrimage" not in fields:
            try:
                micros_list = json.loads(fields["micro_indicators_json"])
                if any("عاشورا" in str(m) for m in micros_list):
                    fields["is_ashura_pilgrimage"] = 1
            except Exception:
                pass
        if "program_kinds" in fields:
            progs = fields.pop("program_kinds")
            if "program_kinds_json" not in fields:
                fields["program_kinds_json"] = json.dumps(progs, ensure_ascii=False)
        if "occurred_on" in fields:
            raw_occ = str(fields["occurred_on"] or "").strip()
            if not raw_occ:
                raise ValueError("تاریخ برگزاری رویداد (occurred_on) الزامی است و نمی‌تواند خالی باشد.")
            fields["occurred_on"] = normalize_to_iso_date(raw_occ)
        if "occasion" in fields:
            raw_occ = str(fields["occasion"] or "").strip()
            if not raw_occ:
                raise ValueError("عنوان یا مناسبت رویداد (occasion) نمی‌تواند خالی باشد.")
            fields["occasion"] = raw_occ
        if "unit" in fields:
            unit_val = fields["unit"]
            if hasattr(unit_val, "value"):
                unit_val = unit_val.value
            fields["unit"] = str(unit_val or "").strip() or "provincial_hq"
        unknown = set(fields) - self._EDITABLE_EVENT_FIELDS
        if unknown:
            raise ValueError(f"fields not editable: {sorted(unknown)}")

        def _op(conn):
            row = conn.execute(
                "SELECT version FROM reported_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None:
                raise EventNotFoundError(f"event {event_id} not found")
            version = int(row["version"])
            current_etag = self._compute_etag(event_id, version)
            if current_etag != expected_etag:
                raise EtagConflictError(event_id, current_etag)
            if fields:
                assignments = [f"{key} = ?" for key in fields]
                values = [
                    v.value if hasattr(v, "value")
                    else (int(v) if isinstance(v, bool)
                    else (str(v) if isinstance(v, (date, datetime))
                    else v))
                    for v in fields.values()
                ]
                assignments.append("version = ?")
                values.append(version + 1)
                values.append(event_id)
                conn.execute(
                    f"UPDATE reported_events SET {', '.join(assignments)} WHERE event_id = ?",
                    tuple(values),
                )
            else:
                conn.execute(
                    "UPDATE reported_events SET version = ? WHERE event_id = ?",
                    (version + 1, event_id),
                )

            if facts_to_update is not None and isinstance(facts_to_update, list):
                conn.execute("DELETE FROM event_facts WHERE event_id = ?", (event_id,))
                for f in facts_to_update:
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
                            event_id,
                            str(f.get("metric", "metric")),
                            float(f.get("value", 0)),
                            "observed" if str(f.get("value_kind", "observed")) not in FactValueKind._value2member_map_ else str(f.get("value_kind")),
                            str(f.get("unit_of_measure", "count")),
                            str(f.get("scope", "province")),
                            json.dumps(list(f.get("evidence_refs") or []), ensure_ascii=False),
                            "manual" if str(f.get("source", "manual")) not in ValueSource._value2member_map_ else str(f.get("source")),
                            _utc_now(),
                            actor,
                            str(f.get("note") or ""),
                        ),
                    )

            new_etag = self._compute_etag(event_id, version + 1)
            changed_keys = sorted(fields)
            if facts_to_update is not None:
                changed_keys.append("facts")
            self._append_audit(
                conn, actor=actor, action="event.update",
                entity_type="reported_events", entity_id=event_id,
                diff={"changed": changed_keys},
                etag_before=current_etag, etag_after=new_etag,
            )
            return new_etag

        return self._run_in_transaction(_op)

    _STATUS_TRANSITIONS = {
        "submit_review": {"draft": "needs_review", "needs_review": "needs_review"},
        "approve": {"needs_review": "approved"},
        "request_revision": {"needs_review": "needs_review", "approved": "needs_review"},
        "mark_conflict": {"needs_review": "conflict", "approved": "conflict"},
        "reopen": {"conflict": "needs_review"},
    }

    def transition_event_status(
        self,
        event_id: str,
        *,
        action: str,
        actor: str,
        reason: str = "",
        actor_id: str | None = None,
        actor_name: str | None = None,
        actor_role: str = "",
        defects_json: str | None = None,
    ) -> str:
        if action not in self._STATUS_TRANSITIONS:
            raise InvalidStatusTransitionError(f"unknown action {action}")
        if action == "mark_conflict" and not reason.strip():
            raise InvalidStatusTransitionError("mark_conflict requires a reason")
        if action == "request_revision" and not reason.strip():
            raise InvalidStatusTransitionError("request_revision requires a reason or defect notes")

        act_id = actor_id or actor
        act_name = actor_name or actor

        def _op(conn):
            row = conn.execute(
                "SELECT version, review_status FROM reported_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None:
                raise EventNotFoundError(f"event {event_id} not found")
            version = int(row["version"])
            current = row["review_status"]
            targets = self._STATUS_TRANSITIONS[action]
            if current not in targets:
                raise InvalidStatusTransitionError(
                    f"{action} not allowed from status {current}"
                )
            new_status = targets[current]
            now_iso = _utc_now()
            etag_before = self._compute_etag(event_id, version)

            if action == "approve":
                conn.execute(
                    """
                    UPDATE reported_events
                    SET review_status = ?, version = ?, reviewed_by_id = ?, reviewed_by_name = ?,
                        reviewed_at = ?, review_notes = ?
                    WHERE event_id = ?
                    """,
                    (new_status, version + 1, act_id, act_name, now_iso, reason, event_id),
                )
            elif action == "request_revision":
                conn.execute(
                    """
                    UPDATE reported_events
                    SET review_status = ?, version = ?, reviewed_by_id = ?, reviewed_by_name = ?,
                        reviewed_at = ?, review_notes = ?,
                        revision_count = revision_count + 1,
                        defects_json = COALESCE(?, defects_json)
                    WHERE event_id = ?
                    """,
                    (new_status, version + 1, act_id, act_name, now_iso, reason, defects_json, event_id),
                )
            elif action == "mark_conflict":
                conn.execute(
                    """
                    UPDATE reported_events
                    SET review_status = ?, version = ?, reviewed_by_id = ?, reviewed_by_name = ?,
                        reviewed_at = ?, review_notes = ?
                    WHERE event_id = ?
                    """,
                    (new_status, version + 1, act_id, act_name, now_iso, reason, event_id),
                )
            elif action == "submit_review":
                conn.execute(
                    """
                    UPDATE reported_events
                    SET review_status = ?, version = ?,
                        registered_by_id = CASE WHEN registered_by_id = '' THEN ? ELSE registered_by_id END,
                        registered_by_name = CASE WHEN registered_by_name = '' THEN ? ELSE registered_by_name END
                    WHERE event_id = ?
                    """,
                    (new_status, version + 1, act_id, act_name, event_id),
                )
            else:
                conn.execute(
                    "UPDATE reported_events SET review_status = ?, version = ? WHERE event_id = ?",
                    (new_status, version + 1, event_id),
                )

            etag_after = self._compute_etag(event_id, version + 1)
            diff_payload: dict[str, Any] = {
                "from": current,
                "to": new_status,
                "reason": reason,
            }

            self._append_audit(
                conn, actor=actor, action=f"event.{action}",
                entity_type="reported_events", entity_id=event_id,
                diff=diff_payload,
                etag_before=etag_before, etag_after=etag_after,
            )
            return etag_after

        return self._run_in_transaction(_op)

    def _lookup_witness_details(self, message_id: int | str) -> tuple[str, dict | None, Path | None]:
        """Look up message text, media_json, and thumbnail path for an Eitaa message."""
        msg_num = int(message_id) if str(message_id).isdigit() else 0
        if not msg_num:
            return ("", None, None)

        base_dir = self.db_path.parent.parent
        found_text = ""
        found_media = None

        for mdb in glob.glob(str(base_dir / "accounts/*/core/messages.sqlite3")):
            try:
                with sqlite3.connect(mdb) as mconn:
                    mconn.row_factory = sqlite3.Row
                    mrow = mconn.execute(
                        "SELECT text, media_json FROM messages WHERE message_id = ?", (msg_num,)
                    ).fetchone()
                    if mrow:
                        found_text = mrow["text"] or ""
                        if mrow["media_json"]:
                            try:
                                found_media = json.loads(mrow["media_json"])
                            except Exception:
                                pass
                        break
            except Exception:
                pass

        cached_path = None
        pattern = f"*_{msg_num}_*.jpg"
        for cfile in glob.glob(str(base_dir / "accounts/*/media/ui-cache/thumbnail" / pattern)):
            if os.path.isfile(cfile) and os.path.getsize(cfile) > 0:
                cached_path = Path(cfile)
                break
        if not cached_path:
            for cfile in glob.glob(str(base_dir / "media/ui-cache/thumbnail" / pattern)):
                if os.path.isfile(cfile) and os.path.getsize(cfile) > 0:
                    cached_path = Path(cfile)
                    break

        return (found_text, found_media, cached_path)

    def _auto_attach_witness_media(
        self,
        conn: sqlite3.Connection,
        event_id: str,
        peer_id: str,
        message_id: str,
        witness_id: str,
        actor: str,
        now: str,
    ) -> None:
        """Locate cached thumbnail/photo for this witness message and link into event_documents."""
        msg_num = int(message_id) if str(message_id).isdigit() else 0
        if not msg_num:
            return

        _, found_media, cached_path = self._lookup_witness_details(msg_num)
        if cached_path and cached_path.exists():
            doc_id = f"doc-w-{witness_id[:8]}-{msg_num}"
            existing = conn.execute(
                "SELECT document_id FROM event_documents WHERE event_id = ? AND (document_id = ? OR storage_ref = ?)",
                (event_id, doc_id, str(cached_path.resolve())),
            ).fetchone()
            if not existing:
                cur_count = conn.execute(
                    "SELECT COUNT(*) FROM event_documents WHERE event_id = ?", (event_id,)
                ).fetchone()[0]
                is_cover = 1 if cur_count == 0 else 0
                conn.execute(
                    """
                    INSERT OR IGNORE INTO event_documents (
                        document_id, event_id, media_id, sha256, kind,
                        size_bytes, display_order, is_cover, added_by, added_at, storage_ref
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        event_id,
                        f"تصویر شاهد ایتا #{msg_num}",
                        "",
                        "image",
                        cached_path.stat().st_size,
                        cur_count + 1,
                        is_cover,
                        actor or "eitaa_witness",
                        now,
                        str(cached_path.resolve()),
                    ),
                )

    def link_witness(self, event_id: str, *, peer_id: str, message_id: str,
                     provider: str = "eitaa", messenger_account: str = "",
                     role: str = "primary", note: str = "", actor: str,
                     observed_at: str | None = None) -> dict:
        if role not in {"primary", "supporting"}:
            raise ValueError(f"invalid witness role {role}")
        if role == "supporting" and not note.strip():
            raise ValueError("supporting links require a note/reason")
        identity = f"{provider}|{messenger_account}|{peer_id}|{message_id}"
        witness_id = f"w-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"

        def _op(conn):
            event_row = conn.execute(
                "SELECT version FROM reported_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if event_row is None:
                raise EventNotFoundError(f"event {event_id} not found")
            now = _utc_now()
            conn.execute(
                """
                INSERT OR IGNORE INTO reporting_message_witnesses (
                    witness_id, provider, messenger_account, peer_id, message_id,
                    observed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (witness_id, provider, messenger_account, peer_id, message_id,
                 observed_at or now, now),
            )
            if role == "primary":
                existing = conn.execute(
                    "SELECT event_id FROM reporting_event_witness_links "
                    "WHERE witness_id = ? AND role = 'primary' AND detached_at IS NULL",
                    (witness_id,),
                ).fetchone()
                if existing is not None and existing["event_id"] != event_id:
                    raise WitnessConflictError(
                        f"witness already primary-linked to event {existing['event_id']}",
                        {"existing_event_id": existing["event_id"], "witness_id": witness_id},
                    )
            pair = conn.execute(
                "SELECT link_id FROM reporting_event_witness_links "
                "WHERE event_id = ? AND witness_id = ? AND detached_at IS NULL",
                (event_id, witness_id),
            ).fetchone()
            if pair is not None:
                raise WitnessConflictError(
                    "witness already linked to this event",
                    {"event_id": event_id, "witness_id": witness_id},
                )
            link_id = f"wl-{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO reporting_event_witness_links (
                    link_id, event_id, witness_id, role, linked_by, linked_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (link_id, event_id, witness_id, role, actor, now, note),
            )
            if provider == "eitaa" and message_id:
                try:
                    self._auto_attach_witness_media(conn, event_id, peer_id, message_id, witness_id, actor, now)
                except Exception:
                    pass
            if messenger_account == "":
                conn.execute(
                    """
                    INSERT OR IGNORE INTO reporting_review_queue (
                        queue_id, item_type, ref_table, ref_id, reason, status, created_at
                    ) VALUES (?, 'witness_missing_account', 'reporting_message_witnesses',
                              ?, 'witness recorded without a messenger account; needs human confirmation',
                              'open', ?)
                    """,
                    (f"rq-witness-{witness_id}", witness_id, now),
                )
            version = int(event_row["version"])
            etag_after = self._compute_etag(event_id, version + 1)
            conn.execute(
                "UPDATE reported_events SET version = ? WHERE event_id = ?",
                (version + 1, event_id),
            )
            self._append_audit(
                conn, actor=actor, action=f"witness.link.{role}",
                entity_type="reported_events", entity_id=event_id,
                diff={"witness_id": witness_id, "role": role},
                etag_after=etag_after,
            )
            return {"witness_id": witness_id, "link_id": link_id, "etag": etag_after}

        return self._run_in_transaction(_op)

    def detach_witness_link(self, link_id: str, *, reason: str, actor: str) -> bool:
        def _op(conn):
            row = conn.execute(
                "SELECT event_id FROM reporting_event_witness_links "
                "WHERE link_id = ? AND detached_at IS NULL",
                (link_id,),
            ).fetchone()
            if row is None:
                return False
            now = _utc_now()
            conn.execute(
                "UPDATE reporting_event_witness_links SET detached_at = ?, detached_reason = ? "
                "WHERE link_id = ?",
                (now, reason, link_id),
            )
            version_row = conn.execute(
                "SELECT version FROM reported_events WHERE event_id = ?",
                (row["event_id"],),
            ).fetchone()
            etag_after = None
            if version_row is not None:
                conn.execute(
                    "UPDATE reported_events SET version = ? WHERE event_id = ?",
                    (int(version_row["version"]) + 1, row["event_id"]),
                )
                etag_after = self._compute_etag(row["event_id"], int(version_row["version"]) + 1)
            self._append_audit(
                conn, actor=actor, action="witness.detach",
                entity_type="reported_events", entity_id=row["event_id"],
                diff={"link_id": link_id, "reason": reason},
                etag_after=etag_after,
            )
            return True

        return self._run_in_transaction(_op)

    def resolve_review_item(self, queue_id: str, *, actor: str, decision: str,
                            note: str = "") -> bool:
        if decision not in {"resolved", "dismissed"}:
            raise ValueError(f"invalid decision {decision}")

        def _op(conn):
            cur = conn.execute(
                "UPDATE reporting_review_queue SET status = ?, resolved_at = ?, resolved_by = ? "
                "WHERE queue_id = ? AND status = 'open'",
                (decision, _utc_now(), actor, queue_id),
            )
            if cur.rowcount == 0:
                return False
            self._append_audit(
                conn, actor=actor, action="queue.resolve",
                entity_type="reporting_review_queue", entity_id=queue_id,
                diff={"decision": decision, "note": note},
            )
            return True

        return self._run_in_transaction(_op)

    def set_user_roles(self, user_id: str, roles, *, actor: str) -> None:
        allowed = {"editor", "approver", "admin"}
        unknown = set(roles) - allowed
        if unknown:
            raise ValueError(f"unknown roles: {sorted(unknown)}")

        def _op(conn):
            conn.execute(
                """
                INSERT INTO reporting_user_roles (user_id, roles_json, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    roles_json = excluded.roles_json,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (user_id, json.dumps(sorted(roles), ensure_ascii=False), actor, _utc_now()),
            )
            self._append_audit(
                conn, actor=actor, action="roles.set",
                entity_type="reporting_user_roles", entity_id=user_id,
                diff={"roles": sorted(roles)},
            )

        self._run_in_transaction(_op)

    def get_user_roles(self, user_id: str) -> list[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT roles_json FROM reporting_user_roles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return []
        return list(json.loads(row["roles_json"]))

    def get_event_audit(self, event_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reporting_audit_log "
                "WHERE entity_type = 'reported_events' AND entity_id = ? "
                "ORDER BY created_at, audit_id",
                (event_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["diff"] = json.loads(item.pop("diff_json") or "{}")
            results.append(item)
        return results

    def list_review_queue(self, *, status: str | None = None,
                          item_type: str | None = None) -> list[dict]:
        query = "SELECT * FROM reporting_review_queue WHERE 1=1"
        params: list = []
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if item_type is not None:
            query += " AND item_type = ?"
            params.append(item_type)
        query += " ORDER BY created_at, queue_id"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def get_event_file(self, event_id: str) -> dict | None:
        """Load the event file: raw fields, etag, witnesses and documents."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reported_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                return None
            version = int(row["version"])
            file = dict(row)
            file.pop("version", None)
            witnesses = conn.execute(
                """
                SELECT l.link_id, l.witness_id, l.role, l.linked_by, l.linked_at,
                       l.note, l.detached_at, l.detached_reason,
                       w.provider, w.messenger_account, w.peer_id, w.message_id
                FROM reporting_event_witness_links l
                JOIN reporting_message_witnesses w ON w.witness_id = l.witness_id
                WHERE l.event_id = ?
                ORDER BY l.linked_at, l.link_id
                """,
                (event_id,),
            ).fetchall()
            now = _utc_now()
            for w in witnesses:
                if w["provider"] == "eitaa" and w["message_id"] and not w["detached_at"]:
                    try:
                        self._auto_attach_witness_media(
                            conn, event_id, w["peer_id"], str(w["message_id"]), w["witness_id"], w["linked_by"] or "eitaa_witness", now
                        )
                    except Exception:
                        pass

            documents = conn.execute(
                """
                SELECT document_id, event_id, media_id, sha256, kind, size_bytes, display_order,
                       is_cover, added_by, added_at, storage_ref
                FROM event_documents WHERE event_id = ?
                ORDER BY display_order, added_at
                """,
                (event_id,),
            ).fetchall()
            fact_rows = conn.execute(
                "SELECT * FROM event_facts WHERE event_id = ? ORDER BY created_at ASC", (event_id,)
            ).fetchall()
            file["facts"] = [
                {
                    "metric": fr["metric"],
                    "value": float(fr["value"]),
                    "value_kind": fr["value_kind"],
                    "unit_of_measure": fr["unit_of_measure"],
                    "source": fr["source"],
                    "note": fr["note"] or "",
                }
                for fr in fact_rows
            ]
        file["etag"] = self._compute_etag(event_id, version)
        enriched_witnesses = []
        for w in witnesses:
            wd = dict(w)
            if wd.get("provider") == "eitaa" and wd.get("message_id"):
                try:
                    f_text, f_media, f_path = self._lookup_witness_details(wd["message_id"])
                    if f_text:
                        wd["text"] = f_text
                    if f_media and isinstance(f_media, dict):
                        wd["media_type"] = f_media.get("type")
                    if f_path and f_path.exists():
                        wd["storage_ref"] = str(f_path.resolve())
                        wd["is_image"] = True
                except Exception:
                    pass
            enriched_witnesses.append(wd)
        file["witnesses"] = enriched_witnesses
        file["documents"] = [dict(d) for d in documents]
        if file.get("micro_indicators_json"):
            try:
                file["micro_indicators"] = json.loads(file["micro_indicators_json"])
            except Exception:
                file["micro_indicators"] = []
        else:
            file["micro_indicators"] = []

        if file.get("program_kinds_json"):
            try:
                file["program_kinds"] = json.loads(file["program_kinds_json"])
            except Exception:
                file["program_kinds"] = []
        else:
            file["program_kinds"] = []

        if file.get("defects_json"):
            try:
                file["defects"] = json.loads(file["defects_json"])
            except Exception:
                file["defects"] = []
        else:
            file["defects"] = []
        return file

    def attach_document(
        self,
        event_id: str,
        *,
        media_id: str,
        sha256: str = "",
        kind: str = "",
        size_bytes: int | None = None,
        display_order: int = 0,
        is_cover: bool = False,
        added_by: str = "",
        storage_ref: str = "",
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Attach document metadata to an event in event_documents."""
        doc_id = document_id or f"doc-{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        def _op(conn):
            cur = conn.execute("SELECT event_id FROM reported_events WHERE event_id = ?", (event_id,))
            if not cur.fetchone():
                raise EventNotFoundError(f"event {event_id} does not exist")
            conn.execute(
                """
                INSERT INTO event_documents (
                    document_id, event_id, media_id, sha256, kind,
                    size_bytes, display_order, is_cover, added_by, added_at, storage_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    event_id,
                    media_id,
                    sha256,
                    kind,
                    size_bytes,
                    int(display_order),
                    1 if is_cover else 0,
                    added_by,
                    now,
                    storage_ref,
                ),
            )
            self._append_audit(
                conn,
                actor=added_by or "system",
                action="document.attach",
                entity_type="event",
                entity_id=event_id,
                diff={"document_id": doc_id, "media_id": media_id, "sha256": sha256, "kind": kind},
            )
        self._run_in_transaction(_op)
        return {
            "document_id": doc_id,
            "event_id": event_id,
            "media_id": media_id,
            "sha256": sha256,
            "kind": kind,
            "size_bytes": size_bytes,
            "display_order": display_order,
            "is_cover": is_cover,
            "added_by": added_by,
            "added_at": now,
            "storage_ref": storage_ref,
        }

    def delete_document(self, event_id: str, document_id: str, actor: str = "system") -> bool:
        """Delete document from event_documents and cleanup physical file if stored on disk."""
        def _op(conn):
            row = conn.execute(
                "SELECT storage_ref FROM event_documents WHERE event_id = ? AND (document_id = ? OR media_id = ?)",
                (event_id, document_id, document_id),
            ).fetchone()
            if not row:
                return False
            storage_ref = row["storage_ref"] if "storage_ref" in row.keys() else ""
            if storage_ref and os.path.exists(storage_ref):
                try:
                    os.remove(storage_ref)
                except Exception:
                    pass

            conn.execute(
                "DELETE FROM event_documents WHERE event_id = ? AND (document_id = ? OR media_id = ?)",
                (event_id, document_id, document_id),
            )
            self._append_audit(
                conn,
                actor=actor,
                action="document.delete",
                entity_type="event",
                entity_id=event_id,
                diff={"document_id": document_id},
            )
            return True

        return self._run_in_transaction(_op)

    def set_document_cover(self, event_id: str, document_id: str, is_cover: bool = True, actor: str = "system") -> bool:
        """Set or toggle a document as cover photo for an event."""
        def _op(conn):
            if is_cover:
                conn.execute("UPDATE event_documents SET is_cover = 0 WHERE event_id = ?", (event_id,))
            conn.execute(
                "UPDATE event_documents SET is_cover = ? WHERE event_id = ? AND document_id = ?",
                (1 if is_cover else 0, event_id, document_id),
            )
            self._append_audit(
                conn,
                actor=actor,
                action="document.set_cover",
                entity_type="event",
                entity_id=event_id,
                diff={"document_id": document_id, "is_cover": is_cover},
            )
            return True

        return self._run_in_transaction(_op)

    def upload_and_attach_document(
        self,
        event_id: str,
        *,
        filename: str,
        content_bytes: bytes,
        kind: str = "",
        display_order: int = 0,
        is_cover: bool = False,
        added_by: str = "",
    ) -> dict[str, Any]:
        """Save raw file bytes to disk under reporting_documents/{event_id} and record in event_documents."""
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        size_bytes = len(content_bytes)

        # Sanitize filename
        raw_name = Path(filename).name
        safe_name = re.sub(r"[^\w.\-\u0600-\u06FF]", "_", raw_name)
        if not safe_name:
            safe_name = "file.bin"

        ext = Path(safe_name).suffix.lower()
        if not kind:
            if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
                kind = "image"
            elif ext == ".pdf":
                kind = "pdf"
            elif ext in {".doc", ".docx"}:
                kind = "word"
            elif ext in {".xls", ".xlsx"}:
                kind = "excel"
            else:
                kind = "document"

        doc_dir = self.db_path.parent / "reporting_documents" / event_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = doc_dir / f"{doc_id}_{safe_name}"
        file_path.write_bytes(content_bytes)

        storage_ref = str(file_path.resolve())

        return self.attach_document(
            event_id,
            media_id=safe_name,
            sha256=sha256,
            kind=kind,
            size_bytes=size_bytes,
            display_order=display_order,
            is_cover=is_cover,
            added_by=added_by,
            storage_ref=storage_ref,
            document_id=doc_id,
        )

    def list_user_role_entries(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id, roles_json, updated_by, updated_at "
                "FROM reporting_user_roles ORDER BY user_id"
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["roles"] = list(json.loads(item.pop("roles_json") or "[]"))
            results.append(item)
        return results

    # ----------------------------------------------------------------------
    # Assistant Feedback and Scoped Aliases (Phase 5 of Unified Strategy)
    # ----------------------------------------------------------------------

    def record_assistant_feedback(
        self,
        *,
        candidate_id: str,
        actor: str,
        action: str,
        scope_kind: str = "local",
        scope_target: str = "",
        suggested_program: str = "",
        suggested_unit: str = "",
        chosen_program: str = "",
        chosen_unit: str = "",
        rule_version: str = "1.0",
        notes: str | None = None,
        feedback_id: str | None = None,
    ) -> dict[str, Any]:
        """Record human reviewer feedback on assistant suggestion (ADR-42/ADR-46/Strategy §7)."""
        valid_actions = {"accept", "correct", "reject", "abstain"}
        if action not in valid_actions:
            raise ValueError(f"action must be one of {sorted(valid_actions)}")
        valid_scopes = {"local", "program", "unit", "global"}
        if scope_kind not in valid_scopes:
            raise ValueError(f"scope_kind must be one of {sorted(valid_scopes)}")
        fid = feedback_id or f"afb-{uuid.uuid4().hex[:12]}"
        now = _utc_now()

        def _op(conn):
            conn.execute(
                """
                INSERT INTO assistant_feedback (
                    feedback_id, candidate_id, scope_kind, scope_target,
                    suggested_program, suggested_unit, chosen_program, chosen_unit,
                    rule_version, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fid,
                    candidate_id,
                    scope_kind,
                    scope_target,
                    suggested_program,
                    suggested_unit,
                    chosen_program,
                    chosen_unit,
                    rule_version,
                    actor,
                    action,
                    notes,
                    now,
                ),
            )
            self._append_audit(
                conn,
                actor=actor,
                action="assistant.feedback.record",
                entity_type="assistant_feedback",
                entity_id=fid,
                diff={"candidate_id": candidate_id, "action": action, "scope_kind": scope_kind},
            )

        self._run_in_transaction(_op)
        return {
            "feedback_id": fid,
            "candidate_id": candidate_id,
            "scope_kind": scope_kind,
            "scope_target": scope_target,
            "suggested_program": suggested_program,
            "suggested_unit": suggested_unit,
            "chosen_program": chosen_program,
            "chosen_unit": chosen_unit,
            "rule_version": rule_version,
            "actor": actor,
            "action": action,
            "notes": notes,
            "created_at": now,
        }

    def revoke_assistant_feedback(self, feedback_id: str, *, actor: str) -> None:
        """Revoke a previously recorded feedback (ADR-46 revocable learning)."""
        now = _utc_now()

        def _op(conn):
            cur = conn.execute(
                "SELECT feedback_id FROM assistant_feedback WHERE feedback_id = ?",
                (feedback_id,),
            )
            if not cur.fetchone():
                raise LookupError(f"feedback {feedback_id} not found")
            conn.execute(
                "UPDATE assistant_feedback SET revoked_at = ?, revoked_by = ? WHERE feedback_id = ?",
                (now, actor, feedback_id),
            )
            self._append_audit(
                conn,
                actor=actor,
                action="assistant.feedback.revoke",
                entity_type="assistant_feedback",
                entity_id=feedback_id,
                diff={"revoked_at": now},
            )

        self._run_in_transaction(_op)

    def list_assistant_feedback(
        self,
        *,
        candidate_id: str | None = None,
        scope_kind: str | None = None,
        include_revoked: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List feedback records with optional filtering."""
        clauses = []
        params: list[Any] = []
        if candidate_id:
            clauses.append("candidate_id = ?")
            params.append(candidate_id)
        if scope_kind:
            clauses.append("scope_kind = ?")
            params.append(scope_kind)
        if not include_revoked:
            clauses.append("revoked_at IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT * FROM assistant_feedback {where} ORDER BY created_at DESC LIMIT ?",
                (*params, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def add_scoped_alias(
        self,
        *,
        alias_text: str,
        canonical_target: str,
        target_type: str,
        approved_by: str,
        scope_kind: str = "local",
        scope_target: str = "",
        weight: float = 1.0,
        alias_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a scoped alias without polluting global namespace without approval."""
        valid_targets = {"program", "unit", "occasion"}
        if target_type not in valid_targets:
            raise ValueError(f"target_type must be one of {sorted(valid_targets)}")
        valid_scopes = {"local", "program", "unit", "global"}
        if scope_kind not in valid_scopes:
            raise ValueError(f"scope_kind must be one of {sorted(valid_scopes)}")
        if scope_kind == "global" and not approved_by:
            raise ValueError("global aliases require explicit approval (approved_by)")
        clean_alias = alias_text.strip()
        if not clean_alias:
            raise ValueError("alias_text cannot be empty")
        aid = alias_id or f"alias-{uuid.uuid4().hex[:12]}"
        now = _utc_now()

        def _op(conn):
            conn.execute(
                """
                INSERT INTO assistant_scoped_aliases (
                    alias_id, alias_text, canonical_target, target_type,
                    scope_kind, scope_target, weight, approved_by, created_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    aid,
                    clean_alias,
                    canonical_target,
                    target_type,
                    scope_kind,
                    scope_target,
                    float(weight),
                    approved_by,
                    now,
                ),
            )
            self._append_audit(
                conn,
                actor=approved_by,
                action="assistant.alias.create",
                entity_type="assistant_scoped_aliases",
                entity_id=aid,
                diff={"alias_text": clean_alias, "target": canonical_target, "scope_kind": scope_kind},
            )

        self._run_in_transaction(_op)
        return {
            "alias_id": aid,
            "alias_text": clean_alias,
            "canonical_target": canonical_target,
            "target_type": target_type,
            "scope_kind": scope_kind,
            "scope_target": scope_target,
            "weight": weight,
            "approved_by": approved_by,
            "created_at": now,
            "status": "active",
        }

    def revoke_scoped_alias(self, alias_id: str, *, actor: str) -> None:
        """Revoke a scoped alias."""
        def _op(conn):
            cur = conn.execute(
                "SELECT alias_id FROM assistant_scoped_aliases WHERE alias_id = ?",
                (alias_id,),
            )
            if not cur.fetchone():
                raise LookupError(f"alias {alias_id} not found")
            conn.execute(
                "UPDATE assistant_scoped_aliases SET status = 'revoked' WHERE alias_id = ?",
                (alias_id,),
            )
            self._append_audit(
                conn,
                actor=actor,
                action="assistant.alias.revoke",
                entity_type="assistant_scoped_aliases",
                entity_id=alias_id,
                diff={"status": "revoked"},
            )

        self._run_in_transaction(_op)

    def list_scoped_aliases(
        self,
        *,
        scope_kind: str | None = None,
        scope_target: str | None = None,
        target_type: str | None = None,
        status: str = "active",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List active/revoked scoped aliases."""
        clauses = []
        params: list[Any] = []
        if scope_kind:
            clauses.append("scope_kind = ?")
            params.append(scope_kind)
        if scope_target:
            clauses.append("scope_target = ?")
            params.append(scope_target)
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT * FROM assistant_scoped_aliases {where} ORDER BY created_at DESC LIMIT ?",
                (*params, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def find_witness_status(self, peer_id: str, message_ids) -> list[dict]:
        """Per-message report-registration status for chat-surface chips."""
        ids = [str(m) for m in message_ids if str(m).strip()]
        if not peer_id or not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT w.peer_id, w.message_id, l.role, l.detached_at,
                       e.event_id, e.review_status
                FROM reporting_message_witnesses w
                JOIN reporting_event_witness_links l ON l.witness_id = w.witness_id
                JOIN reported_events e ON e.event_id = l.event_id
                WHERE w.provider = 'eitaa' AND w.peer_id = ?
                  AND w.message_id IN ({placeholders})
                """,
                (peer_id, *ids),
            ).fetchall()
        grouped: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row["peer_id"], row["message_id"])
            entry = grouped.setdefault(
                key,
                {
                    "peer_id": row["peer_id"],
                    "message_id": row["message_id"],
                    "registered": False,
                    "events": [],
                },
            )
            if row["detached_at"] is None:
                entry["registered"] = True
                entry["events"].append(
                    {
                        "event_id": row["event_id"],
                        "role": row["role"],
                        "review_status": row["review_status"],
                    }
                )
        return [grouped[key] for key in sorted(grouped)]

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
                    is_ashura_pilgrimage, contains_inner_contest, campaign, notes, created_at, created_by, review_status,
                    registered_by_id, registered_by_name, reviewed_by_id, reviewed_by_name,
                    reviewed_at, review_notes, revision_count, defects_json,
                    macro_category, custom_topic, macro_indicator, micro_indicators_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    created_by = excluded.created_by,
                    review_status = CASE WHEN excluded.review_status != 'draft' THEN excluded.review_status ELSE reported_events.review_status END,
                    registered_by_id = CASE WHEN excluded.registered_by_id != '' THEN excluded.registered_by_id ELSE reported_events.registered_by_id END,
                    registered_by_name = CASE WHEN excluded.registered_by_name != '' THEN excluded.registered_by_name ELSE reported_events.registered_by_name END,
                    reviewed_by_id = CASE WHEN excluded.reviewed_by_id != '' THEN excluded.reviewed_by_id ELSE reported_events.reviewed_by_id END,
                    reviewed_by_name = CASE WHEN excluded.reviewed_by_name != '' THEN excluded.reviewed_by_name ELSE reported_events.reviewed_by_name END,
                    reviewed_at = CASE WHEN excluded.reviewed_at IS NOT NULL THEN excluded.reviewed_at ELSE reported_events.reviewed_at END,
                    review_notes = CASE WHEN excluded.review_notes != '' THEN excluded.review_notes ELSE reported_events.review_notes END,
                    revision_count = CASE WHEN excluded.revision_count > 0 THEN excluded.revision_count ELSE reported_events.revision_count END,
                    defects_json = CASE WHEN excluded.defects_json != '[]' THEN excluded.defects_json ELSE reported_events.defects_json END,
                    macro_category = excluded.macro_category,
                    custom_topic = excluded.custom_topic,
                    macro_indicator = excluded.macro_indicator,
                    micro_indicators_json = excluded.micro_indicators_json
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
                    event.review_status or "draft",
                    event.registered_by_id or event.created_by or "",
                    event.registered_by_name or event.created_by or "",
                    event.reviewed_by_id or "",
                    event.reviewed_by_name or "",
                    event.reviewed_at.isoformat() if hasattr(event.reviewed_at, "isoformat") else (event.reviewed_at or None),
                    event.review_notes or "",
                    event.revision_count or 0,
                    event.defects_json or "[]",
                    getattr(event, "macro_category", "workbook_approved") or "workbook_approved",
                    getattr(event, "custom_topic", "") or "",
                    getattr(event, "macro_indicator", "") or "",
                    json.dumps(getattr(event, "micro_indicators", []) or [], ensure_ascii=False),
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

    def list_events(
        self,
        *,
        limit: int = 200,
        review_status: str | None = None,
        registered_by_id: str | None = None,
        macro_category: str | None = None,
        micro_indicator: str | None = None,
        macro_indicator: str | None = None,
        unit_name: str | None = None,
        program_code: str | None = None,
        search_query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[ReportedEvent]:
        with self._connect() as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if review_status and review_status != "all":
                clauses.append("review_status = ?")
                params.append(review_status)
            if registered_by_id:
                clauses.append("(registered_by_id = ? OR created_by = ?)")
                params.extend([registered_by_id, registered_by_id])
            if macro_category:
                clauses.append("macro_category = ?")
                params.append(macro_category)
            if micro_indicator:
                clauses.append("micro_indicators_json LIKE ?")
                params.append(f"%{micro_indicator.strip()}%")
            if macro_indicator:
                clauses.append("macro_indicator = ?")
                params.append(macro_indicator.strip())
            if unit_name:
                clauses.append("unit_name LIKE ?")
                params.append(f"%{unit_name.strip()}%")
            if program_code:
                clean_p = program_code.strip()
                search_terms = {clean_p}
                PROGRAM_CODE_MAP = {
                    "80401": "trip",
                    "80402": "contest",
                    "80403": "ceremony",
                    "80501": "prayer",
                    "80406": "honor",
                    "80601": "customer_care",
                    "80202": "charter",
                    "80301": "training",
                }
                if clean_p in PROGRAM_CODE_MAP:
                    search_terms.add(PROGRAM_CODE_MAP[clean_p])
                for code_k, kind_v in PROGRAM_CODE_MAP.items():
                    if kind_v == clean_p:
                        search_terms.add(code_k)
                try:
                    cat_rows = conn.execute(
                        "SELECT program_code, kind, title, workbook_sheet FROM reporting_program_catalog WHERE program_code = ? OR kind = ?",
                        (clean_p, clean_p),
                    ).fetchall()
                    for r in cat_rows:
                        if r["program_code"]:
                            search_terms.add(r["program_code"])
                        if r["kind"]:
                            search_terms.add(r["kind"])
                        if r["title"]:
                            search_terms.add(r["title"])
                        if r["workbook_sheet"]:
                            search_terms.add(r["workbook_sheet"])
                except Exception:
                    pass

                term_clauses = []
                for term in sorted(search_terms):
                    if term:
                        term_clauses.append("program_kinds_json LIKE ? OR macro_indicator LIKE ?")
                        params.extend([f"%{term}%", f"%{term}%"])
                if term_clauses:
                    clauses.append(f"({' OR '.join(term_clauses)})")
            if search_query:
                q = f"%{search_query.strip()}%"
                clauses.append("(occasion LIKE ? OR notes LIKE ? OR unit_name LIKE ? OR custom_topic LIKE ? OR macro_indicator LIKE ?)")
                params.extend([q, q, q, q, q])
            if date_from:
                try:
                    norm_df = normalize_to_iso_date(str(date_from).strip())
                except Exception:
                    norm_df = str(date_from).strip()
                clauses.append("occurred_on >= ?")
                params.append(norm_df)
            if date_to:
                try:
                    norm_dt = normalize_to_iso_date(str(date_to).strip())
                except Exception:
                    norm_dt = str(date_to).strip()
                clauses.append("occurred_on <= ?")
                params.append(norm_dt)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"SELECT * FROM reported_events {where} ORDER BY occurred_on DESC, created_at DESC LIMIT ?"
            params.append(limit)
            event_rows = conn.execute(sql, tuple(params)).fetchall()

            results: list[ReportedEvent] = []
            for row in event_rows:
                fact_rows = conn.execute(
                    "SELECT * FROM event_facts WHERE event_id = ?", (row["event_id"],)
                ).fetchall()

                facts = [
                    Fact(
                        metric=fr["metric"],
                        value=float(fr["value"]),
                        value_kind=FactValueKind(fr["value_kind"]) if fr["value_kind"] in FactValueKind._value2member_map_ else FactValueKind.OBSERVED,
                        unit_of_measure=fr["unit_of_measure"],
                        scope=fr["scope"],
                        evidence_refs=tuple(_safe_json_list(fr["evidence_refs_json"])),
                        source=ValueSource(fr["source"]) if fr["source"] in ValueSource._value2member_map_ else ValueSource.MANUAL,
                        created_at=_safe_datetime_from_row(fr["created_at"]),
                        created_by=fr["created_by"] or "",
                        note=fr["note"] or "",
                    )
                    for fr in fact_rows
                ]

                occurred = _safe_date_from_row(row["occurred_on"])
                kinds = tuple(_safe_program_kind(k) for k in _safe_json_list(row["program_kinds_json"]))
                unit = UnitScope(row["unit"]) if row["unit"] in {u.value for u in UnitScope} else UnitScope.PROVINCIAL_HQ
                occasion_class = OccasionClass(row["occasion_class"]) if row["occasion_class"] and row["occasion_class"] in OccasionClass._value2member_map_ else None
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
                    macro_category=row["macro_category"] if "macro_category" in row.keys() and row["macro_category"] else "workbook_approved",
                    custom_topic=row["custom_topic"] if "custom_topic" in row.keys() and row["custom_topic"] else "",
                    macro_indicator=row["macro_indicator"] if "macro_indicator" in row.keys() and row["macro_indicator"] else "",
                    micro_indicators=json.loads(row["micro_indicators_json"]) if "micro_indicators_json" in row.keys() and row["micro_indicators_json"] else [],
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
                    review_status=row["review_status"] if "review_status" in row.keys() and row["review_status"] else "draft",
                    registered_by_id=row["registered_by_id"] if "registered_by_id" in row.keys() and row["registered_by_id"] else (row["created_by"] or ""),
                    registered_by_name=row["registered_by_name"] if "registered_by_name" in row.keys() and row["registered_by_name"] else (row["created_by"] or ""),
                    reviewed_by_id=row["reviewed_by_id"] if "reviewed_by_id" in row.keys() and row["reviewed_by_id"] else "",
                    reviewed_by_name=row["reviewed_by_name"] if "reviewed_by_name" in row.keys() and row["reviewed_by_name"] else "",
                    reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if "reviewed_at" in row.keys() and row["reviewed_at"] else None,
                    review_notes=row["review_notes"] if "review_notes" in row.keys() and row["review_notes"] else "",
                    revision_count=int(row["revision_count"]) if "revision_count" in row.keys() and row["revision_count"] is not None else 0,
                    defects_json=row["defects_json"] if "defects_json" in row.keys() and row["defects_json"] else "[]",
                    version=int(row["version"]) if "version" in row.keys() and row["version"] is not None else 1,
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
                    value_kind=FactValueKind(fr["value_kind"]) if fr["value_kind"] in FactValueKind._value2member_map_ else FactValueKind.OBSERVED,
                    unit_of_measure=fr["unit_of_measure"],
                    scope=fr["scope"],
                    evidence_refs=tuple(_safe_json_list(fr["evidence_refs_json"])),
                    source=ValueSource(fr["source"]) if fr["source"] in ValueSource._value2member_map_ else ValueSource.MANUAL,
                    created_at=_safe_datetime_from_row(fr["created_at"]),
                    created_by=fr["created_by"] or "",
                    note=fr["note"] or "",
                )
                for fr in fact_rows
            ]
            occurred = _safe_date_from_row(row["occurred_on"])
            kinds = tuple(_safe_program_kind(k) for k in _safe_json_list(row["program_kinds_json"]))
            unit = UnitScope(row["unit"]) if row["unit"] in {u.value for u in UnitScope} else UnitScope.PROVINCIAL_HQ
            occasion_class = OccasionClass(row["occasion_class"]) if row["occasion_class"] and row["occasion_class"] in OccasionClass._value2member_map_ else None
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
                macro_category=row["macro_category"] if "macro_category" in row.keys() and row["macro_category"] else "workbook_approved",
                custom_topic=row["custom_topic"] if "custom_topic" in row.keys() and row["custom_topic"] else "",
                macro_indicator=row["macro_indicator"] if "macro_indicator" in row.keys() and row["macro_indicator"] else "",
                micro_indicators=_safe_json_list(row["micro_indicators_json"]) if "micro_indicators_json" in row.keys() else [],
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
                created_at=_safe_datetime_from_row(row["created_at"]),
                created_by=row["created_by"] or "",
                review_status=row["review_status"] if "review_status" in row.keys() and row["review_status"] else "draft",
                registered_by_id=row["registered_by_id"] if "registered_by_id" in row.keys() and row["registered_by_id"] else (row["created_by"] or ""),
                registered_by_name=row["registered_by_name"] if "registered_by_name" in row.keys() and row["registered_by_name"] else (row["created_by"] or ""),
                reviewed_by_id=row["reviewed_by_id"] if "reviewed_by_id" in row.keys() and row["reviewed_by_id"] else "",
                reviewed_by_name=row["reviewed_by_name"] if "reviewed_by_name" in row.keys() and row["reviewed_by_name"] else "",
                reviewed_at=_safe_datetime_from_row(row["reviewed_at"]) if "reviewed_at" in row.keys() and row["reviewed_at"] else None,
                review_notes=row["review_notes"] if "review_notes" in row.keys() and row["review_notes"] else "",
                revision_count=int(row["revision_count"]) if "revision_count" in row.keys() and row["revision_count"] is not None else 0,
                defects_json=row["defects_json"] if "defects_json" in row.keys() and row["defects_json"] else "[]",
                version=int(row["version"]) if "version" in row.keys() and row["version"] is not None else 1,
            )

    def delete_event(self, event_id: str, actor: str = "system") -> bool:
        """Safely and completely delete an event with cascade cleanup of witness links, facts, documents, queue items, and disk files."""
        # Clean up files from disk
        doc_dir = self.db_path.parent / "reporting_documents" / event_id
        if doc_dir.exists() and doc_dir.is_dir():
            try:
                import shutil
                shutil.rmtree(doc_dir, ignore_errors=True)
            except Exception:
                pass

        def _op(conn):
            cur = conn.execute("SELECT event_id FROM reported_events WHERE event_id = ?", (event_id,))
            if not cur.fetchone():
                return False

            # Delete witness links (frees up witnesses)
            conn.execute("DELETE FROM reporting_event_witness_links WHERE event_id = ?", (event_id,))
            # Delete facts
            conn.execute("DELETE FROM event_facts WHERE event_id = ?", (event_id,))
            # Delete documents
            conn.execute("DELETE FROM event_documents WHERE event_id = ?", (event_id,))
            # Delete review queue items
            conn.execute("DELETE FROM reporting_review_queue WHERE ref_id = ? AND ref_table = 'reported_events'", (event_id,))
            # Audit log
            self._append_audit(
                conn,
                actor=actor,
                action="event.delete",
                entity_type="event",
                entity_id=event_id,
                diff={"deleted": True},
            )
            # Delete event row
            res = conn.execute("DELETE FROM reported_events WHERE event_id = ?", (event_id,))
            return res.rowcount > 0

        return self._run_in_transaction(_op)

    def find_merge_candidates(self, event_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Rank and return candidate events that can be merged with event_id based on micro-indicators, program, unit, and date."""
        with self._connect() as conn:
            target_row = conn.execute("SELECT * FROM reported_events WHERE event_id = ?", (event_id,)).fetchone()
            if not target_row:
                return []

            target = dict(target_row)
            target_programs = set()
            try:
                target_programs = set(json.loads(target.get("program_kinds_json") or "[]"))
            except Exception:
                pass
            target_macro_indicator = target.get("macro_indicator") or ""
            target_micros = set()
            try:
                target_micros = set(json.loads(target.get("micro_indicators_json") or "[]"))
            except Exception:
                pass
            target_unit = target.get("unit") or target.get("unit_name") or ""
            target_date_str = str(target.get("occurred_on") or "")
            target_title = (target.get("occasion") or target.get("custom_topic") or target.get("notes") or "").lower()
            target_tokens = set(re.findall(r"\w+", target_title))

            # Fetch candidates (exclude self)
            candidates_rows = conn.execute(
                "SELECT * FROM reported_events WHERE event_id != ? ORDER BY occurred_on DESC LIMIT 200",
                (event_id,)
            ).fetchall()

            scored: list[dict[str, Any]] = []
            for row in candidates_rows:
                cand = dict(row)
                score = 0.0
                reasons: list[str] = []

                # Priority 1: شاخصه کلی (Macro Indicator) - بالاترین اولویت
                cand_macro_indicator = cand.get("macro_indicator") or ""
                macro_match = False
                if target_macro_indicator and cand_macro_indicator and target_macro_indicator == cand_macro_indicator:
                    score += 50.0
                    macro_match = True
                    reasons.append(f"همسانی قطعی شاخصه کلی ({target_macro_indicator})")
                else:
                    cand_programs = set()
                    try:
                        cand_programs = set(json.loads(cand.get("program_kinds_json") or "[]"))
                    except Exception:
                        pass
                    if target_programs and target_programs.intersection(cand_programs):
                        score += 25.0
                        macro_match = True
                        reasons.append("همسانی سرفصل کلی برنامه")

                # Priority 2: شاخصه‌های جزئی به حسب میزان همسانی (Micro-indicators similarity degree)
                cand_micros = set()
                try:
                    cand_micros = set(json.loads(cand.get("micro_indicators_json") or "[]"))
                except Exception:
                    pass
                common_micros = target_micros.intersection(cand_micros)
                union_micros = target_micros.union(cand_micros)
                micro_sim_ratio = 0.0
                if union_micros:
                    micro_sim_ratio = len(common_micros) / len(union_micros)
                if common_micros:
                    micro_score = round(micro_sim_ratio * 35.0, 1)
                    score += micro_score
                    pct = int(micro_sim_ratio * 100)
                    reasons.append(f"همسانی شاخصه‌های جزئی: {len(common_micros)} مورد مشترک ({pct}٪ هم‌پوشانی)")

                # Priority 3: همسانی واحد قضایی و سپس سایر واحدها (Judicial Unit Match)
                cand_unit = cand.get("unit") or cand.get("unit_name") or ""
                unit_match = 0
                if target_unit and cand_unit:
                    if target_unit == cand_unit or (cand.get("unit_name") and cand.get("unit_name") == target.get("unit_name")):
                        unit_match = 2
                        score += 20.0
                        reasons.append(f"همسانی قطعی واحد قضایی ({cand.get('unit_name') or cand_unit})")
                    else:
                        target_county = target_unit.split(" - ")[0].replace("دادگستری ", "").strip()
                        cand_county = cand_unit.split(" - ")[0].replace("دادگستری ", "").strip()
                        if target_county and cand_county and target_county == cand_county:
                            unit_match = 1
                            score += 10.0
                            reasons.append(f"همسانی شهرستان/حوزه قضایی ({target_county})")

                # Priority 4: سایر عوامل (نزدیکی زمانی و هم‌پوشانی متنی)
                cand_date_str = str(cand.get("occurred_on") or "")
                if target_date_str and cand_date_str:
                    if target_date_str == cand_date_str:
                        score += 10.0
                        reasons.append("تاریخ وقوع یکسان")
                    else:
                        try:
                            d1 = date.fromisoformat(target_date_str[:10])
                            d2 = date.fromisoformat(cand_date_str[:10])
                            days = abs((d1 - d2).days)
                            if days <= 7:
                                score += 5.0
                                reasons.append(f"فاصله زمانی کمتر از {days} روز")
                        except Exception:
                            pass

                # هم‌پوشانی واژگان
                cand_title = (cand.get("occasion") or cand.get("custom_topic") or cand.get("notes") or "").lower()
                cand_tokens = set(re.findall(r"\w+", cand_title))
                common_tokens = {t for t in target_tokens.intersection(cand_tokens) if len(t) > 2}
                if common_tokens:
                    token_pts = min(len(common_tokens), 5)
                    score += float(token_pts)
                    reasons.append(f"هم‌پوشانی واژگان ({len(common_tokens)} کلمه)")

                if score > 0:
                    scored.append({
                        "event_id": cand["event_id"],
                        "title": cand.get("occasion") or cand.get("custom_topic") or cand.get("notes") or "بدون عنوان",
                        "unit_name": cand.get("unit_name") or cand.get("unit") or "",
                        "occurred_on": cand.get("occurred_on") or "",
                        "review_status": cand.get("review_status") or "needs_review",
                        "macro_indicator": cand.get("macro_indicator") or "",
                        "micro_indicators": list(cand_micros),
                        "score": round(score, 1),
                        "macro_match": 1 if macro_match else 0,
                        "micro_sim_ratio": round(micro_sim_ratio, 3),
                        "unit_match": unit_match,
                        "reasons": reasons,
                    })

            # رتبه‌بندی دقیق مطابق اولویت کاربر:
            # ۱. شاخصه کلی، ۲. شاخصه جزئی به حسب میزان همسانی، ۳. همسانی واحد قضایی، ۴. امتیاز تجمیعی و تاریخ
            scored.sort(
                key=lambda x: (
                    x["macro_match"],
                    x["micro_sim_ratio"],
                    x["unit_match"],
                    x["score"],
                    x["occurred_on"],
                ),
                reverse=True,
            )
            return scored[:limit]

    def merge_events(self, target_event_id: str, source_event_id: str, actor: str = "system") -> dict[str, Any]:
        """Merge source_event_id into target_event_id.
        Re-links witnesses, transfers documents and facts, unions micro-indicators,
        and cleanly removes source event with full audit logging.
        """
        if target_event_id == source_event_id:
            raise ValueError("نمی‌توان یک رویداد را در خودش ادغام کرد.")

        def _op(conn):
            target = conn.execute("SELECT * FROM reported_events WHERE event_id = ?", (target_event_id,)).fetchone()
            if not target:
                raise EventNotFoundError(f"گزارش مقصد {target_event_id} یافت نشد.")
            source = conn.execute("SELECT * FROM reported_events WHERE event_id = ?", (source_event_id,)).fetchone()
            if not source:
                raise EventNotFoundError(f"گزارش مبدأ {source_event_id} یافت نشد.")

            # 1. Transfer witness links
            target_witnesses = {row["witness_id"] for row in conn.execute(
                "SELECT witness_id FROM reporting_event_witness_links WHERE event_id = ?", (target_event_id,)
            ).fetchall()}
            source_links = conn.execute(
                "SELECT * FROM reporting_event_witness_links WHERE event_id = ?", (source_event_id,)
            ).fetchall()
            for sl in source_links:
                w_id = sl["witness_id"]
                if w_id not in target_witnesses:
                    conn.execute(
                        "UPDATE reporting_event_witness_links SET event_id = ?, note = ? WHERE link_id = ?",
                        (target_event_id, f"Merged from {source_event_id}: {sl['note'] or ''}", sl["link_id"])
                    )
                else:
                    # Redundant witness link, remove
                    conn.execute("DELETE FROM reporting_event_witness_links WHERE link_id = ?", (sl["link_id"],))

            # 2. Transfer documents
            conn.execute(
                "UPDATE event_documents SET event_id = ? WHERE event_id = ?",
                (target_event_id, source_event_id)
            )
            # Move physical files if stored in source directory
            src_doc_dir = self.db_path.parent / "reporting_documents" / source_event_id
            tgt_doc_dir = self.db_path.parent / "reporting_documents" / target_event_id
            if src_doc_dir.exists() and src_doc_dir.is_dir():
                tgt_doc_dir.mkdir(parents=True, exist_ok=True)
                for f in src_doc_dir.iterdir():
                    if f.is_file():
                        tgt_file = tgt_doc_dir / f.name
                        try:
                            f.rename(tgt_file)
                            conn.execute(
                                "UPDATE event_documents SET storage_ref = ? WHERE storage_ref = ?",
                                (str(tgt_file.resolve()), str(f.resolve()))
                            )
                        except Exception:
                            pass
                try:
                    src_doc_dir.rmdir()
                except Exception:
                    pass

            # 3. Transfer facts
            conn.execute(
                "UPDATE event_facts SET event_id = ? WHERE event_id = ?",
                (target_event_id, source_event_id)
            )

            # 4. Merge micro-indicators
            tgt_micros = set()
            try:
                tgt_micros = set(json.loads(target["micro_indicators_json"] or "[]"))
            except Exception:
                pass
            src_micros = set()
            try:
                src_micros = set(json.loads(source["micro_indicators_json"] or "[]"))
            except Exception:
                pass
            merged_micros = list(tgt_micros.union(src_micros))

            # Merge notes
            tgt_notes = target["notes"] or ""
            src_notes = source["notes"] or ""
            combined_notes = tgt_notes
            if src_notes and src_notes not in tgt_notes:
                combined_notes = f"{tgt_notes}\n[ادغام‌شده از {source_event_id}]: {src_notes}".strip()

            new_version = int(target["version"] or 1) + 1
            conn.execute(
                """
                UPDATE reported_events
                SET micro_indicators_json = ?, notes = ?, version = ?
                WHERE event_id = ?
                """,
                (json.dumps(merged_micros, ensure_ascii=False), combined_notes, new_version, target_event_id)
            )

            # 5. Audit log
            self._append_audit(
                conn,
                actor=actor,
                action="event.merge",
                entity_type="event",
                entity_id=target_event_id,
                diff={"merged_source_event_id": source_event_id},
            )

            # 6. Delete source event
            conn.execute("DELETE FROM reporting_review_queue WHERE ref_id = ? AND ref_table = 'reported_events'", (source_event_id,))
            conn.execute("DELETE FROM reported_events WHERE event_id = ?", (source_event_id,))

            return {
                "target_event_id": target_event_id,
                "source_event_id": source_event_id,
                "merged_micro_indicators": merged_micros,
                "new_version": new_version,
            }

        return self._run_in_transaction(_op)

    def get_unit_baseline(self, unit_id: str) -> dict[str, Any]:
        """Fetch baseline statistical profile of a judicial unit."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reporting_unit_baselines WHERE unit_id = ?",
                (unit_id,)
            ).fetchone()
            if row:
                return dict(row)
            return {
                "unit_id": unit_id,
                "staff_count": 0,
                "family_multiplier": 2.5,
                "imams_count": 0,
                "prayer_rooms_count": 0,
                "honored_count": 0,
                "notes": "",
                "updated_at": "",
            }

    def save_unit_baseline(
        self,
        unit_id: str,
        *,
        staff_count: int,
        family_multiplier: float = 2.5,
        imams_count: int = 0,
        prayer_rooms_count: int = 0,
        honored_count: int = 0,
        notes: str = "",
    ) -> dict[str, Any]:
        """Upsert baseline statistical profile of a judicial unit."""
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_unit_baselines (
                    unit_id, staff_count, family_multiplier, imams_count,
                    prayer_rooms_count, honored_count, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(unit_id) DO UPDATE SET
                    staff_count = excluded.staff_count,
                    family_multiplier = excluded.family_multiplier,
                    imams_count = excluded.imams_count,
                    prayer_rooms_count = excluded.prayer_rooms_count,
                    honored_count = excluded.honored_count,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (unit_id, int(staff_count), float(family_multiplier), int(imams_count),
                 int(prayer_rooms_count), int(honored_count), notes, now)
            )
        return {
            "unit_id": unit_id,
            "staff_count": staff_count,
            "family_multiplier": family_multiplier,
            "imams_count": imams_count,
            "prayer_rooms_count": prayer_rooms_count,
            "honored_count": honored_count,
            "notes": notes,
            "updated_at": now,
        }

    def list_unit_baselines(self) -> list[dict[str, Any]]:
        """Fetch all registered unit baseline statistical profiles."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reporting_unit_baselines ORDER BY unit_id").fetchall()
            return [dict(r) for r in rows]

    def normalize_event_statistics(self, event_id: str) -> dict[str, Any]:
        """Calculate participation ratio, expected family turnout, and anomaly flags based on unit baselines."""
        file = self.get_event_file(event_id)
        if not file:
            raise EventNotFoundError(f"event {event_id} not found")

        unit_name = file.get("unit_name") or ""
        unit_scope = file.get("unit") or ""
        unit_id = unit_name or unit_scope
        baseline = self.get_unit_baseline(unit_name) if unit_name else {}
        if not baseline or not baseline.get("staff_count"):
            if unit_scope:
                baseline = self.get_unit_baseline(unit_scope)

        staff_base = int(baseline.get("staff_count") or 0)
        family_mul = float(baseline.get("family_multiplier") or 2.5)

        # Extract attendees from facts
        attendees = 0
        for f in file.get("facts", []):
            if f.get("metric") in {"attendees", "participant_count", "trip_attendees"}:
                try:
                    attendees = int(float(f.get("value", 0)))
                except Exception:
                    pass
                break

        estimated_family_pool = int(staff_base * family_mul) if staff_base > 0 else 0
        total_pool = staff_base + estimated_family_pool

        attendance_rate_staff = round((attendees / staff_base * 100), 1) if staff_base > 0 else None
        attendance_rate_total = round((attendees / total_pool * 100), 1) if total_pool > 0 else None

        anomalies: list[str] = []
        if staff_base > 0 and attendees > (staff_base * 4):
            anomalies.append(f"تعداد شرکت‌کنندگان ({attendees}) بیش از ۴ برابر کل کادر پرسنلی ({staff_base}) است؛ نیازمند بازبینی.")

        return {
            "event_id": event_id,
            "unit_id": unit_id,
            "baseline_staff_count": staff_base,
            "estimated_family_pool": estimated_family_pool,
            "total_pool": total_pool,
            "reported_attendees": attendees,
            "attendance_rate_staff_pct": attendance_rate_staff,
            "attendance_rate_total_pct": attendance_rate_total,
            "anomalies": anomalies,
            "has_anomalies": len(anomalies) > 0,
        }

    def get_staff_reporting_stats(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["(registered_by_id != '' OR created_by != '')"]
        params: list[Any] = []
        if from_date:
            clauses.append("created_at >= ?")
            params.append(from_date)
        if to_date:
            clauses.append("created_at <= ?")
            params.append(to_date)
        where_clause = f"WHERE {' AND '.join(clauses)}"
        sql = f"""
            SELECT
                COALESCE(NULLIF(registered_by_id, ''), created_by) AS staff_id,
                COALESCE(NULLIF(registered_by_name, ''), created_by) AS staff_name,
                COUNT(*) AS total_reports,
                SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) AS approved_reports,
                SUM(CASE WHEN review_status = 'approved' AND revision_count = 0 THEN 1 ELSE 0 END) AS first_time_approved,
                SUM(CASE WHEN revision_count > 0 THEN 1 ELSE 0 END) AS revision_required_reports,
                SUM(CASE WHEN review_status = 'conflict' THEN 1 ELSE 0 END) AS conflict_reports
            FROM reported_events
            {where_clause}
            GROUP BY staff_id, staff_name
            ORDER BY total_reports DESC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            results = []
            for r in rows:
                total = int(r["total_reports"] or 0)
                appr = int(r["approved_reports"] or 0)
                fta = int(r["first_time_approved"] or 0)
                rev = int(r["revision_required_reports"] or 0)
                cnf = int(r["conflict_reports"] or 0)
                appr_rate = round((appr / total * 100.0), 1) if total > 0 else 100.0
                ftr_rate = round((fta / appr * 100.0), 1) if appr > 0 else 100.0
                results.append({
                    "staff_id": str(r["staff_id"] or ""),
                    "staff_name": str(r["staff_name"] or r["staff_id"] or ""),
                    "total_reports": total,
                    "approved_reports": appr,
                    "first_time_approved": fta,
                    "revision_required_reports": rev,
                    "conflict_reports": cnf,
                    "approval_rate": appr_rate,
                    "first_time_right_rate": ftr_rate,
                })
            return results

    # ----------------------------------------------------------------------
    # Filled Forms
    # ----------------------------------------------------------------------
    def save_filled_form(self, form: FilledForm, *, updated_by: str = "") -> None:
        now = _utc_now()
        program_id_str = form.program_id.value if hasattr(form.program_id, "value") else str(form.program_id)
        from .forms import EXTENDED_FORMS_BY_PROGRAM
        title = EXTENDED_FORMS_BY_PROGRAM[program_id_str].title if program_id_str in EXTENDED_FORMS_BY_PROGRAM else program_id_str

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

            raw_pid = row["program_id"]
            prog_id = ProgramId(raw_pid) if raw_pid in {p.value for p in ProgramId} else raw_pid
            return FilledForm(
                program_id=prog_id,
                answers=answers,
            )

    def list_filled_forms(self) -> dict[str, FilledForm]:
        with self._connect() as conn:
            rows = conn.execute("SELECT program_id FROM filled_forms").fetchall()
            result: dict[str, FilledForm] = {}
            for row in rows:
                form = self.get_filled_form(row["program_id"])
                if form:
                    key = form.program_id.value if hasattr(form.program_id, "value") else str(form.program_id)
                    result[key] = form
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
        template_version: str = "1",
        rules_version: str = "1",
        traceability: Mapping[str, Any] | None = None,
        wp_opt_in: bool = False,
    ) -> str:
        export_id = f"exp-{uuid.uuid4().hex[:10]}"
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_exports (
                    export_id, export_path, file_sha256, report_period,
                    province_name, total_events, exported_at, exported_by,
                    template_version, rules_version, traceability_json, wp_opt_in
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    template_version,
                    rules_version,
                    json.dumps(traceability, ensure_ascii=False) if traceability is not None else None,
                    1 if wp_opt_in else 0,
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
    # Registry: Units & Liaisons (حوزه‌های قضایی، شهرستان‌ها و رابطین)
    # ----------------------------------------------------------------------
    def _migrate_and_seed_judicial_units_and_liaisons(self, conn: sqlite3.Connection) -> None:
        """Migrate legacy reporting_units columns and seed default Mazandaran judicial units & liaisons."""
        unit_cols = {row[1] for row in conn.execute("PRAGMA table_info(reporting_units)")}
        if unit_cols:
            if "county" not in unit_cols:
                conn.execute("ALTER TABLE reporting_units ADD COLUMN county TEXT NOT NULL DEFAULT ''")
            if "unit_type" not in unit_cols:
                conn.execute("ALTER TABLE reporting_units ADD COLUMN unit_type TEXT NOT NULL DEFAULT ''")
            if "display_name" not in unit_cols:
                conn.execute("ALTER TABLE reporting_units ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
            if "updated_at" not in unit_cols:
                conn.execute("ALTER TABLE reporting_units ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

        # 1. Backfill legacy rows where county or display_name is empty
        legacy_rows = conn.execute(
            "SELECT unit_id, name, county, unit_type, display_name FROM reporting_units"
        ).fetchall()
        for r in legacy_rows:
            u_id = r["unit_id"]
            name = (r["name"] or "").strip()
            county = (r["county"] or "").strip()
            u_type = (r["unit_type"] or "").strip()
            disp = (r["display_name"] or "").strip()

            if not county:
                for city in (
                    "سوادکوه شمالی", "سوادکوه", "بندپی شرقی", "ساری", "بابل", "آمل", "قائمشهر", "قائم‌شهر", "تنکابن", "چالوس",
                    "نوشهر", "نکا", "بهشهر", "رامسر", "بابلسر", "محمودآباد",
                    "جویبار", "فریدونکنار", "فریدون‌کنار", "گلوگاه",
                    "میاندرود", "میاندورود", "کلاردشت", "سیمرغ", "عباس‌آباد", "عباس آباد", "نور",
                    "زیراب", "پل‌سفید", "چمستان", "دابودشت", "سرخرود", "لاریجان", "چهاردانگه",
                ):
                    if city in name:
                        county = city.replace("قائم‌شهر", "قائمشهر").replace("عباس‌آباد", "عباس آباد").replace("فریدون‌کنار", "فریدونکنار")
                        break
            if not u_type:
                if "اداره کل" in name or "ستاد" in name:
                    u_type = "اداره کل"
                elif "دادسرا" in name:
                    u_type = "دادسرا"
                elif "شورای حل اختلاف" in name:
                    u_type = "شورای حل اختلاف"
                elif "تجدیدنظر" in name:
                    u_type = "دادگاه تجدیدنظر"
                elif "دادگاه عمومی بخش" in name or "دادگاه بخش" in name or "بخش" in name:
                    u_type = "دادگاه عمومی بخش"
                elif "دادگستری" in name:
                    u_type = "دادگستری"
                elif county:
                    u_type = "دادگستری"

            if not disp:
                if county and u_type:
                    disp = f"{county} - {u_type}"
                else:
                    disp = name

            conn.execute(
                "UPDATE reporting_units SET county = ?, unit_type = ?, display_name = ? WHERE unit_id = ?",
                (county, u_type, disp, u_id),
            )

        # 2. Seed standard Mazandaran units and sync official canonical list
        now = _utc_now()
        canonical_display_names = set()
        for c_name, u_type, d_name, kind in _DEFAULT_JUDICIAL_UNITS:
            canonical_display_names.add(d_name)
            existing = conn.execute(
                "SELECT unit_id FROM reporting_units WHERE display_name = ? OR name = ?",
                (d_name, d_name),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE reporting_units SET county = ?, unit_type = ?, display_name = ?, name = ?, kind = ?, updated_at = ? WHERE unit_id = ?",
                    (c_name, u_type, d_name, d_name, kind, now, existing[0]),
                )
            else:
                u_id = f"unit-{uuid.uuid4().hex[:10]}"
                conn.execute(
                    """
                    INSERT INTO reporting_units (
                        unit_id, name, county, unit_type, display_name, kind, source, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'system_seed', '', ?, ?)
                    """,
                    (u_id, d_name, c_name, u_type, d_name, kind, now, now),
                )

        # Prune obsolete system_seed units that are not in the canonical list and have no liaisons
        placeholders = ",".join("?" for _ in canonical_display_names)
        conn.execute(
            f"""
            DELETE FROM reporting_units
            WHERE display_name NOT IN ({placeholders})
              AND name NOT IN ({placeholders})
              AND unit_id NOT IN (SELECT DISTINCT unit_id FROM reporting_liaisons)
            """,
            list(canonical_display_names) + list(canonical_display_names),
        )

        # Deduplicate any duplicate display_names (keep the one linked to liaisons, or the earliest created)
        conn.execute("""
            DELETE FROM reporting_units
            WHERE unit_id IN (
                SELECT u1.unit_id
                FROM reporting_units u1
                JOIN reporting_units u2 ON u1.display_name = u2.display_name AND u1.unit_id != u2.unit_id
                WHERE u1.unit_id NOT IN (SELECT DISTINCT unit_id FROM reporting_liaisons)
                  AND (u2.unit_id IN (SELECT DISTINCT unit_id FROM reporting_liaisons) OR u1.rowid > u2.rowid)
            )
        """)

        # 3. Seed default liaisons if table is empty
        count_liaisons = conn.execute("SELECT COUNT(*) FROM reporting_liaisons").fetchone()[0]
        if count_liaisons == 0:
            default_liaisons = [
                ("قاسمی شورابی", "ساری - اداره کل", "ghasemi_sho", "قاسمی,شورابی", "رابط فرهنگی اداره کل دادگستری استان مازندران"),
                ("دیوسالار", "نور - دادگستری", "divsalar", "دیوسالار", "رابط فرهنگی دادگستری شهرستان نور"),
                ("مهدوی", "سوادکوه - دادگستری", "mahdavi_c", "مهدوی", "رابط فرهنگی دادگستری شهرستان سوادکوه"),
                ("احسانی", "بابل - دادگستری", "ehsani", "احسانی", "رابط فرهنگی دادگستری شهرستان بابل"),
                ("حمید سعیدی", "چهاردانگه - دادگاه عمومی بخش", "saeedi_h", "سعیدی,حمید سعیدی", "رابط فرهنگی دادگاه عمومی بخش چهاردانگه"),
            ]
            for f_name, target_unit_disp, uname, kws, notes in default_liaisons:
                unit_row = conn.execute(
                    "SELECT unit_id FROM reporting_units WHERE display_name = ? OR name = ?",
                    (target_unit_disp, target_unit_disp),
                ).fetchone()
                if unit_row:
                    l_id = f"liaison-{uuid.uuid4().hex[:10]}"
                    conn.execute(
                        """
                        INSERT INTO reporting_liaisons (
                            liaison_id, unit_id, full_name, eitaa_username, eitaa_user_id,
                            sender_key, phone, match_keywords, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, '', '', '', ?, ?, ?, ?)
                        """,
                        (l_id, unit_row["unit_id"], f_name, uname, kws, notes, now, now),
                    )

        # Ensure canonical liaisons exist even if table was already partially populated
        for f_name, target_unit_disp, uname, kws, notes in [
            ("حمید سعیدی", "چهاردانگه - دادگاه عمومی بخش", "saeedi_h", "سعیدی,حمید سعیدی", "رابط فرهنگی دادگاه عمومی بخش چهاردانگه"),
        ]:
            existing_l = conn.execute("SELECT liaison_id FROM reporting_liaisons WHERE full_name = ?", (f_name,)).fetchone()
            if not existing_l:
                unit_row = conn.execute(
                    "SELECT unit_id FROM reporting_units WHERE display_name = ? OR name = ?",
                    (target_unit_disp, target_unit_disp),
                ).fetchone()
                if unit_row:
                    l_id = f"liaison-{uuid.uuid4().hex[:10]}"
                    conn.execute(
                        """
                        INSERT INTO reporting_liaisons (
                            liaison_id, unit_id, full_name, eitaa_username, eitaa_user_id,
                            sender_key, phone, match_keywords, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, '', '', '', ?, ?, ?, ?)
                        """,
                        (l_id, unit_row["unit_id"], f_name, uname, kws, notes, now, now),
                    )

        # Clean up legacy noisy unit/city keywords from default seeded liaisons
        conn.execute("UPDATE reporting_liaisons SET match_keywords = 'قاسمی,شورابی' WHERE full_name = 'قاسمی شورابی' AND match_keywords LIKE '%اداره کل%'")
        conn.execute("UPDATE reporting_liaisons SET match_keywords = 'دیوسالار' WHERE full_name = 'دیوسالار' AND match_keywords LIKE '%نور%'")
        conn.execute("UPDATE reporting_liaisons SET match_keywords = 'مهدوی' WHERE full_name = 'مهدوی' AND match_keywords LIKE '%سوادکوه%'")
        conn.execute("UPDATE reporting_liaisons SET match_keywords = 'احسانی' WHERE full_name = 'احسانی' AND match_keywords LIKE '%بابل%'")

    @staticmethod
    def _row_to_unit(row: sqlite3.Row) -> UnitRecord:
        keys = row.keys()
        created_raw = row["created_at"]
        updated_raw = row["updated_at"] if "updated_at" in keys and row["updated_at"] else created_raw
        return UnitRecord(
            unit_id=row["unit_id"],
            name=row["name"],
            county=row["county"] if "county" in keys and row["county"] else "",
            unit_type=row["unit_type"] if "unit_type" in keys and row["unit_type"] else "",
            display_name=row["display_name"] if "display_name" in keys and row["display_name"] else row["name"],
            kind=row["kind"],
            source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(created_raw) if isinstance(created_raw, str) else created_raw,
            updated_at=datetime.fromisoformat(updated_raw) if isinstance(updated_raw, str) else updated_raw,
        )

    @staticmethod
    def _row_to_liaison(row: sqlite3.Row) -> LiaisonRecord:
        keys = row.keys()
        created_raw = row["created_at"]
        updated_raw = row["updated_at"] if "updated_at" in keys and row["updated_at"] else created_raw
        return LiaisonRecord(
            liaison_id=row["liaison_id"],
            unit_id=row["unit_id"],
            full_name=row["full_name"],
            eitaa_username=row["eitaa_username"] or "",
            eitaa_user_id=row["eitaa_user_id"] or "",
            sender_key=row["sender_key"] or "",
            phone=row["phone"] or "",
            match_keywords=row["match_keywords"] or "",
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(created_raw) if isinstance(created_raw, str) else created_raw,
            updated_at=datetime.fromisoformat(updated_raw) if isinstance(updated_raw, str) else updated_raw,
        )

    def find_unit_by_name(self, name: str) -> UnitRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reporting_units WHERE name = ? OR display_name = ?", (name, name)
            ).fetchone()
            if not row:
                return None
            return self._row_to_unit(row)

    def get_unit(self, unit_id: str) -> UnitRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reporting_units WHERE unit_id = ?", (unit_id,)).fetchone()
            if not row:
                return None
            return self._row_to_unit(row)

    def save_unit(self, unit: UnitRecord) -> UnitRecord:
        unit.validate()
        now = _utc_now()
        with self._connect() as conn:
            existing = None
            if unit.unit_id:
                existing = conn.execute("SELECT unit_id FROM reporting_units WHERE unit_id = ?", (unit.unit_id,)).fetchone()
            if not existing and unit.name:
                existing = conn.execute("SELECT unit_id FROM reporting_units WHERE name = ? OR display_name = ?", (unit.name, unit.name)).fetchone()

            if existing:
                unit.unit_id = str(existing["unit_id"])
                conn.execute(
                    """
                    UPDATE reporting_units
                    SET name = ?, county = ?, unit_type = ?, display_name = ?,
                        kind = ?, source = ?, notes = ?, updated_at = ?
                    WHERE unit_id = ?
                    """,
                    (
                        unit.name,
                        unit.county,
                        unit.unit_type,
                        unit.display_name or unit.name,
                        unit.kind,
                        unit.source.value if hasattr(unit.source, "value") else str(unit.source),
                        unit.notes,
                        now,
                        unit.unit_id,
                    ),
                )
            else:
                if not unit.unit_id:
                    unit.unit_id = f"unit-{uuid.uuid4().hex[:10]}"
                conn.execute(
                    """
                    INSERT INTO reporting_units (
                        unit_id, name, county, unit_type, display_name,
                        kind, source, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(unit_id) DO UPDATE SET
                        name = excluded.name,
                        county = excluded.county,
                        unit_type = excluded.unit_type,
                        display_name = excluded.display_name,
                        kind = excluded.kind,
                        source = excluded.source,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        unit.unit_id,
                        unit.name,
                        unit.county,
                        unit.unit_type,
                        unit.display_name or unit.name,
                        unit.kind,
                        unit.source.value if hasattr(unit.source, "value") else str(unit.source),
                        unit.notes,
                        now,
                        now,
                    ),
                )
        return unit

    def delete_unit(self, unit_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM reporting_liaisons WHERE unit_id = ?", (unit_id,))
            cur = conn.execute("DELETE FROM reporting_units WHERE unit_id = ?", (unit_id,))
            return cur.rowcount > 0

    def list_units(self, *, county: str | None = None) -> list[UnitRecord]:
        with self._connect() as conn:
            if county:
                rows = conn.execute(
                    "SELECT * FROM reporting_units WHERE county = ? ORDER BY display_name, name", (county,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reporting_units ORDER BY county, display_name, name"
                ).fetchall()
            return [self._row_to_unit(row) for row in rows]

    def list_counties(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT county FROM reporting_units WHERE county != '' ORDER BY county"
            ).fetchall()
            return [row["county"] for row in rows]

    # Liaisons (رابطین فرهنگی)
    def save_liaison(self, liaison: LiaisonRecord) -> LiaisonRecord:
        liaison.validate()
        now = _utc_now()
        if not liaison.liaison_id:
            liaison.liaison_id = f"liaison-{uuid.uuid4().hex[:10]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_liaisons (
                    liaison_id, unit_id, full_name, eitaa_username, eitaa_user_id,
                    sender_key, phone, match_keywords, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(liaison_id) DO UPDATE SET
                    unit_id = excluded.unit_id,
                    full_name = excluded.full_name,
                    eitaa_username = excluded.eitaa_username,
                    eitaa_user_id = excluded.eitaa_user_id,
                    sender_key = excluded.sender_key,
                    phone = excluded.phone,
                    match_keywords = excluded.match_keywords,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    liaison.liaison_id,
                    liaison.unit_id,
                    liaison.full_name,
                    liaison.eitaa_username.lstrip("@").strip(),
                    liaison.eitaa_user_id.strip(),
                    liaison.sender_key.strip(),
                    liaison.phone.strip(),
                    liaison.match_keywords.strip(),
                    liaison.notes.strip(),
                    now,
                    now,
                ),
            )
        return liaison

    def get_liaison(self, liaison_id: str) -> LiaisonRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reporting_liaisons WHERE liaison_id = ?", (liaison_id,)).fetchone()
            if not row:
                return None
            return self._row_to_liaison(row)

    def delete_liaison(self, liaison_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM reporting_liaisons WHERE liaison_id = ?", (liaison_id,))
            return cur.rowcount > 0

    def list_liaisons(self, *, unit_id: str | None = None) -> list[LiaisonRecord]:
        with self._connect() as conn:
            if unit_id:
                rows = conn.execute(
                    "SELECT * FROM reporting_liaisons WHERE unit_id = ? ORDER BY full_name", (unit_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reporting_liaisons ORDER BY full_name"
                ).fetchall()
            return [self._row_to_liaison(row) for row in rows]

    def resolve_liaison_and_unit(
        self,
        *,
        sender_key: str = "",
        username: str = "",
        full_name: str = "",
        text: str = "",
    ) -> tuple[LiaisonRecord | None, UnitRecord | None]:
        """Resolve sender/message metadata to an assigned liaison and judicial unit."""
        s_key = sender_key.strip()
        u_name = username.strip().lstrip("@").lower()
        f_name = full_name.strip()
        msg_text = text.strip()

        all_liaisons = self.list_liaisons()
        matched_liaison: LiaisonRecord | None = None

        # 1. Exact sender_key match or numeric/prefixed match
        if s_key:
            clean_s = re.sub(r"^(user:|u:)", "", s_key).strip()
            for l in all_liaisons:
                if l.sender_key:
                    if l.sender_key == s_key:
                        matched_liaison = l
                        break
                    clean_l = re.sub(r"^(user:|u:)", "", l.sender_key).strip()
                    if clean_s and clean_s == clean_l:
                        matched_liaison = l
                        break
                if clean_s and l.eitaa_user_id and str(l.eitaa_user_id).strip() == clean_s:
                    matched_liaison = l
                    break

        # 2. Exact username match
        if not matched_liaison and u_name:
            for l in all_liaisons:
                if l.eitaa_username and l.eitaa_username.lower() == u_name:
                    matched_liaison = l
                    break

        # 3. Full name match (exact or significant substring)
        if not matched_liaison and f_name:
            for l in all_liaisons:
                if l.full_name and (l.full_name == f_name or (len(f_name) >= 3 and f_name in l.full_name)):
                    matched_liaison = l
                    break

        # 4. Check match_keywords on liaisons against sender identity (f_name, u_name, s_key)
        if not matched_liaison:
            sender_identity = f"{f_name} {u_name} {s_key}".lower()
            if sender_identity.strip():
                for l in all_liaisons:
                    if not l.match_keywords:
                        continue
                    kws = [k.strip().lower() for k in re.split(r"[,،\s]+", l.match_keywords) if len(k.strip()) >= 3]
                    for kw in kws:
                        kw_pattern = rf"(?:^|[^\w؀-ۿ]){re.escape(kw)}(?=[^\w؀-ۿ]|$)"
                        if re.search(kw_pattern, sender_identity):
                            matched_liaison = l
                            break
                    if matched_liaison:
                        break

        # 4b. Inspect msg_text for structured header or explicit reporter markers
        if not matched_liaison and msg_text:
            for raw_line in msg_text.splitlines()[:8]:
                line = raw_line.strip()
                if not line:
                    continue
                header_m = re.match(
                    r"^(?:[\s#*•\U00010000-\U0010ffff\u2600-\u26FF]*(?:رابط\s*(?:فرهنگی|خبری)?\s*[:：\-–]?\s*)?)?([^\n–—\-:：]{2,30})\s*[-–—]\s*(?:حوزه\s*قضایی\s*|دادگستری\s*|دادگاه\s*عمومی\s*بخش\s*)?([^\n–—\-]+?)(?:\s*[-–—]\s*([^\n]+))?$",
                    line,
                )
                if header_m:
                    cand_name = header_m.group(1).strip()
                    for l in all_liaisons:
                        if l.full_name and (l.full_name == cand_name or cand_name in l.full_name):
                            matched_liaison = l
                            break
                        if l.match_keywords:
                            kws = [k.strip().lower() for k in re.split(r"[,،\s]+", l.match_keywords) if len(k.strip()) >= 3]
                            for kw in kws:
                                if kw in cand_name.lower():
                                    matched_liaison = l
                                    break
                        if matched_liaison:
                            break
                    if matched_liaison:
                        break

            if not matched_liaison:
                reporter_prefix_match = re.search(
                    r"(?:رابط فرهنگی|گزارشگر|نویسنده|ارسال‌کننده|توسط|از)\s*[:：\-–]?\s*([^\n،,.:]{3,35})",
                    msg_text,
                )
                extracted_author = reporter_prefix_match.group(1).strip() if reporter_prefix_match else ""
                if extracted_author:
                    for l in all_liaisons:
                        if l.full_name and (l.full_name in extracted_author or extracted_author in l.full_name):
                            matched_liaison = l
                            break
                        if l.match_keywords:
                            kws = [k.strip().lower() for k in re.split(r"[,،\s]+", l.match_keywords) if len(k.strip()) >= 3]
                            for kw in kws:
                                kw_pattern = rf"(?:^|[^\w؀-ۿ]){re.escape(kw)}(?=[^\w؀-ۿ]|$)"
                                if re.search(kw_pattern, extracted_author.lower()):
                                    matched_liaison = l
                                    break
                        if matched_liaison:
                            break

        if matched_liaison:
            unit = self.get_unit(matched_liaison.unit_id)
            return (matched_liaison, unit)

        # 5. If no liaison matched, try to infer unit directly from text / f_name
        all_units = self.list_units()
        corpus = f"{f_name} {msg_text}"
        # First check full display_name or name
        for u in all_units:
            if u.display_name and u.display_name in corpus:
                return (None, u)
            if u.name and u.name in corpus:
                return (None, u)

        # Check county + unit_type combination
        for u in all_units:
            if u.county and u.county in corpus:
                if u.unit_type and u.unit_type in corpus:
                    return (None, u)

        # Check county alone (fallback to general or first unit of that county)
        for u in all_units:
            if u.county and u.county in corpus:
                return (None, u)

        return (None, None)

    def _lookup_contact_phone(
        self,
        *,
        user_id: str = "",
        username: str = "",
        full_name: str = "",
    ) -> str:
        """Helper to find matching phone number from local contacts SQLite database if present."""
        contacts_db = Path(__file__).resolve().parents[3] / "data" / "contacts.sqlite3"
        if not contacts_db.exists():
            return ""
        try:
            with sqlite3.connect(contacts_db) as conn:
                cur = conn.cursor()
                if user_id:
                    row = cur.execute(
                        "SELECT p.normalized_phone FROM contacts c JOIN contact_phones p ON c.contact_id = p.contact_id WHERE c.eitaa_user_id = ? AND p.normalized_phone != '' LIMIT 1",
                        (user_id,),
                    ).fetchone()
                    if row and row[0]:
                        return str(row[0])
                if username:
                    clean_u = username.lower().replace("@", "")
                    row = cur.execute(
                        "SELECT p.normalized_phone FROM contacts c JOIN contact_phones p ON c.contact_id = p.contact_id WHERE LOWER(c.username) = ? AND p.normalized_phone != '' LIMIT 1",
                        (clean_u,),
                    ).fetchone()
                    if row and row[0]:
                        return str(row[0])
                if full_name and len(full_name) >= 3:
                    row = cur.execute(
                        "SELECT p.normalized_phone FROM contacts c JOIN contact_phones p ON c.contact_id = p.contact_id WHERE (c.first_name || ' ' || c.last_name) LIKE ? AND p.normalized_phone != '' LIMIT 1",
                        (f"%{full_name}%",),
                    ).fetchone()
                    if row and row[0]:
                        return str(row[0])
        except Exception:
            pass
        return ""

    def find_liaison_by_sender(
        self,
        *,
        sender_key: str = "",
        username: str = "",
        user_id: str = "",
        full_name: str = "",
    ) -> tuple[LiaisonRecord | None, UnitRecord | None]:
        """Find a designated liaison record by sender attributes."""
        s_key = sender_key.strip()
        u_name = username.strip().lower().replace("@", "")
        u_id = user_id.strip()
        f_name = full_name.strip()
        all_liaisons = self.list_liaisons()

        # 1. Exact sender_key match
        if s_key:
            for l in all_liaisons:
                if l.sender_key and (l.sender_key == s_key or l.sender_key.replace("u:", "") == s_key.replace("u:", "")):
                    unit = self.get_unit(l.unit_id)
                    return (l, unit)

        # 2. Exact user_id match
        if u_id:
            for l in all_liaisons:
                if l.eitaa_user_id and (l.eitaa_user_id == u_id or l.sender_key == f"u:{u_id}"):
                    unit = self.get_unit(l.unit_id)
                    return (l, unit)

        # 3. Exact username match
        if u_name:
            for l in all_liaisons:
                if l.eitaa_username and l.eitaa_username.lower().replace("@", "") == u_name:
                    unit = self.get_unit(l.unit_id)
                    return (l, unit)

        # 4. Full name match
        if f_name:
            for l in all_liaisons:
                if l.full_name and (l.full_name == f_name or (len(f_name) >= 3 and f_name in l.full_name)):
                    unit = self.get_unit(l.unit_id)
                    return (l, unit)

        return (None, None)

    def assign_author_as_liaison(
        self,
        *,
        unit_id: str,
        full_name: str,
        sender_key: str = "",
        eitaa_username: str = "",
        eitaa_user_id: str = "",
        phone: str = "",
        notes: str = "",
        match_keywords: str = "",
    ) -> tuple[LiaisonRecord, UnitRecord]:
        """Designate or update an author as a cultural liaison for a judicial unit."""
        unit = self.get_unit(unit_id)
        if not unit:
            raise ValueError(f"Judicial unit with ID '{unit_id}' not found.")

        clean_name = full_name.strip()
        clean_user = eitaa_username.strip().replace("@", "")
        clean_key = sender_key.strip()
        clean_uid = eitaa_user_id.strip()
        clean_phone = phone.strip()

        # If phone is not provided, try to discover it from local contacts
        if not clean_phone:
            discovered_phone = self._lookup_contact_phone(user_id=clean_uid, username=clean_user, full_name=clean_name)
            if discovered_phone:
                clean_phone = discovered_phone

        existing_liaison, _ = self.find_liaison_by_sender(
            sender_key=clean_key,
            username=clean_user,
            user_id=clean_uid,
            full_name=clean_name,
        )

        now = _utc_now()
        if existing_liaison:
            existing_liaison.unit_id = unit_id
            if clean_name:
                existing_liaison.full_name = clean_name
            if clean_key:
                existing_liaison.sender_key = clean_key
            if clean_user:
                existing_liaison.eitaa_username = clean_user
            if clean_uid:
                existing_liaison.eitaa_user_id = clean_uid
            if clean_phone:
                existing_liaison.phone = clean_phone
            if notes:
                existing_liaison.notes = notes
            if match_keywords:
                existing_liaison.match_keywords = match_keywords
            existing_liaison.updated_at = now
            saved = self.save_liaison(existing_liaison)
            return (saved, unit)
        else:
            new_id = f"liaison-{uuid.uuid4().hex[:10]}"
            new_liaison = LiaisonRecord(
                liaison_id=new_id,
                unit_id=unit_id,
                full_name=clean_name or (f"@{clean_user}" if clean_user else f"کاربر {clean_uid or clean_key}"),
                eitaa_username=clean_user,
                eitaa_user_id=clean_uid,
                sender_key=clean_key,
                phone=clean_phone,
                match_keywords=match_keywords or clean_name,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
            saved = self.save_liaison(new_liaison)
            return (saved, unit)

    def unlink_author_liaison(
        self,
        *,
        sender_key: str = "",
        liaison_id: str = "",
    ) -> bool:
        """Unlink/remove a cultural liaison record by liaison_id or sender_key."""
        target_id = liaison_id.strip()
        if not target_id and sender_key.strip():
            existing, _ = self.find_liaison_by_sender(sender_key=sender_key)
            if existing:
                target_id = existing.liaison_id

        if not target_id:
            return False
        return self.delete_liaison(target_id)

    def sync_liaison_to_eitaa_contact(
        self,
        liaison_id: str,
        *,
        phone: str = "",
        bridge_api: Any = None,
    ) -> dict[str, Any]:
        """Register or update a cultural liaison as an Eitaa contact with their standardized name."""
        liaison = self.get_liaison(liaison_id)
        if not liaison:
            raise ValueError(f"رابط فرهنگی با شناسه '{liaison_id}' یافت نشد.")

        unit = self.get_unit(liaison.unit_id) if liaison.unit_id else None
        unit_name = (unit.display_name if unit else liaison.unit_display_name or "").strip()

        # Resolve phone
        selected_phone = (phone or liaison.phone or "").strip()
        if not selected_phone:
            selected_phone = self._lookup_contact_phone(
                user_id=liaison.eitaa_user_id,
                username=liaison.eitaa_username,
                full_name=liaison.full_name,
            )
        if not selected_phone:
            raise ValueError("شماره تماس برای این رابط یافت نشد. لطفاً شماره تلفن را وارد کنید.")

        from ..infrastructure.contact_store import SQLiteContactStore, normalize_phone
        try:
            selected_phone = normalize_phone(selected_phone)
        except Exception:
            pass

        # Update phone in liaison record if it was discovered or passed anew
        if selected_phone and liaison.phone != selected_phone:
            liaison.phone = selected_phone
            self.save_liaison(liaison)

        # Standardized naming per user specification:
        # مثلاً حامد باباجانی - رابط فرهنگی فلان جا
        if unit_name:
            contact_display_name = f"{liaison.full_name.strip()} - رابط فرهنگی {unit_name}".strip()
            first_name = liaison.full_name.strip()
            last_name = f"- رابط فرهنگی {unit_name}".strip()
        else:
            contact_display_name = f"{liaison.full_name.strip()} - رابط فرهنگی".strip()
            first_name = liaison.full_name.strip()
            last_name = "- رابط فرهنگی"

        # 1. Update / Upsert in local contacts SQLite database
        resolved_db = Path(self.db_path).resolve()
        if "data" in resolved_db.parts and (resolved_db.parent.parent / "contacts.sqlite3").exists():
            contacts_db = resolved_db.parent.parent / "contacts.sqlite3"
        elif (resolved_db.parent / "contacts.sqlite3").exists():
            contacts_db = resolved_db.parent / "contacts.sqlite3"
        elif (resolved_db.parent.parent / "contacts.sqlite3").exists():
            contacts_db = resolved_db.parent.parent / "contacts.sqlite3"
        else:
            contacts_db = resolved_db.parent / "contacts.sqlite3"
        contacts_db.parent.mkdir(parents=True, exist_ok=True)

        from ..infrastructure.contact_store import SQLiteContactStore
        contact_store = SQLiteContactStore(contacts_db)
        contact_store.initialize()

        e_uid = int(liaison.eitaa_user_id.strip()) if liaison.eitaa_user_id and liaison.eitaa_user_id.strip().isdigit() else None
        contact_payload = {
            "first_name": first_name,
            "last_name": last_name,
            "phones": [selected_phone],
            "username": liaison.eitaa_username.lstrip("@").strip() if liaison.eitaa_username else "",
            "eitaa_user_id": e_uid,
            "source": "cultural_liaison",
            "sendable": True,
        }
        local_contact = contact_store.upsert_contact(contact_payload, duplicate_policy="update")

        # 2. Push to live Eitaa messenger if available
        eitaa_synced = False
        eitaa_error = None
        if bridge_api is not None and hasattr(bridge_api, "_eitaa_contacts_add"):
            try:
                bridge_api._eitaa_contacts_add({
                    "phone": selected_phone,
                    "first_name": first_name,
                    "last_name": last_name,
                    "save_local": True,
                })
                eitaa_synced = True
            except Exception as exc:
                eitaa_error = str(exc)

        return {
            "ok": True,
            "liaison_id": liaison.liaison_id,
            "full_name": liaison.full_name,
            "unit_display_name": unit_name,
            "contact_display_name": contact_display_name,
            "first_name": first_name,
            "last_name": last_name,
            "phone": selected_phone,
            "local_contact_id": local_contact.get("id"),
            "eitaa_synced": eitaa_synced,
            "eitaa_error": eitaa_error,
            "message": f"رابط فرهنگی «{liaison.full_name}» با موفقیت با عنوان «{contact_display_name}» در مخاطبین ایتا ثبت گردید.",
        }

    def sync_all_liaisons_to_eitaa_contacts(
        self,
        *,
        bridge_api: Any = None,
    ) -> dict[str, Any]:
        """Sync all cultural liaisons with a phone number to Eitaa contacts with their standardized title."""
        all_liaisons = self.list_liaisons()
        synced: list[dict[str, Any]] = []
        skipped_no_phone: list[dict[str, Any]] = []

        for l in all_liaisons:
            try:
                res = self.sync_liaison_to_eitaa_contact(l.liaison_id, bridge_api=bridge_api)
                synced.append(res)
            except ValueError as ve:
                unit = self.get_unit(l.unit_id) if l.unit_id else None
                skipped_no_phone.append({
                    "liaison_id": l.liaison_id,
                    "full_name": l.full_name,
                    "unit_display_name": unit.display_name if unit else (l.unit_display_name or ""),
                    "reason": str(ve),
                })
            except Exception as exc:
                skipped_no_phone.append({
                    "liaison_id": l.liaison_id,
                    "full_name": l.full_name,
                    "unit_display_name": l.unit_display_name or "",
                    "reason": str(exc),
                })

        return {
            "ok": True,
            "total": len(all_liaisons),
            "synced_count": len(synced),
            "skipped_count": len(skipped_no_phone),
            "synced": synced,
            "skipped": skipped_no_phone,
            "message": f"{len(synced)} رابط فرهنگی با عنوان رسمی در مخاطبین ایتا ثبت شدند. ({len(skipped_no_phone)} بدون تلفن رد شدند)",
        }

    def get_liaison_profile_analytics(
        self,
        *,
        liaison_id: str = "",
        unit_id: str = "",
        sender_key: str = "",
        user_id: str = "",
        username: str = "",
        full_name: str = "",
        days: int = 365,
    ) -> dict[str, Any]:
        """Aggregate activities, message counts, topic frequencies, and judicial unit comparison."""
        liaison: LiaisonRecord | None = None
        unit: UnitRecord | None = None

        if liaison_id.strip():
            liaison = self.get_liaison(liaison_id.strip())
            if liaison:
                unit = self.get_unit(liaison.unit_id)

        if not liaison:
            liaison, unit = self.find_liaison_by_sender(
                sender_key=sender_key,
                username=username,
                user_id=user_id,
                full_name=full_name,
            )

        if not unit and unit_id.strip():
            unit = self.get_unit(unit_id.strip())

        now_dt = datetime.now(timezone.utc)
        cutoff_dt = now_dt - timedelta(days=max(1, int(days)))
        cutoff_date = cutoff_dt.strftime("%Y-%m-%d")
        cutoff_iso = cutoff_dt.isoformat()

        # Format display title per Requirement 4
        liaison_name = liaison.full_name if liaison else (full_name.strip() or username.strip() or "کاربر نامشخص")
        unit_display_name = unit.display_name if unit else ""
        if liaison and unit_display_name:
            display_title = f"{liaison_name} - حوزه قضایی {unit_display_name}"
        elif unit_display_name:
            display_title = f"حوزه قضایی {unit_display_name}"
        else:
            display_title = liaison_name

        # 1. Messages analytics from data/eitaa_messages.sqlite3
        total_messages = 0
        monthly_messages: list[dict[str, Any]] = []
        messages_db = Path(__file__).resolve().parents[3] / "data" / "eitaa_messages.sqlite3"
        clean_uid_int = None
        raw_uid = user_id.strip() or (liaison.eitaa_user_id if liaison else "")
        if not raw_uid and sender_key.strip():
            match_uid = re.search(r"\d+", sender_key)
            if match_uid:
                raw_uid = match_uid.group(0)
        if raw_uid and raw_uid.isdigit():
            clean_uid_int = int(raw_uid)

        if clean_uid_int is not None and messages_db.exists():
            try:
                with sqlite3.connect(messages_db) as mconn:
                    mcur = mconn.cursor()
                    mrow = mcur.execute(
                        "SELECT COUNT(*) FROM messages WHERE from_peer_id = ? AND date_utc >= ?",
                        (clean_uid_int, cutoff_iso),
                    ).fetchone()
                    total_messages = int(mrow[0]) if mrow else 0

                    monthly_rows = mcur.execute(
                        """
                        SELECT SUBSTR(date_utc, 1, 7) as ym, COUNT(*)
                        FROM messages
                        WHERE from_peer_id = ? AND date_utc >= ?
                        GROUP BY ym
                        ORDER BY ym ASC
                        """,
                        (clean_uid_int, cutoff_iso),
                    ).fetchall()
                    monthly_messages = [{"period": r[0], "count": int(r[1])} for r in monthly_rows]
            except Exception:
                pass

        # 2. Reports analytics from reporting_v3.db
        total_reports = 0
        reports_by_status = {"approved": 0, "needs_review": 0, "draft": 0, "rejected": 0}
        topic_frequency: list[dict[str, Any]] = []
        unit_total_reports = 0
        unit_topic_frequency: list[dict[str, Any]] = []
        recent_reports: list[dict[str, Any]] = []

        with self._connect() as conn:
            # Query liaison reports
            liaison_filter_sql = ""
            liaison_params: list[Any] = [cutoff_date]
            if liaison:
                conds = ["registered_by_id = ?", "registered_by_name = ?", "created_by = ?"]
                liaison_params.extend([liaison.liaison_id, liaison.full_name, liaison.full_name])
                if liaison.eitaa_username:
                    conds.append("created_by = ?")
                    liaison_params.append(liaison.eitaa_username)
                liaison_filter_sql = f"AND ({' OR '.join(conds)})"
            elif clean_name := full_name.strip():
                liaison_filter_sql = "AND (registered_by_name = ? OR created_by = ?)"
                liaison_params.extend([clean_name, clean_name])

            if liaison_filter_sql:
                # Count and status
                status_rows = conn.execute(
                    f"""
                    SELECT COALESCE(review_status, 'draft') as st, COUNT(*)
                    FROM reported_events
                    WHERE occurred_on >= ? {liaison_filter_sql}
                    GROUP BY st
                    """,
                    liaison_params,
                ).fetchall()
                for st_name, st_count in status_rows:
                    total_reports += int(st_count)
                    reports_by_status[str(st_name)] = int(st_count)

                # Topics frequency
                topic_rows = conn.execute(
                    f"""
                    SELECT COALESCE(NULLIF(occasion, ''), NULLIF(macro_category, ''), 'عمومی') as topic, COUNT(*) as cnt
                    FROM reported_events
                    WHERE occurred_on >= ? {liaison_filter_sql}
                    GROUP BY topic
                    ORDER BY cnt DESC
                    """,
                    liaison_params,
                ).fetchall()
                for t_name, t_count in topic_rows:
                    pct = round((int(t_count) / total_reports * 100), 1) if total_reports > 0 else 0.0
                    topic_frequency.append({"topic": str(t_name), "count": int(t_count), "percentage": pct})

                # Recent reports
                rec_rows = conn.execute(
                    f"""
                    SELECT event_id, occurred_on, occasion, review_status, unit_name
                    FROM reported_events
                    WHERE occurred_on >= ? {liaison_filter_sql}
                    ORDER BY occurred_on DESC, created_at DESC
                    LIMIT 5
                    """,
                    liaison_params,
                ).fetchall()
                for r in rec_rows:
                    recent_reports.append({
                        "event_id": str(r[0]),
                        "occurred_on": str(r[1]),
                        "occasion": str(r[2] or "بدون عنوان"),
                        "review_status": str(r[3] or "draft"),
                        "unit_name": str(r[4] or ""),
                    })

            # Unit analytics
            if unit:
                unit_conds = ["unit = ?", "unit = ?", "unit_name = ?", "unit_name = ?"]
                unit_params = [cutoff_date, unit.display_name, unit.unit_id, unit.display_name, unit.name]
                unit_topic_rows = conn.execute(
                    f"""
                    SELECT COALESCE(NULLIF(occasion, ''), NULLIF(macro_category, ''), 'عمومی') as topic, COUNT(*) as cnt
                    FROM reported_events
                    WHERE occurred_on >= ? AND ({' OR '.join(unit_conds)})
                    GROUP BY topic
                    ORDER BY cnt DESC
                    """,
                    unit_params,
                ).fetchall()
                for ut_name, ut_count in unit_topic_rows:
                    unit_total_reports += int(ut_count)
                for ut_name, ut_count in unit_topic_rows:
                    u_pct = round((int(ut_count) / unit_total_reports * 100), 1) if unit_total_reports > 0 else 0.0
                    unit_topic_frequency.append({"topic": str(ut_name), "count": int(ut_count), "percentage": u_pct})

        unit_participation_percentage = round((total_reports / unit_total_reports * 100), 1) if unit_total_reports > 0 else 0.0

        return {
            "liaison": liaison.to_dict() if liaison else None,
            "unit": unit.to_dict() if unit else None,
            "liaison_name": liaison_name,
            "unit_display_name": unit_display_name,
            "display_title": display_title,
            "is_liaison": liaison is not None,
            "time_window_days": days,
            "messages_count": total_messages,
            "monthly_messages": monthly_messages,
            "reports_count": total_reports,
            "reports_by_status": reports_by_status,
            "topic_frequency": topic_frequency,
            "unit_total_reports": unit_total_reports,
            "unit_participation_percentage": unit_participation_percentage,
            "unit_topic_frequency": unit_topic_frequency,
            "recent_reports": recent_reports,
        }

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

    def delete_imam(self, imam_id: str) -> bool:
        """Delete a congregation imam from registry."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM registry_imams WHERE imam_id = ?", (imam_id,))
            return cur.rowcount > 0

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

    def delete_venue(self, venue_id: str) -> bool:
        """Delete a prayer venue from registry."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM registry_venues WHERE venue_id = ?", (venue_id,))
            return cur.rowcount > 0

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

            _CHOICE_ALIASES = {
                "همیشه": "always", "مرتب": "always", "به صورت مرتب": "regular", "گاهی": "sometimes",
                "به ندرت": "rarely", "خیر": "none", "زیاد": "high", "بالا": "high", "متوسط": "medium",
                "کم": "low", "پایین": "low", "شاغل": "staff_cleric", "مدعو": "invited_external",
            }
            if definition.unit == "choice":
                if coded_value not in definition.choices:
                    normalized = _CHOICE_ALIASES.get(coded_value.strip())
                    if normalized and normalized in definition.choices:
                        coded_value = normalized
                    else:
                        raise ReportingStoreError(f"{coded_value!r} is not a choice of {metric_key!r}.")

            if metric_key == "imam_record":
                raw_text = row["raw_text"] or ""
                parts = [p.strip() for p in raw_text.split("|")]
                full_name = coded_value or (parts[0] if parts else row["proposed_value"] or "")
                position = parts[1] if len(parts) > 1 else ""
                source_kind = parts[2] if len(parts) > 2 else "staff_cleric"
                if source_kind not in {"none", "staff_cleric", "invited_external"}:
                    source_kind = "staff_cleric"
                unit_name = row["unit_name"] or ""
                unit_id = f"unit:{unit_name}" if unit_name else ""
                imam_record = ImamRecord(
                    imam_id=f"imam-{uuid.uuid4().hex[:10]}",
                    unit_id=unit_id,
                    full_name=full_name,
                    position=position,
                    source_kind=source_kind,
                    notes=raw_text,
                    evidence_refs=(row["source_ref"],) if row["source_ref"] else (),
                )
                self.save_imam(imam_record)

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
                    plan_id, period, section, strategy, title, plan_type, action_class,
                    targets_json, campaign_tag, mandate_ids_json, needs_confirmation, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id, period) DO UPDATE SET
                    section = excluded.section,
                    strategy = excluded.strategy,
                    title = excluded.title,
                    plan_type = excluded.plan_type,
                    action_class = excluded.action_class,
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
                    item.action_class,
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
                    action_class=(row["action_class"] or "") if "action_class" in row.keys() else "",
                    targets=json.loads(row["targets_json"]),
                    campaign_tag=row["campaign_tag"] or "",
                    mandate_ids=tuple(json.loads(row["mandate_ids_json"])),
                    needs_confirmation=bool(row["needs_confirmation"]),
                    notes=row["notes"] or "",
                )
                for row in rows
            ]

    def seed_default_plans(self, plans: Sequence[PlanItem] | None = None) -> int:
        from .plans import ALL_PLANS_1405
        items = plans if plans is not None else ALL_PLANS_1405
        count = 0
        for item in items:
            self.save_plan_item(item)
            count += 1
        return count

    def save_mandate(self, mandate: Mandate) -> None:
        mandate.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mandates (
                    mandate_id, kind, title, number, issued_on, document_ref, notes, program_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mandate_id) DO UPDATE SET
                    kind = excluded.kind,
                    title = excluded.title,
                    number = excluded.number,
                    issued_on = excluded.issued_on,
                    document_ref = excluded.document_ref,
                    notes = excluded.notes,
                    program_code = excluded.program_code
                """,
                (
                    mandate.mandate_id,
                    mandate.kind,
                    mandate.title,
                    mandate.number,
                    mandate.issued_on,
                    mandate.document_ref,
                    mandate.notes,
                    mandate.program_code,
                    now,
                ),
            )

    def list_mandates(self, *, program_code: str | None = None) -> list[Mandate]:
        with self._connect() as conn:
            if program_code:
                rows = conn.execute(
                    "SELECT * FROM mandates WHERE program_code = ? ORDER BY created_at",
                    (program_code,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM mandates ORDER BY program_code, created_at").fetchall()
            return [
                Mandate(
                    mandate_id=row["mandate_id"],
                    kind=row["kind"],
                    title=row["title"] or "",
                    number=row["number"] or "",
                    issued_on=row["issued_on"] or "",
                    document_ref=row["document_ref"] or "",
                    notes=row["notes"] or "",
                    program_code=row["program_code"] if "program_code" in row.keys() else "",
                )
                for row in rows
            ]

    def delete_mandate(self, mandate_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM mandates WHERE mandate_id = ?", (mandate_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Questionnaire definitions projection (F-095): shared with the portal
    # ----------------------------------------------------------------------
    def list_form_definitions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM form_definitions ORDER BY program_code").fetchall()
            return [dict(row) for row in rows]

    def get_form_definition(self, program_code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM form_definitions WHERE program_code = ?", (program_code.strip(),)
            ).fetchone()
            return dict(row) if row else None

    # ----------------------------------------------------------------------
    # Section Registry (data-driven report axes, F-088 section 4)
    # ----------------------------------------------------------------------
    def list_sections(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reporting_sections ORDER BY source, section_id"
            ).fetchall()
            return [
                {
                    "section_id": row["section_id"],
                    "title": row["title"],
                    "source": row["source"],
                    "workbook_code": row["workbook_code"],
                    "workbook_sheet": row["workbook_sheet"],
                    "visit_label": row["visit_label"],
                    "kinds": json.loads(row["kinds_json"]),
                    "notes": row["notes"] or "",
                }
                for row in rows
            ]

    def upsert_section(self, *, section_id: str, title: str, source: str,
                       workbook_code: str = "", workbook_sheet: str = "",
                       visit_label: str = "", kinds: Sequence[str] = (),
                       notes: str = "") -> None:
        """Operator-defined section (adds new topics; canonical seeds keep ids)."""
        from .sections import SECTION_SOURCES

        if not section_id.strip() or not title.strip():
            raise ReportingStoreError("Section id and title cannot be empty.")
        if source not in SECTION_SOURCES:
            raise ReportingStoreError(f"Unknown section source: {source!r}")
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_sections (
                    section_id, title, source, workbook_code, workbook_sheet,
                    visit_label, kinds_json, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(section_id) DO UPDATE SET
                    title = excluded.title, source = excluded.source,
                    workbook_code = excluded.workbook_code,
                    workbook_sheet = excluded.workbook_sheet,
                    visit_label = excluded.visit_label,
                    kinds_json = excluded.kinds_json,
                    notes = excluded.notes
                """,
                (
                    section_id, title, source, workbook_code, workbook_sheet,
                    visit_label, json.dumps(list(kinds), ensure_ascii=False),
                    notes, now,
                ),
            )

    # ----------------------------------------------------------------------
    # Person Registry (employees + families; PII stays local by design)
    # ----------------------------------------------------------------------
    def save_person(self, person: PersonRecord) -> None:
        person.validate()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_persons (
                    person_id, kind, full_name, personnel_no, national_id, phone,
                    relation, related_personnel_no, unit_id, gender, birth_year,
                    evidence_refs_json, version, source, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    kind = excluded.kind,
                    full_name = excluded.full_name,
                    personnel_no = excluded.personnel_no,
                    national_id = excluded.national_id,
                    phone = excluded.phone,
                    relation = excluded.relation,
                    related_personnel_no = excluded.related_personnel_no,
                    unit_id = excluded.unit_id,
                    gender = excluded.gender,
                    birth_year = excluded.birth_year,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source = excluded.source,
                    notes = excluded.notes,
                    version = registry_persons.version + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    person.person_id,
                    person.kind,
                    person.full_name,
                    person.personnel_no,
                    person.national_id,
                    person.phone,
                    person.relation,
                    person.related_personnel_no,
                    person.unit_id,
                    person.gender,
                    person.birth_year,
                    json.dumps(list(person.evidence_refs), ensure_ascii=False),
                    person.version,
                    person.source.value,
                    person.notes,
                    now,
                    now,
                ),
            )

    def list_persons(self, *, kind: str | None = None, personnel_no: str | None = None,
                     unit_id: str | None = None) -> list[PersonRecord]:
        query = "SELECT * FROM registry_persons"
        clauses: list[str] = []
        params: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if personnel_no:
            clauses.append("personnel_no = ? OR related_personnel_no = ?")
            params.extend([personnel_no, personnel_no])
        if unit_id:
            clauses.append("unit_id = ?")
            params.append(unit_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                PersonRecord(
                    person_id=row["person_id"],
                    kind=row["kind"],
                    full_name=row["full_name"] or "",
                    personnel_no=row["personnel_no"] or "",
                    national_id=row["national_id"] or "",
                    phone=row["phone"] or "",
                    relation=row["relation"] or "",
                    related_personnel_no=row["related_personnel_no"] or "",
                    unit_id=row["unit_id"] or "",
                    gender=row["gender"] or "",
                    birth_year=row["birth_year"] or "",
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                    version=row["version"],
                    source=ValueSource(row["source"]) if row["source"] in {s.value for s in ValueSource} else ValueSource.MANUAL,
                    notes=row["notes"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    def person_family(self, personnel_no: str) -> list[PersonRecord]:
        """Family members related to one employee's personnel number."""
        return self.list_persons(kind="family", personnel_no=personnel_no)

    def delete_person(self, person_id: str) -> bool:
        """Delete a person (employee or family member) from registry."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM registry_persons WHERE person_id = ?", (person_id,))
            return cur.rowcount > 0

    # ----------------------------------------------------------------------
    # WordPress post links (post to event, F-088 section 2)
    # ----------------------------------------------------------------------
    def save_wp_link(self, link: WpPostLink) -> str:
        """Insert a post link; duplicate slugs return the existing link id."""
        link.validate()
        now = _utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT link_id FROM wp_post_links WHERE post_slug = ?",
                (link.post_slug,),
            ).fetchone()
            if existing:
                return str(existing["link_id"])
            link_id = link.link_id or f"wplink-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO wp_post_links (
                    link_id, post_slug, title, source_ref, section, published_on,
                    event_id, match_status, confidence, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    link.post_slug,
                    link.title,
                    link.source_ref,
                    link.section,
                    link.published_on.isoformat() if link.published_on else None,
                    link.event_id,
                    link.match_status,
                    link.confidence,
                    link.note,
                    now,
                ),
            )
            return link_id

    def link_wp_post_to_event(self, link_id: str, event_id: str, *,
                              match_status: str = "confirmed") -> None:
        """Attach an imported event to a post; status auto or confirmed only."""
        if match_status not in {"auto", "confirmed"}:
            raise ReportingStoreError(f"Invalid link status: {match_status!r}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE wp_post_links SET event_id = ?, match_status = ? WHERE link_id = ?",
                (event_id, match_status, link_id),
            )

    def list_wp_links(self, *, status: str | None = None, section: str | None = None,
                      limit: int = 500) -> list[dict[str, Any]]:
        query = "SELECT * FROM wp_post_links"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("match_status = ?")
            params.append(status)
        if section:
            clauses.append("section = ?")
            params.append(section)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ----------------------------------------------------------------------
    # Operational Program Catalog & Indicators (F-128)
    # ----------------------------------------------------------------------
    def list_program_catalog(
        self,
        *,
        year: int | None = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        """List operational program catalog items, optionally filtered by year and active status."""
        with self._connect() as conn:
            query = "SELECT * FROM reporting_program_catalog WHERE 1=1"
            params: list[Any] = []
            if not include_inactive:
                query += " AND is_active = 1"
            if year is not None:
                query += " AND valid_from_year <= ? AND (valid_to_year IS NULL OR valid_to_year >= ?)"
                params.extend([year, year])
            query += " ORDER BY display_order ASC, program_code ASC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_program_by_code(self, program_code: str, *, year: int | None = None) -> dict[str, Any] | None:
        """Retrieve a program catalog row by program_code."""
        clean_code = program_code.strip()
        with self._connect() as conn:
            query = "SELECT * FROM reporting_program_catalog WHERE program_code = ?"
            params: list[Any] = [clean_code]
            if year is not None:
                query += " AND valid_from_year <= ? AND (valid_to_year IS NULL OR valid_to_year >= ?)"
                params.extend([year, year])
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def save_program_catalog_item(
        self,
        program_code: str,
        title: str,
        canonical_macro: str = "",
        kind: str = "custom",
        workbook_sheet: str = "",
        valid_from_year: int = 1403,
        valid_to_year: int | None = None,
        is_active: bool = True,
        display_order: int = 0,
        description: str = "",
    ) -> dict[str, Any]:
        """Create or update an operational program catalog entry."""
        clean_code = program_code.strip()
        clean_title = title.strip()
        clean_macro = canonical_macro.strip() or clean_title
        if not clean_code:
            raise ValueError("کد برنامه نمی‌تواند خالی باشد.")
        if not clean_title:
            raise ValueError("عنوان برنامه نمی‌تواند خالی باشد.")
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_program_catalog (
                    program_code, title, canonical_macro, kind, workbook_sheet,
                    valid_from_year, valid_to_year, is_active, display_order,
                    description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(program_code) DO UPDATE SET
                    title = excluded.title,
                    canonical_macro = excluded.canonical_macro,
                    kind = excluded.kind,
                    workbook_sheet = excluded.workbook_sheet,
                    valid_from_year = excluded.valid_from_year,
                    valid_to_year = excluded.valid_to_year,
                    is_active = excluded.is_active,
                    display_order = excluded.display_order,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (
                    clean_code,
                    clean_title,
                    clean_macro,
                    kind.strip() or "custom",
                    workbook_sheet.strip(),
                    valid_from_year,
                    valid_to_year,
                    1 if is_active else 0,
                    display_order,
                    description.strip(),
                    now,
                    now,
                ),
            )
        return self.get_program_by_code(clean_code) or {}

    def toggle_program_active(self, program_code: str, is_active: bool) -> dict[str, Any]:
        """Soft-deprecate or re-activate an operational program code without corrupting historical data."""
        clean_code = program_code.strip()
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE reporting_program_catalog SET is_active = ?, updated_at = ? WHERE program_code = ?",
                (1 if is_active else 0, now, clean_code),
            )
            if cur.rowcount == 0:
                raise KeyError(f"برنامه‌ای با کد {clean_code} یافت نشد.")
        return self.get_program_by_code(clean_code) or {}

    def list_macro_indicators(self, *, year: int | None = None) -> list[str]:
        """List active canonical macro indicators dynamically sourced from the program catalog."""
        try:
            programs = self.list_program_catalog(year=year, include_inactive=False)
            if programs:
                seen = set()
                result = []
                for p in programs:
                    macro = (p.get("canonical_macro") or p.get("title") or "").strip()
                    if macro and macro not in seen:
                        seen.add(macro)
                        result.append(macro)
                if result:
                    return result
        except Exception:
            pass
        return list(MACRO_INDICATORS)

    def list_micro_indicators(self) -> list[dict[str, Any]]:
        """List all registered micro indicators."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT indicator_id, title, category, color, usage_count, created_at, updated_at "
                "FROM reporting_micro_indicators ORDER BY usage_count DESC, title ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def save_micro_indicator(self, title: str, category: str = "", color: str = "") -> dict[str, Any]:
        """Create or return an existing micro indicator."""
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("عنوان شاخصه جزئی نمی‌تواند خالی باشد.")
        now = _utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT indicator_id, title, category, color, usage_count, created_at, updated_at "
                "FROM reporting_micro_indicators WHERE title = ?",
                (clean_title,),
            ).fetchone()
            if existing:
                return dict(existing)
            ind_id = f"ind-micro-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """
                INSERT INTO reporting_micro_indicators (
                    indicator_id, title, category, color, usage_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (ind_id, clean_title, category.strip(), color.strip(), now, now),
            )
            return {
                "indicator_id": ind_id,
                "title": clean_title,
                "category": category.strip(),
                "color": color.strip(),
                "usage_count": 0,
                "created_at": now,
                "updated_at": now,
            }

    def update_micro_indicator(self, indicator_id: str, title: str | None = None,
                               category: str | None = None, color: str | None = None) -> dict[str, Any]:
        """Update/rename a micro indicator."""
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reporting_micro_indicators WHERE indicator_id = ?",
                (indicator_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"شاخصه جزئی با شناسه {indicator_id} یافت نشد.")
            new_title = title.strip() if title is not None else row["title"]
            new_cat = category.strip() if category is not None else row["category"]
            new_clr = color.strip() if color is not None else row["color"]
            conn.execute(
                """
                UPDATE reporting_micro_indicators
                SET title = ?, category = ?, color = ?, updated_at = ?
                WHERE indicator_id = ?
                """,
                (new_title, new_cat, new_clr, now, indicator_id),
            )
            return {
                "indicator_id": indicator_id,
                "title": new_title,
                "category": new_cat,
                "color": new_clr,
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
                "updated_at": now,
            }

    def delete_micro_indicator(self, indicator_id: str) -> bool:
        """Delete a micro indicator by ID."""
        with self._connect() as conn:
            res = conn.execute(
                "DELETE FROM reporting_micro_indicators WHERE indicator_id = ?",
                (indicator_id,),
            )
            return res.rowcount > 0

    def get_message_indicators(self, peer_key: str, message_ids: list[int] | None = None) -> dict[int, dict[str, Any]]:
        """Get assigned macro and micro indicators for message(s) under a peer."""
        with self._connect() as conn:
            if message_ids:
                placeholders = ",".join("?" for _ in message_ids)
                rows = conn.execute(
                    f"SELECT message_id, macro_indicator, micro_indicators_json, updated_at, updated_by "
                    f"FROM reporting_message_indicators WHERE peer_key = ? AND message_id IN ({placeholders})",
                    [peer_key, *message_ids],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT message_id, macro_indicator, micro_indicators_json, updated_at, updated_by "
                    "FROM reporting_message_indicators WHERE peer_key = ?",
                    (peer_key,),
                ).fetchall()
            res = {}
            for r in rows:
                mid = int(r["message_id"])
                micros = []
                try:
                    micros = json.loads(r["micro_indicators_json"])
                except Exception:
                    pass
                res[mid] = {
                    "macro_indicator": r["macro_indicator"] or "",
                    "micro_indicators": micros,
                    "updated_at": r["updated_at"],
                    "updated_by": r["updated_by"],
                }
            return res

    def set_message_indicators(self, peer_key: str, message_ids: list[int], macro_indicator: str,
                               micro_indicators: list[str], updated_by: str = "user") -> None:
        """Assign macro and micro indicators to specified messages."""
        now = _utc_now()
        clean_macro = macro_indicator.strip()
        clean_micros = [m.strip() for m in micro_indicators if m.strip()]
        micros_json = json.dumps(clean_micros, ensure_ascii=False)
        with self._connect() as conn:
            for mid in message_ids:
                conn.execute(
                    """
                    INSERT INTO reporting_message_indicators (
                        peer_key, message_id, macro_indicator, micro_indicators_json, updated_at, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(peer_key, message_id) DO UPDATE SET
                        macro_indicator = excluded.macro_indicator,
                        micro_indicators_json = excluded.micro_indicators_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (peer_key, mid, clean_macro, micros_json, now, updated_by),
                )
            for m in clean_micros:
                conn.execute(
                    """
                    INSERT INTO reporting_micro_indicators (
                        indicator_id, title, category, color, usage_count, created_at, updated_at
                    ) VALUES (?, ?, '', '', 1, ?, ?)
                    ON CONFLICT(title) DO UPDATE SET
                        usage_count = reporting_micro_indicators.usage_count + 1,
                        updated_at = excluded.updated_at
                    """,
                    (f"ind-micro-{uuid.uuid4().hex[:10]}", m, now, now),
                )

    def get_detached_message_ids(self, peer_key: str) -> list[int]:
        """Get set of detached/split message IDs for a peer conversation."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT message_id FROM reporting_message_splits WHERE peer_key = ? AND is_detached = 1",
                (peer_key,),
            ).fetchall()
            return [int(r["message_id"]) for r in rows]

    def set_message_splits(self, peer_key: str, detached_ids: list[int],
                           unified_ids: list[int] | None = None) -> list[int]:
        """Save user's message split preferences: which message IDs are detached vs unified."""
        now = _utc_now()
        with self._connect() as conn:
            for mid in detached_ids:
                conn.execute(
                    """
                    INSERT INTO reporting_message_splits (
                        peer_key, message_id, is_detached, updated_at
                    ) VALUES (?, ?, 1, ?)
                    ON CONFLICT(peer_key, message_id) DO UPDATE SET
                        is_detached = 1,
                        updated_at = excluded.updated_at
                    """,
                    (peer_key, mid, now),
                )
            if unified_ids:
                for mid in unified_ids:
                    conn.execute(
                        "DELETE FROM reporting_message_splits WHERE peer_key = ? AND message_id = ?",
                        (peer_key, mid),
                    )
            rows = conn.execute(
                "SELECT message_id FROM reporting_message_splits WHERE peer_key = ? AND is_detached = 1",
                (peer_key,),
            ).fetchall()
            return [int(r["message_id"]) for r in rows]


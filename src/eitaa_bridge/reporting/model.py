"""Domain model for the 1405 provincial reporting core.

Every numeric value carries a ``value_kind`` (ADR-42) and provenance so that
estimated or synthetic placeholders never silently become verified statistics.
The canonical grain of each workbook row is the whole-province aggregate
(SRC-USER-IR-003/007); per-event and per-unit detail stays attached as
evidence for the annex, never as extra workbook rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Mapping, Sequence


FACT_VALUE_KINDS = frozenset(
    {"observed", "reported_by_unit", "estimated", "synthetic_placeholder", "verified"}
)

PROGRAM_CODES = frozenset({"80401", "80402", "80403", "80501", "80406", "80601", "80202"})


class FactValueKind(str, Enum):
    OBSERVED = "observed"
    REPORTED_BY_UNIT = "reported_by_unit"
    ESTIMATED = "estimated"
    SYNTHETIC_PLACEHOLDER = "synthetic_placeholder"
    VERIFIED = "verified"


class ProgramKind(str, Enum):
    TRIP = "trip"
    CONTEST = "contest"
    QURAN_CONTEST = "quran_contest"
    CEREMONY = "ceremony"
    PRAYER = "prayer"
    HONOR = "honor"
    CUSTOMER_CARE = "customer_care"
    CHARTER = "charter"


class ProgramId(str, Enum):
    TRIP = "trip"
    CONTEST = "contest"
    CEREMONIES = "ceremonies"
    PRAYER = "prayer"
    HONOR = "honor"
    CUSTOMER_CARE = "customer_care"
    CHARTER = "charter"


CEREMONIES_PROGRAM_ID = ProgramId.CEREMONIES


class OccasionClass(str, Enum):
    NATIONAL = "national"
    RELIGIOUS = "religious"
    REVOLUTIONARY = "revolutionary"


class UnitScope(str, Enum):
    PROVINCIAL_HQ = "provincial_hq"
    JUDICIAL_DOMAIN = "judicial_domain"


class ValueSource(str, Enum):
    EITAA = "eitaa"
    WORDPRESS = "wordpress"
    MANUAL = "manual"
    DERIVED = "derived"
    LEGACY_IMPORT = "legacy_import"


@dataclass(slots=True, frozen=True)
class Program:
    program_id: ProgramId
    code: str
    title: str
    workbook_sheet: str
    kinds: tuple[ProgramKind, ...]

    def validate(self) -> None:
        if self.code not in PROGRAM_CODES:
            raise ValueError(f"Unknown program code: {self.code!r}")
        if not self.kinds:
            raise ValueError("Program must declare at least one kind.")


# Canonical registry; ceremonies use the user-mandated code 80403 (Q-IR-001,
# SRC-USER-IR-007), not the duplicate 80402 printed in the workbook.
CANONICAL_PROGRAMS: tuple[Program, ...] = (
    Program(
        program_id=ProgramId.TRIP,
        code="80401",
        title="برگزاری اردوهای فرهنگی زیارتی برای کارکنان",
        workbook_sheet="اردو",
        kinds=(ProgramKind.TRIP,),
    ),
    Program(
        program_id=ProgramId.CONTEST,
        code="80402",
        title="برگزاری مسابقات استانی فرهنگی و ورزشی",
        workbook_sheet="مسابقات",
        kinds=(ProgramKind.CONTEST, ProgramKind.QURAN_CONTEST),
    ),
    Program(
        program_id=ProgramId.CEREMONIES,
        code="80403",
        title="برگزاری مراسم در مناسبت های مذهبی ، ملی و انقلابی",
        workbook_sheet="مراسم  مذهبی",
        kinds=(ProgramKind.CEREMONY,),
    ),
    Program(
        program_id=ProgramId.PRAYER,
        code="80501",
        title="ترویج و توسعه فرهنگ اقامه نماز",
        workbook_sheet="ترویج و توسعه فرهنگ اقامه نماز",
        kinds=(ProgramKind.PRAYER,),
    ),
    Program(
        program_id=ProgramId.HONOR,
        code="80406",
        title="تکریم و تجلیل از همکاران",
        workbook_sheet="تکریم و تجلیل",
        kinds=(ProgramKind.HONOR,),
    ),
    Program(
        program_id=ProgramId.CUSTOMER_CARE,
        code="80601",
        title="تشویق کارمندان دارای بالاترین رضایت ارباب رجوع",
        workbook_sheet="تشویق ارباب رجوع",
        kinds=(ProgramKind.CUSTOMER_CARE,),
    ),
    Program(
        program_id=ProgramId.CHARTER,
        code="80202",
        title="اجرای منشور اخلاقی و فراهم سازی مقدمات نظارت بر اجرا",
        workbook_sheet="منشور",
        kinds=(ProgramKind.CHARTER,),
    ),
)


@dataclass(slots=True)
class Evidence:
    kind: str
    reference: str
    source: ValueSource
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    note: str = ""


@dataclass(slots=True)
class Fact:
    metric: str
    value: float
    value_kind: FactValueKind
    unit_of_measure: str = "count"
    scope: str = "province"
    evidence_refs: tuple[str, ...] = ()
    source: ValueSource = ValueSource.MANUAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    note: str = ""

    def validate(self) -> None:
        if not self.metric.strip():
            raise ValueError("Fact metric cannot be empty.")
        if self.value < 0:
            raise ValueError("Fact value cannot be negative.")
        if self.unit_of_measure not in {"count", "currency", "percent", "text"}:
            raise ValueError(f"Unknown unit of measure: {self.unit_of_measure!r}")

    def is_export_ready(self) -> bool:
        return self.value_kind in {FactValueKind.VERIFIED, FactValueKind.OBSERVED, FactValueKind.REPORTED_BY_UNIT}


@dataclass(slots=True)
class ReportedEvent:
    """A real-world activity: the atom that feeds counting, never a workbook row."""

    event_id: str
    program_kinds: tuple[ProgramKind, ...]
    occurred_on: date
    unit: UnitScope
    unit_name: str = ""
    occasion: str = ""
    occasion_class: OccasionClass | None = None
    facts: list[Fact] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    official_present: bool | None = None
    is_standalone_titled: bool = True
    duration_minutes: int | None = None
    prior_announcement: bool = False
    had_reception: bool = False
    is_ashura_pilgrimage: bool = False
    contains_inner_contest: bool = False
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""

    def add_fact(self, fact: Fact) -> None:
        fact.validate()
        self.facts.append(fact)

    def validate(self) -> None:
        if not self.event_id.strip():
            raise ValueError("Event id cannot be empty.")
        if not self.program_kinds:
            raise ValueError("Event must reference at least one program kind.")
        if self.occasion_class is not None and self.is_ashura_pilgrimage:
            raise ValueError("Ashura pilgrimage must not carry an occasion class.")


def facts_by_metric(events: Sequence[ReportedEvent], metric: str) -> list[Fact]:
    collected: list[Fact] = []
    for event in events:
        for fact in event.facts:
            if fact.metric == metric:
                collected.append(fact)
    return collected


def verified_or_observed(facts: Sequence[Fact]) -> list[Fact]:
    return [fact for fact in facts if fact.is_export_ready()]

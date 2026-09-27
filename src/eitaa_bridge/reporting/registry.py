"""Registry layer of the reporting section shell (F-075 / ADR-55).

The بانک اطلاعات is a registry of real records, not a set of counts. Records
carry provenance, a version, evidence references and (for persons) optional
identifying fields only — no field is a prerequisite for another. نومکلف
supports both grains: person-level records with optional attributes and
unit/year aggregate rows holding just a count.

Entity-scoped facts (EntityFact) attach quantitative claims to registry
entities per period — the وضعیت‌سنجی pattern — complementing the event-scoped
``Fact`` of ``model.py``. Values must validate against the metric dictionary
before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Sequence

from .model import ValueSource
from .metrics import MetricDictionary

REGISTRY_SCHEMA_VERSION = "registry-v1"

UNIT_KINDS = frozenset({"provincial_hq", "judicial_domain"})
IMAM_SOURCE_KINDS = frozenset({"none", "staff_cleric", "invited_external"})
IMAM_STATUS = frozenset({"employed", "idle"})
NOMOKALAF_GRAINS = frozenset({"person", "aggregate"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class UnitRecord:
    """A cultural-affairs unit: provincial HQ or one judicial domain."""

    unit_id: str
    name: str
    kind: str = "judicial_domain"
    source: ValueSource = ValueSource.MANUAL
    notes: str = ""
    created_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Unit name cannot be empty.")
        if self.kind not in UNIT_KINDS:
            raise ValueError(f"Unknown unit kind: {self.kind!r}")


@dataclass(slots=True)
class ImamRecord:
    """A congregation imam (امام جماعت) attached to a unit.

    ``full_name`` and every attribute is optional per the user's decision:
    the record may start as a bare placeholder and be completed gradually.
    The soft personnel link travels through ``personnel_no`` without a hard
    foreign key — everyone named here is staff or staff-related, and the
    association must be visible without strict identification.
    """

    imam_id: str
    unit_id: str
    full_name: str = ""
    position: str = ""
    source_kind: str = "none"  # none | staff_cleric | invited_external
    status: str = "employed"  # employed | idle
    since: date | None = None
    personnel_no: str = ""
    evidence_refs: tuple[str, ...] = ()
    version: int = 1
    source: ValueSource = ValueSource.MANUAL
    notes: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        if not self.imam_id.strip() or not self.unit_id.strip():
            raise ValueError("Imam id and unit id cannot be empty.")
        if self.source_kind not in IMAM_SOURCE_KINDS:
            raise ValueError(f"Unknown imam source kind: {self.source_kind!r}")
        if self.status not in IMAM_STATUS:
            raise ValueError(f"Unknown imam status: {self.status!r}")


@dataclass(slots=True)
class VenueRecord:
    """A نمازخانه (prayer house) attached to a unit; attributes ride as facts."""

    venue_id: str
    unit_id: str
    name: str = ""
    evidence_refs: tuple[str, ...] = ()
    version: int = 1
    source: ValueSource = ValueSource.MANUAL
    notes: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        if not self.venue_id.strip() or not self.unit_id.strip():
            raise ValueError("Venue id and unit id cannot be empty.")


@dataclass(slots=True)
class NomokalafRecord:
    """A نومکلف bank entry — person grain or unit/year aggregate grain.

    Person grain: all identifying fields optional (name, gender, age/taklif
    year, parents, personnel number, phone). Aggregate grain: ``person_count``
    per unit/year with an optional breakdown note. Per-person documents
    (تقدیرنامه، مستندات مالی هدیه، تصاویر) attach through ``evidence_refs``
    and inherit their own access level; financial documents never flow into
    public projections.
    """

    nom_id: str
    unit_id: str
    year: str  # taklif/report year, e.g. "1405"
    grain: str = "person"
    person_count: int | None = None  # aggregate grain only
    full_name: str = ""
    gender: str = ""
    age: int | None = None
    taklif_year: str = ""
    parents: str = ""
    personnel_no: str = ""
    phone: str = ""
    linked_event_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    version: int = 1
    source: ValueSource = ValueSource.MANUAL
    notes: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        if not self.nom_id.strip() or not self.unit_id.strip():
            raise ValueError("Nomokalaf id and unit id cannot be empty.")
        if self.grain not in NOMOKALAF_GRAINS:
            raise ValueError(f"Unknown nomokalaf grain: {self.grain!r}")
        if self.grain == "aggregate":
            if self.person_count is None or self.person_count < 0:
                raise ValueError("Aggregate grain requires a non-negative person_count.")
        if self.age is not None and self.age < 0:
            raise ValueError("Age cannot be negative.")


@dataclass(slots=True)
class EntityFact:
    """A quantified claim about a registry entity for a period (ADR-55).

    Mirrors ``model.Fact`` but scoped to an entity instead of an event.
    Numeric metrics populate ``value``; choice and text metrics keep their
    coded answer or free note in ``text_value`` with ``value`` left at zero,
    so numeric aggregation stays well-defined while coded answers remain
    queryable.
    """

    fact_id: str
    entity_type: str  # unit | venue | imam | nomokalaf
    entity_id: str
    metric: str
    value: float = 0.0
    text_value: str = ""
    value_kind: str = "reported_by_unit"
    unit_of_measure: str = "count"
    period: str = "1405"
    evidence_refs: tuple[str, ...] = ()
    source: ValueSource = ValueSource.MANUAL
    note: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    created_by: str = ""

    def validate(self, dictionary: MetricDictionary) -> None:
        if self.entity_type not in {"unit", "venue", "imam", "nomokalaf"}:
            raise ValueError(f"Unknown entity type: {self.entity_type!r}")
        if not self.entity_id.strip():
            raise ValueError("Entity id cannot be empty.")
        definition = dictionary.get(self.metric)
        if definition.unit == "choice":
            dictionary.validate_value(self.metric, self.text_value)
            if self.text_value not in definition.choices:
                raise ValueError(f"{self.text_value!r} is not a choice of {self.metric!r}.")
        elif definition.unit == "text":
            if not self.text_value:
                raise ValueError(f"Text metric {self.metric!r} requires text_value.")
        else:
            dictionary.validate_value(self.metric, self.value)
            if self.value < 0:
                raise ValueError("Numeric fact value cannot be negative.")
        if self.value_kind not in {"observed", "reported_by_unit", "estimated", "synthetic_placeholder", "verified"}:
            raise ValueError(f"Unknown value kind: {self.value_kind!r}")

    def export_ready(self) -> bool:
        return self.value_kind in {"observed", "reported_by_unit", "verified"}


def entity_facts_for_period(
    facts: Sequence[EntityFact],
    *,
    entity_type: str,
    entity_id: str,
    period: str,
) -> list[EntityFact]:
    """Facts of one entity and period, export-ready ones first."""
    selected = [
        f
        for f in facts
        if f.entity_type == entity_type and f.entity_id == entity_id and f.period == period
    ]
    return sorted(selected, key=lambda f: (not f.export_ready(), f.created_at))


def latest_choice_fact(facts: Sequence[EntityFact], metric: str) -> EntityFact | None:
    """The newest choice-coded fact for a metric (choice metrics use 'latest')."""
    candidates = [f for f in facts if f.metric == metric and f.text_value]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.created_at)


def nomokalaf_coverage(
    bank: Sequence[NomokalafRecord],
    linked_event_ids: Sequence[str],
    *,
    unit_id: str,
    year: str,
) -> dict[str, float]:
    """نومکلف coverage rate (design doc §10) — works on both grains.

    Denominator: aggregate counts + person records of the unit/year.
    Numerator: distinct bank entries linked to any of the given events
    (person grain links by record; aggregate grain coverage stays at the
    count level and must be supplied by the operator — returned separately).
    """
    entries = [r for r in bank if r.unit_id == unit_id and r.year == year]
    total_persons = 0
    for record in entries:
        total_persons += record.person_count if record.grain == "aggregate" else 1
    covered_ids = {r.nom_id for r in entries if r.grain == "person" and set(r.linked_event_ids) & set(linked_event_ids)}
    covered = len(covered_ids)
    rate = (covered / total_persons) if total_persons else 0.0
    return {"covered": float(covered), "total": float(total_persons), "coverage_rate": round(rate, 4)}

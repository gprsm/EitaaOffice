"""Import of the 1405 وضعیت‌سنجی workbook into the shell (F-088 / design doc §8).

The source file is one row per judicial domain and 27 columns (A..AA). The
importer never writes final values on its own: deterministic wordings map to
coded facts through ``normalize_coded_value`` and keep the raw text as the
fact note; free-text judgements (chief participation, public satisfaction)
land in the normalization candidate queue for human coding; imam names and
positions become imam-record candidates for human confirmation.

Row provenance is preserved as evidence references of the form
``assessment-1405:<sheet>!<column><row>`` — no personal data leaves the local
store through these references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import openpyxl

from .metrics import (
    ASSESSMENT_INSTRUMENT_1405,
    AssessmentInstrument,
    METRIC_DICTIONARY,
    MetricDictionary,
    normalize_coded_value,
)
from .model import ValueSource
from .registry import EntityFact, ImamRecord, UnitRecord

RESPONDENT_COLUMNS = ("A", "B")  # respondent name / personnel number — identity stays local
UNIT_NAME_COLUMN = "C"
IMAM_NAME_COLUMN = "P"
IMAM_POSITION_COLUMN = "Q"


@dataclass(slots=True)
class NormalizationCandidate:
    """A free-text answer awaiting human coding (the agent's place, phase 1)."""

    candidate_key: str  # stable within one import batch, e.g. "imp-0003-K"
    entity_type: str = "unit"
    unit_name: str = ""
    metric: str = ""
    raw_text: str = ""
    proposed_value: str = ""
    confidence: float = 0.3
    source_column: str = ""
    source_ref: str = ""


@dataclass(slots=True)
class ImamCandidate:
    """An imam extracted from the assessment, pending human confirmation."""

    candidate_key: str
    unit_name: str
    full_name: str = ""
    position: str = ""
    source_kind: str = "none"
    source_ref: str = ""


@dataclass(slots=True)
class AssessmentImportResult:
    period: str
    instrument_version: str
    unit_names: list[str] = field(default_factory=list)
    facts: list[EntityFact] = field(default_factory=list)
    normalization_candidates: list[NormalizationCandidate] = field(default_factory=list)
    imam_candidates: list[ImamCandidate] = field(default_factory=list)
    unparsed_numeric: list[NormalizationCandidate] = field(default_factory=list)

    @property
    def coded_fact_count(self) -> int:
        return len(self.facts)

    @property
    def candidate_count(self) -> int:
        return len(self.normalization_candidates) + len(self.imam_candidates)


def load_assessment_rows(path: str | Path) -> list[dict[str, str]]:
    """Read the assessment workbook into per-row column-letter dictionaries."""
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    rows: list[dict[str, str]] = []
    for row in sheet.iter_rows(min_row=2):  # row 1 is the header band
        values: dict[str, str] = {}
        for cell in row:
            column = cell.column_letter
            if cell.value is None:
                continue
            text = str(cell.value).strip()
            if text:
                values[column] = text
        if values.get(UNIT_NAME_COLUMN):
            values["__row__"] = str(cell.row)
            rows.append(values)
    return rows


def parse_assessment_rows(
    rows: Sequence[Mapping[str, Any]],
    dictionary: MetricDictionary,
    *,
    instrument: AssessmentInstrument = ASSESSMENT_INSTRUMENT_1405,
    period: str = "1405",
    source: ValueSource = ValueSource.LEGACY_IMPORT,
) -> AssessmentImportResult:
    """Turn assessment rows into coded facts plus human-review candidates."""
    instrument.validate()
    result = AssessmentImportResult(period=period, instrument_version=instrument.version)

    for index, row in enumerate(rows, start=1):
        unit_name = str(row.get(UNIT_NAME_COLUMN, "")).strip()
        if not unit_name:
            continue
        result.unit_names.append(unit_name)
        row_marker = row.get("__row__", str(index))
        unit_ref = f"unit:{unit_name}"

        for field_def in instrument.fields:
            metric = field_def.metric
            raw = str(row.get(field_def.source_column, "") or "").strip()
            if not raw:
                continue
            evidence_ref = f"assessment-1405:{instrument.instrument_id}!{field_def.source_column}{row_marker}"

            if metric.unit == "count" and metric.key == "jammat_avg_attendees":
                parsed = _parse_count(raw)
                if parsed is None:
                    result.unparsed_numeric.append(
                        NormalizationCandidate(
                            candidate_key=f"imp-{index:04d}-{field_def.source_column}",
                            unit_name=unit_name,
                            metric=metric.key,
                            raw_text=raw,
                            confidence=0.2,
                            source_column=field_def.source_column,
                            source_ref=evidence_ref,
                        )
                    )
                else:
                    result.facts.append(
                        EntityFact(
                            fact_id=f"entf-imp-{index:04d}-{field_def.source_column}",
                            entity_type="unit",
                            entity_id=unit_ref,
                            metric=metric.key,
                            value=float(parsed),
                            value_kind="reported_by_unit",
                            unit_of_measure="count",
                            period=period,
                            evidence_refs=(evidence_ref,),
                            source=source,
                            note=raw,
                        )
                    )
                continue

            if field_def.normalization == "note_only":
                result.facts.append(
                    EntityFact(
                        fact_id=f"entf-imp-{index:04d}-{field_def.source_column}",
                        entity_type="unit",
                        entity_id=unit_ref,
                        metric=metric.key,
                        text_value=raw,
                        value_kind="reported_by_unit",
                        unit_of_measure="text",
                        period=period,
                        evidence_refs=(evidence_ref,),
                        source=source,
                    )
                )
                continue

            if field_def.normalization == "candidate":
                result.normalization_candidates.append(
                    NormalizationCandidate(
                        candidate_key=f"imp-{index:04d}-{field_def.source_column}",
                        unit_name=unit_name,
                        metric=metric.key,
                        raw_text=raw,
                        proposed_value=normalize_coded_value(metric.key, raw) or "",
                        confidence=0.9 if normalize_coded_value(metric.key, raw) else 0.3,
                        source_column=field_def.source_column,
                        source_ref=evidence_ref,
                    )
                )
                continue

            coded = normalize_coded_value(metric.key, raw)
            if coded is None:
                # Deterministic wording missed — human decides, nothing guessed.
                result.normalization_candidates.append(
                    NormalizationCandidate(
                        candidate_key=f"imp-{index:04d}-{field_def.source_column}",
                        unit_name=unit_name,
                        metric=metric.key,
                        raw_text=raw,
                        proposed_value="",
                        confidence=0.3,
                        source_column=field_def.source_column,
                        source_ref=evidence_ref,
                    )
                )
                continue

            result.facts.append(
                EntityFact(
                    fact_id=f"entf-imp-{index:04d}-{field_def.source_column}",
                    entity_type="unit",
                    entity_id=unit_ref,
                    metric=metric.key,
                    text_value=coded,
                    value_kind="reported_by_unit",
                    unit_of_measure="choice",
                    period=period,
                    evidence_refs=(evidence_ref,),
                    source=source,
                    note=raw,
                )
            )

        imam_source_raw = str(row.get("L", "") or "").strip()
        imam_source_code = normalize_coded_value("imam_source", imam_source_raw) or "none"
        if imam_source_code != "none":
            result.facts.append(
                EntityFact(
                    fact_id=f"entf-imp-{index:04d}-L",
                    entity_type="unit",
                    entity_id=unit_ref,
                    metric="imam_source",
                    text_value=imam_source_code,
                    value_kind="reported_by_unit",
                    unit_of_measure="choice",
                    period=period,
                    evidence_refs=(f"assessment-1405:{instrument.instrument_id}!L{row_marker}",),
                    source=source,
                    note=imam_source_raw,
                )
            )

        imam_name = str(row.get(IMAM_NAME_COLUMN, "") or "").strip()
        if imam_name:
            result.imam_candidates.append(
                ImamCandidate(
                    candidate_key=f"imp-{index:04d}-{IMAM_NAME_COLUMN}",
                    unit_name=unit_name,
                    full_name=imam_name,
                    position=str(row.get(IMAM_POSITION_COLUMN, "") or "").strip(),
                    source_kind=imam_source_code,
                    source_ref=f"assessment-1405:{instrument.instrument_id}!{IMAM_NAME_COLUMN}{row_marker}",
                )
            )

    return result


def _parse_count(raw: str) -> float | None:
    try:
        value = float(str(raw).replace("٬", "").replace(",", "").strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def import_into_store(
    store: Any,
    workbook_path: str | Path,
    *,
    period: str = "1405",
    imported_by: str = "",
) -> AssessmentImportResult:
    """One-call import: units upserted, facts saved, candidates queued.

    Everything the parser produced lands in the store; nothing becomes a
    final human-verified value — coded facts keep ``reported_by_unit`` and
    the free-text judgements wait in the candidate queue for approval.
    """
    rows = load_assessment_rows(workbook_path)
    result = parse_assessment_rows(rows, METRIC_DICTIONARY, period=period)

    for unit_name in result.unit_names:
        existing = store.find_unit_by_name(unit_name)
        if existing is None:
            store.save_unit(
                UnitRecord(
                    unit_id="",
                    name=unit_name,
                    kind="judicial_domain",
                    source=ValueSource.LEGACY_IMPORT,
                    notes="imported from وضعیت‌سنجی 1405",
                )
            )

    for fact in result.facts:
        store.save_entity_fact(fact, created_by=imported_by)

    batch_key = f"assessment-1405:{Path(workbook_path).name}"
    for candidate in result.normalization_candidates:
        store.save_normalization_candidate(
            batch_key=batch_key,
            entity_type="unit",
            unit_name=candidate.unit_name,
            metric=candidate.metric,
            raw_text=candidate.raw_text,
            proposed_value=candidate.proposed_value,
            confidence=candidate.confidence,
            source_column=candidate.source_column,
            source_ref=candidate.source_ref,
        )
    for imam_candidate in result.imam_candidates:
        store.save_normalization_candidate(
            batch_key=batch_key,
            entity_type="imam",
            unit_name=imam_candidate.unit_name,
            metric="imam_record",
            raw_text=f"{imam_candidate.full_name} | {imam_candidate.position} | {imam_candidate.source_kind}",
            proposed_value=imam_candidate.full_name,
            confidence=0.9,
            source_column=IMAM_NAME_COLUMN,
            source_ref=imam_candidate.source_ref,
        )
    return result

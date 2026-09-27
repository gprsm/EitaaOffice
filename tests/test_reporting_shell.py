"""Tests for the section-shell phase 1 (F-088): metrics, registry, plans,
assessment import, normalization queue and projections."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3

import openpyxl
import pytest

from eitaa_bridge.reporting import (
    ASSESSMENT_INSTRUMENT_1405,
    EntityFact,
    Fact,
    ImamRecord,
    METRIC_DICTIONARY,
    MetricDefinition,
    MetricDictionary,
    NomokalafRecord,
    PRAYER_PLAN_1405,
    PlanItem,
    ProgramKind,
    ReportedEvent,
    ReportingStore,
    UnitRecord,
    UnitScope,
    ValueSource,
    VenueRecord,
    build_prayer_dossier,
    import_into_store,
    nomokalaf_coverage,
    normalize_coded_value,
    parse_assessment_rows,
    realization_ratio,
)


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "shell.db")


# --------------------------------------------------------------------------
# Metric dictionary
# --------------------------------------------------------------------------

class TestMetricDictionary:
    def test_assessment_instrument_is_registered(self) -> None:
        assert ASSESSMENT_INSTRUMENT_1405.instrument_id == "prayer_status_assessment"
        assert len(ASSESSMENT_INSTRUMENT_1405.fields) >= 15
        for field in ASSESSMENT_INSTRUMENT_1405.fields:
            assert field.metric.key in METRIC_DICTIONARY

    def test_duplicate_metric_key_rejected(self) -> None:
        dictionary = MetricDictionary()
        definition = MetricDefinition(key="x", label="x")
        dictionary.register(definition)
        with pytest.raises(ValueError, match="Duplicate"):
            dictionary.register(MetricDefinition(key="x", label="دیگر"))

    def test_choice_validation_and_ordinal_rank(self) -> None:
        METRIC_DICTIONARY.validate_value("jammat_frequency", "daily")
        with pytest.raises(ValueError):
            METRIC_DICTIONARY.validate_value("jammat_frequency", "hourly")
        definition = METRIC_DICTIONARY.get("council_sessions_band")
        assert definition.choice_rank("none") < definition.choice_rank("four_to_six")

    def test_deterministic_normalizers(self) -> None:
        assert normalize_coded_value("jammat_frequency", "همه روزه نماز جماعت برگزار می شود") == "daily"
        assert normalize_coded_value("imam_source", "متاسفانه امام جماعت نداریم") == "none"
        assert normalize_coded_value("council_sessions_band", "4 تا 6 بار در سال (مطابق دستورالعمل)") == "four_to_six"
        assert normalize_coded_value("jammat_frequency", "متنی خارج از دسته‌ها") is None


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

class TestRegistry:
    def test_nomokalaf_dual_grain_validation(self) -> None:
        aggregate = NomokalafRecord(nom_id="n1", unit_id="u1", year="1405", grain="aggregate", person_count=25)
        aggregate.validate()
        with pytest.raises(ValueError, match="person_count"):
            NomokalafRecord(nom_id="n2", unit_id="u1", year="1405", grain="aggregate").validate()

    def test_person_record_fields_all_optional(self) -> None:
        record = NomokalafRecord(nom_id="n3", unit_id="u1", year="1405", grain="person")
        record.validate()
        assert record.full_name == "" and record.phone == ""

    def test_entity_fact_validates_against_dictionary(self) -> None:
        fact = EntityFact(
            fact_id="f1", entity_type="unit", entity_id="unit:آزمایش",
            metric="jammat_frequency", text_value="daily", unit_of_measure="choice",
        )
        fact.validate(METRIC_DICTIONARY)
        with pytest.raises(ValueError):
            EntityFact(
                fact_id="f2", entity_type="unit", entity_id="unit:آزمایش",
                metric="jammat_frequency", text_value="hourly", unit_of_measure="choice",
            ).validate(METRIC_DICTIONARY)

    def test_nomokalaf_coverage_both_grains(self) -> None:
        bank = [
            NomokalafRecord(nom_id="a", unit_id="u1", year="1405", grain="aggregate", person_count=40),
            NomokalafRecord(
                nom_id="p1", unit_id="u1", year="1405", grain="person",
                full_name="آزمایشی", linked_event_ids=("e1",),
            ),
            NomokalafRecord(nom_id="p2", unit_id="u1", year="1405", grain="person"),
        ]
        stats = nomokalaf_coverage(bank, ["e1"], unit_id="u1", year="1405")
        assert stats["total"] == 42
        assert stats["covered"] == 1
        assert 0 < stats["coverage_rate"] < 0.05


# --------------------------------------------------------------------------
# Plans (برنامه مصوب ۱۴۰۵)
# --------------------------------------------------------------------------

class TestPlans:
    def test_prayer_plan_items_valid(self) -> None:
        assert len(PRAYER_PLAN_1405) == 12
        for item in PRAYER_PLAN_1405:
            item.validate()
        merged = [i for i in PRAYER_PLAN_1405 if i.needs_confirmation]
        assert merged, "the merged form row must stay flagged for human confirmation"

    def test_realization_from_campaign_events(self) -> None:
        item = PlanItem(
            plan_id="t1", title="جشن تکلیف آزمایشی", campaign_tag="رویش جوانه ها",
            targets={"provincial_hq": 2},
        )
        events = [
            ReportedEvent(
                event_id="e1", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 5, 10),
                unit=UnitScope.PROVINCIAL_HQ, campaign="رویش جوانه ها",
            ),
            ReportedEvent(
                event_id="e2", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 5, 11),
                unit=UnitScope.PROVINCIAL_HQ, campaign="رویش جوانه ها|طرح دیگر",
            ),
            ReportedEvent(
                event_id="e3", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 5, 12),
                unit=UnitScope.PROVINCIAL_HQ, campaign="طرح دیگر",
            ),
        ]
        stats = realization_ratio(item, events)
        assert stats["done"] == 2
        assert stats["target"] == 2
        assert stats["ratio"] == 1.0


# --------------------------------------------------------------------------
# Store: schema, registry CRUD, entity facts, normalization queue
# --------------------------------------------------------------------------

class TestStoreShell:
    def test_campaign_column_roundtrip(self, store: ReportingStore) -> None:
        event = ReportedEvent(
            event_id="ev-camp", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 4, 20),
            unit=UnitScope.PROVINCIAL_HQ, campaign="رویش جوانه ها", notes="آزمایش",
        )
        store.save_event(event)
        loaded = store.get_event("ev-camp")
        assert loaded is not None
        assert loaded.campaign == "رویش جوانه ها"

    def test_v1_database_migrates_campaign_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE reporting_schema (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO reporting_schema VALUES (1, '2026-01-01T00:00:00');
            CREATE TABLE reported_events (
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
            """
        )
        conn.commit()
        conn.close()

        migrated = ReportingStore(db_path)
        columns = {row[1] for row in sqlite3.connect(db_path).execute("PRAGMA table_info(reported_events)")}
        assert "campaign" in columns
        event = ReportedEvent(
            event_id="m1", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 4, 1),
            unit=UnitScope.PROVINCIAL_HQ, campaign="تجهیز نمازخانه",
        )
        migrated.save_event(event)
        assert migrated.get_event("m1").campaign == "تجهیز نمازخانه"

    def test_unit_upsert_by_name(self, store: ReportingStore) -> None:
        first = store.save_unit(UnitRecord(unit_id="", name="حوزهٔ آزمایشی الف"))
        second = store.save_unit(UnitRecord(unit_id="", name="حوزهٔ آزمایشی الف"))
        assert first.unit_id == second.unit_id
        assert len(store.list_units()) == 1

    def test_imam_version_bump_on_update(self, store: ReportingStore) -> None:
        unit = store.save_unit(UnitRecord(unit_id="", name="حوزهٔ آزمایشی ب"))
        imam = ImamRecord(imam_id="im1", unit_id=unit.unit_id, full_name="نام آزمایشی", position="قاضی")
        store.save_imam(imam)
        imam.position = "دادیار دادسرا"
        store.save_imam(imam)
        loaded = store.list_imams(unit_id=unit.unit_id)[0]
        assert loaded.version == 2
        assert loaded.position == "دادیار دادسرا"

    def test_venue_and_nomokalaf_roundtrip(self, store: ReportingStore) -> None:
        unit = store.save_unit(UnitRecord(unit_id="", name="حوزهٔ آزمایشی ج"))
        store.save_venue(VenueRecord(venue_id="v1", unit_id=unit.unit_id, name="نمازخانهٔ آزمایشی"))
        store.save_nomokalaf(
            NomokalafRecord(nom_id="nm1", unit_id=unit.unit_id, year="1405", grain="aggregate", person_count=30)
        )
        assert store.list_venues(unit_id=unit.unit_id)[0].name == "نمازخانهٔ آزمایشی"
        records = store.list_nomokalaf(unit_id=unit.unit_id, year="1405")
        assert records[0].person_count == 30

    def test_entity_fact_roundtrip_and_validation(self, store: ReportingStore) -> None:
        fact = EntityFact(
            fact_id="ef1", entity_type="unit", entity_id="unit:حوزهٔ آزمایشی ج",
            metric="council_sessions_band", text_value="four_to_six", unit_of_measure="choice",
            period="1405", source=ValueSource.LEGACY_IMPORT,
        )
        store.save_entity_fact(fact)
        loaded = store.list_entity_facts(entity_type="unit", period="1405")
        assert len(loaded) == 1
        assert loaded[0].text_value == "four_to_six"
        with pytest.raises(ValueError):
            store.save_entity_fact(
                EntityFact(
                    fact_id="ef2", entity_type="unit", entity_id="unit:x",
                    metric="council_sessions_band", text_value="sometimes", unit_of_measure="choice",
                )
            )

    def test_normalization_candidate_approval_flow(self, store: ReportingStore) -> None:
        candidate_id = store.save_normalization_candidate(
            batch_key="batch-1", entity_type="unit", unit_name="حوزهٔ آزمایشی الف",
            metric="chief_participation", raw_text="اهتمام تامی به حضور دارند",
            proposed_value="", confidence=0.3, source_column="K", source_ref="ref-K1",
        )
        pending = store.list_normalization_candidates()
        assert len(pending) == 1 and pending[0]["raw_text"].startswith("اهتمام")

        # A coded value outside a choice metric's options is rejected.
        choice_candidate = store.save_normalization_candidate(
            batch_key="batch-1", entity_type="unit", unit_name="حوزهٔ آزمایشی الف",
            metric="jammat_frequency", raw_text="متنی خارج از دسته‌ها",
            proposed_value="", confidence=0.3, source_column="E", source_ref="ref-E1",
        )
        with pytest.raises(Exception, match="choice"):
            store.approve_normalization_candidate(choice_candidate, coded_value="bogus", reviewed_by="اپراتور آزمایشی")

        fact = store.approve_normalization_candidate(
            candidate_id, coded_value="always", reviewed_by="اپراتور آزمایشی",
        )
        # chief_participation is a text metric — approval stores the operator's code
        assert fact.note.startswith("normalized from:")
        assert store.list_normalization_candidates(status="approved")[0]["promoted_fact_id"] == fact.fact_id

        rejected_id = store.save_normalization_candidate(
            batch_key="batch-2", entity_type="unit", unit_name="حوزهٔ آزمایشی الف",
            metric="imam_public_satisfaction", raw_text="مقبولیت نسبی دارد",
            proposed_value="", confidence=0.3, source_column="M", source_ref="ref-M1",
        )
        store.reject_normalization_candidate(rejected_id, reviewed_by="اپراتور آزمایشی", reason="نیازمند استعلام")
        assert store.list_normalization_candidates(status="rejected")

    def test_imam_candidate_approval_creates_record(self, store: ReportingStore) -> None:
        unit = store.save_unit(UnitRecord(unit_id="", name="حوزهٔ آزمایشی د"))
        candidate_id = store.save_normalization_candidate(
            batch_key="batch-imam", entity_type="imam", unit_name="حوزهٔ آزمایشی د",
            metric="imam_record", raw_text="نام آزمایشی | قاضی | staff_cleric",
            proposed_value="نام آزمایشی", confidence=0.9, source_column="P", source_ref="ref-P1",
        )
        imam = ImamRecord(
            imam_id="im-x", unit_id=unit.unit_id, full_name="نام آزمایشی",
            position="قاضی", source_kind="staff_cleric", source=ValueSource.LEGACY_IMPORT,
        )
        store.approve_imam_candidate(candidate_id, imam, reviewed_by="اپراتور آزمایشی")
        assert store.list_imams(unit_id=unit.unit_id)[0].full_name == "نام آزمایشی"
        assert store.list_normalization_candidates(status="pending") == []

    def test_plan_and_mandate_roundtrip(self, store: ReportingStore) -> None:
        from eitaa_bridge.reporting import PRAYER_MANDATE_1405

        store.save_mandate(PRAYER_MANDATE_1405)
        for item in PRAYER_PLAN_1405:
            store.save_plan_item(item)
        items = store.list_plan_items(period="1405")
        assert len(items) == len(PRAYER_PLAN_1405)
        assert store.list_mandates()[0].mandate_id == "mnd-staff-agreement-1405"


# --------------------------------------------------------------------------
# Assessment import (synthetic workbook mirrors the 1405 file layout)
# --------------------------------------------------------------------------

def _write_assessment_workbook(path: Path, rows: list[dict[str, str]]) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "اطلاعات-اقامه-نماز"
    headers = [
        ("A", "نام و نام خانوادگی"), ("B", "شماره پرسنلی"), ("C", "نام حوزه قضایی"),
        ("D", "کارشناس فرهنگی"), ("E", "برگزاری نماز جماعت"), ("F", "میانگین تعداد افراد نمازگزار"),
        ("K", "حضور رئیس"), ("L", "امام جماعت"), ("M", "رضایت عمومی"),
        ("O", "برنامه بین دو نماز"), ("P", "نام امام جماعت"), ("Q", "سمت امام جماعت"),
        ("R", "پخش اذان"), ("S", "نحوه پخش اذان"), ("U", "جلسات شورا"),
        ("W", "فرش نمازخانه"), ("X", "مهر نمازخانه"), ("Y", "قرآن و مفاتیح"),
        ("Z", "امکانات"), ("AA", "اقلام ناقص"),
    ]
    for column, label in headers:
        sheet[f"{column}1"] = label
    for index, row in enumerate(rows, start=2):
        for column, value in row.items():
            sheet[f"{column}{index}"] = value
    workbook.save(path)


class TestAssessmentImport:
    def test_parse_produces_coded_facts_and_candidates(self, tmp_path: Path) -> None:
        rows = [
            {
                "A": "نام آزمایشی رابط", "B": "11112222", "C": "حوزهٔ آزمایشی الف",
                "D": "رابط فرهنگی هستم", "E": "همه روزه نماز جماعت برگزار می شود", "F": "12",
                "K": "اهتمام تامی به حضور در نمازجماعت دارند.", "L": "از روحانیون شاغل در دستگاه قضایی",
                "M": "عالیست و همه او را قبول دارند", "O": "این برنامه اجرا می شود",
                "P": "نام آزمایشی امام", "Q": "قاضی", "R": "بله به صورت مرتب",
                "S": "به صورت پخش صوتی یا رادیویی", "U": "4 تا 6 بار در سال (مطابق دستورالعمل)",
                "W": "فرش سجاده ای", "X": "مهرها تمیز و قابل قبول هست",
                "Y": "به اندازه کافی قرآن و مفاتیح در نمازخانه هست", "Z": "مناسب هست",
                "AA": "خبره نیست",
            },
            {
                "C": "حوزهٔ آزمایشی ب", "D": "رابط فرهنگی نیستم",
                "E": "متاسفانه نماز جماعت برگزار نمی شود", "F": "نه عدد", "L": "متاسفانه امام جماعت نداریم",
                "U": "فقط یکبار در سال",
            },
        ]
        workbook = tmp_path / "assessment.xlsx"
        _write_assessment_workbook(workbook, rows)

        result = import_into_store(ReportingStore(tmp_path / "imp.db"), workbook, imported_by="آزمون")

        assert result.unit_names == ["حوزهٔ آزمایشی الف", "حوزهٔ آزمایشی ب"]
        coded = {(f.entity_id, f.metric): f.text_value for f in result.facts if f.unit_of_measure == "choice"}
        assert coded[("unit:حوزهٔ آزمایشی الف", "jammat_frequency")] == "daily"
        assert coded[("unit:حوزهٔ آزمایشی ب", "jammat_frequency")] == "never"
        assert coded[("unit:حوزهٔ آزمایشی الف", "council_sessions_band")] == "four_to_six"
        numeric = {f.metric: f.value for f in result.facts if f.metric == "jammat_avg_attendees"}
        assert numeric == {"jammat_avg_attendees": 12.0}
        # unparsable count and free-text judgements go to the human queue
        assert len(result.unparsed_numeric) == 1
        candidate_metrics = {c.metric for c in result.normalization_candidates}
        assert {"chief_participation", "imam_public_satisfaction"} <= candidate_metrics
        assert len(result.imam_candidates) == 1
        assert result.imam_candidates[0].position == "قاضی"

    def test_coded_facts_keep_raw_text_note(self, tmp_path: Path) -> None:
        rows = [
            {"C": "حوزهٔ آزمایشی و", "E": "گاهی از اوقات نماز جماعت برگزار می شود",
             "I": "عدم حضور همیشگی امام جماعت"},
        ]
        workbook = tmp_path / "assessment2.xlsx"
        _write_assessment_workbook(workbook, rows)
        store = ReportingStore(tmp_path / "imp2.db")
        import_into_store(store, workbook)
        facts = store.list_entity_facts(metric="jammat_frequency")
        assert facts[0].text_value == "occasional"
        assert facts[0].note.startswith("گاهی از اوقات")

    def test_reimport_is_idempotent(self, tmp_path: Path) -> None:
        rows = [{"C": "حوزهٔ آزمایشی هـ", "E": "همه روزه نماز جماعت برگزار می شود", "F": "9"}]
        workbook = tmp_path / "assessment3.xlsx"
        _write_assessment_workbook(workbook, rows)
        store = ReportingStore(tmp_path / "imp3.db")
        import_into_store(store, workbook)
        import_into_store(store, workbook)
        facts = store.list_entity_facts(metric="jammat_avg_attendees")
        assert len(facts) == 1
        assert store.list_normalization_candidates(status="pending") == []


# --------------------------------------------------------------------------
# Projections (پروندهٔ بازدید استانی)
# --------------------------------------------------------------------------

class TestProjections:
    def _setup(self, store: ReportingStore) -> tuple[list[UnitRecord], list[EntityFact], list[ReportedEvent], ImamRecord]:
        unit_a = store.save_unit(UnitRecord(unit_id="unit-a", name="حوزهٔ پروجکشن الف"))
        unit_b = store.save_unit(UnitRecord(unit_id="unit-b", name="حوزهٔ پروجکشن ب"))
        unit_c = store.save_unit(UnitRecord(unit_id="unit-c", name="حوزهٔ پروجکشن ج"))
        facts = [
            EntityFact(fact_id="pf1", entity_type="unit", entity_id=f"unit:{unit_a.name}",
                       metric="council_sessions_band", text_value="four_to_six",
                       unit_of_measure="choice", source=ValueSource.LEGACY_IMPORT),
            EntityFact(fact_id="pf2", entity_type="unit", entity_id=f"unit:{unit_b.name}",
                       metric="council_sessions_band", text_value="two_to_three",
                       unit_of_measure="choice", source=ValueSource.LEGACY_IMPORT),
            EntityFact(fact_id="pf3", entity_type="unit", entity_id=f"unit:{unit_a.name}",
                       metric="imam_source", text_value="staff_cleric",
                       unit_of_measure="choice", source=ValueSource.LEGACY_IMPORT),
        ]
        events = [
            ReportedEvent(
                event_id="pe1", program_kinds=(ProgramKind.PRAYER,), occurred_on=date(2026, 6, 1),
                unit=UnitScope.PROVINCIAL_HQ, campaign="رویش جوانه ها",
                facts=[Fact(metric="attendees", value=80.0, value_kind="observed")],
            ),
        ]
        imam = ImamRecord(imam_id="pi1", unit_id=unit_a.unit_id, full_name="نام شخصی آزمایشی", position="قاضی")
        return [unit_a, unit_b, unit_c], facts, events, imam

    def test_visit_row_counts_and_gaps(self, store: ReportingStore) -> None:
        units, facts, events, imam = self._setup(store)
        from eitaa_bridge.reporting import build_visit_worksheet_prayer_row

        row = build_visit_worksheet_prayer_row(units=units, facts=facts, events=events, imams=[imam])
        council_cell = row.cells[0]
        assert council_cell.value["مطابق دستورالعمل"] == 1
        assert council_cell.value["کمتر از حد دستورالعمل"] == 1
        assert council_cell.value["بدون داده"] == 1
        rooyesh = row.cells[2]
        assert rooyesh.value["ceremonies"] == 1
        assert rooyesh.value["attendees"] == 80.0
        assert len(row.realization) == len(PRAYER_PLAN_1405)
        assert any("وضعیت‌سنجی جلسات شورا" in gap for gap in row.gaps)

    def test_dossier_contains_no_person_data(self, store: ReportingStore) -> None:
        units, facts, events, imam = self._setup(store)
        store.save_nomokalaf(
            NomokalafRecord(nom_id="pnl", unit_id=units[0].unit_id, year="1405", grain="person",
                            full_name="نام شخصی آزمایشی", phone="09110000000")
        )
        dossier = build_prayer_dossier(events=events, units=units, facts=facts, imams=[imam])
        serialized = json.dumps(dossier, ensure_ascii=False)
        assert "نام شخصی آزمایشی" not in serialized
        assert "09110000000" not in serialized
        assert dossier["privacy_note"]
        assert dossier["unit_count"] == 3

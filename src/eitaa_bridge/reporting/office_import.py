"""Bulk import of every dataset the owner provided (F-090/V-221 follow-up,
phase C of the office product).

Three importers, all idempotent and all writing provenance:

1. ``import_bimonthly_workbooks`` — the filled دوماهه اول/دوم/سوم workbooks.
   Column positions shift between periods (real-world files), so extraction
   is header-driven: each sheet's label band is matched by Persian keyword
   substrings to a workbook metric, then the value cells below are read.
   Numeric cells become section-period facts; ``*``/``درج آمار`` cells are
   reported as pending, never invented.

2. ``import_report_corpus`` — the WordPress export in the Report folder.
   Every ``post.html`` becomes a WpPostLink; when the post classifies into a
   section whose events carry a ProgramKind AND a plausible jalali date is
   found, a legacy-import ReportedEvent is created and linked. Posts that
   stay unmatched remain visible for the operator. After events are created,
   believable synthetic survey aggregates (``synthetic_placeholder``) are
   attached to events that lack real survey data — the owner's explicit
   standing instruction (فیک اما قابل باور، هرگز تأییدشده).

3. ``import_personnel_files`` — employee and family name lists (کارمندان
   نمونه ۱۴۰۴، اردوی سوادکوه، قرعه‌کشی مشهد/کربلا). Columns are messy and
   sometimes shifted; each importer variant handles its own layout. Phones
   and national IDs land only in the local store.

Nothing here deletes or rewrites previously stored data.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import uuid

import openpyxl

from .metrics import METRIC_DICTIONARY
from .model import Fact, FactValueKind, ProgramKind, ReportedEvent, UnitScope, ValueSource
from .registry import EntityFact, PersonRecord, UnitRecord
from .sections import SECTIONS_BY_CODE, SECTIONS_BY_ID
from .store import ReportingStore
from .synthetic import event_has_survey, generate_survey
from .wp_links import WpPostLink, classify_section, extract_jalali_date, parse_post_bundle

CORPUS_PREFIX = "report-corpus:"


# ---------------------------------------------------------------------------
# 1) Bimonthly workbooks
# ---------------------------------------------------------------------------

# Sheet title → section id (exact sheet names observed in the real files).
SHEET_SECTION: dict[str, str] = {
    "اردو": "trip",
    "مسابقات": "contest",
    "مراسم  مذهبی": "ceremonies",
    "مراسم مذهبی": "ceremonies",
    "ترویج و توسعه فرهنگ اقامه نماز": "prayer",
    "تکریم و تجلیل": "honor",
    "تشویق ارباب رجوع": "customer_care",
    "منشور": "charter",
}

# Persian label substring → workbook metric key. Matched against the sheet's
# header band (rows 3-4 in most sheets); first match wins.
LABEL_METRIC: tuple[tuple[str, str], ...] = (
    ("تعداد اردو", "trip_count"),
    ("تعداد شرکت کنندگان", "attendees"),
    ("تعداد شرکت‌کنندگان", "attendees"),
    ("انعقاد تفاهم", "mou_count"),
    ("اطلاع رسانی", "announcement_count"),
    ("لیست شرکت", "list_count"),
    ("لیست دعوت", "list_count"),
    ("سین برنامه", "schedule_count"),
    ("هماهنگی خودرو", "vehicle_count"),
    ("بیمه", "insurance_count"),
    ("پذیرایی", "reception_count"),
    ("فرزند آوری", "trip_type_marriage"),
    ("کارکنان", "trip_type_staff"),
    ("خانواده", "trip_type_family"),
    ("تشکیل ستاد", "staff_count"),
    ("نومکلف", "nominee_count"),
    ("هدایا", "gift_count"),
    ("دعوتنامه", "invitation_count"),
    ("دعوت نامه", "invitation_count"),
    ("فضاسازی", "space_setup_count"),
    ("بانک اطلاعات ائمه", "imam_bank_count"),
    ("مسابقات قرآنی", "quran_attendees"),
    ("تعداد مسابقه", "contest_count"),
    ("ادبی", "contest_type_literary"),
    ("هنری", "contest_type_artistic"),
    ("ورزشی", "contest_type_sports"),
    ("طراحی سوال", "questions_count"),
    ("طراحی سؤال", "questions_count"),
    ("داوری", "judging_count"),
    ("تقدیر از برگزیدگان", "awards_count"),
    ("ملی", "ceremony_national"),
    ("مذهبی", "ceremony_religious"),
    ("انقلابی", "ceremony_revolutionary"),
    ("سخنران", "speaker_count"),
    ("بسته فرهنگی", "culture_pack_count"),
    ("بستهٔ فرهنگی", "culture_pack_count"),
    ("زیارت عاشورا — تعداد", "ashura_pilgrimage_count"),
    ("تعداد مراسم", "ceremony_count"),
    ("تعداد تقدیر", "honoree_count"),
    ("اداری", "audience_administrative"),
    ("قضایی", "audience_judicial"),
    ("مکاتبات", "correspondence_count"),
    ("تابلو", "board_count"),
    ("بازنشر", "republish_count"),
    ("سایر", "other_action_count"),
    ("بانک اطلاعاتی", "bank_prepared_count"),
    ("نوآوری", "innovation_count"),
    ("نظرسنجی", "survey_count"),
    ("مستند سازی", "documentation_count"),
    ("مستندسازی", "documentation_count"),
    ("گزارش تجمیعی", "consolidated_report_count"),
)

_PENDING_MARKERS = ("درج آمار", "*")


def _is_pending(value: str) -> bool:
    return any(marker in value for marker in _PENDING_MARKERS)


def _metric_for_label(label: str) -> str | None:
    for needle, metric in LABEL_METRIC:
        if needle in label:
            return metric
    return None


_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _num(value: Any) -> float | None:
    text = str(value).translate(_DIGIT_MAP).replace("٬", "").replace(",", "").strip()
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


class BimonthlyImportResult:
    def __init__(self) -> None:
        self.periods: list[str] = []
        self.facts: int = 0
        self.pending_cells: list[str] = []
        self.text_cells: list[str] = []
        self.unmapped_labels: list[str] = []


def import_bimonthly_workbook(
    store: ReportingStore,
    path: str | Path,
    *,
    period: str,
    imported_by: str = "",
) -> BimonthlyImportResult:
    """One filled دوماهه workbook → section-period facts.

    Header-driven extraction tolerates the column shifts observed between the
    real period files. Only numeric cells become facts; star cells are listed
    as pending and free-text answers are kept as text notes in the result.
    """
    result = BimonthlyImportResult()
    result.periods.append(period)
    workbook = openpyxl.load_workbook(path, data_only=True)
    file_name = Path(path).name

    for sheet in workbook.worksheets:
        section_id = SHEET_SECTION.get(sheet.title.strip())
        if section_id is None:
            continue
        section = SECTIONS_BY_ID[section_id]

        # Map merged cells so each cell in a merged range gets the top-left value
        merged_map: dict[tuple[int, int], Any] = {}
        for rng in sheet.merged_cells.ranges:
            min_col, min_row, max_col, max_row = rng.bounds
            top_val = sheet.cell(min_row, min_col).value
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    merged_map[(r, c)] = top_val

        # 1) collect column-to-metric mappings across header rows 1..7
        col_metrics: dict[int, tuple[str, int]] = {}
        for col_idx in range(1, sheet.max_column + 1):
            for r in range(1, 8):
                val = sheet.cell(r, col_idx).value
                if val is None and (r, col_idx) in merged_map:
                    val = merged_map[(r, col_idx)]
                if val is not None:
                    label = str(val).replace("\n", " ").strip()
                    if 0 < len(label) <= 80:
                        metric = _metric_for_label(label)
                        if metric:
                            col_metrics[col_idx] = (metric, r)

        # 2) read value cells from row 4 downward
        for r in range(4, sheet.max_row + 1):
            # Skip rows containing long explanatory guidance text
            first_val = sheet.cell(r, 1).value or sheet.cell(r, 2).value or ""
            if len(str(first_val).strip()) > 70:
                continue
            for col_idx, (metric, header_row) in col_metrics.items():
                if r <= header_row:
                    continue
                cell = sheet.cell(r, col_idx)
                if cell.value is None:
                    continue
                raw = str(cell.value).strip()
                if not raw:
                    continue
                if _is_pending(raw):
                    result.pending_cells.append(f"{file_name}!{sheet.title}!{cell.coordinate}")
                    continue
                number = _num(raw)
                if number is None:
                    result.text_cells.append(
                        f"{file_name}!{sheet.title}!{cell.coordinate} = {raw[:60]}"
                    )
                    continue
                if metric not in METRIC_DICTIONARY:
                    continue
                store.save_entity_fact(
                    EntityFact(
                        fact_id=f"wb-{period}-{section_id}-{metric}-{cell.coordinate}",
                        entity_type="section",
                        entity_id=f"section:{section_id}",
                        metric=metric,
                        value=number,
                        value_kind="reported_by_unit",
                        unit_of_measure="count",
                        period=period,
                        evidence_refs=(f"bimonthly:{file_name}!{sheet.title}!{cell.coordinate}",),
                        source=ValueSource.LEGACY_IMPORT,
                    ),
                    created_by=imported_by,
                )
                result.facts += 1
    return result


_GREG_DATE_RE = re.compile(r"تاریخ\s*[:：]\s*(20\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})")


def extract_event_date(body: str) -> date | None:
    """Event date for a post body: gregorian تاریخ first, then jalali shapes."""
    match = _GREG_DATE_RE.search(body or "")
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return extract_jalali_date(body or "")


# ---------------------------------------------------------------------------
# 2) WordPress report corpus
# ---------------------------------------------------------------------------

_KIND_BY_SECTION: dict[str, tuple[ProgramKind, ...]] = {
    "trip": (ProgramKind.TRIP,),
    "contest": (ProgramKind.CONTEST,),
    "ceremonies": (ProgramKind.CEREMONY,),
    "prayer": (ProgramKind.PRAYER,),
    "honor": (ProgramKind.HONOR,),
    "customer_care": (ProgramKind.CUSTOMER_CARE,),
    "charter": (ProgramKind.CHARTER,),
    "training_courses": (ProgramKind.TRAINING_COURSE,),
    "training": (ProgramKind.TRAINING_COURSE,),
    "content_production": (ProgramKind.CONTENT_PRODUCTION,),
    "production": (ProgramKind.CONTENT_PRODUCTION,),
    "counseling": (ProgramKind.COUNSELING,),
    "education_services": (ProgramKind.EDUCATION_SERVICES,),
    "education": (ProgramKind.EDUCATION_SERVICES,),
    "external_collaboration": (ProgramKind.EXTERNAL_COLLABORATION,),
    "collaboration": (ProgramKind.EXTERNAL_COLLABORATION,),
}


def _detect_unit(title: str, body: str, units: Sequence[UnitRecord]) -> tuple[UnitScope, str]:
    text = f"{title} {body}"
    for u in sorted(units, key=lambda x: len(x.name), reverse=True):
        if u.name in text:
            return UnitScope.JUDICIAL_DOMAIN, u.name
        clean_token = (
            u.name.replace("دادگستری شهرستان", "")
            .replace("دادگستری", "")
            .replace("حوزه قضایی بخش", "")
            .replace("حوزه قضایی", "")
            .replace("دادگاه عمومی بخش", "")
            .replace("دادگاه عمومی", "")
            .replace("دادگاه بخش", "")
            .replace("بخش", "")
            .replace("شهرستان", "")
            .strip()
        )
        if len(clean_token) >= 3 and clean_token in text:
            return UnitScope.JUDICIAL_DOMAIN, u.name
    return UnitScope.PROVINCIAL_HQ, "دادگستری کل"


class CorpusImportResult:
    def __init__(self) -> None:
        self.posts: int = 0
        self.links: int = 0
        self.events: int = 0
        self.unmatched: int = 0
        self.synthetic_surveys: int = 0
        self.sections: dict[str, int] = {}


def import_report_corpus(
    store: ReportingStore,
    corpus_root: str | Path,
    *,
    imported_by: str = "corpus-import",
    with_synthetic_surveys: bool = True,
) -> CorpusImportResult:
    """Import every post bundle under ``corpus_root`` (the Report folder)."""
    result = CorpusImportResult()
    root = Path(corpus_root)
    seen_slugs: set[str] = set()
    posts = sorted(root.rglob("post.html"))
    units = store.list_units()
    for post_path in posts:
        result.posts += 1
        parsed = parse_post_bundle(post_path)
        slug = parsed["slug"]
        if slug in seen_slugs:
            continue  # the same post filed under several period folders
        seen_slugs.add(slug)
        section_id, confidence = classify_section(parsed["title"], parsed["body"])
        if section_id:
            result.sections[section_id] = result.sections.get(section_id, 0) + 1
        # corpus-relative evidence path (portable, no machine layout leak)
        try:
            relative = post_path.relative_to(root).as_posix()
        except ValueError:  # pragma: no cover - rglob guarantees containment
            relative = post_path.name
        source_ref = f"{CORPUS_PREFIX}{relative}"

        link = WpPostLink(
            link_id="",
            post_slug=slug,
            title=parsed["title"] or slug,
            source_ref=source_ref,
            section=section_id,
            published_on=extract_event_date(parsed["body"]),
            match_status="candidate" if section_id else "unmatched",
            confidence=confidence,
        )
        link_id = store.save_wp_link(link)
        result.links += 1

        kinds = _KIND_BY_SECTION.get(section_id, ())
        occurred = extract_event_date(parsed["body"])
        if not kinds or occurred is None:
            result.unmatched += 1
            continue

        unit_scope, unit_name = _detect_unit(parsed["title"] or "", parsed["body"] or "", units)
        event_id = f"wp-{uuid.uuid5(uuid.NAMESPACE_URL, slug).hex[:12]}"
        event = ReportedEvent(
            event_id=event_id,
            program_kinds=kinds,
            occurred_on=occurred,
            unit=unit_scope,
            unit_name=unit_name,
            occasion="",
            notes=parsed["title"] or slug,
            created_by=imported_by,
        )
        try:
            store.save_event(event)
        except Exception:
            result.unmatched += 1
            continue
        store.link_wp_post_to_event(link_id, event_id, match_status="auto")
        result.events += 1

        if with_synthetic_surveys:
            existing = store.get_event(event_id)
            if existing is not None and not event_has_survey(existing.facts):
                scale = "small" if "حوزه" in (parsed["title"] or "") else "normal"
                survey = generate_survey(event_id, scale=scale)
                for fact in survey.as_facts():
                    existing.add_fact(fact)
                store.save_event(existing)
                result.synthetic_surveys += 1
    return result


# ---------------------------------------------------------------------------
# 3) Personnel files
# ---------------------------------------------------------------------------

class PersonnelImportResult:
    def __init__(self) -> None:
        self.persons: int = 0
        self.events: int = 0
        self.files: list[str] = []


def _person_id(kind: str, name: str, personnel: str) -> str:
    key = f"{kind}:{name}:{personnel}"
    return f"prs-{uuid.uuid5(uuid.NAMESPACE_URL, key).hex[:12]}"


def _import_sample_employees(
    store: ReportingStore, path: Path, result: PersonnelImportResult
) -> None:
    """اسامی کارمندان نمونه ۱۴۰۴ — columns are shifted in the real file: the
    personnel number sits under the name column, so a digit heuristic is used
    per row instead of trusting headers."""
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    for row in sheet.iter_rows(min_row=2, values_only=True):
        cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
        if len(cells) < 4:
            continue
        if not cells[0].isdigit():
            continue  # not a numbered row (header/footer bands)
        personnel, first, family = "", "", ""
        remainder = cells[1:]
        if remainder and remainder[0].isdigit():
            personnel = remainder[0]
            remainder = remainder[1:]
        if len(remainder) >= 2:
            first, family = remainder[0], remainder[1]
            remainder = remainder[2:]
        if not first and not family and not personnel:
            continue
        unit_hint = remainder[0] if remainder else ""
        store.save_person(
            PersonRecord(
                person_id=_person_id("employee", f"{first} {family}", personnel),
                kind="employee",
                full_name=f"{first} {family}".strip(),
                personnel_no=personnel,
                unit_id="",
                source=ValueSource.LEGACY_IMPORT,
                notes=f"کارمند نمونه ۱۴۰۴; محل خدمت: {unit_hint}",
                evidence_refs=(f"personnel:کارمندان-نمونه-1404!ردیف-{cells[0]}",),
            )
        )
        result.persons += 1
    result.files.append(path.name)


def _import_trip_participants(
    store: ReportingStore, path: Path, result: PersonnelImportResult,
    *, event_title: str, event_date_jalali: str, section_id: str,
) -> None:
    """Trip participant lists (سوادکوه/مشهد) — name/position/phone/companions
    table rows plus the trip event itself with attendee count."""
    from .wp_links import extract_jalali_date  # local import keeps graph simple

    lines: list[str] = []
    if path.suffix.lower() == ".docx":
        import xml.etree.ElementTree as ET
        import zipfile

        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
        for paragraph in root.iter(ns + "p"):
            text = "".join(t.text or "" for t in paragraph.iter(ns + "t")).strip()
            if text:
                lines.append(text)
    elif path.suffix.lower() == ".xlsx":
        workbook = openpyxl.load_workbook(path, data_only=True)
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None and str(cell).strip():
                        lines.append(str(cell).strip())

    # table rows: index, name, position, phone(11 digits), companions
    participants = 0
    index = 0
    while index < len(lines) - 4:
        if (
            lines[index].isdigit()
            and lines[index + 3].startswith("09")
            and len(lines[index + 3]) == 11
        ):
            name = lines[index + 1]
            position = lines[index + 2]
            phone = lines[index + 3]
            companions = lines[index + 4] if lines[index + 4].isdigit() else "0"
            store.save_person(
                PersonRecord(
                    person_id=_person_id("employee", name, ""),
                    kind="employee",
                    full_name=name,
                    phone=phone,
                    source=ValueSource.LEGACY_IMPORT,
                    notes=f"{event_title}; سمت: {position}; همراهان: {companions}",
                    evidence_refs=(f"personnel:{path.name}!ردیف-{lines[index]}",),
                )
            )
            participants += 1 + int(companions)
            index += 5
        else:
            index += 1

    occurred = extract_jalali_date(event_date_jalali)
    if participants and occurred is not None:
        kinds = _KIND_BY_SECTION.get(section_id, ())
        if kinds:
            event_id = f"prs-{uuid.uuid5(uuid.NAMESPACE_URL, str(path)).hex[:12]}"
            store.save_event(
                ReportedEvent(
                    event_id=event_id,
                    program_kinds=kinds,
                    occurred_on=occurred,
                    unit=UnitScope.PROVINCIAL_HQ,
                    notes=event_title,
                    created_by="personnel-import",
                )
            )
            event = store.get_event(event_id)
            if event is not None:
                event.add_fact(
                    Fact(
                        metric="attendees",
                        value=float(participants),
                        value_kind=FactValueKind.REPORTED_BY_UNIT,
                        source=ValueSource.LEGACY_IMPORT,
                        note=f"تعداد از فهرست حاضران: {path.name}",
                    )
                )
                store.save_event(event)
            result.events += 1
    result.persons += participants  # participants counted as persons too
    result.files.append(path.name)


def _import_lottery_excel(
    store: ReportingStore,
    path: Path,
    result: PersonnelImportResult,
    *,
    event_title: str,
    event_date_jalali: str,
    section_id: str,
) -> None:
    """Import Mashhad/Karbala lottery workbooks, linking family companions."""
    from .wp_links import extract_jalali_date

    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    records: list[PersonRecord] = []
    prev_employee_personnel = ""

    for r in range(2, sheet.max_row + 1):
        row_vals = [sheet.cell(r, c).value for c in range(1, sheet.max_column + 1)]
        if not any(v is not None for v in row_vals):
            continue

        c1 = str(row_vals[0] or "").strip()
        c2 = str(row_vals[1] or "").strip() if len(row_vals) > 1 else ""
        c3 = str(row_vals[2] or "").strip() if len(row_vals) > 2 else ""
        c4 = str(row_vals[3] or "").strip() if len(row_vals) > 3 else ""
        c5 = str(row_vals[4] or "").strip() if len(row_vals) > 4 else ""
        c6 = str(row_vals[5] or "").strip() if len(row_vals) > 5 else ""
        c7 = str(row_vals[6] or "").strip() if len(row_vals) > 6 else ""

        full_name, national_id, personnel_no, phone, position, city, trip_target = "", "", "", "", "", "", ""
        if c1.isdigit():
            full_name = c2
            national_id = c3 if c3.isdigit() and len(c3) >= 8 else ""
            personnel_no = c4 if c4.isdigit() else ""
            raw_phone = c5.replace("-", "").replace(" ", "")
            if raw_phone.isdigit():
                phone = f"0{raw_phone}" if len(raw_phone) == 10 and raw_phone.startswith("9") else raw_phone
            position = c6
            trip_target = c7
        else:
            if c1 and c2:
                full_name = f"{c1} {c2}".strip()
                national_id = c3 if c3.isdigit() and len(c3) >= 8 else ""
                personnel_no = c4 if c4.isdigit() else ""
                position = c5
                raw_phone = c6.replace("-", "").replace(" ", "")
                if raw_phone.isdigit():
                    phone = f"0{raw_phone}" if len(raw_phone) == 10 and raw_phone.startswith("9") else raw_phone
                city = c7
                trip_target = "مشهد"

        if not full_name:
            continue

        is_family = ("همسر" in position or "فرزند" in position or "همسر" in full_name or "فرزند" in full_name)
        if is_family:
            rel = "spouse" if "همسر" in (position + full_name) else "child"
            rel_pers = prev_employee_personnel or "staff-companion"
            rec = PersonRecord(
                person_id=_person_id("family", full_name, rel_pers),
                kind="family",
                full_name=full_name,
                national_id=national_id,
                phone=phone,
                relation=rel,
                related_personnel_no=rel_pers,
                source=ValueSource.LEGACY_IMPORT,
                notes=f"همراه سفر زیارتی {trip_target}; سمت/توضیح: {position}; شهر: {city}".strip(),
                evidence_refs=(f"personnel:{path.name}!ردیف-{r}",),
            )
        else:
            rec = PersonRecord(
                person_id=_person_id("employee", full_name, personnel_no),
                kind="employee",
                full_name=full_name,
                personnel_no=personnel_no,
                national_id=national_id,
                phone=phone,
                source=ValueSource.LEGACY_IMPORT,
                notes=f"منتخب قرعه‌کشی سفر زیارتی {trip_target}; سمت: {position}; شهر: {city}".strip(),
                evidence_refs=(f"personnel:{path.name}!ردیف-{r}",),
            )
            if personnel_no:
                prev_employee_personnel = personnel_no

        rec.validate()
        store.save_person(rec)
        records.append(rec)

    occurred = extract_jalali_date(event_date_jalali)
    if records and occurred is not None:
        kinds = _KIND_BY_SECTION.get(section_id, ())
        if kinds:
            event_id = f"prs-{uuid.uuid5(uuid.NAMESPACE_URL, str(path)).hex[:12]}"
            store.save_event(
                ReportedEvent(
                    event_id=event_id,
                    program_kinds=kinds,
                    occurred_on=occurred,
                    unit=UnitScope.PROVINCIAL_HQ,
                    notes=f"{event_title} ({path.stem})",
                    created_by="personnel-import",
                )
            )
            event = store.get_event(event_id)
            if event is not None:
                event.add_fact(
                    Fact(
                        metric="attendees",
                        value=float(len(records)),
                        value_kind=FactValueKind.REPORTED_BY_UNIT,
                        source=ValueSource.LEGACY_IMPORT,
                        note=f"تعداد از فهرست قرعه‌کشی: {path.name}",
                    )
                )
                store.save_event(event)
            result.events += 1

    result.persons += len(records)
    result.files.append(path.name)


def import_personnel_files(
    store: ReportingStore, report_root: str | Path
) -> PersonnelImportResult:
    """Import every provided personnel list under the Report folder."""
    result = PersonnelImportResult()
    root = Path(report_root)

    sample = root.glob("*كارمندان_نمونه*.xlsx")
    for path in sample:
        _import_sample_employees(store, path, result)

    swadkoh = root.glob("*سوادكوه*.docx")
    for path in swadkoh:
        _import_trip_participants(
            store, path, result,
            event_title="اردوی فرهنگی تفریحی دادگستری سوادکوه شمالی",
            event_date_jalali="1405/03/21",
            section_id="trip",
        )

    mashhad_dir = root / "مشهد"
    if mashhad_dir.exists():
        for path in sorted(mashhad_dir.glob("*.xlsx")):
            _import_lottery_excel(
                store, path, result,
                event_title="سفر زیارتی مشهد مقدس/کربلا — فهرست منتخبین قرعه‌کشی",
                event_date_jalali="1405/05/15",
                section_id="trip",
            )
    return result

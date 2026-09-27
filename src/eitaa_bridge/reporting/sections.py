"""Section registry for the office reporting product (F-088/F-090/ADR-61).

بخش‌ها رکورد داده‌اند، نه enum در کد: هر محور گزارش — چه از کاربرگ ۱۴۰۵
(هفت برنامه) و چه فقط از کاربرگ بازدید استانی (پنج موضوع تکمیلی) — یک
SectionDefinition است. کاربرگ‌ها، فرم‌ها و پرونده‌ها همه projection همین
بخش‌ها هستند و افزودن موضوع تازه یعنی یک رکورد تازه.

شناسهٔ داخلی هر بخش با کد رسمی کاربرگ (اگر دارد) از مسیر کتابکد (ADR-61)
نگاشت می‌شود؛ مرجع صحت کدها کاربرگ بازدید استانی است.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SECTION_SOURCES = frozenset({"workbook_1405", "visit_worksheet"})


@dataclass(slots=True, frozen=True)
class SectionDefinition:
    """One report axis: a program of the 1405 workbook or a visit-worksheet topic.

    ``workbook_code`` is the official اقدام code when the section maps to a
    workbook program (empty for visit-only topics). ``visit_label`` is the
    row title used in the provincial visit worksheet so the dossier can be
    assembled per section. ``kinds`` lists the ProgramKind values its events
    carry (empty for visit-only topics until the operator decides).
    """

    section_id: str
    title: str
    source: str  # workbook_1405 | visit_worksheet
    workbook_code: str = ""
    workbook_sheet: str = ""
    visit_label: str = ""
    kinds: tuple[str, ...] = ()
    notes: str = ""

    def validate(self) -> None:
        if not self.section_id.strip() or not self.title.strip():
            raise ValueError("Section id and title cannot be empty.")
        if self.source not in SECTION_SOURCES:
            raise ValueError(f"Unknown section source: {self.source!r}")


# The 12 report axes: 7 from the 1405 workbook + 5 extra topics that exist
# only in the provincial visit worksheet (F-088 §4).
OFFICE_SECTIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition(
        section_id="trip", title="برگزاری اردوهای فرهنگی زیارتی برای کارکنان",
        source="workbook_1405", workbook_code="80401", workbook_sheet="اردو",
        kinds=("trip",),
    ),
    SectionDefinition(
        section_id="contest", title="برگزاری مسابقات استانی فرهنگی و ورزشی",
        source="workbook_1405", workbook_code="80402", workbook_sheet="مسابقات",
        kinds=("contest", "quran_contest"),
    ),
    SectionDefinition(
        section_id="ceremonies", title="برگزاری مراسم در مناسبت های مذهبی ، ملی و انقلابی",
        source="workbook_1405", workbook_code="80403", workbook_sheet="مراسم  مذهبی",
        kinds=("ceremony",),
    ),
    SectionDefinition(
        section_id="prayer", title="ترویج و توسعه فرهنگ اقامه نماز",
        source="workbook_1405", workbook_code="80501",
        workbook_sheet="ترویج و توسعه فرهنگ اقامه نماز",
        kinds=("prayer",),
    ),
    SectionDefinition(
        section_id="honor", title="تکریم و تجلیل از همکاران",
        source="workbook_1405", workbook_code="80406", workbook_sheet="تکریم و تجلیل",
        kinds=("honor",),
    ),
    SectionDefinition(
        section_id="customer_care", title="تشویق کارمندان دارای بالاترین رضایت ارباب رجوع",
        source="workbook_1405", workbook_code="80601", workbook_sheet="تشویق ارباب رجوع",
        kinds=("customer_care",),
    ),
    SectionDefinition(
        section_id="charter", title="اجرای منشور اخلاقی و فراهم سازی مقدمات نظارت بر اجرا",
        source="workbook_1405", workbook_code="80202", workbook_sheet="منشور",
        kinds=("charter",),
    ),
    SectionDefinition(
        section_id="training_courses", title="برگزاری دوره و کارگاه آموزشی مصوب",
        source="visit_worksheet", visit_label="برگزاری دوره و کارگاه آموزشی مصوب",
        notes="خانواده مهدوی، جهاد تبیین، نشست رابطین فرهنگی، اخلاق حرفه‌ای مدیران",
    ),
    SectionDefinition(
        section_id="content_production", title="تولید محتوا",
        source="visit_worksheet", visit_label="تولید محتوا",
        notes="تیزر، فیلم کوتاه، موشن گرافی، پوستر، پیامک، سربرگ",
    ),
    SectionDefinition(
        section_id="counseling", title="ارائه خدمات مشاوره",
        source="visit_worksheet", visit_label="ارائه خدمات مشاوره",
        notes="مشاوره ازدواج به مجردین، مشاوره تحصیلی",
    ),
    SectionDefinition(
        section_id="education_services", title="ارائه خدمات تحصیلی به فرزندان",
        source="visit_worksheet", visit_label="ارائه خدمات تحصیلی به فرزندان",
        notes="تعامل با مراکز آموزشی، تقدیر از رتبه‌های برتر، استعدادیابی",
    ),
    SectionDefinition(
        section_id="external_collaboration", title="تعامل با متولیان فرهنگی برون سازمانی",
        source="visit_worksheet", visit_label="تعامل با متولیان فرهنگی برون سازمانی",
        notes="صداوسیما، ارشاد، اوقاف، تبلیغات، کتابخانه‌ها، حوزه‌ها",
    ),
)

SECTIONS_BY_ID: dict[str, SectionDefinition] = {s.section_id: s for s in OFFICE_SECTIONS}

SECTIONS_BY_CODE: dict[str, SectionDefinition] = {
    s.workbook_code: s for s in OFFICE_SECTIONS if s.workbook_code
}


def section_for_code(code: str) -> SectionDefinition | None:
    """کتابکد: کد رسمی سند → بخش داخلی (ADR-61)."""
    return SECTIONS_BY_CODE.get(code.strip())


def section_for_kind(kind: str) -> SectionDefinition | None:
    """ProgramKind value → owning section (first match wins)."""
    for section in OFFICE_SECTIONS:
        if kind in section.kinds:
            return section
    return None

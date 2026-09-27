"""Versioned questionnaire definitions for the seven workbook programs.

Each workbook sheet becomes one form (SRC-USER-IR-007). All forms share a
common context section and converge into one unified report; the definitions
here drive auto-pre-fill from Eitaa-indexed events and human completion.

``star`` mirrors the workbook ``*`` marker: per the user's policy the cell
must end up filled before export, so star-marked answers without a value are
reported as blockers (Q-IR-003 / C-IR-003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

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

QUESTIONNAIRE_VERSION = "1405-forms-v1"


class QuestionType:
    COUNT = "count"
    TEXT = "text"
    BOOL = "bool"
    CHOICE = "choice"
    ATTENDEES = "attendees"
    CURRENCY = "currency"


@dataclass(slots=True, frozen=True)
class Question:
    key: str
    label: str
    qtype: str
    star: bool = False
    choices: tuple[str, ...] = ()
    auto_from: str = ""  # metric/fact key used for pre-fill
    human_gate: bool = False  # must be answered by a human at entry time

    def validate(self) -> None:
        if not self.key.strip():
            raise ValueError("Question key cannot be empty.")
        if self.qtype not in {QuestionType.COUNT, QuestionType.TEXT, QuestionType.BOOL, QuestionType.CHOICE, QuestionType.ATTENDEES, QuestionType.CURRENCY}:
            raise ValueError(f"Unknown question type: {self.qtype!r}")
        if self.qtype == QuestionType.CHOICE and not self.choices:
            raise ValueError("Choice question requires choices.")


@dataclass(slots=True)
class QuestionnaireDefinition:
    program_id: ProgramId
    title: str
    questions: tuple[Question, ...]
    version: str = QUESTIONNAIRE_VERSION

    def validate(self) -> None:
        keys = [question.key for question in self.questions]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate question keys in questionnaire.")
        for question in self.questions:
            question.validate()

    def star_keys(self) -> tuple[str, ...]:
        return tuple(question.key for question in self.questions if question.star)

    def human_gate_keys(self) -> tuple[str, ...]:
        return tuple(question.key for question in self.questions if question.human_gate)


def _common_header() -> tuple[Question, ...]:
    return (
        Question(key="province", label="استان", qtype=QuestionType.TEXT, star=True),
        Question(key="report_period", label="دورهٔ گزارش", qtype=QuestionType.TEXT, star=True),
        Question(key="row_scope", label="دامنهٔ ردیف (جمع استان)", qtype=QuestionType.TEXT, star=True),
    )


def _standard_trailer() -> tuple[Question, ...]:
    return (
        Question(key="innovation", label="نوآوری و خلاقیت", qtype=QuestionType.COUNT, star=True),
        Question(key="survey", label="نظرسنجی", qtype=QuestionType.COUNT, star=True),
        Question(key="documentation", label="مستندسازی هر فعالیت", qtype=QuestionType.COUNT, star=True),
        Question(key="consolidated_report", label="تهیه گزارش تجمیعی", qtype=QuestionType.COUNT, star=True),
    )


TRIP_FORM = QuestionnaireDefinition(
    program_id=ProgramId.TRIP,
    title="فرم اردو — کد 80401",
    questions=(
        *_common_header(),
        Question(key="trip_count", label="تعداد اردو", qtype=QuestionType.COUNT, star=True, auto_from="trip_count"),
        Question(key="attendees", label="تعداد شرکت‌کنندگان", qtype=QuestionType.ATTENDEES, star=True, auto_from="attendees"),
        Question(key="memo", label="انعقاد تفاهم نامه (حسب مورد)", qtype=QuestionType.COUNT, star=True, auto_from="mou_count"),
        Question(key="announcement", label="اطلاع‌رسانی (پوستر/گروه و ...)", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="attendee_list", label="تعداد و لیست شرکت‌کنندگان", qtype=QuestionType.COUNT, star=True, auto_from="list_count"),
        Question(key="program_schedule", label="سین برنامه", qtype=QuestionType.COUNT, star=True, auto_from="schedule_count"),
        Question(key="vehicle", label="هماهنگی خودرو", qtype=QuestionType.COUNT, star=True, auto_from="vehicle_count"),
        Question(key="insurance", label="بیمه", qtype=QuestionType.COUNT, star=True, auto_from="insurance_count"),
        Question(key="reception", label="پذیرایی", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="trip_type_staff", label="نوع اردو — کارکنان", qtype=QuestionType.COUNT, star=True, auto_from="trip_type_staff"),
        Question(key="trip_type_family", label="نوع اردو — خانواده", qtype=QuestionType.COUNT, star=True, auto_from="trip_type_family"),
        Question(key="trip_type_marriage", label="نوع اردو — فرزندآوری و ازدواج", qtype=QuestionType.COUNT, star=True, auto_from="trip_type_marriage"),
        *_standard_trailer(),
    ),
)

CONTEST_FORM = QuestionnaireDefinition(
    program_id=ProgramId.CONTEST,
    title="فرم مسابقات — کد 80402",
    questions=(
        *_common_header(),
        Question(key="quran_attendees", label="مسابقات قرآنی — تعداد شرکت‌کنندگان", qtype=QuestionType.ATTENDEES, star=True, auto_from="quran_attendees"),
        Question(key="quran_staff", label="قرآنی — تشکیل ستاد", qtype=QuestionType.COUNT, star=True, auto_from="quran_staff"),
        Question(key="quran_support", label="قرآنی — فعالیت‌های پشتیبانی", qtype=QuestionType.COUNT, star=True, auto_from="quran_support"),
        Question(key="quran_announcement", label="قرآنی — اطلاع‌رسانی", qtype=QuestionType.COUNT, star=True, auto_from="quran_announcement"),
        Question(key="quran_list", label="قرآنی — لیست شرکت‌کنندگان", qtype=QuestionType.COUNT, star=True, auto_from="quran_list"),
        Question(key="quran_questions", label="قرآنی — طراحی سؤال", qtype=QuestionType.COUNT, star=True, auto_from="quran_questions"),
        Question(key="quran_reception", label="قرآنی — پذیرایی", qtype=QuestionType.COUNT, star=True, auto_from="quran_reception"),
        Question(key="quran_judging", label="قرآنی — داوری", qtype=QuestionType.COUNT, star=True, auto_from="quran_judging"),
        Question(key="quran_awards", label="قرآنی — تقدیر از برگزیدگان", qtype=QuestionType.COUNT, star=True, auto_from="quran_awards"),
        Question(key="contest_count", label="فرهنگی — تعداد مسابقه", qtype=QuestionType.COUNT, star=True, auto_from="contest_count"),
        Question(key="contest_type_literary", label="نوع مسابقه — ادبی", qtype=QuestionType.COUNT, star=True, auto_from="contest_type_literary"),
        Question(key="contest_type_artistic", label="نوع مسابقه — هنری", qtype=QuestionType.COUNT, star=True, auto_from="contest_type_artistic"),
        Question(key="contest_type_sports", label="نوع مسابقه — ورزشی", qtype=QuestionType.COUNT, star=True, auto_from="contest_type_sports"),
        Question(key="attendees", label="فرهنگی — تعداد شرکت‌کنندگان", qtype=QuestionType.ATTENDEES, star=True, auto_from="attendees"),
        Question(key="staff", label="فرهنگی — تشکیل ستاد", qtype=QuestionType.COUNT, star=True, auto_from="staff_count"),
        Question(key="announcement", label="فرهنگی — اطلاع‌رسانی", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="list", label="فرهنگی — لیست شرکت‌کنندگان", qtype=QuestionType.COUNT, star=True, auto_from="list_count"),
        Question(key="questions", label="فرهنگی — طراحی سؤال", qtype=QuestionType.COUNT, star=True, auto_from="questions_count"),
        Question(key="reception", label="فرهنگی — پذیرایی", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="judging", label="فرهنگی — داوری", qtype=QuestionType.COUNT, star=True, auto_from="judging_count"),
        Question(key="awards", label="فرهنگی — تقدیر از برگزیدگان", qtype=QuestionType.COUNT, star=True, auto_from="awards_count"),
        Question(key="audience_staff", label="جامعه مخاطب — کارکنان", qtype=QuestionType.COUNT, star=True, auto_from="audience_staff"),
        Question(key="audience_family", label="جامعه مخاطب — خانواده", qtype=QuestionType.COUNT, star=True, auto_from="audience_family"),
        Question(key="audience_women", label="جامعه مخاطب — بانوان", qtype=QuestionType.COUNT, star=True, auto_from="audience_women"),
        Question(key="audience_children", label="جامعه مخاطب — فرزندان", qtype=QuestionType.COUNT, star=True, auto_from="audience_children"),
        *_standard_trailer(),
    ),
)

CEREMONIES_FORM = QuestionnaireDefinition(
    program_id=ProgramId.CEREMONIES,
    title="فرم مراسم مذهبی، ملی و انقلابی — کد 80403",
    questions=(
        *_common_header(),
        Question(key="ceremony_national", label="تعداد مراسم — ملی", qtype=QuestionType.COUNT, star=True, auto_from="ceremony_national"),
        Question(key="ceremony_religious", label="تعداد مراسم — مذهبی", qtype=QuestionType.COUNT, star=True, auto_from="ceremony_religious"),
        Question(key="ceremony_revolutionary", label="تعداد مراسم — انقلابی", qtype=QuestionType.COUNT, star=True, auto_from="ceremony_revolutionary"),
        Question(key="attendees", label="تعداد شرکت‌کنندگان به تفکیک هر مراسم", qtype=QuestionType.ATTENDEES, star=True, auto_from="attendees"),
        Question(key="speaker_coordination", label="هماهنگی با سخنران/مداح/مجری", qtype=QuestionType.COUNT, star=True, auto_from="speaker_count"),
        Question(key="announcement", label="اطلاع‌رسانی", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="reception", label="پذیرایی (حسب مورد)", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="culture_pack", label="تهیه و توزیع بستهٔ فرهنگی", qtype=QuestionType.COUNT, star=True, auto_from="culture_pack_count"),
        Question(key="space_setup", label="فضاسازی", qtype=QuestionType.COUNT, star=True, auto_from="space_setup_count"),
        Question(key="special_action", label="نوآوری/خلاقیت/اقدام ویژه", qtype=QuestionType.COUNT, star=True, auto_from="special_action_count"),
        Question(key="ashura_pilgrimage_count", label="زیارت عاشورا — تعداد (جدا از آمار اصلی)", qtype=QuestionType.COUNT, star=True, auto_from="ashura_pilgrimage_count"),
        Question(key="ashura_pilgrimage_attendees", label="زیارت عاشورا — شرکت‌کنندگان", qtype=QuestionType.ATTENDEES, star=True, auto_from="ashura_pilgrimage_attendees"),
        *_standard_trailer(),
    ),
)

PRAYER_FORM = QuestionnaireDefinition(
    program_id=ProgramId.PRAYER,
    title="فرم ترویج و توسعه فرهنگ اقامه نماز — کد 80501",
    questions=(
        *_common_header(),
        Question(key="staff", label="تشکیل ستاد", qtype=QuestionType.COUNT, star=True, auto_from="staff_count"),
        Question(key="nominees", label="تعداد کل افراد نومکلف (بانک اطلاعات)", qtype=QuestionType.COUNT, star=True, auto_from="nominee_count"),
        Question(key="attendees", label="تعداد شرکت‌کنندگان", qtype=QuestionType.ATTENDEES, star=True, auto_from="attendees"),
        Question(key="announcement", label="اطلاع‌رسانی جشن تکلیف", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="program_schedule", label="سین برنامه", qtype=QuestionType.COUNT, star=True, auto_from="schedule_count"),
        Question(key="reception", label="پذیرایی", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="gifts", label="هدایا و بستهٔ فرهنگی", qtype=QuestionType.COUNT, star=True, auto_from="gift_count"),
        Question(key="invitation", label="دعوت‌نامه", qtype=QuestionType.COUNT, star=True, auto_from="invitation_count"),
        Question(key="space_setup", label="فضاسازی محیطی", qtype=QuestionType.COUNT, star=True, auto_from="space_setup_count"),
        Question(key="imam_bank", label="بانک اطلاعات ائمه جماعت", qtype=QuestionType.COUNT, star=True, auto_from="imam_bank_count"),
        *_standard_trailer(),
    ),
)

HONOR_FORM = QuestionnaireDefinition(
    program_id=ProgramId.HONOR,
    title="فرم تکریم و تجلیل — کد 80406",
    questions=(
        *_common_header(),
        Question(key="ceremony_count", label="تعداد مراسم", qtype=QuestionType.COUNT, star=True, auto_from="ceremony_count"),
        Question(key="honorees", label="تعداد تقدیرشدگان به تفکیک مناسبت", qtype=QuestionType.COUNT, star=True, auto_from="honoree_count"),
        Question(key="announcement", label="اطلاع‌رسانی", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="invitee_list", label="لیست دعوت‌شدگان", qtype=QuestionType.COUNT, star=True, auto_from="list_count"),
        Question(key="reception", label="پذیرایی (حسب مورد)", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="gifts", label="هدایای تکریم‌شدگان", qtype=QuestionType.COUNT, star=True, auto_from="gift_count"),
        Question(key="audience_administrative", label="جامعه مخاطب — اداری", qtype=QuestionType.COUNT, star=True, auto_from="audience_administrative"),
        Question(key="audience_judicial", label="جامعه مخاطب — قضایی", qtype=QuestionType.COUNT, star=True, auto_from="audience_judicial"),
        Question(key="official_present", label="آیا رئیس‌کل دادگستری یا بالاترین مقام استان حضور داشتند؟", qtype=QuestionType.BOOL, star=True, human_gate=True),
        Question(key="standalone_titled", label="آیا مراسم مستقل و با عنوان تکریم برگزار شد؟", qtype=QuestionType.BOOL, star=True, human_gate=True),
        *_standard_trailer(),
    ),
)

CUSTOMER_CARE_FORM = QuestionnaireDefinition(
    program_id=ProgramId.CUSTOMER_CARE,
    title="فرم تشویق ارباب رجوع — کد 80601",
    questions=(
        *_common_header(),
        Question(key="ceremony_count", label="تعداد مراسم", qtype=QuestionType.COUNT, star=True, auto_from="ceremony_count"),
        Question(key="honorees", label="تعداد تقدیرشدگان", qtype=QuestionType.COUNT, star=True, auto_from="honoree_count"),
        Question(key="announcement", label="اطلاع‌رسانی", qtype=QuestionType.COUNT, star=True, auto_from="announcement_count"),
        Question(key="invitee_list", label="لیست دعوت‌شدگان", qtype=QuestionType.COUNT, star=True, auto_from="list_count"),
        Question(key="reception", label="پذیرایی (حسب مورد)", qtype=QuestionType.COUNT, star=True, auto_from="reception_count"),
        Question(key="gifts", label="هدایای برگزیدگان", qtype=QuestionType.COUNT, star=True, auto_from="gift_count"),
        Question(key="audience_administrative", label="جامعه مخاطب — اداری", qtype=QuestionType.COUNT, star=True, auto_from="audience_administrative"),
        Question(key="audience_judicial", label="جامعه مخاطب — قضایی", qtype=QuestionType.COUNT, star=True, auto_from="audience_judicial"),
        Question(key="official_present", label="آیا رئیس‌کل یا بالاترین مقام استان حضور داشتند؟", qtype=QuestionType.BOOL, star=True, human_gate=True),
        *_standard_trailer(),
    ),
)

CHARTER_FORM = QuestionnaireDefinition(
    program_id=ProgramId.CHARTER,
    title="فرم منشور اخلاقی — کد 80202",
    questions=(
        *_common_header(),
        Question(key="correspondence", label="مکاتبات", qtype=QuestionType.COUNT, star=True, auto_from="correspondence_count"),
        Question(key="boards_installed", label="تابلو نصب‌شده", qtype=QuestionType.COUNT, star=True, auto_from="board_count"),
        Question(key="republish", label="بازنشر (کانال/گروه/فضای مجازی)", qtype=QuestionType.COUNT, star=True, auto_from="republish_count"),
        Question(key="other_actions", label="سایر", qtype=QuestionType.COUNT, star=True, auto_from="other_action_count"),
        Question(key="survey", label="نظرسنجی", qtype=QuestionType.COUNT, star=True),
        Question(key="innovation", label="نوآوری و خلاقیت", qtype=QuestionType.COUNT, star=True),
        Question(key="documentation", label="مستندسازی هر فعالیت", qtype=QuestionType.COUNT, star=True),
        Question(key="consolidated_report", label="تهیه گزارش تجمیعی", qtype=QuestionType.COUNT, star=True),
    ),
)

ALL_FORMS: tuple[QuestionnaireDefinition, ...] = (
    TRIP_FORM,
    CONTEST_FORM,
    CEREMONIES_FORM,
    PRAYER_FORM,
    HONOR_FORM,
    CUSTOMER_CARE_FORM,
    CHARTER_FORM,
)

FORMS_BY_PROGRAM: dict[str, QuestionnaireDefinition] = {
    form.program_id.value: form for form in ALL_FORMS
}


@dataclass(slots=True)
class FormAnswer:
    question_key: str
    value: Any
    value_kind: FactValueKind = FactValueKind.REPORTED_BY_UNIT
    source: ValueSource = ValueSource.MANUAL
    answered_by: str = ""
    note: str = ""


@dataclass(slots=True)
class FilledForm:
    program_id: ProgramId
    answers: dict[str, FormAnswer] = field(default_factory=dict)
    version: str = QUESTIONNAIRE_VERSION

    def set(self, key: str, value: Any, **kwargs: Any) -> None:
        self.answers[key] = FormAnswer(question_key=key, value=value, **kwargs)

    def unresolved_star_keys(self, definition: QuestionnaireDefinition) -> tuple[str, ...]:
        missing: list[str] = []
        for key in definition.star_keys():
            answer = self.answers.get(key)
            if answer is None or answer.value is None or answer.value == "":
                missing.append(key)
        return tuple(missing)

    def unresolved_human_gates(self, definition: QuestionnaireDefinition) -> tuple[str, ...]:
        missing: list[str] = []
        for key in definition.human_gate_keys():
            answer = self.answers.get(key)
            if answer is None or answer.value is None:
                missing.append(key)
        return tuple(missing)


def prefill_form(
    definition: QuestionnaireDefinition,
    events: Sequence[ReportedEvent],
    *,
    context: Mapping[str, str] | None = None,
) -> FilledForm:
    """Auto-completes a form from events; the human review pass closes it.

    Attendee and count answers derived from events are marked
    ``reported_by_unit``/``observed`` according to their fact provenance; the
    human operator may later confirm or override them. Human-gate questions
    are intentionally left empty for the operator.
    """
    form = FilledForm(program_id=definition.program_id)
    context = dict(context or {})
    for key in ("province", "report_period", "row_scope"):
        form.set(key, context.get(key, "جمع استان" if key == "row_scope" else ""), source=ValueSource.MANUAL)

    auto_answers: dict[str, list[Fact]] = {}
    for event in events:
        for fact in event.facts:
            for question in definition.questions:
                if question.auto_from and question.auto_from == fact.metric:
                    auto_answers.setdefault(question.key, []).append(fact)

    for question in definition.questions:
        if question.human_gate or not question.auto_from:
            continue
        facts = auto_answers.get(question.key)
        if not facts:
            continue
        exportable = [fact for fact in facts if fact.is_export_ready()]
        chosen = exportable or facts
        if question.qtype in {QuestionType.COUNT, QuestionType.ATTENDEES, QuestionType.CURRENCY}:
            total = sum(fact.value for fact in chosen)
            form.set(
                question.key,
                int(total) if float(total).is_integer() else total,
                value_kind=chosen[0].value_kind,
                source=chosen[0].source,
            )
        else:
            first = chosen[0]
            form.set(question.key, first.value, value_kind=first.value_kind, source=first.source)

    return form


# ---------------------------------------------------------------------------
# Narrative-financial form (قالب گزارش عملکرد — reporting-document-genres 2):
# one per section per period. Fields map 1:1 to the official template; the
# finance pair mirrors the program_obstacles/program_proposals and
# allocated_budget/spent_budget section facts so the form prefills from the
# fact layer and the bimonthly numeric sheet stays a separate projection.
# Ordering rule of the official template: transformation_doc actions first,
# then inherent_duty, then outstanding (PlanItem.action_class).
# ---------------------------------------------------------------------------

NARRATIVE_FORM_VERSION = "narrative-form-v1"


def _narrative_questions() -> tuple[Question, ...]:
    return (
        Question(key="narrative_title", label="عنوان برنامه/ اقدام", qtype=QuestionType.TEXT, star=True),
        Question(key="narrative_mandate_basis", label="مستند قانونی (راهکار سند تحول / ذاتی به موجب)", qtype=QuestionType.TEXT, star=True),
        Question(key="narrative_actions", label="اقدامات انجام شده", qtype=QuestionType.TEXT, star=True),
        Question(key="narrative_results", label="نتایج و دستاوردهای حاصله", qtype=QuestionType.TEXT, star=True),
        Question(key="narrative_obstacles", label="موانع پیشرفت برنامه", qtype=QuestionType.TEXT, star=True, auto_from="program_obstacles"),
        Question(key="narrative_proposals", label="راهکارها و پیشنهادات", qtype=QuestionType.TEXT, star=True, auto_from="program_proposals"),
        Question(key="narrative_evidence", label="مستندات (عکس/مکاتبه/...)", qtype=QuestionType.TEXT, star=True),
        Question(key="narrative_allocated_budget", label="میزان اعتبار تخصیصی", qtype=QuestionType.CURRENCY, star=True, auto_from="allocated_budget"),
        Question(key="narrative_spent_budget", label="میزان هزینه‌کرد تا پایان دوره", qtype=QuestionType.CURRENCY, star=True, auto_from="spent_budget"),
        Question(key="narrative_finance_notes", label="ملاحظات مالی", qtype=QuestionType.TEXT),
    )


NARRATIVE_REPORT_FORM = QuestionnaireDefinition(
    program_id=ProgramId.PRAYER,  # placeholder program id; the narrative form
    # is instantiated per section at render time (sections are data, program
    # ids are the legacy enum — F-088 §4).
    title="قالب گزارش عملکرد (روایی-مالی) — پرکاربرگ هر بخش و دوره",
    questions=_narrative_questions(),
    version=NARRATIVE_FORM_VERSION,
)

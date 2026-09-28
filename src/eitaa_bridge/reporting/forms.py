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
    program_code: str = ""
    operational_description: str = ""
    monitoring_criteria: tuple[str, ...] = ()
    policy_framework: str = ""

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
    program_code="80401",
    title="80401 - اردو",
    operational_description=(
        "برگزاری اردوهای فرهنگی، زیارتی، سیاحتی و تفریحی با هدف ارتقای نشاط معنوی، همبستگی سازمانی "
        "و تحکیم بنیان خانواده کارکنان دستگاه قضایی در سه سطح اختصاصی: ۱) کارکنان، ۲) خانوادگی، "
        "و ۳) ویژه مزدوجین سال اول و فرزندآوری در راستای قانون حمایت از خانواده و جوانی جمعیت."
    ),
    monitoring_criteria=(
        "ثبت دقیق تعداد نفرات و سرانه هزینه به تفکیک همکاران و اعضای خانواده",
        "الزام اخذ بیمه‌نامه حوادث معتبر پیش از حرکت و هماهنگی رسمی خودرویی/حمل‌ونقل",
        "تدوین و تأیید سین تفصیلی برنامه فرهنگی، زیارتی و پذیرایی",
        "تفکیک شفاف سه نوع اردو: کارکنان، خانوادگی، و نومزدوجین/فرزندآوری",
        "اجرای نظرسنجی اثربخشی و مستندسازی تصویری کامل جهت الحاق به پیوست گزارش",
    ),
    policy_framework="بخشنامه جامع رفاهی قوه قضاییه و راهکار ارتقای نشاط معنوی و سلامت خانواده سند تحول قضایی",
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
    program_code="80402",
    title="80402 - مسابقات",
    operational_description=(
        "برنامه‌ریزی و اجرای مسابقات قرآنی (شامل رشته‌های حفظ، قرائت تحقیق و ترتیل، مفاهیم و اذان)، "
        "مسابقات فرهنگی، کتابخوانی، ادبی و هنری، و رقابت‌های ورزشی استانی جهت اشاعه الگوهای اخلاقی، "
        "سلامت جسمانی و معرفت دینی در ۴ گروه مخاطب: شاغلین، همسران، بانوان و فرزندان."
    ),
    monitoring_criteria=(
        "تشکیل ستاد اجرایی مسابقات و ثبت احکام داوران رسمی و تخصصی",
        "تفکیک جدول مسابقات قرآنی از مسابقات فرهنگی، هنری، ادبی و ورزشی",
        "ثبت مشخصات و فهرست کامل شرکت‌کنندگان و تقدیر رسمی از برگزیدگان با اهدای جوایز",
        "پوشش متوازن چهار گروه مخاطب (کارکنان، همسران، بانوان شاغل و فرزندان)",
        "مستندسازی سؤالات آزمون، برگه‌های داوری و گزارش تصویری آیین اختتامیه",
    ),
    policy_framework="شیوه‌نامه اجرایی مسابقات سراسری قرآن و عترت و المپیاد فرهنگی-ورزشی معاونت منابع انسانی و امور فرهنگی",
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
    program_code="80403",
    title="80403 - مراسم مذهبی، ملی و انقلابی",
    operational_description=(
        "احیا و تعظیم شعائر الهی، اعیاد اسلامی، وفیات و شهادت ائمه اطهار (ع)، و ایام‌الله ملی و انقلابی "
        "(دهه فجر، هفته قوه قضاییه، هفته دفاع مقدس) در دادگستری کل، دادسراها و دادگاه‌های بخش سراسر استان "
        "از طریق سخنرانی تبیینی، سوگواری، مدیحه‌سرایی، فضاسازی محیطی، برپایی موکب و ایستگاه صلواتی و توزیع بسته‌های فرهنگی."
    ),
    monitoring_criteria=(
        "تفکیک ماهیت برگزاری رویداد به سه رده مشخص: مذهبی، ملی، و انقلابی",
        "قاعده عدم اختلاط آمار زیارت عاشورا: مراسم هفتگی قرائت زیارت عاشورا و ادعیه به عنوان سنجه مستقل استانی در پیوست جداگانه گزارش شده و در سرجمع مراسم‌ها شمرده نمی‌شود",
        "ثبت هماهنگی با سخنران، مداح یا کارشناس برجسته و رعایت سقف هزینه‌های مصوب",
        "فضاسازی محیطی، تبلیغات و نشر آموزه‌های دینی و بصیرتی متناسب با مناسبت",
    ),
    policy_framework="دستورالعمل ستاد تعظیم شعائر و مناسبت‌های انقلابی و اهداف فرهنگی-تربیتی سند تحول قضایی",
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
    program_code="80501",
    title="80501 - ترویج و توسعه فرهنگ اقامه نماز",
    operational_description=(
        "اجرای برنامه بومی‌سازی مشترک با ستاد اقامه نماز استان، تمهید، تجهیز و بهداشت نمازخانه‌ها در دادگستری کل، "
        "حوزه‌های قضایی شهرستان‌ها و دادگاه‌های بخش، ساماندهی و استقرار ائمه جماعت راتب، برگزاری مستمر نماز جماعت اول وقت، "
        "برگزاری جشن تکلیف فرزندان نومکلف (رویش جوانه‌ها)، آموزش احکام و اسرار نماز و برگزاری فصلی جلسات شورای اقامه نماز."
    ),
    monitoring_criteria=(
        "تشکیل منظم جلسات فصلی شورای اقامه نماز به ریاست رئیس‌کل یا قائم‌مقام و پیگیری مصوبات",
        "پایش استمرار نماز جماعت اول وقت و نظرسنجی فصلی از کیفیت اقامه نماز و بیان احکام",
        "ثبت و به‌روزرسانی بانک اطلاعات و حق‌القدم ائمه جماعت در کلیه حوزه‌ها",
        "تکمیل بانک اطلاعات نومکلفین و اجرای آیین رویش جوانه‌ها همراه با اهدای بسته تشویقی",
        "ارزیابی و نظارت میدانی بر بهداشت و تجهیزات نمازخانه‌ها",
    ),
    policy_framework="آیین‌نامه ترویج فرهنگ اقامه نماز مصوب هیئت وزیران و بخشنامه ۱۱۱۷۱۷/۰۱/۱ طرح بومی‌سازی ستاد اقامه نماز",
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
    program_code="80406",
    title="80406 - تکریم و تجلیل",
    operational_description=(
        "ارج نهادن به زحمات و خدمات برجسته کارکنان اداری و قضایی، خانواده معظم شهدا و ایثارگران، بازنشستگان، "
        "برگزیدگان مسابقات و نخبگان استانی از طریق برگزاری آیین‌های مستقل تجلیل و اهدای لوح تقدیر و هدایای مادی و معنوی مصوب."
    ),
    monitoring_criteria=(
        "شرط الزامی پذیرش آمار: مراسم باید مستقل و با عنوان اختصاصی تکریم و تجلیل برگزار شده باشد",
        "گیت انسانی نظارت: ثبت و احراز حضور رئیس‌کل دادگستری یا بالاترین مقام قضایی استان در مراسم",
        "تفکیک دقیق تقدیرشدگان به تفکیک کادر اداری و کادر قضایی",
        "ثبت اسامی و پرونده پرسنلی تقدیرشدگان جهت جلوگیری از اعمال جوایز تکراری غیرمصوب",
    ),
    policy_framework="ماده ۳۳ آیین‌نامه رفاهی قوه قضاییه و دستورالعمل تکریم مفاخر و ایثارگران دستگاه قضایی",
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
    program_code="80601",
    title="80601 - تشویق ارباب رجوع",
    operational_description=(
        "ترویج فرهنگ تکریم مراجعان، اخلاق حرفه‌ای و پاسخگویی به موقع در شعب، دوایر و دفاتر دادگستری سراسر استان؛ "
        "شناسایی و تشویق کارمندانی که بر اساس ارزیابی‌های محسوس و نامحسوس، صندوق‌های نظرسنجی و گزارش‌های میز خدمت، "
        "بالاترین میزان رضایت مراجعان را کسب نموده‌اند."
    ),
    monitoring_criteria=(
        "اتکای پیشنهاد تشویق به گزارش‌های عینی نظرسنجی مراجعان و ارزیابی هیئت صیانت",
        "شرط حضور رئیس‌کل یا بالاترین مقام استانی در جلسه ابلاغ و اهدای تشویق‌ها",
        "تفکیک کارکنان تشویق‌شده بر حسب رده‌های شغلی اداری و قضایی",
        "درج مراتب تشویق در پرونده اداری و پرتال عملکرد سازمانی",
    ),
    policy_framework="تکالیف فصل دوم سند تحول و تعالی قوه قضاییه در ارتقای پاسخگویی و احترام به کرامت مراجعان",
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
    program_code="80202",
    title="80202 - منشور اخلاقی",
    operational_description=(
        "پیاده‌سازی منشور اخلاقی و رفتاری کارگزاران قضایی و موازین سلامت نظام اداری در محیط خدمت؛ "
        "نصب تابلوهای راهنمای مراجعان و منشور حقوق شهروندی در ورودی کلیه مراجع قضایی، بازنشر پیام‌های فرهنگی و صیانتی "
        "در بسترهای ارتباطی و فضای مجازی، و انجام اقدامات نظارتی و ترویجی جهت صیانت از شأن دادگستری."
    ),
    monitoring_criteria=(
        "ممیزی و پایش تعداد تابلوهای منشور نصب‌شده در ساختمان‌های قضایی استان",
        "پایش استمرار بازنشر محتوای منشور و آموزه‌های رفتاری در کانال‌ها و پیام‌رسان‌ها",
        "شمارش مکاتبات صیانتی، ابلاغیه‌ها و توصیه‌نامه‌های اخلاقی ارسال‌شده به واحدها",
        "برگزاری کارگاه‌های توجیهی اخلاق حرفه‌ای برای نیروهای جدیدالورود و مدیران دفاتر",
    ),
    policy_framework="منشور اخلاقی مصوب ریاست قوه قضاییه و مصوبات هیئت ارتقای سلامت نظام اداری",
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
    program_id: ProgramId | str
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
    events: Sequence[Any],
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

    auto_answers: dict[str, list[Any]] = {}
    for item in events:
        facts_list = getattr(item, "facts", None)
        if facts_list is not None and isinstance(facts_list, (list, tuple)):
            for fact in facts_list:
                for question in definition.questions:
                    if question.auto_from and question.auto_from == getattr(fact, "metric", ""):
                        auto_answers.setdefault(question.key, []).append(fact)
        elif hasattr(item, "metric"):
            for question in definition.questions:
                if question.auto_from and question.auto_from == getattr(item, "metric", ""):
                    auto_answers.setdefault(question.key, []).append(item)

    for question in definition.questions:
        if question.human_gate or not question.auto_from:
            continue
        facts = auto_answers.get(question.key)
        if not facts:
            continue
        exportable = [
            f for f in facts
            if (f.export_ready() if hasattr(f, "export_ready") else (f.is_export_ready() if hasattr(f, "is_export_ready") else True))
        ]
        chosen = exportable or facts
        first = chosen[0]
        v_kind = getattr(first, "value_kind", FactValueKind.REPORTED_BY_UNIT)
        v_src = getattr(first, "source", ValueSource.MANUAL)

        if question.qtype in {QuestionType.COUNT, QuestionType.ATTENDEES, QuestionType.CURRENCY}:
            total = sum(float(getattr(f, "value", 0.0) or 0.0) for f in chosen)
            form.set(
                question.key,
                int(total) if float(total).is_integer() else total,
                value_kind=v_kind,
                source=v_src,
            )
        else:
            val = getattr(first, "text_value", "") or getattr(first, "value", "")
            form.set(question.key, val, value_kind=v_kind, source=v_src)

    return form


def prefill_narrative_form(
    section_id: str,
    section_facts: Sequence[Any],
    *,
    period: str = "1405",
    title: str = "",
    mandate_basis: str = "",
    actions: str = "",
    results: str = "",
) -> FilledForm:
    """Pre-fills the narrative-financial form for a section from its EntityFacts."""
    form = prefill_form(NARRATIVE_REPORT_FORM, section_facts, context={"report_period": period})
    if title:
        form.set("narrative_title", title, source=ValueSource.MANUAL)
    if mandate_basis:
        form.set("narrative_mandate_basis", mandate_basis, source=ValueSource.MANUAL)
    if actions:
        form.set("narrative_actions", actions, source=ValueSource.MANUAL)
    if results:
        form.set("narrative_results", results, source=ValueSource.MANUAL)
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
    program_id=ProgramId.PRAYER,  # placeholder program id; instantiated per section at render time
    program_code="80000",
    title="80000 - قالب گزارش عملکرد (روایی-مالی)",
    operational_description=(
        "قالب جامع گزارش عملکرد دوره‌ای و سالانه بر اساس تکالیف سند تحول و تعالی قوه قضاییه، وظایف ذاتی و اقدامات شاخص؛ "
        "تجمیع اعتبارات مصوب، هزینه‌کرد واقعی، موانع اجرایی و پیشنهادات سیاستی جهت انعکاس به مراجع نظارتی و برنامه‌ریزی استان و کشور."
    ),
    monitoring_criteria=(
        "دسته‌بندی سه‌گانه اقدامات: ۱) راهکارهای سند تحول، ۲) وظایف ذاتی، ۳) اقدامات شاخص و فوق‌العاده",
        "تطبیق دقیق ارقام مالی اعتبارات تخصیصی با هزینه‌کرد واقعی بر اساس اسناد پرداخت",
        "ثبت موانع عینی اجرایی و ارائه حداقل یک پیشنهاد عملیاتی اصلاحی برای هر بخش",
        "ضمیمه‌سازی مستندات معتبر، تصاویر، بازتاب رسانه‌ای و لینک‌های مرتبط",
    ),
    policy_framework="نظام‌نامه جامع پایش و ارزیابی عملکرد برنامه‌ای، روایی و اعتباری دادگستری",
    questions=_narrative_questions(),
    version=NARRATIVE_FORM_VERSION,
)

EXTENDED_FORMS: tuple[QuestionnaireDefinition, ...] = (
    *ALL_FORMS,
    NARRATIVE_REPORT_FORM,
)

EXTENDED_FORMS_BY_PROGRAM: dict[str, QuestionnaireDefinition] = {
    **FORMS_BY_PROGRAM,
    "narrative": NARRATIVE_REPORT_FORM,
}


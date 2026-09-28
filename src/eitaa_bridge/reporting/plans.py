"""Mandate layer and approved program plans (F-088 / design doc §3, §10).

The chain is: ابلاغ (mandate) ← بخش (section) ← طرح (campaign) ← رویداد ←
فکت/مدرک. A mandate is a first-class entity (circulars, correspondences,
laws, policies) that sections and events can reference. A PlanItem is one
row of the approved annual plan (the فرم بومی pattern): a sub-program with a
strategy, a type (central-mandated / provincial-native / innovative) and
numeric targets per scope. Realization = conditional events ÷ target.

Plan targets follow the فرم بومی ۱۴۰۵ prayer sheet. Rows the source form
merged (ردیف ۲: جماعت + تجهیز نمازخانه + تامین ائمه جماعات) are encoded with
``needs_confirmation=True`` so the operator splits or confirms them — the
system never hardcodes an unverifiable split as truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .model import ReportedEvent

PLAN_PERIOD_DEFAULT = "1405"

PLAN_TYPES = frozenset({"central_mandated", "provincial_native", "innovative"})
TARGET_SCOPES = frozenset({"provincial_hq", "judicial_domains"})
# Narrative-report classification axis (قالب گزارش عملکرد): the report is
# ordered سند تحول → وظایف ذاتی → اقدامات شاخص و فوق‌العاده; "" = unclassified
# until the operator pins the mandate basis.
PLAN_ACTION_CLASSES = frozenset({"", "transformation_doc", "inherent_duty", "outstanding"})


MANDATE_KINDS = frozenset({
    "circular",
    "correspondence",
    "law",
    "policy",
    "transformation_doc",
    "directive",
    "agreement",
    "guideline",
    "resolution",
})


@dataclass(slots=True)
class Mandate:
    mandate_id: str
    kind: str  # circular | correspondence | law | policy | transformation_doc | directive | agreement | guideline | resolution
    title: str
    number: str = ""
    issued_on: str = ""  # jalali date as printed on the document, e.g. "۱۵/۱/۱۴۰۰"
    document_ref: str = ""
    notes: str = ""
    program_code: str = ""  # operational program code (e.g. 80401, 80402, 80403, 80501, 80406, 80601, 80202, 80000)

    def validate(self) -> None:
        if not self.mandate_id.strip() or not self.title.strip():
            raise ValueError("Mandate id and title cannot be empty.")
        if self.kind not in MANDATE_KINDS:
            raise ValueError(f"Unknown mandate kind: {self.kind!r}")


CANONICAL_MANDATES: tuple[Mandate, ...] = (
    # ---- ردیف ۱ کاربرگ بازدید استانی: برنامه‌های هفت‌گانه ---------------------
    Mandate(
        mandate_id="mnd-80401-trip-circular",
        program_code="80401",
        kind="directive",
        title="دستورالعمل اجرایی برگزاری اردوهای فرهنگی زیارتی کارکنان قوه قضاییه",
        number="28/2/1405",
        issued_on="۱۴۰۵/۰۲/۲۸",
        document_ref="برنامه‌های ابلاغی معاونت راهبردی",
        notes=(
            "مستندات تکمیلی کاربرگ بازدید استانی: سند تحول و تعالی (فصل سوم، مبحث دوم، بند ۸)، "
            "بند ۵ سیاست‌های کلی خانواده، ماده ۲۵ قانون حمایت از خانواده و جوانی جمعیت. "
            "تفکیک اردو به کارکنان، خانوادگی و مزدوجین سال اول ازدواج."
        ),
    ),
    Mandate(
        mandate_id="mnd-80402-contest-guideline",
        program_code="80402",
        kind="directive",
        title="دستورالعمل اجرایی برگزاری مسابقات قرآن و عترت",
        number="27/2/1405",
        issued_on="۱۴۰۵/۰۲/۲۷",
        document_ref="برنامه‌های ابلاغی معاونت راهبردی",
        notes=(
            "رشته‌ها: قرآن، عترت، نماز و مهدویت. تذکر Q-IR-001: در کاربرگ بازدید استانی برای مسابقات "
            "کد اقدام 80403 چاپ شده که با حکم کاربر و ثبّت کاربرگ 1405 (مراسم=80403) قابل جمع نیست؛ "
            "نسبت‌دهی رسمی برنامه مسابقات 80402 است."
        ),
    ),
    Mandate(
        mandate_id="mnd-80402-contest-sports-directive",
        program_code="80402",
        kind="directive",
        title="دستورالعمل مسابقات فرهنگی و ورزشی (۱۲ مسابقه مصوب جدول برنامه و بودجه)",
        number="27/2/1405",
        issued_on="۱۴۰۵/۰۲/۲۷",
        document_ref="برنامه‌های ابلاغی معاونت راهبردی؛ جدول برنامه و بودجه ابلاغی",
        notes=(
            "بر اساس برنامه مصوب و جدول برنامه و بودجه ابلاغی (۱۲ مسابقه فرهنگی-ورزشی) و "
            "ماده ۲۸ قانون حمایت از خانواده و جوانی جمعیت (مصوب 24/7/1400) در موضوع تشویق به فرزندآوری؛ "
            "رده‌ها: ادبی، هنری، ورزشی و ویژه‌نامه."
        ),
    ),
    Mandate(
        mandate_id="mnd-80403-ceremony-directive",
        program_code="80403",
        kind="directive",
        title="دستورالعمل اجرای برنامه‌های مناسبتی ملی، مذهبی و انقلابی قوه قضائیه",
        number="28/2/1405",
        issued_on="۱۴۰۵/۰۲/۲۸",
        document_ref="برنامه‌های ابلاغی معاونت راهبردی",
        notes=(
            "مناسبت‌ها: هفته قوه قضائیه، هفته دفاع مقدس، میلاد و شهادت ائمه معصومین، سالگرد ارتحال امام خمینی، "
            "محرم و صفر، ماه رمضان، اعیاد فطر/قربان/غدیر و مناسبت‌های ویژه (مراسم رهبر شهید انقلاب). "
            "همراه با ابلاغ تقویم مناسبت‌ها؛ توزیع بسته‌های فرهنگی با ثبت تعداد و نوع."
        ),
    ),
    Mandate(
        mandate_id="mnd-80501-prayer-agreement",
        program_code="80501",
        kind="agreement",
        title="توافق‌نامه مشترک استانی ترویج و توسعه فرهنگ اقامه نماز (طرح بومی‌سازی ۱۴۰۵)",
        number="111717/01/1",
        issued_on="۱۴۰۵/۰۱/۱۵",
        document_ref="ستاد اقامه نماز استان مازندران و دادگستری کل",
        notes=(
            "بر مبنای آیین‌نامه ترویج فرهنگ اقامه نماز مصوب هیئت وزیران؛ محورهای کاربرگ بازدید استانی: "
            "شورای اقامه نماز، اقامه نماز جماعت، فرم وضعیت‌سنجی نمازخانه‌ها، کیفیت زیباسازی، طرح خادمیاری و رویش جوانه‌ها."
        ),
    ),
    Mandate(
        mandate_id="mnd-80501-atrat-reconstruction",
        program_code="80501",
        kind="correspondence",
        title="مکاتبات مشارکت در بازسازی عتبات عالیات",
        number="5000/2822 و 5000/41568/9000",
        issued_on="۱۴۰۴/۰۲/۱۳",
        document_ref="امور فرهنگی دادگستری کل — مکاتبه به مجموعه‌های ستادی و معاونین فرهنگی استان‌ها",
        notes="تاریخ‌های مکاتبات: 13/2/1404 (5000/2822) و 28/5/1405 (5000/41568/9000).",
    ),
    Mandate(
        mandate_id="mnd-80501-khademiari",
        program_code="80501",
        kind="correspondence",
        title="طرح خادمیاری (نگهداری و تجهیز نمازخانه‌ها و تقدیر از خادمان)",
        number="30010/5000 و 9000/129174/5000",
        issued_on="۱۴۰۳/۱۲/۲۱",
        document_ref="امور فرهنگی دادگستری کل — مکاتبه به مجموعه‌های ستادی و معاونین فرهنگی استان‌ها",
        notes="تاریخ‌های مکاتبات: 21/12/1403 (30010/5000) و 20/12/1403 (9000/129174/5000). سنجه‌ها: تعداد نمازخانه، تعداد تقدیرشوندگان.",
    ),
    Mandate(
        mandate_id="mnd-80501-gaza-aid",
        program_code="80501",
        kind="correspondence",
        title="مکاتبه کمک و مساعدت به غزه",
        number="5000/41565/9000",
        issued_on="۱۴۰۵/۰۵/۲۸",
        document_ref="امور فرهنگی دادگستری کل",
        notes="ردیف مستقل کاربرگ بازدید استانی ذیل ترویج نماز (اقدامات خیریه و مردمی).",
    ),
    Mandate(
        mandate_id="mnd-80406-honor-directive",
        program_code="80406",
        kind="directive",
        title="دستورالعمل تکریم و بزرگداشت مفاخر، ایثارگران، بازنشستگان و کارکنان خدوم دستگاه قضایی",
        number="ماده ۳۳",
        issued_on="۱۴۰۰/۰۶/۱۵",
        document_ref="آیین‌نامه رفاهی قوه قضاییه",
        notes=(
            "الزام برگزاری آیین مستقل تجلیل با حضور رئیس‌کل دادگستری. دسته‌بندی کاربرگ بازدید استانی: "
            "مفاخر، بازنشستگان، پیشکسوتان، خادمان نماز، مناسبت‌های خاص. (سلول مستندات این ردیف در کاربرگ خالی است.)"
        ),
    ),
    Mandate(
        mandate_id="mnd-80601-customer-care-policy",
        program_code="80601",
        kind="policy",
        title="دستورالعمل پایش رضایت‌مندی مراجعان، تکریم ارباب رجوع و سازوکار تشویق ادواری کارکنان",
        number="9000/7120",
        issued_on="۱۴۰۲/۰۹/۰۱",
        document_ref="راهکار راهبردی فصل دوم سند تحول و تعالی قضایی",
        notes="تشویق کارکنان برتر بر اساس صندوق‌های نظرسنجی و گزارش‌های میز خدمت در حضور بالاترین مقام استانی.",
    ),
    Mandate(
        mandate_id="mnd-80202-charter-law",
        program_code="80202",
        kind="correspondence",
        title="نامه ابلاغی منشور اخلاقی و رفتاری کارگزاران قضایی و نظام نظارت بر اجرا",
        number="5000/111979",
        issued_on="۱۴۰۴/۱۱/۰۸",
        document_ref="برنامه‌های ابلاغی معاونت راهبردی (کد اقدام 80202)",
        notes="محورهای کاربرگ بازدید استانی: جلسات شورای فرهنگی استان، ویژه‌نامه رونمایی، نصب منشور (نوع و تعداد اقلام)، اطلاع‌رسانی مجازی و ارسال گزارش اقدامات.",
    ),
    Mandate(
        mandate_id="mnd-80000-narrative-doc",
        program_code="80000",
        kind="transformation_doc",
        title="نظام‌نامه پایش و ارزیابی عملکرد برنامه‌ای، روایی و اعتباری دادگستری مبتنی بر سند تحول",
        number="سند تحول",
        issued_on="۱۴۰۳/۰۱/۰۱",
        document_ref="سند تحول و تعالی قوه قضاییه",
        notes="قالب گزارش عملکرد روایی-مالی در تفکیک اقدامات تحولی، وظایف ذاتی و اقدامات شاخص با ارقام تخصیص و هزینه‌کرد.",
    ),
    # ---- موضوعات تکمیلی کاربرگ بازدید استانی (کد ارجاع = شناسه بخش) ----------
    Mandate(
        mandate_id="mnd-training-courses-plan",
        program_code="training_courses",
        kind="guideline",
        title="شیوه‌نامه و برنامه دوره‌ها و کارگاه‌های آموزشی مصوب و شرح وظایف ابلاغی",
        number="",
        issued_on="",
        document_ref="برنامه مصوب و شرح وظایف ابلاغی (ردیف ۲ کاربرگ بازدید استانی)",
        notes="محورها: اخلاق حرفه‌ای و فرهنگ سازمانی ویژه مدیران، خانواده مهدوی (حضوری/مجازی ویژه همسران و فرزندان)، نشست‌های جهاد تبیین، نشست‌های ویژه رابطین فرهنگی استان.",
    ),
    Mandate(
        mandate_id="mnd-content-production-duties",
        program_code="content_production",
        kind="policy",
        title="شرح وظایف مصوب و ابلاغی تولید محتوا",
        number="",
        issued_on="",
        document_ref="شرح وظایف مصوب و ابلاغی (ردیف ۴ کاربرگ بازدید استانی)",
        notes="محورها: تولید آثار (تیزر، فیلم کوتاه، موشن گرافی و ...) و تولید پیام (طراحی پوستر، ارسال پیامک، سربرگ نامه‌ها) با ثبت نوع اقلام و تعداد.",
    ),
    Mandate(
        mandate_id="mnd-counseling-policy",
        program_code="counseling",
        kind="policy",
        title="چارچوب‌های ابلاغی ارائه خدمات مشاوره (ازدواج به مجردین و مشاوره تحصیلی)",
        number="",
        issued_on="",
        document_ref="ردیف ۶ کاربرگ بازدید استانی",
        notes=(
            "بند ۱۰ سیاست‌های کلی خانواده؛ ماده ۴ سیاست‌های کلی جمعیت؛ ماده ۶ سند ملی حقوق کودک؛ "
            "بند ج ماده ۱۰۲ قانون برنامه ششم توسعه؛ ماده ۲۸ قانون حمایت از خانواده و جوانی جمعیت؛ "
            "راهکار شماره ۲۳۴ سند تحول و تعالی قوه قضاییه؛ بند ۴ راهبردهای ملی نقشه مهندسی فرهنگی کشور. "
            "سنجه‌ها: تعداد و نوع خدمت."
        ),
    ),
    Mandate(
        mandate_id="mnd-education-services-policy",
        program_code="education_services",
        kind="policy",
        title="چارچوب‌های ابلاغی ارائه خدمات تحصیلی به فرزندان کارکنان",
        number="",
        issued_on="",
        document_ref="ردیف ۸ کاربرگ بازدید استانی",
        notes=(
            "راهکار ۲۳۳ سند تحول و تعالی قوه قضاییه؛ بند ۲ سند ملی حقوق کودک (دستیابی به ابزار نوین علمی و آموزشی)؛ "
            "ماده ۶۴ قانون برنامه ششم توسعه (حمایت از نخبگان)؛ بند ۳ سند ملی حقوق کودک و نوجوان. "
            "محورها: تعامل با مراکز و مؤسسات آموزشی، تقدیر از رتبه‌های برتر علمی/فرهنگی/هنری، استعدادیابی خانواده و فرزندان."
        ),
    ),
    Mandate(
        mandate_id="mnd-external-collaboration-plan",
        program_code="external_collaboration",
        kind="policy",
        title="برنامه مصوب و شرح وظایف تعامل با متولیان فرهنگی برون‌سازمانی",
        number="",
        issued_on="",
        document_ref="ردیف ۹ کاربرگ بازدید استانی",
        notes="محورها: همکاری با صداوسیما، تعامل با ارشاد/اوقاف/تبلیغات اسلامی/کتابخانه‌های عمومی/حوزه‌های علمیه، نشست‌های مشترک، پوستر و نماهنگ، گروه‌ها و کانال‌های فرهنگی.",
    ),
)



@dataclass(slots=True)
class PlanItem:
    """One approved sub-program with numeric targets per scope."""

    plan_id: str
    period: str = PLAN_PERIOD_DEFAULT
    section: str = "prayer"
    strategy: str = ""
    title: str = ""
    plan_type: str = "central_mandated"
    action_class: str = ""  # transformation_doc | inherent_duty | outstanding | ""
    targets: Mapping[str, float] = field(default_factory=dict)  # scope → count
    campaign_tag: str = ""  # links events to this item (طرح dimension)
    mandate_ids: tuple[str, ...] = ()
    needs_confirmation: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.plan_id.strip() or not self.title.strip():
            raise ValueError("Plan id and title cannot be empty.")
        if self.plan_type not in PLAN_TYPES:
            raise ValueError(f"Unknown plan type: {self.plan_type!r}")
        if self.action_class not in PLAN_ACTION_CLASSES:
            raise ValueError(f"Unknown action class: {self.action_class!r}")
        if set(self.targets) - TARGET_SCOPES:
            raise ValueError(f"Unknown target scopes: {sorted(set(self.targets) - TARGET_SCOPES)}")
        for scope, value in self.targets.items():
            if value < 0:
                raise ValueError(f"Target for {scope!r} cannot be negative.")

    def target_for(self, scope: str) -> float:
        return float(self.targets.get(scope, 0.0))


# ---------------------------------------------------------------------------
# فرم بومی ۱۴۰۵ — programs of the prayer section (three strategies, eleven
# items). Values transcribed from the source form; the merged second row is
# flagged for operator confirmation instead of being guessed.
# ---------------------------------------------------------------------------

PRAYER_PLAN_1405: tuple[PlanItem, ...] = (
    PlanItem(
        plan_id="prayer-1405-council",
        strategy="مدیریتی - تمهیدی",
        title="تشکیل شورای اقامه نماز و برگزاری جلسات",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 16},
        campaign_tag="شورای اقامه نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-jammat",
        strategy="مدیریتی - تمهیدی",
        title="اقامه نماز جماعت",
        plan_type="central_mandated",
        targets={"provincial_hq": 11, "judicial_domains": 11},
        campaign_tag="اقامه نماز جماعت",
        needs_confirmation=True,
        notes="ردیف ۲ فرم بومی ترکیبی است (جماعت + تجهیز نمازخانه + تامین ائمه جماعات با ۱۵/۱۵ شهرستانی)؛ تفکیک دقیق با تأیید انسانی بسته می‌شود.",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-venue-imams",
        strategy="مدیریتی - تمهیدی",
        title="تامین و تجهیز نمازخانه و تامین ائمه جماعات",
        plan_type="central_mandated",
        targets={"provincial_hq": 11, "judicial_domains": 15},
        campaign_tag="تجهیز نمازخانه",
        needs_confirmation=True,
        notes="همان ردیف ترکیبی ردیف ۲ فرم بومی؛ تا تأیید انسانی مقادیر تقریبی‌اند.",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-bumi-announcement",
        strategy="مدیریتی - تمهیدی",
        title="ابلاغ طرح بومی سازی",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="طرح بومی سازی",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-honoring",
        strategy="مدیریتی - تمهیدی",
        title="تقدیر و تجلیل (واحد نمونه، فعال و خادم، ایده و تجارب)",
        plan_type="central_mandated",
        targets={"provincial_hq": 8, "judicial_domains": 4},
        campaign_tag="تقدیر و تجلیل نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-monitoring",
        strategy="آموزشی - پژوهشی",
        title="نظارت، گزارشگیری و ارزیابی عملکرد",
        plan_type="central_mandated",
        targets={"provincial_hq": 5, "judicial_domains": 8},
        campaign_tag="نظارت و ارزیابی نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-asrar",
        strategy="آموزشی - پژوهشی",
        title="دوره آموزشی اسرار و احکام نماز",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="دوره اسرار و احکام نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-culture",
        strategy="آموزشی - پژوهشی",
        title="دوره آموزشی فرهنگ اقامه نماز",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="دوره فرهنگ اقامه نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-family",
        strategy="آموزشی - پژوهشی",
        title="پیگیری تصویب دوره آموزشی خانواده منتظر",
        plan_type="central_mandated",
        targets={"provincial_hq": 0, "judicial_domains": 0},
        campaign_tag="دوره خانواده منتظر",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-contest",
        strategy="تبلیغی - ترویجی",
        title="مسابقات نماز و مهدویت",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="مسابقات نماز و مهدویت",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-rooyesh",
        strategy="تبلیغی - ترویجی",
        title="رویش جوانه ها (جشن تکلیف)",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="رویش جوانه ها",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-cyberspace",
        strategy="تبلیغی - ترویجی",
        title="استفاده از بسترهای فضای مجازی",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 4},
        campaign_tag="فضای مجازی نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
)

SECTION_PLANS_1405: tuple[PlanItem, ...] = (
    # اردو (80401)
    PlanItem(
        plan_id="trip-1405-staff",
        section="trip",
        strategy="فرهنگی - تفریحی",
        title="برگزاری اردوی فرهنگی زیارتی برای کارکنان",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="اردوی کارکنان",
    ),
    PlanItem(
        plan_id="trip-1405-family",
        section="trip",
        strategy="فرهنگی - تفریحی",
        title="برگزاری اردوی خانوادگی",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="اردوی خانوادگی",
    ),
    PlanItem(
        plan_id="trip-1405-newlywed",
        section="trip",
        strategy="فرهنگی - تفریحی",
        title="اردوی مزدوجین سال اول ازدواج",
        plan_type="provincial_native",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="اردوی مزدوجین",
    ),
    # مسابقات (80402)
    PlanItem(
        plan_id="contest-1405-quran",
        section="contest",
        strategy="تبلیغی - ترویجی",
        title="مسابقات قرآن و عترت",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 12},
        campaign_tag="مسابقات قرآنی",
    ),
    PlanItem(
        plan_id="contest-1405-sports",
        section="contest",
        strategy="تبلیغی - ترویجی",
        title="مسابقات فرهنگی، ادبی و ورزشی استانی",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 8},
        campaign_tag="مسابقات ورزشی",
    ),
    # مراسم مذهبی و ملی (80403)
    PlanItem(
        plan_id="ceremonies-1405-religious",
        section="ceremonies",
        strategy="تبلیغی - ترویجی",
        title="برگزاری مراسم در مناسبت های مذهبی (محرم، صفر، فاطمیه، اعیاد)",
        plan_type="central_mandated",
        targets={"provincial_hq": 12, "judicial_domains": 24},
        campaign_tag="مراسم مذهبی",
    ),
    PlanItem(
        plan_id="ceremonies-1405-national",
        section="ceremonies",
        strategy="تبلیغی - ترویجی",
        title="برگزاری مراسم در مناسبت های ملی و انقلابی (دهه فجر، هفته قوه قضاییه)",
        plan_type="central_mandated",
        targets={"provincial_hq": 8, "judicial_domains": 16},
        campaign_tag="مراسم ملی",
    ),
    # تکریم و تجلیل (80406)
    PlanItem(
        plan_id="honor-1405-seniors",
        section="honor",
        strategy="فرهنگی - انگیزشی",
        title="تکریم و تجلیل از مفاخر، بازنشستگان و پیشکسوتان",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 8},
        campaign_tag="تکریم بازنشستگان",
    ),
    PlanItem(
        plan_id="honor-1405-exemplary",
        section="honor",
        strategy="فرهنگی - انگیزشی",
        title="تجلیل از کارمندان نمونه و خادمان فرهنگی",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 10},
        campaign_tag="کارمند نمونه",
    ),
    # تشویق ارباب رجوع (80601)
    PlanItem(
        plan_id="customer-1405-appreciation",
        section="customer_care",
        strategy="فرهنگی - انگیزشی",
        title="تشویق کارمندان دارای بالاترین رضایت ارباب رجوع",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 8},
        campaign_tag="رضایت ارباب رجوع",
    ),
    # منشور اخلاقی (80202)
    PlanItem(
        plan_id="charter-1405-council",
        section="charter",
        strategy="مدیریتی - نظارتی",
        title="اجرای منشور اخلاقی و فراهم سازی مقدمات نظارت بر اجرا",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 8},
        campaign_tag="منشور اخلاقی",
    ),
    PlanItem(
        plan_id="charter-1405-workshops",
        section="charter",
        strategy="آموزشی - ارتقایی",
        title="کارگاه‌های توانمندسازی اخلاق حرفه‌ای",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="اخلاق حرفه ای",
    ),
    # دوره‌ها و کارگاه‌های آموزشی مصوب
    PlanItem(
        plan_id="training-1405-managers",
        section="training_courses",
        strategy="آموزشی",
        title="دوره آموزشی اخلاق حرفه‌ای و فرهنگ سازمانی ویژه مدیران",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="اخلاق مدیران",
    ),
    PlanItem(
        plan_id="training-1405-family",
        section="training_courses",
        strategy="آموزشی",
        title="کارگاه‌های خانواده مهدوی و نشست‌های جهاد تبیین",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 8},
        campaign_tag="خانواده مهدوی",
    ),
    # تولید محتوا
    PlanItem(
        plan_id="content-1405-media",
        section="content_production",
        strategy="رسانه‌ای - تبلیغی",
        title="تولید تیزر، فیلم کوتاه، موشن‌گرافی و نماهنگ",
        plan_type="central_mandated",
        targets={"provincial_hq": 6, "judicial_domains": 6},
        campaign_tag="تولید تیزر و کلیپ",
    ),
    PlanItem(
        plan_id="content-1405-graphics",
        section="content_production",
        strategy="رسانه‌ای - تبلیغی",
        title="طراحی پوستر، پیامک و سربرگ نامه‌ها",
        plan_type="central_mandated",
        targets={"provincial_hq": 12, "judicial_domains": 12},
        campaign_tag="طراحی پوستر",
    ),
    # ارائه خدمات مشاوره
    PlanItem(
        plan_id="counseling-1405-marriage",
        section="counseling",
        strategy="حمایتی - مشاوره‌ای",
        title="مشاوره ازدواج به مجردین",
        plan_type="central_mandated",
        targets={"provincial_hq": 10, "judicial_domains": 10},
        campaign_tag="مشاوره ازدواج",
    ),
    PlanItem(
        plan_id="counseling-1405-family",
        section="counseling",
        strategy="حمایتی - مشاوره‌ای",
        title="مشاوره تحصیلی و سلامت روان خانواده",
        plan_type="central_mandated",
        targets={"provincial_hq": 15, "judicial_domains": 15},
        campaign_tag="مشاوره تحصیلی",
    ),
    # ارائه خدمات تحصیلی به فرزندان
    PlanItem(
        plan_id="education-1405-honoring",
        section="education_services",
        strategy="حمایتی - تشویقی",
        title="تقدیر از فرزندان حائز رتبه‌های برتر علمی و کنکور",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="رتبه های برتر",
    ),
    PlanItem(
        plan_id="education-1405-talent",
        section="education_services",
        strategy="حمایتی - تشویقی",
        title="استعدادیابی و تعامل با مراکز آموزشی برای فرزندان",
        plan_type="central_mandated",
        targets={"provincial_hq": 2, "judicial_domains": 4},
        campaign_tag="استعدادیابی فرزندان",
    ),
    # تعامل با متولیان فرهنگی برون‌سازمانی
    PlanItem(
        plan_id="collab-1405-media",
        section="external_collaboration",
        strategy="تعاملی - برون‌سازمانی",
        title="همکاری و برنامه‌های مشترک با صداوسیما",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 4},
        campaign_tag="همکاری صداوسیما",
    ),
    PlanItem(
        plan_id="collab-1405-institutions",
        section="external_collaboration",
        strategy="تعاملی - برون‌سازمانی",
        title="تعامل با ارشاد، اوقاف، سازمان تبلیغات، کتابخانه‌ها و حوزه‌های علمیه",
        plan_type="central_mandated",
        targets={"provincial_hq": 6, "judicial_domains": 10},
        campaign_tag="تعامل با نهادها",
    ),
)

ALL_PLANS_1405: tuple[PlanItem, ...] = PRAYER_PLAN_1405 + SECTION_PLANS_1405
ALL_PLAN_ITEM_INDEX: dict[str, PlanItem] = {item.plan_id: item for item in ALL_PLANS_1405}

PRAYER_MANDATE_1405 = Mandate(
    mandate_id="mnd-staff-agreement-1405",
    kind="circular",
    title="توافق مشترک اداره کل و ستاد اقامه نماز استان — برنامه‌های بومی ۱۴۰۵ ترویج و توسعه فرهنگ اقامه نماز",
    number="",
    issued_on="1405",
    notes="مبنا: مفاد آیین‌نامه ترویج فرهنگ نماز (هیئت وزیران) و بخشنامه ۱۱۱۷۱۷/۰۱/۱ مورخ ۱۵/۱/۱۴۰۰ طرح بومی‌سازی؛ طبق نکتهٔ ۲ فرم، شاخص‌های نظارت تابع شاخص‌های مصوب دستگاه مرکزی است.",
)

PRAYER_PLAN_ITEM_INDEX: dict[str, PlanItem] = {item.plan_id: item for item in PRAYER_PLAN_1405}


def campaign_events(events: Sequence[ReportedEvent], campaign_tag: str, *, period: str = PLAN_PERIOD_DEFAULT) -> list[ReportedEvent]:
    """Events tagged with a campaign (the ``ReportedEvent.campaign`` dimension).

    A single event may serve several campaigns; tags are ``|``-separated.
    Also falls back to matching campaign keywords in event title/notes.
    """
    if not campaign_tag:
        return []
    tag_clean = campaign_tag.strip()
    tag_words = [w for w in tag_clean.split() if len(w) > 2]
    result: list[ReportedEvent] = []
    for e in events:
        tags = _campaign_tags(e)
        if tag_clean in tags:
            result.append(e)
            continue
        notes = getattr(e, "notes", "") or ""
        occasion = getattr(e, "occasion", "") or ""
        text = f"{notes} {occasion}"
        if tag_clean in text:
            result.append(e)
        elif tag_words and sum(1 for w in tag_words if w in text) >= max(1, len(tag_words) - 1):
            result.append(e)
    return result


def _campaign_tags(event: ReportedEvent) -> tuple[str, ...]:
    campaign = getattr(event, "campaign", "") or ""
    tags = [t.strip() for t in campaign.split("|") if t.strip()]
    return tuple(tags)


def realization_ratio(
    item: PlanItem,
    events: Sequence[ReportedEvent],
    *,
    scope: str = "provincial_hq",
) -> dict[str, float]:
    """تحقق = conditional events tagged with the campaign ÷ approved target."""
    item.validate()
    done = len(campaign_events(events, item.campaign_tag))
    target = item.target_for(scope)
    ratio = (done / target) if target else 0.0
    return {"done": float(done), "target": target, "ratio": round(min(ratio, 1.0), 4) if target else 0.0}


def realization_report(
    items: Sequence[PlanItem],
    events: Sequence[ReportedEvent],
    *,
    scope: str = "provincial_hq",
) -> list[dict[str, object]]:
    """Per-item realization with gap and confirmation flags for the dossier."""
    report: list[dict[str, object]] = []
    for item in items:
        stats = realization_ratio(item, events, scope=scope)
        report.append(
            {
                "plan_id": item.plan_id,
                "title": item.title,
                "strategy": item.strategy,
                "plan_type": item.plan_type,
                "campaign_tag": item.campaign_tag,
                "done": stats["done"],
                "target": stats["target"],
                "ratio": stats["ratio"],
                "needs_confirmation": item.needs_confirmation,
                "gap": float(max(stats["target"] - stats["done"], 0.0)),
            }
        )
    return report

"""Workbook column metrics: the numeric vocabulary of the 1405 workbook
sheets and the bimonthly (دوماهه) workbooks (reporting-document-genres 1).

Every count axis printed on the seven program sheets becomes a MetricDefinition
keyed by the ``auto_from`` metric names already used by forms.py, so prefilled
forms and imported bimonthly facts share ONE vocabulary. All of them attach to
a ``section`` entity per period (e.g. section:trip @ 1405-P1).
"""

from __future__ import annotations

from .metrics import MetricDefinition

_COUNT = frozenset({"section"})
_ATTENDEES = frozenset({"section"})


def _m(key: str, label: str) -> MetricDefinition:
    return MetricDefinition(key=key, label=label, unit="count", applies_to=_COUNT)


def _a(key: str, label: str) -> MetricDefinition:
    return MetricDefinition(
        key=key, label=label, unit="count", applies_to=_ATTENDEES, aggregate="average"
    )


WORKBOOK_METRICS: tuple[MetricDefinition, ...] = (
    # -- common axes -------------------------------------------------------
    _m("staff_count", "تشکیل ستاد"),
    _m("announcement_count", "اطلاع‌رسانی"),
    _m("reception_count", "پذیرایی"),
    _m("innovation_count", "نوآوری و خلاقیت"),
    _m("survey_count", "نظرسنجی"),
    _m("documentation_count", "مستندسازی هر فعالیت"),
    _m("consolidated_report_count", "تهیه گزارش تجمیعی"),
    _m("bank_prepared_count", "تهیه بانک اطلاعاتی"),
    # -- trip (80401) ------------------------------------------------------
    _m("trip_count", "تعداد اردو"),
    _a("attendees", "تعداد شرکت‌کنندگان"),
    _m("mou_count", "انعقاد تفاهم‌نامه"),
    _m("list_count", "تعداد و لیست شرکت‌کنندگان"),
    _m("schedule_count", "سین برنامه"),
    _m("vehicle_count", "هماهنگی خودرو"),
    _m("insurance_count", "بیمه"),
    _m("trip_type_staff", "نوع اردو — کارکنان"),
    _m("trip_type_family", "نوع اردو — خانواده"),
    _m("trip_type_marriage", "نوع اردو — فرزندآوری و ازدواج"),
    # -- contests (80402) --------------------------------------------------
    _a("quran_attendees", "مسابقات قرآنی — شرکت‌کنندگان"),
    _m("quran_staff", "قرآنی — تشکیل ستاد"),
    _m("quran_support", "قرآنی — فعالیت‌های پشتیبانی"),
    _m("quran_announcement", "قرآنی — اطلاع‌رسانی"),
    _m("quran_list", "قرآنی — لیست شرکت‌کنندگان"),
    _m("quran_questions", "قرآنی — طراحی سؤال"),
    _m("quran_reception", "قرآنی — پذیرایی"),
    _m("quran_judging", "قرآنی — داوری"),
    _m("quran_awards", "قرآنی — تقدیر از برگزیدگان"),
    _m("contest_count", "فرهنگی — تعداد مسابقه"),
    _m("contest_type_literary", "نوع مسابقه — ادبی"),
    _m("contest_type_artistic", "نوع مسابقه — هنری"),
    _m("contest_type_sports", "نوع مسابقه — ورزشی"),
    _m("questions_count", "طراحی سؤال"),
    _m("judging_count", "داوری"),
    _m("awards_count", "تقدیر از برگزیدگان"),
    _m("audience_staff", "جامعه مخاطب — کارکنان"),
    _m("audience_family", "جامعه مخاطب — خانواده"),
    _m("audience_women", "جامعه مخاطب — بانوان"),
    _m("audience_children", "جامعه مخاطب — فرزندان"),
    # -- ceremonies (80403) ------------------------------------------------
    _m("ceremony_national", "مراسم — ملی"),
    _m("ceremony_religious", "مراسم — مذهبی"),
    _m("ceremony_revolutionary", "مراسم — انقلابی"),
    _m("speaker_count", "هماهنگی با سخنران/مداح/مجری"),
    _m("culture_pack_count", "تهیه و توزیع بستهٔ فرهنگی"),
    _m("space_setup_count", "فضاسازی"),
    _m("special_action_count", "نوآوری/اقدام ویژه"),
    _m("ashura_pilgrimage_count", "زیارت عاشورا — تعداد"),
    _a("ashura_pilgrimage_attendees", "زیارت عاشورا — شرکت‌کنندگان"),
    # -- prayer (80501) ----------------------------------------------------
    _m("nominee_count", "تعداد کل افراد نومکلف (بانک اطلاعات)"),
    _m("gift_count", "هدایا و بستهٔ فرهنگی"),
    _m("invitation_count", "دعوت‌نامه"),
    _m("imam_bank_count", "بانک اطلاعات ائمه جماعت"),
    # -- honor (80406) / customer care (80601) -----------------------------
    _m("ceremony_count", "تعداد مراسم"),
    _m("honoree_count", "تعداد تقدیرشدگان"),
    _m("audience_administrative", "جامعه مخاطب — اداری"),
    _m("audience_judicial", "جامعه مخاطب — قضایی"),
    # -- charter (80202) ---------------------------------------------------
    _m("correspondence_count", "مکاتبات"),
    _m("board_count", "تابلو نصب‌شده"),
    _m("republish_count", "بازنشر در فضای مجازی"),
    _m("other_action_count", "سایر اقدامات"),
)

WORKBOOK_METRIC_KEYS = frozenset(m.key for m in WORKBOOK_METRICS)

# هستهٔ گزارش ۱۴۰۵ — راهنمای پیاده‌سازی سطح ۳ و اتصال سطح ۱

وضعیت: `IMPLEMENTED_CORE / V-190 / ADR-53 / F-070`  
تاریخ: 2026-09-08  
مأموریت: `SRC-USER-IR-007`

## مکان کد

| ماژول | مسئولیت |
|---|---|
| `src/eitaa_bridge/reporting/model.py` | `Program` (هفت برنامهٔ canonical با کد مراسم `80403`)، `ReportedEvent`، `Fact` با `value_kind` و provenance، `UnitScope`، `OccasionClass` |
| `rules.py` | قواعد شمارش نسخه‌دار `workbook-1405-rules-v1`: زیارت عاشورا (C12)، مسابقهٔ داخل مراسم (C15)، تعریف نشست (C16)، شرط حضور مقام و استقلال عنوان تکریم/تشویق (B9/B10/C8)، دروازهٔ export مقدارها (ADR-42) |
| `aggregate.py` | تجمیع استانی: هر ردیف = جمع استان؛ breakdown واحد/رویداد برای ضمیمه؛ هشدار مقدار غیرقابل‌export |
| `forms.py` | هفت `QuestionnaireDefinition` نسخه‌دار (`1405-forms-v1`)؛ ستاره = «باید پر شود»؛ `human_gate` = پرسش اجباری از انسان؛ `prefill_form` از رویدادها پیش‌پر می‌کند |
| `eitaa_extraction.py` | استخراج محافظه‌کارانهٔ کاندید از متن پیام ایتا با کلمات کلیدی و نرمال‌سازی فارسی؛ در مبهمی abstain می‌کند |
| `excel_export.py` | نوشتن روی **کپی** workbook اصلی (هرگز فایل `SRC-IR-001` بازنویسی نمی‌شود)؛ ضمیمهٔ زیارت عاشورا؛ بلاک با `UnresolvedStarCellsError` |
| `service.py` | `ReportingService`: خط لولهٔ یکپارچه ایتا → رویداد → فرم → تجمیع → export |
| `tests/test_reporting_core.py` | ۳۶ تست: قواعد، تجمیع، فرم‌ها، دروازه‌ها، hash فایل اصلی، ضمیمه |

## خط لوله

```text
پیام ایتا ─(extractor)→ EventCandidate (پیشنهاد + provenance پیام)
   ↓ بازبینی ستاد
ReportedEvent + Fact(value_kind, provenance)
   ↓ aggregate (قواعد نسخه‌دار) + prefill فرم
FilledForm (بازبینی انسانی؛ پرسش‌های human_gate دست‌نخورده برای اپراتور)
   ↓ export_unified_report (کپی workbook)
Excel + ضمیمهٔ زیارت عاشورا  →  بازبینی/اصلاح نهایی انسانی
```

## مرزهای غیرقابل‌نقض

- فایل اصلی workbook فقط‌خواندنی است؛ export همیشه روی کپی است (ADR-53).
- مقدار `estimated`/`synthetic_placeholder` بدون تأیید صریح وارد آمار export نمی‌شود (ADR-42).
- `official_present` و `standalone_titled` هرگز خودکار حدس زده نمی‌شوند؛ فرم در زمان ورود از انسان می‌پرسد (Q-IR-011).
- رویداد = اتم ورودی شمارش است، نه ردیف workbook؛ ردیف همیشه جمع استان است (SRC-USER-IR-003/007).

## باقی‌ماندهٔ فاز بعدی

- UI فارسی فرم‌ها و اتصال زندهٔ Provider ایتا به extractor (سطح ۱ عملیاتی).
- نگاشت projection وردپرس از رویدادهای تأییدشده (سطح ۲).
- ثبت پایدار رویداد/فکت در SQLite و تاریخچهٔ تأیید.
- rebuild wheel تا تست پریتی بسته همیشه سبز بماند.

## افزودنی ۲۰۲۶-۰۹-۰۸: رصد ایتا، ایندکس‌گذار intent و بله (ADR-54)

| ماژول | مسئولیت |
|---|---|
| `reporting/indexer.py` | ایندکس‌گذار چندمعیاره: امتیازدهی اجرا/برنامه/عدد/واحد/مناسبت/آینده/تبلیغ؛ خروجی `IndexDecision` با شواهد کامل؛ سه کلاس `event_report`/`informational`/`promotional` |
| `reporting/monitor.py` | رصد گفتگوهای هدف («مدیریت امور فرهنگی دادگستری»، «رابطان فرهنگی دادگستری»)؛ خواندن فقط-خواندنی از `eitaa_core`؛ dedup رفرنس؛ پرهیز در نبود runtime |
| `reporting/bale_messaging.py` | فاساد ارسال/دریافت بله روی `application/bale_client`؛ تاریخچه → همان خط لولهٔ intent؛ خطای Provider امن‌شده |

جریان تازه: پیام ایتا/بله → `IndexDecision` (intent + امتیاز + شواهد) → کاندید رویداد با provenance → صف بازبینی ستاد → بقیهٔ خط لولهٔ V-190. تست‌ها: `tests/test_reporting_indexer.py` (۲۶ تست).

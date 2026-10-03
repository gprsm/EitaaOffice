# گزارش فاز دو — هستهٔ تراکنشی و دسترسی

* **شناسهٔ سند:** `PHASE2-UNIFIED-REPORTING-2026-10-03`
* **تاریخ:** ۲۰۲۶-۱۰-۰۳
* **سند حاکم:** [UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md](../specifications/UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md) (بخش ۹، فاز دو)
* **سند طراحی:** [REPORTING_TRANSACTIONAL_CORE_2026-10-03.md](../specifications/REPORTING_TRANSACTIONAL_CORE_2026-10-03.md) (`P2-DESIGN-2026-10-03`)
* **وضعیت:** `PHASE2_EXECUTED / GATE_GREEN`

## ۱. مصنوعات

| زیرمأموریت | مصنوع | کامیت |
|---|---|---|
| P2-A | سند طراحی هستهٔ تراکنشی (مالکیت، v6، etag، نقش‌ها، قرارداد API) | طراحی در کامیت طراحی فاز دو |
| P2-B | `src/eitaa_bridge/reporting/ownership.py` — اجارهٔ قفل فایلی با heartbeat/تصاحب stale (رفع F-104) + ۵ تست | `c11f4290` |
| P2-C1 | مهاجرت v6: `reporting_user_roles`، `reporting_audit_log`، ستون `version` روی رویدادها + نسخه‌آگاه‌سازی اسکریپت/تست‌های v5 | `87318ab4` |
| P2-C2 | متدهای تراکنشی store: استثناها، `_run_in_transaction` (BEGIN IMMEDIATE + retry قفل)، ممیزی، پیش‌نویس/ویرایش با etag، گذار وضعیت، پیوند شاهد تراکنشی، detach، صف، نقش‌ها | `7f700a3a` |
| P2-D | `src/eitaa_bridge/application/reporting_api_v3.py` (handlers خالص) + ادغام در dispatch تسویه‌حساب `api.py` | `c4808af5` |
| P2-E | `tests/test_reporting_phase2_gate.py` — ۷ تست دروازه | همین کامیت |

## ۲. نتایج دروازه (بخش ۹ سند حاکم)

| شرط دروازه | نتیجه | شاهد |
|---|---|---|
| هیچ گزارشی با ثبت ناقص یا شمارش دوباره | PASS — پیوند شاهد+صف+ممیزی+version در یک تراکنش؛ آزمون rollback در `test_rollback_on_witness_link_failure` (هیچ ردیف یتیم) | V-247 |
| دو کاربر هم‌زمان یکی از دو نتیجهٔ روشن | PASS — تعارض 409 با `current_etag` در `test_full_lifecycle_with_etag`؛ تعارض شاهد با قید DB | V-247 |
| پیام مشابه در دو حساب = دو شاهد مستقل | PASS — `test_two_concurrent_users_same_message` (accA/accB موفق؛ تکرار همان حساب → WitnessConflictError) | V-247 |
| editor نتواند approve کند | PASS — 403 در `test_conflict_resolution_requires_approver_role`؛ نقش‌ها فقط از جدول سمت سرور | V-247 |
| مجوزهای ممنوع | PASS — 403/404/400/409 نگاشت‌شده؛ بوت‌استرپ نقش‌ها فقط با جدول خالی و با ممیزی | V-247 |
| ممیزی تغییر | PASS — `reporting_audit_log` در همان تراکنش؛ `test_audit_trail_records_actions` (بدون PII در diff) | V-247 |
| بازیابی DB/رسانه | PASS — رزمایش rollback اسکریپت ایزوله با هش/نسخه (V-245 الگو)؛ رسانه (blob) به فاز سه موکول شد — جدول و API متادیتا آماده | V-247 |
| مجموعهٔ کامل سبز | PASS — pytest کامل (۰ شکست) + tsc + observability + checker حافظه؛ wheel محلی مجدداً بازتولید شد | V-247 |

## ۳. تصمیم‌های ثبت‌شدهٔ این فاز

1. **بوت‌استرپ نقش‌ها:** جدول `reporting_user_roles` در حالت خالی اجازهٔ نخستین تخصیص را می‌دهد (پاسخ 201، ممیزی `roles.set`)؛ پس از آن فقط admin. رفع بن‌بست «هیچ‌کس نقش ندارد» بدون نقض «بدون حدس».
2. **ادغام نقش سراسری:** `principal.global_role == "admin"` همان نقش‌های سه‌گانهٔ reporting را می‌گیرد (سازگار با کاربرد موجود global_role در api.py).
3. **رسانه:** ثبت متادیتای مدرک (sha256 الزامی) در فاز دو؛ سروکردن بایت‌های رسانه با کنترل مجوز به فاز سه — پیش از آن هیچ مسیر محتوایی فعالی نیست.
4. **عملیات واقعی DB:** مهاجرت‌های v5/v6 فقط‌افزودنی‌اند و هنگام next restart سرور روی DB واقعی اعمال می‌شوند؛ طبق RPO مصوب پیش از آن backup گرفته شود. اسکریپت ایزوله دوباره اجرا و PASS شد.

## ۴. ثبت چرخهٔ agy

* موفق: P2-A، P2-B (ماژول ۲۹۵ خطی آزاد نوشته شد)، P2-C2a/C2b (کد کامل در پرامپت)، P2-D1/D2، P2-E (۷ تست، بار اول سبز).
* شکست/اصلاح: P2-C2 اولیه timeout (شکست به C2a/C2b)؛ اصلاحیهٔ نسخه‌آگاه v5→v6 دو بار timeout → توسط ناظر اعمال و ثبت شد؛ نقص مشخصاتِ چک primary در link_witness در راستی‌آزمایی کشف و با یک راند اصلاحی به agy رفع شد.
* درس ماندگار: پرامپت agy هرگز inline با backtick در bash — همیشه فایل پرامپت؛ مأموریت‌های کدِ بلند با «کد کامل در پرامپت» یا شکستن به قطعات ≤۱۵۰ خط.

## ۵. شاهدان

* V-247 (دروازهٔ فاز دو)؛ کامیت‌های جدول بخش ۱؛ خروجی‌های v3.dispatch در تست‌های دروازه.

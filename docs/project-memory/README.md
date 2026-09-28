# حافظهٔ مهندسی پایدار Eitaa Bridge

وضعیت: مرجع اجباری پیش از بررسی دوبارهٔ کد یا اجرای آزمون  
ایجاد: ۲۰۲۶-۰۸-۱۳  
آخرین بازبینی: ۲۰۲۶-۰۸-۲۹

## ۱. هدف

این پوشه حافظهٔ مهندسی به‌روزشوندهٔ پروژه است. وضعیت کشف‌شده، تصمیم، محدودیت، بدهی فنی، نتیجهٔ آزمون و نقشه‌راه نباید فقط در گفت‌وگو باقی بماند. پیش از هر بررسی تازه باید ابتدا این فهرست و سند موضوعی مرتبط خوانده شود.

هدف این است که:

- بررسی یا آزمون معتبر بدون دلیل تکرار نشود؛
- دانسته‌های مربوط به UI، حساب‌ها، Providerها، استقرار و عملیات یک مرجع مشخص داشته باشند؛
- بعد از هر تغییر، همان بخش از حافظه به‌روزرسانی شود؛
- تفاوت میان «طراحی‌شده»، «پیاده‌سازی‌شده»، «آزموده‌شده با Fake» و «پذیرفته‌شده با حساب واقعی» روشن بماند؛
- هیچ نتیجهٔ مادی فقط در Chat نگهداری نشود.

## ۲. ترتیب مطالعهٔ اجباری

1. [گزارش جامع و نقشه‌راه](PROJECT_ENGINEERING_MEMORY_AND_ROADMAP_2026-08-13.md)
2. [برنامهٔ جامع تثبیت و رفع اشکال snapshot جاری](STABILIZATION_REMEDIATION_PLAN_2026-08-25.md)
3. [دفتر اجرای append-only تثبیت](STABILIZATION_EXECUTION_LOG.md)
4. [نقشه‌راه هوشمندسازی ایندکس و گزارش‌سازی](INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md)
5. [مدل عملیاتی چهارسطحی ایندکس و گزارش](INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md)
6. [قرارداد مدیریت توسعه و واگذاری میان Agentها](MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md)
7. [دفتر اجرای append-only ایندکس و گزارش](INDEX_INTELLIGENCE_EXECUTION_LOG.md)
8. [دفتر منابع و تعارض‌های ایندکس](INDEX_SOURCE_AND_CONFLICT_REGISTER.md)
9. [مرجع نرمال‌شدهٔ workbook برنامه‌های ۱۴۰۵](INDEX_1405_WORKBOOK_REFERENCE.md)
10. [دفتر پرسش‌ها و پاسخ‌های شفاهی دامنه](INDEX_DOMAIN_QUESTION_REGISTER.md)
11. [مدل پیشنهادی پرسشنامهٔ برنامه](INDEX_PROGRAM_QUESTIONNAIRE_MODEL.md)
12. [دفتر artifactهای بیرونی عامل‌های هوشمند](EXTERNAL_AGENT_ARTIFACT_REGISTER.md)
13. [Handoff جاری Codex/AntiGravity](../handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md)
14. [قرارداد همکاری Codex/AntiGravity](CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md)
15. [آخرین Handoff توقف موقت](../handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md)
16. [وضعیت پایهٔ فعلی](CURRENT_SYSTEM_BASELINE.md)
17. [دفتر یافته‌ها و تصمیم‌ها](FINDINGS_REGISTER.md)
18. سند موضوعی مرتبط:
   - [ممیزی لاگ‌گذاری و Observability](OBSERVABILITY_AND_LOGGING_AUDIT.md)
   - [نقشه‌راه چندحسابی و چندپیام‌رسانی](MULTI_ACCOUNT_PROVIDER_ROADMAP.md)
   - [Discovery و مرز انطباق Provider بله](BALE_PROVIDER_DISCOVERY.md)
   - [راهنمای توسعهٔ Provider مجاز](../PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md)
   - [مرز بیرونی ادامهٔ Phase 11](../reports/blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md)
19. [دفتر اعتبارسنجی‌ها](VALIDATION_LEDGER.md)
20. [پروتکل مستندسازی تغییرات](ENGINEERING_DOCUMENTATION_PROTOCOL.md)
21. برای تصمیم‌های کلان: [ARCHITECTURE_DECISIONS.md](../../ARCHITECTURE_DECISIONS.md)

## ۳. قاعدهٔ جلوگیری از بررسی تکراری

بررسی کد یا آزمون زنده فقط در یکی از وضعیت‌های زیر تکرار می‌شود:

1. فایل‌ها یا قراردادهای مؤثر بر یافته از زمان ثبت آن تغییر کرده باشند؛
2. نتیجه به محیط اجرا وابسته باشد و محیط یا Config تغییر کرده باشد؛
3. رخداد جدیدی با یافتهٔ ثبت‌شده تعارض داشته باشد؛
4. پذیرش واقعی یا عملیات پرخطر نیازمند شاهد تازه باشد؛
5. تاریخ اعتبار تعیین‌شده در دفتر اعتبارسنجی منقضی شده باشد؛
6. کاربر صریحاً تکرار آزمون را درخواست کند.

در غیر این صورت، پاسخ و توسعه باید بر پایهٔ این حافظه و گزارش‌های پذیرش موجود انجام شود.

## ۴. وضعیت‌های استاندارد

- `DECIDED`: تصمیم معماری پذیرفته شده است.
- `IMPLEMENTED`: کد موجود است، ولی لزوماً پذیرش واقعی نشده است.
- `FAKE_VERIFIED`: با Fake/Contract/Adversarial آزموده شده است.
- `LIVE_ACCEPTED`: با محیط یا حساب واقعی پذیرفته شده است.
- `PARTIAL`: بخشی موجود و بخشی باز است.
- `PLANNED`: فقط در نقشه‌راه است.
- `DEFERRED`: آگاهانه به مرحلهٔ بعد منتقل شده است.
- `BLOCKED`: مانع بیرونی یا نیاز قطعی به همکاری وجود دارد.

## ۵. قاعدهٔ به‌روزرسانی

هر تغییر مادی باید حداقل این آثار را داشته باشد:

- به‌روزرسانی سند موضوعی؛
- ثبت یا بستن یافته در `FINDINGS_REGISTER.md`؛
- ثبت آزمون یا دلیل اجرا نشدن آن در `VALIDATION_LEDGER.md`؛
- در صورت تغییر تصمیم کلان، به‌روزرسانی `ARCHITECTURE_DECISIONS.md`؛
- ثبت تاریخ، سطح شاهد و فایل‌های اثرپذیر.
- اجرای `scripts/check_project_memory_integrity.py`؛ برای متن آسیب‌دیده، حفظ provenance و منع بازسازی حدسی.

## ۶. مرز امنیتی

این حافظه نباید Credential، Cookie، Token، OTP، رمز، شمارهٔ کامل، متن خصوصی پیام، Access Hash، Session، IP عمومی، مسیر شخصی غیرضروری یا محتوای خام Support Bundle را ثبت کند. فقط Metadata امن، شناسهٔ opaque و مسیر نسبی پروژه مجاز است.

- [REPORTING_CORE_IMPLEMENTATION_2026-09-08.md](REPORTING_CORE_IMPLEMENTATION_2026-09-08.md) — هستهٔ گزارش ۱۴۰۵ پیاده‌سازی شد؛ رصد ایتا + ایندکس‌گذار intent + بله اضافه شد (ADR-53/54، F-070/071، V-190/191)
- [گزارش بازنشانی کامل نصب سرور](../reports/features/EITAA_SERVER_FULL_RESET_REPORT_2026-09-26.md) — جایگزینی نسخهٔ محلی، حذف state و توکن‌های پیشین، و مرز پذیرش گفت‌وگوها (F-080/F-082، V-212).
- [گزارش زیرساخت اتصال سامانهٔ آموزش/آزمون](../reports/features/EDUCATION_SYSTEM_M2M_INFRASTRUCTURE_REPORT_2026-09-27.md) — M2M محدود، resolve فقط‌خواندنی، داربست بله بات و درگاه عامل پس از اعتبارسنجی مستقل (F-083/F-084، V-213/V-214، ADR-59).
- [دستورهای تکمیل بله و کلاینت وب](../implementation-plans/bridge-client-2026-09-28/README.md) — مأموریت مستقل بله و نه فاز sender/limits/reservation/OTP/AI/client/Live/تحویل؛ فقط `PLANNED`، نه قابلیت پیاده‌شده (F-092، V-226).

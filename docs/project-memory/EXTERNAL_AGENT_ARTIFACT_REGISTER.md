# دفتر artifactهای بیرونی عامل‌های هوشمند

وضعیت: `ACTIVE / PROVENANCE_AND_CONFLICT_CONTROL`  
تاریخ آغاز: 2026-08-27  
هدف: جلوگیری از تبدیل plan/task/walkthrough ذخیره‌شده در حافظهٔ اختصاصی ابزارها به مرجع اجرایی پروژه.

## قاعدهٔ حاکم

1. تنها اسناد داخل `docs/project-memory` و تصمیم‌های متصل به Finding/Validation/ADR می‌توانند canonical باشند.
2. فایل‌های پوشهٔ اختصاصی Agentها، از جمله Antigravity brain، حافظهٔ همان ابزارند و به‌خودی‌خود مجوز، baseline، acceptance یا task جاری نیستند.
3. یک Agent پیش از اجرا باید `AGENTS.md` و ترتیب مطالعهٔ حافظهٔ پروژه را بخواند. اگر artifact بیرونی با مرجع canonical تعارض داشت، artifact بیرونی فقط historical/provenance است.
4. checkbox، عنوان «تکمیل شد»، timestamp یا خلاصهٔ metadata شاهد آزمون و پذیرش نیست.
5. artifact بیرونی مرتبط حذف نمی‌شود مگر duplicate بایت‌یکسان و بدون ارزش provenance باشد. روش پیش‌فرض: حفظ محتوا + هشدار superseded + پیوند مرجع canonical.
6. نقش‌ها vendor-neutral و در `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md` تعریف شده‌اند: کاربر مالک دامنه/پذیرش، Codex مدیر معماری و promoter canonical، و Agentهای دیگر مجری/پژوهشگر محدود به Task Contract هستند.

## Artifact Register

شناسهٔ نشست/مسیر خارجی در این سند mask شده است؛ تطبیق با hash انجام می‌شود.

| ID | نوع | SHA-256 پس از اصلاح | طبقه‌بندی | اقدام 2026-08-27 |
|---|---|---|---|---|
| EA-ART-001 | نقشه‌راه ۶ فازهٔ ایندکس | `FF7878B4...186EB182` | `SUPERSEDED / DO_NOT_IMPLEMENT` | هشدار canonical در Markdown و metadata افزوده شد؛ محتوا حفظ شد |
| EA-ART-002 | طرح اولیهٔ forced category/live learning | `4058AD7D...1838AFD4` | `SUPERSEDED / DO_NOT_IMPLEMENT` | هشدار افزوده شد؛ محتوا حفظ شد |
| EA-ART-003 | نقشهٔ ادعایی وضعیت توسعه | `E0532B57...AECFEB1` | `HISTORICAL / NOT_BASELINE` | هشدار افزوده شد؛ metadata اصلاح شد |
| EA-ART-004 | checklist تکمیل‌شدهٔ ادعایی | `AAE07167...BC4C9B5` | `HISTORICAL / NOT_ACCEPTANCE` | هشدار افزوده شد؛ checkboxها برای provenance دست‌نخورده ماندند |
| EA-ART-005 | walkthrough با ادعای «تکمیل شد» | `8B916EAF...BE3D8C8` | `SUPERSEDED_CLAIM` | عنوان تاریخی و هشدار عدم اتکا افزوده شد؛ metadata اصلاح شد |
| EA-ART-006 | implementation plan مربوط به Bale Bot | `93F31D6D...8538559` | `OUT_OF_INDEX_SCOPE / UNMODIFIED` | فقط در inventory دیده شد؛ بررسی/اصلاح نشد |
| EA-ART-007 | implementation plan مربوط به Phase 11-C | `0D98E505...EB22C5FF` | `OUT_OF_INDEX_SCOPE / UNMODIFIED` | فقط در inventory دیده شد؛ بررسی/اصلاح نشد |

## تعارض‌های خطرناک مهارشده

- forced-primary برای هر پیام با اصل `not relevant/abstention` و فاز صفر تعارض دارد.
- schema v4 و جدول‌های پیشنهادی پیش از مدل دامنه قطعی شده بودند.
- کدهای workbook به‌عنوان شناسهٔ قطعی دسته تلقی شده بودند؛ اکنون `80402/80403` باز است.
- daemon/thread ساعتی به‌عنوان «تکمیل‌شده» معرفی شده بود، در حالی که G-05 آن را به‌علت lifecycle/observability حذف و safe-default خاموش کرده است.
- ادعای «یک اصلاح و یادگیری برای همیشه» یا live retraining بدون corpus/evaluation/version/rollback معتبر نیست.
- category وردپرس، activity program، action، occasion و reporting metric در artifactهای قدیمی مخلوط شده بودند.

## مرجع جایگزین

- Roadmap: `INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md`
- Baseline: `CURRENT_SYSTEM_BASELINE.md`
- Source/Conflict: `INDEX_SOURCE_AND_CONFLICT_REGISTER.md`
- Workbook reference: `INDEX_1405_WORKBOOK_REFERENCE.md`
- Questions: `INDEX_DOMAIN_QUESTION_REGISTER.md`
- Four-level model: `INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md`
- Delegation governance: `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md`
- Findings: `F-051` تا `F-065`

## وضعیت IR-GOV-01

نسخهٔ سیاستی `IR-GOV-01 / POLICY_V1` پذیرفته و در `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md` ثبت شد: نقش‌ها، ownership فایل، Task Contract، handoff، review، promotion و منع دو writer تعریف شده‌اند. allocator/lock/merge queue ماشینی هنوز پیاده نشده و enforcement فعلی فرایندی است.

شاهد عملی 2026-08-27: دو task موازی، بدون اشتراک دامنهٔ محصول، هم‌زمان F-056/V-169/ADR-44 را در رجیسترهای مشترک مصرف کردند. checker collision را متوقف و task ایندکس به شناسه‌های تازه منتقل شد. بنابراین «ماژول‌های متفاوت» جای ownership فایل canonical و رزرو شناسه را نمی‌گیرد؛ F-059/V-172.

شاهد تکرار 2026-08-28: هم‌زمان با ثبت IR-GOV-01، task امضای داخلی F-064/V-186/ADR-50 را مصرف کرد. رکورد آن task حفظ و مدل چهارسطحی به F-065/V-187/ADR-51 منتقل شد. policy فرایندی ثبت شده، اما تا allocator/lock ماشینی، sole-writer باید در عمل enforce شود.

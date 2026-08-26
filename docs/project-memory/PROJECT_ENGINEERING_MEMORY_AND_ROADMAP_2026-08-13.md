# گزارش جامع حافظهٔ مهندسی و نقشه‌راه Eitaa Bridge

تاریخ: ۲۰۲۶-۰۸-۱۳  
وضعیت: مرجع فعال برای ادامهٔ توسعه  
دامنه: وضعیت فعلی، UI، چندحسابی، چندProvider، لاگ‌گذاری و مسیر آینده

## فصل ۱ — نتیجهٔ مدیریتی

معماری پایه برای `multi-user + multi-account-per-provider + multi-provider` طراحی شده و بخش‌های مهم جداسازی حساب، Worker، Session، داده، Job، Rate limit و Audit پیاده‌سازی و آزموده شده‌اند. بنابراین برای افزودن چند حساب ایتا، چند حساب بله و Providerهای آینده نیاز به بازنویسی پروژه از ابتدا نیست.

دو فاصلهٔ محصولی اولیه اکنون چنین به‌روزرسانی شده‌اند:

1. Onboarding چندحسابی ایتا در Phase 11-0 با UI/API امن و آزمون Fake تکمیل شده است؛ Pilot واقعی حساب دوم هنوز انجام نشده است.
2. Observability Foundation تکمیل و Event Catalog، پوشش UI/Electron و correlation برقرار شده‌اند؛ عملیات retention/disk health و Web metrics همچنان partial هستند.

اولویت توسعه طبق تصمیم جدید:

1. تکمیل Onboarding چندحسابی برای ایتا و Pilot واقعی حساب دوم؛
2. عمومی‌سازی قراردادهای Provider بدون حدس API؛
3. Discovery و Adapter بله؛
4. سپس Providerهای دیگر با استفاده از همان قرارداد و Contract Suite.

## فصل ۲ — حافظه به‌جای بررسی تکراری

از این تاریخ، سندهای این پوشه مرجع اول هستند. دانستهٔ معتبر تنها هنگامی دوباره از کد یا محیط زنده استخراج می‌شود که Triggerهای ابطال در [فهرست پوشه](README.md) برقرار باشند. هر توسعه باید در همان نوبت اسناد مربوط را به‌روز کند.

این سیاست به معنی حذف آزمون مهندسی نیست؛ به معنی اجرای هدفمند آزمون پس از تغییر مرتبط است. آزمون پذیرش معتبر تا وقتی ورودی‌ها و قرارداد اثرگذار تغییر نکرده‌اند دوباره اجرا نمی‌شود.

## فصل ۳ — وضعیت تثبیت‌شدهٔ محصول

- Phase 10-A تا 10-D کامل و گزارش نهایی Phase 10 پذیرفته شده است.
- ورود واقعی ایتا و نگهداری Session پذیرفته شده است.
- محیط فعلی یک حساب واقعی ایتا دارد.
- معماری و تست‌های Fake چندکاربر/چندحساب وجود دارند؛ Pilot واقعی حساب دوم تا مرحلهٔ استقرار نهایی به تعویق افتاده بود.
- UI دارای انتخاب‌گر «حساب پیام‌رسان» و پنل مدیریت حساب‌های موجود است.
- UI و API مسیر ساخت حساب جدید را دارند؛ ورود مستقل حساب دوم از flow حساب‌محور موجود پس از Start صریح استفاده می‌کند و Pilot واقعی آن هنوز اجرا نشده است.
- Adapter واقعی فقط برای ایتا وجود دارد؛ بله در Catalog شناخته شده ولی پیکربندی نشده است.
- Rubika، SoroushPlus و Telegram هنوز Adapter واقعی ندارند.

جزئیات و سطح شاهد در [CURRENT_SYSTEM_BASELINE.md](CURRENT_SYSTEM_BASELINE.md) ثبت شده است.

## فصل ۴ — جمع‌بندی لاگ‌گذاری

موارد موجود:

- Runtime log ساختاریافته و چرخشی در سطح Application؛
- Worker log مستقل هر MessengerAccount؛
- Correlation/Request ID؛
- Redaction بازگشتی برای Secret، شماره و محتوای خصوصی؛
- Diagnostics جزءبه‌جزء؛
- Audit پایدار، append-only و hash-chained؛
- Support Bundle محدود و اسکن fail-closed؛
- ثبت status، duration و error code برای درخواست‌های API.

نتیجهٔ ممیزی این است که «زیرساخت قوی است» ولی «پوشش کامل همهٔ رخدادهای مهم» هنوز قابل ادعا نیست. شکاف‌های اصلی و برنامهٔ بستن آن‌ها در [OBSERVABILITY_AND_LOGGING_AUDIT.md](OBSERVABILITY_AND_LOGGING_AUDIT.md) ثبت شده‌اند.

## فصل ۵ — تعریف درست ثبت رخداد

هدف، ثبت هر رخداد مادی است؛ نه ثبت بی‌حد هر کلیک، Payload یا محتوای خصوصی. حداقل رخدادهای الزامی عبارت‌اند از:

- Startup، readiness، shutdown و crash؛
- خطا و Warning غیرمنتظره در API، Worker، Provider، Electron و React؛
- تغییر وضعیت Authentication، Session، Account و Worker؛
- آغاز، موفقیت، شکست، retry، cancel و uncertain شدن عملیات بیرونی؛
- تصمیم Rate limit/Circuit breaker؛
- رویداد امنیتی، رد Authorization، CSRF/Host/Origin و Input نامعتبر مهم؛
- Backup/Restore/Support Bundle و تغییر Config؛
- هر عملیاتی که اثر بیرونی یا غیرقابل‌بازگشت احتمالی دارد.

ثبت Payload خام، Credential، متن پیام، شمارهٔ کامل یا Session ممنوع است.

## فصل ۶ — نقشه‌راه آینده

مسیر پیشنهادی و ثبت‌شده:

### ۶.۱. Observability Foundation

- تعریف Event Catalog و Schema نسخه‌دار؛
- یک API مشترک برای Log/Audit/Diagnostic؛
- Error Boundary و ثبت امن خطاهای React؛
- یکپارچه‌سازی Electron با JSONL و Correlation؛
- آزمون پوشش رخداد و آزمون عدم نشت Secret/PII؛
- سیاست Retention و Health لاگ.

### ۶.۲. Multi-account Onboarding Foundation

- API امن ساخت PhoneAccount/MessengerAccount؛
- State machine عمومی Auth با مرحله‌های Provider-specific؛
- Wizard افزودن حساب و Resume/Cancel/Recovery؛
- نام نمایشی، شمارهٔ ماسک‌شده، Provider و وضعیت Worker؛
- تعویض حساب بدون خروج از AppUser؛
- Logout/Re-auth مستقل هر حساب؛
- Pilot واقعی حساب دوم ایتا با تأیید لحظه‌ای.

### ۶.۳. Bale First

- Discovery مستند و بدون حدس API؛
- Adapter و Fake Contract Suite؛
- Capability matrix؛
- ورود واقعی فقط با اجازه و ورود خصوصی Credential؛
- Pilot محدود و سپس پذیرش.

### ۶.۴. Providerهای بعدی

Rubika، SoroushPlus، Telegram یا Provider دیگر باید بدون افزودن شرط‌های پراکنده به Core/UI و با Registry، Capability و Contract Suite مشترک اضافه شوند. هر Provider فقط ماژول Adapter، Auth flow، Error mapping و Capability declaration خود را اضافه می‌کند.

جزئیات در [MULTI_ACCOUNT_PROVIDER_ROADMAP.md](MULTI_ACCOUNT_PROVIDER_ROADMAP.md) آمده است.

## فصل ۷ — نتیجهٔ این نوبت

در این نوبت هیچ آزمون زنده، ارسال واقعی، ورود حساب، تغییر Config، شبکه، Firewall، Git stage/commit/push یا عملیات بیرونی انجام نشد. فقط ممیزی ایستای هدفمند لاگ‌گذاری و ایجاد حافظهٔ مهندسی انجام شد. نتیجه‌ها در دفتر یافته‌ها و دفتر اعتبارسنجی ثبت شده‌اند.

## فصل ۸ — وضعیت اجرای نقشه‌راه در 2026-08-13

- Observability Foundation: `IMPLEMENTED / AUTOMATED_VERIFIED`؛ Event Catalog، JSONL مشترک، correlation و پوشش Backend/Electron/React انجام شد.
- Observability Operations: `PARTIAL`؛ retention/disk health، migration کامل legacy و Web metrics باقی است.
- Multi-account Onboarding Foundation: `IMPLEMENTED / FAKE_VERIFIED`؛ ساخت اتمیک/idempotent، هویت DPAPI، owner membership، UI descriptor-driven و audit/log تکمیل شد. Pilot واقعی deferred است.
- Bale: Phase 11-A Discovery کامل شد. personal client به‌علت منع صریح API غیررسمی/مهندسی معکوس در شرایط رسمی `BLOCKED` است؛ API رسمی Bot/Arm مسیر محصولی جدا و نیازمند تصمیم کاربر است. onboarding بله غیرفعال باقی می‌ماند.
- Provider Extension Foundation: Phase 11-B0 `IMPLEMENTED / FAKE_VERIFIED`؛ قرارداد API v1، authorization/state gate، allowlist Registry، Worker factory، DTOهای محدود و Fake harness ساخته شده‌اند و full regression پذیرفته شد. slot بله فقط scaffold غیرفعال است و blocker مسیر Personal را رفع نمی‌کند.
- Multi-provider Core: Phase 11-B1 `IMPLEMENTED / FAKE_VERIFIED`؛ Registry پایدار، Coordinator v6، Contact v3، Audit عمومی، Fake سوم و Capability service حساب‌محور با full regression `540/540` تکمیل شدند. اجرای application در بعضی handlerهای v1 هنوز Eitaa-specific و مرز 11-B2 است.
- اسناد و نقشهٔ پروژه: `IMPLEMENTED`؛ `AGENTS.md`، درگاه docs، project specification/structure/logging و نقشهٔ ماشینی برقرار است.

گزارش اجرا: `../reports/features/OBSERVABILITY_FOUNDATION_REPORT_2026-08-13.md`، `../DOCUMENT_ORGANIZATION_2026-08-13.md`، `../reports/phases/PHASE11_0_MULTI_ACCOUNT_ONBOARDING_FOUNDATION_REPORT_2026-08-13.md`، `../reports/phases/PHASE11B_PROVIDER_EXTENSION_FOUNDATION_REPORT_2026-08-13.md` و `../reports/phases/PHASE11B1_MULTI_PROVIDER_CORE_REPORT_2026-08-13.md`.

## فصل ۹ — اولویت جاری پس از Phase 11-B1

1. 11-B2: انتقال orchestration عملیات عمومی Dialog/History/Send/Media/Contacts به Adapter contract؛
2. حفظ Eitaa به‌عنوان Adapter واقعی مرجع و عبور Fake سوم از همان مسیر بدون شبکه؛
3. اتصال UI به endpoint Capability حساب و fail-closed ماندن عملیات unsupported؛
4. Pilot واقعی حساب دوم ایتا فقط با اعلام آمادگی و ورود خصوصی کاربر؛
5. Bale فقط پس از ورودی رسمی/مجاز و بدون استفاده از client غیررسمی.

Registry/schema/audit/contact در B1 عمومی شده‌اند؛ این بخش‌ها برای Provider سوم دوباره ممیزی سراسری نمی‌شوند مگر Triggerهای ثبت‌شده تغییر کنند.

## فصل ۱۰ — به‌روزرسانی وضعیت در 2026-08-20

- Phase 11-B2: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED / NOT_LIVE`؛ شش operation عمومی، Eitaa Process RPC، Media/Contacts، media broker و receipt پایدار Coordinator v7 تکمیل شدند.
- آزمون‌ها: B2=`20/20`، مجموعهٔ مرتبط=`133/133` و full Backend=`561/561`؛ UI capability=`6/6`، onboarding=`7/7` و build موفق است.
- Phase 11-C: برای Bale Personal به API رسمی/اجازهٔ کتبی و برای Bale Bot/Arm به تصمیم account kind نیاز دارد؛ خودکار قابل ادامه نیست.
- Phase 11-D: بخش محلی capability/isolation کامل و ورود/read-live-sync حساب موجود ایتا پذیرفته است؛ Pilot واقعی حساب دوم Eitaa/Bale همچنان ورودی خصوصی/مجوز یا تصمیم مالک می‌خواهد.
- مرجع جاری: `CURRENT_SYSTEM_BASELINE.md`، گزارش `../reports/phases/PHASE11B2_PROCESS_RPC_MEDIA_CONTACT_PERSISTENCE_REPORT_2026-08-20.md` و blocker `../reports/blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md`.

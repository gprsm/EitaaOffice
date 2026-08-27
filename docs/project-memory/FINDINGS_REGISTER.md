# دفتر یافته‌ها و تصمیم‌های مهندسی

آخرین بازبینی: ۲۰۲۶-۰۸-۲۶  
قاعده: هیچ یافتهٔ مادی نباید فقط در Chat بماند.

## فصل ۱ — یافته‌های فعال

### F-001 — حافظهٔ مهندسی دائمی

- وضعیت: `DECIDED / IMPLEMENTED`
- تاریخ: ۲۰۲۶-۰۸-۱۳
- یافته: پراکندگی گزارش‌ها باعث بررسی دوبارهٔ وضعیت UI و کد می‌شد.
- تصمیم: `docs/project-memory` مرجع اول همهٔ ادامه‌هاست و فقط با Trigger ابطال بررسی تکرار می‌شود.
- اثر: همهٔ تغییرهای بعدی باید سند موضوعی و Validation ledger را به‌روزرسانی کنند.

### F-002 — تعویض حساب موجود در UI پیاده‌سازی شده است

- وضعیت: `IMPLEMENTED`
- شاهد: `MessengerAccountGate` و انتخاب‌گر حساب.
- محدودیت: نصب فعلی فقط یک حساب واقعی دارد؛ تعویض واقعی میان دو حساب هنوز `LIVE_ACCEPTED` نیست.

### F-003 — افزودن حساب جدید در UI/API

- وضعیت: `CLOSED / IMPLEMENTED / FAKE_VERIFIED`
- شدت: بالا برای هدف چندحسابی
- نتیجه: UI دارای Dialog خصوصی و API دارای Create اتمیک/idempotent با owner membership، سقف self-service، شناسه‌های server-owned و Audit/Log امن است.
- شاهد: `../reports/phases/PHASE11_0_MULTI_ACCOUNT_ONBOARDING_FOUNDATION_REPORT_2026-08-13.md` و V-016 تا V-019.
- باقی‌مانده: Pilot واقعی حساب دوم فقط با اعلام آمادگی و ورود خصوصی کاربر انجام می‌شود؛ این باقی‌مانده نقص معماری 11-0 نیست.

### F-004 — معماری چندProvider مناسب و تعمیم application مرحله‌ای است

- وضعیت: `CORE_GENERALIZED / APPLICATION_ORCHESTRATION_VERIFIED`
- یافته: علاوه بر هستهٔ عمومی 11-B1، در 11-B2 هر شش عملیات Dialog/History/Text Send/Media/Contacts برای Eitaa compatibility، Process Runtime و Fake از orchestrator و ترتیب امن واحد عبور می‌کنند.
- باقی‌مانده: مسیرهای richer legacy فقط تا وقتی قرارداد عمومی عمداً جزئیات آنها را پوشش نمی‌دهد حفظ می‌شوند؛ بدهی محلی Process/Media/Contacts بسته است. ادامهٔ باقی‌مانده Live و Provider مجاز است.
- تصمیم: هر slice باید route مجزا، compatibility کامل، Contract/Fake و مرز process روشن داشته باشد؛ مسیر نیمه‌مهاجرت‌یافته جایگزین legacy نمی‌شود.

### F-005 — پوشش لاگ‌گذاری کامل نیست

- وضعیت: `CLOSED / CURRENT_PROGRAM_SCOPE_AUTOMATED_VERIFIED / WEB_METRICS_DEFERRED`
- شدت: بالا
- یافته: Backend/Audit قوی است، اما React global errors، Electron structured correlation و Event coverage contract کامل نیستند.
- تصمیم: Observability Foundation پیاده شد و G-08 lifecycle/background، scanner چندحسابی، write-health، retention/disk و Support Bundle را تکمیل کرد. G-09 full Backend=`656/656` و UI/Electron Observability را دوباره پذیرفت. OBS-008 Web metrics برای deployment واقعی deferred است و Production-ready عمومی ادعا نمی‌شود.
- جزئیات: `OBSERVABILITY_AND_LOGGING_AUDIT.md`.
- Trigger بازگشایی: تغییر Event Catalog/logger/scanner/retention/Support Bundle/Electron/React یا آغاز deployment Web metrics.

### F-006 — raw targetPath در Electron باید sanitize شود

- وضعیت: `CLOSED / FIXED / AUTOMATED_VERIFIED`
- شدت: بالا از دید Privacy hardening
- یافته: خطای درخواست Desktop می‌تواند `targetPath` را مستقیم ثبت کند.
- تصمیم/نتیجه: فقط pathname امن ثبت می‌شود، Query/Fragment حذف و segment حساس opaque می‌شود. UI/Electron Observability در G-09-D سبز و full Backend جاری=`656/656` است.
- Trigger بازگشایی: تغییر Electron request proxy، `sanitizeRoutePath`، DesktopLogger یا diagnostic IPC.

### F-007 — اولویت Providerها

- وضعیت: `DECIDED`
- تصمیم: Eitaa اول، Bale دوم؛ Providerهای دیگر پس از تثبیت قرارداد مشترک.
- قید: هیچ API/Session/Capability برای Provider جدید حدس زده نمی‌شود.

### F-008 — تعریف «ثبت هر اتفاق»

- وضعیت: `DECIDED`
- تصمیم: همهٔ رخدادهای مادی، Errorها، Warningها و transitionهای امنیتی/عملیاتی ثبت می‌شوند؛ Payload خصوصی، هر کلیک و نویز کم‌ارزش ثبت نمی‌شوند.
- دلیل: قابلیت پشتیبانی، امنیت، کارایی و امکان جست‌وجوی مؤثر.

## فصل ۲ — یافته‌های بسته‌شده یا پذیرفته‌شده

### F-009 — Phase 10 تکمیل شده است

- وضعیت: `CLOSED / LIVE_ACCEPTED`
- شاهد: `../reports/phases/PHASE10_FINAL_ACCEPTANCE_REPORT_2026-08-13.md` و گزارش‌های 10-A تا 10-D.
- قاعدهٔ تکرار: فقط پس از تغییر قرارداد/Config اثرگذار یا پیش از عملیات استقرار واقعی.

### F-010 — جداسازی چندکاربر/چندحساب

- وضعیت: `CLOSED / FAKE_VERIFIED`
- شاهد: Phase 10-C3 و تست‌های Phase 7 تا 9.
- باقی‌مانده: Pilot واقعی حساب دوم، نه بازنویسی معماری.

## فصل ۳ — قالب ثبت یافتهٔ جدید

```text
### F-NNN — عنوان
- وضعیت: DECIDED | IMPLEMENTED | FAKE_VERIFIED | LIVE_ACCEPTED | PARTIAL | OPEN | DEFERRED | BLOCKED
- تاریخ:
- شدت:
- دامنه:
- یافته:
- شاهد:
- اثر:
- تصمیم/اقدام:
- Trigger ابطال:
- نتیجهٔ نهایی:
```

## فصل ۴ — به‌روزرسانی یافته‌ها در 2026-08-13

### F-011 — Observability Foundation و شکاف‌های پرخطر

- وضعیت: `IMPLEMENTED / AUTOMATED_VERIFIED`
- جایگزین وضعیت: F-005 از `OPEN` به `PARTIAL` و F-006 از `OPEN` به `CLOSED` تغییر می‌کنند.
- نتیجه: Event Catalog، schema مشترک JSONL، correlation، React/Electron error coverage، route sanitization و client diagnostic محدود پیاده شد.
- کشف حین پذیرش: تست پوشش ابتدا 43 رخداد literal legacy خارج از catalog یافت؛ همه ثبت شدند و regression guard دائمی اضافه شد.
- شاهد: `../reports/features/OBSERVABILITY_FOUNDATION_REPORT_2026-08-13.md` و V-011 تا V-013.
- باقی‌مانده: فقط Web metrics/alert وابسته به deployment در OBS-008؛ retention/disk health و مسیرهای مادی برنامه در G-08 بسته‌اند. هر legacy path آینده باید wrapper/catalog جاری را رعایت کند.
- Trigger ابطال: تغییر `event_catalog.py`، `runtime_logger.py`، Electron observability، client diagnostic route یا correlation header.

### F-012 — سازمان‌دهی و نقشهٔ پایدار پروژه

- وضعیت: `IMPLEMENTED / AUTOMATED_VERIFIED`
- نتیجه: 103 سند Markdown و 8 artifact/یادداشت از ریشه دسته‌بندی، ارجاع‌ها اصلاح و درگاه مستندات، AGENTS، مشخصات، ساختار، logging guide و project map اضافه شد.
- شاهد: `../DOCUMENT_ORGANIZATION_2026-08-13.md` و V-014.
- تصمیم: launcher/config/runtime در ریشه یا محل عملیاتی خود باقی می‌مانند؛ cacheها بدون مجوز حذف نمی‌شوند.
- Trigger ابطال: جابه‌جایی سند، تغییر generator یا اضافه‌شدن فایل ریشه بدون تعیین مالکیت.

### F-013 — اندازهٔ bundle اصلی UI

- وضعیت: `OPEN / NON_BLOCKING`
- شدت: متوسط؛ performance/maintainability
- یافته: code splitting صفحه‌های Settings/Contacts/Index و حذف dependency/CSS runtime قدیمی، chunk اصلی را از 894.38 kB به 785.60 kB minified کاهش داد؛ با این حال هنوز بالاتر از آستانهٔ پیشنهادی 500 kB است.
- اثر: blocker عملکردی Observability نیست، اما زمان بارگذاری Web و نگهداری bundle می‌تواند با رشد پروژه بدتر شود.
- اقدام آینده: تحلیل bundle و استخراج WordPress/composer و controllerهای سنگین باقی‌مانده؛ بدون شکستن shell و account scope مشترک.
- Trigger ابطال: تغییر import graph، Vite config یا اجرای bundle analyzer.

### F-014 — Multi-account Onboarding Foundation

- وضعیت: `IMPLEMENTED / FAKE_VERIFIED`
- شدت: قابلیت محصولی اصلی
- دامنه: Coordinator، AppAuth، API، Provider descriptor، UI و Observability.
- نتیجه: یک AppUser می‌تواند چند حساب Eitaa مستقل بسازد و بین cardهای مجاز جابه‌جا شود؛ retry/restart/race حساب تکراری نمی‌سازد و AppUser دیگر به هویت یا حساب دسترسی نمی‌گیرد.
- حریم خصوصی: شماره فقط در state کوتاه‌عمر UI و PhoneProtector است؛ DB، Runtime Log و Audit فقط ciphertext/fingerprint داخلی، hint پوشیده و metadata امن دارند.
- محدودیت آگاهانه: Bale فقط descriptor غیرفعال دارد؛ Pilot واقعی Eitaa دوم و هر ورود/ارسال واقعی انجام نشده است.
- شاهد: گزارش 11-0، پنج تست Python اختصاصی، هفت assertion UI و پذیرش دیداری Fake در Desktop/Mobile.
- Trigger ابطال: تغییر route ساخت حساب، PhoneProtector، transaction/uniqueness، Membership policy، descriptor یا UI onboarding.

### F-015 — Warning دکمهٔ غیرفعال داخل Tooltip

- وضعیت: `CLOSED`
- کشف: پذیرش دیداری Fake یک Warning مربوط به MUI گزارش کرد که Tooltip مستقیماً child غیرفعال داشت.
- اقدام: دکمهٔ Template در `QuickSendBar.tsx` داخل `span` قرار گرفت.
- شاهد: تب تازهٔ Development پس از اصلاح، صفر console error/warning گزارش کرد و build/type-check موفق بود.

### F-016 — API غیررسمی حساب شخصی بله با شرایط رسمی سازگار نیست

- وضعیت: `BLOCKED / DISCOVERY_COMPLETE`
- تاریخ: ۲۰۲۶-۰۸-۱۳
- شدت: بحرانی برای مسیر Bale Personal
- دامنه: دو ZIP محلی، مخزن Aiobale، مستندات و شرایط رسمی بله.
- یافته: کدهای غیررسمی قابلیت‌های personal client را نشان می‌دهند، اما شرایط رسمی بله استفاده از API غیررسمی/مهندسی معکوس را ممنوع و فقط API رسمی بازو را مجاز می‌کند.
- شاهد: `BALE_PROVIDER_DISCOVERY.md` و گزارش Phase 11-A.
- اثر: هیچ Bale personal adapter/transport/session/auth از این منابع وارد محصول نمی‌شود و onboarding بله غیرفعال می‌ماند.
- تصمیم: مسیر رسمی Bot/Arm فقط به‌عنوان account kind جدا و پس از تصمیم محصولی؛ مسیر personal فقط با API رسمی یا اجازهٔ کتبی.
- Trigger ابطال: انتشار API رسمی personal، مجوز کتبی، تغییر مادی شرایط، یا انتخاب صریح مسیر رسمی Bot.

### F-017 — مرز عمومی Provider آماده است، اتصال بله نیست

- وضعیت: `FOUNDATION_IMPLEMENTED / BALE_RUNTIME_BLOCKED`
- تاریخ: ۲۰۲۶-۰۸-۱۳
- شدت: معماری اصلی
- یافته: Provider Extension API v1، Manifest مجوزمحور، state gate، DTO محدود، allowlist Registry، Worker factory، Fake session store و contract harness ایجاد شده‌اند. Worker دیگر به شرط ثابت Fake/Eitaa متکی نیست و descriptor قابلیت/account kind/state را اعلام می‌کند.
- اثر: کد مجاز آینده می‌تواند در package اختصاصی Adapter قرار گیرد، بدون بازنویسی AppUser ownership، Account isolation، Coordinator، Worker IPC یا UI shell.
- مرز: slot بله factory، endpoint، transport، codec، credential، auth یا session implementation ندارد و state آن `scaffold` است. این یافته blocker F-016 را نمی‌بندد.
- بدهی B2 بسته‌شده در ۲۰۲۶-۰۸-۲۰: Child RPC حالت process، execution عمومی Media/Contacts و receipt پایدار mutation تکمیل شدند. بدهی باقی‌مانده فقط پذیرش Live/Provider مجاز است.
- شاهد: `../PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md`، تست Phase 11-B0 و گزارش مستقل.
- Trigger ابطال: تغییر Provider contracts/registry، Worker IPC، session ownership، Event Catalog یا authorization policy.

### F-018 — هستهٔ پایدار چندProvider و Capability تکمیل شد

- وضعیت: `CLOSED / IMPLEMENTED / FAKE_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۱۳
- شدت: معماری اصلی
- یافته: Coordinator schema v6 و Contact schema v3 از Provider registration پایدار و FK استفاده می‌کنند؛ Registry در startup به‌شکل افزایشی reconcile می‌شود و رکورد تاریخی حذف نمی‌شود. Audit filter، onboarding و worker start دیگر allowlist ثابت Eitaa/Bale ندارند.
- امنیت: observation حساب نمی‌تواند Capability اعلام‌نشده در Manifest را فعال کند؛ mismatch میان Manifest و Registry به‌صورت fail-closed رد می‌شود. Fake Provider در catalog محصول پنهان و فقط در آزمون opt-in است.
- شاهد: `tests/test_phase11b1_multi_provider_core.py` و گزارش `../reports/phases/PHASE11B1_MULTI_PROVIDER_CORE_REPORT_2026-08-13.md`.
- مرز: این پذیرش Contract/Fake است؛ DB عملیاتی در این نوبت migrate نشد، Provider network استفاده نشد و هیچ ورود/ارسال واقعی انجام نشد.
- Trigger ابطال: تغییر schema v6/v3، reconciliation، Capability enum/service/route map، audit provider filter، contact binding یا Fake Adapter.

### F-019 — قرارداد همکاری دوایجنتی برای worktree عمداً dirty

- وضعیت: `DECIDED / DOCUMENTED`
- تاریخ: ۲۰۲۶-۰۸-۱۷
- دامنه: واگذاری Phase 11-B2 میان Codex و Antigravity یا ایجنت آینده.
- یافته: نوشتن هم‌زمان دو ایجنت روی همان فایل‌ها، به‌ویژه Registry، API dispatch، migration، Event Catalog و اسناد generated، می‌تواند تغییرهای dirty مشروع را overwrite یا شاهد آزمون را مبهم کند.
- تصمیم: حالت پیش‌فرض «یک مالک نوشتن در هر بازه + بازبینی ترتیبی ایجنت دوم» است. اجرای موازی فقط با نقش reviewer فقط‌خواندنی، مجموعه‌فایل‌های از پیش جدا، یا کپی/محیط مستقل و تحویل patch محدود مجاز است.
- شاهد: `../handoffs/ANTIGRAVITY_PHASE11B2_HANDOFF_PROMPT_2026-08-17.md`.
- اثر: حافظهٔ مهندسی و handoff/report/diff کانال canonical تبادل‌اند؛ Chat به‌تنهایی حافظهٔ مشترک تلقی نمی‌شود.
- Trigger ابطال: تغییر سیاست مالکیت worktree، ایجاد سازوکار رسمی merge/snapshot، یا آغاز همکاری هم‌زمان با دامنهٔ فایل تازه.

### F-020 — Provider-neutral Application Orchestration و Process boundary کامل

- وضعیت: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: معماری/امنیتی اصلی
- یافته: orchestrator نام Provider را branch نمی‌کند، context حساب را فقط از resolver سرور می‌گیرد، Manifest را سقف Capability می‌داند، deadline/result را محدود و exception ناشناخته را sanitize می‌کند. هر شش operation Dialog/History/Text Send/Media/Contacts اکنون از همین مسیر عبور می‌کنند.
- یافتهٔ حین پیاده‌سازی: cache اولیهٔ idempotency پیش از authorization بازگشت داده می‌شد؛ این مسیر به داخل invocation پس از تمام guardها منتقل شد و replay پس از لغو دسترسی با تست رد می‌شود.
- Process: Child فقط method/fieldهای allowlisted و fence حساب/generation را می‌پذیرد؛ Parent result را دوباره محدود می‌کند. media path در Child باقی می‌ماند و فقط chunkهای محدود/پیوسته broker می‌شوند.
- Persistence: Coordinator schema v7 receiptهای Send/Contact را به actor و fingerprint bind می‌کند. replay پس از restart بدون provider call، payload/owner mismatch fail-closed و claim منقضی‌شده بدون retry `uncertain` است. payload خام در DB و کلید/fingerprint در log ذخیره نمی‌شوند.
- UI: snapshot قابلیت به شناسهٔ حساب انتخابی bind است؛ `restricted/unsupported/unknown/error/loading` همگی پیش از request به حالت غیرفعال می‌روند.
- شاهد: `tests/test_phase11b2_provider_neutral_orchestration.py` با 20/20، مجموعهٔ مرتبط 133/133، UI B2 با 6/6، full Backend با 561/561، build و privacy scan موفق.
- Trigger ابطال: تغییر orchestrator، Eitaa compatibility، Provider DTO/Manifest، routeهای v2، account capability UI یا Event Catalog.

### F-021 — ادامهٔ بخش‌های حساب دوم/Bale فاز ۱۱ نیازمند ورودی بیرونی است

- وضعیت: `PARTIAL_LIVE_ACCEPTED / EXTERNAL_DECISION_OR_PRIVATE_INPUT_REMAINS`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- دامنه: Pilot حساب دوم Eitaa، Bale Personal، Bale Bot/Arm و Pilot نهایی Phase 11.
- شاهد تازه: ورود واقعی حساب موجود ایتا و read/live-sync گفتگو/پیام با اجازهٔ مالک پذیرفته شد؛ هیچ ارسال یا دعوتی در این شاهد انجام نشد.
- مانع باقی‌مانده: Pilot حساب دوم ایتا به هویت/OTP خصوصی همان حساب نیاز دارد؛ Bale Personal تا API رسمی یا مجوز کتبی مسدود است؛ Bale Bot/Arm یک account kind جدا و نیازمند تصمیم صریح محصول است.
- تصمیم: هیچ transport/login/send غیررسمی اجرا نشود؛ پذیرش حساب موجود به حساب دوم یا Bale تعمیم داده نمی‌شود.
- شاهد: F-016، Discovery 11-A و `../reports/blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md`.
- Trigger ابطال: ورود خصوصی حساب دوم برای Pilot Eitaa، API/مجوز معتبر Bale Personal، یا انتخاب صریح Bale Bot/Arm.

### F-022 — بررسی نسخهٔ ۶ پیش از مهاجرت v7 جدول تازه را زودهنگام مطالبه می‌کرد

- وضعیت: `CLOSED / FIXED / REGRESSION_TESTED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: زیاد برای ارتقای نصب موجود
- کشف: آزمون مستقیم v6→v7 نشان داد `_verify_schema(expected_version=6)` به‌جای `REQUIRED_TABLES_V6` از مجموعهٔ جاری v7 استفاده می‌کرد و پیش از اجرای migration جدول receipt را مطالبه می‌کرد؛ در نتیجه ارتقای واقعی نسخهٔ ۶ fail-closed اما غیرقابل‌اجرا می‌شد.
- اقدام: `REQUIRED_TABLES_V6` به نگاشت verifier افزوده شد و آزمون اتمیک direct-upgrade، `foreign_key_check` و `quick_check` ثبت شد.
- شاهد: `tests/test_coordinator_schema.py::test_schema6_upgrades_atomically_to_persistent_provider_receipts` و full Backend `561/561`.
- اثر بیرونی: فقط DB موقت تست؛ DB عملیاتی migrate یا restart نشد.
- Trigger ابطال: تغییر schema version، required-table mapping، migration script یا initialize verifier.

### F-023 — ثبت‌نام خصوصی AppUser، رمز چهار نویسه‌ای و نشست یک‌ساله

- وضعیت: `CLOSED / IMPLEMENTED / AUTOMATED_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: قابلیت محصولی و امنیت نشست
- نتیجه: `/api/v2/app-auth/register` و دکمهٔ «کاربر جدید هستم» اضافه شدند. ثبت‌نام فقط در profileهای خصوصی loopback/LAN، با role ثابت `user` و وجود مدیر فعال انجام می‌شود و reverse-proxy عمومی fail-closed است.
- سیاست: حداقل رمز 4 نویسه و idle/absolute session هر دو یک سال؛ Cookie برابر 31536000 ثانیه است. PBKDF2-600000، throttle/lockout، CSRF، سقف طول/بایت، revoke و audit امن حفظ شده‌اند.
- Config: تغییر همین چهار مقدار در `bridge.json` با دستور صریح مالک انجام شد؛ هیچ secret، session واقعی یا حساب Provider تغییر نکرد.
- شاهد: full Backend `566/566`، آزمون پذیرش رمز چهار نویسه‌ای/role غیرمدیر، config fail-closed و قرارداد mobile-auth-live.
- Trigger ابطال: تغییر AppAuth policy، register route، deployment profile، cookie، AppUser Gate یا password validation.

### F-024 — رابط فعال Material-only، mobile-first و دریافت خودکار پیام

- وضعیت: `IMPLEMENTED / AUTOMATED_VERIFIED / NOT_LIVE_PROVIDER`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: معماری UI و تجربهٔ کاربری اصلی
- نتیجه: sourceهای فعال TSX بدون `className` یا import stylesheet اختصاصی‌اند و visual state فقط با Material UI و `theme/sx` ساخته می‌شود. Navigation، Conversation List، Chat Header، Settings، Contacts، Auth و Toast moduleهای مستقل‌اند.
- Mobile: shellهای صریح، safe-area، bottom navigation، Dialog تمام‌صفحه، چیدمان تک‌ستونه و touch target 44px با قراردادهای 360/390px پوشش دارند.
- Live: پیام گفتگوی باز و top/unread فهرست گفتگوها با polling تطبیقی account-scoped و merge بدون حذف رکوردهای قدیمی خودکار تازه می‌شوند؛ reload یا دکمهٔ بارگذاری پیام تازه لازم نیست. این near-real-time polling است و ادعای Push/WebSocket ندارد.
- شاهد: UI/Python هدفمند `65/65`، npm شماره‌دار `68/68`، observability و mobile-auth-live موفق، TypeScript/build موفق؛ full Backend `566/566`.
- Trigger ابطال: افزودن stylesheet/class، تغییر Theme/shell/module boundaries، تغییر dialog live-sync/message polling یا account scope.

### F-025 — پذیرش دیداری تازهٔ مرورگر محلی

- وضعیت: `CLOSED / REPLACED_BY_LOCAL_ELECTRON_VISUAL_ACCEPTANCE`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- سابقه: Browser درون برنامه localhost را با `ERR_BLOCKED_BY_CLIENT` بست و Chrome در دسترس نبود؛ هیچ bypass یا تغییر امنیتی انجام نشد.
- رفع محدودیت: fixture توسعه در Chromium خود Electron با viewport دسکتاپ 1280×800 و موبایل 390×844 اجرا، تصویر ثبت و مختصات RTL به‌صورت خودکار سنجیده شد. این شاهد Provider network، Login، Send یا WordPress را درگیر نکرد.
- نتیجه: جهت محاسبه‌شدهٔ `html/main` برابر RTL، ترتیب ستون‌ها از راست و ترتیب Avatar/Author/Action کارت پیام پذیرفته شد؛ کشوی بستهٔ موبایل نیز بیرون لبهٔ راست قرار گرفت.
- Trigger ابطال: تغییر layout/theme/RTL cache، Workspace grid، Message Card، Conversation drawer یا Electron/Vite fixture.

### F-026 — PID قدیمی Worker می‌توانست پس از استفادهٔ مجدد ویندوز Backend را متوقف کند

- وضعیت: `CLOSED / FIXED / REGRESSION_TESTED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: زیاد برای قابلیت اجرای نرم‌افزار
- کشف: Coordinator و `worker.lock` یک PID قدیمی را فعال نگه داشته بودند؛ PID زنده بود اما executable واقعی آن دیگر Python Worker نبود. بررسی قبلی فقط زنده‌بودن PID را ملاک مالکیت می‌گرفت و startup را با `eitaa_worker_process_alive` متوقف می‌کرد.
- اقدام: هویت executable در کنار liveness به‌صورت سه‌حالته بررسی می‌شود. mismatch قطعی مانند PID reuse بازیابی می‌شود، مالک Python معتبر حفظ می‌شود و وضعیت غیرقابل‌تشخیص همچنان fail-closed است. بازیابی Coordinator با reason امن `worker_process_pid_reused` audit می‌شود.
- شاهد: آزمون red/green چهار قرارداد PID-reuse، مجموعهٔ Process ownership برابر 25/25 و full/privacy regression ثبت‌شده در V-062 تا V-065.
- اثر بیرونی: وضعیت عملیاتی فقط‌خواندنی بررسی شد؛ restart، Provider network، Login، Session mutation یا پاک‌سازی دستی انجام نشد.
- جزئیات: `../reports/features/BACKEND_STARTUP_PID_REUSE_RECOVERY_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر Worker lease، liveness/executable probe، Coordinator recovery یا Provider Worker spawn.

### F-027 — کارت Material پیام و بازیابی خودکار نشست نامعتبر

- وضعیت: `CLOSED / IMPLEMENTED / AUTOMATED_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: تجربهٔ اصلی گفتگو و احراز هویت Provider
- پیام: نمایش هر پیام از `App.tsx` به module مستقل `MessageContentCard.tsx` منتقل شد و با `CardHeader/CardMedia/CardContent/CardActions/Collapse` ساخته می‌شود. نام نویسنده در Header است، مخاطب ایتا مشخص می‌شود و متن بلند expand/collapse دارد؛ رسانه، گالری، انتخاب، ایندکس و وضعیت WordPress حفظ شده‌اند.
- نام: نام دفترچهٔ محلی/ایتا اولویت دارد، اما عنوان عمومی `Eitaa` یا `ایتا` نام واقعی عضو/تاریخچه را نمی‌پوشاند. اگر نام واقعی محلی موجود نباشد، username یا fallback امن استفاده می‌شود.
- Auth: نشست دارای state قطعی `invalid` بدون نمایش عملیات archive بازیابی و سپس درخواست کد ورود خودکار می‌شود. Backend این حالت را برای نشست سالم رد می‌کند، backup را نگه می‌دارد، نام آن را در پاسخ automatic برنمی‌گرداند و reason امن ثبت می‌کند. OTP/رمز دوم دور زده نمی‌شوند.
- Login: panel بازاریابی/معماری حذف و Surface ورود Material در مرکز با عرض موبایل‌محور محدود شد؛ متن‌های فنی Session/backup از مسیر معمول حذف شدند.
- شاهد: red اولیه پنج شکست قرارداد و نبود component را ثبت کرد؛ هدفمند `24/24`، UI شماره‌دار `68/68`، TypeScript/build، full Backend `573/573` و اسکن ۹۱۲۹ رکورد با finding صفر موفق شدند.
- پذیرش دیداری: محدودیت پیشین F-025 با fixture محلی Electron و بدون Provider/Login واقعی بسته شد؛ مختصات کارت پیام در RTL به‌صورت خودکار پذیرفته شد.
- جزئیات: `../reports/features/MATERIAL_MESSAGE_CARD_AUTOMATIC_SESSION_RECOVERY_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر enrichment نویسنده، Contact priority، Message card، Auth state/reset/challenge یا Login surface.

### F-028 — drift راه‌اندازی Electron، فونت و مرز نشست در پذیرش زنده

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED / LIVE_READ_ACCEPTED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: زیاد برای اجرای Desktop و ورود واقعی
- Startup: اجرای development به‌اشتباه executable قدیمی را به Python module جاری ترجیح می‌داد و نسخهٔ hard-coded Electron نیز Backend سالم را ناسازگار تشخیص می‌داد. source اکنون module جاری را ترجیح می‌دهد و نسخه از `VERSION.txt` می‌آید؛ اجرای بسته‌بندی‌شده fallback محدود دارد.
- Font: دو فایل موجود IRANSans Regular/Bold از `MuiCssBaseline` فعال شدند و Theme مرکزی همچنان تنها مرجع typography است؛ مسیر نسبی در Electron `file://` و HTTP معتبر است.
- Auth: invalid شدن Eitaa دیگر CSRF نشست AppUser را پاک نمی‌کند. OTP فارسی/عربی و directional mark امن نرمال می‌شوند؛ خطاهای رایج Provider به کدهای allowlisted و پیام قابل اقدام نگاشت شده‌اند و resend تازه در UI موجود است.
- Live: ورود واقعی ایتا کامل شد و dialog/message sync حساب موجود به‌صورت پیوسته 200 داد؛ هیچ Send/Invite/WordPress در این پذیرش اجرا نشد.
- شاهد: V-073 تا V-078 و `../reports/features/LIVE_STARTUP_IRANSANS_AUTH_ACCEPTANCE_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر Electron runtime/version، Theme/font files، AppUser CSRF، auth challenge/OTP یا polling زنده.

### F-029 — اعمال دوبارهٔ direction در Workspace، رابط RTL را LTR کرده بود

- وضعیت: `CLOSED / FIXED / VISUALLY_AND_AUTOMATICALLY_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: زیاد برای تجربهٔ اصلی رابط فارسی
- کشف: `html` و Theme هر دو RTL بودند، اما Workspace دوباره در `sx` مقدار `direction: 'rtl'` می‌گرفت. `stylis-plugin-rtl` این declaration را آینه و جهت محاسبه‌شدهٔ `main` را LTR می‌کرد؛ بنابراین Navigation و Conversation List در سمت چپ و Avatar نویسنده در سمت نادرست قرار می‌گرفتند.
- اقدام: declaration تکراری حذف شد تا Workspace جهت root را به ارث ببرد. لبه و transform کشوهای موبایل نیز با inline-start/inline-end واقعی و تبدیل‌شدن Stylis هماهنگ شدند؛ Conversation از راست و Composer از چپ وارد می‌شوند.
- آزمون: قرارداد red ابتدا روی declaration تکراری و جهت قدیمی کشوها شکست خورد؛ سپس Phase 9 acceptance=`13/13`، همهٔ assertionهای شماره‌دار UI=`70/70`، TypeScript/observability/build، full Python=`580/580` و پذیرش تصویری Electron در 1280×800 و 390×844 موفق شدند.
- دامنه: هیچ Provider network، Login/OTP، Send/Invite، WordPress، Session/Config عملیاتی، migration/rollback یا تغییر Firewall/Proxy/Port/Certificate انجام نشد.
- جزئیات: `../reports/features/RTL_LAYOUT_REGRESSION_REPAIR_REPORT_2026-08-20.md`.
- Trigger ابطال: افزودن `direction` به سطحی زیر RTL Cache، تغییر grid/source order، mobile drawer edge/transform، Theme/Emotion RTL یا Message Card header.

### F-030 — پورت Backend محل تنظیم واحد و امن در UI نداشت

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED / LIVE_CONFIG_UNCHANGED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: متوسط برای راه‌اندازی وب و زیاد در صورت ویرایش دستی ناسازگار Host/Origin
- کشف: پورت فقط در config deployment قابل تغییر بود و کاربر محل واحدی در نرم‌افزار نداشت. تغییر دستی صرف bind port می‌توانست allowed Host/Origin را با پورت قبلی باقی بگذارد و startup یا same-origin را بشکند.
- اقدام: `DeploymentPortSettings` candidate کامل را پیش از write اعتبارسنجی، allowlist داخلی را هماهنگ، backup و replace اتمیک ایجاد می‌کند. API سراسری v2 مشاهده را از scope حساب پیام‌رسان جدا و mutation را به مدیر+CSRF+confirmation محدود می‌کند. UI فقط از Material component و `sx` استفاده می‌کند و نیاز restart/Proxy sync را نشان می‌دهد.
- ایمنی: پورت ۴۴۳ برای HTTP داخلی، مقدار boolean و خارج از بازه رد می‌شوند. Host/Origin عمومی Reverse Proxy دست‌نخورده می‌مانند. رخداد موفق/ردشده/شکست persistence، canonical، audit-required و correlationدار هستند؛ failure ساخت backup پیش از write فایل اصلی را دست‌نخورده می‌گذارد.
- شاهد: RED نبود سرویس و RED خطای خام PermissionError ثبت شدند؛ targeted نهایی `9/9`، full Python=`588/588`، UI شماره‌دار=`70/70`، TypeScript/observability/build موفق‌اند.
- دامنه: `bridge.json` واقعی، listener، Firewall، Laragon/Proxy و Certificate تغییر نکردند و سرویس واقعی restart نشد.
- جزئیات: `../reports/features/CENTRALIZED_DEPLOYMENT_PORT_SETTINGS_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر `HttpDeploymentConfig`، loader/serializer، API auth/CSRF، SettingsPage، HTTP bind، Reverse Proxy contract یا event catalog.

### F-031 — Bottom Navigation موبایل فهرست انتخاب‌شده را نشان نمی‌داد

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: زیاد برای موبایل
- کشف: `onSection={setTab}` فقط فیلتر را تغییر می‌داد و drawer بسته می‌ماند؛ آیکون Header نیز منوی مبهم بود.
- اقدام: `showDialogSection` tab را تنظیم، Composer را در موبایل می‌بندد و فهرست را باز می‌کند. فهرست زیر ۹۰۰px نمای اولیه است و Header Arrow بازگشت RTL دارد.
- شاهد: RED ایستا، TypeScript/build، UI شماره‌دار=`70/70` و full Python=`589/589` موفق‌اند.
- جزئیات: `../reports/features/MOBILE_CONVERSATION_NAVIGATION_MICROPHASE_2_1_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر `chatsOpen/chatsDocked/tab`، BottomNavigation، selectDialog، ChatHeader یا breakpoint.

### F-032 — Header موبایل وضعیت موفق بدیهی را تکرار و WordPress را نامتقارن می‌کرد

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED`
- تاریخ: ۲۰۲۶-۰۸-۲۰
- شدت: متوسط
- اقدام: عبارت «همگام‌سازی زنده» حذف شد؛ فقط اتصال/Retry موقت باقی ماند. WordPress با safe-area و touch target ۴۸px در inline-end، مقابل منوی inline-start قرار گرفت.
- شاهد: دو RED مستقل، targeted، TypeScript، Phase9، mobile-live، build و full Python=`590/590` موفق‌اند.
- جزئیات: `../reports/features/MOBILE_HEADER_MICROPHASE_2_2_REPORT_2026-08-20.md`.
- Trigger ابطال: تغییر ChatHeader، live state label، Workspace menu placement، breakpoint یا safe-area.

### F-033 — Bottom Navigation: برجسته‌سازی و تنظیم موقعیت گزینه «منتخب» در موبایل

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED`
- تاریخ: 2026-08-21
- شدت: تجربه‌کاربری / رابط‌کاربری
- اقدام: ایجاد `mobileSections` اختصاصی جهت مرتب‌سازی تب‌ها در BottomNavigation و اعمال `sx` شرطی جهت دایره‌ای و برجسته‌کردن آیکون `favorite`.
- شاهد: تست‌های RED اضافه شده به `run-phase9-workspace-tests.mjs` و پاس شدن 12/12، به همراه موفقیت کامل TypeScript و Observability.
- گزارش: `../reports/features/MOBILE_NAVIGATION_MICROPHASE_2_3_REPORT_2026-08-21.md`

### F-034 — Phase 3: Header Search Overlay, independent UsageInfoDialog, and WordPressIcon

- وضعیت: `CLOSED / FIXED / FULL_AUTOMATED_VERIFIED`
- تاریخ: 2026-08-21
- شدت: تجربه‌کاربری / رابط‌کاربری
- اقدام: توسعه HeaderMessageSearch، جداسازی UsageInfoDialog از Composer و تعویض سراسری PublicRounded.
- شاهد: تست‌های 3.1, 3.2 و 3.3 در `run-phase9-workspace-tests.mjs` همگی PASSED.
- گزارش: `../reports/features/PHASE_3_HEADER_COMPOSER_ICONS_REPORT_2026-08-21.md`

### F-035 — تصمیم تاریخی مسیر Bale Bot/Arm؛ رکورد اصلی آسیب‌دیده

- وضعیت: `RECOVERED_FROM_PARTIAL_EVIDENCE / HISTORICAL / SUPERSEDED_BY_F-046`
- تاریخ تصمیم تاریخی: 2026-08-21
- تاریخ بازیابی سند: 2026-08-25
- دامنه: انتخاب account kind و Adapter بله.
- منشأ بازیابی: متن اصلی این رکورد دچار جایگزینی نویسه و control character شده و بازسازی لفظ‌به‌لفظ ممکن نیست. این خلاصه فقط از قطعه‌های سالم همین رکورد، انتهای `BALE_PROVIDER_DISCOVERY.md` و تصمیم متأخر F-046 استخراج شده است.
- بخش قابل‌بازیابی تصمیم تاریخی: مسیر رسمی `Bale Bot/Arm API` از Personal Client جدا در نظر گرفته شده بود؛ ماژول مستقل `bale_bot` با احراز هویت Token و endpoint رسمی `https://tapi.bale.ai` مطرح شده بود.
- مرجع جاری: مطابق F-046 قرارداد متأخر Bale rollback نمی‌شود؛ در برنامهٔ تثبیت فعلی هیچ قابلیت تازهٔ Bale ساخته نمی‌شود و G-02 فقط implementation شکسته را آفلاین مهار و اصلاح می‌کند.
- مرز عملیات: این رکورد تاریخی مجوز اجرای Login/OTP/Session/Send/Capture نیست؛ هر عملیات Live نیازمند تأیید همان لحظه است.
- Trigger ابطال: دستور محصولی تازهٔ کاربر دربارهٔ نوع حساب Bale یا تغییر F-046.

### F-036 - نقشه‌راه بهبود سیستم ایندکس‌گذاری محلی (Index Intelligence Roadmap)

- **وضعیت:** PLANNED / DECISIONS_RECORDED
- **تاریخ:** 2026-08-22
- **حوزه:** سیستم ایندکس‌گذاری محلی
- **خلاصه:** در گفتگوی 2026-08-22 کاربر نیازمندی‌های جدید برای سیستم ایندکس را تعریف کرد. سه تغییر بنیادی در مبانی نظری نسبت به GMI2 پذیرفته شد:
  1. **دسته‌بندی اجباری:** هر پست گروه/کانال باید دقیقاً یکی از دسته‌های فعالیت اصلی را داشته باشد — uncertain برای scope این دسته‌ها مجاز نیست.
  2. **تاریخ متن > تاریخ ارسال:** تاریخ مرجع برای ایندکس باید از درون متن استخراج شود، نه timestamp ارسال.
  3. **هویت سازمانی فرستنده:** سیستم باید نگاشت «فرستنده → واحد سازمانی» را یاد بگیرد (مثال: احمد = واحد آمل).
- **تصمیم‌های قطعی:**
  - نتایج auto-index در MessageCard نمایش داده نمی‌شوند (گزینه B)
  - score و confidence از UI پنهان است؛ فقط نام دسته نمایش می‌یابد
  - چت‌های شخصی (PeerType.USER) از scope ایندکس خارج هستند
  - یادگیری هم تعاملی (feedback فوری) و هم batch (هر اجرای index) است
- **مرجع:** [implementation_plan.md](implementation_plan.md)
- **Trigger ابطال:** تغییر در content_index.py، content_index_service.py، content_index_store.py، ContentIndexDialog.tsx یا API endpoint ایندکس.

### F-037 - دسته‌بندی فعالیت اصلی: مستقل از وردپرس

- **وضعیت:** DECIDED / ARCHITECTURE_PENDING
- **تاریخ:** 2026-08-22
- **حوزه:** معماری سیستم ایندکس‌گذاری
- **خلاصه:** کاربر ۸-۹ دسته فعالیت اصلی سازمانی دارد که:
  - کاملاً مستقل از دسته‌بندی وردپرس هستند
  - کاربر باید بتواند آن‌ها را در UI تعریف، ویرایش و حذف کند
  - هر پست گروه/کانال **اجباراً** باید یکی از این دسته‌ها را داشته باشد
  - این دسته‌ها primary label برای classifier هستند
- **تفکیک معماری:**
  - index_activity_categories: جدول جدید در content_index_store.py — مستقل از WP
  - WP categories/tags: برای انتشار — اختیاری و جداگانه باقی می‌مانند
  - Classifier: primary label = activity category؛ secondary = WP category (اختیاری)
- **Schema پیشنهادی:**
  `sql
  CREATE TABLE index_activity_categories (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      name        TEXT NOT NULL UNIQUE,
      aliases     TEXT NOT NULL DEFAULT '[]',  -- JSON array
      description TEXT,
      is_active   INTEGER NOT NULL DEFAULT 1,
      sort_order  INTEGER NOT NULL DEFAULT 0,
      created_at  TEXT NOT NULL,
      updated_at  TEXT NOT NULL
  );
  `
- **UI مورد نیاز:** صفحه مدیریت دسته‌های فعالیت در Settings یا ContentIndexDialog
- **Trigger ابطال:** تغییر schema index_activity_categories یا منطق primary label در classifier.

### F-038 - صف بررسی نتایج auto-index در ContentIndexDialog

- **وضعیت:** DECIDED / UI_PENDING
- **تاریخ:** 2026-08-22
- **حوزه:** UI سیستم ایندکس‌گذاری
- **خلاصه:** نتایج auto-index در یک صف بررسی در ContentIndexDialog به کاربر نمایش داده می‌شوند. کاربر می‌تواند دسته‌جمعی تأیید یا رد کند.
- **ویژگی‌های UI:**
  - tab جدید «بررسی نتایج» در ContentIndexDialog
  - نمایش: خلاصه متن پیام + نام دسته پیشنهادی (بدون score)
  - دکمه تأیید/رد برای هر پیام + «تأیید همه» / «رد همه»
  - مرتب‌سازی داخلی بر اساس score (نزولی) — score به کاربر نشان داده نمی‌شود
  - «صادر به WP» برای پیام‌های تأییدشده
- **schema جدید در index_results:**
  `sql
  source_kind  TEXT NOT NULL DEFAULT 'manual'  -- 'manual' | 'auto'
  review_state TEXT NOT NULL DEFAULT 'accepted' -- auto: 'pending_review' | 'accepted' | 'rejected'
  `
- **Trigger ابطال:** تغییر ContentIndexDialog.tsx، index_results schema یا review API.

### F-039 — پوشهٔ AntiGravity2 فاقد تاریخچهٔ Git محلی است

- وضعیت: `MITIGATED / CRYPTO_BASELINED / GIT_HISTORY_CONNECTED / COMMIT_PENDING`
- تاریخ: 2026-08-25
- دامنه: انتقال پروژه از پوشهٔ قبلی به `AntiGravity2` و قابلیت ممیزی تغییرها.
- یافته: ریشهٔ جدید مخزن Git نیست، در حالی که پوشهٔ قبلی هنوز مخزن `main` با worktree عمداً dirty است. مقایسهٔ hash روی source/UI/tests/scripts/installer/docs، بدون داده‌ها و cacheهای عملیاتی، نسبت به پوشهٔ قبلی 94 فایل افزوده، 35 فایل تغییرکرده و 1 فایل حذف‌شده نشان داد.
- اثر: ادعای «ثبت کامل تغییرات» به اسناد و timestampها محدود شده و commit/diff canonical برای تغییرهای 2026-08-21 تا 2026-08-23 وجود ندارد.
- اقدام بعدی: پیش از توسعهٔ گسترده، کاربر باید مسیر حفظ تاریخچهٔ Git قبلی یا ایجاد baseline نسخه‌پذیر تازه را تعیین کند؛ هیچ Git mutation در این ارزیابی انجام نشد.
- Trigger ابطال: شناسایی یا ایجاد repository معتبر در ریشهٔ `AntiGravity2` و ثبت snapshot قابل بازگشت.
- به‌روزرسانی 2026-08-25 / G-00: repository با مالک صحیح ایجاد، شاخهٔ `stabilization` به commit تاریخی `legacy/main` متصل و baseline deterministic شامل 613 فایل امن ساخته/تأیید شد. داده‌های عملیاتی و artifactهای Bale خارج‌اند. stage/commit به‌دلیل نیاز به دستور صریح انجام نشده و تا آن زمان receipt/hash + Execution Log مرجع تغییر است.
- شاهد: `G00_TRACEABILITY_BASELINE_REPORT_2026-08-25.md`، V-108 و `STAB-G00-R01`.

### F-040 — فعال‌سازی Bale Personal در runtime فعلی شکسته و نیازمند مهار تثبیتی است

- وضعیت: `CLOSED / FAIL_CLOSED / FULL_BACKEND_VERIFIED / NO_NEW_DEVELOPMENT`
- تاریخ: 2026-08-25
- شدت: بحرانی
- دامنه: `providers/bale/slot.py`، `application/bale_provider_adapter.py`، onboarding عمومی و حافظهٔ Discovery بله.
- یافته: slot بله برخلاف Baseline و ابتدای سند Discovery به `LIVE_ACCEPTED`، `OFFICIAL_API` و runtime/onboarding فعال تغییر کرده، اما reference آن به مستندات client غیررسمی اشاره دارد. factory به module ناموجود `eitaa_bridge.providers.application` import می‌کند و در probe آفلاین با `ModuleNotFoundError` شکست خورد. Adapter نیز چند عملیات را پس از network call به نتیجهٔ خالی نگاشت می‌کند، session را بدون probe معتبر authenticated می‌پذیرد و در send متن خام exception را وارد خطای عمومی می‌کند.
- اثر: صرف‌نظر از مبنای توسعهٔ پذیرفته‌شده توسط کاربر، نمایش `live_accepted` برای implementationای که factory آن ساخته نمی‌شود قابل اتکا نیست و capability/observability را دور می‌زند.
- تصمیم کاربر در 2026-08-25: آخرین قرارداد امنیتی/توسعه‌ای Bale معتبر تلقی می‌شود و قراردادهای متأخر دیگر rollback نمی‌شوند؛ بااین‌حال این برنامه فقط مهار و رفع خرابی موجود است و هیچ قابلیت تازه یا عملیات Live بله در دامنه ندارد.
- تصمیم تثبیتی: تا سبزشدن contract/adversarial آفلاین، هیچ Login/OTP/Session/Send/Capture بله اجرا نشود و runtime/onboarding شکسته fail-closed بماند.
- Trigger ابطال: مهار مسیر شکسته، همسوسازی metadata با قرارداد پذیرفته‌شده و پذیرش کامل آفلاین؛ پذیرش Live همچنان نیازمند دستور همان لحظه است.
- نتیجهٔ G-02 در 2026-08-25: تصمیم F-046 با `authorization_reference=document:F-046` حفظ شد، اما state به `implemented` و `configured/runtime/onboarding=false` تغییر کرد؛ capability/auth step تبلیغ نمی‌شود و Adapter/Worker factory وجود ندارد. compatibility class آداپتر ناقص نیز پیش از هر client/session/network با `provider_adapter_not_configured` رد می‌شود.
- شاهد: تست RED مستقل `4/4 failed` پس از اصلاح setup؛ GREEN اختصاصی `5/5`، مجموعهٔ مرتبط `21/21`، Backend کامل `599/599`، TypeScript/Observability و UI B2=`6/6` سبز. هیچ عملیات Live/Network اجرا نشد.
- Trigger تازه: هر تلاش برای روشن‌کردن configured/runtime/onboarding، افزودن factory/capability، import کردن `bale_client` از مرز Adapter یا دستور توسعهٔ تازهٔ کاربر.

### F-041 — blockerهای نصب تمیز و Legacy Auth بسته شدند

- وضعیت: `CLOSED / G-03 COMPLETE / SYNTHETIC_OFFLINE_ACCEPTED`
- تاریخ: 2026-08-25
- شدت: زیاد برای portability
- یافتهٔ اولیهٔ بسته‌شده: startup با AppUser Auth نبود Coordinator DB را با `app_auth_coordinator_missing` رد می‌کرد و Legacy auth summary را بدون `challenge_id` برمی‌گرداند، در حالی که UI وجود آن را اجباری می‌دانست.
- اثر پیشین: نصب تازه بدون DB/config/session موجود می‌توانست پیش از ورود یا بلافاصله پس از ارسال OTP متوقف شود.
- پیشرفت G-03-A در 2026-08-26: پیش از ازسرگیری، SHA-256 هر چهار فایل محصول دقیقاً با handoff توقف تطبیق داده شد. اجرای نخست پس از patch برابر `4 collected / 3 passed / 1 failed` بود؛ failure با `CHECK` طول salt/digest به test double مصنوعی و نه منطق محصول مربوط بود. فقط fixture آزمون از material کوتاه به byte-array مصنوعی با طول معتبر schema تغییر کرد. retry مستقل با basetemp تازه `4/4 passed` شد.
- وضعیت پس از G-03-A در آن زمان فقط چهار قرارداد اختصاصی سبز بود؛ مراحل B تا E سپس regression مرتبط، adversarial/restart، full Backend و معیارهای installer/startup را تکمیل کردند.
- پیشرفت G-03-B در 2026-08-26: چهار suite مرتبط `test_app_user_auth.py`، `test_app_user_api.py`، `test_account_runtime.py` و `test_application_api.py` در یک اجرای ایزوله `57/57 passed` شدند. هش چهار فایل محصول و چهار فایل آزمون پیش و پس از اجرا یکسان بود؛ در این زیرمرحله هیچ اصلاح source/test لازم نشد.
- پیشرفت G-03-C در 2026-08-26: پنج قرارداد adversarial/restart افزوده شد. RED معتبر `5 collected / 4 passed / 1 failed` نشان داد پس از restart، submit روی challenge گم‌شده Provider را فراخوانی نمی‌کند اما رکورد چندحسابی را در `challenge_pending` رها می‌کند. guard مرکزی Account challenge اصلاح شد تا فقدان runtime را audit کرده و همان generation را بدون افزایش نسل به `expired` منتقل کند. GREEN اختصاصی `5/5` و regression مرتبط شامل clean-install، چرخهٔ AccountAuth و suiteهای G-03-B برابر `81/81` شد.
- قراردادهای سبز G-03-C: restart و پاک‌سازی runtime/challenge معلق Legacy، انقضای terminal مرحلهٔ password و منع replay، supersession درخواست قدیمی، رد stage/شناسهٔ خصمانه بدون Provider/echo، و reconciliation رکورد چندحسابی پس از restart. `git diff --check` هدفمند نیز با مسیر صریح worktree سبز شد.
- پیشرفت G-03-D در 2026-08-26: Backend کامل نخست `608 collected / 607 passed / 1 failed` شد؛ failure مستقیماً به G-03 مربوط بود و دو event جدید `auth_challenge_denied` و `auth_challenge_expired` را خارج از Event Catalog یافت. هر دو با category احراز هویت، result=`rejected` و `audit_required=true` ثبت شدند. observability هدفمند `6/6` و retry کامل Backend `608/608` سبز شد؛ TypeScript check و UI/Electron observability نیز exit code صفر دارند.
- آزمون Phase 11 onboarding عمداً تکرار نشد: شکست allowlist آن در F-042/G-06 ثبت شده، کد مرتبط در G-03 تغییر نکرده و trigger بررسی مجدد وجود نداشت. `git diff --check` هدفمند سبز است.
- نتیجهٔ G-03-E: شکاف شاهد startup تکراری و installer rehearsal ایزوله کشف و با `2/2 passed` بسته شد؛ Backend نهایی پس از افزودن این acceptanceها `610/610` است. گزارش نهایی در `../reports/stabilization/G03_CLEAN_INSTALL_AUTH_STABILIZATION_REPORT_2026-08-26.md` قرار دارد.
- Trigger بازگشایی: تغییر bootstrap Coordinator/AppAuth، empty runtime selection، قرارداد challenge شناسه/stage/TTL/restart، config-copy نصب‌کننده یا Event Catalog احراز هویت.

### F-042 — اعتبارسنجی و بسته‌بندی snapshot جدید drift دارد

- وضعیت: `CLOSED / G-06_TEST_CONTRACT_AND_G-07_PACKAGING_VERIFIED / OFFLINE_AUTOMATED_ACCEPTED`
- تاریخ: 2026-08-25
- شدت: زیاد
- یافته: Backend جاری 587 تست جمع‌آوری کرد؛ 585 موفق و 2 تست به‌علت BOM در Bale slot شکست خوردند. دو contract UI دیگر نیز شکست خوردند: Phase 10 پس از انتقال helper به module جدید به‌روز نشده و Phase 11 تغییر allowlist onboarding از phone-only به پذیرش token را رد می‌کند. تابع بسته‌بندی تمیز نیز allowlist انتشار ندارد و فایل‌های scratch/backup/prompt و JSONهای probe خارج از پوشه‌های حذف‌شده را می‌تواند داخل ZIP قرار دهد.
- اثر: گزارش `PROJECT_FINALIZATION_REPORT_2026-08-21.md` که وضعیت بدون regression و آمادهٔ deployment را اعلام می‌کند، برای snapshot فعلی معتبر نیست.
- Trigger ابطال: سبزشدن suite کامل و همهٔ contractهای UI، حذف/قرنطینهٔ artifactهای غیرمحصول از release manifest و اجرای clean-package privacy scan.
- به‌روزرسانی G-03-E: Backend کامل جاری پس از دو acceptance تکمیلی برابر `610/610` است؛ TypeScript و UI/Electron observability نیز سبزند. Phase 11 onboarding هنوز روی assertion قدیمی allowlist و Phase 10 روی محل قدیمی helper شکست می‌خورند و بدون trigger تکرار نشدند؛ packaging نیز تا G-07 باز است.
- به‌روزرسانی G-04-C: Trigger مرتبط با onboarding فعال و drift آن بسته شد. token از allowlist عمومی حذف، phone validator به E.164 محدود و قرارداد Phase 11 onboarding برابر `7/7` سبز شد. F-042 همچنان برای Phase 10 helper drift و packaging تا G-06/G-07 باز است؛ full Backend بعداً در V-121 برابر `620/620` سبز شد.
- ممیزی G-06-A: شکست‌های Bale BOM در G-02 و Phase 11 onboarding در G-04 بسته باقی‌اند. تنها RED جاری test contract، Phase 10 است که پنج assertion را می‌گذراند و سپس به‌جای import واقعی helper دنبال تعریف قدیمی داخل `App.tsx` می‌گردد. هشت runner دیگر exit code صفر دارند.
- guard تازهٔ Python: empty test contract صفر و skip/xfail نامعتبر صفر؛ یک skipif ویندوزی reason صریح دارد. قرارداد import Phase 10 عمداً RED است (`2/3 passed`, `1/3 failed`). packaging به‌طور رسمی خارج از patch G-06 و در G-07 باقی می‌ماند.
- اصلاح G-06-B: runner فایل واقعی `utils/helpers.tsx` را می‌خواند، import در App و export canonical را با `assert.ok` و پیام محدود می‌سنجد و دیگر برای این assertion کل source را actual نمی‌کند. guard=`3/3`، Phase10=`7/7`، مرتبط=`66/66` و mobile-auth static سبز است؛ کد محصول/helper تغییر نکرد.
- شاهد G-06-C: هر ۹ runner رابط کاربری exit code صفر دارند؛ Phase10=`7/7`، onboarding=`7/7`، TypeScript و build محلی Vite نیز سبزند. build فقط هشدار غیرمسدودکنندهٔ chunk بزرگ‌تر از 500 kB داد. package/installer مطابق مرز G-07 اجرا نشد.
- شاهد G-06-D: دامنهٔ گستردهٔ ۳۵ suite مرتبط Application/Auth/Privacy/Observability/Content/UI phases برابر `307/307 passed`، failure/error/skip صفر؛ collect-only مستقل نیز 307. یک PytestCacheWarning مجوزی غیرمحصولی ثبت شد. suite کامل به E و packaging به G-07 تعلق دارد.
- closure دامنهٔ تست در G-06-E: full Backend در اجرای نخست `628/628 passed` با failure/error/skip صفر؛ collect-only نیز 628. همهٔ ۹ runner UI، TypeScript و build شاهد جاری C هستند و پس از آن هیچ source/test/UI تغییر نکرد. empty test صفر و skip/xfail بی‌دلیل صفر است. بخش packaging این Finding تا G-07 باز می‌ماند و release readiness اعلام نمی‌شود.
- ممیزی G-07-A: `package_clean.py` دارای BOM/encoding UTF-16LE و 1826 بایت NUL از 3654 بایت است و Python آن را import نمی‌کند. با loader صرفاً ممیزی، رفتار blacklist روی درخت مصنوعی ثابت کرد `prompt_out.txt` و `probe.json` وارد ZIP می‌شوند. RED canonical=`0/8`: encoding، allowlist، dry-run/determinism، privacy و سه traversal case همگی شکست خوردند یا API لازم را نداشتند.
- اصلاح G-07-B: packager اکنون UTF-8، بر پایهٔ فایل‌ها/scopeهای سفید صریح، دارای manifest داخلی، receipt بیرونی، timestamp ثابت ZIP، hash هر entry، dry-run بدون write، scan کلید خصوصی/JWT و verifier نام/duplicate/collision/traversal/size است. targeted=`8/8` و مرتبط=`21/21`. dry-run واقعی 296 فایل انتخاب و صفر خروجی ایجاد کرد؛ archive واقعی به C موکول است.
- شاهد G-07-C: guardهای collision/tamper/atomic-output افزوده و adversarial=`11/11` شد. دو archive مستقل در artifacts هرکدام 2,031,927 بایت و SHA-256=`3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903` دارند؛ manifest=296، forbidden top-level=0، collision=0 و receiptها با hash منطبق‌اند. fresh-install rehearsal به D تعلق دارد.
- شاهد G-07-D: guard wheel/source parity، stale wheel واقعی را با missing=57/mismatched=20 رد کرد. نخستین fresh venv نیز `pip check` را با سه dependency صرفاً متعلق به client قرنطینه‌شدهٔ Bale شکست داد. release/wheel اکنون `application/bale_client` را حذف ولی fail-closed slot را حفظ می‌کند؛ metadata فقط dependencyهای runtime جاری را دارد. wheel نهایی deterministic با 90 source file و صفر drift؛ archive=282؛ fresh venv/runtime checker/pip check/import سبز و related=`102/102`. closure نهایی به E تعلق دارد.
- closure G-07-E: full Backend در اجرای نخست=`643/643 passed` و skip صفر؛ TypeScript و UI/Electron Observability سبز. دو archive نهایی پس از هم‌سویی اسناد منتخب release بایت‌یکسان، manifest/receipt/verifier و forbidden scan سبزند. test drift و packaging هر دو بسته‌اند؛ F-042 بسته است. این closure نصب/امضا/انتشار واقعی یا release readiness کل پروژه را اعلام نمی‌کند.
- Trigger بازگشایی: تغییر allowlist، recursive release scope، dependency/pyproject، wheel builder، source package، installer layout، Bale quarantine، content scanner/verifier یا فایل منتخب release.

### F-043 — worker خودکار ایندکس بدون lifecycle و observability کافی اضافه شده است

- وضعیت: `CLOSED / G-05_COMPLETE / OFFLINE_AUTOMATED_ACCEPTED`
- تاریخ: 2026-08-25
- شدت: متوسط تا زیاد
- یافته: API هنگام startup یک thread ساعتی و نامحدود آغاز می‌کند؛ stop/join در `close()` ندارد و تمام exceptionها را بدون Event/Audit با `except Exception: pass` می‌بلعد.
- اثر: failureهای ایندکس قابل مشاهده نیستند، shutdown کامل نیست و ادعای «ثبت رخدادهای مادی» نقض می‌شود.
- شاهد G-05-A در 2026-08-26: چهار contract آفلاین ایجاد شد؛ manual index برابر PASS، اما scheduler safe-default، event cataloged/correlated و حذف loop شکسته هر سه RED شدند (`1/4 passed`, `3/4 failed`). thread کنترل‌شده پس از ثبت failure release/join شد و orphan آزمون باقی نماند.
- تصمیم اجرای G-05: مطابق مسیر امن برنامه، scheduler ناقص فعلاً fail-closed/disabled می‌شود و APIهای manual index بدون تغییر حفظ می‌شوند. فعال‌سازی دوباره در آینده نیازمند feature/config و قرارداد scheduler مستقل است.
- شاهد G-05-B: startup thread و `_run_auto_indexer` حذف شدند؛ event `content_auto_index_scheduler_skipped` با correlation و reason امن catalog شد. اختصاصی=`4/4` و regression API/content-index/account-runtime/observability/clean-install=`76/76` سبز است.
- شاهد G-05-C: سه چرخهٔ start/close هیچ `bridge-auto-indexer` تازه‌ای باقی نگذاشت؛ هر startup یک event با correlation یکتا و فقط metadata allowlisted ثبت کرد. G-05+Observability برابر `11/11` سبز شد.
- شاهد G-05-D: regression گسترده ۱۴ suite مرتبط lifecycle/API/content-index/diagnostics/Phase10/11 برابر `143/143` سبز شد؛ هیچ source/test تغییر نکرد و full Backend به E موکول است.
- شاهد G-05-E: full Backend در اجرای نخست `625/625`، TypeScript و UI/Electron Observability exit code صفر. هش نهایی کد با B/C ثابت و هیچ regression یا retry رخ نداد.
- closure: scheduler ناقص حذف و safe-default صریح/قابل‌مشاهده است؛ manual index حفظ؛ هیچ background account scope یا failure خاموش باقی نیست. فعال‌سازی آینده فقط با feature/config و قرارداد scheduler مستقل مجاز است.
- Trigger ابطال: lifecycle کنترل‌شده، account scope روشن، Event Catalog/Correlation، failure tests و acceptance ایزوله.

### F-044 — قرارداد متأخر نمایش کامل شماره و شاهد مستقل redaction تکمیل شد

- وضعیت: `CLOSED / G-04_COMPLETE / OFFLINE_AUTOMATED_ACCEPTED`
- تاریخ: 2026-08-25
- شدت: زیاد
- یافتهٔ اولیه: تابع `masked_phone()` برای هویت E.164 مقدار کامل را برمی‌گرداند و دو تست `test_bootstrap_rejects_display_hint_with_too_many_digits` و `test_phone_mask_never_contains_the_full_number` به بدنهٔ خالی `pass` تبدیل شده‌اند. ناهم‌ترازی متنی Baseline/Specification در G-01 اصلاح شد، اما شاهد رفتاری خالی باقی ماند.
- شاهد G-04-A در 2026-08-26: آزمون مستقل تازه با سه قرارداد اجرا شد. حفظ مقدار canonical در مرز مجاز محصول سبز بود؛ تشخیص دو placeholder و حذف مقدار کامل زیر کلیدهای `phone_hint`/`display_hint` هر دو به‌طور هدفمند قرمز شدند. علت redaction این است که allowlist فعلی کلیدهای تلفن این دو identity hint را پوشش نمی‌دهد.
- شاهد G-04-B در 2026-08-26: دو تست با نام‌های منقضی حذف و با assertionهای واقعی پذیرش display hint کامل و حفظ canonical در مرز محصول جایگزین شدند؛ guard مانع بازگشت نام/قرارداد masking است. `phone_hint` و `display_hint` به redaction مشترک افزوده شدند. آزمون اختصاصی `3/3` و regression مرتبط schema/diagnostics/observability برابر `28/28` سبز است.
- شاهد G-04-C در 2026-08-26: دو RED Backend ثابت کردند validator تلفن token-shaped identity را می‌پذیرفت و endpoint عمومی آن را تا PhoneProtector عبور می‌داد؛ contract UI نیز روی allowlist شکست خورد. پس از اصلاح، validator فقط E.164 است، endpoint فقط `provider/phone/label` می‌پذیرد و فقط identity kind تلفنی را به PhoneAccount می‌فرستد. هدفمند Backend=`2/2`، UI onboarding=`7/7` و regression مرتبط=`126/126` سبز است.
- شاهد G-04-D در 2026-08-26: پنج آزمون خصمانهٔ مستقل ابتدا `5/5 failed` شدند؛ Runtime Log، Diagnostic، Audit persistence/query/export، تولید Support Bundle و scanner جهانی همگی E.164 یا Bearer ساختگی را زیر کلید ناشناخته/تو‌در‌تو حفظ یا تشخیص‌نداده بودند. پس از hardening مشترک، همان پنج تست `5/5` و سه regression مرتبط `53/53`، `2/2` و `50/50` سبز شدند.
- اصلاح G-04-D: redaction عمومی E.164 جهانی، شمارهٔ محلی ایران، Bearer و token-shaped provider value را در متن‌های طبقه‌بندی‌نشده sanitize می‌کند؛ Audit metadata پیش از hash/persistence redacted و هنگام query/export دوباره sanitize می‌شود؛ Support Bundle و scanner از الگوی global phone مشترک برخوردارند.
- ممیزی آغاز G-04-E در 2026-08-26: تمام هش‌های نهایی فایل‌های مؤثر ثبت‌شده در V-119/V-120 با snapshot جاری تطبیق کامل دارند. تلاش اول ممیزی دو نام مسیر حدسی و ناموجود داشت و exit code 1 گرفت؛ با استخراج مسیر واقعی از project map تکرار و بدون drift سبز شد. این رخداد خطای ابزار ممیزی بود، نه failure محصول.
- full Backend نخست G-04-E: `620 collected / 618 passed / 2 failed`. هر دو failure از timeout ده‌ثانیه‌ای subprocess در Process Worker بودند؛ اجرای فوری همان دو node در isolation و basetemp تازه `2/2 passed` شد. در همان نقطه closure متوقف ماند و full rerun بعدی الزام را بست.
- شاهد نهایی G-04-E: full rerun با basetemp تازه `620/620 passed`؛ TypeScript و UI/Electron Observability exit code صفر و قرارداد Phase 11 onboarding=`7/7`. هش‌های A تا D بدون drift ماندند و هیچ patch محصولی در E لازم نشد.
- اثر نهایی: رفتار نمایش canonical در مرز مجاز محصول حفظ، تست‌های masking منقضی حذف، onboarding تلفنی از token جدا و عدم نشت synthetic در Runtime Log/Audit/Diagnostic/Support Bundle اثبات شد.
- تصمیم کاربر در 2026-08-25: نمایش کامل شماره در مرز مجاز محصول حفظ می‌شود و masking قدیمی بازنمی‌گردد. این تصمیم ممنوعیت شماره در Log/Audit/Diagnostic/Support Bundle را تغییر نمی‌دهد.
- اقدام بعدی: هیچ اقدام دیگری در G-04 باقی نیست. G-05 فقط با دستور صریح کاربر آغاز شود؛ این closure مجوز Live، migration عملیاتی یا release readiness عمومی نیست.
- Trigger ابطال: آزمون غیرخالی نمایش کامل + عدم نشت در خروجی‌های تشخیصی و همسوشدن Baseline/Specification/Architecture.

### F-045 — برنامهٔ تثبیت هدف‌محور و دفتر اجرای append-only ایجاد شد

- وضعیت: `CLOSED / G-00..G-09 COMPLETE / USER_ACCEPTED`
- تاریخ: 2026-08-25
- دامنه: رفع `F-039` تا `F-044`، حاکمیت اجرای تغییر و لاگ‌گذاری دقیق.
- تصمیم: اهداف `G-00` تا `G-09` با چرخهٔ وضعیت، معیار خروج، دروازهٔ تأیید و ترتیب وابستگی در `STABILIZATION_REMEDIATION_PLAN_2026-08-25.md` تعریف شدند. تمام اقدام‌های بعدی باید در `STABILIZATION_EXECUTION_LOG.md` به‌صورت append-only و با Run/Step ID ثبت شوند.
- مرز Bale: هیچ قابلیت تازه‌ای توسعه نمی‌یابد؛ فقط مهار و رفع خرابی‌های موجود، با آزمون کاملاً آفلاین، در دامنه است.
- نتیجهٔ 2026-08-26: اجرای فنی G-00 تا G-09 کامل است؛ Backend=`656/656`، همهٔ UI contracts/build، archive/fresh-install/privacy و اسناد سبزند. کاربر ساعت 21:54 به‌وقت تهران G-09 و ثبت closure نهایی را صریحاً پذیرفت؛ F-045 بسته شد. هیچ Git mutation یا عملیات Live انجام نشد.
- Trigger ابطال: تغییر دامنه توسط کاربر یا بسته‌شدن کامل `G-00` تا `G-09` با شواهد پذیرش.

### F-046 — قراردادهای متأخر امنیتی rollback نمی‌شوند

- وضعیت: `DECIDED / PLAN_AMENDED`
- تاریخ: 2026-08-25
- تصمیم کاربر: آخرین قرارداد امنیتی مرتبط با توسعهٔ Bale مرجع تصمیم محصولی است و سایر قراردادهایی که مطابق آن تغییر کرده‌اند، از جمله نمایش کامل شماره در سطح مجاز محصول، به نسخهٔ قدیمی بازگردانده نمی‌شوند.
- مرز این تثبیت: اعتبار قرارداد توسعهٔ Bale به معنی توسعهٔ قابلیت تازه در این برنامه نیست؛ implementation شکسته فقط مهار و اصلاح می‌شود و عملیات Live نیازمند تأیید همان لحظه است.
- مرز ثابت اطلاعات حساس: شمارهٔ کامل، Token، OTP، Cookie، Session و متن خصوصی همچنان در Log/Audit/Diagnostic/Support Bundle ممنوع‌اند.
- اثر برنامه: G-04 از «بازگرداندن masking» به «اثبات قرارداد متأخر و redaction مستقل» تغییر کرد؛ F-040 از review مبنای مجوز به runtime safety blocker محدود شد.
- Trigger ابطال: دستور صریح تازهٔ کاربر برای تغییر قرارداد محصول یا دامنهٔ Bale.

### F-047 — گزارش‌های تثبیت در REPORTS_INDEX پنهان بودند

- وضعیت: `CLOSED / FIXED / TESTED_IN_G-01`
- تاریخ: 2026-08-25
- دامنه: `scripts/refresh_project_docs.py` و `docs/REPORTS_INDEX.md`.
- یافته: generator پوشهٔ `docs/reports/stabilization` را در `REPORT_GROUPS` نداشت؛ در نتیجه با وجود سبز بودن generator، گزارش‌های G-00/G-01 در فهرست قابل‌کشف Agent بعدی نبودند.
- RED: `tests/test_refresh_project_docs.py` با `KeyError` برای گروه «گزارش‌های تثبیت» شکست خورد.
- اصلاح/GREEN: گروه افزوده شد؛ تست `1/1` و suite هدفمند G-01 برابر `5/5` سبز شد؛ index تولیدشونده هر دو گزارش را لینک می‌کند.
- Trigger ابطال: تغییر `REPORT_GROUPS`، مسیر گزارش‌های تثبیت یا generator index.

### F-048 — پوشش عملیاتی Observability برای اسکن چندحسابی و سلامت نوشتن/نگه‌داری ناقص است

- وضعیت: `CLOSED / G-08_COMPLETE / OFFLINE_AUTOMATED_ACCEPTED`
- تاریخ: 2026-08-26
- شدت: متوسط تا زیاد
- دامنه: Runtime log scanner، `RuntimeLogger` write health، retention rotationهای Application/Worker و disk-health امن.
- یافته: اسکنر Phase 10 یک شناسهٔ حساب ثابت دارد؛ خطای نوشتن RuntimeLogger به عملیات اصلی نشت می‌کند و counter/health ندارد؛ cleanup جاری فقط diagnostic runها را پوشش می‌دهد.
- شاهد RED: چهار قرارداد مصنوعی `4/4 failed`: دو شکست نبود scanner چندحسابی و malformed fail-closed، یک شکست انتشار `OSError` از logger، و یک شکست نبود retention/disk-health API.
- تصمیم دامنه: هیچ runtime/config/account واقعی اسکن یا prune نمی‌شود. پیاده‌سازی و آزمون فقط روی ریشه‌های مصنوعی است؛ Web metrics وابسته به deployment در OBS-008 deferred می‌ماند.
- اقدام بعدی: G-08-B scanner opaque را تکمیل کند؛ G-08-C coverage lifecycle/catalog و G-08-D health/retention/Support Bundle را ببندند؛ closure نهایی در E.
- پیشرفت G-08-B: account id ثابت حذف شد؛ application و تمام account scopeهای مستقیم با rotation عددی کشف و در گزارش با scope ترتیبی بدون path/id/value نمایش داده می‌شوند. malformed/unsafe fail-closed است؛ targeted=`2/2` و related=`18/18` سبز.
- وضعیت جاری: بخش scanner بسته است؛ F-048 برای G-08-C/D/E باز می‌ماند.
- پیشرفت G-08-C: background عمومی lifecycle متوازن و correlated دارد؛ manual content-index، read-receipt، unexpected lease renewal و startup/shutdown/auth-close رخدادهای امن صریح دارند. Catalog از 92 به 102 رسید؛ RED=`4/4 failed`، GREEN=`4/4` و related=`98/98`.
- وضعیت جاری: scanner و lifecycle/catalog بسته‌اند؛ F-048 فقط برای health/retention/Support Bundle در D و closure E باز است.
- پیشرفت G-08-D: logger failure counter/path-free health، retention محدود numeric rotations با حفاظت current، disk-health امن، health endpoint، JSONL normalization و scanner report opaque تکمیل شد. RED اصلی=`4/4` و endpoint RED=`1/1`؛ G08=`13/13` و related=`78/78` سبز.
- وضعیت جاری: A تا D سبز؛ F-048 فقط تا full regression و closure G-08-E باز است. هیچ retention یا scan روی runtime واقعی اجرا نشد.
- closure G-08-E: full نخست=`655/656` با تنها wheel/source drift شش‌فایلی؛ wheel آفلاین دوبار بایت‌یکسان بازسازی و parity 90/0 drift شد. package+G08=`28/28`، full rerun=`656/656`، TypeScript و UI/Electron Observability سبز. F-048 بسته است؛ archive/fresh-install تجمیعی تازه به G-09 تعلق دارد.
- اثر نهایی: scanner همهٔ account scopeها را opaque می‌پوشاند؛ background/lifecycle failure مادی cataloged/correlated است؛ logger write failure و disk/retention health قابل‌مشاهده و Support Bundle روی malformed input fail-safe است.
- مرز closure: فقط آفلاین/مصنوعی؛ Web metrics OBS-008 deferred، داده و عملیات Live خارج. این closure release readiness اعلام نمی‌کند.
- Trigger ابطال: تغییر scanner discovery/report، RuntimeLogger emit/health، retention policy، Event Catalog/background lifecycle یا Support Bundle.

### F-049 — runtime patch پنجرهٔ گروه منتخب را به checkpoint قدیمی منحرف می‌کرد

- وضعیت: `SUPERSEDED / G-10_SOURCE_FIX_CORRECT_BUT_BROWSER_DELIVERY_STALE / F-050`
- تاریخ: 2026-08-26
- شدت: زیاد
- دامنه: fetch wrapper موقعیت مطالعه در `ui/src/ui33-runtime-patch.js` و قرارداد متناظر.
- یافتهٔ ماسک‌شده: catalog و SQLite فقط‌خواندنی نشان دادند peer منتخب فعال است، 674 پیام محلی دارد، top catalog با max محلی برابر و جدیدترین تاریخ متعلق به همان روز است؛ failure log مرتبط صفر بود. عنوان، peer/account id و متن پیام ثبت نشد.
- علت: در گفتگوی بدون unread، checkpoint ذخیره‌شده `before_id` را به `lastVisibleId + 1` و `limit` را حداقل 120 می‌کرد. در نتیجه هر بار بازکردن/refresh پس از sync نیز پنجرهٔ قدیمی دوباره درخواست می‌شد.
- RED: قرارداد منع بازنویسی request روی pre-image برابر `1 failed / 5 passed` بود.
- اصلاح: body و pagination دیگر تغییر نمی‌کنند و fetch اصلی با `input/init` دست‌نخورده اجرا می‌شود؛ metadata WordPress و scroll restoration در سطح نمایش حفظ شده‌اند.
- GREEN: contract=`1/1`، targeted runtime/mobile=`11/11`، full Backend=`657/657` بدون failure/error/skip، تمام runnerهای UI، TypeScript و build سبزند؛ source/dist hash یکسان=`6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893`.
- بازگشایی پس از گزارش کاربر: کاربر پس از انتشار G-10 اعلام کرد نمایش همچنان قدیمی است. ممیزی G-11 ثابت کرد اصلاح source درست بوده، اما مرورگر به‌علت cache immutable یک‌سالهٔ URL ثابت patch، pre-image قدیمی را اجرا می‌کرد؛ بنابراین ادعای اثر عملیاتی G-10 زودهنگام بود و با F-050 جایگزین شد.
- اثر عملیاتی: پیام/login/OTP/Provider write/Bale صفر. مشاهدهٔ بصری به‌علت شکست زیرساخت Computer Use پیش از input اجرا نشد و باید پس از راه‌اندازی build تازه توسط کاربر تأیید شود.
- Trigger ابطال: بازگشت هرگونه بازنویسی `messages/list` با checkpoint، تغییر قرارداد pagination یا تغییر معماری scroll restoration.

### F-050 — runtime patch اصلاح‌شده زیر URL ثابت با cache یک‌ساله تحویل نمی‌شد

- وضعیت: `CLOSED_CODE_AND_AUTOMATED_ACCEPTANCE / G-11 / USER_VISUAL_RECHECK_PENDING`
- تاریخ: 2026-08-27
- شدت: زیاد
- دامنه: `ui/scripts/finalize-ui-build.mjs`، cache policy فایل‌های UI در `src/eitaa_bridge/interfaces/http_api.py` و قراردادهای build/HTTP.
- شاهد ماسک‌شده: نمونهٔ اعلام‌شدهٔ کاربر در storage قدیمی 420 پیام و آخرین تاریخ ۶ مرداد داشت، اما حساب جاری همان peer را با 674 پیام و آخرین تاریخ ۴ شهریور نگه می‌داشت؛ 254 پیام پس از checkpoint قدیمی حاضر بود. عنوان، شناسهٔ peer/account و متن پیام ثبت نشد.
- علت ریشه‌ای: finalizer patch را همیشه با نام ثابت `/assets/ui33-runtime-patch.js` کپی می‌کرد و HTTP server همهٔ assetهای غیر-index را یک سال `immutable` می‌فرستاد. مرورگر pre-image G-09/G-10 را بدون revalidation نگه می‌داشت؛ restart Backend یا وجود فایل تازه روی دیسک این URL cached را عوض نمی‌کرد.
- RED: قرارداد hash نام فایل، استفادهٔ finalizer از SHA-256 و منع immutable برای asset ثابت در مجموع `3 failed / 6 passed` بود.
- اصلاح: نام patch از ۱۶ نویسهٔ نخست SHA-256 محتوا ساخته می‌شود؛ tag قدیمی و assetهای patch پیشین هنگام build حذف می‌شوند؛ server فقط asset مستقیم دارای نام hashدار را immutable و فایل ثابت/index را `no-store` می‌فرستد.
- GREEN: قرارداد هدفمند=`9/9`، regression مرتبط=`54/54`، full Backend نهایی=`658/658` با skip صفر، همهٔ ۹ runner UI، TypeScript و build سبزند. full نخست فقط به‌علت drift مورد انتظار wheel/source برابر `657/658` بود؛ wheel دوبار بایت‌یکسان بازسازی و parity برابر 90/0 شد.
- انتشار آفلاین: wheel SHA=`ba05c810...`، دو archive canonical پس از ثبت ADR-40 با 282 فایل و SHA بایت‌یکسان=`08c5d5dd...` و content-set=`4ec774ed...`، verifier/privacy داخلی PASS و fresh venv فقط با wheelهای محلی و `--no-index` سبز است.
- محدودیت شاهد: برنامه هنگام validation نهایی HTTP اجرا نبود و اتصال loopback رد شد؛ برنامه بدون اجازه راه‌اندازی نشد. تأیید بصری پس از بستن و اجرای دوبارهٔ برنامه هنوز بر عهدهٔ کاربر است و تا آن زمان ادعای Live-verified ثبت نمی‌شود.
- Trigger ابطال: URL ثابت برای runtime patch، cache immutable روی asset بدون content hash، تغییر finalizer/static serving یا گزارش تکرار نمایش تاریخ قدیمی پس از restart.

### F-056 — ادغام محتوایی پیام‌های متوالی و تفکیک مسیر آواتار تکمیل شد

- وضعیت: `CLOSED_CODE_AND_FULL_AUTOMATED_ACCEPTANCE / USER_VISUAL_RECHECK_OPTIONAL`
- تاریخ: 2026-08-27
- دامنه: timeline پیام، آلبوم/رسانهٔ ترکیبی، انتخاب و پیمایش مجازی، cache و صف آواتار حساب‌محور.
- مسئله: grouping قبلی فقط Cardهای جدا را از نظر گوشه و فاصله شبیه یک مجموعه می‌کرد، حد زمانی محاسبه‌شده اعمال نمی‌شد و آلبوم با متن/آلبوم بعدی ادغام نمی‌شد. صف سه‌تایی آواتار نیز cache probe و remote fetch را مخلوط می‌کرد؛ کار remote کند cache hitهای دیگر را عقب می‌انداخت و failure/stale account به‌اندازهٔ کافی مهار نمی‌شد.
- اصلاح: `buildMessageGroupLookup` آلبوم‌های موجود و همهٔ محتوای متوالی یک فرستنده را تا پنج دقیقه و در همان روز نمایشی یک واحد می‌کند. renderer ترتیب text/image/file را حفظ، selection/index/usage/read/focus را روی همهٔ اعضا اعمال و follower مجازی را صفرارتفاع می‌کند. آواتار cache-first با صف cache شش‌تایی و remote تک‌صف امن، failure TTL کوتاه، scope guard و prefix صحیح پاک‌سازی اجرا می‌شود.
- محدودیت داده: Core جاری photo reference مخاطب را از contact codec به مدل User منتقل نمی‌کند. عکس فرستندهٔ گروهی فقط اگر همان User در dialog catalog reference قابل استفاده داشته باشد بارگیری می‌شود؛ نبود/مخفی‌بودن/stale بودن reference به initials امن برمی‌گردد. گروه/کانال و personal dialog معمولاً reference مستقیم دارند و از صف تازه بهره می‌برند.
- RED: grouped-media به‌علت نبود API تازه و Phase 9 به‌علت نبود module صف شکست خورد؛ contract Python نیز نبود cached-only/two-lane را ثابت کرد.
- GREEN: grouped-media=`29/29`، queue/workspace=`18/18`، UI/Material regression=`42/42`، تمام ۹ runner UI، TypeScript و build 1016-module، full Backend=`659/659` سبز است.
- حریم خصوصی/عملیات: دادهٔ واقعی، login/OTP، ارسال، WordPress، Provider mutation و فایل عملیاتی صفر؛ فقط fixture مصنوعی و artifact آزمون/بسته‌بندی ایجاد شد.
- شناسهٔ F-056 برای جلوگیری از برخورد با F-051 تا F-055 در کار موازی ایندکس رزرو شد؛ فایل‌های آن کار در این commit نیستند.
- مرجع: `docs/reports/features/CONSECUTIVE_MESSAGE_GROUPING_AND_AVATAR_RESILIENCE_REPORT_2026-08-27.md`، ADR-44 و V-169/V-170.
- Trigger بازبینی: تغییر threshold/identity/day rule، ساخت lookup پس از filter، parallel کردن نشست Provider، تغییر Core photo codec/catalog یا گزارش شکست بصری روی دادهٔ واقعی.

### F-061 — WordPress opt-in، نقش fail-closed و صف کم‌اولویت آواتار تکمیل شد

- وضعیت: `CLOSED_CODE_AND_FULL_AUTOMATED_ACCEPTANCE / LIVE_RECHECK_OPTIONAL`
- تاریخ: 2026-08-27
- دامنه: نمایش پنل WordPress، taxonomy fetch، عملیات گروه/کانال، role hint حساب و بارگیری آواتار.
- مسئله: UI حتی بدون نیاز جاری WordPress، surface و مسیر بررسی taxonomy را عرضه می‌کرد؛ عملیات گفتگو شاهد قابل‌اعتماد مالک/مدیر نداشت؛ آواتار فهرست نیز از نظر اولویت با گفت‌وگوی فعال تمایز کافی نداشت و cache خراب می‌توانست نقص را پایدار کند.
- اصلاح: پنل WordPress با default خاموش و شرط credential opt-in شد؛ taxonomy در حالت خاموش request نمی‌شود. نقش owner/admin از parse معتبر dialog به catalog منتقل و eligibility فقط برای active group/channel به‌شکل fail-closed محاسبه می‌شود. آواتار فعال/background صف و اولویت جدا، promotion، idle delay و اعتبارسنجی magic/size دارد، در حالی که نشست Provider همچنان سریال است.
- محدودیت صادقانه: Channel/Supergroup owner/admin و basic-group creator قابل تشخیص‌اند؛ basic-group admin غیرمالک در قرارداد Core جاری شاهد کافی ندارد و `unknown` باقی می‌ماند. dialogهای قبلی نیز برای پرشدن نقش نیازمند sync بعدی‌اند. نبود photo reference معتبر همچنان با initials مهار می‌شود.
- GREEN: full Backend=`664/664` در partitionهای کامل، تمام runnerهای UI، TypeScript و build 1016-module سبز؛ wheel و archiveها deterministic و fresh-install آفلاین سبز است.
- حریم خصوصی/عملیات: Live/Login/OTP/Send/Member mutation/WordPress/Provider operation و دادهٔ عملیاتی صفر؛ فقط fixture و artifact کنترل‌شده.
- مرجع: ADR-47، V-181/V-182 و `docs/reports/features/WORDPRESS_PANEL_ROLE_GATING_AND_PRIORITY_AVATAR_REPORT_2026-08-27.md`.
- Trigger بازبینی: تغییر TL dialog flags/Core codec، role contract، taxonomy loading، scheduler priority، avatar validation یا گزارش شکست روی دادهٔ واقعی.

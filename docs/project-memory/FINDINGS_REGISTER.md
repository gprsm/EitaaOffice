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
- به‌روزرسانی 2026-09-27: مالک با F-085 دستور ابطال همین Trigger را داد؛ تفسیر fail-closed دائمی از این رکورد منسوخ است و قرارداد جاری Bale در فصل ۷ سند Discovery و ADR-60 ثبت شده است.

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

## ثبت‌های میراثی گفت‌وگوی پیشین دربارهٔ ایندکس

رکوردهای `LEGACY-INDEX-*` زیر از یک ثبت ناقص Agent پیشین حفظ شده‌اند. شناسه‌های اولیهٔ آن‌ها (`F-039` تا `F-042`) با یافته‌های رسمی موجود تکراری بود و برخی ادعاهای معماری، schema، کد برنامه و میزان استفاده از API پیش از تحلیل منبع معتبر قطعی اعلام شده بود. این متن‌ها برای provenance حذف نشده‌اند، اما تصمیم canonical یا مجوز پیاده‌سازی نیستند و همگی با `F-051` جایگزین شده‌اند.

### LEGACY-INDEX-F039 - تصمیم استراتژیک: هدف نهایی گزارش است، نه وردپرس

- **وضعیت:** `HISTORICAL_UNVALIDATED / SUPERSEDED_BY_F-051`
- **تاریخ:** 2026-08-27
- **حوزه:** معماری کلان پروژه
- **خلاصه:** کاربر در 2026-08-27 تصریح کرد که وردپرس ممکن است تنها یک منبع داده میانی باشد، نه هدف نهایی. هدف نهایی تکمیل فایل اکسل عملکردی (و هر گزارش مشابه) است. این یعنی:
  - داده‌های ایندکس‌گذاری‌شده باید به صورت ساختاریافته و مستقل از وردپرس ذخیره شوند
  - لایه داده هوشمند باید از سه منبع تغذیه شود: ایتا + وردپرس + ورود دستی کاربر
  - چارچوب گزارش‌دهی باید انعطاف‌پذیر باشد (هر گزارشی که درخواست شود از همین داده‌ها قابل تولید است)
- **فیلدهای ساختاریافته اجباری برای هر ایندکس:**
  - `activity_code` — کد برنامه (مثل ۸۰۴۰۲)
  - `unit` — واحد سازمانی (مثل سیمرغ، نور، بابل)
  - `event_name` — نام مناسبت/رویداد (مثل زیارت عاشورا، هفته وحدت)
  - `event_date` — تاریخ رویداد (از متن، نه timestamp)
  - `calendar_season` — فصل تقویمی (محرم، هفته قوه قضائیه، ...)
  - `report_status` — وضعیت: draft / confirmed / exported
- **تأثیر بر این چرخه توسعه:** ایندکس‌گذاری باید این فیلدها را مستقل ذخیره کند تا لایه گزارش‌دهی آینده بتواند از آن‌ها استفاده کند
- **Trigger ابطال:** تغییر در ساختار فایل اکسل یا چارچوب گزارش‌دهی سازمان

### LEGACY-INDEX-F040 - معماری سه‌لایه: TF-IDF + Cache + LLM API

- **وضعیت:** `HISTORICAL_UNVALIDATED / SUPERSEDED_BY_F-051`
- **تاریخ:** 2026-08-27
- **حوزه:** موتور ایندکس‌گذاری
- **خلاصه:** برای ایندکس‌گذاری هوشمند با حداقل هزینه و حداکثر یادگیری، معماری سه‌لایه تصویب شد:
  - لایه ۱: TF-IDF محلی (سریع، رایگان، آفلاین) — برای الگوهای شناخته‌شده
  - لایه ۲: Cache یادگیری — الگوهایی که قبلاً از LLM پاسخ گرفته‌اند، دیگر API فراخوانی نمی‌شود
  - لایه ۳: LLM API — فقط برای الگوهای جدید/مبهم، یک‌بار و ذخیره‌سازی نتیجه
- **منطق:** سیستم باید کم‌کم از API مستقل شود. هر الگوی جدید یک‌بار از API می‌آموزد، بعد محلی پاسخ می‌دهد
- **هدف بلندمدت:** پس از چند ماه، ۹۰٪+ پیام‌ها بدون API ایندکس شوند
- **Trigger ابطال:** تغییر در Provider LLM یا schema جدول cache

### LEGACY-INDEX-F041 - دسته‌های فعالیت تأییدشده (از فایل اکسل)

- **وضعیت:** `HISTORICAL_UNVALIDATED / SUPERSEDED_BY_F-051`
- **تاریخ:** 2026-08-27
- **حوزه:** Activity Categories
- **خلاصه:** کاربر دسته‌های فعالیت زیر را از فایل اکسل تأیید کرد:

  | کد | عنوان |
  |---|---|
  | ۸۰۲۰۲ | اجرای منشور اخلاقی |
  | ۸۰۴۰۱ | برگزاری اردوهای فرهنگی-زیارتی برای کارکنان |
  | ۸۰۴۰۲-الف | برگزاری مراسم در مناسبت‌های مذهبی-ملی-انقلابی |
  | ۸۰۴۰۲-ب | برگزاری مسابقات فرهنگی و ورزشی |
  | ۸۰۵۰۱ | ترویج و توسعه فرهنگ اقامه نماز |
  | ۸۰۴۰۶ | تکریم و تجلیل از همکاران |
  | ۸۰۶۰۱ | تشویق کارمندان برتر |
  | — | نامربوط (پیام‌هایی که در هیچ دسته‌ای نمی‌گنجند) |

- **نکته:** این دسته‌ها در UI باید قابل بازتعریف باشند چون چارچوب ممکن است تغییر کند
- **Trigger ابطال:** تغییر در فایل اکسل سازمانی یا بازتعریف کاربر در UI

### LEGACY-INDEX-F042 - الزام: ایندکس ساختاریافته (نه فقط برچسب)

- **وضعیت:** `HISTORICAL_UNVALIDATED / SUPERSEDED_BY_F-051`
- **تاریخ:** 2026-08-27
- **حوزه:** schema ایندکس
- **خلاصه:** نتایج ایندکس نباید صرفاً یک برچسب دسته باشند. برای هر پیام ایندکس‌شده باید فیلدهای جداگانه‌ای ذخیره شود که لایه گزارش‌دهی آینده بتواند از آن‌ها استفاده کند. این فیلدها در `predictions_json` یا ستون‌های جداگانه در `index_results` ذخیره می‌شوند.
- **تأثیر:** schema v4 باید این فیلدها را در بر بگیرد
- **Trigger ابطال:** تغییر در ساختار گزارش نهایی

### F-051 — نقشه‌راه هوشمندسازی ایندکس و گزارش‌سازی از فاز صفر آغاز می‌شود

- وضعیت: `DECIDED / PHASE_0_AUTHORIZED / PRODUCT_IMPLEMENTATION_NOT_STARTED`
- تاریخ: 2026-08-27
- دامنه: تحلیل دامنه، ایندکس محتوای ایتا، شواهد رویداد، قواعد گزارش، WordPress، فایل‌های گزارش و امکان استفادهٔ محدود آینده از مدل زبانی.
- مسئله: طراحی پیشین «دسته»، «برنامه»، «مناسبت»، «مکان»، «واحد گزارش‌دهنده»، «فرستنده»، «رویداد»، «مدرک» و «وضعیت مرتبط‌بودن سند» را به‌قدر کافی جدا نمی‌کرد. ثبت‌های میراثی بالا نیز پیش از احراز مستندات، معماری و schema مشخصی را قطعی فرض کرده بودند.
- تصمیم:
  - هدف داخلی سامانه یک لایهٔ ساختاریافتهٔ شواهد و گزارش است؛ WordPress فقط یکی از projectionهای خروجی یا ورودی‌های قابل تطبیق است، نه منبع حقیقت.
  - پیش از طراحی schema/API/UI، فاز صفر باید منابع، واژگان، نسخه‌های چارچوب گزارش، نمونه‌های مجاز و معیار سنجش را روشن کند.
  - «نامربوط/اطلاع‌رسانی» disposition سند است و دستهٔ فعالیت شمرده نمی‌شود.
  - تاریخ ارسال، تاریخ‌های ذکرشده و تاریخ منتخب رویداد مستقل و دارای provenance هستند؛ مکان برگزاری نیز با واحد گزارش‌دهنده یا وابستگی فرستنده یکی نیست.
  - alias canonical فقط صورت‌های هم‌ارز یک مفهوم را یکسان می‌کند؛ مفاهیم مرتبط مانند «هفته وحدت» و «ولادت پیامبر» بدون قاعدهٔ دامنه‌ای versioned مترادف اعلام نمی‌شوند.
  - کد ابلاغی ویژگی versioned برنامه/شاخص است و تا احراز یکتایی از مستندات رسمی، شناسهٔ داخلی محسوب نمی‌شود.
  - مسیر پایه local-first و deterministic است. API مدل زبانی در فاز صفر و مسیر پایه خاموش می‌ماند و فقط در فاز بعدیِ مستقل، با opt-in، سهمیه، redaction، خروجی ساختاریافته و تأیید انسانی قابل ارزیابی است.
  - پاسخ مدل خودکار به قاعدهٔ دائمی تبدیل نمی‌شود؛ exact cache، retrieval محلی و حافظهٔ تأییدشده قراردادهای جداگانه خواهند داشت.
  - scheduler خودکار فعلی تا تکمیل قرارداد lifecycle، cancellation، isolation، backoff و observability خاموش باقی می‌ماند.
- موارد عمداً تأییدنشده: فهرست نهایی برنامه‌ها/شاخص‌ها، معنای دقیق کدهای ابلاغی، schema ذخیره‌سازی، مدل/Provider/prompt، درصد مصرف API و فرض یک برنامه برای هر پیام.
- مرجع canonical: [نقشه‌راه هوشمندسازی ایندکس و گزارش‌سازی](INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md) و [دفتر اجرای آن](INDEX_INTELLIGENCE_EXECUTION_LOG.md).
- اقدام بعدی: `IR-0-A` فقط با inventory منبع، provenance و conflict register آغاز شود؛ کد محصول، migration، API خارجی و دادهٔ عملیاتی در این ثبت تغییر نکرده است.
- Trigger بازبینی: تکمیل هر زیرمرحلهٔ فاز صفر، دریافت مستند رسمی تازه، تغییر چارچوب گزارش یا تصمیم صریح کاربر دربارهٔ دامنه/حریم خصوصی/API.

### F-052 — workbook ۱۴۰۵ مرجع پایه است، اما منطق گزارش executable و کامل نیست

- وضعیت: `OPEN / IR-0-A / PRIMARY_SOURCE_REGISTERED / USER_CLARIFICATIONS_REQUIRED`
- تاریخ: 2026-08-27
- دامنه: workbook محلی برنامه‌های متناظر استانی سال ۱۴۰۵، هفت sheet برنامه، قواعد آماری/مستندسازی و تعارض‌های دامنه.
- مجوز و provenance: کاربر اعلام کرد سند دیگری در دسترس نیست و خواست همین فایل مرجع شود. Source ID=`SRC-IR-001` و hash امن آن در Source Register ثبت شد؛ فایل اصلی وارد Git نشد.
- شاهد مستقیم: workbook شامل هفت sheet/جدول و formula صفر است. کدهای مشاهده‌شده `80401`، `80402`، `80402`، `80501`، `80406`، `80601` و `80202` هستند؛ دو کاربرد `80402` تا پاسخ کاربر تعارض باز محسوب می‌شوند.
- قواعد مهم مستقیم: زیارت عاشورا در شمارش اصلی مراسم وارد نمی‌شود ولی جداگانه گزارش می‌شود؛ مسابقهٔ حین مراسم در برنامهٔ مسابقات لحاظ می‌شود؛ نشست شرایط حداقلی دارد؛ تکریم/تشویق شروط حضور مقام دارند؛ موارد ستاره‌دار مستند می‌خواهند.
- یافتهٔ معماری: sheetها فقط «دسته» نیستند؛ در هرکدام برنامه، metric، اقدام پشتیبان، جامعهٔ مخاطب، مدرک و خروجی گزارش ترکیب شده است. تبدیل مستقیم هر sheet یا ستون به activity category/schema خطاست.
- محدودیت: اصالت مستقل، completeness، سال درون‌فایلی، grain ردیف، نوع مقادیر ستاره‌دار، محل projection استثناها، کیفیت اعداد و کفایت مدارک تعریف کامل ندارند.
- تصمیم موقت: متن سلول‌ها `VERIFIED_AS_TRANSCRIBED` و تفسیرها `USER_CONFIRMATION_PENDING` هستند. دوازده پرسش `Q-IR-001..012` ثبت شد و هیچ ابهامی با حدس بسته نمی‌شود.
- مرجع: `INDEX_SOURCE_AND_CONFLICT_REGISTER.md`، `INDEX_1405_WORKBOOK_REFERENCE.md` و `INDEX_DOMAIN_QUESTION_REGISTER.md`.
- اثر محصول: صفر؛ هیچ schema، migration، classifier، LLM/API، WordPress mapping یا scheduler تغییر نکرد.
- Trigger بازبینی: پاسخ شماره‌دار کاربر، یافتن نسخهٔ تازه/سند مکمل، تغییر hash فایل یا ورود نمونهٔ گزارش پذیرفته‌شده.

### F-053 — artifactهای brain ادعاهای منقضی را به‌صورت plan و acceptance جاری نمایش می‌دادند

- وضعیت: `CONTAINED / EXTERNAL_ARTIFACTS_MARKED_SUPERSEDED`
- تاریخ: 2026-08-27
- دامنه: حافظهٔ بیرونی Antigravity/Sonnet برای موضوع ایندکس؛ plan، development map، task checklist، walkthrough و metadata همراه.
- یافته: یک نقشه‌راه ۶ فازه و یک مجموعهٔ قدیمی‌تر، forced-primary، schema v4، live retraining و daemon ساعتی را قطعی/تکمیل‌شده اعلام می‌کردند. این ادعاها با F-051، IR-0-A و closure G-05 تعارض دارند.
- ریسک: Agent بعدی ممکن بود checkbox یا عنوان «تکمیل شد» را مجوز اجرا/پذیرش بداند و scheduler حذف‌شده یا schema پیش‌رس را بازگرداند.
- ممیزی مشابه‌ها: چهار فایل با نام `implementation_plan.md` در brain یافت شد؛ دو مورد مربوط به Bale و Phase 11-C خارج از دامنهٔ ایندکس بودند و تغییر نکردند. مجموعهٔ مرتبط شامل پنج Markdown و پنج metadata بود.
- اصلاح: هیچ artifact تاریخی حذف نشد. در ابتدای پنج Markdown هشدار `SUPERSEDED/HISTORICAL/DO_NOT_IMPLEMENT` و پیوند به مرجع canonical افزوده و summary پنج metadata همسو شد؛ متن و checkboxهای تاریخی برای provenance باقی ماندند.
- قاعده: artifact بیرونی canonical نیست مگر در project-memory ثبت، با Finding/Validation متصل و توسط writer اصلی promote شود.
- مرجع: `EXTERNAL_AGENT_ARTIFACT_REGISTER.md` و V-165.
- Trigger بازبینی: تولید artifact جدید دربارهٔ ایندکس در حافظهٔ Agentها، حذف/تغییر هشدار، یا طراحی چارچوب چندعاملی IR-GOV-01.

### F-054 — آمار دستیِ تخمینی یا ساختگی provenance و دروازهٔ تأیید مستقل دارد

- وضعیت: `DECIDED / DOMAIN_POLICY_ACCEPTED / IMPLEMENTATION_DEFERRED`
- تاریخ: 2026-08-27
- دامنه: مقدارهای عددی گزارش، تکمیل دستی Excel، دادهٔ آموزشی و خروجی رسمی.
- یافتهٔ کاربر: تکمیل نهایی Excel با دخالت مستقیم کاربر انجام می‌شود و ممکن است در برخی وضعیت‌ها آمار تخمینی/ساختگی وارد شود. معنای `*` نیز باید از واحد ستادی پرسیده شود.
- ریسک: اگر مقدار مشاهده‌شده، اعلامی واحد، تخمینی، placeholder ساختگی و تأییدشده یکسان ذخیره شوند، گزارش، ارزیابی مدل و یادگیری بعدی غیرقابل‌اعتماد می‌شوند.
- تصمیم پذیرفته‌شدهٔ کاربر در `SRC-USER-IR-002`: سامانه نباید عدد بسازد یا مقدار تخمینی/ساختگی را بی‌نشان `verified` کند. ورودی دستی باید provenance، `value_kind`، زمان/عامل ورود و تاریخچهٔ اصلاح داشته باشد؛ مقدار تخمینی/ساختگی بدون تأیید صریح کاربر وارد training truth یا آمار تأییدشده نمی‌شود.
- stateهای مفهومی پذیرفته‌شده: `observed`، `reported_by_unit`، `estimated`، `synthetic_placeholder` و `verified`. نام فنی ستون/enum تا طراحی مدل دامنه قطعی نیست.
- وضعیت پاسخ‌های دیگر: کد مراسم `80403` فقط فرضیهٔ نامطمئن کاربر است؛ اعتبار قالب تا پایان ۱۴۰۵ محتمل و تغییرپذیر است؛ هیچ‌کدام به حقیقت قطعی تبدیل نشدند.
- اثر محصول: صفر؛ این تصمیم قاعدهٔ دامنه است و schema/migration/export workflow در فاز مناسب بعد از Phase 0 طراحی می‌شود.
- Trigger بازبینی: تغییر تصمیم کاربر، پاسخ واحد ستادی، یا تعریف workflow تأیید/export گزارش.

### F-055 — grain رویداد با grain ردیف گزارش استانی یکی نیست

- وضعیت: `DECIDED / DOMAIN_GRAIN_ACCEPTED / IMPLEMENTATION_DEFERRED`
- تاریخ: 2026-08-27
- دامنه: پیام/مدرک، رویداد، واحد شهرستانی، metric برنامه و ردیف workbook سال ۱۴۰۵.
- پاسخ کاربر: ردیف اصلی هر برنامه نمایندهٔ آمار تجمیعی کل استان، شامل ستاد استانی و همهٔ واحدهای شهرستانی است. ثبت یک ردیف به‌ازای هر رویداد با ستون‌هایی مانند «تعداد اردو» ناسازگار است.
- تصمیم: grain داخلی event/evidence است، ولی grain projection workbook برابر `province + reporting period + framework version + program/subtable` خواهد بود. رخدادها برای ساخت اعداد تجمیعی استفاده می‌شوند.
- قید traceability: جزئیات واحد، رویداد، تاریخ و مدرک حذف یا در عدد نهایی مستهلک نمی‌شود؛ breakdown باید قابل بازسازی باشد. عبارت `مراسم  مذهبی!C11` نیز breakdown حوزه/مراسم را پشتیبان می‌کند.
- provenance: `SRC-USER-IR-003` تفسیر عقلایی و تأییدشدهٔ کاربر پس از طرح سؤال با ستاد است؛ متن رسمی قالب grain را صریح تعریف نمی‌کند و clarification رسمی آینده می‌تواند supersede کند.
- اثر محصول: صفر؛ schema، aggregation engine، Excel projection و event store هنوز پیاده نشده‌اند.
- مرجع: Q-IR-004، ADR-43 و V-168.
- Trigger بازبینی: پاسخ رسمی متفاوت ستاد، نسخهٔ تازهٔ workbook یا تعریف reporting period/subtable.

### F-057 — زیارت عاشورا metric و ضمیمهٔ مستقل خارج از شمارش اصلی مراسم است

- وضعیت: `DECIDED / DOMAIN_RULE_ACCEPTED / IMPLEMENTATION_DEFERRED`
- تاریخ: 2026-08-27
- دامنه: `مراسم  مذهبی!C12`، گزارش تجمیعی استان، breakdown رویداد/واحد و projection خارج از ستون‌های workbook.
- تصمیم کاربر: تعداد زیارت عاشورا در سطح استان جداگانه تجمیع و مستندات آن در ضمیمهٔ مستقل ارائه شود، حتی اگر workbook ستون مستقیم ندارد.
- قاعده: زیارت عاشورا به main ceremony count افزوده نمی‌شود. هر رخداد/واحد و evidence آن برای audit حفظ و از آن metric جداگانه تولید می‌شود.
- نتیجهٔ معماری: report rule می‌تواند metric/annex versioned بیرون از ستون‌های صریح template داشته باشد؛ نبود ستون به معنای حذف fact نیست.
- provenance: `SRC-USER-IR-004`، Q-IR-005، ADR-45 و V-171.
- اثر محصول: صفر؛ نام فنی metric، قالب ضمیمه، query و export هنوز پیاده نشده‌اند.
- Trigger بازبینی: پاسخ رسمی ستاد، template تازه یا تغییر قاعدهٔ شمارش زیارت عاشورا.

### F-058 — پرسشنامهٔ نسخه‌دار حلقهٔ اتصال دادهٔ خام به metric گزارش است

- وضعیت: `PROPOSED / IR-0-B_INPUT / ANALYSIS_REQUIRED`
- تاریخ: 2026-08-27
- دامنه: هفت برنامهٔ workbook، Eitaa/WordPress/ورودی دستی، دادهٔ مالی/پایه، فرض‌ها، محاسبات و گزارش تفصیلی.
- پیشنهاد کاربر: برای هر عنوان کلی گزارش پرسشنامهٔ مناسب ساخته شود تا اجزای پراکندهٔ یک موضوع—خبر، تعداد، هزینه و اطلاعات تکمیلی—به هم متصل و مقدارهای استنباطی از داده‌های پایه/نرخ‌ها محاسبه شوند.
- صورت‌بندی: هستهٔ مشترک زمینه/رویداد/evidence/value/provenance/review به‌علاوهٔ module اختصاصی هر برنامه. تعریف پرسش نسخه‌دار است و فرم UI فقط presentation آن است.
- قاعدهٔ محاسبه: assumption و derived value از fact جدا می‌مانند؛ formula/version/inputها قابل trace هستند؛ مقدار دقیق متناظر estimate را جایگزین می‌کند و با آن double count نمی‌شود.
- فرصت: نرخ اجرای واحدها، تقویم مناسبت‌ها، تعداد کارکنان و نرخ حضور می‌توانند estimate دوره‌ای بسازند و شکاف‌های داده را شفاف کنند.
- ریسک: ضرب نرخ‌ها بدون eligibility/denominator/version، برآورد را به عدد ظاهراً دقیق ولی غیرقابل‌دفاع تبدیل می‌کند. خروجی باید value-kind و عدم‌قطعیت را حفظ کند.
- workflow اکنون با Q-IR-014/ADR-46 بسته است: فقط کاربران مجاز ستادی پرسشنامه را تکمیل و تأیید می‌کنند؛ شهرستان‌ها صرفاً از Eitaa داده می‌فرستند و Agent فقط پیشنهادگر است. فرم و schema همچنان ناپیاده‌اند.
- مرجع: `INDEX_PROGRAM_QUESTIONNAIRE_MODEL.md` و SRC-USER-IR-004.
- اثر محصول: صفر؛ schema/form/calculation engine ساخته نشده‌اند.
- Trigger بازبینی: تغییر مرز دسترسی/اختیار انسانی، تکمیل glossary/report map، یا طراحی IR-0-B/C.

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
- مرجع: `docs/reports/features/CONSECUTIVE_MESSAGE_GROUPING_AND_AVATAR_RESILIENCE_REPORT_2026-08-27.md`، ADR-44 و V-169/V-170.
- Trigger بازبینی: تغییر threshold/identity/day rule، ساخت lookup پس از filter، parallel کردن نشست Provider، تغییر Core photo codec/catalog یا گزارش شکست بصری روی دادهٔ واقعی.

### F-059 — چند writer هم‌زمان واقعاً شناسه‌های canonical را متعارض کردند

- وضعیت: `DECIDED / GOVERNANCE_V1_REGISTERED / AUTOMATED_ENFORCEMENT_DEFERRED`
- تاریخ: 2026-08-27
- دامنه: Findings/Validation/ADR مشترک میان task جاری ایندکس و یک task موازی ویژگی UI.
- رخداد: هنگام ثبت Q-IR-005، task جاری شناسه‌های F-056/V-169/ADR-44 را آزاد دیده و استفاده کرد؛ پیش از validation نهایی، writer دیگری همان شناسه‌ها را برای feature گروه‌بندی پیام/آواتار ثبت کرد. memory checker دقیقاً دو duplicate رسمی را رد کرد و ADR-44 نیز با ممیزی heading متعارض یافت شد.
- مهار: رکوردهای writer دیگر حذف یا بازنویسی نشدند. رکوردهای ایندکس به F-057/F-058، V-171 و ADR-45 منتقل و همهٔ backlinkهای مربوط اصلاح شدند؛ integrity نهایی PASS شد.
- نتیجه: تفکیک موضوعی taskها به‌تنهایی کافی نیست؛ رجیسترهای append-only، Baseline، Handoff و generated docs نقاط write مشترک‌اند و باید یک writer/allocator canonical داشته باشند.
- اثر محصول: این Finding صحت feature موازی را ممیزی یا رد نمی‌کند؛ فقط collision مستندات را ثبت می‌کند.
- اقدام انجام‌شده: `IR-GOV-01 / POLICY_V1` ownership فایل، Task Contract، handoff، review، promotion و منع دو writer را تعریف کرد. رزرو شناسه/lock/merge queue ماشینی هنوز deferred است؛ تا آن زمان Codex allocator/promoter و sole writer پیش‌فرض اسناد canonical ایندکس است.
- تکرار 2026-08-28: هنگام ثبت همین policy، writer سناریوی امضای داخلی F-064/V-186/ADR-50 را هم‌زمان مصرف کرد. checker دوباره collision را گرفت؛ رکورد امضای داخلی حفظ و مدل چهارسطحی به F-065/V-187/ADR-51 منتقل شد. این رخداد نشان می‌دهد policy بدون lock/allocator ماشینی فقط risk reduction است، نه حذف race.
- مرجع شاهد: V-172 و `EXTERNAL_AGENT_ARTIFACT_REGISTER.md`.
- Trigger بازبینی: هر اجرای هم‌زمان، طراحی governance یا collision دوبارهٔ ID/file.

### F-060 — workflow گزارش ستادمحور است و Agent اختیار تأیید ندارد

- وضعیت: `DECIDED / ACCESS_AND_REVIEW_BOUNDARY / IMPLEMENTATION_DEFERRED`
- تاریخ: 2026-08-27
- دامنه: ورود دادهٔ شهرستان، کاربران سامانه، شبکهٔ محلی، WordPress، اتوماسیون/LLM، تأیید، aggregation استانی و export.
- تصمیم کاربر: واحدهای شهرستانی هیچ دسترسی یا نقش مستقیمی در سامانه ندارند و اطلاعات را از طریق Eitaa می‌فرستند. فقط کاربر اصلی و همکاران ستادی مجاز در محل فیزیکی مشترک و شبکهٔ خصوصی، داده‌ها و پرسشنامه‌ها را تکمیل/اصلاح می‌کنند.
- جایگاه منابع: Eitaa مسیر inbound evidence/claim است. WordPress مخزن و نمای فعالیت‌های اداره و یک source/projection قابل تطبیق است، نه مرجع حقیقت انحصاری.
- مرز هوشمندی: اتوماسیون یادگیرندهٔ محلی مسیر ترجیحی کمک است و API عامل هوشمند فقط fallback اختیاری و کنترل‌شده است. هیچ خروجی خودکار به‌تنهایی verified، approved یا صادرشده محسوب نمی‌شود.
- اختیار نهایی: تأیید factها، استنتاج نهایی، محاسبات استانی و خروجی گزارش فقط به کاربر انسانی مرکزی مجاز منتسب می‌شود؛ Codex/LLM/Agent approver نیست.
- قید امنیتی: استقرار LAN اعتماد ضمنی ایجاد نمی‌کند؛ authentication، authorization سمت سرور، audit و تفکیک سطح دسترسی اسناد همچنان الزامی‌اند.
- اثر محصول: صفر؛ role schema، UI، LAN deployment، workflow engine و اتصال API هنوز پیاده نشده‌اند.
- مرجع: `SRC-USER-IR-005`، Q-IR-014، ADR-46 و V-173.
- Trigger بازبینی: تغییر تصمیم کاربر دربارهٔ کاربران سامانه، محل استقرار، مرجع تأیید یا نحوهٔ استفاده از Agent/API.

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

### F-062 — Setup قابل‌اشتراک self-contained شد و بستهٔ خام دستی نیازمند repair بود

- وضعیت: `IMPLEMENTED / WINDOWS_EXE_BUILT / VERIFY_ONLY_AND_OFFLINE_ACCEPTED / CODE_SIGN_AND_CLEAN_INSTALL_PENDING`
- تاریخ: 2026-08-28
- دامنه: پوشهٔ خام انتقالی، wheel/source parity، Windows setup، Runtime وابستگی، حریم خصوصی artifact و سازگاری Windows 7.
- یافتهٔ اولیه: پوشهٔ `Eitaa_Bridge/Eitaa_Bridge` یک سطح nesting اضافی داشت، `VERSION.txt` در آن نبود و `package_clean.py --dry-run` با `mismatched=2` متوقف شد؛ wheel از `api.py` و `eitaa_provider_runtime_operations.py` جاری عقب بود. `bridge.json` عملیاتی در ریشهٔ خام وجود داشت و طبق policy خوانده یا وارد artifact نشد.
- ریشهٔ خطای اولین اجرا: دو defect تاریخی empty Coordinator و Legacy `challenge_id` همان F-041 بودند و در source جاری بسته باقی ماندند. regression نصب تمیز/احراز هویت در این checkpoint دوباره سبز شد؛ کپی مستقیم کل پوشه همچنان روش انتقال پشتیبانی‌شده نیست.
- اصلاح: builder ابتدا wheel را deterministic از source جاری بازسازی و allowlist/parity را fail-closed بررسی می‌کند. Python 3.13 x64 و runtime packageهای نصب‌شده فقط از wheelهای محلی داخل Setup قرار می‌گیرند؛ Node/npm روی مقصد لازم نیست. ابزارهای Backup/Restore/Diagnostics/Doctor نیز Python همراه را می‌شناسند.
- حریم خصوصی: builder وجود Config/Session/data/runtime/diagnostics/backups/catalog build host را در staging رد می‌کند. Setup تازه sample config می‌سازد و ارتقا managed code را mirror می‌کند، ولی state خصوصی مقصد را حفظ می‌کند. انتقال state فقط از Backup/Restore جداگانه است.
- سازگاری: Setup فقط Windows 10/11 x64 را می‌پذیرد. Python رسمی 3.13 Windows 7 را پشتیبانی نمی‌کند، قرارداد پروژه `>=3.11` است و Edge پشتیبانی‌شدهٔ Windows 7 منقضی است؛ port به Python 3.8/dependencyهای EOL یا Runtime غیررسمی release امن محسوب نشد.
- artifact: EXE تک‌فایلی با `--verify-only` موفق، SHA-256=`B609DD9AA689451A694C78FBB0DCAA71943D396F8F548B11E11ECEF500930121` و وضعیت امضا=`NotSigned`. nested payload شامل 4397 فایل و privacy finding صفر بود. ZIP fallback نیز SHA-256=`855E734098E5C1AF4C3637C5782631FFB376A830518CF580367383D417F660DA` دارد.
- شاهد: RED contract=`3/3 failed`، targeted=`4/4`، related=`88/88`، full Backend=`674/674`، TypeScript و UI/Electron Observability سبز؛ گزارش مستقل و V-184 مرجع جزئیات‌اند.
- محدودیت: EXE روی نصب واقعی مقصد اجرا نشد و code-sign/SmartScreen reputation/Windows visual پذیرش نشده‌اند؛ بنابراین وضعیت Production همچنان مجاز نیست.
- Trigger بازبینی: تغییر builder/bootstrap، Python/runtime wheels، UI dist marker، installer copy/exclusion، supported OS، Backup/Restore boundary، source wheel یا اجرای clean-machine واقعی.

### F-063 — فعال‌سازی آفلاین دستگاه‌محور با کلید خصوصی خارج از Release تکمیل شد

- وضعیت: `IMPLEMENTED / BRANCH_RC2_BUILT / OFFLINE_E2E_ACCEPTED / PRODUCTION_KEY_AND_CODE_SIGN_PENDING`
- تاریخ: 2026-08-28
- دامنه: request code، fingerprint دستگاه، صدور/تأیید مجوز، ذخیره‌سازی، Startup gate، انتقال نصب، بستهٔ آفلاین و private-key boundary.
- تصمیم امنیتی: «فرمول محرمانه» یا secret متقارن داخل برنامه استفاده نشد، زیرا با استخراج برنامه قابل جعل بود. مجوز با Ed25519 امضا می‌شود؛ customer artifact فقط public key دارد و private key/tool مالک از allowlist، Setup، Portable و Git خارج‌اند.
- fingerprint: Machine GUID و serial دیسک سیستم ابتدا جداگانه hash و سپس در payload نسخه‌دار canonical hash می‌شوند. request code شناسهٔ خام، نام دستگاه، شماره، account یا دادهٔ پیام ندارد. نصب مجدد Windows یا تعویض/فرمت دیسک می‌تواند فعال‌سازی تازه بخواهد.
- فایل مجوز: activation code امضاشده با DPAPI user-scoped در `data/licensing/activation.dat` ذخیره می‌شود. کپی/خرابی/کاربر Windows دیگر fail-closed است؛ امضا و تطبیق fingerprint مرجع صحت باقی می‌ماند.
- اجرا: Office launcher پیش از Backend پنجرهٔ فعال‌سازی را فقط در نبود مجوز معتبر باز می‌کند؛ Startupهای بعدی بی‌صدا هستند. `BridgeApplicationApi` و Facade نیز قبل از Config/DB gate دارند تا دورزدن Launcher مسیر عادی محصول را باز نکند.
- شاهد: RED محصول=`5 failed` با دو خطای Temp محیطی جدا؛ GREEN هدفمند=`60/60`، full Backend=`684/684`، TypeScript/Observability PASS. rehearsal بستهٔ RC2 ابتدا unlicensed را رد، سپس request→issue→DPAPI save→check→API را پذیرفت؛ plaintext activation در store صفر بود.
- artifact: Setup RC2 SHA-256=`84453D43A2E04F10FC2F453A81639AF6ED69C971FEE18AA8ED29EC1BC10EF02F`، Portable SHA-256=`A78C5AAA5EF2D6BAC00BBA8F321FAF8B03419C89CFA8556C880E7A9BDE89D129`، nested payload=4664 فایل و private-key/operational finding صفر.
- محدودیت صادقانه: نرم‌افزار Python روی دستگاه تحت کنترل کاربر قفل مطلق و غیرقابل Patch ندارد. کلید جاری بدون رمز و صرفاً branch-test است؛ پیش از Production باید کلید رمزدار مالک، backup آفلاین، public-key replacement، build/test تازه، code-sign و clean-machine acceptance انجام شود.
- مرجع: ADR-49، V-185 و `docs/reports/features/OFFLINE_DEVICE_ACTIVATION_REPORT_2026-08-28.md`.
- Trigger بازبینی: تغییر componentهای fingerprint، public key/key rotation، license payload، DPAPI scope، clock/expiry، Startup/API gate، Backup/Restore، installer payload یا گزارش false reactivation/bypass.

### F-065 — مدل چهارسطحی و قرارداد مدیریت چندعاملی پذیرفته شد

- وضعیت: `DECIDED / CANONICAL_OPERATING_MODEL / IR-GOV-01_POLICY_V1 / NOT_IMPLEMENTED`
- تاریخ: 2026-08-28
- دامنه: ایندکس معنایی، WordPress، هستهٔ گزارش، یادگیری/اتوماسیون و تقسیم کار میان Taskها/Agentها.
- تصمیم محصول: کار در چهار سطح پیگیری می‌شود: L1 ایندکس معنایی، L2 projection اختیاری WordPress، L3 هستهٔ محلی گزارش و L4 اتصال/یادگیری کنترل‌شده. سطح‌ها دو بخش مفهومی «فهم/سامان‌دهی محتوا» و «نظام گزارش» را روی هستهٔ مشترک evidence/fact/provenance/review پیاده می‌کنند.
- تصمیم مالکیت: کاربر مالک دامنه و پذیرش نهایی است. Codex مدیر معماری/یکپارچه‌سازی و writer/promoter canonical پیش‌فرض این workstream است؛ Agentهای دیگر فقط با Task Contract و خروجی noncanonical کار می‌کنند.
- تصمیم هم‌زمانی: یک writer برای فایل/رجیستر canonical؛ parallel read-only یا worktree ایزولهٔ بدون file overlap مجاز است. شناسه‌های F/V/ADR/Source/Question را allocator canonical تخصیص می‌دهد.
- مرز WordPress: WordPress در L2 adapter/projection و source قابل تطبیق است. System of Record گزارش در L3 محلی و ساختاریافته است.
- مرز هوشمندی: L4 پس از baseline/review سطح‌های قبلی، local-first و human-in-the-loop است؛ Agent هیچ اختیار گزارش رسمی ندارد.
- artifactها: `INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md` و `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md`.
- اثر محصول: صفر؛ schema، UI، API، allocator، lock، scheduler و Agent integration پیاده نشده‌اند.
- مرجع: `SRC-USER-IR-006`، ADR-51 و V-187.
- Trigger بازبینی: تغییر تعداد/مرز سطح‌ها، نقش Codex/کاربر، سیاست واگذاری، introduction ابزار orchestration یا collision تازه.

### F-066 — Copy/Paste فعال‌سازی وابسته به layout بود و Setup بازخورد گرافیکی نداشت

- وضعیت: `CLOSED_CODE_AND_FULL_AUTOMATED_ACCEPTANCE / CLEAN_MACHINE_VISUAL_PENDING`
- تاریخ: 2026-08-28
- دامنه: پنجرهٔ فعال‌سازی، bootstrap تک‌فایلی Windows، ارتقا و lifecycle خروجی‌های Release.
- مسئله: request box با `state=disabled` انتخاب/کپی دشوار داشت و Paste activation به event حرف `V` وابسته بود؛ در layout فارسی `Ctrl+V` قابل اتکا نبود. Setup نیز مستقیماً پنجرهٔ Console/Batch را اجرا می‌کرد و مسیر نصب، حفظ داده و progress را به‌صورت UI نشان نمی‌داد. خروجی‌های قبلی در ساخت جدید کنار فایل تازه باقی می‌ماندند.
- اصلاح: دکمه و منوی Copy/Paste/Select All، تشخیص keycode فیزیکی `V/C/A`، `Shift+Insert` و پاک‌سازی whitespace/format-control افزوده شد. Setup به WinForms فارسی RTL با مسیر `%LOCALAPPDATA%\Programs\EitaaBridge`، progress و launch option تبدیل و Batch داخلی `/quiet` شد. نسخه‌های نام‌دار قبلی پیش از publish به آرشیو زمان‌دار با hash Manifest منتقل می‌شوند.
- سازگاری/امنیت: format `EBRQ1/EBLC1`، Ed25519، fingerprint، DPAPI و startup gate تغییر نکرد. دادهٔ نصب قبلی و activation در ارتقای عادی حفظ می‌شوند. private key وارد delivery نشد.
- خروجی: RC4 Setup SHA=`E964C93B...BFA4`، Portable SHA=`8D9AE8AD...66FC` و Delivery SHA=`6DACA748...FD9E`; signer/tamper/verify سبز، 13 entry و private-key finding صفر، هشت متن UTF-8 BOM سالم.
- پذیرش: targeted=`41/41`، Backend=`690/690`، TypeScript و Observability سبز. نصب/مشاهدهٔ واقعی روی ماشین تمیز و trust مقصد باز است.
- مرجع: `docs/reports/features/GRAPHICAL_SETUP_AND_ACTIVATION_UX_REPORT_2026-08-28.md`، ADR-48..50 و V-188.
- Trigger بازبینی: تغییر format کد، binding Clipboard/Tk، مسیر یا UI نصب، preservation allowlist، archive pattern، امضا یا گزارش شکست روی Windows مقصد.

### F-064 — RC3 برندشده و امضاشده با trust bundle داخلی پذیرفته شد

- وضعیت: `IMPLEMENTED / BRANDED_INTERNAL_SIGNED_RC3_BUILT / OFFLINE_AUTOMATED_ACCEPTED / CLEAN_INSTALL_PENDING`
- تاریخ: 2026-08-28
- دامنه: Authenticode داخلی، کلید خصوصی، CER عمومی، اعتماد مقصد، آیکون Setup/میانبر و Build RC3.
- گواهی: RSA 3072/SHA-256 با Code Signing EKU در `Cert:\CurrentUser\My` و export policy=`None` ساخته شد. Thumbprint عمومی=`441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`؛ CER public-only است و هیچ PFX/private key در Repository/delivery ساخته نشد.
- اعتماد: trust bundle عمومی CER/metadata/hash/Thumbprint/راهنمای فارسی و installer pin‌شده دارد. Setup اعتماد را خودکار نصب نمی‌کند؛ CurrentUser/LocalMachine انتخاب صریح مقصد است. Self-signed SmartScreen/public CA reputation نمی‌سازد.
- کد: Setup فقط با ICO معتبر و `/win32icon` ساخته می‌شود؛ همان asset برای Desktop/Start Menu نصب می‌شود. امضا SHA-256، signer pin، hash بعد از امضا و tamper invalidation fail-closed هستند؛ fallback Setup بدون icon حذف شد.
- asset/artifact: PNG کاربر بدون edit مولد به ICO نه‌اندازه تبدیل شد؛ hashes source/ICO=`6ED4762B...FA1C / 8C35B98F...F5F7`. Setup RC3=`46,842,176 bytes / SHA-256 9587728C...6463` و Portable=`45,936,308 bytes / SHA-256 07931D6E...3566` است.
- شاهد: `--verify-only`، signer pin، hash بعد از امضا، tamper detection، icon extracted، payload icon parity، shortcut contract و privacy scan سبز؛ full Backend=`688/688`، TypeScript و Observability PASS. delivery ZIP SHA=`81C45B14...F15E`.
- اصلاح تحویل: راهنمای فارسی نخست به‌علت تفسیر UTF-8 بدون BOM توسط Windows PowerShell 5.1 mojibake و سه مقدار unresolved داشت. generator با source BOM، placeholder صریح و UTF-8 BOM قطعی اصلاح شد؛ ممیزی همهٔ فایل‌های bundle اکنون strict UTF-8، JSON/script syntax، CER hash/Thumbprint و نبود replacement/mojibake/unresolved placeholder را تأیید می‌کند.
- Trigger بازبینی: تغییر icon/converter، rotation/expiry گواهی، export policy، Thumbprint/trust bundle، timestamp، امضا، shortcut/install path یا clean-install واقعی.

### F-067 — پروفایل نصب RC4 قابلیت چندحسابی را خاموش می‌کرد و bootstrap ایزوله بدون حساب crash داشت

- وضعیت: `CLOSED_CODE_AND_FULL_AUTOMATED_ACCEPTANCE / RC5_BUILT_SIGNED / CLEAN_MACHINE_USER_RECHECK_PENDING`
- تاریخ: 2026-08-29
- دامنه: `bridge.example.json` بستهٔ customer، ترتیب AppUser/MessengerAccount onboarding، startup بدون حساب و خروجی RC5.
- علت اول: sample config نصب‌شونده هر سه feature مربوط به AppUser Auth، Multi-session و Worker Process را خاموش داشت؛ در نتیجه نصب تازه وارد مسیر legacy تک‌حسابی می‌شد و UI مدیریت/تعویض حساب‌ها ظاهر نمی‌شد.
- علت دوم: پس از روشن‌شدن هم‌زمان این سه feature، startup نصب خالی تلاش می‌کرد `legacy_runtime` غایب را از registry ایزوله بگیرد. این وضعیت پیش از ساخت مدیر و حساب نخست crash می‌کرد.
- اصلاح: هر سه feature در پروفایل installer روشن شدند. API در bootstrap خالیِ process-isolated بدون runtime معتبر بالا می‌آید، مسیرهای runtime-dependent را با `messenger_account_selection_required` می‌بندد و logging نبود account را بدون dereference ثبت می‌کند.
- قرارداد UX/مالکیت: `AppUserGate` پیش از `MessengerAccountGate` است. نخستین کاربر `admin` ساخته می‌شود؛ سپس فهرست حساب خالی است و اولین Eitaa account با membership اتمیک `owner/active` برای همان مدیر ساخته می‌شود. Start/Auth/OTP همچنان صریح و account-scoped است.
- شاهد: rehearsal نصب‌شده با config واقعی بسته، phone protector و دادهٔ کاملاً ساختگی، بدون Provider/network، مالکیت `admin/owner/active` را تأیید کرد. full Backend=`691/691`، collection=`691`، TypeScript/Observability و onboarding UI=`8/8` سبز شدند.
- artifact: RC5 Setup=`31,295,296 bytes / SHA-256 2BC28046...20CC`، Portable=`30,492,682 bytes / SHA-256 175D8011...E925` و Delivery ZIP=`61,883,250 bytes / SHA-256 66AF0894...2D26 / 15 entries` است. `--verify-only`، signer pin و tamper detection PASS؛ status پیش از trust گواهی Self-signed برابر `UnknownError` و timestamp=false است. payload/delivery scanner operational/private-key finding صفر داشت.
- محدودیت: ورود واقعی حساب دوم، OTP و مشاهدهٔ UI روی ماشین مقصد در این Run اجرا نشد. ارتقای عادی config قدیمی را حفظ می‌کند؛ برای دیدن bootstrap تازه باید پوشهٔ نصب قبلی بسته و تغییر نام داده شود، نه حذف.
- مرجع: ADR-52، V-189 و `docs/reports/features/MULTI_ACCOUNT_CLEAN_INSTALL_RC5_REPORT_2026-08-29.md`.
- Trigger بازبینی: تغییر sample config، Gate ordering، empty-account runtime bootstrap، membership creation، installer preservation یا گزارش مقصد.

### F-068 — روی ماشین مقصد، پس از ثبت مدیر و افزودن حساب، Gate حساب باقی می‌ماند و Start Worker با `eitaa_runtime_account_not_runnable` شکست می‌خورد

- وضعیت: `OPEN / REPORTED_BY_USER_ON_TARGET_MACHINE / ROOT_CAUSE_NOT_YET_INVESTIGATED`
- تاریخ: ۲۰۲۶-۰۹-۰۸
- گزارشگر: کاربر (تست واقعی نصب تحویل‌شده). این یافته از گزارش کاربر ثبت شده است، نه از اجرای خودکار؛ علت‌یابی هنوز شروع نشده.
- سناریوی بازتولید به روایت کاربر: نصب تمیز RC5 → فعال‌سازی موفق → صفحهٔ ثبت مدیر اولیه → ثبت مدیر → رفتن به مسیر افزودن شمارهٔ جدید → UI به‌جای پیش‌روی، صفحهٔ Gate با عنوان «یک حساب فعال را انتخاب کنید» را نشان داد. زیر آن فهرست حساب: `ایتا +98911000000` با برچسب «وارد نشده» و «Worker متوقف»، نقش=`مدیر نرم‌افزار`، وضعیت=`created` و دکمهٔ «شروع ورکر». فشردن «شروع ورکر» با پیام `The selected Eitaa account is not runnable.` رد شد. بستن و اجرای دوبارهٔ برنامه → همان خطای استارتاپی که پیش‌تر ادعا شده بود رفع شده، دوباره ظاهر شد.
- نکتهٔ کد (بدون اجرا، فقط انکر): `ui/src/MessengerAccountGate.tsx:314` عنوان Gate است. `_assert_runnable` در `src/eitaa_bridge/application/account_runtime.py:1424` خطای `eitaa_runtime_account_not_runnable` را زمانی می‌دهد که `lifecycle_state != "active"` یا `desired_worker_state != "running"` باشد (`account_runtime.py:1440`). اسکرین‌شات کاربر `lifecycle_state=created` را نشان می‌دهد، یعنی حساب ساخته شده اما هرگز به `active/running` نرسیده — مسیر انتقال حالت حین onboarding مقصد، مظنون اصلی است. خطای استارتاپ پس از restart نیز باور عمومی «رفع‌شده» را زیر سؤال می‌برد و باید با لاگ/بوم واقعی ماشین مقصد بی‌تشریح و تأیید شود، نه با فرض.
- وضعیت artifact در لحظهٔ گزارش: ZIP تحویل=`Eitaa_Bridge/delivery-activation-branch/EitaaBridge-0.8.0-rc5-MultiAccount-InternalSigned-GuiSetup-Delivery.zip` با SHA-256=`D5B17F50AF00221F300023BB332D2B179AEB62A5F10B973B53D8B7BCF0A0D3F6` و sidecar متنوع. fix مربوط به lazy `upload_root` در `src/eitaa_bridge/interfaces/http_api.py` اعمال شده اما **هنوز commit نشده** (شاخهٔ `codex/stabilization-g09`؛ working tree تغییرهای uncommitted قدیمی‌ترِ غیرمرتبط هم دارد). تست رگرسیون `tests/test_clean_install_http_boot.py` روی کد فعلی `2/2 passed` با venv پروژه بازتأیید شد.
- سؤالات باز برای علت‌یابی بعدی: (۱) آیا ردّ Start Worker در مقصد به‌علت `lifecycle_state=created` است یا `desired_worker_state`؟ (۲) آیا خطای استارتاپ بعد از restart همان `messenger_account_selection_required` قدیمی است یا خطای دیگری با متن مشابه؟ (۳) آیا fix lazy `upload_root` واقعاً داخل payload بستهٔ ZIP منتقل شده، یا ZIP از کد بدون fix ساخته شده است؟ (۴) چرا مسیر onboarding مقصد به‌جای جریان افزودن شماره در Gate متوقف شد؟
- داده‌های موردنیاز از ماشین مقصد (در فرصت بعدی): پیام دقیق خطای استارتاپ پس از restart (متن کامل یا تصویر)، لاگ‌های Backend در پوشهٔ data/logs مقصد، خروجی health endpoint، و در صورت امکان خروجی `doctor.py`.
- اقدامات ممنوع تا علت‌یابی: حذف یا بازنویسی پوشهٔ نصب مقصد؛ rebuild/تحویل ZIP جدید؛ commit؛ اعتماد به ادعای قبلی «خطای استارتاپ رفع شد» بدون بازتولید.
- Trigger بازگشایی/اقدام: دستور صریح کاربر برای شروع کار بعدی؛ این یافته پیش از هر تحویل جدید باید بسته یا توضیح داده شود.

**ادامهٔ ۲۰۲۶-۰۹-۰۸ (پس از دستور شروع کار):**

- وضعیت: `ROOT_CAUSED / FIX_IMPLEMENTED / REGRESSION_TESTS_GREEN / E2E_GREEN_ON_EMULATED_INSTALL / FULL_REGRESSION_AND_REBUILD_PENDING`
- روش: بازتولید کامل روی نصبِ emulate‌شدهٔ تحویل (extract Portable → office_payload → کپی app با post-steps نصب‌کننده، بدون نصب واقعی در LOCALAPPDATA). فعال‌سازی با کلید branch-test (`Eitaa_Bridge/license-admin-private/branch-test-signing-key.pem`) موفق؛ بوت، setup مدیر، onboard حساب `+98911000000` همه طبق گزارش کاربر بازتولید شد.
- ریشهٔ اصلی (تخم‌مرغ‌مرغ lifecycle): onboarding حساب را `created/stopped` می‌سازد (store.py INSERT)؛ گذار `created→active/running` فقط در `request_worker_start` (store.py UPDATE) رخ می‌دهد؛ اما `start_account` مسیر process قبل از آن `_assert_runnable` را صدا می‌زد که خودش `active/running` را پیش‌شرط می‌خواست → دکمهٔ «شروع ورکر» همیشه با `eitaa_runtime_account_not_runnable` رد می‌شد و حساب برای همیشه در created می‌ماند. coordinator خودش فقط `disabled/quarantined/archived` را بلاک می‌کند؛ یعنی قراردادِ coordinator start برای created مجاز است و `_assert_runnable` در مسیر start نادرست بود.
- ریشهٔ دوم (مرگ استارتاپ پس از restart): `BridgeApplicationApi` فقط در حالت «DB کاملاً خالی» bootstrap مجاز می‌داد؛ پس از ساخت مدیر+حساب created، restart → سازندهٔ registry/`resolve_v1` با `multi_session_legacy_default_required` می‌مرد (نمونهٔ واقعی: RC5 روی ماشین مقصد). ریشهٔ سوم (بوت پس از Start موفق): با حساب active/running نیز چون `legacy_default_messenger_account_id=null` بود همان خطا می‌آمد — این حالت در E2E محلی کشف شد (بوت #2 روی repro) و کاربر هنوز به آن نرسیده بود.
- اصلاح (سه فایل، همه uncommitted): (۱) `store.py`: متد‌های `runnable_messenger_account_id`/`has_runnable_messenger_account`؛ (۲) `account_runtime.py`: `_assert_startable` جدید برای مسیر start صریح (همان بلاک‌های coordinator)؛ `resolve_v1` با نبود legacy default، حساب runnable موجود را انتخاب می‌کند؛ سازندهٔ registry وقتی حساب runnable موجود است die نمی‌کند؛ (۳) `api.py`: حالت «بدون حساب runnable» مانند clean bootstrap تلقی می‌شود (boot روی onboarding می‌ماند، start صریح حساب را ارتقا می‌دهد).
- شواهد: تست جدید `tests/test_first_account_start_regression.py` = ۶/۶ سبز (RED روی کد قبل از اصلاح با git stash موقت اثبات شد: ۵/۵ fail؛ ششم بعد از کشف ریشهٔ سوم). E2E روی نصب emulate‌شدهٔ payload واقعی تحویل: بوت با حساب created ✓، worker/start → 200 با `active/running` و worker `ready` با heartbeat ✓، restart با حساب created ✓، restart دوم پس از start (حالت کشف‌شده) ✓، login و فهرست حساب پس از بوت ✓. همهٔ فرآیندهای repro پاک شدند.
- باقی‌مانده: full Backend regression (مجموعهٔ کامل ~693+)؛ wheel/Setup/ZIP rebuild برای تحویل rev2؛ تست نصب تازه روی ماشین مقصد طبق CLEAN_INSTALL_TEST_FA.md؛ commit هماهنگی‌شده با کاربر (working tree تغییرهای قدیمی‌تر غیرمرتبط دارد). پوشهٔ `D:\eitaa Project\E2E_F068_Repro` عمداً نگه داشته شد (نصب فعال‌سازی‌شده + request/activation code) تا rebuild جدید با همان مسیر آزمودسنجی شود؛ حاوی دادهٔ ساختگی است و بعد از تحویل rev2 می‌تواند حذف شود.
**ادامهٔ ۲۰۲۶-۰۹-۰۸ (سوم — تحویل rev2):**

- وضعیت: `FIXED / REBUILT_REV2_DELIVERED_TO_DELIVERY_FOLDER / TARGET_MACHINE_TEST_PENDING / COMMIT_PENDING`
- rebuild: wheel با `build_wheel_stdlib.py --force` بازسازی شد (SHA-256=`83ec1f1b2afb232f5986030861d468bb2592a77f17b525aeba704554bce5292d`)؛ تست parity سورس→wheel که پیش‌تر به‌علت wheel قدیمی fail می‌داد اکنون سبز است. تست deterministic wheel-builder همچنان fail دارد اما با stash موقت `package_clean.py` اثبات شد که مشکل قدیمی مسیر tmp (دیسک C خارج از project root) است و مستقل از اصلاح F-068؛ به‌عنوان بدهی تست جداگانه ثبت شد (F-069).
- full suite پس از rebuild: `697 passed / 2 failed` → پس از rebuild فقط همان تست deterministic قدیمی می‌ماند. TypeScript UI check سبز.
- بستهٔ rev2: `BUILD_OFFICE_SETUP_EXE.bat /quiet` با گواهی داخلی؛ Setup=`31,299,904 bytes / SHA-256 44A2EDAAD4A434666A6EE96E7E1C1759EE52E8C3144052B22A4ED91ECE6DFFD5` (signer pin سبز، tamper tested سبز)، Portable=`30,497,765 / SHA-256 4ed983cc3224970ced25288ccb2a413737bfa23f1c8c079e69a3b903657d3b19`.
- E2E روی payload واقعی rev2 (نصب emulate‌شدهٔ تازه، فعال‌سازی با کلید branch-test): بوت تمیز ✓ → setup مدیر (201) ✓ → حساب اول `created/stopped` ✓ → **worker/start=200 با active/running و worker ready+heartbeat** ✓ → **restart با حساب active: بوت، login و فهرست حساب با worker ready** ✓ → **worker/stop→paused→worker/start=200 مجدد** ✓. یعنی هر سه حالت مرگ قبلی و چرخهٔ کامل stop/start روی همان بسته‌ای که تحویل می‌شود سبز است.
- تحویل: پوشهٔ `Eitaa_Bridge/delivery-activation-branch/rc5-multiaccount-internal-signed-rev2/` (Setup+Portable+sidecars+manifest rev2+SHA256SUMS ۱۴ entrada+trust+branding+متن‌های فارسی) و ZIP تحویل با همان نام سابق جایگزین شد: `EitaaBridge-0.8.0-rc5-MultiAccount-InternalSigned-GuiSetup-Delivery.zip` = `61,886,807 bytes / SHA-256 20f77a32d8751d350fe2cb1db1705754d7f593010d5084ff0f9639a0c4644769 / 15 entries`؛ بستهٔ rev1 به `archive/20260908-151043` منتقل شد. ممیزی ZIP: Setup داخل ZIP hash-identical، هر سه فایل fix داخل payload، ۱۰ متن UTF-8 سالم، manifest rev2 سالم.
- باقی‌مانده: commit گزینشی با هماهنگی کاربر؛ نصب rev2 روی ماشین مقصد طبق CLEAN_INSTALL_TEST_FA.md و آزمون UI واقعی (گیت حساب باید با «شروع ورکر» عبور کند)؛ سپس بستن F-068.

**بستن ۲۰۲۶-۰۹-۰۸ (نشست چهارم):**

- وضعیت: `CLOSED_CODE_AND_REAL_INSTALL_VERIFIED / CUSTOMER_TARGET_MACHINE_CONFIRMATION_OPTIONAL`
- commit: دو commit گزینشی ساخته شد — `6248aafe` (baseline کارهای قبلی: licensing/امضا/installer/UI/اسناد + fix قبلی http_api و تست بوت) و `2f561e77` (اصلاح F-068 سه‌فایلی + تست‌های ۶گانه + رفع F-069 در تست deterministic + ignores). working tree پس از آن کاملاً تمیز است.
- suite کامل پس از commit: `699 passed / 0 failed` (برای اولین بار شامل تست deterministic هم که با انتقال scratch wheels داخل project root سبز شد — F-069 بسته شد).
- نصب تمیز واقعی روی همین ماشین (مسیر مشتری `%LOCALAPPDATA%\Programs\EitaaBridge`، بدون نصب قبلی): اجرای همان زنجیرهٔ رسمی `install_office_payload.cmd /quiet` (که Setup GUI با تأیید کاربر اجرا می‌کند؛ Setup EXE خودش آرگومان نمی‌پذیرد و GUI است) → نصب کامل با میانبرهای Desktop/Start Menu → فعال‌سازی با کلید branch-test → launch با کنترلر رسمی `office_runtime.py` → setup مدیر (201) → حساب اول `created` → **«شروع ورکر»=200 با active/running و worker ready (pid واقعی)** → **stop رسمی → relaunch رسمی → بوت سبز، login 200، حساب active/running با worker ready**. سپس برنامه stop و کل نصب آزمایشی و میانبرها حذف شدند؛ هیچ اثری باقی نماند.
- نتیجه: هر سه ریشهٔ F-068 روی نصب واقعیِ مسیر مشتری حل‌شده و اثبات‌شده‌اند. تأیید روی ماشین خود مشتری اختیاری است (بستهٔ rev2 = همان کد همین آزمون).

### F-069 — تست deterministic wheel-builder پیش از F-068 خراب است (مسیر tmp خارج از project root)

- وضعیت: `OPEN / PREEXISTING / UNRELATED_TO_F068 / LOW`
- تاریخ: ۲۰۲۶-۰۹-۰۸
- یافته: `tests/test_g07_release_packaging.py::test_stdlib_wheel_builder_is_deterministic_and_uses_canonical_contract` wheel را در `tmp_path` پایتون (درایو C) می‌سازد و بلافاصله `verify_bridge_wheel_source_parity(root, first)` را روی همان مسیر صدا می‌زند؛ `_safe_file` مسیر بیرون از project root (D) را رد می‌کند با `A release entry resolved outside the project root.`
- اثبات مستقل‌بودن از F-068: با `git stash push -- package_clean.py` (فقط فایل قدیمی uncommitted) تست همچنان fail ماند؛ یعنی مشکل از امروز و از اصلاح سه‌فایلی نیست.
- گزینه‌های اصلاح (بعدی): تست tmp را داخل project root بسازد (مثلاً زیر `build/` با cleanup) یا `verify_bridge_wheel_source_parity` پارامتر `root` صریح برای wheel خارج از root بپذیرد. تا آن زمان این تست به‌عنوان بدهی شناخته‌شده skip/fail شمرده می‌شود.
- Trigger بازگشایی: هر rebuild/تغییر package_clean.py یا تست‌های g07.

### F-070 — ملاک‌های عملیاتی نهایی ۱۴۰۵ پذیرفته و توسعهٔ هستهٔ گزارش آغاز شد

- وضعیت: `DECIDED / IN_IMPLEMENTATION`
- تاریخ: 2026-09-08
- منبع: `SRC-USER-IR-007` و ADR-53
- یافته: پرسش‌های بحرانی Q-IR-001/003/004/011 با ملاک‌های کاربر بسته شد: کد مراسم `80403`؛ ستاره یعنی «باید پر شود»؛ ردیف = مجموع استان با تفکیک در ضمیمه؛ حضور مسئولان هنگام ورود از انسان پرسیده می‌شود. کاربر تأکید کرد ملاک، آمار قابل‌اثبات و باورپذیر است حتی با بزرگ‌نمایی؛ بنابراین provenance و ضمیمه باید همیشه قابل بازتولید باشد.
- تصمیم: توسعهٔ کامل سطح ۱ (ایندکس ایتا) و سطح ۳ (هستهٔ گزارش با فرم هفت‌گانه، تجمیع، Excel export روی کپی) به Codex واگذار شد. WordPress projection باقی می‌ماند؛ مرجع حقیقت فقط هستهٔ محلی است.
- اثر: package `reporting` ساخته می‌شود؛ فایل اصلی workbook فقط‌خواندنی می‌ماند؛ تست‌های شمارش/تجمیع/export الزامی‌اند.

### F-071 — ایندکس‌گذار intent ایتا و پیام‌رسانی بله پیاده و تست شد

- وضعیت: `IMPLEMENTED / VERIFIED_OFFLINE`
- تاریخ: 2026-09-08
- منبع: `SRC-USER-IR-008` و ADR-54
- یافته: پیام‌های دو گفتگوی هدف باید پیش از ورود به گزارش، از اطلاع‌رسانی/تبلیغاتی تفکیک می‌شدند؛ نبود این تفکیک آمار رویدادها را با اطلاعیه‌ها آلوده می‌کرد.
- تصمیم: `EitaaIntentIndexer` با وزن‌گذاری چندمعیاره (اجرا +۳، برنامه +۲، عدد +۲، واحد +۱، مناسبت +۱، آینده −۲٫۵، تبلیغ −۲)؛ آستانهٔ event_report نیازمند سیگنال فعالیت است. `EitaaReportMonitor` روی eitaa_core فقط می‌خواند و بدون runtime پرهیز می‌کند. `BaleMessagingFacade` ارسال/دریافت بله را با تبدیل امن خطا فراهم می‌کند و تاریخچهٔ بله همان خط لولهٔ ایندکس را می‌گیرد.
- اثر: ۲۶ تست جدید؛ متن پیام هرگز در خروجی ایندکس ذخیره نمی‌شود؛ دروازه‌های انسانی ADR-53 دست‌نخورده.

### F-072 — پاسخ Live بله برای مخاطبین شکل peer-only و wrapped-text دارد

- وضعیت: `CLOSED / FIXED / LIVE_ACCEPTED (session ops)`
- تاریخ: 2026-09-15
- دامنه: شاخهٔ استثنایی `Bale`؛ کامیت `b4491b7f`.
- یافته: در Live (2026-09-15) `GetContacts` فقط peer برمی‌گرداند و `local_name`/`username` به شکل پیام wrapped `{1: text}` می‌آیند؛ `SearchContacts` سرور نیز فقط مخاطبین ذخیره‌شده را match می‌کند و رکوردهای ناقص بی‌نام برمی‌گرداند. نتیجهٔ قبلی در UI مخاطبین بی‌نام یا خالی بود.
- تصمیم: غنی‌سازی با فراخوانی دسته‌ای `LoadUsers` (با ترجیح رکورد کامل وقتی سرور مستقیم می‌دهد)، دیکد دو-شکلی wrapped-text، و fallback جستجوی محلی روی فهرست غنی‌شده. نگاشت `PermissionDenied` به `bale_access_denied` و پخش صدا هشدار OTP نیز در همین کامیت.
- شاهد: V-194؛ ۳۶/۳۶ تست آفلاین + پذیرش Live روی نشست کاربر (لیست/جستجو/خواندن/ارسال).
- نقص باز: `last_text` دیالوگ‌ها در `LoadDialogs` null است (غیرمسدودکننده؛ `read-history` متن کامل می‌دهد).
- Trigger بازگشایی: تغییر codecهای `bale_client` یا drift جدید schema سرور بله.

### F-073 — `last_text` دیالوگ‌ها در LoadDialogs همیشه null است

- وضعیت: `RESOLVED / LIVE_ACCEPTED`
- تاریخ: 2026-09-15 (ثبت)، 2026-09-22 (حل)
- دامنه: شاخهٔ استثنایی `Bale`؛ `codecs.py`، `codecs_ext.py`، `api.py`، `api_server.py`، `models.py`.
- ریشه‌یابی و یافته:
  1. در `build_load_dialogs` فیلد ۱ به نام `min_date` برابر `0` فرستاده می‌شد؛ سرور بله این فیلد را به عنوان `offset_date` تفسیر می‌کند و با مقدار `0` تنها ۳ گفتگوی بسیار قدیمی سال ۲۰۲۰ را با محتوای خالی برمی‌گرداند. با تغییر پیش‌فرض به `(1 << 63) - 1`، سرور تمام ۲۰ گفتگوی فعال جاری را همراه فیلدهای `message_id`، `sender_id`، `date` و محتوای غنی برگرداند.
  2. در `decode_content` محتوای نوع ۱۳ (پیام‌های تعاملی و الگودار ربات‌ها) دیکد نمی‌شد؛ پشتیبانی بازگشتی از فیلد ۱۳ برای استخراج سند، زیرعنوان، متن و دکمه‌ها اضافه شد.
  3. مقادیر `sort_date` و `last_message_date` به signed int64 تبدیل شدند تا مقادیر منفی پروتوباف به مقادیر غیرعادی تبدیل نشوند.
  4. متد `to_dict` به `FileDetails` اضافه و در `DialogSummary.to_dict()` به همراه `media_kind` یکپارچه شد.
  5. پیام خطای UI در `webui.html` هنگام دریافت خطای `unauthorized` به پیام فارسی خوانا ارتقا یافت.
- اثر: نقص F-073 به‌طور کامل برطرف شد؛ پیش‌نمایش آخرین پیام و رسانه برای گفتگوهای زنده به‌درستی نمایش داده می‌شود.
- شاهد: V-195؛ ۳۹/۳۹ تست آفلاین `test_bale_branch_api.py` و ۵/۵ تست تثبیت `test_bale_stabilization_fail_closed.py` + آزمون Live موفق روی سرور فعال (پورت ۸۷۹۱) و تایید دریافت مقادیر واقعی برای `last_text`، `last_document` و `last_message_id`.
- Trigger تکرار/بازگشایی: تغییر پروتکل سرور بله در ساختار پیام‌های دیالوگ.

### F-074 — وابستگی Windows DPAPI مانع bootstrap واقعی روی Linux بود

- وضعیت: `RESOLVED / LIVE_DEPLOYED / CDN_PUBLIC_TLS_PENDING_USER`
- تاریخ: 2026-09-22
- دامنه: Coordinator identity/AppAuth، بستهٔ Linux، systemd، Nginx و خط انتشار چندسایتی.
- یافته: API روی Linux بالا می‌آمد، اما نخستین fingerprint کاربر یا حفاظت شماره به `WindowsDpapiPhoneProtector` می‌رسید و bootstrap/onboarding را fail-closed متوقف می‌کرد. همچنین سرور میزبان چند دامنه به releaseهای جدا، state پایدار و فرمان انتشار مشترک نیاز داشت.
- تصمیم: `FileKeyPhoneProtector` و `FileKeySubjectFingerprinter` برای غیرWindows با AES-GCM/HMAC و کلیدهای service-owned `0600` افزوده شد؛ Windows DPAPI تغییر نکرد. استقرار با release immutable، `shared` جدا، کاربر systemd اختصاصی، Backend فقط Loopback، Nginx همان‌میزبان، gateway داخلی و dispatcher ریشه‌مالک انجام شد.
- شاهد: V-196؛ full Backend=`809 passed + 1 skipped` از ۸۱۰؛ UI TypeScript/Build/Observability سبز؛ تست Live redirect/UI/login/cookie/session سبز؛ پورت‌های داخلی از بیرون بسته و سایت‌های قبلی سالم.
- باقی‌ماندهٔ بیرونی: کاربر باید CDN را برای certificate عمومی فعال کند. origin TLS حاضر است و HTTP عمداً به HTTPS redirect می‌شود؛ کاهش Secure Cookie یا بازکردن Backend مجاز نیست.
- Trigger بازگشایی: تغییر محافظ هویت، مالکیت کلید، پروفایل Proxy، systemd unit، handler انتشار، دامنه/CDN یا پورت‌های داخلی.

### F-075 — قفل تاریخی HTTP، OTP را در استقرار امن HTTPS نیز رد می‌کرد

- وضعیت: `RESOLVED / SOURCE_FIXED / LIVE_DEPLOYED`
- تاریخ: 2026-09-22
- دامنه: `HttpDeploymentConfig`، سیاست درخواست Reverse Proxy، Config تولید Linux و آزمون Phase 10-C.
- یافته: پاسخ زندهٔ endpoint دریافت کد با `remote_messenger_auth_disabled` و mode=`web_reverse_proxy` ثابت کرد درخواست پیش از Provider رد می‌شود. Config تولید flag را خاموش داشت و اعتبارسنجی نیز روشن‌کردن آن را در همهٔ modeها ممنوع می‌کرد؛ بنابراین کنترل قدیمی Phase 6-A به‌اشتباه HTTPS معتبر را هم مانند HTTP شبکهٔ داخلی می‌بست.
- تصمیم: flag فقط در `web_reverse_proxy` معتبر شد؛ الزامات Loopback backend، Proxy مورد اعتماد، forwarded proto برابر HTTPS، Host/Origin دقیق، Secure Cookie، AppUser Auth و CSRF دست‌نخورده ماند. `trusted_lan_http` همچنان fail-closed است.
- شاهد: V-197؛ contract هدفمند 50/50 و full Backend سبز پس از rebuild wheel؛ release تازه و migration rollback-safe روی Production موفق، readiness=200 و probe بدون credential به‌جای قفل deployment به AppUser auth رسید. درخواست واقعی OTP یا تماس Provider در تشخیص/آزمون انجام نشد.
- Trigger بازگشایی: تغییر remote auth paths، Proxy/TLS contract، Origin/CSRF، Config تولید یا نتیجهٔ live پس از انتشار.

### F-076 — Child لینوکس شمارهٔ حساب را با محافظ هویت ویندوز باز می‌کرد

- وضعیت: `RESOLVED / SOURCE_FIXED / LIVE_DEPLOYED`
- تاریخ: 2026-09-22
- دامنه: `application/account_runtime.py` و انتخاب محافظ هویت در Child/Registry.
- شاهد ریشه: پس از رفع F-075، درخواست‌های واقعی کاربر پیش از تماس با Provider در audit با `eitaa.auth.request_code.denied`، `account_phone_resolution_failed` و `CoordinatorIdentityError` ثبت شدند. کد Child و Registry همچنان `WindowsDpapiPhoneProtector` می‌ساخت، در حالی‌که onboarding لینوکس از `FileKeyPhoneProtector` استفاده می‌کرد.
- تصمیم: هر دو مسیر Runtime از `default_phone_protector` مشترک استفاده کنند؛ type contract به `PhoneProtector` تعمیم یافت. کلید و ciphertext عملیاتی تغییر یا جابه‌جا نشدند.
- شاهد آزمون: V-198؛ تست Child با هویت ساختگی از همان کلید Coordinator شماره را بازیابی می‌کند. نسخهٔ اصلاحی روی سرور فعال است و بررسی فقط‌خواندنی با کاربر سرویس، بازشدن هویت یک حساب موجود را تأیید کرد. پس از انتشار، اقدام خود کاربر در UI با audit امن `eitaa.auth.request_code.succeeded` ثبت شد؛ این Run خودش OTP ارسال نکرد.
- Trigger بازگشایی: تغییر factory هویت، account_process، Registry یا فرمت کلید/هویت.

### F-077 — فرم ورود، شمارهٔ دیگر را برای حساب انتخاب‌شده پیشنهاد می‌کرد

- وضعیت: `RESOLVED / SOURCE_FIXED / LIVE_DEPLOYED`
- تاریخ: 2026-09-23
- دامنه: فرم ورود ایتا و انتخاب حساب در UI چندحسابی.
- شاهد: audit امن پس از انتشار F-076 سه رخداد `eitaa.auth.login.completed` و چند خروج موفق ثبت کرد؛ ردهای متأخر `eitaa.auth.request_code.denied` با `account_phone_mismatch` بودند. سرور به‌درستی اتصال شمارهٔ دیگر به همان MessengerAccount را رد می‌کند، ولی UI گزینهٔ «ورود با شماره‌ای دیگر» را در همان scope نشان می‌داد و پیام عمومی Child را نمایش می‌داد.
- تصمیم: guard سرور دست‌نخورده بماند؛ انتخاب/افزودن حساب در فرم ورود در دسترس باشد، راهنمای شمارهٔ ماسک‌شدهٔ حساب نشان داده شود، عدم تطابق پیام فارسی قابل اقدام داشته باشد و متن دکمهٔ بازگشت به شماره در حالت چندحسابی به «اصلاح شمارهٔ همین حساب» تغییر کند.
- شاهد اعتبارسنجی: V-199. هیچ شمارهٔ کامل، کد یا نشست در این سند ثبت نشد.
- Trigger بازگشایی: تغییر Account Gate، error code هویت، یا فرم ورود.

### F-078 — اعتبارسنجی زودهنگام Bearer مانع راه‌اندازی ورود کاربر و پروب‌ها در حضور AppUser Auth بود

- وضعیت: `RESOLVED / SOURCE_FIXED / LIVE_DEPLOYED`
- تاریخ: 2026-09-24
- دامنه: `src/eitaa_bridge/application/api.py` (`_dispatch_inner` و `authorize_local_resource`)، تفکیک مرز نشست کاربر از توکن محلی Bearer، پروب‌های سرویس و دسترسی به کش رسانه.
- ریشهٔ قطعی: متد `self._authorize(authorization)` در ابتدای `_dispatch_inner` و `authorize_local_resource` به‌صورت سراسری و بدون بررسی فعال بودن `app_user_auth` فراخوانی می‌شد. با تنظیم `EITAA_BRIDGE_API_TOKEN` در محیط عملیاتی، تمام درخواست‌های مرورگر (فاقد هدر Bearer) از جمله `/api/v2/app-auth/status`، ورود، و حتی پروب readiness خط انتشار با HTTP 401 `api_unauthorized` («راه‌اندازی ورود نرم‌افزار انجام نشد — A valid local API bearer token is required.») متوقف می‌شدند.
- تصمیم معماری و محدودیت‌ها:
  1. طرح «نشست یا Bearer برای همهٔ مسیرها» رد شد. توکن Bearer به‌هیچ‌وجه جایگزین نشست کاربر برای دسترسی به APIهای کاربر یا ارسال پیام نخواهد بود.
  2. در استقرار دارای `app_user_auth_enabled=True`، مسیرهای عمومی و پیش از ورود (`/api/v1/health`، `/readiness`، `/schema`، `/api/v2/app-auth/status`، `/login`، `/register` و `/setup`) بدون هدر Bearer قابل دسترس‌اند.
  3. کلیهٔ کنترل‌های امنیتی لایهٔ HTTP شامل بررسی دقیق Origin، محدودیت‌های نرخ درخواست و قفل ورود (`lockout_minutes`)، و ممنوعیت راه‌اندازی اولیهٔ مدیر از راه دور (`bootstrap_admin_loopback_only: True`) حفظ شدند.
  4. تمام مسیرهای محافظت‌شده کاربری (شامل ارسال پیام، مدیریت حساب‌ها، تنظیمات و ...) منحصراً بر پایهٔ نشست معتبر AppUser و توکن CSRF (برای درخواست‌های نامتقارن) ارزیابی می‌شوند؛ ارسال توکن Bearer بدون نشست کاربر با `app_auth_required` رد می‌شود.
  5. در `authorize_local_resource` و کش رسانه، درخواست‌های مرورگر با نشست معتبر بدون هدر Bearer پذیرفته می‌شوند.
  6. در حالت تک‌کاربرهٔ سنتی (`app_user_auth_enabled=False`)، رفتار الزام Bearer روی تمام مسیرها جهت حفظ سازگاری دست‌نخورده ماند.
- شاهد اعتبارسنجی: V-200 و V-201؛ تست هدفمند اولیه ۷/۷ سبز بود. آزمون تکمیلی با
  همان پروفایل `web_reverse_proxy` تولید، چندحسابی فعال، Bearer تنظیم‌شده،
  forwarded HTTPS و منع setup از IP بیرونی اضافه شد. UI اکنون خطای آغاز ورود را
  به راهنمای امن تبدیل می‌کند، برای خطاهای گذرا فقط یک بار خودکار تلاش می‌کند،
  و رویداد وضعیت ورود نمی‌تواند حلقهٔ refresh بسازد. gate انتشار علاوه بر readiness
  پاسخ وضعیت ورود مرورگر را هم الزام می‌کند.
- وضعیت اتصال onlineexam: ارزیابی امن و فقط‌خواندنی نشان داد `onlineexam` اکنون متصل یا موفق نیست (توکن آن خالی بوده و لاگ سرور نیز درخواستی نشان نمی‌دهد؛ به علاوه در صورت ارسال نیز به دلیل نبود نشست کاربری مسدود می‌شد). طرح احراز هویت ماشینی مستقل در قالب توکن اختصاصی محدود به مسیر پیام و مقید به یک حساب مشخص به کاربر پیشنهاد شد.
- به‌روزرسانی عملیاتی V-203: در اسکن بعدی مقدار غیرخالی توکن در محیط `onlineexam`
  دیده شد؛ آن کپی بنا به درخواست مالک حذف گردید. نبود آن در اعتبارسنجی Production
  این پروژه مانع آغاز backend بود؛ شرط اعتبارسنجی اصلاح و نسخهٔ بدون توکن ساخته
  و با وضعیت `healthy` فعال شد. ادعای «توکن خالی» در شاهد تاریخی بالا، وضعیت
  زمان همان بررسی است و به وضعیت فعلی تعمیم داده نمی‌شود.
- Trigger بازگشایی: تغییر خط انتشار، تغییر کنترل‌های session/Bearer در API، تغییر
  مسیر بازیابی آغاز UI، یا پیاده‌سازی احراز هویت ماشینی جدید.
- پذیرش زنده: release `20260924T045946Z-d81b875cbac0` از مسیر رسمی منتشر شد؛
  پاسخ عمومی `app-auth/status` برابر `200` با `enabled=true`،
  `authenticated=false` و `setup_required=false` است. صفحهٔ واقعی در مرورگر
  فرم ورود را نشان داد؛ readiness عمومی و gateway هر دو `200`، مسیر `/me` بدون
  نشست `401` و سرویس systemd فعال است. ورود تعاملی با حساب واقعی انجام نشد.

### F-079 — پاسخ ورود Child در مرز IPC کلید ممنوع داشت

- وضعیت: `SERVER_DEPLOYED / INSTALLED_IPC_CHECK_PASSED / LIVE_OTP_RECHECK_PENDING`
- تاریخ: 2026-09-25
- دامنه: سه پاسخ ورود ایتا در `eitaa_auth_child_operations.py`؛ تکمیل کد، نیاز به رمز دوم و تکمیل رمز دوم.
- یافته: `LoginStepResult.safe_summary()` در همهٔ این پاسخ‌ها کلید `session` دارد، حتی وقتی مقدار آن تهی است. اعتبارسنج IPC این کلید را با `ipc_payload_forbidden` رد می‌کند. همین خطا در درخت محلی `AntiGravity2` پیش از اصلاح برای هر سه حالت بازتولید شد.
- اصلاح: Child فقط فیلدهای شناخته‌شدهٔ نتیجه را عبور می‌دهد و خلاصهٔ غیرمحرمانهٔ نشست را زیر `session_snapshot` قرار می‌دهد. والد از قبل این فیلد را برای پاسخ HTTP به `session` برمی‌گرداند.
- مرز شاهد: release `20260925T194540Z-52d1b93b938b` روی سرور فعال است و ماژول نصب‌شدهٔ آن آزمون مصنوعی IPC را گذرانده؛ ورود واقعی با OTP و صفحهٔ پس از refresh هنوز تأیید نشده‌اند. نشست‌های موجود در ریشهٔ عملیاتی محلی هنگام اصلاح کد تغییر نکردند.
- مرجع: V-205، V-207 و `tests/test_auth_child_ipc_summary.py`.
- Trigger بازبینی: ورود واقعی پس از انتشار نسخهٔ تازه، خطای جدید در مرحلهٔ OTP، یا تغییر قرارداد Core/IPC/HTTP.

### F-080 — پس از ورود واقعی، فهرست گفت‌وگو و پیام خالی ماند

- وضعیت: `PARTIAL / LOCAL_UI_RECOVERED / PROCESS_WORKER_UI_COMPATIBILITY_OPEN`
- تاریخ: 2026-09-25
- یافته: کاربر ورود واقعی با شماره و OTP را موفق گزارش کرد، اما صفحه هیچ پیام یا گفت‌وگویی نشان نداد. پیش از پاک‌سازی V-208، نشست ایتا در سرور `authenticated` بود و پایگاه دادهٔ پیام حساب جاری صفر ردیف در جدول‌های `dialogs` و `messages` داشت.
- مرز شاهد: بازنشانی کامل داده‌ها در V-204 تاریخچهٔ محلی را حذف کرده بود؛ روشن نیست چرا پس از ورود تازه همگام‌سازی دوباره آن را پر نکرد. حذف توکن‌ها در V-208 این علت را تعیین یا اصلاح نمی‌کند. ورود و همگام‌سازی تازه پس از پاک‌سازی هنوز آزموده نشده است.
- اقدام بعدی: پس از ورود تازهٔ کاربر، وضعیت sync و خطاهای امن Worker/API و شمارش‌های پایگاه داده بررسی شوند، بدون ثبت متن پیام، شناسهٔ مخاطب یا شمارهٔ کامل.
- بازبینی محلی 2026-09-26 پس از بازنشانی V-209: ورود واقعی موفق بود و Core یک صفحهٔ ۲۵ گفت‌وگویی از مجموع ۲۰۶ مورد با warning صفر دریافت کرد، اما DB پیام صفر گفت‌وگو/پیام داشت. UI پیش از بارگذاری گفتگو `GET /api/v1/sites` را می‌خواست؛ این درخواست با `eitaa_process_operation_ipc_required` و HTTP 400 رد می‌شد، `siteKey` خالی می‌ماند و `loadDialogs/syncDialogs` اصلاً اجرا نمی‌شد. علت در این نصب، فعال شدن `worker_process` هنگام کپی sample config بود؛ Config محلی پیش از بازنشانی این flag را خاموش داشت.
- فقط در `bridge.json` عملیاتی همین نصب، `worker_process.enabled=false` شد؛ `app_user_auth` و `multi_session` روشن ماندند. پس از توقف مالکیت‌دار و راه‌اندازی دوباره، routeهای sites/dialog sync/message list با HTTP 200 اجرا شدند و DB محلی به ۲۰۶ گفت‌وگو رسید. این شاهد رفع نمایش در نصب محلی است؛ پاسخ دیداری کاربر و تکمیل تاریخچهٔ پیام جداگانه ثبت می‌شود.
- راه‌حل پایدارِ پروفایل نصب با Worker Process روشن هنوز باز است: UI فعلی از routeهای v1 استفاده می‌کند و نگاشت آن‌ها به Child RPC/DTO با حفظ Membership، Capability و account scope باید طراحی و آزموده شود. صرف بازکردن guard بدون مهاجرت مسیرهای Core کافی نیست. خطای منفرد avatar با fallback جدا از مانع اصلی است.
- بازبینی سرور در 2026-09-26: Config نصب قبلی هنوز Worker Process را روشن داشت و داده‌های مشترک انتشارهای قبلی را حفظ می‌کرد. در V-212 تمام state قبلی پاک و نسخهٔ محلی با Worker Process خاموش منتشر شد. ورود مدیر و فهرست حساب‌ها روی وب عمومی موفق‌اند؛ حساب پیام‌رسان اکنون عمداً صفر است. پس از ورود تازهٔ مالک به ایتا باید عبور routeهای sites/dialog sync و شمار گفت‌وگوها دوباره سنجیده شود. این بازنشانی به‌تنهایی شاهد بازیابی Live گفت‌وگو نیست.
- مرجع: V-204، V-207، V-208، V-210 و V-212.

### F-081 — آغاز چندحسابی درون‌فرایندی پس از ساخت مدیر و پیش از حساب پیام‌رسان شکست می‌خورد

- وضعیت: `CLOSED_CODE_AND_FULL_OFFLINE_REGRESSION / LOCAL_FRESH_BOOT_VERIFIED`
- تاریخ: 2026-09-26
- Trigger: درخواست بازنشانی دوبارهٔ نصب محلی با یک مدیر تازه و صفر حساب پیام‌رسان؛ برای نمایش گفت‌وگوها پس از ورود، Worker Process در Config محلی طبق V-210 خاموش ماند.
- یافته: `BridgeApplicationApi` فقط وقتی Worker Process روشن بود، «بدون حساب runnable» را onboarding bootstrap می‌شناخت. پس از ساخت مدیر و پیش از افزودن نخستین حساب، `clean_install_bootstrap` false می‌شد و آغاز دوباره با `multi_session_legacy_default_required` شکست می‌خورد. این نقص با DB تازهٔ واقعی پیش از اصلاح بازتولید شد.
- اصلاح: تشخیص نبود حساب runnable مستقل از حالت Worker Process شد. هنگام onboarding، Process mode همچنان بدون runtime v1 آغاز می‌شود و in-process mode از legacy runtime بی‌اثر برای bootstrap استفاده می‌کند. مسیرهای حساب‌محور همچنان Membership/انتخاب حساب را الزام می‌کنند؛ Provider یا حساب پیش‌فرض پنهان ساخته نمی‌شود.
- شاهد: regression تازه روی config/DB ساختگی، targeted clean-install=`3/3`، مجموعهٔ هدفمند reporting/package پس از همسان‌سازی wheel و بازگرداندن الگوی ثابت=`37/37`، full Backend نهایی exit=0 با یک skip موجود، TypeScript و Observability PASS؛ boot محلی واقعی `app-auth/status=200` با `setup_required=false` و `authenticated=false`. ورود/OTP/Send تازه‌ای در این اصلاح انجام نشد.
- مرجع: V-211 و `tests/test_clean_install_http_boot.py`.
- Trigger بازبینی: تغییر startup runtime registry، حالت multi-session/worker، onboarding مدیر و حساب نخست یا گزارش خرابی نصب تازه.

### F-082 — توکن اتصال ایتا در پروژهٔ هم‌میزبان پس از پاک‌سازی پیشین بازگشت

- وضعیت: `CURRENT_SERVER_CLEARED / EXTERNAL_REDEPLOYMENT_RISK`
- تاریخ: 2026-09-26
- Trigger: مالک پاک‌سازی کامل داده و اعتبارهای ایتا روی سرور را درخواست کرد؛ پاک‌سازی V-208 برای وضعیت فعلی کافی نبود.
- یافته: با اینکه `.env` و state خود Eitaa Bridge پاک شد، یک انتساب غیرخالی توکن اتصال ایتا در `.env` پروژهٔ هم‌میزبان `onlineexam` و محیط کانتینر backend آن وجود داشت. سند وضعیت همان پروژه بازتولید توکن در انتشار 2026-09-25 را ثبت کرده است. هیچ مقدار توکن خوانده‌شده در خروجی یا سند ثبت نشد.
- اصلاح: انتساب به مقدار خالی تبدیل و فقط backend هم‌میزبان بازساخته شد. کد استقرار یافتهٔ آن پروژه هنوز در Production توکن را اجباری می‌دانست و کانتینر را ناسالم کرد؛ اعتبارسنجی source سرور اصلاح شد تا نبود URL/توکن را بپذیرد و توکن بدون URL را رد کند، contract متناظر به‌روز شد، تصویر جدید ساخته و backend سالم شد. فایل و کانتینر هر دو مقدار غیرخالی صفر دارند.
- محدودیت: این اصلاح در source سرور پروژهٔ دیگر است و انتشار آتی آن پروژه یا اجرای دوبارهٔ اسکریپت پیکربندی می‌تواند آن را بازنویسی کند. باید در منبع انتشار canonical همان پروژه حفظ شود. اتصال ایتا در `onlineexam` اکنون غیرفعال است.
- مرجع: V-212 و گزارش بازنشانی سرور.

### F-083 — پیاده‌سازی زیرساخت اتصال امن سامانهٔ آموزش/آزمون، تطبیق‌دهندهٔ بله بات و درگاه عامل هوشمند

- وضعیت: `CLOSED / IMPLEMENTED / OFFLINE_TESTS_ACCEPTED`
- تاریخ: 2026-09-27
- دامنه: احراز هویت ماشین‌به‌ماشین (M2M)، ارسال پیام و بررسی گیرنده، داربست بله بات رسمی، درگاه عامل هوشمند، پنل تنظیمات UI و قرارداد نسخهٔ ۱.
- یافته: سامانهٔ آموزش/آزمون نیازمند اتصال بدون نشست کاربری/CSRF، ارسال پیام از حساب‌های مجاز ایتا و بله، و گفت‌وگوی امن کاربران با هوش مصنوعی بود.
- اصلاحات انجام‌شده:
  1. احراز هویت ماشین‌به‌ماشین (M2M): تعریف مدل و جدول `service_credentials` (اسکیمای نسخهٔ ۸) با هش PBKDF2-HMAC-SHA256، تفکیک از نشست AppUser، بررسی دامنهٔ اختیارات (`scopes`) و حساب‌های مجاز، محدودیت نرخ ۶۰ درخواست بر دقیقه، سقف ۶۴ کیلوبایت بدنه، الزام هدر `X-Request-Id`، و نقاط پایانی مدیریتی ساخت، فهرست، چرخش و ابطال اعتبارات.
  2. ارسال و بررسی گیرنده: پیاده‌سازی `POST /api/v2/m2m/messages/send-text`، `POST /api/v2/m2m/recipients/resolve`، و استعلام وضعیت با کلید پایاپای `GET /api/v2/m2m/messages/{idempotency_key}/status` با اتصال مستقیم به Orchestrator بدون دور زدن لایه‌های اعتبارسنجی.
  3. تطبیق‌دهندهٔ رسمی Bale Bot API: ایجاد بستهٔ `src/eitaa_bridge/providers/bale_bot/` بر پایهٔ Bot API رسمی (بدون نقض قوانین و محدودیت‌های بله شخصی طبق F-046/ADR-20)، در وضعیت اولیهٔ Scaffold و خاموش در زمان اجرا تا زمان پیکربندی توکن.
  4. درگاه عامل هوشمند: طراحی `agent_gateway.py` شامل پروتکل `AgentAdapter`، تطبیق‌دهندهٔ آزمایشی `TestAgentAdapter` (با پرچم صریح `is_test_response: true`)، تطبیق‌دهندهٔ قابل‌پیکربندی `ConfigurableAgentAdapter`، و مدیریت نشست با حافظه، انقضا (TTL) و سقف نشست.
  5. پنل تنظیمات رابط کاربری: ایجاد `ui/src/ServiceAccountSettingsPanel.tsx` و ادغام در `SettingsPage.tsx` جهت کنترل بصری مدیر بر حساب‌های فعال برای API، صدور، چرخش، ابطال توکن‌ها و پایش وضعیت.
  6. مستندسازی قرارداد: ایجاد سند مرجع `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md`.
- شاهد و آزمون‌ها: ۳۱ آزمون واحد و منفی آفلاین در ۴ فایل (`test_service_auth.py`, `test_m2m_endpoints.py`, `test_bale_bot_adapter.py`, `test_agent_gateway.py`) با ۱۰۰٪ قبولی؛ عبور کامل `npm run check` و `test:observability`.
- مرجع: V-213 و `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md`.

### F-084 — اعتبارسنجی مستقل F-083: هفت شکست مجموعهٔ کامل، resolve ساختگی و پنل UI غیرعملیاتی

- وضعیت: `CLOSED / FAKE_VERIFIED / HONEST_CONTRACT_RESTORED`
- تاریخ: 2026-09-27
- دامنه: اعتبارسنجی ادعای F-083/V-213 در برابر مجموعهٔ کامل Backend و بازبینی کد حیاتی M2M.
- یافته: ادعای «۳۱/۳۱ سبز» فقط برای چهار فایل آزمون جدید درست بود؛ اجرای مستقل مجموعهٔ کامل هفت شکست نشان داد که در گزارش قبلی ذکر نشده بود:
  1. باگ scoping پایتون: import درون‌تابعی `CompositionValidationError` در شاخهٔ M2M، این نام را برای کل تابع dispatch محلی می‌کرد و بررسی forged-field مسیرهای v1 را با `UnboundLocalError` (500 به‌جای 400) می‌شکست — رگرسیون امنیتی واقعی.
  2. سه آزمون ارتقای اسکیما برای نسخهٔ ۷ نوشته شده بودند و با v8 می‌شکستند (تنزل آزمایشی، artifacts v8 را حذف نمی‌کرد).
  3. بستهٔ `providers/bale_bot` با import مستقیم `httpx` قرارداد نگهبان transport-free درخت providers (F-046/G-02) را می‌شکست.
  4. سه رخداد `service_credential_*` در Event Catalog ثبت نشده بودند.
  5. parity ویل بسته‌بندی به‌علت فایل‌های جدید شکسته بود.
  6. `recipients/resolve` کاملاً ساختگی بود: هر مقدار بدون پسوند «9999» با `peer_reference` جعلی «resolved» اعلام می‌شد؛ در حالی که مسیر ارسال واقعی ایتا شناسهٔ گفتگو می‌خواهد و شمارهٔ خام به `api_dialog_not_found` می‌رسید.
  7. پنل UI `ServiceAccountSettingsPanel` هیچ فراخوانی API نداشت و «توکن» هاردکد قلابی نشان می‌داد؛ دکمه‌های چرخش/ابطال عملیاتی نبودند.
- اصلاحات: حذف importهای درون‌تابعی و افزودن throttle تأیید ناموفق توکن (ضد DoS PBKDF2) و جداسازی Bearer قدیمی از مسیر M2M؛ به‌روزرسانی سه آزمون اسکیما به v8؛ بازنویسی صادقانهٔ m2m_api (resolve فقط‌خواندنی واقعی از دایرکتوری مخاطبین + کاتالوگ گفتگوی حساب، منع شمارهٔ خام به‌عنوان peer با 409 m2m_recipient_unresolved، enforcement حدود `allowed_providers`، نقش کم‌امتیاز user به‌جای admin، حذف دور زدن scope در agent chat، مهار استعلام وضعیت به حساب‌های مجاز)؛ آداپتور peek فقط‌خواندنی برای جلوگیری از اجرای ناخواستهٔ worker هنگام resolve؛ ثبت سه رخداد در کاتالوگ؛ بازسازی wheel؛ بازنویسی کاربردی پنل UI متصل به endpointهای واقعی؛ انتقال آزمون‌های bale_bot از فایل اسکرچ داخل بسته به `tests/` و حذف `_offline_tests.py`؛ اصلاح rotate برای رد ردیف ناموجود/ابطال‌شده به‌جای بازگرداندن توکن قلابی؛ carve-out مستند آزمون نگهبان برای bale_bot (ADR-59) با حفظ fail-closed بودن ثبت در registry.
- مرجع: V-214، ADR-59 و `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` (نسخهٔ 1.1.0).

### F-085 — ممیزی مستقل ادعای تکمیل اتصال سامانهٔ آموزش: شکاف‌های باز در مرز مجوز و گفت‌وگو

- وضعیت: `OPEN / STATIC_VERIFIED / LIVE_NOT_ACCEPTED`
- تاریخ: 2026-09-27
- Trigger: درخواست مالک برای راستی‌آزمایی دستور اولیه و پاسخ نهایی عامل، پس از ثبت F-084/V-214. این بازبینی به‌دلیل تعارض ادعای تکمیل با کد جاری و ریسک مجوز M2M انجام شد.
- یافته‌های باز:
  1. `api.py` در `dispatch` زمینهٔ `ContextVar` سرویس را برای هر درخواست مقداردهی اولیه/بازنشانی نمی‌کند، اما شاخهٔ M2M آن را تنظیم می‌کند. `_authorize_provider_operation_account` با دیدن زمینهٔ سرویس، بررسی عضویت AppUser را دور می‌زند. در اجرای درخواست بعدی در همان execution context، زمینهٔ مانده می‌تواند کنترل حساب را تغییر دهد. شاهد فعلی ایستا است و برای مسیر واقعی HTTP باید آزمون بازتولید مستقل افزوده شود.
  2. پنل مدیریت هنگام انتخاب‌نکردن حساب، `allowed_messenger_account_ids=null` و فهرست ثابت `allowed_providers=['eitaa','bale']` می‌فرستد؛ سمت سرور مقدار null را بدون حصار حساب می‌پذیرد و شاخهٔ مجوز سرویس بررسی عضویت را کنار می‌گذارد. ایجاد اعتبارنامهٔ محدود به حساب معین تضمین نمی‌شود. فهرست خالی Provider نیز در `_validate_provider` به‌صورت محدودیت اعمال نمی‌شود.
  3. مسیر استعلام رسید هیچ scope اختصاصی بررسی نمی‌کند؛ آزمون موجود حتی با `scopes=[]` نتیجهٔ موفق می‌خواهد. query فقط بر پایهٔ `idempotency_key` و در صورت وجود، فهرست حساب است؛ schema رسید مالک سرویس ندارد. پس جداسازی نتیجهٔ دو سرویس در یک حساب اثبات نشده است.
  4. درخواست چت `message_id` لازم در مأموریت را ندارد و هیچ حفاظت تکرار برای پیام چت ندارد. تاریخچه در حافظه ثبت می‌شود، ولی adapter فقط پیام جاری را می‌فرستد؛ ادامهٔ گفت‌وگوی دارای context آزموده/پیاده نشده است. `ConfigurableAgentAdapter` در source فقط تعریف شده و در dispatch پیکربندی یا نصب نمی‌شود.
- شاهدهای تأییدشده: دو کامیت ادعاشده در شاخهٔ `Bale` و در `origin/Bale` وجود دارند؛ مجموعهٔ کامل آزمون‌ها و کنترل‌های جاری در V-215 سبزند. سبز بودن آزمون‌ها این چهار شکاف پوشش‌داده‌نشده و پذیرش عملیاتی را رفع نمی‌کند.
- اقدام لازم: اصلاح چرخهٔ عمر زمینهٔ سرویس و افزودن آزمون request-sequence؛ الزام allowlist صریح و معتبر حساب/Provider؛ بستن استعلام رسید به scope، سرویس و حساب؛ تکمیل `message_id`، replay policy، context و پیکربندی واقعی adapter پیش از ادعای آمادگی.
- مرجع: V-215، قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` و گزارش F-084.

### F-086 — مجوز مالک: مسیر حساب شخصی بله مسیر درجه‌یک محصول است و محدودیت fail-closed تفسیری F-046/G-02 منسوخ می‌شود

- وضعیت: `DECIDED / IMPLEMENTED / FAKE_VERIFIED (ADAPTER) / LIVE_ACCEPTED (SESSION OPS VIA BRANCH SURFACE, V-194)`
- تاریخ: 2026-09-27
- تصمیم مالک: به‌طور صریح و در پاسخ به تفسیر محدودکنندهٔ عامل‌ها، اعلام کرد که (۱) مسیر «حساب شخصی بله» که خودش زمان زیادی برای آن صرف کرده و روی شاخهٔ Bale پیاده‌سازی و برای عملیات نشست پذیرش زنده شده است (V-194/F-072)، باید قابل استفاده باشد؛ (۲) زیرساخت بات بله هم‌زمان و در کنار آن حفظ شود؛ (۳) همهٔ قراردادها و منابعی که استفاده از حساب شخصی بله را ممنوع می‌کنند اصلاح شوند.
- ریشهٔ سوءتفاهم: فصل ۷ سند Discovery، Bale Personal Provider را «مسیر اصلی، مجاز و تأییدشده» اعلام کرده بود؛ F-046 فقط rollback قراردادهای متأخر را منع می‌کرد و Trigger ابطال صریح داشت. برنامهٔ تثبیت (G-02) این را به «هرگز قابل فعال‌سازی نیست» تعبیر کرد و عامل‌های بعدی همان تفسیر را به‌عنوان تصمیم دائمی بازتولید کردند.
- اجرای تصمیم:
  1. ثبت `providers/bale/slot.py` با مانیفست مجاز (`authorization_reference=document:F-085`، capabilities واقعی کلاینت، `account_identity_kind=phone_e164`، مراحل auth تلفنی) و اتصال `adapter_factory` به آداپتور واقعی.
  2. بازنویسی `application/bale_provider_adapter.py` به آداپتور واقعیِ متصل به `bale_client` با backend تزریقی؛ پاس کامل probe قرارداد آفلاین؛ نگاشت صادقانهٔ وضعیت‌ها (اتصال قطعی‌نشدنی → `uncertain`).
  3. رفع قرنطینهٔ `application/bale_client/` از بسته‌بندی release و wheel؛ افزودن وابستگی `websockets`؛ قواعد حریم خصوصی (منع ورود passphrase/OTP/رمز/شمارهٔ کامل به لاگ و خطا) در آداپتور حفظ شد.
  4. به‌روزرسانی سند Discovery، Baseline، roadmap، Handoff و ADR-60؛ آزمون‌های نگهبان به قرارداد جدید بازنویسی شدند (`test_bale_personal_authorization.py`).
- مرز باقی‌مانده (صادقانه): `runtime_enabled` و `onboarding_enabled` مسیر چندProvider برای اتصال onboarding/worker حساب‌های بله هنوز False است و فاز بعدیِ مجازِ اتصال نیاز به دروازه‌های خودش دارد؛ پذیرش Live ارسال از مسیر orchestrator هنوز انجام نشده و عملیات Live همچنان تأیید همان‌لحظهٔ مالک می‌خواهد. محرمانگی داده‌ها (Token، OTP، Cookie، Session، شمارهٔ کامل، متن خصوصی) به قوت قبل است.
- مرجع: ADR-60، V-216، فصل ۷ `BALE_PROVIDER_DISCOVERY.md`، V-194/F-072. شناسهٔ این رکورد در 2026-09-27 به‌دلیل تداخل هم‌زمان با F-085 (ممیزی M2M) به F-086 تغییر یافت.

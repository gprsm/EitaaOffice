# برنامهٔ جامع تثبیت و رفع اشکال AntiGravity2

وضعیت: `G-00..G-09 COMPLETE / USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE`  
تاریخ مبنا: 2026-08-25  
دامنهٔ یافته‌ها: `F-039` تا `F-044`  
دفتر اجرای الزامی: [STABILIZATION_EXECUTION_LOG.md](STABILIZATION_EXECUTION_LOG.md)
Handoff توقف: [STABILIZATION_PAUSE_HANDOFF_2026-08-25.md](../handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md)
Handoff جاری Codex/AntiGravity: [ANTIGRAVITY_STABILIZATION_CURRENT.md](../handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md)
قرارداد همکاری: [CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md](CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md)

اصلاح دامنه در 2026-08-25: مطابق تصمیم تازهٔ کاربر، قراردادهای امنیت/حریم خصوصی متأخر—از جمله نمایش کامل شماره در سطح محصول—به نسخهٔ قدیمی برگردانده نمی‌شوند. آخرین قرارداد ثبت‌شدهٔ توسعهٔ Bale به‌عنوان تصمیم محصولی شناخته می‌شود، اما دامنهٔ این برنامه همچنان فقط مهار و رفع خرابی موجود Bale است و هیچ قابلیت تازه یا عملیات Live را مجاز نمی‌کند.

## ۱. هدف، مرز و اصل کنترل

هدف کلان این برنامه رساندن snapshot موجود `AntiGravity2` به یک baseline قابل‌بازگشت، قابل‌ممیزی، امن، قابل‌نصب و دارای آزمون سبز است؛ بدون بازسازی پروژه از صفر و بدون دست‌کاری داده‌های عملیاتی.

این سند در مرحلهٔ جاری فقط برنامه است. اجرای هر هدف فقط پس از دستور صریح کاربر آغاز می‌شود و در هر زمان حداکثر یک هدف اجرایی فعال خواهد بود.

مرزهای قطعی:

- توسعهٔ قابلیت تازه برای Bale فعلاً ممنوع است. فقط غیرفعال‌سازی، قرنطینه، اصلاح خرابی موجود و جلوگیری از ورود آن به runtime/release مجاز است.
- Login، OTP، Session واقعی، ارسال پیام، WordPress، نصب Proxy، تغییر Firewall، bind واقعی 80/443، migration یا rollback عملیاتی بدون تأیید همان لحظه اجرا نمی‌شود.
- `bridge.json`، `.env`، نشست واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` بدون مجوز جابه‌جا، بازنویسی یا حذف نمی‌شوند.
- هیچ `reset`، `checkout`، `clean`، `stage`، `commit` یا `push` بدون دستور صریح کاربر انجام نمی‌شود.
- آزمون‌های Provider باید تا مرحلهٔ پذیرش جداگانه کاملاً آفلاین و با Fake باشند.

## ۲. تعریف هدف کدها

| حوزه | هدف محصولی کد | وضعیت مطلوب پس از تثبیت |
|---|---|---|
| هستهٔ Application | هماهنگ‌سازی حساب، Provider و عملیات بدون دورزدن مرز چندحسابی | مسیر واحد، account-scoped و قابل‌ردیابی |
| Eitaa | Provider عملیاتی اول پروژه | رفتار موجود بدون regression و بدون عملیات زنده در آزمون |
| Bale | Provider اولویت دوم، اما فعلاً خارج از توسعه | disabled/scaffold، بدون runtime، onboarding یا network |
| احراز هویت | bootstrap امن نصب تازه و challenge متصل به نشست/مرحله/مهلت | replay و cross-challenge مردود؛ secret هرگز وارد log نشود |
| هویت و حریم خصوصی | حفظ قرارداد متأخر نمایش کامل شماره در سطح مجاز محصول، بدون نشت به لاگ/خروجی پشتیبانی | عدم rollback، تست رفتار مطلوب و redaction مستقل |
| ایندکس محلی | پردازش کنترل‌شدهٔ محتوای cache محلی | lifecycle کامل، account scope و failure قابل‌مشاهده |
| UI | نمایش صادقانهٔ capability و قرارداد Backend | TypeScript و همهٔ contractها سبز |
| بسته‌بندی/نصب | تولید خروجی فقط از allowlist و راه‌اندازی روی محیط خالی | بدون artifact خصوصی/آزمایشی و با fresh-install سبز |
| Observability | ثبت رخدادهای مادی بدون PII/secret | event catalog، correlation، audit و redaction قابل‌آزمون |
| مستندات | حافظهٔ canonical و شاهد قابل‌اتکا | UTF-8 سالم، شناسه یکتا، لینک معتبر و ادعای همسو با کد |

## ۳. حلقهٔ اجباری اهداف

چرخهٔ هر هدف به‌ترتیب زیر است:

`QUEUED → SCOPED → BASELINED → RED_VERIFIED → IMPLEMENTING → TARGETED_GREEN → REGRESSION_GREEN → DOCUMENTED → USER_ACCEPTED → CLOSED`

شاخه‌های استثنا:

- `BLOCKED`: نیاز به تصمیم کاربر، مجوز عملیاتی یا شاهد بیرونی؛ دلیل و شرط رفع مانع ثبت می‌شود.
- `ROLLED_BACK`: فقط فایل‌های دقیق همان Run با pre-image معتبر بازگردانده می‌شوند؛ rollback گسترده ممنوع است.
- `SUPERSEDED`: رکورد قبلی حذف نمی‌شود و رکورد تازه با شناسهٔ مرجع جای آن را می‌گیرد.

قواعد چرخه:

1. هر هدف شناسهٔ `G-00` تا `G-09` دارد و هر تلاش شناسهٔ `STAB-Gxx-Rnn` می‌گیرد.
2. قبل از اولین Write، دامنهٔ فایل‌ها و hash امن pre-image ثبت می‌شود.
3. ابتدا شکست فعلی با تست هدفمند بازتولید می‌شود. عبور از `RED_VERIFIED` فقط برای تغییر صرفاً مستندی یا encoding با دلیل ثبت‌شده مجاز است.
4. هر patch باید کوچک، هدف‌محور و فاقد تغییر نامرتبط باشد.
5. شکست تست پیش از retry ثبت و به یکی از گروه‌های `product_regression`، `test_drift`، `environment`، `permission`، `contract` یا `privacy` طبقه‌بندی می‌شود.
6. سبزشدن تست هدفمند به‌تنهایی برای بستن هدف کافی نیست؛ regression مرتبط، مستندات و دفتر شواهد نیز باید کامل باشند.
7. بسته‌شدن نهایی هر هدف به گزارش به کاربر و پذیرش او وابسته است.

## ۴. قرارداد دقیق لاگ‌گذاری

### ۴.۱ لایهٔ اول: دفتر اجرای مهندسی

تمام اقدام‌های خواندن، نوشتن، آزمون، build، تولید سند و عملیات احتمالی به‌صورت append-only در `STABILIZATION_EXECUTION_LOG.md` ثبت می‌شوند. حداقل فیلدهای هر رکورد:

| فیلد | الزام |
|---|---|
| `event_id` | یکتا؛ مانند `STAB-G03-R01-S04` |
| `started_at` / `ended_at` / `duration_ms` | ISO-8601 با timezone؛ زمان پایان برای اقدام تمام‌شده اجباری |
| `goal_id` / `run_id` | اتصال مستقیم اقدام به هدف و تلاش |
| `state_before` / `state_after` | انتقال وضعیت حلقهٔ هدف |
| `actor` | `codex` یا `user_approved_operation` |
| `action_kind` | یکی از `READ/WRITE/TEST/BUILD/GENERATE/OPERATION/DECISION` |
| `cwd` | مسیر نسبی/ریشهٔ پروژه؛ مسیر شخصی غیرضروری ثبت نمی‌شود |
| `intent` | نتیجه‌ای که اقدام باید ایجاد کند |
| `command_safe` | فرمان sanitize‌شده؛ آرگومان حساس با `[redacted]` |
| `files_intended` / `files_changed` | فهرست دقیق؛ عدم تغییر نیز صریح ثبت می‌شود |
| `pre_sha256` / `post_sha256` | فقط برای source/docs امن؛ نه داده، session یا secret |
| `exit_code` | عدد واقعی یا `N/A` برای تصمیم انسانی |
| `result` | `PASS/FAIL/BLOCKED/SKIPPED/PARTIAL` |
| `test_counts` | collected/pass/fail/error/skip در صورت وجود |
| `failure_class` / `reason_code` | برای هر شکست یا skip اجباری |
| `retry_of` / `supersedes` | اتصال تلاش یا تصحیح تازه به رکورد قبلی |
| `external_effect` | `none/read_only/test_temp/config/data/network/process/system` |
| `approval_ref` | برای عملیات نیازمند تأیید همان لحظه |
| `artifacts` | لینک گزارش، diff امن، Ledger یا Finding |

قواعد ثبت:

- رکورد شکست هرگز حذف یا بازنویسی نمی‌شود؛ retry شناسهٔ تازه می‌گیرد.
- اصلاح اشتباه لاگ با `supersedes` انجام می‌شود.
- فایل‌های تغییرکرده از خروجی واقعی پس از اقدام استخراج می‌شوند، نه فقط از قصد اولیه.
- خلاصهٔ خروجی آزمون ثبت می‌شود؛ dump کامل فقط در artifact امن و بدون secret نگهداری می‌شود.
- هر Run یک رکورد `RUN_STARTED` و یک رکورد `RUN_FINISHED` یا `RUN_BLOCKED` دارد.
- یکپارچگی دفتر با شناسهٔ یکتا، ترتیب زمانی، کامل‌بودن فیلدها، وجود مراجع و اسکن PII/secret کنترل می‌شود.

### ۴.۲ لایهٔ دوم: دفتر اعتبارسنجی

هر شاهد معنادار به‌صورت `V-NNN` در `VALIDATION_LEDGER.md` ثبت می‌شود: علت اجرا/تکرار، محیط، دامنه، نتیجه، شمار تست‌ها، اثر بیرونی، یافته‌های مرتبط، تاریخ انقضا و Trigger تکرار. خروجی‌های آزمایشی کوچک و تکراری فقط در دفتر اجرا می‌مانند؛ شاهد پذیرش هدف در هر دو دفتر ثبت می‌شود.

### ۴.۳ لایهٔ سوم: Runtime Event و Audit

هر رفتار مادی نرم‌افزار باید مطابق `LOGGING_AND_OBSERVABILITY.md` دارای `event` پایدار، `level`، `result`، `reason_code`، `correlation_id`، `operation`، `thread` و `fields` امن باشد. تغییر امنیتی/مالکیت/پیکربندی، reveal دادهٔ شخصی یا اثر بیرونی باید علاوه بر Event، Audit مستقل داشته باشد.

ثبت موارد زیر در همهٔ لایه‌ها ممنوع است:

- Token، Cookie، OTP، password، session payload و header/query حساس؛
- شمارهٔ کامل، متن خصوصی پیام، raw provider payload و raw exception مشکوک؛
- شناسهٔ حساس قابل‌انتساب یا مسیر شخصی غیرضروری؛
- dump کامل DB، Support Bundle یا محیط.

تست‌های adversarial باید ثابت کنند redaction روی exception، nested payload، URL/query، header و fieldهای ناشناخته نیز عمل می‌کند.

## ۵. ترتیب اهداف و برنامهٔ رفع

### G-00 — تثبیت baseline و قابلیت بازگشت

هدف: تبدیل snapshot جدید به مبنای نسخه‌پذیر بدون آسیب به پوشهٔ قبلی یا داده‌های عملیاتی.

اقدام‌ها:

1. inventory و hash امن source/UI/tests/scripts/installer/docs با exclusion عملیاتی.
2. اسکن secret و بررسی `.gitignore` پیش از هر ثبت نسخه.
3. ارائهٔ دو مسیر تصمیم به کاربر: پیوند غیرمخرب با تاریخچهٔ قبلی یا ایجاد repository/baseline تازه.
4. اجرای Git mutation فقط پس از انتخاب صریح؛ بدون `reset/checkout/clean`.
5. ثبت وضعیت اولیه، diff امن و نقطهٔ بازگشت. commit/tag فقط با دستور جداگانه.

معیار خروج: ریشهٔ جدید repository معتبر، snapshot جاری recoverable، داده‌های عملیاتی خارج از نسخه و گزارش baseline ثبت‌شده باشد.

### G-01 — سلامت حافظهٔ مهندسی و حاکمیت لاگ

هدف: حذف تناقض و خرابی متنی از مرجع canonical پیش از تغییر کد.

اقدام‌ها:

- اصلاح معنایی `F-035` و سند Bale Discovery که UTF-8 آن‌ها normalize شده اما نویسه‌های ازدست‌رفته هنوز نیازمند بازسازی از شاهد معتبرند.
- رفع شناسه‌های تکراری/خراب مانند `V-015` و `V-078`، مسیر کنترل‌کاراکتری `brain/...` و قالب فرمان‌های آسیب‌دیده.
- همسان‌سازی Baseline و گزارش‌های `PRODUCTION_READY` با یافته‌های باز `F-039` تا `F-044`.
- افزودن کنترل خودکار UTF-8، شناسهٔ یکتا، لینک محلی، نبود «چهار علامت سؤال جایگزینِ پیاپی»/`U+FFFD`، الگوی secret/PII و ادعای متناقض.

معیار خروج: کنترل تولید اسناد و لینک‌ها و کنترل‌های integrity تازه همگی سبز باشند.

### G-02 — مهار Bale و رفع خرابی موجود، بدون توسعه

هدف: Bale هیچ مسیر فعال محصولی یا شبکه‌ای نداشته باشد و وضعیت آن صادقانه `disabled/scaffold` باشد.

تفسیر دامنه: این غیرفعال‌سازی، لغو یا بازگردانی قرارداد متأخر توسعهٔ Bale نیست؛ یک اقدام تثبیتی موقت برای implementation شکستهٔ فعلی است. استفاده از آن قرارداد برای ساخت قابلیت تازه، login یا عملیات Live در این برنامه مجاز نیست.

اقدام‌ها:

- بازگرداندن manifest به `configured=false`، `runtime=false` و `onboarding=false` و حذف factoryهای فعال از registry.
- رفع BOM فایل slot و تست مربوط، بدون افزودن قابلیت.
- جلوگیری از import/reachability adapter و client شخصی شکسته در runtime، onboarding و release.
- حذف `token` از onboarding عمومی؛ account kind تازه برای Bale در این فاز ساخته نمی‌شود.
- نگه‌داری artifactهای عملیاتی پوشهٔ Bale بدون خواندن/حذف/جابه‌جایی؛ قرنطینه یا حذف فیزیکی فقط با مجوز.
- تست آفلاین برای نبود network، نبود factory، رد onboarding و false بودن capability.

معیار خروج: تمام contractهای B0/B1/B2 و privacy مرتبط سبز، هیچ ادعای live و هیچ مسیر شبکه‌ای Bale موجود نباشد.

### G-03 — نصب تمیز و احراز هویت آغازین

وضعیت اجرا: `COMPLETE` در 2026-08-26؛ F-041 بسته، Backend نهایی `610/610` و گزارش `../reports/stabilization/G03_CLEAN_INSTALL_AUTH_STABILIZATION_REPORT_2026-08-26.md`.

هدف: نصب کاملاً خالی بدون DB/config/session قبلی، ایمن و تکرارپذیر بالا بیاید.

اقدام‌ها:

- ایجاد مرکزی و idempotent مسیرهای لازم پیش از آغاز سرویس‌ها.
- bootstrap امن Coordinator DB و حالت setup اولیه، بدون الزام به حساب ازپیش‌موجود.
- اصلاح legacy challenge با handle opaque سمت سرور که به raw provider challenge، stage، TTL/deadline و generation نشست متصل است.
- بازگرداندن `challenge_id` از request و الزام/اعتبارسنجی آن در submit code/password؛ UUID تزئینی و کنترل‌نشده پذیرفته نیست.
- تست replay، cross-challenge، expiry، stage اشتباه، challenge مفقود و restart.
- هماهنگی installer و config example؛ تمام تست‌ها با Fake و ریشهٔ موقت خالی.

معیار خروج: fresh-install برای legacy و multi-session، startup تکراری و installer rehearsal ایزوله سبز باشد و هیچ network/provider واقعی لمس نشود.

### G-04 — هم‌ترازی قرارداد متأخر هویت و مرز مستقل لاگ

وضعیت اجرا: `G-04 COMPLETE / F-044 CLOSED` در 2026-08-26. هش‌های A تا D بدون drift؛ full Backend نخست `618/620` با دو timeout، isolation همان دو=`2/2` و full rerun تازه=`620/620`. TypeScript، Observability و UI onboarding=`7/7` سبزند. گزارش نهایی `../reports/stabilization/G04_IDENTITY_PRIVACY_STABILIZATION_FINAL_REPORT_2026-08-26.md`.

تقسیم اجرای کنترل‌شده:

- G-04-A: ممیزی قرارداد و تولید RED مستقل؛ کامل.
- G-04-B: اصلاح دو آزمون خالی و پوشش کلیدهای identity hint در redaction؛ `TARGETED_GREEN` در 2026-08-26، گزارش `../reports/stabilization/G04B_IDENTITY_REDACTION_GREEN_REPORT_2026-08-26.md`.
- G-04-C: جداسازی `phone_e164` از token در onboarding عمومی، بدون توسعهٔ Bale؛ `RELATED_REGRESSION_GREEN` در 2026-08-26، گزارش `../reports/stabilization/G04C_PUBLIC_ONBOARDING_IDENTITY_BOUNDARY_REPORT_2026-08-26.md`.
- G-04-D: اسکن خصمانهٔ Log/Audit/Diagnostic/Support Bundle و regression مرتبط؛ `ADVERSARIAL_GREEN` در 2026-08-26، گزارش `../reports/stabilization/G04D_PRIVACY_CHANNELS_ADVERSARIAL_REPORT_2026-08-26.md`.
- G-04-E: full regression، کنترل اسناد، بستن F-044 و گزارش نهایی؛ `COMPLETE` در 2026-08-26.

هدف: قرارداد فعلی نمایش کامل شماره حفظ شود و هیچ کد یا تستی آن را به masking قدیمی بازنگرداند؛ هم‌زمان ممنوعیت شمارهٔ کامل در Log/Audit/Diagnostic/Support Bundle به‌صورت مستقل اثبات شود.

تصمیم قطعی کاربر:

- `masked_phone()` برای هویت تلفنی می‌تواند مقدار canonical کامل را برای `display_hint/phone_hint` برگرداند و UI مجاز محصول آن را نمایش دهد.
- تست‌های قدیمی که masking یا رد `display_hint` کامل را الزام می‌کردند بازگردانده نمی‌شوند.
- این تصمیم، ثبت شماره در Runtime Log، Audit، Diagnostic، Support Bundle یا گزارش مهندسی را مجاز نمی‌کند؛ مرز `docs/SECURITY.md` و قواعد AGENTS پابرجاست.

اقدام‌ها:

- جایگزینی دو تست خالی با تست رفتار مطلوب تازه: پذیرش و نمایش مقدار canonical در مرز مجاز محصول، همراه با تست مستقل عدم ورود آن به Event/Audit/Diagnostic/Support Bundle.
- همسان‌سازی Baseline، Specification، Architecture و گزارش آزمون با قرارداد متأخر، بدون migration یا بازنویسی DB عملیاتی.
- جداسازی `phone_e164` از token در onboarding عمومی همسو با G-02؛ تغییر account kind یا قابلیت تازهٔ Bale خارج از دامنه است.
- هر migration یا rollback روی DB واقعی فقط با تأیید همان لحظه و برنامهٔ مستقل.

معیار خروج: هیچ assertion قدیمی masking بازنگردد، تست‌های جایگزین غیرخالی باشند و اسکن خروجی‌های لاگ/پشتیبانی نبود شماره و secret را ثابت کند.

### G-05 — lifecycle و Observability ایندکس خودکار

وضعیت اجرا: A=`3/4 RED`؛ B=`4/4`+`76/76`؛ C=`11/11`؛ D=`143/143`. G-05-E full Backend=`625/625` و TypeScript/Observability سبز است؛ closure اسناد در جریان و گزارش نهایی `../reports/stabilization/G05_AUTO_INDEX_LIFECYCLE_STABILIZATION_FINAL_REPORT_2026-08-26.md` ایجاد شد.

هدف: قابلیت دستی موجود حفظ شود و thread ناقص خودکار نتواند failure را پنهان یا پس از shutdown زنده بماند.

مسیر ایمن پیش‌فرض: scheduled auto-index تا تکمیل قرارداد scheduler غیرفعال شود. اگر نگه‌داری آن بعداً تأیید شد، `stop Event`، `join` محدود، account scope، idempotency، backoff و eventهای started/succeeded/failed/skipped/stopped اجباری است.

اقدام‌ها:

- حذف `except Exception: pass` و ثبت reason code امن.
- تست startup/close، تزریق failure، account isolation، عدم orphan thread و عدم network.
- اتصال correlation به job و event catalog.

معیار خروج: shutdown قطعی، نبود exception خاموش و پوشش failure/lifecycle سبز باشد.

### G-06 — ترمیم قرارداد آزمون و regression

وضعیت اجرا: `COMPLETE` در 2026-08-26. A تنها RED واقعی Phase 10 را ثابت کرد؛ B runner را به import/export canonical متصل کرد؛ C همهٔ ۹ runner UI، TypeScript و build محلی را سبز کرد؛ D برابر `307/307` و E full Backend برابر `628/628` با skip صفر است. تست خالی و skip/xfail بی‌دلیل صفر. گزارش نهایی `../reports/stabilization/G06_TEST_CONTRACT_AND_REGRESSION_STABILIZATION_FINAL_REPORT_2026-08-26.md`. حوزهٔ تست F-042 بسته و packaging آن صریحاً برای G-07 باز است.

هدف: هر تست یا واقعاً رفتار محصول را محافظت کند یا با دلیل مستند اصلاح شود.

اقدام‌ها:

- رفع دو شکست BOM و contractهای Phase 10/Phase 11 پس از تعیین product regression در برابر test drift.
- تغییر Phase 10 از وابستگی به محل helper به سنجش رفتار/import contract.
- بازیابی تست‌های `pass` یا خالی با assertion معنادار مطابق قرارداد متأخر؛ تست‌های masking حذف‌شده نباید کورکورانه بازگردند. اسکن empty-test افزوده می‌شود.
- اجرای تست هدفمند پس از هر هدف و سپس suite کامل Backend، تمام contractهای UI، TypeScript و build.
- انتظار قبلی `587 collected / 585 passed / 2 failed` baseline است؛ تغییر count باید با علت ثبت شود.

معیار خروج: صفر failure/error، تست خالی صفر و شمار/دلیل skip ثبت‌شده باشد.

### G-07 — سخت‌سازی بسته‌بندی و نصب

وضعیت اجرا: `COMPLETE` در 2026-08-26. A تا C encoding/blacklist را به allowlist+manifest+reproducibility تبدیل کردند. D stale wheel و dependency drift را بست؛ wheel 90 فایل/صفر drift و fresh venv آفلاین سبز شد. E Backend=`643/643` با skip صفر، TypeScript/Observability و دو archive نهایی بایت‌یکسان را پذیرفت. F-042 بسته و گزارش نهایی `../reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md` است؛ در پایان G-07، G-08/G-09 باز بودند و اکنون فقط G-09 باقی است.

هدف: خروجی release فقط از manifest سفید تولید شود.

اقدام‌ها:

- جایگزینی blacklist در `package_clean.py` با allowlist فایل‌های canonical.
- حذف قطعی secret/config/session/data/runtime/diagnostics/backups، artifactهای Bale، scratch/fix scripts، backup، prompt output، probe JSON، cache و egg-info از archive.
- dry-run manifest، SHA-256، privacy/secret scan، traversal/duplicate check و reproducibility.
- fresh-install rehearsal در مسیر ایزوله؛ publish/install واقعی فقط با مجوز.

معیار خروج: archive scan بدون finding، hash بازتولیدپذیر و نصب تمیز سبز باشد.

### G-08 — تکمیل Observability و پوشش لاگ

وضعیت اجرا: `COMPLETE` در 2026-08-26. A تا D scanner چندحسابی، lifecycle/catalog، write-health/retention/disk و Support Bundle را بستند. E wheel drift شش‌فایلی را یافت/بازسازی کرد و full Backend=`656/656`، TypeScript/Observability را پذیرفت. F-048 بسته و گزارش نهایی `../reports/stabilization/G08_OBSERVABILITY_COMPLETION_FINAL_REPORT_2026-08-26.md` است؛ G-09 باقی است.

هدف: هیچ failure مادی یا حساب پیکربندی‌شده‌ای خارج از پوشش scanner نماند.

اقدام‌ها:

- تعمیم scanner از مسیر hard-coded یک حساب به enumeration امن همهٔ logهای پیکربندی‌شده، بدون چاپ شناسهٔ حساس.
- پوشش background task، bootstrap، lifecycle و تصمیم‌های امنیتی در Event Catalog/Audit.
- تست correlation، redaction، malformed JSONL، retention/disk-health و Support Bundle.

معیار خروج: catalog coverage کامل برای تغییرهای این برنامه، اسکن همهٔ حساب‌ها و صفر نشت PII/secret باشد.

### G-09 — پذیرش نهایی و handoff

وضعیت اجرا: `COMPLETE / USER_ACCEPTED` در 2026-08-26. A تا C archive deterministic/privacy/fresh-install را سبز کردند؛ D full Backend=`656/656` با skip صفر، هر ۹ runner UI، TypeScript و build 1015-module را پذیرفت؛ E اسناد، Release Manifest و handoff را همسو و artifact نهایی را بازسازی کرد. کاربر closure را صریحاً پذیرفت. snapshot=`OFFLINE_RELEASE_CANDIDATE` است و دروازه‌های Production مستقل باقی‌اند.

هدف: یک شاهد واحد و قابل‌اتکا برای پایان تثبیت ایجاد شود.

حداقل پذیرش:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
```

همراه با تمام contractهای UI، build، fresh-install ایزوله، package dry-run، privacy/log scan و diff امن. هیچ پذیرش زندهٔ Eitaa/Bale، ارسال، WordPress یا تغییر سیستمی جزو این هدف نیست.

معیار خروج: Baseline، Findings، Ledger، Architecture، گزارش نهایی و handoff همسو؛ همهٔ کنترل‌ها سبز؛ پذیرش کاربر ثبت‌شده باشد. commit/tag فقط با دستور صریح جداگانه است.

## ۶. وابستگی و ترتیب اجرا

ترتیب اصلی:

`G-00 → G-01 → G-02 → G-03 → G-04 → G-05 → G-06 → G-07 → G-08 → G-09`

G-06 به‌صورت کنترل پیوسته بعد از هر هدف اجرا می‌شود، ولی تجمیع نهایی آن پس از اصلاحات کدی است. شروع هدف بعدی پیش از ثبت نتیجهٔ هدف جاری ممنوع است.

## ۷. دروازه‌های نیازمند دستور یا تأیید تازه

| دروازه | نیاز |
|---|---|
| انتخاب روش Git baseline | دستور کاربر در G-00 |
| stage/commit/tag/push | دستور صریح مستقل |
| تغییر دوبارهٔ قرارداد نمایش شماره | دستور صریح تازه؛ تصمیم جاری عدم rollback است |
| حذف/انتقال artifactهای Bale | تأیید هدف دقیق |
| migration/rollback دادهٔ واقعی | تأیید همان لحظه |
| Login/OTP/Session/Send/WordPress | تأیید همان لحظه |
| نصب/publish/Firewall/Proxy/Port | تأیید همان لحظه |

## ۸. Definition of Done هر هدف

یک هدف فقط وقتی قابل‌بستن است که:

1. هدف محصولی آن بدون توسعهٔ خارج از دامنه محقق شده باشد؛
2. تغییر نامرتبط وجود نداشته باشد؛
3. red/green هدفمند و regression مرتبط ثبت شده باشد؛
4. دفتر اجرا، Validation Ledger، Finding و سند موضوعی به‌روز باشند؛
5. اسکن secret/PII برای خروجی‌های مرتبط پاس شود؛
6. اثر بیرونی و مجوزها صریح باشند؛
7. گزارش قابل‌فهم به کاربر ارائه و پذیرش او دریافت شود.

## ۹. دستور پیشنهادی مرحلهٔ بعد

پس از تأیید این برنامه، نقطهٔ شروع پیشنهادی چنین است:

`G-00 را شروع کن؛ فقط baseline و گزینه‌های Git را آماده کن و پیش از هر stage/commit متوقف شو.`

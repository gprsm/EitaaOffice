# نقشه‌راه هوشمندسازی ایندکس و گزارش‌سازی

وضعیت: `PHASE_0 AUTHORIZED / DOMAIN_DISCOVERY_ACTIVE / PRODUCT_IMPLEMENTATION_NOT_STARTED`  
تاریخ آغاز: 2026-08-27  
Finding مرجع: `F-051`  
Validation مرجع آغاز: `V-163`  
Execution Log: [INDEX_INTELLIGENCE_EXECUTION_LOG.md](INDEX_INTELLIGENCE_EXECUTION_LOG.md)
مدل چهارسطحی: [INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md](INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md)  
قرارداد واگذاری: [MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md](MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md)

## ۱. هدف محصول

هدف، ساخت یک tagger پیچیده‌تر یا اتصال مستقیم پیام به WordPress نیست. محصول هدف باید شواهد موجود در Eitaa، WordPress و ورودی دستی مجاز را به دادهٔ ساختاریافته و قابل‌بازبینی تبدیل کند تا از آن بتوان چارچوب Excel جاری و گزارش‌های نسخه‌دار آینده را تولید کرد.

```text
Eitaa / WordPress / Manual input
              ↓
          source evidence
              ↓
      candidate claims and events
              ↓
       human review and provenance
              ↓
 versioned reporting rules and metrics
              ↓
 Excel / WordPress / future report projections
```

WordPress یک projection و منبع شواهد احتمالی است، نه Source of Truth گزارش. Source of Truth تازه نیز نباید پیام خام Provider را جایگزین کند؛ فقط reference حساب‌محور، claim ساختاریافته، provenance، تصمیم بازبینی و fact گزارش را نگه می‌دارد.

### مدل سطح در برابر فاز

معماری محصول چهار سطح پایدار دارد: `L1 semantic indexing`، `L2 WordPress projection`، `L3 reporting core` و `L4 controlled intelligence/orchestration`. فازهای `IR-0..IR-8` ترتیب تحلیل و ساخت این سطح‌ها هستند و جای آن‌ها را نمی‌گیرند. جزئیات ورودی، خروجی، مرز اختیار و دروازهٔ هر سطح در سند مدل چهارسطحی canonical است.

## ۲. تصمیم‌های پذیرفته‌شده برای شروع

1. تحلیل دامنه و ساخت مرجع صحت پیش از schema/API/UI تفصیلی انجام می‌شود.
2. مفاهیم `reporting program`، `metric`، `activity/event`، `evidence role`، `action`، `occasion`، `reporting unit`، `location`، `sender identity` و `document disposition` از هم جدا می‌مانند.
3. `not relevant` دستهٔ فعالیت نیست؛ تصمیم ارتباط/نقش سند پیش از نگاشت گزارش انجام می‌شود.
4. تاریخ ارسال، تاریخ‌های ذکرشده و تاریخ منتخب رویداد فیلدهای مستقل با provenance هستند.
5. نام canonical و alias یک مفهوم را یکسان می‌کنند؛ مفاهیم مرتبط، مانند یک مناسبت و رویدادهای وابسته، مترادف فرض نمی‌شوند.
6. External program code شناسهٔ داخلی نیست. کد، سال، نسخهٔ چارچوب، منبع و وضعیت تأیید metadata نسخه‌دار هستند.
7. LLM/API در فاز صفر و پیاده‌سازی پایه خاموش است. ورود بعدی آن فقط به‌عنوان پیشنهادگر موارد حل‌نشده، opt-in، بودجه‌دار، privacy-reviewed و human-confirmed بررسی می‌شود.
8. پاسخ مدل یا شباهت یک پیام خودکار به rule دائمی تبدیل نمی‌شود. exact cache، retrieval مشابه و حافظهٔ تصمیم تأییدشده سه قرارداد متفاوت‌اند.
9. auto-index scheduler فعلی safe-default خاموش می‌ماند؛ فعال‌سازی دوباره فقط پس از قرارداد مستقل lifecycle، cancellation، account isolation، backoff و observability مجاز است.
10. توسعه در یک worktree با یک Agent نویسنده انجام می‌شود. کار موازی فقط برای مسیرهای مستقل و ترجیحاً فقط‌خواندنی است؛ ادغام و ثبت canonical در همین workstream انجام می‌شود.
11. مقدار گزارش دارای نوع و provenance مستقل است: `observed`، `reported_by_unit`، `estimated`، `synthetic_placeholder` و `verified`. مقدار تخمینی/ساختگی بدون تأیید صریح کاربر نه training truth است و نه آمار تأییدشده.
12. grain داخلی و خروجی جداست: پیام/مدرک به رویداد و fact متصل می‌شود؛ ردیف اصلی workbook آمار تجمیعی کل استان برای برنامه/دوره است. breakdown شهرستان/رویداد برای audit و ضمیمه حفظ می‌شود.
13. metric یا ضمیمه می‌تواند در قواعد گزارش وجود داشته باشد حتی اگر workbook ستون مستقیم ندارد. زیارت عاشورا metric تجمیعی/ضمیمهٔ مستقل است و شمارش اصلی مراسم را افزایش نمی‌دهد.
14. workflow ستادمحور است: شهرستان‌ها فقط از Eitaa داده می‌فرستند و به سامانه دسترسی ندارند؛ کاربران مجاز ستادی در شبکهٔ خصوصی محلی تکمیل/review می‌کنند و تأیید/محاسبه/export نهایی همیشه انسانی است. Agent فقط پیشنهادگر است.
15. چهار سطح محصول عبارت‌اند از ایندکس معنایی، projection اختیاری WordPress، هستهٔ محلی گزارش و اتصال/یادگیری کنترل‌شده. همه بر evidence/fact/provenance/review مشترک‌اند و WordPress مرجع حقیقت گزارش نیست.
16. Codex مدیر معماری/یکپارچه‌سازی و writer canonical پیش‌فرض این workstream است. واگذاری فقط با Task Contract، مالکیت فایل، خروجی noncanonical، review و promotion انجام می‌شود؛ کار موازی write در worktree یا رجیستر مشترک ممنوع است.

## ۳. موارد عمداً تأییدنشده

- یکتا یا تکراری‌بودن کدهای برنامه در اسناد رسمی؛ تعارض مشاهده‌شده در workbook محلی ممکن است خطای تایپی باشد.
- فهرست نهایی برنامه‌ها، شاخص‌ها، استثناها و قواعد شمارش سال ۱۴۰۵ تا تطبیق با مستندات ابلاغی.
- schema نهایی پایگاه داده و محل ownership آن در مرز AppUser/MessengerAccount/Reporting Workspace.
- درصد پوشش محلی یا سقف فراخوانی API؛ هیچ هدف `90%/8%/2%` بدون corpus و اندازه‌گیری پذیرفته نیست.
- مدل ML/LLM، Provider، prompt، embedding، cache semantics یا budget نهایی.
- اینکه هر پیام دقیقاً یک برنامه دارد؛ workbook و نمونه‌های واقعی ممکن است primary/secondary metric یا چند report fact را لازم کنند.
- اینکه اشاره به یک مکان، واحد گزارش‌دهنده یا وابستگی سازمانی فرستنده را اثبات می‌کند.

این موارد باید در Phase 0 شاهد و تصمیم مستقل بگیرند و پیش از آن وارد schema یا code contract نشوند.

## ۴. سلسله‌مراتب منابع

در تعارض معنایی، ترتیب اولیهٔ اعتبار چنین است و در IR-0-A با کاربر نهایی می‌شود:

1. بخشنامه و برنامهٔ رسمی ابلاغی؛
2. پیوست‌ها و دستورالعمل‌های شمارش/مستندسازی؛
3. template رسمی همان دوره؛
4. نمونهٔ گزارش تکمیل‌شده و پذیرفته‌شده؛
5. رویهٔ عملی صریح کاربر؛
6. WordPress taxonomy و تاریخچهٔ تأییدشده؛
7. استنباط local engine یا LLM.

هر داده باید `source_reference`، `framework_version` و یکی از وضعیت‌های `verified`، `user_confirmed`، `inferred`، `unresolved` یا `conflicted` داشته باشد. تضاد با منبع قوی‌تر با حدس بسته نمی‌شود.

## ۵. Phase 0 — کشف دامنه و مرجع صحت

### IR-0-A — فهرست منابع و provenance

وضعیت جاری: `IN_PROGRESS / SRC-IR-001_REGISTERED / USER_CLARIFICATIONS_PENDING`  
مرجع‌ها: [Source/Conflict Register](INDEX_SOURCE_AND_CONFLICT_REGISTER.md)، [مرجع workbook ۱۴۰۵](INDEX_1405_WORKBOOK_REFERENCE.md) و [دفتر پرسش‌های دامنه](INDEX_DOMAIN_QUESTION_REGISTER.md).

خروجی:

- فهرست منابع موجود/مفقود، مالک، دوره، نسخه، درجهٔ اعتبار و محدودیت حریم خصوصی؛
- Conflict Register، از جمله تعارض کد مشاهده‌شده در workbook محلی؛
- تعیین اینکه کدام ورودی‌ها قابل commit، فقط محلی یا عملیاتی‌اند؛
- تعیین سلسله‌مراتب نهایی منابع با تأیید کاربر.

معیار خروج:

- هیچ سند رسمیِ موجود بدون provenance باقی نماند؛
- منبع مفقود و اثر آن صریح باشد؛
- فایل‌های عملیاتی یا خصوصی وارد Git/گزارش نشوند.

### IR-0-B — واژه‌نامه و مرز مفاهیم

خروجی:

- تعریف رسمی program، metric، event، action، occasion، evidence، unit، location، sender mapping، audience، document disposition، report fact و output mapping؛
- مثال مثبت/منفی و قواعد عدم‌ادغام مفاهیم؛
- مدل confidence داخلی، provenance و وضعیت review بدون نمایش probability گمراه‌کننده.

معیار خروج:

- هر فیلد پاسخ‌گوی یک سؤال روشن باشد؛
- مکان، واحد و هویت فرستنده مخلوط نشوند؛
- تاریخ ارسال و تاریخ رویداد مستقل باشند؛
- `not relevant` از taxonomy فعالیت جدا باشد.

### IR-0-C — نقشهٔ نسخه‌دار چارچوب گزارش

خروجی:

- نگاشت هر sheet/program به metricها، نوع مقدار، مدارک لازم، قواعد شمارش و استثنا؛
- تفکیک «وقوع فعالیت»، «اقدام پشتیبان»، «اطلاع‌رسانی» و «مستند»؛
- شناسهٔ داخلی پایدار و external code نسخه‌دار؛
- تشخیص دادهٔ قابل‌استخراج از Eitaa در برابر دادهٔ نیازمند WordPress/ورود دستی.

معیار خروج:

- افزایش شمارش اصلی فقط با شاهد واجد قاعده ممکن باشد؛
- استثناهایی مانند گزارش جداگانه بدون ورود به شمارش اصلی قابل‌مدل‌سازی باشند؛
- تغییر template بدون بازنویسی message evidence ممکن باشد.

### IR-0-D — corpus مرجع و دستور annotation

خروجی:

- نمونه‌های de-identified یا صریحاً مجاز از گزارش انجام‌شده، اعلان، خبر عمومی، پیام+گالری، گالری بی‌متن، تاریخ ناقص/متعارض، واحد صریح/استنباطی و چند پیام یک رویداد؛
- annotation schema در سطح field و event؛
- مجموعهٔ train/development/test بدون نشت near-duplicate؛
- ثبت پاسخ مرجع کاربر و موارد `unknown/needs-review`.

معیار خروج:

- ارزیابی از پیام‌های واقعی نماینده باشد؛
- متن خصوصی در گزارش مهندسی ثبت نشود؛
- دسترسی به دادهٔ عملیاتی فقط با مجوز صریح، read-only، masking و scope محدود باشد.

### IR-0-E — baseline و Gap Analysis سیستم جاری

خروجی:

- ثبت رفتارهای جاری: WordPress-driven labels، primary forcing، score غیرکالیبره، تاریخ مبتنی بر ارسال، sender context محدود، browser-local taxonomy و predictions-only store؛
- تعیین containmentهای کم‌خطر پیش از معماری جدید؛
- تفکیک قابلیت قابل‌حفظ از contract نیازمند supersede.

معیار خروج:

- هر ادعای نقص به source/test یا شاهد مشاهده‌شده متصل باشد؛
- هیچ migration یا تغییر رفتار در Phase 0 اجرا نشود؛
- برنامهٔ RED آینده پیش از patch تعریف شود.

### IR-0-F — feasibility و طرح ارزیابی

بدون API و بدون تغییر محصول، روش‌های زیر روی corpus کنترل‌شده مقایسه می‌شوند:

- normalization و فرهنگ canonical entity؛
- rules و parserهای تاریخ/امضا/هشتگ؛
- retrieval از مثال‌های تأییدشده؛
- classifier محلی موجود به‌عنوان baseline؛
- event/evidence bundling پیشنهادی با قواعد محافظه‌کارانه.

معیارها field-specific هستند: relevance، document role، unit، location، event date، occasion، action، program/metric mapping و event grouping. Precision، recall، coverage، abstention، خطای شمارش، CPU/RAM و زمان ثبت می‌شوند. score خام classifier احتمال محسوب نمی‌شود.

### IR-0-G — دروازهٔ پذیرش Phase 0

خروجی نهایی:

- Domain Discovery Report؛
- Source/Conflict Register؛
- glossary و conceptual model؛
- versioned report map؛
- corpus/annotation protocol و baseline results؛
- privacy/cost decision برای کمک اختیاری مدل؛
- Architecture Decision Memo و برنامهٔ RED-GREEN فاز ۱.

Phase 1 فقط پس از پذیرش صریح کاربر آغاز می‌شود. باقی‌ماندن منبع رسمی مفقود مجاز است، مشروط به اینکه اثر آن `BLOCKED/UNVERIFIED` ثبت و هیچ حدس قراردادی جایگزین آن نشود.

## ۶. نقشهٔ مراحل پس از Phase 0

| فاز | هدف | دروازهٔ خروج |
|---|---|---|
| IR-1 | مهار خروجی گمراه‌کنندهٔ index فعلی؛ حذف forced-primary، تفکیک زمان ارسال و event date، review-safe UI | RED/GREEN هدفمند، حفظ manual index و regression مرتبط |
| IR-2 | مدل دامنه و taxonomy نسخه‌دار سمت سرور با ownership چندکاربر/چندحساب | migration backup/recovery، authorization/isolation، audit/privacy |
| IR-3 | استخراج deterministic ادعاها با provenance و abstention | corpus field metrics و adversarial Persian/date/entity tests |
| IR-4 | Event/Evidence Workbench، صف بازبینی و اتصال محافظه‌کارانهٔ پیام/گالری | review/reversal/dedup/counting safety و mobile-first UI |
| IR-5 | Reporting rule engine و projection به WordPress/Excel | round-trip، versioned mapping، no double count و نمونهٔ گزارش پذیرفته‌شده |
| IR-6 | retrieval/learning محلی از تصمیم‌های تأییدشده | evaluation split، reproducible model/version، drift و rollback |
| IR-7 | کمک اختیاری LLM برای خوشه‌های حل‌نشده | opt-in، quota/budget، redaction، structured output validation و human confirmation |
| IR-8 | scheduler کنترل‌شده و پذیرش تجمیعی | feature/config، stop/join، account isolation، backoff، observability و full regression |

هر فاز به زیرمرحله‌های `RED → minimum patch → targeted GREEN → related regression → privacy/docs → user gate` تقسیم می‌شود. فاز بعدی بدون بسته‌شدن دروازهٔ قبلی آغاز نمی‌شود.

### نگاشت سطح‌ها به فازها

| سطح محصول | فازهای غالب |
|---|---|
| L1 — ایندکس معنایی | IR-0، IR-1، IR-2، IR-3 و IR-4 |
| L2 — WordPress projection | IR-2، IR-4 و IR-5 |
| L3 — هستهٔ گزارش | IR-0-C، IR-2، IR-4 و IR-5 |
| L4 — یادگیری/اتوماسیون | IR-6، IR-7 و IR-8 |

این نگاشت وابستگی را بیان می‌کند، نه اجازهٔ اجرای هم‌زمان. L4 پیش از مرجع صحت L1 و fact/review قابل‌اعتماد L3 آغاز نمی‌شود.

## ۷. مرز داده، امنیت و عملیات

- Token، Cookie، OTP، Session، شمارهٔ کامل، متن خصوصی پیام، raw payload، شناسهٔ واقعی غیرضروری و مسیر حساس وارد سند/لاگ/test fixture نمی‌شوند.
- Provider/message/WordPress operation، ورود واقعی، ارسال، انتشار، خواندن گستردهٔ دادهٔ عملیاتی و migration واقعی در Phase 0 مجاز نیستند.
- استفادهٔ cloud LLM به معنی خروج محتوای انتخابی از رایانه است و بدون تصمیم privacy، config صریح و تأیید کاربر فعال نمی‌شود.
- Evidence reference باید `provider + messenger_account_id + peer/message reference` و authorization server-side داشته باشد. Context ارسالی UI مجوز نیست.
- Reporting Workspace چندمنبعی نباید isolation حساب‌ها یا Provider abstraction را دور بزند.
- استقرار در LAN خصوصی جایگزین authentication، role-based authorization و audit نیست. واحد شهرستانی role سامانه ندارد و کاربران ستادی باید مجوز server-side داشته باشند.
- ورودی محلی مرجع، از جمله workbook کاربر، تا تصمیم بسته‌بندی/حریم خصوصی وارد Git نمی‌شود.

## ۸. آزمون و مستندسازی

- Phase 0 فقط اسناد، تحلیل read-only و artifactهای مصنوعی/de-identified دارد؛ اجرای full product suite بدون Trigger ممنوع است.
- هر Run در [INDEX_INTELLIGENCE_EXECUTION_LOG.md](INDEX_INTELLIGENCE_EXECUTION_LOG.md)، هر تصمیم/یافته در `FINDINGS_REGISTER.md` و هر شاهد در `VALIDATION_LEDGER.md` ثبت می‌شود.
- تغییر Markdown با memory integrity، refresh، stale و link check بسته می‌شود.
- تغییر source/schema/UI در فازهای بعد علاوه بر تست هدفمند، regression متناسب و در قرارداد مرکزی full Backend/UI/build را می‌خواهد.
- یافتهٔ Agent موازی تا ادغام توسط Agent نویسندهٔ اصلی canonical نیست.
- تمام واگذاری‌های این workstream تابع `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md` هستند. Agent مجری شناسهٔ canonical تازه تخصیص نمی‌دهد و خروجی او تا review/promotion در وضعیت noncanonical می‌ماند.

## ۹. وضعیت آغاز

- Phase 0 با دستور کاربر در 2026-08-27 مجاز شد.
- IR-0-A اولین زیرمرحله است.
- منبع محلی Excel مشاهده شده، اما code conflict آن تأیید رسمی نیست و خود فایل خارج از scope انتشار این نقشه‌راه است.
- پیاده‌سازی، schema v4، LLM integration، auto-index و تغییر WordPress در این checkpoint آغاز نشده‌اند.

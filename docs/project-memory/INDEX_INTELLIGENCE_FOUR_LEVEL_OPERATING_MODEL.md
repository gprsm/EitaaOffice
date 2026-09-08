# مدل عملیاتی چهارسطحی هوشمندسازی ایندکس و گزارش

وضعیت: `USER_ACCEPTED / CANONICAL_CONCEPTUAL_MODEL / PRODUCT_IMPLEMENTATION_NOT_STARTED`  
نسخه: `1.0`  
تاریخ پذیرش: 2026-08-28  
منبع تصمیم: `SRC-USER-IR-006`  
Finding: `F-065`  
ADR: `ADR-51`  
قرارداد واگذاری: [MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md](MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md)

## ۱. هدف سند

این سند مرجع پایدار تقسیم محصول به چهار سطح است تا هر سطح بتواند در یک Task/گفت‌وگوی مستقل تحلیل، طراحی، پیاده‌سازی و پذیرفته شود، بدون آنکه هدف کلی یا مرز داده‌ها از بین برود.

«سطح» در این سند بخش پایدار معماری محصول است. «فاز» در نقشه‌راه `IR-0..IR-8` ترتیب کشف، ساخت و آزمون همان سطح‌هاست. یک فاز ممکن است برای بیش از یک سطح خروجی تحلیلی بسازد، اما پیاده‌سازی باید وابستگی سطح‌ها را رعایت کند.

## ۲. دو بخش مفهومی و چهار سطح اجرایی

دو بخش مفهومی مورد تأیید کاربر چنین به چهار سطح شکسته می‌شوند:

| بخش مفهومی | سطح | پرسش اصلی | نتیجهٔ پایدار |
|---|---|---|---|
| فهم و سامان‌دهی محتوا | سطح ۱ — ایندکس معنایی | این پیام/مدرک دربارهٔ چیست و چه چیزی را اثبات می‌کند؟ | candidateهای ساختاریافته با provenance و امکان abstention/review |
| فهم و سامان‌دهی محتوا | سطح ۲ — projection و انتشار WordPress | کدام بخش از دادهٔ تأییدشده چگونه در WordPress نمایش یا منتشر شود؟ | نگاشت نسخه‌دار، draft قابل‌بازبینی و پیوند بازگشت به منبع |
| نظام گزارش | سطح ۳ — هستهٔ گزارش و دانش سازمانی | از رخدادها و داده‌های تکمیلی چه fact، metric و گزارش استانی ساخته شود؟ | مخزن محلی گزارش، پرسشنامه، قواعد تجمیع و خروجی نسخه‌دار |
| نظام گزارش | سطح ۴ — اتصال، یادگیری و اتوماسیون کنترل‌شده | چگونه حلقهٔ داده، بازبینی، گزارش و یادگیری با حداقل کار انسانی هماهنگ شود؟ | orchestration محلی، حافظهٔ تصمیم، کمک اختیاری Agent/API و نظارت کامل |

این چهار سطح چهار پایگاه حقیقت جدا نیستند. همه بر یک هستهٔ مشترک evidence/fact/provenance/review تکیه می‌کنند.

## ۳. نمای کلان جریان

```text
Eitaa / WordPress / Manual central-office input
                         ↓
Level 1 — evidence, claim, event and semantic index candidates
                         ↓ human review
Level 2 — optional WordPress draft/projection/publication mapping
                         ↓
Level 3 — verified facts, questionnaires, rules, metrics and reports
                         ↓
Level 4 — controlled orchestration, local learning and optional API help
                         ↺
              reviewed decisions return as governed memory
```

WordPress مسیر موازیِ بی‌ارتباط نیست؛ projection سطح ۲ و یک source قابل تطبیق برای سطح ۱/۳ است. مرجع حقیقت گزارش، هستهٔ ساختاریافتهٔ محلی سطح ۳ خواهد بود، نه taxonomy یا postهای WordPress.

## ۴. سطح ۱ — ایندکس معنایی و استخراج محافظه‌کارانه

### هدف

تبدیل پیام، آلبوم، فایل یا خبر خام به candidateهای ساختاریافته‌ای که انسان بتواند دلیل هر پیشنهاد را ببیند، اصلاح یا رد کند.

### ورودی‌ها

- پیام‌ها و رسانه‌های Eitaa با reference حساب‌محور؛
- metadata امن فرستنده، گفتگو و زمان؛
- taxonomy و تاریخچهٔ تأییدشدهٔ WordPress در صورت فعال‌بودن؛
- واژه‌نامه، aliasها، تقویم مناسبت‌ها و قواعد نسخه‌دار؛
- تصمیم‌های قبلیِ تأییدشده، فقط از حافظهٔ governed.

### وظایف

- normalization فارسی بدون نابودی متن منبع؛
- تعیین `relevant / informational / not_relevant / needs_review`؛
- تفکیک نقش سند: گزارش انجام‌شده، اعلان، خبر، مدرک، توضیح یا پیوست؛
- استخراج action، occasion، event date، send date، location، reporting unit و sender relation به‌صورت مستقل؛
- نگاشت محافظه‌کارانه به program/metricهای نسخه‌دار؛
- canonicalization صورت‌های واقعاً هم‌ارز، بدون یکی‌کردن مفاهیم صرفاً مرتبط؛
- اتصال پیشنهادی پیام/گالری به یک event، با حفظ شناسهٔ مستقل همهٔ evidenceها؛
- abstention در نبود شاهد کافی؛ forced-primary ممنوع است؛
- ارائهٔ explanation/provenance برای هر field candidate.

### خروجی مفهومی

- `SourceEvidence`؛
- `ContentBundleCandidate`؛
- `ClaimCandidate`؛
- `EventCandidate`؛
- `EntityReferenceCandidate`؛
- `SemanticIndexAssignment`؛
- `ReviewDecision`.

نام فنی جدول/API هنوز قطعی نیست. این‌ها مرز مفهومی‌اند، نه schema تصویب‌شده.

### خارج از دامنهٔ سطح ۱

- ساخت عدد گزارش بدون داده/قاعده؛
- انتشار خودکار WordPress؛
- محاسبهٔ تجمیعی استان؛
- تبدیل confidence خام به حقیقت؛
- فراخوانی پیش‌فرض LLM یا scheduler خودکار.

### دروازهٔ خروج

- glossary و report map پذیرفته شده باشد؛
- corpus مجاز و دستور annotation وجود داشته باشد؛
- معیارهای field-specific، coverage و abstention ثبت شوند؛
- هر پیشنهاد تا evidence و rule/model version قابل ردیابی باشد؛
- صف بازبینی و بازگشت‌پذیری تصمیم طراحی و آزموده شود.

## ۵. سطح ۲ — projection و انتشار کنترل‌شدهٔ WordPress

### هدف

تبدیل دادهٔ بازبینی‌شدهٔ سطح ۱ به نمایش یا draft WordPress، بدون آنکه WordPress مالک دانش دامنه یا مرجع حقیقت گزارش شود.

### وظایف

- نگاشت نسخه‌دار مفهوم‌های canonical به category/tag/custom fieldهای WordPress؛
- حفظ وحدت tag، مانند یک canonical واحد برای صورت‌های «شهرستان X»، «واحد X» و صورت کوتاه پذیرفته‌شده؛
- تشخیص اینکه کدام field در category، tag، متن، media یا metadata قرار گیرد؛
- تشکیل draft از یک یا چند evidence مرتبط با حفظ source links؛
- preview و تأیید انسانی پیش از publish واقعی؛
- idempotency، conflict detection و جلوگیری از پست تکراری؛
- ثبت round-trip reference میان post و event/evidence/fact؛
- واردکردن تغییرهای معتبر WordPress به‌عنوان source تازه، نه overwrite خام source fact.

### اصل جایگزین‌پذیری

خاموش‌کردن یا حذف WordPress نباید سطح ۱ یا ۳ را از کار بیندازد. adapter سطح ۲ باید اختیاری باشد و taxonomy WordPress شناسهٔ داخلی program/event/fact نباشد.

### خارج از دامنهٔ سطح ۲

- تصمیم نهایی دربارهٔ صحت گزارش؛
- نگه‌داری تنها نسخهٔ fact؛
- aggregation استانی؛
- انتشار بدون تأیید همان لحظه؛
- تفسیر category به‌عنوان گزارش انجام‌شده.

### دروازهٔ خروج

- mapping versioned و reversible باشد؛
- canonical tagها duplicate کنترل‌شده داشته باشند؛
- draft/publish مجوز و audit مستقل داشته باشد؛
- round-trip و rollback projection آزموده شود؛
- نبود WordPress رفتار هسته را خراب نکند.

## ۶. سطح ۳ — هستهٔ محلی گزارش و دانش سازمانی

### هدف

ساخت مرجع ساختاریافته‌ای که شواهد و رخدادهای تأییدشده را با اطلاعات تکمیلی ستاد به fact، metric و خروجی گزارش تبدیل کند.

### تصمیم معماری پایه

پیش‌فرض معماری، «هستهٔ گزارش محلی مستقل + adapter WordPress» است. توسعهٔ WordPress فقط وقتی مجاز است که با versioning، provenance، review، audit، چندمنبعی و aggregation این هسته سازگار باشد. WordPress به‌تنهایی System of Record گزارش نیست.

### وظایف

- پرسشنامهٔ نسخه‌دار با هستهٔ مشترک و module اختصاصی هر برنامه؛
- اتصال خبر، تعداد، هزینه، مدرک، دادهٔ پایه و توضیح به event/fact صحیح؛
- تفکیک `observed`، `reported_by_unit`، `estimated`، `synthetic_placeholder` و `verified`؛
- ثبت assumption، formula version، inputها و derived value؛
- جایگزینی estimate با مقدار دقیق هم‌دامنه بدون double count؛
- نگاشت event/fact به program/metric و framework version؛
- تجمیع ستاد و شهرستان‌ها در grain استانیِ دوره؛
- حفظ breakdown شهرستان/رخداد/مدرک برای audit و ضمیمه؛
- تولید Excel، ضمیمه، داشبورد و گزارش‌های آینده به‌صورت projection؛
- نگه‌داری قواعد استثنا، از جمله metric/annex مستقل زیارت عاشورا.

### کاربران

فقط کاربر اصلی و همکاران ستادی مجاز در شبکهٔ خصوصی محلی. شهرستان‌ها account/role ندارند و داده را از Eitaa می‌فرستند. تأیید fact، محاسبهٔ نهایی و export فقط انسانی است.

### دروازهٔ خروج

- schema و migration قابل‌بازگشت و account/user-scoped باشند؛
- پرسش‌ها به metric/evidence requirement نگاشت شده باشند؛
- قواعد شمارش و عدم شمارش مضاعف با نمونهٔ پذیرفته‌شده آزموده شوند؛
- تمام اعداد، formulaها و تغییر وضعیت‌ها audit و provenance داشته باشند؛
- projection Excel/گزارش از breakdown قابل بازتولید باشد.

## ۷. سطح ۴ — اتصال، یادگیری و اتوماسیون کنترل‌شده

### هدف

کاهش کار تکراری انسان پس از تثبیت سه سطح قبلی، بدون انتقال اختیار تأیید یا حقیقت‌سازی به Agent.

### ترتیب ابزارهای کمک

1. rule و parser deterministic محلی؛
2. exact match/cache فقط برای ورودی واقعاً همسان و rule version یکسان؛
3. retrieval از نمونه‌ها و تصمیم‌های تأییدشده؛
4. مدل/classifier محلی نسخه‌دار و قابل ارزیابی؛
5. API عامل هوشمند فقط برای موارد حل‌نشده، با opt-in، redaction، budget و structured output؛
6. بازبینی انسانی پیش از تبدیل پیشنهاد به fact/rule/training truth.

### وظایف

- پیشنهاد تکمیل شکاف پرسشنامه و اتصال evidenceها؛
- پیشنهاد دسته/واحد/مناسبت/تاریخ با explanation؛
- تشخیص drift، تعارض و نیاز به بازبینی؛
- حافظهٔ تصمیم‌های تأییدشده با version و scope؛
- جلوگیری از فراخوانی تکراری API فقط در صورت equivalence اثبات‌شده، نه شباهت سطحی؛
- scheduler دارای stop/join/cancellation، backoff، account isolation و observability؛
- هزینه، latency، coverage، خطا، abstention و نرخ اصلاح انسانی؛
- rollback مدل/rule و عدم‌اثرگذاری خودکار مدل تازه بر گزارش‌های تاریخی.

### مرز اختیار

Agent می‌تواند استخراج، پیشنهاد، مقایسه، تست و draft بسازد. Agent نمی‌تواند fact را نهایی، آمار را verified، گزارش را approved، WordPress را واقعاً publish یا خروجی رسمی را صادر کند مگر آن عمل جداگانه و در همان لحظه توسط کاربر مجاز تأیید شود.

### دروازهٔ خروج

- baseline deterministic و corpus مستقل موجود باشد؛
- سود مدل نسبت به baseline با معیار ثبت‌شده اثبات شود؛
- privacy/cost/retention و schema-bound output پذیرفته شود؛
- تمام پیشنهادها provenance و model/rule version داشته باشند؛
- human override و rollback آزموده شود؛
- scheduler و عملیات بیرونی با observability و دروازهٔ کاربر بسته شوند.

## ۸. هستهٔ مفهومی مشترک

| مفهوم | معنای پایدار |
|---|---|
| Source | منبع دارای مالک، نسخه، دوره، سطح اعتبار و محدودیت حریم خصوصی |
| Evidence | پیام، رسانه، سند یا post که چیزی را ادعا/پشتیبانی می‌کند و حذف معنایی نمی‌شود |
| Claim | گزارهٔ استخراج‌شده که هنوز ممکن است تأییدنشده یا متعارض باشد |
| Event | رخداد/فعالیتی که چند evidence و claim می‌توانند به آن متصل شوند |
| Entity | واحد، مکان، شخص/فرستنده، مناسبت، action، audience یا مفهوم canonical |
| Program | عنوان برنامهٔ گزارش در یک framework version؛ external code شناسهٔ داخلی نیست |
| Metric | کمیت/وضعیتی که با rule مشخص از factها ساخته می‌شود |
| Fact | دادهٔ پذیرفته‌شده با value kind، provenance و review state |
| Rule | قاعدهٔ نسخه‌دار استخراج، eligibility، شمارش، aggregation یا projection |
| Review | تصمیم انسانی ثبت‌شده، قابل برگشت و منتسب به actor مجاز |
| Projection | نمایش مشتق‌شده در WordPress، Excel، ضمیمه یا گزارش؛ قابل بازسازی از هسته |

## ۹. قواعد تغییرناپذیر میان سطح‌ها

1. متن و metadata منبع با دادهٔ مشتق‌شده جایگزین نمی‌شود.
2. هر field پیشنهادی provenance و status مستقل دارد.
3. تاریخ ارسال، تاریخ ذکرشده و event date یکی نیستند.
4. sender identity، وابستگی سازمانی فرستنده، reporting unit و location یکی نیستند.
5. alias فقط هم‌ارزی را canonical می‌کند؛ ارتباط تقویمی/موضوعی rule جداست.
6. `not_relevant` disposition است، نه activity category.
7. یک event می‌تواند چند evidence و چند metric داشته باشد؛ یک evidence نیز ممکن است چند claim بسازد.
8. grain داخلی event/evidence است و grain خروجی اصلی workbook تجمیع استان/دوره/program است.
9. estimate یا synthetic بدون تأیید صریح verified یا training truth نمی‌شود.
10. WordPress و Excel projection هستند و تغییر آن‌ها source evidence/fact را نابود نمی‌کند.
11. local-first اصل پایه است و خروج داده به API خارجی opt-in است.
12. Agent پیشنهادگر است؛ انسان ستادی مجاز approver نهایی است.

## ۱۰. ترتیب آغاز Taskهای مستقل

| اولویت | Task پیشنهادی | سطح | وابستگی |
|---|---|---|---|
| ۱ | تکمیل Q-IR-001..003 و Q-IR-006..012 | مشترک/فاز صفر | پاسخ کاربر و ستاد |
| ۲ | glossary و قرارداد خروجی سطح ۱ | سطح ۱ | IR-0-A |
| ۳ | report map و taxonomy/version rules | سطح ۱ و ۳ | glossary |
| ۴ | corpus/annotation و baseline ایندکس جاری | سطح ۱ | منابع مجاز |
| ۵ | قرارداد WordPress projection | سطح ۲ | خروجی سطح ۱ |
| ۶ | مدل پرسشنامه و reporting core | سطح ۳ | report map |
| ۷ | adapterها و اتصال سطح‌ها | سطح ۲ و ۳ | هسته‌های پذیرفته‌شده |
| ۸ | retrieval/learning/API/scheduler | سطح ۴ | پذیرش سطح‌های ۱ تا ۳ |

شروع سطح ۴ پیش از ساخت مرجع صحت سطح ۱ و هستهٔ fact/review سطح ۳ مجاز نیست.

## ۱۱. معیار پایان کل برنامه

- کاربر بتواند مجموعه‌ای مانند «فضاسازی‌های هفته وحدت در همهٔ واحدها و یک دوره» را با unit/date/occasion/action صحیح بازیابی کند؛
- بتوان evidenceهای هم‌راستا را بدون از دست‌دادن منشأ، برای WordPress یا گزارش گروه‌بندی کرد؛
- هر عدد استانی تا event/fact/evidence/rule قابل drill-down باشد؛
- تغییر قالب گزارش با framework version و projection تازه انجام شود، نه بازنویسی تاریخچه؛
- سیستم در نبود شاهد کافی abstain کند و review بخواهد؛
- کار تکراری انسان کاهش یابد، اما اختیار تأیید و خروجی رسمی انسانی بماند.

## ۱۲. وضعیت فعلی

این سند معماری مفهومی و ترتیب توسعه را تثبیت می‌کند. schema، API، UI، migration، classifier، LLM integration، scheduler، WordPress mapping و reporting engine با این ثبت ساخته یا فعال نشده‌اند. اقدام جاری همچنان تکمیل Phase 0 و پرسش‌های باز دامنه است.

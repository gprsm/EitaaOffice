# قرارداد مدیریت توسعه و واگذاری کار میان Agentها

وضعیت: `ACTIVE / IR-GOV-01 / POLICY_V1 / ENFORCEMENT_BY_PROCESS`  
نسخه: `1.0`  
تاریخ پذیرش: 2026-08-28  
دامنه: هوشمندسازی ایندکس، WordPress projection، هستهٔ گزارش و اتوماسیون مرتبط  
مرجع معماری: [INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md](INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md)

## ۱. هدف

این قرارداد اجازه می‌دهد کار در Taskهای مستقل و با Agentهای متفاوت انجام شود، بدون تداخل در worktree، شناسه‌های canonical، قراردادهای معماری یا داده‌های عملیاتی. نام ابزار تعیین‌کنندهٔ اختیار نیست؛ scope، ریسک، شاهد، قرارداد تحویل و review تعیین‌کننده‌اند.

## ۲. نقش‌ها و اختیارها

### ۲.۱. مالک محصول و دامنه — کاربر

- هدف سازمانی، اولویت، قواعد مبهم گزارش و پذیرش نهایی را تعیین می‌کند.
- تنها مرجع مجاز تأیید نهایی fact، آمار استانی، export رسمی و عملیات بیرونیِ نیازمند اجازه است.
- می‌تواند Agent یا ابزار پیشنهادی را تغییر دهد؛ قرارداد و شواهد همچنان لازم‌اند.

### ۲.۲. مدیر معماری و یکپارچه‌سازی — Codex

- خط‌مشی، مدل دامنه، مرز سطح‌ها، ADRها و قراردادهای مرکزی را تدوین و نگهداری می‌کند.
- backlog را به Taskهای bounded تبدیل و سطح ریسک/مالکیت فایل/معیار پذیرش را تعیین می‌کند.
- تنها allocator و promoter پیش‌فرض اسناد canonical ایندکس است.
- خروجی Agentهای دیگر را review، بازآزمایی و در صورت پذیرش به مرجع پروژه promote می‌کند.
- مسئول جلوگیری از واگرایی معماری، bypass چندکاربری/چندحسابی/Provider و اختلاط WordPress با Source of Truth است.
- اختیار Codex بالاتر از تصمیم صریح کاربر نیست و Codex approver گزارش سازمانی محسوب نمی‌شود.

### ۲.۳. Agent مجری محدود

- فقط Task Contract مکتوب و فایل‌های مجاز را اجرا می‌کند.
- حق گسترش scope، تغییر ADR، ساخت schema مرکزی، تغییر عملیات Live یا promotion خروجی خود به canonical را ندارد مگر قرارداد صریحاً اجازه دهد.
- باید فرض‌ها، فایل‌ها، تست‌ها، شکست‌ها و محدودیت‌های نتیجه را در handoff ثبت کند.

### ۲.۴. Agent پژوهش/بازبین

- به‌صورت read-only تحقیق، مقایسه، test design یا review انجام می‌دهد.
- خروجی آن evidence پیشنهادی است، نه تصمیم یا acceptance.
- در صورت نیاز به تغییر فایل، باید Task تازه با writer ownership صادر شود.

## ۳. طبقه‌بندی کار برای واگذاری

| کلاس | نمونه | مالک پیش‌فرض | واگذاری |
|---|---|---|---|
| A — دامنه/معماری/امنیت | taxonomy، schema، ADR، privacy، authority، report rule | Codex + پذیرش کاربر | تحلیل کمکی مجاز؛ تصمیم و promotion قابل واگذاری نیست |
| B — قرارداد مرکزی/پرریسک | migration، authorization، aggregation، Provider/WordPress mutation، scheduler | Codex یا Agent ارشد با review مستقیم Codex | فقط worktree ایزوله، RED/GREEN و full regression متناسب |
| C — ماژول محدود | parser مستقل، adapter pure، UI محصور، test harness | Agent مناسب | با فایل‌های مجاز، interface ثابت و تست هدفمند قابل واگذاری است |
| D — مکانیکی/کم‌ریسک | fixture مصنوعی، تبدیل فرمت، lint، inventory، مستند draft | Agent سبک‌تر | در صورت خروجی deterministic و review آسان قابل واگذاری است |

انتخاب Claude، Gemini، AntiGravity یا هر Agent دیگر فقط نمونهٔ تخصیص بر پایهٔ توان/هزینه است و در معماری hard-code نمی‌شود.

## ۴. قاعدهٔ یک نویسنده و مالکیت فایل

1. در هر زمان فقط یک writer برای هر فایل یا مجموعهٔ canonical وجود دارد.
2. فایل‌های زیر به‌طور پیش‌فرض فقط توسط مدیر معماری/یکپارچه‌سازی تغییر می‌کنند:
   - `AGENTS.md`؛
   - `ARCHITECTURE_DECISIONS.md`؛
   - `docs/project-memory/README.md`؛
   - `CURRENT_SYSTEM_BASELINE.md`؛
   - `FINDINGS_REGISTER.md`؛
   - `VALIDATION_LEDGER.md`؛
   - roadmap، source/conflict register، domain questions و handoff جاری.
3. F/V/ADR/Source/Question ID فقط توسط allocator همان Run رزرو می‌شود. Agent مجری در artifact خود شناسهٔ موقت task-scoped می‌نویسد، نه شناسهٔ canonical تازه.
4. دو Agent نویسنده در یک worktree مشترک ممنوع‌اند، حتی اگر ماژول‌های محصول متفاوت باشند؛ generated docs و registerها نقاط برخورد پنهان‌اند.
5. کار موازی فقط در یکی از این شکل‌ها مجاز است:
   - read-only؛
   - worktree/branch ایزوله با مالکیت فایل غیرهم‌پوشان؛
   - artifact خارج از canonical که بعداً توسط مدیر promote می‌شود.
6. reset، checkout، clean، overwrite یا حذف کار writer دیگر ممنوع است.

## ۵. Task Contract اجباری

پیش از واگذاری، مدیر باید قرارداد زیر را تکمیل کند:

```text
Task ID:
Level / Phase:
Goal:
Why now:
In scope:
Out of scope:
Allowed files/directories:
Forbidden/canonical files:
Source-of-truth references:
Assumptions allowed:
Questions that must remain unresolved:
Required RED evidence:
Acceptance criteria:
Required tests/checks:
Privacy and operational boundary:
External actions allowed/forbidden:
Expected deliverables:
Handoff format:
Stop conditions:
```

قرارداد باید آن‌قدر محدود باشد که Agent نتواند از عبارت کلی «هوشمندسازی ایندکس» مجوز تغییر schema، WordPress، scheduler یا دادهٔ عملیاتی استنتاج کند.

## ۶. چرخهٔ واگذاری و ارتقا

```text
Canonical brief by Codex
        ↓
isolated analysis or implementation by assigned Agent
        ↓
agent handoff + diff/artifact + tests + known limits
        ↓
Codex review against architecture and task contract
        ↓
targeted revalidation / privacy / regression
        ↓
canonical promotion by sole writer
        ↓
user gate when domain, Live, publish or official report is involved
```

وضعیت خروجی‌ها:

- `DRAFT`: فقط پیشنهاد؛
- `AGENT_COMPLETED_UNREVIEWED`: Agent کار خود را تمام دانسته، اما canonical نیست؛
- `CODEX_REVIEWED`: با قرارداد تطبیق داده شده، ولی شاید acceptance کامل ندارد؛
- `VALIDATED`: تست و کنترل متناسب سبز است؛
- `CANONICAL_PROMOTED`: مدیر در حافظهٔ پروژه ثبت کرده است؛
- `USER_ACCEPTED`: دروازه‌ای که نیازمند تصمیم کاربر بوده بسته شده است.

checkbox، عبارت «done» یا گزارش خود Agent هیچ‌کدام به‌تنهایی `VALIDATED/CANONICAL_PROMOTED` نیستند.

## ۷. قرارداد تحویل Agent مجری

هر handoff باید حداقل شامل موارد زیر باشد:

- Task ID و commit/base یا snapshot آغاز؛
- فایل‌های خوانده‌شده و تغییرکرده؛
- خلاصهٔ مسئله و root cause؛
- فرض‌ها و موارد unresolved؛
- RED، patch، GREEN و regression با شمار دقیق؛
- اثر امنیتی، حریم خصوصی و عملیات بیرونی؛
- فایل‌های خارج از scope که عمداً تغییر نکردند؛
- diff یا artifact قابل بازبینی؛
- دستور دقیق ادامه/بازآزمایی؛
- اعلام صریح اینکه خروجی هنوز canonical نیست.

## ۸. دروازه‌های review برحسب نوع تغییر

### اسناد و تحلیل دامنه

- تطبیق با source hierarchy؛
- جداسازی fact/assumption/proposal؛
- Finding/ADR/Question/Source linkage؛
- UTF-8، ID uniqueness، freshness و link check.

### کد محدود

- RED پیش از patch؛
- targeted GREEN؛
- regression ماژول مجاور؛
- نبود تغییر خارج از allowed files؛
- observability و privacy متناسب.

### قرارداد مرکزی یا schema

- migration/rollback/backup rehearsal؛
- authorization و account isolation؛
- adversarial tests؛
- full Backend/UI/build/docs در checkpoint نهایی؛
- گزارش مستقل و پذیرش Codex؛
- پذیرش کاربر اگر رفتار/دامنه تغییر می‌کند.

### عملیات بیرونی

Login/OTP، Send، WordPress publish، Provider mutation، Firewall/Proxy، bind واقعی، نصب واقعی و export رسمی فقط با تأیید همان لحظهٔ کاربر انجام می‌شوند؛ Task Contract قدیمی مجوز دائمی این عملیات نیست.

## ۹. سیاست حافظه و promotion

- گفت‌وگوی Agent حافظهٔ پروژه نیست.
- artifact بیرونی با source hash/task ID ثبت و تا زمان review با وضعیت noncanonical نگه داشته می‌شود.
- Agent مجری حق ویرایش مستقیم Finding/Validation/ADR مشترک را ندارد، مگر آنکه در همان Run رسماً sole writer باشد.
- مدیر پس از review، نتیجه را با شناسهٔ تازه یا correction/supersession ثبت می‌کند؛ متن تاریخی معتبر حذف نمی‌شود.
- اگر Agent به تعارض یا یافتهٔ تازه رسید، آن را در handoff با شناسهٔ موقت مانند `TASK-X-F01` می‌آورد.

## ۱۰. مدیریت چند Task/گفت‌وگو

- هر Task باید فقط یک Goal اصلی و یک Level/Phase غالب داشته باشد.
- Task معماری، Task implementation و Task review بهتر است از هم جدا باشند، اما promotion نهایی در workstream مدیر انجام می‌شود.
- Taskهای read-only می‌توانند موازی باشند. Taskهای write فقط با worktree ایزوله، file ownership غیرهم‌پوشان و merge queue اجرا می‌شوند.
- کاربر می‌تواند Taskهای تازه بسازد، ولی brief آن‌ها باید از Task Contract canonical کپی شود تا Agent جدید از Chat قدیمی حدس نزند.
- اگر دو Task به یک فایل canonical نیاز دارند، یکی متوقف یا به draft artifact تبدیل می‌شود؛ هم‌زمان‌نویسی مجاز نیست.

## ۱۱. معیار انتخاب Agent

Agent بر اساس این موارد انتخاب می‌شود:

- توان تحلیل دامنه و معماری؛
- توان پیاده‌سازی زبان/ماژول موردنظر؛
- قابلیت اجرای تست و نگه‌داری context؛
- هزینه و سرعت؛
- سهولت ارزیابی deterministic خروجی؛
- ریسک دسترسی به داده/شبکه/فایل‌های مشترک.

کار ساده و قابل سنجش می‌تواند به Agent سبک‌تر سپرده شود. کار معماری، schema، امنیت، migration، گزارش رسمی و ادغام چند ماژول باید زیر review مستقیم Codex بماند.

## ۱۲. شرایط توقف Agent

Agent باید بدون حدس‌زدن متوقف و handoff بدهد اگر:

- منبع رسمی یا تصمیم دامنه مفقود است؛
- لازم است از allowed files خارج شود؛
- worktree شامل تغییر هم‌پوشان ناشناخته است؛
- تست RED به علت متفاوتی از قرارداد شکست خورده است؛
- نیاز به دادهٔ عملیاتی، credential یا عملیات Live دارد؛
- معماری موجود با Task Contract تعارض دارد؛
- acceptance criteria قابل سنجش نیست.

## ۱۳. الگوی آغاز Task جدید

```text
این Task بخشی از مدل چهارسطحی هوشمندسازی ایندکس و گزارش است.
پیش از هر اقدام AGENTS.md، project-memory/README.md،
INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md و
MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md را بخوان.

Task Contract: <پیوند/متن قرارداد>
وضعیت خروجی مورد انتظار: AGENT_COMPLETED_UNREVIEWED
حق تغییر اسناد canonical یا گسترش scope وجود ندارد.
هر تعارض، RED یا نیاز به عملیات بیرونی را متوقف و در handoff ثبت کن.
```

## ۱۴. وضعیت اجرایی قرارداد

این نسخه، سیاست و قالب لازم را ایجاد می‌کند؛ allocator خودکار، قفل فایل، merge queue ماشینی، ابزار رزرو ID یا enforcement CI هنوز پیاده نشده‌اند. تا آن زمان اجرای قرارداد انسانی/فرایندی است و مدیر معماری sole writer اسناد canonical باقی می‌ماند.

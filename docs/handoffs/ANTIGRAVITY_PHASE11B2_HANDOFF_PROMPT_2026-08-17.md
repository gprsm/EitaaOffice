# پرامپت تحویل Phase 11-B2 به Antigravity

تاریخ تهیه: 2026-08-17  
نوع سند: handoff اجرایی و قابل کپی  
وضعیت مبدأ: `Phase 11-B1 IMPLEMENTED / FAKE_VERIFIED`  
هدف بعدی: `Phase 11-B2 Provider-neutral Application Orchestration`

## ۱. متن آمادهٔ تحویل به Antigravity

متن زیر را بدون حذف قواعد ایمنی و معیارهای پذیرش به ایجنت بده:

---

بسم الله الرحمن الرحیم

تو مسئول ادامهٔ کنترل‌شدهٔ پروژهٔ **Eitaa Bridge** از وضعیت واقعی موجود هستی. پروژه را از صفر نساز و هیچ فرضی را جایگزین اسناد canonical نکن.

### مسیر پروژه

```text
C:\Users\Mohsen\Documents\eitaa\Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send
```

### مأموریت دقیق

مرحلهٔ بعدی پروژه، **Phase 11-B2 — Provider-neutral Application Orchestration** است. هدف این مرحله آن است که عملیات عمومی Dialog، History، Send، Media و Contacts از handlerها و runtimeهای خاص ایتا جدا شوند و از service/portهای عمومی Provider عبور کنند؛ به‌گونه‌ای که Provider آینده فقط Manifest، Adapter/transport مجاز، capability و mapping اختصاصی خود را اضافه کند و Core، مالکیت AppUser، Account isolation، UI shell و Security boundary بازنویسی نشوند.

این مأموریت **به معنی ساخت اتصال بله نیست**. Bale Personal تا وجود API رسمی یا اجازهٔ کتبی همچنان `BLOCKED` و غیرفعال است. از ZIPها، APIهای غیررسمی، مهندسی معکوس، endpoint حدسی یا کد ناقض شرایط سرویس استفاده نکن. Bale Bot/Arm نیز account kind جداست و بدون تصمیم صریح محصول آغاز نمی‌شود.

### ترتیب مطالعهٔ اجباری

قبل از بررسی کد یا اجرای آزمون، این فایل‌ها را کامل و به همین ترتیب بخوان:

1. `AGENTS.md`
2. `docs/project-memory/README.md`
3. `docs/project-memory/CURRENT_SYSTEM_BASELINE.md`
4. `docs/project-memory/FINDINGS_REGISTER.md`
5. `docs/project-memory/VALIDATION_LEDGER.md`
6. `ARCHITECTURE_DECISIONS.md`
7. `docs/PROJECT_SPECIFICATION.md`
8. `docs/PROJECT_STRUCTURE.md`
9. `docs/project-memory/ENGINEERING_DOCUMENTATION_PROTOCOL.md`
10. `docs/project-memory/MULTI_ACCOUNT_PROVIDER_ROADMAP.md`
11. `docs/PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md`
12. `docs/reports/phases/PHASE11B1_MULTI_PROVIDER_CORE_REPORT_2026-08-13.md`
13. همین handoff: `docs/handoffs/ANTIGRAVITY_PHASE11B2_HANDOFF_PROMPT_2026-08-17.md`

پس از مطالعه، ابتدا یک گزارش کوتاه از وضعیت کشف‌شده، فایل‌های واقعاً مرتبط و مرز دقیق تغییر بده. ممیزی کامل پروژه یا اجرای Live را بی‌دلیل تکرار نکن. برای هر بررسی تازه، Trigger آن را در Validation Ledger ثبت کن.

### وضعیت معتبر فعلی

- Phase 10 کامل و `LIVE_ACCEPTED` است.
- Phase 11-0 زیرساخت افزودن چند حساب ایتا و تعویض حساب را با Fake/Contract/Adversarial پذیرفته است؛ Pilot واقعی حساب دوم هنوز انجام نشده است.
- Phase 11-A وضعیت Bale Personal را به علت نبود API رسمی/مجوز و منع API غیررسمی `BLOCKED` ثبت کرده است.
- Phase 11-B0 Provider Extension API v1، allowlist Registry، Manifest، DTOهای bounded، Worker factory، Fake harness و slot غیرفعال بله را ساخته است.
- Phase 11-B1 Registry پایدار، Coordinator schema v6، Contact schema v3، Audit عمومی، Capability service حساب‌محور، route guards و Fake Provider سوم را تکمیل کرده است.
- آخرین شواهد B1: Backend `540/540`، UI assertions `61/61`، TypeScript/observability/build موفق و PII scan روی `9106` رکورد با finding=`0`.
- Fake Provider سوم test-only، آفلاین و خارج از catalog محصول است.
- بعضی handlerهای v1 و `EitaaRuntimeRegistry` هنوز Eitaa-specific هستند؛ این بدهی دقیقاً مرز B2 است.
- پایگاه عملیاتی و سرویس واقعی در B1 migrate/restart نشدند. شواهد migration فقط متعلق به DBهای موقت آزمون است.

### معماری لازم‌الاجرا

مدل مالکیت:

```text
AppUser -> Membership/Authorization -> PhoneAccount -> MessengerAccount -> Provider Runtime
```

قواعد اصلی:

- هر MessengerAccount مالک Session، Worker، DB/Cache/Media، Job/Lease، rate/circuit، Log و Audit مستقل است.
- Membership باید پیش از افشای capability یا انتخاب runtime کنترل شود.
- Context حساب، Provider و مسیرهای storage فقط سمت سرور ساخته می‌شوند.
- لایهٔ application نباید بر اساس نام `eitaa`، `bale` یا Provider آینده branch عمومی داشته باشد.
- Provider-specific translation/transport فقط در package همان Provider مجاز است.
- Manifest سقف Capability است و observation حق افزایش capability را ندارد.
- DTO عمومی نباید raw SDK object، raw RPC/response، Cookie، Token، Session object، Access Hash، OTP، رمز، شمارهٔ کامل، متن خصوصی یا مسیر حساس داشته باشد.
- Correlation، deadline، idempotency و taxonomy امن خطا باید در مرز application-to-provider حفظ شوند.
- ارسال با وضعیت `uncertain` هرگز خودکار تکرار نمی‌شود.

### دامنهٔ پیاده‌سازی B2

1. handlerها و serviceهای فعلی Dialog، History، Send، Media و Contacts را فقط در دامنهٔ مرتبط بررسی و dependencyهای Eitaa-specific را فهرست کن.
2. یک application orchestration عمومی و تست‌پذیر تعریف کن که ورودی آن Context معتبر حساب، operation، capability لازم، correlation/deadline و DTO محدود باشد.
3. ترتیب اجباری اجرای هر عملیات را حفظ کن:

```text
AppUser authentication
-> active Membership/account scope
-> capability decision
-> account-scoped runtime/adapter resolution
-> bounded provider operation
-> safe result/error mapping
-> structured event/audit where required
```

4. مسیرهای عمومی را مرحله‌ای به orchestrator منتقل کن. رفتار موجود Eitaa باید با compatibility adapter/port حفظ شود؛ کد Provider-specific تازه را داخل application یا API پخش نکن.
5. Fake Provider سوم باید بدون شبکه از **همان orchestrator عمومی** برای عملیات اعلام‌شدهٔ خود عبور کند؛ مسیر مخصوص تست که production orchestration را دور بزند نپذیر.
6. برای Media و Contacts ابتدا DTO/semantics موجود Eitaa را به contract محدود و عمومی تبدیل کن. قابلیت یا رفتار Provider دیگر را حدس نزن. اگر یک عملیات واقعاً اختصاصی ایتاست، route آن را صریح و Eitaa-specific نام‌گذاری و دلیلش را مستند کن.
7. UI باید وضعیت supported/restricted/unsupported را از endpoint حساب‌محور capability بخواند و عملیات unsupported را پیش از درخواست غیرفعال کند؛ نام Provider نباید معیار عمومی فعال‌سازی باشد.
8. رخدادهای تازه را قبل از استفاده به Event Catalog اضافه کن و redaction/coverage test بنویس. exception خام Provider در log/audit ممنوع است.
9. migration روی DB عملیاتی، restart سرویس واقعی و تغییر config بخشی از B2 نیست. اگر تغییر schema واقعاً اجتناب‌ناپذیر شد، فقط migration و تست روی DB موقت را بساز و اعمال عملیاتی را به rollout جدا موکول کن.

اگر کل B2 برای یک تحویل اتمیک بیش از حد بزرگ بود، آن را به vertical sliceهای کامل تقسیم کن؛ هیچ مسیر نیمه‌مهاجرت‌شده تحویل نده. نخستین slice باید دست‌کم Dialog + History + Text Send را با Eitaa compatibility و Fake سوم از یک orchestrator مشترک عبور دهد، و قرارداد Media/Contacts را بدون فعال‌سازی حدسی تثبیت کند. باقی‌مانده را با معیار ورود و blocker دقیق ثبت کن.

### تست‌های اجباری

حداقل یک suite مستقل برای B2 ایجاد کن، ترجیحاً:

```text
tests/test_phase11b2_provider_neutral_orchestration.py
```

این موارد باید پوشش داده شوند:

- Eitaa compatibility با stub/Fake و بدون شبکه یا حساب واقعی؛
- Fake Provider سوم از همان application orchestrator؛
- رد عملیات unsupported پیش از ساخت/فراخوانی adapter؛
- عدم capability escalation از observation یا payload جعلی؛
- دو AppUser، چند MessengerAccount از یک Provider و چند Provider، بدون cross-account read/write/session leakage؛
- runtime resolution فقط از account scope سمت سرور؛
- correlation و deadline معتبر/منقضی؛
- idempotency و duplicate/race برای mutation؛
- `uncertain send` بدون retry خودکار؛
- malformed/oversized result و exception خام Provider با نگاشت fail-closed و امن؛
- نبود branch نام Provider در orchestration عمومی؛
- نبود Secret/PII در log، audit، fixture، report و support data؛
- سازگاری route/API و UI capability behavior.

پس از targeted tests، کنترل‌های canonical `AGENTS.md` را متناسب با تغییر و در نهایت مجموعهٔ کامل اجرا کن:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
```

اگر UI یا build graph تغییر کرد، contractهای UI مرتبط و production build را نیز اجرا کن. هر failure، timeout، invocation نامعتبر و نتیجهٔ نهایی را در `docs/project-memory/VALIDATION_LEDGER.md` ثبت کن؛ failure اولیه را پنهان نکن و آن را با نتیجهٔ نهایی اشتباه نگیر.

### مستندسازی اجباری

هیچ یافته‌ای نباید فقط در گفت‌وگو باقی بماند. در پایان:

- `docs/project-memory/CURRENT_SYSTEM_BASELINE.md` را فقط اگر رفتار واقعی تغییر کرد به‌روز کن؛
- `docs/project-memory/FINDINGS_REGISTER.md` را به‌روز کن؛
- `docs/project-memory/VALIDATION_LEDGER.md` را با شناسه‌های تازه به‌روز کن؛
- `docs/project-memory/MULTI_ACCOUNT_PROVIDER_ROADMAP.md` را به‌روز کن؛
- `ARCHITECTURE_DECISIONS.md` را فقط در صورت تصمیم معماری تازه به‌روز کن؛
- راهنمای Provider و مشخصات/ساختار پروژه را در صورت تغییر قرارداد هماهنگ کن؛
- گزارش مستقل زیر را بنویس:

```text
docs/reports/phases/PHASE11B2_PROVIDER_NEUTRAL_APPLICATION_ORCHESTRATION_REPORT_2026-08-17.md
```

- پس از تغییر فایل/نماد، `scripts/refresh_project_docs.py` را اجرا کن؛ فایل‌های generated را دستی ویرایش نکن.

گزارش نهایی باید دقیقاً سطح شاهد (`STATIC`، `UNIT`، `CONTRACT/FAKE`، `ADVERSARIAL`، `ISOLATED RUNTIME` یا `LIVE`)، فایل‌های تغییرکرده، شمار آزمون‌ها، failureهای میانی، اثر بیرونی و محدودیت باقی‌مانده را اعلام کند. ادعای Live نکن مگر آزمون واقعی با تأیید لحظه‌ای کاربر انجام شده باشد.

### ممنوعیت‌ها و مرزهای توقف

- worktree عمداً dirty است؛ `reset`، `checkout`، `clean`، `stage`، `commit` و `push` نکن.
- `bridge.json`، `.env`، Session واقعی، `data/`، `runtime/`، `diagnostics/`، `catalog/` و `backups/` را جابه‌جا، بازنویسی یا حذف نکن.
- هیچ Provider network، Login، OTP، Credential، Send واقعی، WordPress publish یا حساب واقعی تازه استفاده نکن.
- هیچ Firewall/Proxy/Certificate/Port 80/443/bind یا تنظیم بیرونی را تغییر نده.
- هیچ dependency یا کد خارجی Provider را بدون provenance و حق استفاده وارد نکن.
- Secret، Cookie، Token، OTP، رمز، شمارهٔ کامل، متن خصوصی پیام یا مسیر دارای شناسهٔ حساس را مشاهده، ثبت یا گزارش نکن.

اگر برای ادامه نیاز قطعی به credential، حساب/شبکهٔ واقعی، تغییر دادهٔ عملیاتی، تصمیم محصولی دربارهٔ Bale Bot/Personal، مجوز حقوقی، عملیات Git یا تغییر بیرونی بود، **هیچ راه دورزدنی انتخاب نکن**. یک گزارش جامع blocker در `docs/reports/blockers/` بنویس، Validation Ledger را به‌روز کن و دقیقاً متوقف شو.

اگر فایل مرتبطی دارای تغییر ناشناخته یا هم‌زمان متعلق به ایجنت دیگر بود، آن را overwrite نکن. دامنهٔ تعارض را مستند و کار را متوقف کن تا مالک پروژه زمان نوشتن انحصاری یا روش ادغام را تعیین کند.

### قالب پاسخ نهایی تو

1. نتیجه و سطح شاهد؛
2. چه چیزی عمومی شد و چه چیزی عمداً Provider-specific ماند؛
3. فایل‌های تغییرکرده؛
4. آزمون‌ها با شمار دقیق pass/fail و invocationهای نامعتبر؛
5. اثر بیرونی و تأیید اینکه داده/Session/Git حفظ شده‌اند؛
6. بدهی‌ها، blockerها و مرحلهٔ بعد؛
7. لینک گزارش مستقل و اسناد به‌روزشده.

---

## ۲. شیوهٔ پیشنهادی استفادهٔ هم‌زمان از Codex و Antigravity

### حالت پیشنهادی: تحویل ترتیبی با یک مالک نوشتن

1. Codex وضعیت canonical و محدودهٔ کار را در `docs/handoffs/` ثبت می‌کند.
2. در یک بازه فقط Antigravity روی worktree اصلی می‌نویسد و گزارش/آزمون/فهرست فایل‌ها را تکمیل می‌کند.
3. پس از پایان نوشتن Antigravity، Codex تغییرها را فقط‌خواندنی بازبینی، تست‌های لازم را اجرا و ناسازگاری اسناد/معماری/امنیت را اصلاح می‌کند.
4. کاربر تنها مرجع اجازه برای Live، Credential، ارسال، انتشار، شبکه، rollback و Git mutation باقی می‌ماند.

این حالت برای worktree فعلی که عمداً dirty است کم‌خطرترین روش است.

### حالت موازی مجاز

- یکی از ایجنت‌ها نویسندهٔ کد و دیگری فقط reviewer، طراح تست یا ممیز اسناد باشد؛ یا
- دو ایجنت فقط روی مجموعه‌فایل‌های کاملاً جدا کار کنند و مالکیت فایل‌ها پیشاپیش در یک handoff ثبت شود؛ یا
- کار نوشتنی در کپی/محیط جدا انجام و فقط patch/diff محدود برای بازبینی به مالک worktree اصلی تحویل شود.

دو ایجنت نباید هم‌زمان یک فایل، migration، Event Catalog، Registry، API dispatch یا سند generated را تغییر دهند. Branch/worktree تازه نیز به‌تنهایی تغییرهای dirty فعلی را منتقل نمی‌کند؛ بنابراین مبنای آن باید صریحاً با وضعیت واقعی همگام و روش ادغام از قبل تعیین شود.

### تقسیم نقش پیشنهادی برای B2

| نقش | مسئولیت |
|---|---|
| Antigravity | تحلیل محدود handlerها، پیاده‌سازی vertical slice عمومی، Fake/Contract tests و گزارش B2 |
| Codex | بازبینی معماری/امنیت، بررسی عدم regression، full validation، هماهنگی حافظهٔ مهندسی و پذیرش نهایی |
| مالک پروژه | تأیید عملیات Live/بیرونی، حل تعارض دامنه و تصمیم محصولی دربارهٔ Provider/account kind |

## ۳. قرارداد تبادل بین دو ایجنت

هر تحویل باید این هفت مورد را داشته باشد:

1. شناسهٔ فاز و محدودهٔ فایل‌ها؛
2. وضعیت اولیه از روی اسناد canonical؛
3. فهرست دقیق فایل‌های تغییرکرده؛
4. تصمیم‌ها و فرض‌های تازه؛
5. فرمان‌ها و شمار نتایج آزمون؛
6. failureها، blockerها و اثر بیرونی؛
7. گزارش مستقل و Validation Ledger به‌روزشده.

Chat حافظهٔ مشترک دو ایجنت نیست. `docs/project-memory/`، `docs/handoffs/`، `docs/reports/` و خروجی diff تنها کانال‌های معتبر تبادل هستند.

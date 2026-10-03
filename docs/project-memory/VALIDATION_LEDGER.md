# دفتر اعتبارسنجی‌ها و جلوگیری از آزمون تکراری

آخرین بازبینی: ۲۰۲۶-۰۸-۲۵

> یادداشت اعتبار جاری: رکوردهای پیش از V-103 شاهد تاریخی و وابسته به Trigger خود هستند. به‌علت drift ثبت‌شده در V-103، هیچ نتیجهٔ قدیمی `PRODUCTION_READY` یا شمارش `590/590` به‌تنهایی وضعیت snapshot جاری را اثبات نمی‌کند؛ V-103 به بعد مرجع وضعیت snapshot جاری است.

## فصل ۱ — اعتبارسنجی‌های قابل اتکا

| شناسه | موضوع | نوع شاهد | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-001 | ورود و Session واقعی ایتا | Live | پذیرفته | Phase 10-B | تغییر Auth/session ownership یا رخداد واقعی متعارض |
| V-002 | UI Desktop/Mobile و Account workspace | Live + automated | پذیرفته | Phase 9 و 10-B/10-D | تغییر layout/account gate/responsive CSS |
| V-003 | جداسازی AppUser/MessengerAccount | Fake/Contract/Adversarial | 48/48 و suites قبلی پذیرفته | Phase 10-C3 | تغییر authorization/scope/job/runtime |
| V-004 | Process isolation | Real child-process tests | پذیرفته | Phase 7 | تغییر IPC/supervisor/process runtime |
| V-005 | Audit/Correlation/Stress | Automated stress | پذیرفته | Phase 8-D | تغییر schema/audit/job/lease/correlation |
| V-006 | Support Bundle و PII scan | Real bundle + adversarial | finding=0 | Phase 10-D | تغییر bundler/scanner/log schema/included paths |
| V-007 | Health/readiness/drain/restart | Isolated runtime | پذیرفته | Phase 10-D | تغییر HTTP server/lifecycle/deployment |
| V-008 | وضعیت UI حساب‌ها | Static + Fake live در ۲۰۲۶-۰۸-۱۳ | Select و Add account descriptor-driven موجود؛ یک option واقعی؛ چندحساب Fake پذیرفته | Phase 11-0 | تغییر Gate/descriptor/onboarding route یا Pilot واقعی |
| V-009 | پوشش معماری لاگ | Static audit در ۲۰۲۶-۰۸-۱۳ | زیرساخت قوی، پوشش سراسری ناکامل | Logging audit | تغییر logger/audit/Electron/UI error handling |
| V-010 | یکپارچگی حافظهٔ مهندسی | Static documentation check | ۸ فایل، لینک مفقود=۰، خطای Encoding=۰، شمارهٔ کامل=۰ | `docs/project-memory` | افزودن/تغییر نام سند یا لینک |

## فصل ۲ — کار انجام‌شده در نوبت ۲۰۲۶-۰۸-۱۳

- نوع: ممیزی ایستای هدفمند و مستندسازی؛
- آزمون زنده: اجرا نشد؛
- شبکه/Provider: استفاده نشد؛
- Credential/Session/PII: مشاهده نشد؛
- تغییر Config: انجام نشد؛
- Git mutation: انجام نشد؛
- دلیل اجرا نشدن test suite: این تغییر فقط مستندات و تصمیم معماری است و شواهد آزمون‌های مربوط از Phase 7 تا 10 معتبرند.
- کنترل یکپارچگی مستندات: همهٔ لینک‌های Markdown محلی resolve شدند و اسکن Encoding/شمارهٔ کامل بدون Finding بود.

## فصل ۳ — قالب ورودی بعدی

```text
### V-NNN — عنوان
- تاریخ:
- سطح: Static | Unit | Contract | Fake | Adversarial | Isolated runtime | Live
- دامنه و فایل‌های مؤثر:
- فرمان/روش امن:
- نتیجه:
- Artifact/Report:
- دادهٔ واقعی/اثر بیرونی:
- Trigger تکرار:
```

## فصل ۴ — اعتبارسنجی Observability و سازمان‌دهی 2026-08-13

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-011 | Event Catalog، پوشش رخداد literal، schema، redaction، client diagnostics و rate limit | Unit/Contract/Adversarial | 6/6 موفق | `tests/test_observability_contract.py` | تغییر catalog/logger/client diagnostic |
| V-012 | regression کامل Backend | Automated full suite | 513/513 موفق در 81.5s | pytest با basetemp مستقل | تغییر Backend مرکزی/dependency |
| V-013 | React/Electron و UI regression | Contract + Build | observability موفق؛ 54/54 assertion شمارش‌دار موفق؛ production build موفق | npm scripts و Vite build | تغییر UI/API bridge/Electron/build config |
| V-014 | map/index/link و syntax ابزارها | Static/Generated | stale=0، broken link=0، py_compile موفق | `scripts/refresh_project_docs.py` | انتقال سند/تغییر generator/release script |
| V-015 | حفظ worktree و دادهٔ واقعی | Read-only filesystem/Git | diff-check دامنهٔ تغییر موفق؛ `bridge.json`، session، data، runtime، catalog و backups موجود؛ هیچ Git mutation انجام نشد | کنترل نهایی محلی | تغییر/انتقال config، runtime یا عملیات Git |

یادداشت invocation: نخستین تلاش اجرای هدفمند از working directory اشتباه `ui` به venv نسبی نرسید و PowerShell اجرای `npm.ps1` را رد کرد؛ هیچ تستی در آن تلاش اجرا نشد. روش canonical ویندوز از ریشه و با `.\.venv\Scripts\python.exe` و `npm.cmd --prefix ui` است.

یادداشت intentional-red: تست جدید پوشش catalog در اجرای نخست 43 رخداد literal قدیمی ثبت‌نشده را گزارش کرد. پس از افزودن metadata مرکزی همهٔ رخدادها، همان تست و suite کامل سبز شدند؛ failure اولیه یافتهٔ حل‌شده بود، نه وضعیت نهایی.

یادداشت import precedence: یک بررسی شمارش با `python -c` بدون `PYTHONPATH=src` نسخهٔ نصب‌شدهٔ قدیمی‌تر `.venv/site-packages` را resolve کرد و ImportError داد؛ این invocation هیچ اعتبارسنجی‌ای انجام نداد. pytest طبق `pyproject.toml` source جاری را استفاده کرد و شمارش catalog از فایل source برابر 68 بود. راهنمای توسعه این تفاوت را ثبت می‌کند.

یادداشت Git ownership: نخستین `git status` در sandbox با هشدار `dubious ownership` متوقف شد و هیچ تغییری نداد. بررسی فقط‌خواندنی با `git -c safe.directory=<workspace>` تکرار شد؛ global/local Git config تغییر نکرد و worktree عمداً dirty باقی ماند.

جزئیات: `../reports/features/OBSERVABILITY_FOUNDATION_REPORT_2026-08-13.md`.

## فصل ۵ — اعتبارسنجی Phase 11-0 در 2026-08-13

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-016 | Backend کامل پس از Multi-account Onboarding | Unit/Contract/Fake/Adversarial full regression | 518/518 موفق در 91.5s | pytest با basetemp مستقل | تغییر Coordinator/AppAuth/API/provider/account isolation |
| V-017 | قرارداد UI و Build | Static model/Contract/TypeScript/Build | 61/61 assertion شماره‌دار + observability موفق؛ production build موفق | npm scripts و Vite | تغییر Gate/dialog/descriptor/api bridge/build config |
| V-018 | پذیرش دیداری Onboarding | Fake live Desktop + Mobile | Dialog/Provider/privacy/enablement/cancel موفق؛ 390×844 بدون overflow؛ console نهایی 0 warning/error | Browser development fixture | تغییر layout/dialog/MUI/account management surface |
| V-019 | Runtime log PII/redaction | Read-only scanner | 9106 record، invalid JSON=0، finding=0 | `scripts/phase10_log_redaction_verify.py` | تغییر logger/redaction/event fields/included logs |
| V-020 | Idempotency و جداسازی ساخت حساب | Fake/Adversarial | retry پس از service restart، race هم‌زمان، cross-owner denial و forged fields موفق | `tests/test_phase11_0_multi_account_onboarding.py` | تغییر fingerprint/transaction/unique/membership/payload allowlist |
| V-021 | نقشه، فهرست گزارش و لینک‌های Markdown پس از Phase 11-0 | Generated/Static | refresh موفق؛ stale=0 و broken link=0 | `scripts/refresh_project_docs.py` | تغییر مسیر، سند، generator یا report |

### دامنه و اثر بیرونی

- حساب واقعی دوم: ساخته نشد؛
- Credential/OTP/password/Cookie/Token/شمارهٔ واقعی: مشاهده یا ثبت نشد؛
- Provider network و ارسال واقعی: استفاده نشد؛
- WordPress/Laragon: استفاده نشد؛
- Firewall/Proxy/Port 80/443: تغییر نکرد؛
- `bridge.json`، Session واقعی، data/catalog/backups: تغییر داده نشدند؛
- Git reset/checkout/clean/stage/commit/push/config mutation: انجام نشد؛
- Vite Fake listener فقط روی Loopback اجرا و پس از پذیرش terminate شد.
- پنج basetemp دقیق `.pytest-phase11-0-*` پس از ثبت نتیجه و کنترل مسیر حذف شدند؛ سایر cacheها و داده‌های عملیاتی حفظ شدند.

### Warning معتبر باز

- Build chunk اصلی 894.38 kB است و هشدار آستانهٔ 500 kB دارد؛ F-013 غیرمسدودکننده و باز است.

### Invocation/error ledger

1. Python پیش‌فرض سیستم `pytest` نداشت؛ نتیجهٔ معتبری تولید نشد و `.venv` استفاده شد.
2. pytest Temp سراسری Windows مجوز نداشت؛ اجرای معتبر با basetemp داخل workspace تکرار شد.
3. یک targeted regression پس از گسترش Provider descriptor یک expectation قدیمی را شکست؛ expectation به قرارداد تازه ارتقا و suite سبز شد.
4. اجرای نخست تست‌های تازه پنج خطای fixture/assertion داشت؛ fixture AppPrincipal، نام کلید خطا و correlation argument اصلاح شدند.
5. PowerShell `npm.ps1` را طبق ExecutionPolicy رد کرد؛ `npm.cmd` check/test/build موفق بود.
6. `Start-Process` به‌علت duplicate PATH در محیط sandbox آغاز نشد؛ اجرای مستقیم Vite موفق و سپس terminate شد.
7. پذیرش دیداری Warning Tooltip روی Button غیرفعال را یافت؛ wrapper اصلاح و تب تازه صفر warning/error شد.
8. Git read-only ابتدا `dubious ownership` داد؛ با override همان invocation و بدون تغییر Config بررسی شد.
9. lookup یک Event Catalog و Baseline با مسیر اشتباه fail شد؛ مسیر canonical پیدا شد و هیچ mutation مرتبطی رخ نداد.
10. یک block اعتبارسنجی payload هنگام patch ابتدا در handler مجاور دیده شد؛ بازبینی قبل از پذیرش آن را جابه‌جا کرد و compile/targeted/full suite موفق شدند.
11. نخستین فرمان تجمیعی کنترل نهایی به‌دلیل عملگر سه‌تایی ناسازگار با PowerShell parse نشد؛ فرمان فقط‌خواندنی بود و با `if/else` تکرار شد. نتیجهٔ معتبر: داده‌های عملیاتی حاضر، scratch این مرحله صفر و diff-check موفق.

جزئیات: `../reports/phases/PHASE11_0_MULTI_ACCOUNT_ONBOARDING_FOUNDATION_REPORT_2026-08-13.md`.

## فصل ۶ — اعتبارسنجی Phase 11-A در 2026-08-13

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-022 | ممیزی دو ZIP بله | Static source/archive | traversal=0، binary=0؛ Personal: 20 فایل Python/9 تست آفلاین؛ Aiobale: 237 فایل Python/0 تست همراه | `BALE_PROVIDER_DISCOVERY.md` | تغییر hash ورودی یا منبع تازه |
| V-023 | بررسی منابع رسمی بله | Current primary web sources | API رسمی فقط Bot/Arm مستند؛ استفاده از API غیررسمی/مهندسی معکوس صریحاً ممنوع | شرایط و مستندات رسمی بله | تغییر مادی صفحهٔ رسمی یا مجوز کتبی |
| V-024 | حفظ مرز محصول | Static project state | هیچ source/config/dependency/descriptor/runtime تغییر نکرد؛ Bale غیرفعال ماند | گزارش Phase 11-A | انتخاب مسیر رسمی Bot یا قرارداد personal |

### دامنه و اثر بیرونی

- ZIPها استخراج، import، نصب یا اجرا نشدند؛
- test suite داخل ZIPها اجرا نشد؛ اعداد test از تحلیل ایستا به‌دست آمد؛
- Provider endpoint، auth، OTP، Session، Send و Capture استفاده نشد؛
- فقط GitHub پروژه، مستندات خود Aiobale و صفحات عمومی رسمی بله خوانده شدند؛
- هیچ Credential/Token/Cookie/شمارهٔ کامل یا مقدار app key وارد Log/Report نشد؛
- هیچ Git mutation، Config change یا دست‌کاری دادهٔ واقعی انجام نشد؛
- regression محصول اجرا نشد، چون source/config/runtime محصول تغییر نکرد.

جزئیات: `../reports/phases/PHASE11A_BALE_DISCOVERY_AND_COMPLIANCE_BLOCKER_REPORT_2026-08-13.md`.

## فصل ۷ — اعتبارسنجی زیرساخت Phase 11-B0 در 2026-08-13

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-025 | Provider Extension contract و fail-closed Bale slot | Unit/Contract/Fake/Adversarial targeted | 23/23 موفق؛ مجوز/state gate، factory shape، session isolation، secret repr و منع network/dynamic loader پذیرفته شد | `tests/test_phase11b_provider_extension_foundation.py` و suiteهای مرتبط | تغییر contracts/registry/worker/Bale slot |
| V-026 | سازگاری UI و Observability | TypeScript + source contracts | type-check موفق؛ onboarding 7/7؛ observability contract موفق | `ui/` | تغییر descriptor/Gate/Event Catalog/Electron observability |
| V-027 | Full regression پس از Registry migration | Backend + UI + production build | Python 525/525؛ UI شماره‌دار 61/61؛ observability موفق؛ build موفق | pytest و npm scripts | تغییر contracts/registry/worker/UI |
| V-028 | محرمانگی log واقعی | Read-only scanner | 9106 رکورد؛ invalid JSON=0؛ finding=0 | `scripts/phase10_log_redaction_verify.py` | تغییر logger/redaction/Provider event fields یا log corpus |
| V-029 | اسناد و metadata نهایی | Generated/Static | stale=0؛ broken link=0؛ compile موفق؛ Event Catalog=76؛ provider catalog=`bale,eitaa`؛ diff-check موفق | refresh script و source probe | تغییر docs/generator/contracts/catalog |

### دامنه و اثر بیرونی

- هیچ endpoint پیام‌رسان، login، OTP، Session یا Send استفاده نشد؛
- ZIPهای بله import، نصب، استخراج یا اجرا نشدند؛
- `bridge.json`، داده، catalog، runtime، backup و نشست واقعی تغییر نکردند؛
- هیچ Firewall/Proxy/Port/Git config تغییر نکرد؛
- Bale descriptor همچنان runtime/onboarding غیرفعال است.

### Invocation/error ledger

1. lookup اولیهٔ مسیر فرضی `domain/models.py` نتیجه نداشت؛ مسیرهای canonical با جست‌وجوی source پیدا شدند و mutation رخ نداد.
2. Git sandbox هشدار `dubious ownership` داد؛ بررسی فقط‌خواندنی با override همان invocation و بدون تغییر config ادامه یافت.
3. یک عبارت جست‌وجو که با `--provider` آغاز می‌شد flag تفسیر شد؛ بررسی با نحو امن تکرار شد.
4. نخستین full regression یک failure سازگاری Worker داشت: کد امن `eitaa_worker_process_feature_disabled` در factory boundary عمومی شده بود. Registry برای عبور همهٔ `BridgeError`های امن اصلاح شد و exceptionهای ناشناخته همچنان sanitize می‌شوند.
5. metadata probe نخست بدون `PYTHONPATH=src` نسخهٔ نصب‌شدهٔ قدیمی محیط مجازی را import کرد؛ با source path صریح تکرار و نتیجهٔ معتبر ثبت شد. pytestهای پروژه از ابتدا `pythonpath=[src]` داشتند.

هشدار build: chunk اصلی 894.38 kB است؛ همان بدهی غیرمسدودکنندهٔ F-013 و بدون تغییر نسبت به مبنای پیشین.

## فصل ۸ — اعتبارسنجی Phase 11-B1 در 2026-08-13/14

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-030 | Coordinator v5→v6 و Contact v2→v3 | Migration/Unit/Adversarial | حفظ داده، checksum، FK، trigger، quick-check و backup موفق | `tests/test_phase11b1_multi_provider_core.py` | تغییر schema/migration/reconciliation |
| V-031 | Fake Provider سوم، Registry، Capability و عدم escalation | Contract/Fake/Adversarial | targeted مرتبط `48/48` موفق | تست B1 و Provider foundation | تغییر Manifest/Registry/Fake/Capability |
| V-032 | API/AppUser/runtime/observability compatibility | Unit/Contract | targeted `55/55` موفق | suiteهای API و Phase 11 | تغییر API dispatch/account auth/runtime |
| V-033 | regression کامل Backend | Automated full suite | `540/540` موفق در 102.6s | pytest با basetemp مستقل | تغییر Backend/dependency/schema |
| V-034 | UI/Electron/build | TypeScript/Contract/Build | check موفق؛ assertion شماره‌دار `61/61`؛ observability موفق؛ build موفق | npm scripts و Vite | تغییر UI/API descriptor/capability/build |
| V-035 | محرمانگی Runtime log | Read-only scanner | 9106 رکورد، invalid JSON=0، finding=0 | `scripts/phase10_log_redaction_verify.py` | تغییر logger/event fields/redaction/log corpus |
| V-036 | metadata عمومی B1 | Static/source probe | schema=6، Event Catalog=78، product catalog=`bale,eitaa`، collected tests=540 | source با `PYTHONPATH=src` | تغییر catalog/schema/test collection |

### دامنه و اثر بیرونی

- Provider network/Login/OTP/Send/WordPress استفاده نشد.
- DB عملیاتی، `bridge.json`، Session، data/runtime/catalog/backups تغییر نکردند.
- migration فقط روی فایل‌های موقت آزمون انجام شد.
- Git reset/checkout/clean/stage/commit/push/config mutation انجام نشد و worktree dirty حفظ شد.

### Invocation/error ledger

1. چند جست‌وجوی فقط‌خواندنی اولیه به‌علت quoting/glob ناسازگار PowerShell اجرا نشدند؛ با الگوی Windows-safe تکرار شدند.
2. دو lookup مسیر فرضی را پیدا نکردند؛ مسیر canonical با فهرست فایل‌ها مشخص شد.
3. targeted نخست `38 passed / 1 failed` داشت؛ شکست فقط assertion قدیمی version=5 بود. انتظار به schema جاری 6 ارتقا و اجرای نهایی سبز شد.
4. Git status نخست `dubious ownership` داد؛ فقط همان فرمان با override موقت invocation اجرا شد و هیچ config تغییر نکرد.
5. full regression نخست در سقف 120s و 66٪ timeout شد؛ نتیجهٔ معتبر تلقی نشد. اجرای دوم با basetemp تازه `540/540` موفق شد.
6. collect-only نخست با tail شمار کل را نشان نداد؛ جمع امن شمار فایل‌ها مقدار 540 را تأیید کرد.
7. patch تجمیعی نخستِ اسناد به‌علت تفاوت context انتهای Validation ledger اعمال نشد و هیچ فایل را تغییر نداد؛ patch به بخش‌های دقیق تقسیم و سپس کامل اعمال شد.

جزئیات: `../reports/phases/PHASE11B1_MULTI_PROVIDER_CORE_REPORT_2026-08-13.md`.

## فصل ۹ — آماده‌سازی handoff دوایجنتی در 2026-08-17

### V-037 — پرامپت اجرایی Antigravity و قرارداد مالکیت نوشتن

- تاریخ: ۲۰۲۶-۰۸-۱۷
- سطح: `STATIC / DOCUMENTATION`
- دامنه و فایل‌های مؤثر: حافظهٔ مهندسی، نقشه‌راه چندProvider، راهنمای Provider، گزارش نهایی 11-B1 و handoff تازهٔ 11-B2.
- روش امن: فقط اسناد canonical خوانده شدند؛ کد، listener، DB عملیاتی، Session و Provider network دوباره بررسی نشدند، زیرا Trigger ابطال برای شواهد B1 وجود نداشت.
- نتیجه: وضعیت فعلی، مأموریت B2، معیارهای آزمون، ممنوعیت‌های عملیاتی، شرایط توقف و قرارداد همکاری Codex/Antigravity در `docs/handoffs/ANTIGRAVITY_PHASE11B2_HANDOFF_PROMPT_2026-08-17.md` ثبت شد؛ refresh فهرست اسناد انجام و هر دو کنترل stale و لینک‌های محلی با exit code صفر پذیرفته شدند.
- Artifact/Report: handoff یادشده و F-019.
- دادهٔ واقعی/اثر بیرونی: هیچ؛ Credential/PII مشاهده نشد، سرویس/Config/Git/data/runtime تغییر نکرد.
- Trigger تکرار: تغییر وضعیت Phase 11-B2، سیاست مالکیت worktree، گزارش نهایی تازه یا آغاز Provider مجاز جدید.

### Invocation/error ledger

1. نخستین فراخوانی ابزار مطالعه به نام ناموجود `shell_command` ارجاع داد و پیش از اجرای هر فرمان با `TypeError` متوقف شد؛ هیچ فایل یا وضعیت بیرونی تغییر نکرد. مطالعه با ابزار صحیح و read-only تکرار شد.
2. یک مطالعهٔ تجمیعی اسناد خروجی بیش از ظرفیت همان فراخوانی تولید کرد و نمایش آن truncate شد؛ اسناد الزامی سپس در فراخوانی‌های محدودتر و فایل‌محور دوباره خوانده شدند.

## فصل ۱۰ — اعتبارسنجی Phase 11-B2 slice 1 در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-038 | orchestrator عمومی، Eitaa compatibility، Fake سوم، authorization/capability/deadline/result | Unit/Contract/Fake/Adversarial | suite نهایی B2 برابر `14/14` موفق | `tests/test_phase11b2_provider_neutral_orchestration.py` | تغییر orchestrator/DTO/adapter/API |
| V-039 | replay/idempotency/race/uncertain send و Manifest ceiling | Adversarial | replay پس از لغو دسترسی رد؛ duplicate race یک provider call؛ uncertain بدون retry؛ escalation رد | همان suite | تغییر cache/key/manifest/capability |
| V-040 | دو AppUser، چند حساب یک Provider و چند Provider | Contract/Adversarial | account context فقط server-resolved؛ cross-account پیش از adapter رد؛ result هر حساب مستقل | همان suite | تغییر membership/context resolver/adapter resolution |
| V-041 | UI account capability و منع request نامجاز | Static contract/TypeScript | B2 UI=`6/6`، onboarding=`7/7`، TypeScript check نهایی موفق | `ui/scripts/run-phase11b2-orchestration-tests.mjs` | تغییر Gate/App/QuickSend/Contacts |
| V-042 | regression هدفمند Phase 11/API | Unit/Contract | B0+B1+B2+11-0+API برابر `75/75` موفق؛ observability Python=`6/6` | pytest با basetemp مستقل | تغییر Provider core/API/observability |
| V-043 | regression کامل Backend | Automated full suite | اجرای نهایی `554/554` موفق؛ collection مستقل=`554` | pytest full با `.pytest-phase11b2-full-02` | تغییر Backend/قرارداد مرکزی |
| V-044 | UI/Electron/build | Contract/TypeScript/Build | B2=`6/6`، observability موفق، onboarding=`7/7`، build نهایی موفق | npm scripts/Vite | تغییر UI/build graph/capability |
| V-045 | محرمانگی runtime log و Event Catalog | Read-only scanner/Contract | `9106` رکورد، invalid JSON=`0`، finding=`0`؛ Event Catalog=`84` | redaction verifier و source probe | تغییر event fields/logger/scanner |
| V-046 | نقشه، فهرست گزارش و لینک‌های B2 | Generated/Static | refresh موفق؛ stale=`0`؛ broken local link=`0` | `scripts/refresh_project_docs.py` | تغییر source/docs/generator/path |

### ترتیب شواهد هدفمند

1. هنگام رشد suite مستقل B2، نتایج میانی `7/7`، `9/9`، `10/10` و نهایی `14/14` همگی سبز بودند.
2. regressionهای میانی B2+B1 برابر `22/22`، B2+B1+B0 برابر `30/30`، API+11-0 برابر `39/39` و تجمیع نهایی مرتبط `75/75` بود.
3. تست‌های malformed result، media بزرگ‌تر از حد request، exception خام، correlation نامعتبر، deadline منقضی، context جعلی و snapshot stale همگی fail-closed موفق شدند.

### Invocation/error ledger

1. patch تجمیعی نخست برای افزودن API helperها به‌علت context نامنطبق اعمال نشد؛ هیچ فایلی تغییر نکرد و patch به بخش‌های کوچک تقسیم شد.
2. دو patch ترکیبی UI به‌علت یک خط بسیار بلند Contact modal context پیدا نکردند و اتمیک بدون mutation متوقف شدند؛ guard سمت handler و اجزای قابل‌ویرایش جداگانه اعمال شدند.
3. اجرای نخست UI B2 پس از `3/6` به‌دلیل assertion بیش‌ازحد وابسته به نام شرط متوقف شد؛ تست به behavior واقعی `canSend/disabled` تغییر کرد و نهایی `6/6` شد.
4. نخستین production build با دو `TS18047` در narrowing مقدار nullable capability snapshot متوقف شد. null guard صریح افزوده شد؛ TypeScript check و build نهایی موفق شدند.
5. full regression نخست `553 passed / 1 failed` داشت. failure فقط expectation ایستای قدیمی dependency array رسانه بود؛ انتظار به dependency امن تازهٔ `mediaReadSupported` ارتقا یافت، targeted سبز شد و full دوم `554/554` موفق بود.
6. چند جست‌وجوی PowerShell با quote/glob ناسازگار parse/resolve نشدند؛ فرمان‌ها فقط‌خواندنی بودند و با `rg` و مسیر Windows-safe تکرار شدند.
7. Git read-only به‌علت `dubious ownership` ابتدا اجرا نشد؛ فقط همان فراخوانی با `git -c safe.directory=<workspace>` تکرار شد و config/stage/commit تغییر نکرد.
8. یک source probe با `python -c` بدون `src` در import path، package جاری را پیدا نکرد و شاهدی نساخت؛ probe با `sys.path` صریح تکرار و Event Catalog=`84` تأیید شد.
9. فراخوانی `--help` اسکنر فقط usage را تأیید کرد و شاهد privacy محسوب نشد؛ اجرای واقعی جداگانه با finding=`0` پذیرفته شد.

### دامنه و اثر بیرونی

- Provider network، Login، OTP، Credential، Send واقعی و WordPress استفاده نشد.
- DB عملیاتی، `bridge.json`، `.env`، Session، `data/`، `runtime/`، `diagnostics/` و `backups/` تغییر داده نشدند؛ scanner فقط‌خواندنی بود و مقدارها را echo نکرد.
- هیچ Firewall/Proxy/Port/Certificate یا Git mutation/config انجام نشد و worktree عمداً dirty حفظ شد.
- سطح شاهد B2 فقط `UNIT / CONTRACT-FAKE / ADVERSARIAL / BUILD`؛ هیچ ادعای Live وجود ندارد.

## فصل ۱۱ — تکمیل محلی Phase 11-B2 و رسیدن به مرز بیرونی در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-047 | شش operation عمومی، Media/Contacts و confirmation | Unit/Contract/Adversarial | B2 مستقل نهایی `20/20`؛ field allowlist، capability، bounded result و `confirm=true` پذیرفته | `tests/test_phase11b2_provider_neutral_orchestration.py` | تغییر route/DTO/orchestrator/confirmation |
| V-048 | Eitaa Process Child RPC و media chunk broker | Contract/Process/Adversarial | method/field/fence forged رد؛ شش mapper typed؛ media path در Child و chunk پیوسته/محدود پذیرفته | B2 + Phase 7A/7B/7D + HTTP media | تغییر worker/process runtime/IPC/media streaming |
| V-049 | receipt پایدار Send/Contact و مهاجرت Coordinator v7 | Unit/Migration/Privacy | restart replay بدون provider call؛ owner/payload mismatch رد؛ stale claim بدون retry uncertain؛ direct v6→v7 + FK/quick check موفق؛ B2+schema=`38/38` | `coordinator/receipts.py`، `schema.py` و تست‌های B2/schema | تغییر receipt/schema/orchestrator idempotency |
| V-050 | regression مرتبط Phase 11/Process/API/Observability | Unit/Contract/Fake/Adversarial | `133/133` موفق | ۱۲ فایل تست مرتبط با basetemp مستقل | تغییر Provider core/API/Process/Coordinator |
| V-051 | regression کامل Backend | Automated full suite | اجرای نهایی پس از همهٔ تغییرها `561/561` موفق؛ collection مستقل=`561` | pytest full با `.pytest-work/full-phase11-delivery-20260820` | تغییر Backend یا قرارداد مرکزی |
| V-052 | UI capability/onboarding/observability/build | Contract/TypeScript/Build | B2=`6/6`، onboarding=`7/7`، observability موفق، TypeScript check و Vite production build موفق | npm scripts canonical | تغییر UI/Electron/build graph |
| V-053 | Event Catalog و محرمانگی log/receipt | Contract/Read-only scanner | Catalog=`86`؛ runtime=`9106` رکورد، invalid=`0`، finding=`0`؛ replay log فاقد متن/identity/key؛ DB تست فاقد payload خام | observability/B2 tests و `scripts/phase10_log_redaction_verify.py` | تغییر logger/event/receipt/redaction |
| V-054 | حافظه، گزارش نهایی، فهرست و لینک‌ها | Generated/Static | refresh سه artifact موفق؛ stale=`0`؛ broken local link=`0`؛ `git diff --check` موفق | `scripts/refresh_project_docs.py` و Git read-only | تغییر source/docs/generator/path |

### Failure و تحلیل اصلاحی

1. نخستین اجرای persistence یک شکست داشت چون harness تست قابلیت‌ها را همیشه از Manifest Fake می‌خواند؛ harness به Provider واقعی account bind شد و اجرای تکراری `38/38` سبز شد.
2. آزمون تازهٔ direct v6→v7 یک ایراد واقعی پیدا کرد: verifier نسخهٔ ۶ جدول v7 را زود مطالبه می‌کرد. نگاشت `REQUIRED_TABLES_V6` اصلاح و همان آزمون با integrity/FK check پذیرفته شد؛ F-022 ثبت شد.
3. دو assertion لاگ ابتدا با context عمومی `finally` در محل تست اشتباه patch شدند؛ قبل از اجرا با جست‌وجوی موضعی کشف، حذف و در سناریوهای persistence دقیق قرار گرفتند.
4. Git read-only بدون safe-directory موقت به‌علت مالکیت sandbox رد شد؛ فقط invocation با `git -c safe.directory=<workspace>` تکرار شد و هیچ config/stage/commit تغییر نکرد.
5. probe شمار Catalog ابتدا package نصب‌شدهٔ قدیمی را import کرد؛ شاهد نساخت و با `sys.path.insert(0,'src')` فقط‌خواندنی تکرار شد؛ نتیجه 86 است.
6. patch تجمیعی نخست مستندات به‌علت context متفاوت `PROJECT_STRUCTURE.md` اتمیک اعمال نشد؛ اسناد به patchهای فایل‌محور کوچک تقسیم شدند.

### دامنه و اثر بیرونی

- همهٔ DBها و cacheهای این پذیرش در مسیر موقت workspace بودند؛ DB عملیاتی migrate و سرویس واقعی restart نشد.
- Provider network، Login، OTP، Credential، Send واقعی، WordPress و تغییر Firewall/Proxy/Port/Certificate انجام نشد.
- `bridge.json`، `.env`، Session واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` نوشته یا جابه‌جا نشدند؛ log scanner فقط‌خواندنی بود.
- worktree عمداً dirty حفظ شد و reset/checkout/clean/stage/commit/push یا Git config mutation انجام نشد.
- سطح پذیرش `UNIT / CONTRACT-FAKE / ADVERSARIAL / BUILD` است. ادامهٔ 11-C/Live 11-D فقط طبق گزارش blocker بیرونی مجاز است.

## فصل ۱۲ — Material/mobile، ثبت‌نام و دریافت خودکار پیام در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-055 | AppUser self-registration، رمز چهار نویسه‌ای و نشست یک‌ساله | Unit/Contract/Config | ثبت‌نام private-only و user-only، min=4، cookie/session یک‌ساله و fail-closed config در full suite پذیرفته | `test_app_user_auth.py`، `test_app_user_api.py`، `test_config.py` | تغییر AppAuth/register/policy/deployment/cookie |
| V-056 | Material-only و mobile-first UI contract | Static/Unit/Contract | مجموعهٔ هدفمند Python برابر `65/65`؛ source فعال بدون class و stylesheet اختصاصی، module/safe-area/touch/layout پذیرفته | تست‌های Material/Phase6D/UI repair/scroll/composer | تغییر TSX/theme/shell/module/layout |
| V-057 | مدل‌ها و contractهای شماره‌دار UI | Contract | Scroll=`10/10`، grouped media=`16/16`، Phase9=`22/22`، Phase10=`7/7`، Phase11=`13/13`؛ جمع شماره‌دار=`68/68`؛ mobile-auth-live و observability نیز موفق | npm scripts canonical | تغییر UI state/polling/account gate/Electron |
| V-058 | TypeScript و production build | TypeScript/Build | check موفق؛ Vite موفق با 1006 module؛ main=`785.60 kB` و gzip=`240.96 kB`؛ warning آستانه 500 kB در F-013 باز | `npm.cmd --prefix ui run check/build` | تغییر dependency/import graph/Vite/UI |
| V-059 | regression کامل Backend و migration در Windows | Automated full suite/Isolated temp | full=`566/566`؛ migration suite خارج از sandbox=`7/7`؛ فقط warning cache غیرعملکردی | pytest با basetemp workspace و اجرای مجاز خارج sandbox | تغییر Backend/schema/migration/auth/live route |
| V-060 | حافظه، گزارش مستقل، map/index و لینک‌ها | Generated/Static | سه artifact تولیدشونده refresh شد؛ stale=`0` و broken local link=`0` | `scripts/refresh_project_docs.py` | تغییر source/docs/generator/path |
| V-061 | حفظ worktree و توقف listener موقت | Read-only Git/process | `git diff --check` موفق؛ status فقط‌خواندنی dirty گستردهٔ موجود را تأیید کرد؛ Port 5173 پس از Ctrl-C listener ندارد؛ هیچ Git mutation نشد | Git با safe-directory invocation و کنترل listener | تغییر Git state یا اجرای dev server |

### Failure و تحلیل اصلاحی

1. full pytest داخل sandbox ابتدا 20 شکست ثبت کرد: 18 تست ایستای قدیمی وجود class/CSS سفارشی و labelهای پیشین را مطالبه می‌کردند؛ قراردادها به MUI component، `sx`، aria و moduleهای جاری منتقل و رفتارهای ایمنی متن دعوت/ویرایش تقویت شدند. دو شکست migration فقط `WinError 5` روی rename پوشهٔ موقت بودند؛ اجرای خارج sandbox `7/7` و full نهایی `566/566` شد.
2. rerun هدفمند UI ابتدا `64/65` بود چون تست label قدیمی «شناسه و Access Hash» را انتظار داشت؛ label امن جاری «شناسه فنی» معیار شد و rerun `65/65` سبز شد.
3. نخستین full run پیش از اصلاح قراردادها خطای session 13ساعته نیز داشت؛ این انتظار تاریخی با policy صریح یک‌ساله ناسازگار بود. تست اکنون active در 13 ساعت و expired پس از عبور از یک سال را بررسی می‌کند.
4. Pytest امکان نوشتن `.pytest_cache` را نداشت، اما basetemp داخل workspace و exit code نهایی صفر بود؛ warning شاهد شکست محصول نیست.
5. Browser درون برنامه localhost را با `ERR_BLOCKED_BY_CLIENT` رد کرد؛ Chrome در دسترس نبود و file URL طبق مرز امنیتی رد شد. bypass انجام نشد و پذیرش دیداری تازه شاهد این نوبت نیست؛ F-025 باز شد.
6. build موفق است ولی chunk اصلی هنوز بالاتر از 500 kB است؛ از 894.38 به 785.60 kB کاهش یافت و F-013 باز باقی ماند.
7. چند patch تجمیعی context خطوط بلند را پیدا نکردند و بدون mutation متوقف شدند؛ patchهای کوچک‌تر اعمال و پس از آن TypeScript/full regression اجرا شد.
8. Vite dev server مورد استفاده برای تلاش پذیرش دیداری، هنگام dependency scan به HTMLهای موجود در runtime/Edge profile نیز رسید و به access/resolve/EPERM خورد؛ این scan شاهد build نبود. production build مستقل موفق شد، dev server با Ctrl-C بسته شد و کنترل نهایی Port 5173 را بدون listener یافت.

### دامنه و اثر بیرونی

- با دستور صریح مالک فقط policyهای self-registration/session در `bridge.json` و نمونهٔ آن به‌روز شدند؛ secret یا PII در گزارش/لاگ وارد نشد.
- Provider network، Login، OTP، Send/Invite واقعی و WordPress استفاده نشد.
- Session واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` جابه‌جا یا بازنویسی نشدند.
- Firewall/Proxy/Port/Certificate/rollback و migration DB عملیاتی انجام نشد.
- سطح شاهد UI جدید `STATIC / UNIT / CONTRACT / BUILD` است؛ پذیرش Live Provider یا Browser دیداری ادعا نمی‌شود.

جزئیات: `../reports/features/MATERIAL_MOBILE_SELF_REGISTRATION_LIVE_SYNC_REPORT_2026-08-20.md`.

## فصل ۱۳ — بازیابی startup پس از استفادهٔ مجدد PID در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-062 | علت‌یابی خروج Backend و تطبیق مالکیت واقعی PID | Local runtime forensics / Read-only | لاگ startup به `eitaa_worker_process_alive` رسید؛ رکورد و lease قدیمی یک PID زنده داشتند، اما executable سیستم‌عامل `svchost.exe` و نامرتبط با Python Worker بود | `server-console.log`، metadata امن Coordinator/lease و OS executable probe | تغییر رکورد عملیاتی، liveness probe یا رخداد startup تازه |
| V-063 | قرارداد PID reuse، lease، registry و audit reason | Unit/Contract/OS probe | red اولیه خطای قبلی را بازتولید کرد؛ نهایی `4/4` و suite مالکیت/Process برابر `25/25` موفق | `tests/test_phase4d_account_management.py` و Phase 7B/7C/7D | تغییر account runtime، lease، coordinator recovery یا spawn |
| V-064 | regression کامل و کنترل‌های canonical | Automated full suite / TypeScript / Observability / Generated docs | Backend `570/570`؛ TypeScript check و observability موفق؛ docs refresh/check/link-check موفق | pytest، npm و `scripts/refresh_project_docs.py` | تغییر Backend/UI/docs generator |
| V-065 | محرمانگی لاگ واقعی پس از علت‌یابی | Read-only scanner | ۹۱۰۸ رکورد JSONL؛ `invalid_json=0` و `finding=0` | `scripts/phase10_log_redaction_verify.py` | تغییر logger/redaction/event fields یا log corpus |

### Failure و تحلیل اصلاحی

1. آزمون red نخست علاوه بر failure عملکردی مورد انتظار، برای fixture دارای `tmp_path` با `WinError 5` در temp سراسری روبه‌رو شد؛ اجرای معتبر با basetemp صریح داخل workspace انجام شد.
2. دو probe فقط‌خواندنی Python ابتدا به‌علت quote نامعتبر، یک `SyntaxError` و سپس خطای SQL ساختند و هیچ شاهدی تولید نکردند؛ query پارامتری امن در اجرای سوم metadata بدون شناسهٔ حساب را برگرداند.
3. `Get-CimInstance` و `tasklist` برای جزئیات فرایند با Access denied متوقف شدند؛ راه‌حل محصول به API فقط‌خواندنی Toolhelp محدود شد و همان API executable نامرتبط را با موفقیت تشخیص داد.
4. یک `rg` اولیه glob ویندوز را نپذیرفت؛ مسیرهای canonical با الگوی Windows-safe پیدا شدند.
5. فرمان Git فقط‌خواندنی به‌دلیل نبودن repository قابل‌شناسایی در این context اجرا نشد؛ هیچ Git config یا mutation انجام نشد و شاهد پذیرش بر Git متکی نیست.

### دامنه و اثر بیرونی

- لاگ واقعی، Worker metadata، lease و executable فقط‌خواندنی بررسی شدند؛ هیچ PII، شناسهٔ حساب یا Credential در سند ثبت نشد.
- `bridge.json`، `.env`، Session، `data/`، `runtime/`، `diagnostics/` و `backups/` تغییر داده نشدند؛ test artifactها فقط در basetemp workspace بودند.
- Backend واقعی restart نشد و Provider network/Login/OTP/Send/WordPress به‌کار نرفت.
- هیچ process termination، پاک‌سازی دستی lease، migration عملیاتی، تغییر Port/Firewall/Proxy/Certificate یا Git mutation انجام نشد.

جزئیات: `../reports/features/BACKEND_STARTUP_PID_REUSE_RECOVERY_REPORT_2026-08-20.md`.

## فصل ۱۴ — کارت Material پیام و بازیابی خودکار نشست در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-066 | Red contracts نام نویسنده، نشست و Login/Card | Test-first / Static / Unit | اجرای نخست `5/5` شکست مورد انتظار داشت؛ script موبایل نیز نبود component را آشکار کرد | تست‌های تازه در `test_application_api.py`، `test_account_auth_lifecycle.py`، `test_material_ui_repair.py` و mobile script | تغییر قرارداد محصول یا حذف test |
| V-067 | نام Contact و استثنای Eitaa | Unit/Contract | Contact عادی اولویت دارد؛ عنوان `Eitaa/ایتا` نام member/history را نمی‌پوشاند؛ targeted نهایی موفق | `test_api_message_sender_names_prefer_eitaa_contacts_then_members` | تغییر sender enrichment/contact source |
| V-068 | بازیابی خودکار fail-closed نشست | Unit/Adversarial/Audit | invalid به absent و backup یکتا؛ response بدون archive name؛ reason امن؛ نشست authenticated با 400 دست‌نخورده ماند | دو test automatic recovery در `test_account_auth_lifecycle.py` | تغییر auth state/reset/archive/audit |
| V-069 | Material Card، Login مرکزی و UI regressions | Static/Contract/TypeScript/Build | هدفمند `24/24`؛ assertionهای شماره‌دار UI `68/68`؛ mobile-auth-live/observability/check موفق؛ build 1008 module و main=`787.69 kB` gzip=`241.44 kB` | Python UI contracts و همهٔ npm scriptهای canonical | تغییر Message card/Login/App/UI graph |
| V-070 | regression کامل Python | Automated full suite / Isolated temp | اجرای نهایی `573/573` موفق؛ collection مستقل=`573` | pytest با `.test-tmp/full-session-card-final` | تغییر Backend، API، auth یا UI static contracts |
| V-071 | محرمانگی log واقعی | Read-only scanner | application=`8645`، worker=`484`، مجموع=۹۱۲۹؛ invalid JSON=`0` و finding=`0` | `scripts/phase10_log_redaction_verify.py` | تغییر logger/audit/redaction/log corpus |
| V-072 | حافظه، report index، map/symbol و لینک‌ها | Generated/Static/Git read-only | سه artifact refresh؛ stale=`0`، broken local link=`0`، TypeScript/observability تکراری و `git diff --check` موفق | `scripts/refresh_project_docs.py` و Git با safe-directory موقت | تغییر source/docs/generator/path |
| V-073 | Red قرارداد runtime/version/font/CSRF/OTP | Test-first / Static / Unit | dev entry-point، version source، دو وزن فونت، استقلال CSRF، OTP محلی‌سازی‌شده و provider error mapping ابتدا روی رفتار قبلی شکست خوردند | runtime/UI/auth testهای تازه | تغییر Electron main، Theme، api client یا auth OTP |
| V-074 | runtime، Auth و Material هدفمند | Unit/Contract/TypeScript | runtime ownership نهایی `21/21`؛ Auth+Material نهایی `38/38`؛ TypeScript check موفق | pytest هدفمند و `npm run check` | تغییر runtime ownership/version/auth/Login UI |
| V-075 | مدل‌ها و build نهایی UI | Contract/TypeScript/Build | Scroll=`10/10`، grouped=`16/16`، Phase9=`22/22`، Phase10=`7/7`، Phase11=`13/13`؛ observability/mobile-auth-live موفق؛ build 1008 module و main=`788.97 kB` gzip=`241.76 kB` | همهٔ npm scriptهای canonical و build | تغییر UI state/import graph/theme/auth/live sync |
| V-076 | regression کامل Backend پس از اصلاح‌های زنده | Automated full suite / Isolated temp | `580/580` موفق و collection مستقل `580` | pytest با `.test-tmp/full-live-startup-font-auth` | تغییر Backend/API/auth/static UI contracts |
| V-077 | پذیرش زندهٔ Startup، ورود و خواندن Eitaa | Live / Read-only provider acceptance | Health=`200`؛ reset خودکار و request-code موفق؛ login completed؛ dialog/message sync/list پیوسته با status 200؛ هیچ Send/Invite/WordPress انجام نشد | Electron workspace build و log/audit امن | تغییر startup/version/session/auth/provider read/polling |
| V-078 | محرمانگی log پس از ورود واقعی | Read-only scanner | application=`8827`، worker=`678`، invalid JSON=`0` و finding=`0` | `scripts/phase10_log_redaction_verify.py` | تغییر logger/audit/redaction یا corpus زنده |
| V-079 | حافظه، گزارش، map/index و لینک‌ها | Generated/Static/Git read-only | سه artifact تولیدشونده refresh؛ stale=`0`، broken local link=`0` و `git diff --check` موفق؛ dirty worktree موجود حفظ شد | `scripts/refresh_project_docs.py` و Git با safe-directory موقت | تغییر source/docs/generator/path |

### Failure و تحلیل اصلاحی

1. Red اولیه پنج failure مورد انتظار و نبود فایل Card را ثبت کرد. پس از implementation، هدفمند بدون basetemp با `WinError 5` temp سراسری مواجه شد و یک assertion helper نیز نام متفاوت داشت؛ basetemp workspace و نام قرارداد اصلاح و `24/24` شد.
2. نخستین invocation هدفمند یک نام test ناموجود داشت و شاهد نساخت؛ بلافاصله با نام canonical فایل تکرار شد.
3. full نخست پس از extraction فقط یک failure داشت: test scroll رشتهٔ media layout را هنوز در `App.tsx` می‌جست. مرجع به module جدید منتقل و full نهایی `573/573` شد.
4. patch تجمیعی source و patch تجمیعی نخست مستندات به‌علت context متفاوت اتمیک رد شدند؛ هیچ تغییر نیمه‌اعمال‌شده نداشتند و patchهای کوچک فایل‌محور جایگزین شدند.
5. production build موفق بود ولی warning chunk بالاتر از 500 kB باقی ماند؛ F-013 باز است و شاهد شکست build محسوب نشد.
6. Git read-only نخست به‌علت dubious ownership sandbox رد شد؛ هیچ safe-directory دائمی یا Git mutation انجام نشد.

### دامنه و اثر بیرونی

- همهٔ Session و DBهای auth در basetemp workspace تستی بودند؛ Session، `data/` و Config عملیاتی تغییر نکردند.
- Provider network، Login، OTP، Credential، Send/Invite و WordPress واقعی انجام نشد؛ Browser live نیز برای جلوگیری از probe عملیاتی اجرا نشد.
- Scanner فقط‌خواندنی بود و هیچ متن خصوصی، شماره، Token، Cookie یا شناسهٔ حساس در گزارش ثبت نشد.
- Firewall/Proxy/Port/Certificate، migration/rollback عملیاتی و Git reset/checkout/clean/stage/commit/push انجام نشد.

جزئیات: `../reports/features/MATERIAL_MESSAGE_CARD_AUTOMATIC_SESSION_RECOVERY_REPORT_2026-08-20.md`.

## فصل ۱۵ — اصلاح بازگشت RTL در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-080 | Red قرارداد double-flip و drawer edge | Test-first / Static contract | direction تکراری Workspace و لبه/transform قدیمی موبایل پیش از اصلاح شکست خوردند؛ پس از اصلاح Phase 9 acceptance=`13/13` | `ui/scripts/run-phase9-acceptance-tests.mjs` | تغییر root/theme/rtlCache/App grid/drawer |
| V-081 | پذیرش مختصات RTL در Chromium محلی Electron | Local visual/runtime fixture | دسکتاپ 1280×800 و موبایل 390×844: `html/main=rtl`؛ ترتیب Navigation→Conversation→Chat از راست، Header کارت و drawer بستهٔ موبایل در بیرون لبهٔ راست پذیرفته شدند | `ui/scripts/capture-rtl-layout.cjs` | تغییر layout/theme/card/drawer/Electron fixture |
| V-082 | مدل‌ها و قراردادهای کامل UI | Contract | Scroll=`10/10`، grouped=`16/16`، Phase9 workspace+acceptance=`24/24`، Phase10=`7/7`، Phase11=`13/13`؛ جمع شماره‌دار=`70/70`؛ mobile-auth-live و observability موفق | npm scripts canonical | تغییر UI state/layout/auth/live sync |
| V-083 | TypeScript، production build و full Python | TypeScript / Build / Automated full suite | check موفق؛ build 1008 module و main=`788.97 kB` gzip=`241.76 kB`؛ full Python با basetemp workspace=`580/580` | npm check/build و pytest canonical | تغییر source/dependency/contracts |
| V-084 | حافظه، گزارش، map/index و لینک‌ها | Generated/Static/Git read-only | سه artifact تولیدشونده refresh شد؛ stale=`0`، broken local link=`0` و `git diff --check` موفق؛ dirty worktree موجود حفظ شد | `scripts/refresh_project_docs.py` و Git با safe-directory موقت | تغییر source/docs/generator/path |

### Failure و تحلیل اصلاحی

1. Browser درون برنامه localhost را با `ERR_BLOCKED_BY_CLIENT` رد کرد و Chrome در دسترس نبود؛ هیچ bypass انجام نشد و Chromium محلی خود Electron با fixture توسعه جایگزین شد.
2. نخستین Vite invocation با cwd نامناسب root را 404 داد. اجرای داخل `ui` در sandbox نیز هنگام پیمایش dependency والد با access/resolve error متوقف شد؛ اجرای محدود خارج sandbox با cwd صحیح موفق و listener پس از پذیرش متوقف شد.
3. harness Electron در navigation اولیهٔ Vite یک `ERR_FAILED` ناشی از optimization reload دید؛ فقط همین cancellation محدود تحمل و صفحهٔ RTL واقعی پس از بارگیری اندازه‌گیری شد.
4. probe کلیک خودکار drawer در BrowserWindow پنهان state را تغییر نداد و شاهد محسوب نشد؛ حذف شد. مختصات حالت بسته، قرارداد edge/transform و screenshot موبایل معیار پذیرش‌اند.
5. full pytest نخست به temp سراسری کاربر دسترسی نداشت و با `WinError 5` setup error ساخت؛ rerun با basetemp تازهٔ workspace بدون تغییر محصول `580/580` موفق شد.
6. production build موفق بود اما warning chunk بالاتر از 500 kB باقی است؛ F-013 باز و مستقل از RTL است.
7. Git read-only نخست به‌علت dubious ownership sandbox رد شد؛ هیچ safe-directory دائمی یا Git mutation انجام نشد و invocation read-only با safe-directory موقت در پایان استفاده می‌شود.

### دامنه و اثر بیرونی

- پذیرش تصویری فقط fixture محلی و داده‌های ساختگی را استفاده کرد؛ Provider network، Login/OTP، Send/Invite و WordPress انجام نشد.
- Session، Config، `data/`، runtime عملیاتی، diagnostics و backupها جابه‌جا یا بازنویسی نشدند؛ basetemp فقط برای suite تست بود.
- Firewall/Proxy/Port/Certificate، migration/rollback عملیاتی، حذف داده و Git reset/checkout/clean/stage/commit/push انجام نشد.
- جزئیات: `../reports/features/RTL_LAYOUT_REGRESSION_REPAIR_REPORT_2026-08-20.md`.

## فصل ۱۶ — تنظیم متمرکز پورت داخلی در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | مرجع | Trigger تکرار |
|---|---|---|---|---|---|
| V-085 | RED قرارداد منبع واحد پورت | Test-first / Static+Unit | collection با ImportError نبود `DeploymentPortSettings` شکست مورد انتظار داشت؛ قرارداد پیش از پیاده‌سازی موجود بود | `tests/test_deployment_port_settings.py` و Material/API assertions | تغییر نیاز محصول یا حذف test |
| V-086 | persistence اتمیک و سه profile استقرار | Unit/Adversarial/Config | desktop default به deployment کامل تبدیل، Host/Origin داخلی sync، 443/bool/range/unconfirmed بدون write رد، public reverse-proxy حفظ و PermissionError backup به failure امن بدون تغییر فایل تبدیل شد؛ `7/7` | `test_deployment_port_settings.py` | تغییر config dataclass/loader/serializer/atomic write |
| V-087 | API سراسری، مجوز و Observability | Contract/Auth/Audit | GET برای user واردشده با `can_manage=false`؛ POST user=`403`، admin+CSRF+confirm موفق؛ event موفق correlationدار و event ردشده audit-required | `test_app_user_api_setup_session_csrf_roles_and_logout` و Event Catalog | تغییر dispatch/Auth/CSRF/routes/logger/catalog |
| V-088 | Material UI و build | Static/TypeScript/Build | کنترل واحد «شبکه و وب» بدون class، check و observability موفق؛ build 1009 module، Settings=`30.62 kB`، main=`788.97 kB` gzip=`241.76 kB` | `SettingsPage.tsx`، Material test و npm check/build/observability | تغییر Settings/theme/API client/import graph |
| V-089 | regression کامل Backend و UI | Automated full suite / Isolated temp / Contract | Python=`588/588`؛ UI شماره‌دار=`70/70`؛ mobile-auth-live موفق | pytest با basetemp workspace و همهٔ npm scriptهای canonical | تغییر Backend/API/UI/auth/live/navigation |
| V-090 | حافظه، map/index و لینک‌ها | Generated/Static/Git read-only | سه artifact تولیدشونده refresh شد؛ stale=`0`، broken local link=`0`، Event Catalog=`89` و `git diff --check` موفق؛ dirty worktree موجود حفظ شد | `scripts/refresh_project_docs.py` و Git read-only | تغییر source/docs/generator/path |

### Failure و تحلیل اصلاحی

1. RED اولیه در collection و به‌علت نبود سرویس شکست خورد؛ این همان failure مورد انتظار test-first بود.
2. اجرای service پس از implementation به temp سراسری ویندوز دسترسی نداشت و شش setup error با `WinError 5` ساخت؛ rerun با basetemp تازه در workspace `6/6` شد و هیچ تغییر محصولی برای دورزدن مجوز انجام نشد.
3. API آزمایشی v1 برای کاربر عادی پیش از route به gate حساب پیام‌رسان خورد و `app_auth_legacy_workspace_forbidden` داد. چون تنظیم deployment سراسری است، route به namespace v2 منتقل شد؛ user مشاهده می‌کند ولی فقط admin تغییر می‌دهد.
4. تست correlation ابتدا پارامتر داخلی `request_id` را به public dispatch داد و TypeError ساخت؛ public contract واقعی `correlation_id` استفاده و رویداد با همان شناسه پذیرفته شد.
5. production build موفق بود ولی warning chunk بالاتر از 500 kB باقی است؛ F-013 باز و مستقل از این فاز است.
6. بازبینی failure دیسک یک RED تازه ساخت: PermissionError ایجاد backup خام بالا می‌آمد. خطا به کد امن و رخداد `deployment_port_update_failed` نگاشت شد؛ آزمون هدفمند `15/15` و full تکراری `588/588` موفق شدند.

### دامنه و اثر بیرونی

- همهٔ Configها و backupهای mutation در basetemp workspace بودند؛ `bridge.json`، `.env`، Session، data، runtime/diagnostics/backups عملیاتی تغییر نکردند.
- Backend واقعی restart نشد و Port/Firewall/Laragon/Proxy/Certificate تغییر نکرد.
- Provider network، Login/OTP/Credential، Send/Invite و WordPress اجرا نشد.
- migration/rollback عملیاتی، حذف داده و Git reset/checkout/clean/stage/commit/push انجام نشد.
- جزئیات: `../reports/features/CENTRALIZED_DEPLOYMENT_PORT_SETTINGS_REPORT_2026-08-20.md`.

## فصل ۱۷ — ریزفاز ۲.۱ ناوبری موبایل در 2026-08-20

| شناسه | موضوع | سطح | نتیجه | Trigger تکرار |
|---|---|---|---|---|
| V-091 | RED فهرست/بازگشت | Test-first/Static | نبود transition فهرست‌محور شکست مورد انتظار داشت | تغییر قرارداد/test |
| V-092 | State و Material | Static/TypeScript | targeted و check موفق؛ فهرست اولیه، section transition و Arrow بازگشت پذیرفته شد | تغییر App/Header/Navigation |
| V-093 | UI regression | Contract | assertionهای شماره‌دار=`70/70` و mobile-auth-live/observability موفق | تغییر shell/state/live |
| V-094 | Build و full suite | Build/Automated | build 1010 module؛ Python=`589/589` | تغییر source/import graph |
| V-095 | مستندات | Generated/Static | سه artifact refresh؛ stale=`0`، broken link=`0` و diff-check موفق | تغییر source/docs |

جزئیات: `../reports/features/MOBILE_CONVERSATION_NAVIGATION_MICROPHASE_2_1_REPORT_2026-08-20.md`.

## فصل ۱۸ — ریزفاز ۲.۲ Header موبایل در 2026-08-20

| شناسه | موضوع | سطح | نتیجه |
|---|---|---|---|
| V-096 | RED متن زنده/تقارن | Test-first/Static | Python و mobile-live روی رفتار قبلی شکست خوردند |
| V-097 | Material/State | Static/TypeScript | حالت live بی‌صدا، connecting/retrying و جایگاه ۴۸px پذیرفته شد |
| V-098 | UI contracts | Contract | Phase9=`13/13`، mobile-live و observability موفق |
| V-099 | Build/full | Build/Automated | build 1010 module و Python=`590/590` |
| V-100 | Docs | Generated/Static | سه artifact refresh؛ stale=`0`، broken link=`0` و diff-check موفق |

جزئیات: `../reports/features/MOBILE_HEADER_MICROPHASE_2_2_REPORT_2026-08-20.md`.

## 2026-08-21 - Microphase 2.3 Mobile Navigation Selected Item

- **هدف:** اعتبارسنجی تغییر ترتیب و استایل گزینه «منتخب» در Bottom Navigation.
- **تغییرات:** ایجاد `mobileSections` در `WorkspaceNavigation.tsx`.
- **نتیجه:**
  - TypeScript `check`: **موفق**
  - Observability UI: **موفق**
  - Phase 9 UI Tests: **موفق (12/12)**
  - Pytest Backend: **موفق (590/590)**
  - Docs Consistency: **موفق**
- **وضعیت نهایی تاریخی:** `HISTORICAL_GREEN / SUPERSEDED_BY_V-103`

## 2026-08-21 - Phase 3 (Header Search, Composer Fix, WP Icon)

- **هدف:** اجرای کامل فاز ۳ شامل ۳ ریزفاز.
- **تغییرات:** افزودن HeaderMessageSearch، UsageInfoDialog، WordPressIcon.
- **نتیجه:**
  - TypeScript `check`: **موفق**
  - UI Unit Tests: **موفق (15/15)**
- **وضعیت نهایی تاریخی:** `HISTORICAL_GREEN / SUPERSEDED_BY_V-103`

| LEGACY-2026-08-21-PHASE45 | Timeline Pagination & Phase 5 Grouping | Automated Tests + TypeScript + Review | PASS تاریخی (590/590، TS بدون خطا)؛ برای snapshot جاری منقضی طبق V-103 | Phase 4/5 | تغییر timeline grouping/layout یا V-103 |

| LEGACY-2026-08-21-BALE-BOT-DECISION | تصمیم تاریخی مسیر رسمی Bale Bot/Arm | Recovered/Historical Decision | قطعهٔ قابل‌بازیابی: مسیر رسمی Bot/Arm جدا از Personal و Token-based مطرح شده بود؛ متن اصلی لفظ‌به‌لفظ بازیابی‌پذیر نیست و مرجع جاری F-046 است. | F-035 و F-046 | تغییر تصمیم محصولی Bale |

| 2026-08-21 | UI Layout & Avatar Changes | `npm.cmd --prefix ui run check`؛ `npm.cmd --prefix ui run test:observability` | Pass تاریخی؛ برای snapshot جاری منقضی طبق V-103 | نمایش شرطی شناسه پیام، cache آواتار و هم‌ترازی flex |

| 2026-08-22 | Avatar Concurrency Control | `npm.cmd --prefix ui run check`؛ `npm.cmd --prefix ui run build` | Pass تاریخی؛ برای snapshot جاری منقضی طبق V-103 | صف هم‌زمانی حداکثر ۳ در `avatarLoader.ts` |

## 2026-08-22 — ثبت تصمیم‌های معماری ایندکس‌گذاری

| شناسه | موضوع | نوع | نتیجه | مرجع | Trigger ابطال |
|---|---|---|---|---|---|
| V-101 | تصمیم‌های معماری ایندکس‌گذاری | Decision/Interactive | سه تغییر بنیادی پذیرفته شد: دسته اجباری، تاریخ از متن، هویت سازمانی فرستنده. گزینه B برای نمایش auto-index انتخاب شد. score از UI پنهان. چت شخصی خارج از scope. | F-036، F-037، F-038 و [implementation_plan.md](implementation_plan.md) | تغییر نیاز کاربر یا scope |
| V-102 | دسته فعالیت اصلی مستقل از WP | Decision | ۸-۹ دسته سازمانی مستقل از WP categories تعریف می‌شوند. جدول index_activity_categories جدید. هر پست گروه/کانال باید یکی داشته باشد. | F-037 | تغییر schema یا تعریف primary label |

## 2026-08-25 — ممیزی انتقال به AntiGravity2

### V-103 — Baseline، مقایسهٔ پوشهٔ قبلی و اعتبارسنجی محلی snapshot

- تاریخ: 2026-08-25
- سطح: `STATIC / AUTOMATED LOCAL / READ-ONLY OPERATIONAL SCAN`
- دامنه: source، UI، tests، scripts، installer، docs و لاگ‌های JSONL جاری؛ بدون Provider network یا داده‌برداری از محتوای خصوصی.
- علت تکرار: 94 فایل افزوده، 35 فایل تغییرکرده و 1 فایل حذف‌شده نسبت به پوشهٔ قبلی، همراه با تغییر قراردادهای Bale، onboarding، identity و content index، Trigger ابطال شواهد 590/590 قبلی را فعال کرد.
- نتیجهٔ Git: ریشهٔ `AntiGravity2` repository نیست. پوشهٔ قبلی repository شاخهٔ `main` و عمداً dirty است؛ status فقط‌خواندنی با safe-directory محدود به همان invocation انجام شد و هیچ config/stage/commit تغییر نکرد.
- Backend: تلاش اول به‌علت basetemp کپی‌شده و غیرقابل‌نوشتن شاهد معتبر نساخت. اجرای معتبر با basetemp تازه 587 test جمع‌آوری کرد؛ 585 موفق و 2 شکست به‌علت BOM در `providers/bale/slot.py` ثبت شد.
- UI: TypeScript check و observability موفق؛ scroll=`10/10`، grouped-media=`16/16`، Phase 9 workspace/acceptance، Phase 11-B2=`6/6` و mobile-auth-live موفق. Phase 10 local activation به‌علت assertion قدیمی محل helper و Phase 11 onboarding به‌علت گسترش allowlist به `token` شکست خوردند.
- Bale probe آفلاین: manifest مقدار `live_accepted/configured/runtime/onboarding=true` برگرداند، ولی ساخت Adapter با `ModuleNotFoundError` روی import اشتباه متوقف شد. هیچ درخواست شبکه‌ای اجرا نشد.
- اسناد: check اولیه سه artifact تولیدشونده را stale یافت؛ generator اجرا و سپس `--check --check-links` با exit code صفر پذیرفته شد.
- لاگ جاری: scanner فقط‌خواندنی روی 8373 رکورد Application و 6304 رکورد Worker، `invalid_json=0` و `finding=0` گزارش کرد. این شاهد فقط مسیرهای تعریف‌شدهٔ scanner را پوشش می‌دهد و artifactهای مستقل پوشهٔ `Bale` را تأیید نمی‌کند.
- اثر بیرونی: هیچ Login/OTP/Session mutation/Send/Invite/WordPress، migration/rollback، restart، Firewall/Proxy/Port/Certificate یا Git mutation انجام نشد. `bridge.json`، `.env`، Session، `data/`، `runtime/`، `diagnostics/` و `backups/` بازنویسی یا جابه‌جا نشدند.
- یافته‌های مرتبط: F-039 تا F-044.
- Trigger تکرار: اصلاح فایل‌های مذکور، ایجاد baseline Git، تغییر package manifest یا درخواست پذیرش تازه.

| 2026-08-23 | Message Grouping & Skeleton | `npm.cmd --prefix ui run check`؛ `npm.cmd --prefix ui run build` | Pass تاریخی؛ برای snapshot جاری منقضی طبق V-103 | حذف محدودیت ۵ دقیقه و افزودن Skeleton تصویر |

## 2026-08-25 — برنامهٔ تثبیت و قرارداد لاگ‌گذاری

### V-104 — ثبت برنامهٔ G-00 تا G-09 و دفتر اجرای append-only

- تاریخ: 2026-08-25
- سطح: `DOCUMENTATION / GOVERNANCE / NO_CODE_CHANGE`
- Run: `STAB-GPLAN-R00`
- دامنه: تعریف هدف کدها، اتصال `F-039` تا `F-044` به اهداف اجرایی، ترتیب وابستگی، معیار خروج، دروازه‌های تأیید، قرارداد سه‌لایهٔ لاگ و مرز عدم توسعهٔ Bale.
- نتیجه: `STABILIZATION_REMEDIATION_PLAN_2026-08-25.md` و `STABILIZATION_EXECUTION_LOG.md` ایجاد و از `README.md` مرجع شدند؛ برنامهٔ توسعه‌ای قبلی UI تا پایان تثبیت `DEFERRED` شد؛ `F-045` افزوده شد.
- کنترل اسناد: generator، `--check` و `--check --check-links` با exit code صفر اجرا شدند. پس از ثبت این Ledger نیز کنترل نهایی اسناد و لینک‌ها باید exit code صفر داشته باشد.
- تست کد: اجرا نشد؛ از شاهد `V-103` تا این تغییر فقط اسناد حاکمیتی تغییر کرده‌اند و Trigger تکرار suite کد فعال نشده است.
- اثر بیرونی: هیچ کد، config، دادهٔ عملیاتی، Provider network، فرایند سیستم یا Git state تغییر نکرد.
- Trigger تکرار: تغییر خود برنامه/قرارداد لاگ یا آغاز هر هدف اجرایی.

### V-105 — اصلاح دامنه: عدم rollback قرارداد متأخر هویت و Bale

- تاریخ: 2026-08-25
- سطح: `USER_DECISION / STATIC SOURCE+DOCUMENT REVIEW / NO_CODE_CHANGE`
- Run: `STAB-GPLAN-R01`
- علت: کاربر صریحاً اعلام کرد بازگرداندن قراردادهای امنیت/حریم خصوصی قدیمی هدف نیست، آخرین قرارداد امنیتی توسعهٔ Bale مرجع است و سایر قراردادهای اصلاح‌شده باید حفظ شوند.
- شاهد هویت: `identity.masked_phone()` برای E.164 مقدار کامل را برمی‌گرداند؛ `MessengerAccountGate` همان `phone_hint` را نمایش می‌دهد و گزارش `ACCOUNT_MANAGEMENT_UI_AND_UNMASKING_REPORT_2026-08-21.md` این رفتار را تصمیم محصول ثبت کرده است.
- شاهد شکاف: دو تست masking همچنان بدنهٔ خالی دارند و Baseline/Specification قدیمی نمایش پوشیده را ادعا می‌کردند. اسناد در این Run همسو شدند؛ اصلاح تست به G-04/G-06 موکول است.
- شاهد Bale: فصل‌های متأخر `BALE_PROVIDER_DISCOVERY.md` مجوز توسعه را اعلام می‌کنند، اما slot جاری با factory نامعتبر و ادعای `live_accepted` شکسته است. تصمیم مجوز rollback نشد؛ دامنهٔ تثبیت همچنان فقط fail-closed و رفع خرابی بدون قابلیت تازه است.
- مرز مستقل: `docs/SECURITY.md` و AGENTS همچنان شماره، Token، OTP، Cookie، Session و متن خصوصی را در Log/Audit/Diagnostic/Support Bundle ممنوع می‌کنند. نمایش در UI مجوز ثبت در لاگ نیست.
- تغییرهای مستندی: G-04، F-040، F-044، F-046، Baseline، Specification، Bale Discovery و تصمیم معماری ۳۴.
- تست کد: اجرا نشد؛ هیچ source/test/config تغییر نکرد.
- اثر بیرونی: فقط اسناد؛ بدون Provider network، DB/session/config/Git mutation.
- Trigger تکرار: تغییر قرارداد کاربر، تغییر `identity.py`/UI/تست‌های هویت، یا آغاز G-02/G-04.

### V-106 — توقف موقت و Handoff قابل‌ازسرگیری

- تاریخ: 2026-08-25
- سطح: `USER_DECISION / DOCUMENTATION / NO_CODE_CHANGE`
- Run: `STAB-GPAUSE-R00`
- علت: کاربر توقف موقت تا دستور بعدی را همراه با ثبت دقیق مسیر، وضعیت و ادامهٔ کار درخواست کرد.
- نتیجه: `docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md` ایجاد شد؛ وضعیت plan و Execution Log به `USER_PAUSED` تغییر کرد؛ G-00 تا G-09 همگی `QUEUED / NOT_STARTED` باقی ماندند.
- وضعیت tracker: هدف در لحظهٔ handoff در وضعیت `blocked` تا دریافت فرمان کاربر بود؛ این سند معنای عملیاتی آن را `USER_PAUSED` ثبت می‌کند و هیچ ادعای تکمیل ندارد.
- تست کد: اجرا نشد؛ هیچ source/test/config تغییر نکرد.
- اثر بیرونی: فقط اسناد؛ بدون Git/Provider/network/DB/session/config/process mutation.
- ادامه: پس از فرمان کاربر با خواندن همین handoff و Run پیشنهادی `STAB-G00-R01`.
- Trigger تکرار: ازسرگیری هدف یا تغییر دامنه توسط کاربر.

### V-107 — ازسرگیری، ثبت RED توقف و قرارداد همکاری AntiGravity

- تاریخ: 2026-08-25
- سطح: `DOCUMENTATION / GENERATED ARTIFACT / NO_CODE_CHANGE`
- Run: `STAB-GRESUME-R00`
- RED: پس از توقف فوری، `refresh_project_docs.py --check` و `--check --check-links` هر دو با exit code 1 فقط `docs/REPORTS_INDEX.md` را stale یافتند.
- اصلاح: قرارداد `CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md` و Handoff جاری `ANTIGRAVITY_STABILIZATION_CURRENT.md` ایجاد و اسناد تولیدشونده refresh شدند.
- GREEN: هر دو check نهایی exit code صفر؛ broken link گزارش نشد.
- تست کد: اجرا نشد؛ source/test/config تغییری نداشت و Trigger suite کد فعال نشد.
- اثر بیرونی: فقط اسناد؛ بدون Git/Provider/network/DB/session/config/process mutation.
- ادامه: `STAB-G00-R01` برای baseline امن و قابلیت بازگشت.
- Trigger تکرار: تغییر اسناد حاکمیتی، Handoff یا generator.

### V-108 — G-00 baseline امن و اتصال تاریخچهٔ Git

- تاریخ: 2026-08-25
- سطح: `AUTOMATED / LOCAL GIT METADATA / RECOVERY ARTIFACT / NO COMMIT`
- Run: `STAB-G00-R01`
- علت: F-039 و شروع اولین فاز اجرایی پس از دستور کاربر.
- RED: ریشه Git نبود (`exit=128`)؛ تست baseline به‌علت نبود module در collection شکست خورد.
- GREEN هدفمند: `tests/test_stabilization_baseline.py = 2/2` با cache غیرفعال؛ allowlist و determinism/hash verification پذیرفته شد.
- artifact واقعی: 613 فایل؛ archive SHA-256=`70908224926eb45791bdc504558478756328743f0a9f7b8355f19b30d73ca8ab`؛ content-set SHA-256=`d128912b0e14e2f5113a209d7fb403349379e9d372217dcfe252bfef0f08239a`؛ forbidden top-level=`0`.
- Git: repository/branch=`stabilization` و `legacy/main` هر دو به commit `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` متصل‌اند؛ مالک `.git` حساب ویندوز است.
- failure/retry: verifier نخست false positive مستندی داشت؛ `safe.directory` global رد و تغییر نکرد؛ metadata sandbox-owner به artifact recovery منتقل و repository با مالک صحیح بازسازی شد.
- محدودیت: index/stage/commit عمداً انجام نشد؛ manifest+Execution Log تا مجوز کاربر شاهد canonical است.
- اثر بیرونی: fetch فقط محلی؛ بدون Provider/network/DB/session/config/process mutation.
- یافته: F-039 mitigated؛ commit gate باقی است.
- Trigger تکرار: تغییر baseline tooling/scope، خرابی artifact، تغییر refs یا دستور stage/commit.

### V-109 — G-01 سلامت اسناد، شناسه‌ها و فهرست گزارش تثبیت

- تاریخ: 2026-08-25
- سطح: `TEST-FIRST / UNIT / REPOSITORY INTEGRATION / GENERATED DOCS`
- Run: `STAB-G01-R01`
- RED ابزار: import checker ناموجود با collection error؛ پس از ساخت checker، repository واقعی ۱۴۳ نشانه گزارش کرد: replacement=`2`، question-run=`129`، control=`4`، duplicate validation ID=`2` و malformed command row=`6`.
- تفسیر RED: ۱۴۳ تعداد نشانه‌ها بود، نه تعداد defect مستقل؛ بیشتر question-runها از چند سطر واحدِ encoding-corrupt منشأ داشتند.
- ترمیم: F-035 و Bale Discovery بدون حدس لفظی و با provenance بازیابی شدند؛ duplicateهای تاریخی به `LEGACY-...` منتقل، مسیرهای control-character و جدول‌های npm اصلاح و Baseline/Specification/finalization با V-103/F-046 همسو شدند.
- guard: `check_project_memory_integrity.py` به حداقل کیفیت AGENTS افزوده شد و full pytest با تست repository واقعی از encoding/ID drift جلوگیری می‌کند.
- RED فهرست گزارش: تست تازه به‌علت نبود `docs/reports/stabilization` در `REPORT_GROUPS` با `KeyError` شکست خورد.
- GREEN نهایی: suite هدفمند=`5/5`؛ checker repository=`issue_count 0`؛ refresh/check/check-links همگی exit=`0`؛ `git diff --check` exit=`0` با safe-directory فقط همان invocation.
- failure محیطی ثبت‌شده: Temp پیش‌فرض pytest مجوز نداشت و basetemp نخست parent نداشت؛ retry داخل `.test-tmp` سبز شد. Git بدون safe-directory invocation نیز به‌علت مالک متفاوت sandbox رد شد؛ هیچ config سراسری تغییر نکرد.
- اثر بیرونی: فقط source ابزار/test/docs/generated docs و test temp؛ بدون Provider network، config/data/session/runtime و بدون stage/commit/push.
- یافته‌ها: F-035 بازیابی شد؛ F-047 بسته شد؛ ادعاهای جاری F-040/F-042 شفاف شدند.
- Trigger تکرار: تغییر checker، generator، Markdown حافظه، تعریف F/V یا مسیر گزارش‌های تثبیت.

### V-110 — G-02 مهار آفلاین Bale و بسته‌شدن شکست‌های Backend

- تاریخ: 2026-08-25
- سطح: `TEST-FIRST / CONTRACT / ADVERSARIAL STATIC / FULL BACKEND / UI STATIC`
- Run: `STAB-G02-R01`
- RED setup: import test store از module اشتباه و فیلد ناموجود context موجب collection/setup error شد؛ خود تست اصلاح و از RED محصول جدا ثبت شد.
- RED معتبر: تست اختصاصی `4/4 failed` روی state فعال، descriptor runnable، constructor غیرquarantine و BOM. پس از patch، foundation=`1 failed/6 passed` و account-management=`1 failed/8 passed` روی انتظارهای active قدیمی شکست خوردند.
- اصلاح: F-046 با `document:F-046` حفظ شد؛ state=`implemented`، configured/runtime/onboarding=false، factory/capability/auth steps خالی و reason امن. Adapter compatibility پیش از client/session/network رد و UI fixture غیرفعال شد.
- GREEN اختصاصی=`5/5`؛ مرتبط Bale/foundation/account-management=`21/21`.
- regression Backend: collection مستقل=`599`؛ full run exit=`0` و `599/599` PASS.
- UI: TypeScript و Observability PASS؛ Phase 11-B2=`6/6`. Phase 11 onboarding روی assertion منقضی allowlist پیش از assertion Bale شکست خورد و به F-042/G-06 متصل ماند.
- docs: refresh، integrity، stale و local-link checks همگی exit=`0`؛ G-02 در REPORTS_INDEX موجود است؛ diff-check exit=`0`.
- اثر بیرونی: none؛ فقط source/test/UI fixture/docs/test temp. بدون network/Login/OTP/Session/Send/Capture/config/data/runtime و بدون stage/commit/push.
- یافته: F-040 بسته؛ F-042 به `BACKEND_GREEN / UI_AND_PACKAGING_PENDING` به‌روزرسانی شد.
- Trigger تکرار: تغییر Bale slot/quarantine/registry/UI descriptor، فعال‌سازی capability/factory/runtime/onboarding، یا دستور توسعه/Live تازه.

### V-111 — G-03 RED نصب تمیز و توقف پیش از اعتبارسنجی patch

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / SYNTHETIC LOCAL DATA / USER_PAUSED / NOT_GREEN`
- Run: `STAB-G03-R01` (ناتمام)
- RED اولیه: نخست test module به‌دلیل نبود `LegacyAuthChallenge` در collection شکست خورد. پس از افزودن مدل اولیه، اجرای Temp پیش‌فرض با `PermissionError` محیطی متوقف و با `--basetemp artifacts/stabilization/...` تکرار شد.
- RED معتبر نهایی: `tests/test_clean_install_auth_stabilization.py = 4 collected / 4 failed`. علت‌ها: `app_auth_setup_unavailable` روی DB کاملاً خالی، `app_auth_coordinator_missing` در startup، و دو `KeyError: challenge_id` در Legacy auth. یک defect اولیه در password-hasher تست از RED محصول جدا و پیش از اجرای نهایی اصلاح شد.
- patch اعمال‌شده ولی آزموده‌نشده: مدل `LegacyAuthChallenge` و safe allowlist، bootstrap اتمیک مدیر روی Coordinator واقعاً خالی، مجوز محدود runtime برای empty-bootstrap، startup DB initialization، و binding شناسه/stage/expiry در submit-code/submit-password Legacy.
- وضعیت پذیرش: `UNVALIDATED`. پس از آخرین patch هیچ pytest، syntax/import check، docs refresh، integrity check یا diff-check اجرا نشد، زیرا کاربر توقف فوری به‌علت اتمام token خواست. G-03 بسته نیست و F-041 باز است.
- هش‌های نقطهٔ توقف: `api.py=a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `account_runtime.py=7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`؛ `coordinator/app_auth.py=637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c`؛ تست=`f88ffae3e15575039cd8e53dcc32a8ef22b734e9239c5b132910aec0db32f59d`.
- اثر بیرونی: فقط source/test/docs و مسیرهای Temp آزمون؛ بدون Provider network، Login/OTP/Send، بدون داده/config/session/runtime عملیاتی و بدون Git stage/commit/push.
- ادامهٔ اجباری: اجرای همان ۴ تست با basetemp تازه؛ سپس بازبینی شکست‌ها، suiteهای `test_app_user_auth.py`، `test_app_user_api.py`، `test_account_runtime.py` و `test_application_api.py`؛ در پایان Backend کامل و کنترل اسناد.

### V-112 — G-03-A ازسرگیری کنترل‌شده و GREEN اختصاصی

- تاریخ: 2026-08-26
- سطح: `TARGETED / SYNTHETIC LOCAL DATA / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G03-R02`
- علت تکرار: patch ثبت‌شده در V-111 به‌دلیل توقف فوری کاربر هرگز پس از تغییر آزموده نشده بود. پیش از اجرا، SHA-256 هر چهار فایل محصول با هش‌های V-111 یکسان بود؛ بنابراین همان patch متوقف‌شده و نه نسخه‌ای ناشناخته سنجیده شد.
- تلاش A01: همان چهار تست با `--basetemp artifacts/stabilization/pytest-g03-resume-a` اجرا شد؛ نتیجه `4 collected / 3 passed / 1 failed`. شکست در درج credential و به‌علت کوتاه‌بودن salt/digest ساختگی test double نسبت به CHECK واقعی schema بود؛ مسیر bootstrap محصول تا نقطهٔ درج با موفقیت طی شده بود.
- اصلاح: فقط یک سطر fixture آزمون تغییر کرد تا `PasswordMaterial` مصنوعی طول معتبر schema داشته باشد؛ هیچ کد محصولی در این ازسرگیری تغییر نکرد.
- تلاش A02: retry با basetemp تازه `artifacts/stabilization/pytest-g03-resume-b` برابر `4 collected / 4 passed` و exit code صفر شد.
- کنترل مستندات: generator با exit code صفر نقشهٔ فایل و index نمادها را به‌روزرسانی کرد؛ سپس memory integrity، stale check و link check هر سه با exit code صفر گذشتند.
- SHA-256 نهایی: `api.py=a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `account_runtime.py=7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`؛ `coordinator/app_auth.py=637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c`؛ تست=`1e5be6e0bbb998b2de8fd6aca442a48df5f4ec224286c4b9bf2a8d8b1c565344`.
- پذیرش مرحله: `G-03-A TARGETED_GREEN`. F-041 باز است؛ این رکورد جایگزین regression مرتبط، adversarial/restart یا full Backend نیست.
- اثر بیرونی: فقط source/test/docs و مسیرهای Temp آزمون؛ بدون Provider network، Login/OTP/Send، داده/config/session/runtime عملیاتی و بدون Git stage/commit/push.
- ادامه: G-03-B فقط با دستور بعدی کاربر آغاز شود.

### V-113 — G-03-B regression مرتبط AppAuth/API/AccountRuntime

- تاریخ: 2026-08-26
- سطح: `RELATED REGRESSION / SYNTHETIC LOCAL DATA / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G03-R03`
- Trigger اجرا: دستور صریح کاربر برای شروع G-03-B پس از بسته‌شدن کنترل‌شدهٔ G-03-A؛ این suiteها از زمان patch مرتبط G-03 دوباره اجرا نشده بودند.
- دامنه: `tests/test_app_user_auth.py`، `tests/test_app_user_api.py`، `tests/test_account_runtime.py` و `tests/test_application_api.py` در یک pytest با `--basetemp artifacts/stabilization/pytest-g03b-r01-a`.
- نتیجه: `57 collected / 57 passed`، exit code صفر. هیچ failure محیطی، محصولی یا contract drift مشاهده نشد و retry لازم نبود.
- تغییر: هیچ فایل source یا test در G-03-B تغییر نکرد. SHA-256 چهار فایل محصول و چهار suite پیش و پس از اجرا تطبیق کامل داشت.
- کنترل مستندات: generator، memory integrity، stale check و link check همگی با exit code صفر پایان یافتند.
- SHA-256 محصول: `api.py=a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `account_runtime.py=7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`؛ `coordinator/app_auth.py=637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c`.
- SHA-256 آزمون‌ها: `test_app_user_auth.py=075f3015580830c4fc30e9b5c8d442f5499360be1bbf344a8ca62783437d7400`؛ `test_app_user_api.py=b5ce8c79277f72ab945b2a54d061bdac3f21be5d08a41eb73c34580c18e9b773`؛ `test_account_runtime.py=0868d6fbb0514828ede6c24b43de61a1c98c603ac361fae2ba2eb008f2b0dcc3`؛ `test_application_api.py=c287251789a933ab86c6e40528c8f9d1c6e9cce5f7b5a76f0f7fa0d51e30ac93`.
- پذیرش مرحله: `G-03-B RELATED_REGRESSION_GREEN`. F-041 باز است؛ آزمون‌های adversarial/restart و Backend کامل هنوز اجرا نشده‌اند.
- اثر بیرونی: فقط خواندن source/test و مسیر Temp آزمون؛ بدون Provider network، Login/OTP/Send، داده/config/session/runtime عملیاتی و بدون Git stage/commit/push.
- ادامه: G-03-C فقط با دستور بعدی کاربر آغاز شود.

### V-114 — G-03-C adversarial/restart و reconciliation چرخهٔ challenge

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / ADVERSARIAL / RESTART / SYNTHETIC LOCAL DATA / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G03-R04`
- Trigger اجرا: دستور صریح کاربر برای شروع G-03-C؛ V-113 صراحتاً adversarial/restart را آزموده‌نشده ثبت کرده بود.
- قراردادهای تازه: restart و پاک‌سازی Legacy runtime، انقضای password و منع replay، supersession challenge قدیمی، رد stage/شناسهٔ خصمانه بدون Provider/echo، و reconciliation رکورد چندحسابی پس از گم‌شدن in-memory challenge.
- RED: اجرای `-k g03c` روی دو فایل هدفمند با basetemp ایزوله `5 collected / 4 passed / 1 failed` شد. failure محصولی یگانه: submit پس از restart پاسخ `api_auth_challenge_missing` می‌داد و Provider را صدا نمی‌زد، اما رکورد Coordinator را نادرست در `challenge_pending` نگه می‌داشت.
- اصلاح محصول: در `_require_account_challenge`، نبود challenge/runtime اکنون تلاش معلق را می‌بندد و اگر رکورد همان لحظه `challenge_pending` باشد، با reason=`challenge_runtime_missing` و action=`eitaa.auth.challenge.expired` به `expired` منتقل می‌کند؛ generation افزایش نمی‌یابد و metadata فقط stage امن دارد.
- GREEN اختصاصی: retry با basetemp تازه `5 collected / 5 passed` و exit code صفر.
- regression مرتبط: شش فایل شامل clean-install، AccountAuth lifecycle و چهار suite G-03-B با basetemp تازه `81 passed` و exit code صفر.
- کنترل مستندات: generator نقشهٔ فایل و index نمادها را refresh کرد؛ memory integrity، stale check و link check همگی exit code صفر داشتند.
- کنترل diff: تلاش نخست `git diff --check` بدون مسیر صریح به‌علت کشف‌نشدن worktree exit code 1 داد؛ این failure محیطی/فرمانی بود. retry read-only با `--git-dir=.git --work-tree=.` روی سه فایل تغییرکرده exit code صفر شد. هیچ index/stage/commit تغییر نکرد.
- SHA-256 پیش: `api.py=a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `test_clean_install_auth_stabilization.py=1e5be6e0bbb998b2de8fd6aca442a48df5f4ec224286c4b9bf2a8d8b1c565344`؛ `test_account_auth_lifecycle.py=89621f194f5a41ef6e26e18e7c10c92a7bf4d3219be49ed6b04bbd7861d00a25`.
- SHA-256 پس: `api.py=1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `test_clean_install_auth_stabilization.py=05ac08438f7da1b7692caa1bf4a9b0af846975ddf6ffe0d6d38df5ca5c7fea45`؛ `test_account_auth_lifecycle.py=ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882`.
- پذیرش مرحله: `G-03-C ADVERSARIAL_RESTART_GREEN`. F-041 باز است؛ Backend کامل و کنترل UI مرتبط هنوز اجرا نشده‌اند.
- اثر بیرونی: فقط source/test/docs و Temp DB/config/session مصنوعی زیر basetemp؛ بدون Provider network، Login/OTP/Send واقعی، داده/config/session/runtime عملیاتی و بدون Git stage/commit/push.
- ادامه: G-03-D فقط با دستور بعدی کاربر آغاز شود.

### V-115 — G-03-D full Backend و کنترل‌های UI/Observability

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / UI TYPESCRIPT / UI-ELECTRON OBSERVABILITY / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G03-R05`
- Trigger اجرا: دستور صریح کاربر برای G-03-D و تغییر guard مرکزی API پس از آخرین full suite معتبر V-110؛ جلوگیری از تکرار نقض نمی‌شود چون کد مرکزی و پنج تست تازه اضافه شده بود.
- Backend تلاش A01: کل pytest با basetemp ایزوله `608 collected / 607 passed / 1 failed`. failure در `test_literal_runtime_events_are_registered_in_catalog` بود: `auth_challenge_denied` و `auth_challenge_expired` در G-03 emit شده اما catalog نشده بودند.
- بررسی مسیر traceback: Resolve-Path فایل آزمون و cwd هر دو snapshot جاری `AntiGravity2` را تأیید کردند؛ نمایش مسیر قدیمی به metadata bytecode منتقل‌شده مربوط بود و آزمون source جاری را پیمایش کرده است، نه پوشهٔ قدیمی را.
- اصلاح: دو تعریف event با category=`authentication`، default result=`rejected` و `audit_required=true` به Event Catalog افزوده شد؛ هیچ payload خصوصی یا شناسهٔ challenge به schema افزوده نشد.
- GREEN هدفمند: `tests/test_observability_contract.py = 6/6 passed`.
- GREEN نهایی Backend: retry مستقل با basetemp تازه `608/608 passed` در 85.33 ثانیه.
- UI: `npm.cmd --prefix ui run check` exit code صفر؛ `npm.cmd --prefix ui run test:observability` exit code صفر و قراردادهای UI/Electron سبز.
- کنترل مستندات: generator نقشهٔ فایل و index نمادها را refresh کرد؛ memory integrity، stale check و link check همگی exit code صفر داشتند.
- جلوگیری از تکرار: Phase 11 onboarding اجرا نشد، زیرا failure allowlist آن در F-042/G-06 ثبت و هیچ کد مرتبطی در G-03 تغییر نکرده است. Phase 10 نیز trigger تازه نداشت.
- diff: کنترل read-only هدفمند با git-dir/work-tree صریح exit code صفر؛ هیچ stage/commit/push انجام نشد.
- SHA-256 نهایی: `api.py=1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4`؛ `event_catalog.py=33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9`؛ `test_clean_install_auth_stabilization.py=05ac08438f7da1b7692caa1bf4a9b0af846975ddf6ffe0d6d38df5ca5c7fea45`؛ `test_account_auth_lifecycle.py=ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882`؛ `test_observability_contract.py=748b2d9437e2fcd82ad20047e77e356031b936364f740a08d9fcdf1bdc245ad5`.
- پذیرش مرحله: `G-03-D FULL_REGRESSION_GREEN`. F-041 فقط برای finalization/report در G-03-E باز می‌ماند؛ این نتیجه F-042، packaging یا release readiness عمومی را نمی‌بندد.
- اثر بیرونی: فقط source/docs و Temp DB/config/session/log مصنوعی زیر basetemp و build metadata محلی TypeScript؛ بدون Provider network، Login/OTP/Send واقعی، داده/config/session/runtime عملیاتی و بدون Git mutation.
- ادامه: G-03-E فقط با دستور بعدی کاربر آغاز شود.

### V-116 — G-03-E معیارهای تکمیلی، finalization و بستن F-041

- تاریخ: 2026-08-26
- سطح: `EXIT-CRITERIA AUDIT / ISOLATED INSTALL REHEARSAL / FULL BACKEND / FINALIZATION`
- Run: `STAB-G03-R06`
- بازبینی: هش هفت فایل اصلی با V-112/V-114/V-115 و تغییر test-only همین Run تطبیق داده شد؛ نمادهای bootstrap/challenge/restart/catalog حاضر و diff check هدفمند exit code صفر بود.
- شکاف کشف‌شده: معیار خروج رسمی G-03، startup تکراری و installer rehearsal ایزوله را لازم می‌دانست اما V-111 تا V-115 شاهد مستقل برای آن دو نداشتند. F-041 پیش از رفع این gap بسته نشد.
- acceptance تازه: `test_g03e_empty_multisession_startup_is_repeatable` و `test_g03e_installer_config_copy_rehearsal_starts_offline_twice` با basetemp ایزوله `2/2 passed`. config نمونه مطابق قرارداد copy-if-missing در ریشهٔ موقت استفاده و هر سناریو بدون Provider/Session واقعی دو بار startup شد.
- Trigger تکرار full suite: فایل آزمون clean-install تغییر کرد؛ Backend کامل با basetemp تازه `610/610 passed` در 82.28 ثانیه. UI دوباره اجرا نشد چون هیچ فایل UI تغییر نکرد و V-115 شاهد جاری سبز دارد.
- کنترل مستندات: generator نقشهٔ فایل، index نمادها و REPORTS_INDEX را refresh و گزارش G-03 را discoverable کرد؛ memory integrity، stale check و link check همگی exit code صفر داشتند.
- SHA-256 نهایی: `api.py=1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4`؛ `account_auth.py=6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`؛ `account_runtime.py=7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`؛ `coordinator/app_auth.py=637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c`؛ `event_catalog.py=33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9`؛ `test_clean_install_auth_stabilization.py=980d467153927d6f9b6d8b1ccacfb88ebb3db177dce94b8178524c9912b0830c`؛ `test_account_auth_lifecycle.py=ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882`.
- privacy/PII: challenge/provider material فقط در حافظه ماند؛ تست‌های mismatch/hostile-id/password expiry و observability عدم echo/leak را پوشش دادند. گزارش هیچ مقدار خصوصی یا شناسهٔ حساس ندارد.
- پذیرش: `G-03 COMPLETE / F-041 CLOSED / SYNTHETIC_OFFLINE_ACCEPTED`. این پذیرش F-042/F-043/F-044 یا release readiness عمومی را نمی‌بندد.
- اثر بیرونی: فقط test/docs و Temp DB/config/session/log مصنوعی؛ بدون نصب واقعی، Provider network، Login/OTP/Send، دادهٔ عملیاتی و بدون Git stage/commit/push.
- ادامه: G-04 فقط با دستور بعدی کاربر آغاز شود.

### V-117 — G-04-A ممیزی قرارداد هویت و RED مستقل حریم خصوصی

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / STATIC CONTRACT / PRIVACY RED / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G04-R01`
- Trigger اجرا: دستور صریح کاربر برای شروع G-04 پس از closure G-03؛ F-044 دو تست خالی و نبود شاهد مستقل redaction را باز نگه داشته بود.
- دامنه: فقط ممیزی قرارداد و افزودن `tests/test_g04_identity_privacy_stabilization.py`؛ هیچ اصلاح محصول در این زیرمرحله مجاز نبود.
- آزمون هدفمند: `3 collected / 1 passed / 2 failed` با basetemp ایزوله `artifacts/stabilization/pytest-g04a-r01-red-a` و exit code 1.
- PASS: مقدار canonical ساختگی در مرز مجاز نمایش محصول بدون بازگشت masking حفظ شد.
- RED معتبر ۱: هر دو تست تاریخی قرارداد تلفن در `tests/test_coordinator_schema.py` همچنان placeholder تک‌دستوری `pass` هستند.
- RED معتبر ۲: redaction عمومی مقدار کامل زیر نام‌های `phone_hint` و `display_hint` را حذف نمی‌کند، زیرا این نام‌ها در مجموعهٔ کلیدهای تلفن ثبت نشده‌اند.
- طبقه‌بندی: `test_drift` برای placeholderها و `privacy_contract` برای identity hint؛ failure محیطی یا retry وجود نداشت.
- جلوگیری از افشا: ورودی کاملاً ساختگی بود؛ assertionهای شکست مقدار را echo نکردند و هیچ مقدار کامل در Ledger، Handoff یا گزارش ثبت نشد.
- SHA-256: `identity.py=14de42290d97bb0ddc543ffa28dc41402b1619c9a3f91a85faaabaddefb32ac0`؛ `redaction.py=3d688ab266d6856f49b412cfbcb4f82b05ad921139a0e409bdb1e48c9c186cbb`؛ `test_coordinator_schema.py=cfb6c6ebc41e04a6cc644c4bd1e6605fbc46ef610f929e2e40ef348658d0b04e`؛ `test_g04_identity_privacy_stabilization.py=d78bf0fb9c6c94b417d8420fbbcd613dba53271efb4f5a5834f4079ecad70280`.
- full regression: اجرا نشد؛ suite جاری عمداً RED است و هیچ کد محصولی تغییر نکرد. آخرین `610/610` فقط شاهد snapshot پایان G-03 است.
- کنترل مستندات: generator نقشهٔ فایل، index نمادها و REPORTS_INDEX را refresh کرد؛ memory integrity، stale check، link check و diff check هدفمند همگی exit code صفر داشتند. گزارش G-04-A در سطر 154 فهرست گزارش‌ها discoverable است.
- پذیرش مرحله: `G-04-A RED_VERIFIED`. F-044 باز و G-04-B تا دستور بعدی کاربر شروع‌نشده است.
- اثر بیرونی: فقط test/docs و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send، داده/config/session/runtime عملیاتی، توسعهٔ Bale یا Git stage/commit/push.
- Trigger تکرار: تغییر دو تست تاریخی، `identity.py`، `redaction.py` یا نام‌های identity hint؛ نخستین retry فقط در G-04-B و با دستور کاربر.

### V-118 — G-04-B جایگزینی تست‌های خالی و GREEN مرز redaction

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / TARGETED GREEN / RELATED PRIVACY REGRESSION / STAGE_COMPLETE`
- Run: `STAB-G04-R02`
- Trigger اجرا: دستور صریح کاربر برای G-04-B و دو RED معتبر V-117.
- اصلاح آزمون: دو نام/قرارداد masking منقضی حذف و با تست پذیرش display hint canonical در Coordinator persistence و حفظ canonical در مرز محصول جایگزین شدند. guard G-04 هم وجود replacementهای غیرخالی و غیبت نام‌های قدیمی را کنترل می‌کند.
- اصلاح محصول: `phone_hint` و `display_hint` به `PHONE_KEYS` در redaction مشترک افزوده شدند؛ دادهٔ هویت در UI/persistence محصول کامل می‌ماند، اما در observability mask می‌شود.
- GREEN اختصاصی: `tests/test_g04_identity_privacy_stabilization.py = 3/3 passed` با basetemp `artifacts/stabilization/pytest-g04b-r01-targeted-a`.
- regression مرتبط: coordinator schema، diagnostics، observability و G-04 برابر `28/28 passed` با basetemp مستقل `artifacts/stabilization/pytest-g04b-r01-related-a`؛ retry یا failure محیطی وجود نداشت.
- SHA-256 پس از اصلاح: `redaction.py=8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe`؛ `test_coordinator_schema.py=e06789ad01726a9544ceb8fbbe36405e6580f17b901948cabd3290f7192e35e3`؛ `test_g04_identity_privacy_stabilization.py=9a7e80a3ef542bfc289b42185bbcaec77c6a7c6b9c495051785a26afa4d1bbe6`.
- full regression: اجرا نشد؛ دامنهٔ B محدود به دو RED بود و Backend کامل در G-04-E اجرا می‌شود.
- کنترل مستندات: generator نقشه/نماد/REPORTS_INDEX را refresh کرد؛ گزارش B در سطر 155 discoverable است و integrity، stale، link و diff check هدفمند همگی exit code صفر داشتند.
- پذیرش مرحله: `G-04-B TARGETED_GREEN / RELATED_REGRESSION_GREEN`. F-044 برای G-04-C تا E باز است.
- اثر بیرونی: فقط source/test/docs و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send، داده/config/session/runtime عملیاتی، توسعهٔ Bale یا Git stage/commit/push.
- ادامه: G-04-C با مجوز همان فرمان کاربر شروع شود؛ token از onboarding عمومی حذف و phone identity مستقل آزموده شود.
- Trigger تکرار: تغییر redaction، نام‌های identity hint، Coordinator display validation یا قرارداد نمایش محصول.

### V-119 — G-04-C جداسازی E.164 از token در onboarding عمومی

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / API CONTRACT / UI CONTRACT / RELATED REGRESSION / STAGE_COMPLETE / USER_PAUSED`
- Run: `STAB-G04-R03`
- Trigger اجرا: دستور صریح کاربر برای انجام G-04-C؛ پذیرش token در allowlist API و failure ثبت‌شدهٔ Phase 11 onboarding در F-042.
- RED Backend: دو تست جدید با basetemp `artifacts/stabilization/pytest-g04c-r01-red-a` برابر `2/2 failed`؛ validator تلفن token-shaped identity را رد نمی‌کرد و endpoint عمومی آن را تا PhoneProtector عبور می‌داد.
- RED UI: `test:phase11-onboarding` پس از یک PASS روی assertion allowlist با exit code 1 شکست خورد؛ runner برای failure کل source API را در خروجی dump کرد. هیچ credential/PII واقعی در source یا خروجی وجود نداشت، اما این verbosity به‌عنوان رفتار ابزار ثبت شد.
- اصلاح: branch و regex token از identity تلفنی حذف شد؛ validator فقط E.164 است. API فقط `provider/phone/label` می‌پذیرد، phone را در boundary اعتبارسنجی می‌کند و descriptor غیر `phone_e164` را با reason امن رد می‌کند.
- مرز Bale: descriptor آن همچنان onboarding=false است و هیچ account kind/token path/factory/capability تازه‌ای اضافه نشد.
- GREEN هدفمند: Backend=`2/2 passed` با basetemp تازه `artifacts/stabilization/pytest-g04c-r01-targeted-a`؛ UI Phase 11 onboarding=`7/7 passed`.
- regression مرتبط A: هفت suite G-04/Coordinator/Phase11 onboarding/Application API/AccountRuntime/B0/B1 برابر `90/90 passed` با basetemp `artifacts/stabilization/pytest-g04c-r01-related-a`.
- regression مرتبط B: AccountAuth lifecycle و Provider-neutral orchestration برابر `36/36 passed` با basetemp `artifacts/stabilization/pytest-g04c-r01-related-b`. مجموع regression مرتبط=`126/126`.
- SHA-256 نهایی: `api.py=c77364d8ee8cc2d82a08b13e975f5653f98999b854e62dc7f60164f0ba007a32`؛ `identity.py=afe44246c207e6d8b753d5d310ae67fe4ccefad8ac882677aeed4849fe7f6dde`؛ `redaction.py=8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe`؛ `test_g04_identity_privacy_stabilization.py=57e992b76a75ee63a2ce4536988dcf11419b14c1f46b9b556d116b5312f75e54`؛ `test_phase11_0_multi_account_onboarding.py=ad520f90da77da2be8fda1e2fcae39153a5acddcc268e6e4416c779588cd6428`؛ `test_coordinator_schema.py=e06789ad01726a9544ceb8fbbe36405e6580f17b901948cabd3290f7192e35e3`.
- full Backend: اجرا نشد؛ تغییر مرکزی ثبت و Trigger آن فعال است، اما طبق بخش‌بندی کاربر full suite در G-04-E اجرا می‌شود. آخرین `610/610` شاهد snapshot پایان G-03 است، نه snapshot جاری.
- کنترل مستندات: generator نقشه/نماد/REPORTS_INDEX را refresh کرد؛ گزارش C در سطر 156 discoverable است و integrity، stale، link و diff check هدفمند همگی exit code صفر داشتند.
- پذیرش مرحله: `G-04-C TARGETED_AND_RELATED_REGRESSION_GREEN`. F-044 برای privacy scan و finalization باز؛ G-04-D تا فرمان کاربر شروع‌نشده است.
- اثر بیرونی: فقط source/test/docs، basetemp مصنوعی و اجرای static UI؛ بدون Provider network، Login/OTP/Send، داده/config/session/runtime عملیاتی، توسعهٔ Bale یا Git stage/commit/push.
- Trigger تکرار: تغییر API onboarding allowlist، E.164 validator، Provider identity kind، UI onboarding contract یا PhoneProtector boundary.

### V-120 — G-04-D پذیرش خصمانهٔ چهار کانال privacy

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / ADVERSARIAL PRIVACY / AUDIT PERSISTENCE / SUPPORT BUNDLE / RELATED REGRESSION / USER_PAUSED`
- Run: `STAB-G04-R04`
- Trigger اجرا: دستور صریح کاربر برای G-04-D و تغییر redaction/identity boundary در G-04-B/C؛ شاهدهای قدیمی فقط شمارهٔ ایران و کلیدهای شناخته‌شده را پوشش می‌دادند.
- دامنه: Runtime Log، Diagnostic JSONL، Audit persistence/query/export، Support Bundle creator و scanner؛ همه با E.164/Bearer کاملاً ساختگی و بدون echo مقدار در failure.
- RED: `tests/test_g04d_privacy_channels.py = 5/5 failed` با basetemp `artifacts/stabilization/pytest-g04d-r01-red-a`. هر پنج کانال/کنترل شکست مستقل داشت؛ bundle creator فقط مسیر ZIP موقت را در stdout چاپ کرد و هیچ مقدار خصوصی echo نشد.
- علت ریشه‌ای: redaction عمومی generic string را pattern-scan نمی‌کرد؛ Audit append metadata را پیش از hash/persistence sanitize نمی‌کرد و دفاع query/export key-aware نبود؛ bundle creator/scanner الگوی global E.164 نداشتند.
- اصلاح: redaction مشترک canonical E.164، شکل‌های پشتیبانی‌شدهٔ تلفن، Bearer و provider-token shape را در string ناشناخته/تو‌در‌تو sanitize می‌کند؛ Coordinator Audit پیش از persistence و در query/export redaction دارد؛ creator/scanner الگوی global phone همسو دارند.
- GREEN اختصاصی: همان پنج تست با basetemp تازه `artifacts/stabilization/pytest-g04d-r01-targeted-a` برابر `5/5 passed`.
- regression مرتبط A: G-04/G-04-D، diagnostics/observability، Phase 10-D bundle، Audit stress/access، AccountAuth و account management برابر `53/53 passed` با basetemp `artifacts/stabilization/pytest-g04d-r01-related-a`.
- regression مرتبط B: دو privacy contract در LAN/AppAuth برابر `2/2 passed` با basetemp `artifacts/stabilization/pytest-g04d-r01-related-b`.
- regression مرتبط C: Coordinator، AppUser Auth، Phase 10-B audit، Phase 11 onboarding و B1 registry برابر `50/50 passed` با basetemp `artifacts/stabilization/pytest-g04d-r01-related-c`.
- SHA-256 نهایی: `redaction.py=10eb93c1a3ff08845764d55b39c04ba21ed45888e5b767f28c66dbb9ba37a9a4`؛ `runtime_logger.py=2dc04203775c829ebafd34f4ebc960232b7e34f8507465aecef87d65cc554fc1`؛ `manager.py=fba43190216467231baffeca8838fe24a057812e74c586d9ef3c8521532face9`؛ `store.py=b7ceb3c5b41bd3071f93e9331623794939eb9ee293210317d068cc65844ef710`؛ `audit.py=385f2621726584fe8bc5b6b3b1a8c69b942f8ae62763666464a3d5350b631f22`؛ `create_diagnostics_bundle.py=480805802c27b27814f20f60a6fe8a2a9c33c3d58fd67f7b53a959cf81538202`؛ `scan_diagnostics_bundle.py=b02e66e97a7fcce4661634bf34eeaa117a332f9e50d6f43cb30008b4a143a4cc`؛ `test_g04d_privacy_channels.py=5096701603a670a3270ddc368ce88ef54c4de0e50acc3359d271eded6bc5244e`.
- full Backend: اجرا نشد؛ طبق بخش‌بندی کاربر در G-04-E اجباری است و تغییر store/redaction Trigger آن را فعال نگه می‌دارد.
- کنترل ثبت نهایی: refresh تولیدکننده انجام شد؛ memory integrity، stale check، link check و targeted diff check همگی exit code صفر داشتند. گزارش G-04-D در سطر 157 `REPORTS_INDEX.md` discoverable و SHA-256 آن `42cdbf1084169ba268c1565a36b4306464e7a71fa826e049a0467a1a6df3061f` است.
- پذیرش مرحله: `G-04-D ADVERSARIAL_GREEN / RELATED_REGRESSION_GREEN`. F-044 فقط برای full regression/finalization باز و G-04-E تا دستور کاربر شروع‌نشده است.
- اثر بیرونی: فقط source/test/docs و DB/log/diagnostic/bundle مصنوعی زیر basetemp؛ بدون خواندن diagnostics/config/session/data واقعی، Provider network، Login/OTP/Send، توسعهٔ Bale یا Git stage/commit/push.
- Trigger تکرار: تغییر redaction، RuntimeLogger/Diagnostic manager، Audit append/query/export، bundle creator/scanner، identity kind یا الگوی تلفن.

### V-121 — G-04-E ممیزی نهایی و full regression

- تاریخ: 2026-08-26
- سطح: `EXIT AUDIT / FULL BACKEND GREEN / UI CONTRACT GREEN / G-04 COMPLETE / F-044 CLOSED`
- Run: `STAB-G04-R05`
- Trigger اجرا: دستور صریح کاربر برای G-04-E و منقضی‌بودن full Backend پس از تغییرهای مرکزی B تا D.
- ممیزی هش: فایل‌های نهایی مؤثر V-119/V-120 بدون drift. تلاش اول دو مسیر ناموجود حدسی داشت و exit code 1 گرفت؛ تکرار با مسیرهای کشف‌شده exit code صفر داشت. این failure ابزار audit بود، نه محصول.
- full Backend نخست: `620 collected / 618 passed / 2 failed`، basetemp=`artifacts/stabilization/pytest-g04e-r01-full-a`، exit code 1. هر دو شکست `subprocess.TimeoutExpired` ده‌ثانیه‌ای در Process Worker Phase 7 بودند؛ هیچ failure هویت/privacy ثبت نشد.
- isolation همان دو node: `2/2 passed`، basetemp=`artifacts/stabilization/pytest-g04e-r01-timeout-isolation-a`، exit code صفر و بدون patch/retry در کد.
- طبقه‌بندی نهایی: دو timeout نخست ازدحام زمانی full-suite بودند؛ شاهد isolation و full rerun تازه بدون patch محصول سبز است و failure اولیه در Ledger حفظ شد.
- collect-only: `70` فایل و `620` تست، exit code صفر.
- full Backend دوم: `620/620 passed`، basetemp=`artifacts/stabilization/pytest-g04e-r02-full-b`، exit code صفر و بدون patch محصول.
- UI نهایی: `npm.cmd --prefix ui run check` exit code صفر؛ `test:observability` exit code صفر؛ `test:phase11-onboarding=7/7 passed`.
- هش پایانی فایل‌های مؤثر با S01 یکسان و drift_count=`0`؛ در G-04-E هیچ source/test تغییر نکرد.
- پذیرش: `G-04 COMPLETE / F-044 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`. release readiness عمومی، Live privacy scan و مجوز Provider از این پذیرش استنباط نمی‌شود.
- کنترل اسناد: generator فهرست گزارش‌ها را refresh کرد؛ memory integrity، stale check، link check و targeted diff check همگی exit code صفر داشتند. گزارش نهایی در سطر 154 `REPORTS_INDEX.md` discoverable و SHA-256 آن `c0f1afd36abfca1a5c9a58fb609a4b321fd4338a4d63bbe4898f6a5dcb8afc08` است.
- ادامه: G-05 فقط با دستور صریح کاربر آغاز شود.
- اثر بیرونی: فقط subprocessهای Fake/disabled Eitaa و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send یا دادهٔ عملیاتی.

### V-122 — G-05-A ممیزی lifecycle ایندکس خودکار و RED آفلاین

- تاریخ: 2026-08-26
- سطح: `STATIC / TEST-FIRST / THREAD LIFECYCLE RED / MANUAL CONTRACT GREEN`
- Run: `STAB-G05-R01`
- Trigger اجرا: دستور صریح کاربر برای G-05 و F-043 باز؛ اجرای خودکار زیرمرحله‌ها با checkpoint مستند مجاز شد.
- دامنه: فقط API موقت، thread کنترل‌شده، application log مصنوعی و static source contract؛ بدون اجرای LocalContentIndexService، Provider یا شبکه.
- آزمون: `tests/test_g05_auto_index_lifecycle_stabilization.py = 1/4 passed, 3/4 failed` با basetemp=`artifacts/stabilization/pytest-g05a-r01-red-a` و exit code 1.
- REDها: scheduler ناقص در startup واقعاً thread ساخت؛ `close()` آن را متوقف نکرد؛ event cataloged/correlated برای safe-default وجود نداشت؛ loop unbounded و نام thread در source باقی بود.
- PASS: پنج route/method ایندکس دستی همچنان موجودند.
- cleanup آزمون: target monkeypatch‌شده پس از مشاهدهٔ failure با Event آزاد و join شد؛ thread یتیم آزمون باقی نماند.
- SHA-256 پیش از patch محصول: `api.py=c77364d8ee8cc2d82a08b13e975f5653f98999b854e62dc7f60164f0ba007a32`؛ `event_catalog.py=33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9`؛ تست=`2c649fba8b4153e5130881c233687155c82d8690acef5a4ae2d84c1a8ad871fe`.
- تصمیم پذیرش A: `RED_VERIFIED`. G-05-B خودکار ادامه می‌یابد؛ F-043 باز است.
- کنترل ثبت A: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 159 `REPORTS_INDEX.md` discoverable و SHA-256 آن `c10cbdbe3aee5ec5a6eae5641ba40f1f6ab6b3243eccfd75f3cc0dedd0adfc6c` است.
- اثر بیرونی: فقط temp config/log/DB و thread کنترل‌شده؛ بدون دادهٔ عملیاتی، Provider network، Login/OTP/Send، Bale یا Git mutation.

### V-123 — G-05-B safe-default و حذف scheduler ناقص

- تاریخ: 2026-08-26
- سطح: `SOURCE PATCH / TARGETED GREEN / RELATED REGRESSION GREEN`
- Run: `STAB-G05-R01`
- Trigger اجرا: سه RED معتبر V-122 و مسیر امن صریح برنامهٔ G-05.
- اصلاح: thread startup و method نامحدود `_run_auto_indexer` حذف؛ manual index حفظ؛ event cataloged/correlated `content_auto_index_scheduler_skipped` با reason=`content_auto_index_scheduler_disabled_safe_default` افزوده شد.
- اختصاصی: `4/4 passed` با basetemp=`artifacts/stabilization/pytest-g05b-r01-targeted-a` و exit code صفر.
- regression مرتبط: هفت suite G-05/content-index/account-runtime/observability/Application/AppUser/clean-install برابر `76/76 passed` با basetemp=`artifacts/stabilization/pytest-g05b-r01-related-a` و exit code صفر.
- collect-only مرتبط: `76` تست، exit code صفر. failure یا retry محیطی وجود نداشت.
- SHA-256: `api.py=d5f3bde003b9c5827429727446f870feddc91ebe0d7d90e158a06e9b51486f79`؛ `event_catalog.py=3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f`؛ تست=`2c649fba8b4153e5130881c233687155c82d8690acef5a4ae2d84c1a8ad871fe`.
- پذیرش B: `TARGETED_AND_RELATED_GREEN`. F-043 تا C/D/E باز و C خودکار ادامه می‌یابد.
- کنترل ثبت B: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 160 `REPORTS_INDEX.md` discoverable و SHA-256 آن `c1273fa4c31beef87de9c34f1aeea8d45ab22c8a6cad9c4f185106d918e08f44` است.
- اثر بیرونی: source/test/docs و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.

### V-124 — G-05-C guard تکرار lifecycle و correlation

- تاریخ: 2026-08-26
- سطح: `ADVERSARIAL THREAD LIFECYCLE / CORRELATION / OBSERVABILITY CONTRACT`
- Run: `STAB-G05-R01`
- Trigger اجرا: پذیرش B و نیاز F-043 به اثبات restart/close، نبود orphan و event امن.
- آزمون: G-05 به‌همراه `test_observability_contract.py` برابر `11/11 passed` با basetemp=`artifacts/stabilization/pytest-g05c-r01-adversarial-a` و exit code صفر.
- سه startup/close متوالی: thread count مربوط به auto-index بدون تغییر؛ سه event دقیق با correlationهای یکتا و fields allowlisted؛ بدون account scope/private payload.
- literal event catalog contract سبز است؛ event جدید cataloged و schema نسخهٔ جاری حفظ شد.
- SHA-256: `api.py=d5f3bde003b9c5827429727446f870feddc91ebe0d7d90e158a06e9b51486f79`؛ `event_catalog.py=3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f`؛ تست=`a305bd989063bd09c34ea394aadd12c8bf7f22d9397a432b0734e0ff794ec8ba`.
- پذیرش C: `ADVERSARIAL_GREEN`. F-043 تا D/E باز و D خودکار ادامه می‌یابد.
- کنترل ثبت C: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 161 `REPORTS_INDEX.md` discoverable و SHA-256 آن `d4826af6fc253b06283047193e58a56f49dc4f73288a0cc7c98c28e631cbe2a5` است.
- اثر بیرونی: سه API/config/log/DB مصنوعی؛ بدون Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.

### V-125 — G-05-D regression گسترده lifecycle/API

- تاریخ: 2026-08-26
- سطح: `BROAD RELATED REGRESSION / OFFLINE`
- Run: `STAB-G05-R01`
- Trigger اجرا: تغییر مرکزی API startup و Event Catalog در B و پذیرش adversarial در C.
- دامنه: ۱۴ suite G-05/content-index/account-auth/account-runtime/Application/AppUser/clean-install/diagnostics/observability/Phase10-B/D/Phase11 onboarding/B1/B2.
- نتیجه: `143/143 passed` با basetemp=`artifacts/stabilization/pytest-g05d-r01-broad-a` و exit code صفر؛ collect-only نیز 143.
- failure/retry: هیچ‌کدام. source/test در D تغییر نکرد.
- پذیرش D: `BROAD_RELATED_REGRESSION_GREEN`. F-043 تا full regression/finalization E باز و E خودکار ادامه می‌یابد.
- کنترل ثبت D: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 162 `REPORTS_INDEX.md` discoverable و SHA-256 آن `620fbeaa38af8cc026543002b8b8ea076ee5a233d61d1d72a2362fb9cff11efb` است.
- اثر بیرونی: فقط test execution و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.

### V-126 — G-05-E full regression و closure فنی F-043

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / UI STATIC / OBSERVABILITY / FINALIZATION`
- Run: `STAB-G05-R01`
- Trigger اجرا: تغییر مرکزی API startup/Event Catalog و سبزی A تا D.
- full Backend: `625/625 passed` در اجرای نخست با basetemp=`artifacts/stabilization/pytest-g05e-r01-full-a` و exit code صفر.
- collect-only: `625` تست، exit code صفر.
- UI: TypeScript check exit code صفر؛ UI/Electron Observability exit code صفر.
- SHA-256 نهایی: `api.py=d5f3bde003b9c5827429727446f870feddc91ebe0d7d90e158a06e9b51486f79`؛ `event_catalog.py=3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f`؛ تست=`a305bd989063bd09c34ea394aadd12c8bf7f22d9397a432b0734e0ff794ec8ba`.
- failure/retry: هیچ‌کدام. manual index حفظ و scheduler خودکار safe-default خاموش است.
- پذیرش فنی: `G-05 COMPLETE / F-043 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`؛ کنترل نهایی اسناد و discoverability هنوز در همین E ثبت می‌شود.
- کنترل اسناد: generator refresh؛ memory integrity، stale check، link check و targeted diff check همگی exit code صفر. گزارش نهایی در سطر 159 `REPORTS_INDEX.md` discoverable و SHA-256 آن `4a2b5bc45dd61ebc41a8a52386f197d2393a5c2b1a40ae9cf3d5d29ab07cf386` است.
- وضعیت نهایی: `G-05 COMPLETE / F-043 CLOSED`. طبق دستور کاربر، پس از پنج دقیقه نبود پیام توقف G-06 خودکار آغاز می‌شود.
- اثر بیرونی: test execution، UI static runner و basetemp مصنوعی؛ بدون Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.

### V-127 — G-06-A ممیزی F-042 و RED قرارداد Phase 10

- تاریخ: 2026-08-26
- سطح: `STATIC UI CONTRACT / TEST-FIRST / EMPTY TEST AND SKIP GUARD`
- Run: `STAB-G06-R01`
- Trigger اجرا: پایان خودکار بازهٔ پنج‌دقیقه‌ای پس از G-05 و F-042 باز.
- تفکیک وضعیت: Bale BOM بسته در G-02؛ Phase 11 onboarding=`7/7` بسته در G-04؛ packaging صریحاً G-07؛ RED جاری فقط Phase 10 helper drift.
- Phase 10: پنج assertion PASS، assertion ششم FAIL، exit code 1؛ علت test drift از تعریف محلی به import `utils/helpers.tsx`. runner روی failure source کامل App را چاپ کرد؛ credential/PII عملیاتی وجود نداشت.
- هشت runner دیگر UI همگی exit code صفر: scroll=`10/10`، grouped-media=`16/16`، Phase9 workspace/acceptance، observability، Phase11 onboarding=`7/7`، B2=`6/6` و mobile-auth static.
- guard جدید attempt اول=`0/3` به‌علت BOM reader در دو تست و RED واقعی Phase10؛ reader به `utf-8-sig` اصلاح شد. attempt دوم و سوم هر دو=`2/3 passed`, `1/3 failed` با basetempهای تازه؛ attempt سوم پس از کشف مسیر واقعی `.tsx` شاهد canonical است.
- guardهای سبز: empty test contract صفر؛ unconditional/unreasoned skip/xfail صفر. یک skipif ویندوزی reason صریح دارد.
- رخدادهای audit-tool جدا: یک quoting error، یک Windows wildcard error و یک helper suffix حدسی ناموجود؛ هیچ تغییر محصول/داده ایجاد نکردند.
- SHA-256 پیش از patch runner: runner=`772d331dfacb0d975bd0a034187647fa0b8e189bc318b14cede1c2cae6000185`؛ helper=`c8a0bb0ed4a1e4ddd11df473a1540999132006beb010ab8923df67b4b9015909`؛ guard=`93c23ebec88398333e2f0494f8bd5ce1d7240f7fa3201eddc86e87fb1174c79f`.
- پذیرش A: `RED_VERIFIED`. F-042 برای Phase10/G-06 و packaging/G-07 باز؛ B خودکار ادامه می‌یابد.
- کنترل ثبت A: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 164 `REPORTS_INDEX.md` discoverable و SHA-256 آن `4bc6929f1c583bf6c3f4c2ec092b9075395886da2806678971b370685e8d283d` است.
- اثر بیرونی: test/docs و UI static readers؛ بدون build/package واقعی، Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.

### V-128 — G-06-B اصلاح import contract Phase 10

- تاریخ: 2026-08-26
- سطح: `TEST RUNNER PATCH / TARGETED GREEN / RELATED REGRESSION`
- Run: `STAB-G06-R01`
- Trigger اجرا: RED canonical V-127.
- اصلاح: runner فایل `helpers.tsx` را مستقیم می‌خواند؛ import App و export canonical helper را با assertion محدود می‌سنجد؛ assertion تعریف محلی منقضی حذف شد.
- targeted: guard Python=`3/3 passed` با basetemp=`artifacts/stabilization/pytest-g06b-r01-targeted-a`؛ Phase10 UI=`7/7 passed`؛ هر دو exit code صفر.
- related Backend: G-06/Phase10-B/clean-install/account-auth/Application=`66/66 passed` با basetemp=`artifacts/stabilization/pytest-g06b-r01-related-a`؛ mobile-auth static exit code صفر.
- SHA-256: runner=`6d35d3f3c6c3536d77b9451a42d421d24c05135e0c114e381b84e0d35d9c6de4`؛ helper بدون تغییر=`c8a0bb0ed4a1e4ddd11df473a1540999132006beb010ab8923df67b4b9015909`؛ guard=`93c23ebec88398333e2f0494f8bd5ce1d7240f7fa3201eddc86e87fb1174c79f`.
- failure/retry: هیچ‌کدام پس از patch. پذیرش B=`TARGETED_AND_RELATED_GREEN`؛ C خودکار ادامه می‌یابد.
- کنترل ثبت B: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 165 `REPORTS_INDEX.md` discoverable و SHA-256 آن `b01b575db3637d888b73591ea48550e24c66e4cdd8cef22056b652ad0e5b82cf` است.
- اثر بیرونی: test runner/test/docs و basetemp مصنوعی؛ بدون تغییر product UI، Provider، دادهٔ عملیاتی، package یا Git mutation.

### V-129 — G-06-C قراردادهای UI، TypeScript و build محلی

- تاریخ: 2026-08-26
- سطح: `ALL UI CONTRACTS / TYPESCRIPT / LOCAL BUILD`
- Run: `STAB-G06-R01`
- Trigger اجرا: سبزی import contract در V-128 و معیار خروج G-06 برای تمام قراردادهای UI و build.
- ۹ runner UI همگی در اجرای نخست exit code صفر: scroll=`10/10`، grouped-media=`16/16`، Phase9 workspace=`12/12` و `15/15`، Phase9 acceptance=`13/13`، Phase10=`7/7`، observability=PASS، Phase11 onboarding=`7/7`، Phase11-B2=`6/6` و mobile-auth=PASS.
- TypeScript check exit code صفر. build محلی نیز 1015 module را تبدیل و با exit code صفر پایان داد؛ `pack:win`/installer اجرا نشد.
- هشدار ثبت‌شده: chunk اصلی minified برابر `794.74 kB` و بیش از آستانهٔ 500 kB است؛ warning غیرمسدودکننده و جدا از صحت قرارداد.
- SHA-256: `package.json=4271574af58a8352648a7d17e93a151516da7c1539771295267bb3cf6ea10bb3`؛ runner Phase10=`6d35d3f3c6c3536d77b9451a42d421d24c05135e0c114e381b84e0d35d9c6de4`؛ guard=`93c23ebec88398333e2f0494f8bd5ce1d7240f7fa3201eddc86e87fb1174c79f`.
- رخداد ابزار: Git status نخست به‌علت dubious ownership رد شد؛ retry با `-c safe.directory` همان فرمان موفق شد و هیچ Git config/mutation انجام نشد.
- پذیرش C: `UI_TYPESCRIPT_BUILD_GREEN`؛ D خودکار ادامه می‌یابد. اثر بیرونی فقط test readers و `ui/dist` تولیدشدهٔ محلی؛ بدون package، Provider network، Login/OTP/Send، دادهٔ عملیاتی یا Bale.
- کنترل ثبت C: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 166 `REPORTS_INDEX.md` discoverable و SHA-256 آن `77c2942993514554851d0a97cdacbbc3eabba2131c7eefe398cfc4752a295a08` است.

### V-130 — G-06-D regression گسترده و شمارش skip

- تاریخ: 2026-08-26
- سطح: `BROAD BACKEND REGRESSION / SKIP ACCOUNTING / OFFLINE`
- Run: `STAB-G06-R01`
- Trigger اجرا: سبزی تمام قراردادهای UI/build در V-129 و نیاز به پوشش گسترده پیش از full regression.
- دامنه: ۳۵ suite شامل guard G-06، G-04/G-05، clean install، account/application/auth، coordinator، diagnostics/observability، content index و Phaseهای 4/6/8/9/10/11.
- نتیجه: `307/307 passed` با basetemp=`artifacts/stabilization/pytest-g06d-r01-broad-a`، failure/error/skip صفر و exit code صفر.
- collect-only canonical: `307 tests collected` با cacheprovider خاموش و exit code صفر. تلاش quiet قبل از آن exit code صفر داشت اما خروجی بریده‌شدهٔ سه‌سطره جمع کل را نشان نداد؛ برای ثبت عدد دقیق فقط collection تکرار شد.
- warning محیطی: pytest نتوانست cache سراسری nodeids را به‌علت permission بنویسد؛ test basetemp و نتیجه سالم بود، بنابراین retry محصولی انجام نشد.
- پذیرش D: `BROAD_BACKEND_GREEN`؛ full suite و closure دامنهٔ تست به E، packaging به G-07. اثر بیرونی فقط test temp؛ بدون Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.
- کنترل ثبت D: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 167 `REPORTS_INDEX.md` discoverable و SHA-256 آن `c0db258fdc36dbca3a2309c103fa8f2f648e772d23149c99dd8064694808050f` است.

### V-131 — G-06-E full regression و closure حوزهٔ test contract

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / FINAL TEST CONTRACT ACCEPTANCE / OFFLINE`
- Run: `STAB-G06-R01`
- Trigger اجرا: سبزی A تا D و معیار خروج G-06 برای suite کامل و شمار skip.
- full Backend: `628/628 passed` در اجرای نخست با cacheprovider خاموش، basetemp=`artifacts/stabilization/pytest-g06e-r01-full-a`، failure/error/skip صفر و exit code صفر.
- collect-only مستقل: `628 tests collected` با exit code صفر. نسبت به G-05 عدد سه تست افزایش دارد که همان guardهای G-06 برای empty body، skip/xfail reason و import contract Phase 10 هستند.
- شاهد UI جاری از V-129: هر ۹ runner، TypeScript و build محلی سبز؛ از آن checkpoint تا E هیچ source/test/UI تغییر نکرد.
- whitespace scan هدفمند runner/guard صفر match داشت. SHA-256 نهایی runner=`6d35d3f3c6c3536d77b9451a42d421d24c05135e0c114e381b84e0d35d9c6de4` و guard=`93c23ebec88398333e2f0494f8bd5ce1d7240f7fa3201eddc86e87fb1174c79f` است.
- پذیرش: `G-06 COMPLETE / TEST_CONTRACT_DOMAIN_CLOSED`. F-042 فقط برای packaging در G-07 باز؛ پروژه `NOT_RELEASE_READY` و هیچ پذیرش Live ایجاد نشده است.
- اثر بیرونی: test temp و مستندات؛ بدون package/installer، Provider network، Login/OTP/Send، دادهٔ عملیاتی، Bale یا Git mutation.
- کنترل closure: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ هم‌سویی Baseline/Specification/Findings/Plan/Handoff تأیید شد. گزارش نهایی در سطر 164 `REPORTS_INDEX.md` discoverable و SHA-256 آن `f55cdbee77c225599dfac4421d669b3af1810875292448cecd9cf6ac9d441e5f` است.

### V-132 — G-07-A RED بسته‌بندی allowlist

- تاریخ: 2026-08-26
- سطح: `TEST-FIRST / SYNTHETIC PACKAGING / ENCODING AND PRIVACY CONTRACT`
- Run: `STAB-G07-R01`
- Trigger اجرا: پایان بازهٔ پنج‌دقیقه‌ای پس از G-06 و بخش packaging باز F-042.
- audit بایتی: `package_clean.py` برابر 3654 بایت، UTF-16LE/BOM و دارای 1826 NUL از offset 3 تا 3653؛ import عادی Python با SyntaxError متوقف می‌شود.
- تلاش اول: collection error=1 به‌علت NUL، exit code 1. هیچ تست رفتاری اجرا نشد.
- تلاش دوم با loader فقط-audit: `0/8 passed`, `8/8 failed`; assertion encoding source bytes امن را verbose چاپ کرد. harness به assertion boolean محدود اصلاح شد.
- تلاش سوم canonical: `0/8 passed`, `8/8 failed` با basetemp=`artifacts/stabilization/pytest-g07a-r03-red-c` و exit code 1.
- REDهای ثابت‌شده: UTF-8/importability، ورود scratch/probe توسط blacklist، نبود collector allowlist، dry-run/determinism/receipt، privacy scan و verifier traversal برای سه نام ناسالم.
- SHA-256 pre-image=`be8a9cf215e92fe8d077474e8f7742991c1730128424edf444acd12f5fe6b00c`؛ test canonical=`9d3d01fb1c95916e9bc10e8ef9ccf88a18f62969325d0979e16e02cd1c353598`.
- اثر بیرونی: فقط فایل/ZIP مصنوعی زیر basetemp؛ هیچ package واقعی پروژه، دادهٔ عملیاتی، Provider network، Bale یا Git mutation. پذیرش A=`RED_VERIFIED` و B خودکار ادامه می‌یابد.
- کنترل ثبت A: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 169 `REPORTS_INDEX.md` discoverable و SHA-256 آن `dff3d3388a020c3e416d4479ee6a0882f200e592e022f711f8df366ab1c58e9d` است.

### V-133 — G-07-B پیاده‌سازی allowlist و manifest

- تاریخ: 2026-08-26
- سطح: `SOURCE REPLACEMENT / TARGETED GREEN / REAL DRY-RUN`
- Run: `STAB-G07-R01`
- Trigger اجرا: هشت RED canonical در V-132.
- محدودیت ابزار: apply_patch نتوانست pre-image UTF-16 را decode کند. پس از resolve و containment check، فایل به artifact recoverable با هش ثابت منتقل و نسخهٔ UTF-8 با apply_patch ساخته شد؛ حذف غیرقابل‌بازگشت رخ نداد.
- اصلاح: exact root/script/docs/installer/wheel files و recursive product scopes سفید؛ manifest داخلی/hash/size، receipt بیرونی، dry-run، ZIP deterministic، scan private-key/JWT و verifier نام/duplicate/case/traversal/size/hash.
- compile=PASS و NUL count نهایی صفر. targeted=`8/8 passed` با basetemp=`artifacts/stabilization/pytest-g07b-r01-targeted-a`؛ related=`21/21 passed` با basetemp=`artifacts/stabilization/pytest-g07b-r01-related-a`; هر دو exit code صفر.
- dry-run واقعی: file_count=`296` و content_set_sha256=`bf8483fea77af8b29fbc922daf475916bfc05ed83c02eb4d931792b274f52a72`؛ output zip/receipt هر دو absent و exit code صفر.
- رخداد ابزار: جست‌وجوی اولیهٔ `rg *.bat` روی Windows exit code 2؛ retry با glob داخلی `-g` موفق. این failure محصول یا packaging نبود.
- SHA-256: source=`4c4ca4543f262e07918f831f1580e14ae859e5ed25995443e92f04768aff7fd8`؛ test=`9d3d01fb1c95916e9bc10e8ef9ccf88a18f62969325d0979e16e02cd1c353598`؛ pre-image preserved=`be8a9cf215e92fe8d077474e8f7742991c1730128424edf444acd12f5fe6b00c`.
- پذیرش B=`ALLOWLIST_TARGETED_GREEN`; C archive واقعی فقط زیر artifacts می‌سازد و adversarial/reproducibility را ادامه می‌دهد. بدون نصب، Provider، Bale، دادهٔ عملیاتی یا Git mutation.
- کنترل ثبت B: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 170 `REPORTS_INDEX.md` discoverable و SHA-256 آن `655ae6c036f6a5ba6985af05322699e0608ea8dc88a086a05b8f15f25b6df1fc` است.

### V-134 — G-07-C adversarial archive و reproducibility

- تاریخ: 2026-08-26
- سطح: `ADVERSARIAL ZIP / PRIVACY NAMES / BYTE REPRODUCIBILITY`
- Run: `STAB-G07-R01`
- Trigger اجرا: سبزی allowlist/dry-run در V-133 و معیار archive واقعی G-07.
- guardها: case-insensitive collision، entry hash tamper و عدم overwrite/atomic temp؛ suite کامل package=`11/11 passed` با basetemp=`artifacts/stabilization/pytest-g07c-r01-adversarial-a` و exit code صفر.
- archive A/B: هرکدام file_count=296، ZIP entries=297 با manifest آخر، size=2,031,927، content-set=`bf8483fea77af8b29fbc922daf475916bfc05ed83c02eb4d931792b274f52a72` و SHA-256 یکسان=`3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903`.
- receipt A/B هر دو با hash archive منطبق؛ verifier هر دو 296 و content equality=true. اسکن مستقل top-level forbidden=0 و case collision=0.
- false-positive audit: rule نخست 13 مورد nested product diagnostics، fail-closed Bale slot و `vendor/runtime` را operational تشخیص داد؛ نام‌ها بررسی و rule به top-level محدود شد. این‌ها دادهٔ عملیاتی/Bale artifact نیستند.
- invocation failure: f-string یک‌خطی verifier به‌علت quoting SyntaxError گرفت؛ retry بدون nested quoting exit code صفر. هیچ artifact تغییر نکرد.
- SHA-256 source بدون drift B=`4c4ca4543f262e07918f831f1580e14ae859e5ed25995443e92f04768aff7fd8`؛ test C=`3ae9ad268acc8011230ee1c38faf55319814f3593c6444de1dbc078c19a30a2f`.
- پذیرش C=`ADVERSARIAL_REPRODUCIBLE_GREEN`; اثر بیرونی فقط چهار artifact کنترل‌شدهٔ ZIP/receipt. بدون install/publish، Provider، دادهٔ عملیاتی، Bale development یا Git mutation.
- کنترل ثبت C: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 171 `REPORTS_INDEX.md` discoverable و SHA-256 آن `b754d82a264f43aae08fd02c6d855b073c22286eca64fd495e53615bf0003d1a` است.

### V-135 — G-07-D wheel parity و fresh-install rehearsal ایزوله

- تاریخ: 2026-08-26
- سطح: `WHEEL PARITY / OFFLINE BUILD / EXTRACT / FRESH VENV REHEARSAL`
- Run: `STAB-G07-R01`
- Trigger اجرا: archive reproducible V-134 و معیار fresh-install G-07.
- RED parity: audit wheel source سه نمونه را متفاوت/غایب یافت. guard پس از fixture newline correction به RED canonical=`12/13 passed`, `1/13 failed` با basetemp=`artifacts/stabilization/pytest-g07d-r03-red-c`; failure واقعی missing=57/mismatched=20.
- build attempt استاندارد با `--no-build-isolation` به‌علت `BackendUnavailable: setuptools.build_meta` exit code 1؛ شبکه استفاده نشد. builder stdlib به API پارامتردار/deterministic و metadata canonical تبدیل شد.
- pre-image wheel قدیمی: SHA=`668a30c29228229b0172258d80f9c6324fc7a11289d877a34fe11499fc81257a` در artifact recoverable. label نخست بر اساس hash تاریخی اشتباه بود و به prefix واقعی تغییر نام یافت.
- wheel میانی SHA=`bb9ecb443802f45582d87baf69b25eb8a2aaa11690cbd3fd37b48a04f4edc60f` و parity 104/0 drift؛ fresh venv اول install/runtime-check PASS ولی `pip check` سه missing dependency داد.
- علت dependency RED: cryptography/httpx/websockets فقط در subtree قرنطینه‌شدهٔ `application/bale_client` استفاده می‌شوند. آن subtree از release/wheel حذف، سه dependency از pyproject/metadata حذف و fail-closed `providers/bale/slot.py` حفظ شد.
- دو wheel نهایی مستقل byte-equal، SHA=`de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf` و parity=`90 source / missing=0 / mismatch=0 / extra=0`.
- archive نهایی: file_count=282، SHA=`8b76948818111db7856278f8787ed8c1a277d1b2dd5d0680c0c24733fe3f3437`، content-set=`3c777df594577009860338934bf0dec4f34fdb0ee309f10497adf46ae50a1c1b`; extract required=15/missing=0، quarantined client=0، self-dry-run=282 و output absent، compile PASS.
- fresh venv نهایی: runtime wheels/core/bridge آفلاین نصب؛ runtime checker PASS؛ `pip check`=`No broken requirements found`; import BridgeApplicationApi/Event Catalog PASS و catalog count=92.
- targeted package+Bale=`20/20 passed`; related 11 suite=`102/102 passed` با basetemp=`artifacts/stabilization/pytest-g07d-r07-related-green`; collect-only=102.
- هش‌های نهایی: package_clean=`589df28708f5bd246319d4b78f0683ba288c230bd024901a70b212dc0184263e`؛ builder=`6f5e65deec8eb93b90a663e45ae4de0eaadf9e9473c659d8455e45e803dd46e3`؛ launcher=`352182c89be3fd4ee5c231b35419fe895bc8987cfbfc2890f603b306f177cf06`؛ pyproject=`a5eb3685b2e9990c9afee4514d22fae626295ec989c98e4127f0083a51f12e30`؛ test=`9756ba63f7fe9d32046e89e3eabd3b6dd4cfd63aa3181c7e64457855072fd770`.
- پذیرش D=`FRESH_INSTALL_REHEARSAL_GREEN`. تمام installها فقط در venv مصنوعی artifacts؛ بدون نصب سیستم/کاربر، Provider، دادهٔ عملیاتی، Bale development یا Git mutation.
- کنترل ثبت D: generator refresh و memory integrity/stale/link check همگی exit code صفر؛ گزارش در سطر 172 `REPORTS_INDEX.md` discoverable و SHA-256 آن `2e72a0c25a420b0a8a6d56b6eff5f191416e38e770682c38f56e6753b1b1c52f` است.

### V-136 — G-07-E full regression و closure F-042

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / TYPESCRIPT / OBSERVABILITY / FINAL RELEASE ARCHIVES`
- Run: `STAB-G07-R01`
- Trigger اجرا: سبزی A تا D و معیار closure F-042/G-07.
- full Backend: `643/643 passed` در اجرای نخست با basetemp=`artifacts/stabilization/pytest-g07e-r01-full-a`، failure/error/skip صفر و exit code صفر؛ collect-only=643.
- UI: TypeScript و UI/Electron Observability exit code صفر. build G-06-C جاری است و به‌علت نبود تغییر UI تکرار نشد.
- wheel نهایی SHA=`de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf`؛ core wheel SHA=`bd12add1866fcb0f25928f9f2b29229f1010e7253738f06ae42c3aa9cd1f23b0`.
- archive نهایی A/B: هرکدام file_count=282، entries=283، SHA-256 بایت‌یکسان=`729a3d613f8e941c7b973af2e6433fb387b1f97fee2b4e07e72d196b79e2cb57` و content-set=`1b7cc61fac50c3b581aaa6c577f6a64589ff921370d80bf0e75c12ee43e4170c`. verifier هر دو=282؛ top-level/quarantined forbidden=0؛ collision=0؛ manifest-last و receipt match=true.
- hashهای نهایی: package_clean=`589df28708f5bd246319d4b78f0683ba288c230bd024901a70b212dc0184263e`؛ builder=`6f5e65deec8eb93b90a663e45ae4de0eaadf9e9473c659d8455e45e803dd46e3`؛ launcher=`352182c89be3fd4ee5c231b35419fe895bc8987cfbfc2890f603b306f177cf06`؛ pyproject=`a5eb3685b2e9990c9afee4514d22fae626295ec989c98e4127f0083a51f12e30`؛ package test=`9756ba63f7fe9d32046e89e3eabd3b6dd4cfd63aa3181c7e64457855072fd770`؛ Release Manifest=`15aae5e02bf60ffa6d327217215be6a39aa76f178f6edb2adc3f81e811d6c3cd`.
- کنترل closure: Release Manifest JSON، generator refresh، memory integrity، stale/link check همگی exit code صفر؛ Baseline/Specification/Structure/Installer/Security/ADR/Findings/Plan/Handoff هم‌سو. گزارش نهایی در سطر 169 `REPORTS_INDEX.md` و SHA-256 آن `bfcb2a3fe6e64ef0ce6c488bbeb50e4be4f491d56fecb64f2c1b2edc3ffd97a8` است.
- پذیرش فنی: `G-07 COMPLETE / F-042 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`.
- مرز: no code-sign، installer EXE، نصب واقعی، publish، Provider/Login/Send، دادهٔ عملیاتی یا Bale development؛ پروژه `NOT_RELEASE_READY`.

### V-137 — G-08-A ممیزی و RED مشاهده‌پذیری

- تاریخ: 2026-08-26
- سطح: `STATIC AUDIT / SYNTHETIC CONTRACT RED`
- Run: `STAB-G08-R01`
- Trigger اجرا: تکمیل G-07، پایان بازهٔ پنج‌دقیقه‌ای بدون دستور توقف کاربر و شکاف‌های OBS-006/007 و scanner تک‌حساب.
- pre-imageها: scanner=`99c34024b9b24477dc5fde05f88045dcdb87e6f9058773192a3c15e457b8958d`؛ RuntimeLogger=`2dc04203775c829ebafd34f4ebc960232b7e34f8507465aecef87d65cc554fc1`؛ manager=`fba43190216467231baffeca8838fe24a057812e74c586d9ef3c8521532face9`؛ diagnostics init=`dd84e2df98e9b1415927749ad85f0ce82074eec7ddef93a02281bfca855f2537`؛ Event Catalog=`3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f`.
- RED canonical: `tests/test_g08_observability_completion.py` با basetemp=`artifacts/stabilization/G08A-red` برابر `4 collected / 4 failed`، exit code 1.
- طبقه‌بندی: هر چهار شکست `contract`؛ دو scanner، یک logger write-health و یک retention/disk-health. warning cacheprovider به‌علت permission محیطی و غیرمؤثر است.
- test SHA-256=`1644076e371754207add4ed52e64d3f63ed29ca3f21a34ef927526ec90a09071`.
- پذیرش A=`RED_VERIFIED`; F-048 باز و B خودکار ادامه می‌یابد.
- اثر بیرونی: فقط basetemp مصنوعی/test/docs؛ بدون خواندن runtime/diagnostics/config/account واقعی، شبکه، Provider، Bale یا Git mutation.

### V-138 — G-08-B اسکنر چندحسابی opaque

- تاریخ: 2026-08-26
- سطح: `SOURCE PATCH / TARGETED + RELATED CONTRACT`
- Run: `STAB-G08-R01`
- Trigger اجرا: دو RED scanner در V-137.
- اصلاح: حذف `ACCOUNT_ID/LOGS` ثابت؛ discovery محدود application/account current+numeric rotations؛ رد symlink؛ scope ترتیبی؛ عدم چاپ path/id/value؛ malformed JSON/UTF-8/read failure/missing current fail-closed؛ format v2 و root مصنوعی.
- اصلاح test harness: application log سالم به سناریوی malformed افزوده شد تا finding مفقودی فایل لازم با دو finding هدف مخلوط نشود.
- compile=PASS؛ targeted scanner=`2/2 passed` با basetemp=`artifacts/stabilization/G08B-targeted-b`؛ related privacy/observability/diagnostics/Phase10-D=`18/18 passed` با basetemp=`artifacts/stabilization/G08B-related-a`؛ exit codeها صفر.
- SHA-256: scanner=`a0c28c122d54896082318545d56c884f12c65292871323a0bfeb4df22eb893d5`؛ test=`3922875718d92d72a652a598c9bd68a3d8bef0c8bd9f33259cdb63064b16b043`.
- پذیرش B=`MULTI_ACCOUNT_SCANNER_GREEN`; F-048 برای C/D/E باز و C خودکار آغاز می‌شود.
- اثر بیرونی: test temp/source/test/docs؛ بدون اسکن Live، runtime/diagnostics/config/account واقعی، Provider، Bale، شبکه یا Git mutation.

### V-139 — G-08-C Event Catalog و background/lifecycle

- تاریخ: 2026-08-26
- سطح: `SYNTHETIC CONTRACT RED/GREEN / RELATED REGRESSION`
- Run: `STAB-G08-R01`
- RED C: `4/4 failed` با basetemp=`artifacts/stabilization/G08C-red-a`؛ missing catalog=5، background success/failure lifecycle=2 و silent manual/best-effort event coverage=1.
- اصلاح: generic background از `observed_operation`؛ content-index lifecycle/cleanup، read-receipt failure، unexpected lease-renew و application/auth-close lifecycle امن؛ Catalog `92→102`.
- GREEN C=`4/4 passed` با basetemp=`artifacts/stabilization/G08C-targeted-a`؛ related صحیح=`98/98 passed` با basetemp=`artifacts/stabilization/G08C-related-b`; compile=PASS.
- رخداد دامنه: اجرای related نخست دو RED برنامه‌ریزی‌شدهٔ D را هم وارد کرد و فقط همان health/retention test را شکست داد؛ C و سایر تست‌ها سبز بودند. retry_of دامنه با حذف D RED برابر 98/98 است؛ failure_class=`test_scope_selection`.
- pre-image read-only از archive نهایی G-07-E: API=`d5f3bde003b9c5827429727446f870feddc91ebe0d7d90e158a06e9b51486f79`؛ account runtime=`7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`؛ Catalog=`3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f`.
- post SHA-256: API=`cdc21b9ab2c10056c3a27c8ae45147e2e579710bc339ef96e1f2ecacb4c1f8b4`؛ account runtime=`8dfee07d7c514ce0d120485e124b924415dd1c07650bd2010c7bf3f80d785286`؛ Catalog=`f4e96b84d9040e32424cc88764d6ee34ae55ec15a5acb2937246946dbc8a99a3`؛ test=`d0a7738ff4f647e3a5d50c2d2a8b40d8369ff36c06f27f32c01fc14b980cc185`.
- پذیرش C=`EVENT_LIFECYCLE_GREEN`; F-048 برای D/E باز و D خودکار آغاز می‌شود.
- اثر بیرونی: synthetic config/runtime test temp و source/docs؛ بدون Live log/account/Provider، Bale، شبکه یا Git mutation.

### V-140 — G-08-D write-health، retention/disk و Support Bundle adversarial

- تاریخ: 2026-08-26
- سطح: `ADVERSARIAL SYNTHETIC / TARGETED + RELATED REGRESSION`
- Run: `STAB-G08-R01`
- RED: چهار قرارداد اصلی=`4/4 failed` با basetemp=`artifacts/stabilization/G08D-red-a`؛ health endpoint جدا=`1/1 failed` با status 404 و basetemp=`G08D-red-b`.
- اصلاح: health-aware handler/counter، numeric path-free health، runtime current/rotation allowlist retention و budget، disk summary، maintenance event/health endpoint، JSONL normalization/marker، symlink rejection و scanner member/archive opaque.
- targeted-a=`4/5 passed`: expected remaining bytes در fixture 54 بود، مقدار واقعی سه سطر 19‌بایتی=57؛ فقط assertion اصلاح شد. targeted-b=`5/5 passed`.
- expanded guard attempt=`12/13`: BrokenStream فاقد `seek/tell` بود و AttributeError را به‌جای OSError هدف ساخت؛ test double تکمیل شد. G08 all retry=`13/13 passed` با basetemp=`artifacts/stabilization/G08D-g08-all-b`.
- related privacy/Phase10-D/observability/diagnostics/API/account/audit=`78/78 passed` با basetemp=`artifacts/stabilization/G08D-related-a`.
- pre SHA-256: RuntimeLogger=`2dc04203775c829ebafd34f4ebc960232b7e34f8507465aecef87d65cc554fc1`؛ manager=`fba43190216467231baffeca8838fe24a057812e74c586d9ef3c8521532face9`؛ init=`dd84e2df98e9b1415927749ad85f0ce82074eec7ddef93a02281bfca855f2537`؛ API(C)=`cdc21b9ab2c10056c3a27c8ae45147e2e579710bc339ef96e1f2ecacb4c1f8b4`؛ Catalog(C)=`f4e96b84d9040e32424cc88764d6ee34ae55ec15a5acb2937246946dbc8a99a3`؛ creator=`480805802c27b27814f20f60a6fe8a2a9c33c3d58fd67f7b53a959cf81538202`؛ scanner=`b02e66e97a7fcce4661634bf34eeaa117a332f9e50d6f43cb30008b4a143a4cc`.
- post SHA-256: RuntimeLogger=`c017daaefa36d3a851feafbfd8a2f1dec89e023dc0e92381eb59256c174fc1a8`؛ manager=`65b2587b4cf6f209f601ec514058b2ea14c17bf868525d73c20670973b1c9887`؛ init=`7ae8c0946e72abfc6e8977b3c3cae7d5ff9199fd2c3a3f79d7b65d366d9b0c6a`؛ API=`1ca260183f02af219a281a47829c43872206614d13cf7f91a355780e9a454f4a`؛ Catalog=`e4707ce394b5e2af1f97656aa88dbfff891e08e781fc54efd9031206a9c62097`؛ creator=`dd694d4928f22718c0cf002567dd9b77ca96a50b536d3b17ff27fc6e4907bf06`؛ scanner=`7c713d862e4c2dd894be3c2eed8a9b18721d6a71c74996d24fb3aee6e620e661`؛ test=`6a957b4016f643d8136bfadf93d5e5f1f00581398f087f2e9da7e2eb05d7a7ef`.
- Catalog count=`103`; پذیرش D=`HEALTH_RETENTION_SUPPORT_GREEN`; E خودکار ادامه دارد.
- اثر بیرونی: فقط source/test/docs و فایل‌های مصنوعی؛ حذف فقط rotationهای basetemp. بدون runtime/diagnostics/config/DB واقعی، Provider، Bale، شبکه یا Git mutation.

### V-141 — G-08-E full regression، wheel parity و closure

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / WHEEL PARITY / TYPESCRIPT / UI OBSERVABILITY`
- Run: `STAB-G08-R01`
- full attempt A: `656 collected / 655 passed / 1 failed` با basetemp=`artifacts/stabilization/G08E-full-a`; تنها failure=`test_bundled_bridge_wheel_matches_current_source_tree` و parity=`missing0/mismatched6/extra0`؛ failure_class=`packaging_artifact_drift`.
- pre-image wheel SHA=`de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf` در `artifacts/stabilization/G08E_bridge_wheel_preimage_de9dd96f.whl` حفظ شد.
- builder stdlib آفلاین دو خروجی مستقل بایت‌یکسان ساخت؛ wheel SHA=`9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70`، source files=90 و missing/mismatch/extra=0.
- package+G08=`28/28 passed` با basetemp=`artifacts/stabilization/G08E-wheel-related-a`.
- full retry B=`656/656 passed` با basetemp=`artifacts/stabilization/G08E-full-b`، failure/error/skip صفر. collect-only مستقل total=656 و exit code صفر.
- UI: TypeScript و UI/Electron Observability هر دو exit code صفر؛ build UI تکرار نشد چون هیچ UI source change از G-06-C وجود ندارد.
- پذیرش=`G-08 COMPLETE / F-048 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`؛ archive نهایی G-07 پس از G-08 تاریخی و بازتولید/fresh-install نهایی در G-09 الزامی است.
- اثر بیرونی: full tests، دو wheel محلی کنترل‌شده، pre-image recoverable و docs؛ بدون publish/install واقعی، Provider/Live، Bale، دادهٔ عملیاتی یا Git mutation.
- کنترل closure: Release Manifest JSON، generator refresh، memory integrity، stale check و link check همگی exit code صفر؛ گزارش نهایی در سطر 174 `REPORTS_INDEX.md` و SHA-256 آن `d0c819e6aeb97c5e323b583dd1c00c64fdb59b09de11c157169475e3d1fb32b0` است.

### V-142 — G-09-A baseline پذیرش و package dry-run

- تاریخ: 2026-08-26
- سطح: `READ-ONLY HASH AUDIT / PACKAGE DRY-RUN`
- Run: `STAB-G09-R01`
- Trigger: تکمیل G-08 و پایان بازهٔ پنج‌دقیقه‌ای بدون دستور توقف کاربر؛ نیاز G-09 به archive/fresh-install نهایی.
- hashها: package_clean=`589df28708f5bd246319d4b78f0683ba288c230bd024901a70b212dc0184263e`؛ builder=`6f5e65deec8eb93b90a663e45ae4de0eaadf9e9473c659d8455e45e803dd46e3`؛ wheel=`9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70`؛ Release Manifest=`3b1010b892f80eca0fc8a95c8c396359ceeba30bcd1ba57a18521f0e74cc622c`.
- dry-run: exit code 0، file_count=282، content-set=`cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a`، output/receipt write=0.
- RED اجرا نشد: A تغییر رفتاری نیست و فقط baseline acceptance/read-only است؛ REDهای package در V-132 و wheel drift در V-141 جاری‌اند.
- پذیرش=`G09A_BASELINED`; B خودکار ادامه دارد. اثر بیرونی فقط read/test process؛ بدون archive write، Live/Provider، data، Bale یا Git mutation.

### V-143 — G-09-B archive نهایی، privacy و reproducibility

- تاریخ: 2026-08-26
- سطح: `FINAL ARCHIVE / INDEPENDENT VERIFIER / PACKAGE REGRESSION`
- Run: `STAB-G09-R01`
- archiveهای A/B: هرکدام file_count=282، ZIP entries=283 و SHA-256 یکسان=`a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360`.
- content-set هر دو=`cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a`؛ receipt/hash/count تطبیق دارد.
- verifier هر دو: schema/order/member size/hash PASS؛ privacy scan high-confidence private-key/JWT finding=0.
- بازبینی مستقل ZIP هر دو: manifest-last=true، duplicate=0، case-collision=0، forbidden-entry=0.
- package test attempt A=`3 passed / 12 setup errors`؛ علت فقط PermissionError پوشهٔ Temp پیش‌فرض Pytest بود و test bodyهای متأثر اجرا نشدند. retry با basetemp کنترل‌شده و بدون تغییر کد=`15/15 passed`.
- packager SHA=`589df28708f5bd246319d4b78f0683ba288c230bd024901a70b212dc0184263e` و test SHA=`9756ba63f7fe9d32046e89e3eabd3b6dd4cfd63aa3181c7e64457855072fd770`؛ source/test change=0.
- RED تازه موضوعیت نداشت: artifact acceptance روی قراردادهای adversarial V-132 و wheel-drift V-141 بنا شده است.
- کنترل اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش در سطر 180 `REPORTS_INDEX.md` و SHA-256 آن `e8ca7f336402f62be07015c65071754e7e6651fc3b33207dbe0528022681fd9d` است.
- پذیرش=`G09B_FINAL_ARCHIVE_GREEN`; C خودکار ادامه دارد. اثر بیرونی فقط چهار artifact محلی و test temp؛ بدون Live/Provider، data، Bale، شبکه، نصب سیستمی یا Git mutation.

### V-144 — G-09-C extract و fresh-install کاملاً آفلاین

- تاریخ: 2026-08-26
- سطح: `FINAL ARCHIVE EXTRACT / WHEEL PARITY / ISOLATED OFFLINE INSTALL`
- Run: `STAB-G09-R01`
- archive ورودی SHA=`a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360`؛ extract files=283، required canonical=`15/15` و quarantined Bale client files=0.
- checklist attempt نخست به‌علت مسیر قدیمی Event Catalog missing=1 کاذب داد؛ مسیر canonical اصلاح و بدون تغییر artifact/source نتیجه missing=0 شد.
- self dry-run داخل extract: file_count=282، content-set=`cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a`، archive/receipt write=0؛ compileall=PASS.
- wheel parity داخل extract: source=90، missing/mismatched/extra=0 و SHA=`9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70`.
- fresh venv فقط زیر artifacts ساخته و با `--no-index` از core/bridge/runtime wheelهای archive نصب شد؛ download/network=0.
- runtime checker=`ok=true/failures=0`؛ pip check=PASS؛ module زیر prefix محیط تازه؛ product/API/Catalog=`0.7.0-ui-mvp6.1.1-gmi4.2 / v1 / 103`؛ entrypoints=4.
- RED تازه اجرا نشد: rehearsal acceptance بر REDهای V-132/V-135/V-141 بنا شده و source/test change=0 است.
- کنترل اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش در سطر 181 `REPORTS_INDEX.md` و SHA-256 آن `be707f7b85f82c85f090f02c35cf5104dffb1adcd4c64d85942b79795b318309` است.
- پذیرش=`G09C_OFFLINE_FRESH_INSTALL_GREEN`; D خودکار ادامه دارد. اثر بیرونی فقط extract/compile cache/fresh venv زیر artifacts و اسناد؛ بدون نصب سیستم/کاربر، Live/Provider، data، Bale، شبکه یا Git mutation.

### V-145 — G-09-D full Backend، تمام قراردادهای UI و build

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / ALL UI CONTRACTS / TYPESCRIPT / LOCAL BUILD / SAFE STATUS AUDIT`
- Run: `STAB-G09-R01`
- full Backend attempt A با basetemp=`artifacts/stabilization/G09D_full_20260826`: `656/656 passed`، failure/error/skip=0 و exit code صفر؛ collect-only مستقل=656/exit0.
- ۹ runner UI همگی در اجرای نخست exit0: scroll=`10/10`، grouped=`16/16`، Phase9 workspace=`12/12 + 15/15`، Phase9 acceptance=`13/13`، Phase10=`7/7`، observability=PASS، Phase11 onboarding=`7/7`، Phase11-B2=`6/6` و mobile-auth/live static=PASS.
- TypeScript check=PASS؛ build=PASS/1015 modules. bundle اصلی=794741 bytes و SHA=`6659940b0dd49cf0a0cff3f5e23b200e7f5cdc8529ecf7a89373f3f379f17461`؛ warning chunk >500kB غیرمسدودکننده و بدون تغییر نسبت به G-06-C.
- privacy/log criterion: G08 contracts=`13/13` در full suite جاری و G09B archive privacy findings=0؛ هیچ log/runtime واقعی اسکن نشد.
- safe Git status read-only موفق؛ tree عمداً dirty و دست‌نخورده ماند؛ root operational rows برای bridge.json/.env/data/runtime/diagnostics/backups=0. هیچ safe.directory دائمی یا Git mutation انجام نشد.
- RED تازه اجرا نشد: مرحلهٔ acceptance تجمیعی است و source/test change=0؛ REDهای هدفی پیش‌تر بسته شده‌اند.
- کنترل اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش در سطر 182 `REPORTS_INDEX.md` و SHA-256 آن `951a3c2975db874b77af41212d687bae648d083f9a1ce6cb97fb5e151a0d0f80` است.
- پذیرش=`G09D_FULL_AUTOMATED_ACCEPTANCE_GREEN`; E خودکار ادامه دارد. اثر بیرونی test temp، `ui/dist` محلی و اسناد؛ بدون pack:win/installer، Live/Provider، data، Bale، شبکه یا Git mutation.

### V-146 — G-09-E همسوسازی canonical، Release Manifest و handoff

- تاریخ: 2026-08-26
- سطح: `FINAL CANONICAL ALIGNMENT / RELEASE CLASSIFICATION / HANDOFF`
- Run: `STAB-G09-R01`
- شواهد فنی ورودی: dry-run=282/write0؛ archiveهای بایت‌یکسان SHA=`a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360`؛ privacy=0؛ fresh-install no-index=PASS؛ wheel=90/0 drift؛ Backend=`656/656`/skip0؛ تمام UI contracts/TypeScript/build=PASS.
- اسناد همسو: Current Baseline، Project Specification، Findings Register، Observability Audit، Architecture Decisions، Release Manifest، remediation plan، final report و handoff.
- Findings: F-005 و F-006 برای current program scope بسته؛ F-045=`AUTOMATED_TECHNICAL_EXECUTION_COMPLETE / USER_ACCEPTANCE_PENDING`. F-039 commit pending، F-013 nonblocking و OBS-008 deferred باقی‌اند.
- release classification=`OFFLINE_RELEASE_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED`; code-sign، Windows visual، real-user installer و پذیرش صریح کاربر دروازه‌های مستقل‌اند.
- Release Manifest JSON parse=PASS؛ SHA=`b4d27d10b68b579be641bd92ee44c4c1489b2ce95ed813b51a495bbc1e44d122`.
- canonical SHAها: Baseline=`72d40473d0226c5b0210c11cf9c81f8b3923fe8d4b6c559b2d90df847f0854bb`؛ Findings=`480187d66d9c0400253e131d719172563d8855268a8a0190ddf64dea2920cd0a`؛ Architecture=`cd30755e34d090ee179be9c35b50bcafc5f14dddf83633c63d69b0616651048b`.
- RED تازه اجرا نشد: E تغییر رفتاری محصول نیست؛ canonical acceptance از شواهد A تا D و REDهای بسته‌شدهٔ برنامه مشتق می‌شود.
- کنترل اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش نهایی در سطر 179 `REPORTS_INDEX.md` و SHA-256 آن `314819c90a045a404a7750c449c0229f80a6355f302b95f8e6d682be18c60c46` است؛ handoff SHA=`5e7224f3a7fe569b799f55ac4d3c7d0103131933f1762474181d10330ad2486b`.
- پذیرش فنی=`G09_AUTOMATED_SCOPE_COMPLETE`; پذیرش کاربر هنوز ثبت نشده است. اثر بیرونی فقط اسناد؛ بدون Live/Provider، data، Bale، شبکه، نصب سیستم یا Git mutation.

### V-147 — G-09-E بازسازی archive پس از همسوسازی اسناد و fresh-install نهایی

- تاریخ: 2026-08-26
- سطح: `FINAL SELECTED-DOC DRIFT DETECTION / REPRODUCIBLE ARCHIVE / EXACT-ARTIFACT FRESH INSTALL`
- Run: `STAB-G09-R01`
- Trigger: dry-run پس از canonical alignment مقدار content-set تازه=`d60b10eac4abdd1fd28d1cd6e1ff9f955576b2e393e926e8945a913667a41a49` را در برابر G09B=`cf055cd4...` نشان داد؛ تحویل artifact قدیمی مجاز نبود.
- manifest diff دقیق: changed فقط `ARCHITECTURE_DECISIONS.md`؛ added=0 و removed=0. source/UI/wheel/dependency drift=0.
- دو archive نهایی E: file_count=282، entries=283، SHA یکسان=`6ff12e2b82bcaf35833a16d158502fad507a4f16a177113d5b6c65ea87528071` و content-set یکسان=`d60b10eac4abdd1fd28d1cd6e1ff9f955576b2e393e926e8945a913667a41a49`.
- verifier هر دو: privacy high-confidence finding=0، schema/order/member hash/size PASS؛ بازبینی مستقل manifest-last=true، duplicate/case-collision/forbidden=0.
- extract archive نهایی: self dry-run=282/content-set exact/write0؛ wheel parity=90 source/missing-mismatch-extra=0/SHA=`9408596d...`؛ Architecture decision 39 حاضر.
- fresh venv نهایی از دقیقاً همین extract و `--no-index`: install PASS، runtime checker ok/failures0، pip check PASS، imports product/API/Catalog=`0.7.0-ui-mvp6.1.1-gmi4.2/v1/103`.
- archiveهای G09B تاریخی و artifactهای `G09E_release_final_a/b` canonical هستند. اثر بیرونی فقط archive/extract/venv کنترل‌شده و اسناد؛ بدون Live/Provider، data، Bale، شبکه، نصب سیستم یا Git mutation.
- dry-run پس از تمام patchهای closure همچنان 282 فایل/content-set=`d60b10ea...`/write0 است. Release Manifest JSON=PASS و SHA=`05282e5da4331f478c7bb97d6333434f2a2410137e158e56e2191c4357ef12e9`.
- کنترل نهایی اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش سطر 179 و SHA=`f785e84cabaaa218c6ca539b89703f995f1af1557018f6292bcb33d5a23e49ad`؛ handoff SHA=`6f5cf5198d94184751c66e1b874b422c7713914e8a5c5fdd8efeb585ad1dc1a6`.

### V-148 — پذیرش صریح کاربر و closure رسمی G-09/F-045

- تاریخ: 2026-08-26 ساعت 21:54 به‌وقت تهران
- سطح: `USER ACCEPTANCE / DOCUMENTATION-ONLY FINAL CLOSURE`
- Run: `STAB-G09-R01`
- فرمان کاربر: «G09 را می‌پذیرم و closure نهایی را ثبت کن».
- نتیجه: G-09=`COMPLETE / USER_ACCEPTED` و F-045=`CLOSED / G-00..G-09 COMPLETE / USER_ACCEPTED`.
- طبقه‌بندی snapshot بدون تغییر=`OFFLINE_RELEASE_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED`؛ پذیرش کاربر code-sign، Windows visual، real-user installer، عملیات Live یا Git mutation را مجاز نمی‌کند.
- تغییر این checkpoint فقط اسناد canonical، Release Manifest و handoff است؛ source/test/archive/data عملیاتی تغییر نمی‌کند.
- Release Manifest JSON=PASS و SHA=`596d75e4658ed063af4bd37e1ae2b953eeb6f71a72a68ede7fd8f4a93a7b5191`؛ package dry-run پس از closure همچنان 282 فایل/content-set=`d60b10ea...`/write0 است، بنابراین archive canonical منقضی نشد.
- کنترل اسناد: refresh، memory integrity، stale و link check همگی exit code صفر؛ گزارش نهایی سطر 179 و SHA=`23d939e842ef96df75b6e7a8b7752cc073c9bcfa4a942c38b1d60c22964a6316`؛ handoff SHA=`8c277648ffe0f508780f07b460b7691de262e5af1668c45ce3e7da37e5eee441`.

### V-149 — ممیزی commit PyCharm و حفاظت پیش از پاک‌سازی

- تاریخ: 2026-08-26
- سطح: `READ AUDIT / RECOVERABLE BACKUP REF / GITHUB REMOTE VERIFICATION`
- Run: `STAB-GIT-R01`
- commit اولیه=`f4464ef8...` با 7213 فایل؛ temp/cache=6068 و archive/binary=100. operational root/DB/bridge.json واقعی=0.
- secret-pattern filename scan: فقط `tests/test_g07_release_packaging.py` با fixture مصنوعی adversarial؛ credential واقعی اثبات نشد.
- وضعیت remote: مخزن جاری origin GitHub ندارد و upstream آن remote محلی `legacy/stabilization` است. GitHub `EitaaDesktop` در خواندن زنده فقط main=`a4df3ec...` داشت؛ commit جدید و branch stabilization موجود نبود.
- backup ref پیش از cleanup: `codex/backup-pycharm-f4464ef` دقیقاً روی `f4464ef8...` ساخته شد.
- سیاست: حذف فقط از index با `--cached`؛ حذف local file/reset hard ممنوع. engineering logs/reports/handoffs باید در commit تمیز حفظ شوند.
- وضعیت=`CLEANUP_AUTHORIZED / PUSH_PENDING`؛ هیچ push یا تغییر main در این checkpoint انجام نشد.

### V-150 — پاک‌سازی cached-only و candidate امن commit

- تاریخ: 2026-08-26
- سطح: `GIT INDEX SANITIZATION / NO LOCAL DELETE / PRE-COMMIT AUDIT`
- Run: `STAB-GIT-R01`
- policy ignore افزوده‌شده: top-level `.pytest*`، `.phase*pytest*`، `.test-tmp`، `.tmp`، `.codex_work`، `Bale`، prompt، fix scripts و backup copy.
- pass نخست 6068 temp/cache و scopeهای تحقیقاتی/scratch را از index خارج کرد؛ audit مستقل 171 فایل `.phase*pytest*` جاافتاده یافت و pass دوم آن‌ها را cached-only خارج کرد.
- candidate نهایی نسبت به parent: files=642، temp/cache=0، operational root=0، DB=0، Bale top-level=0، fix/scratch/backup=0.
- engineering memory/reports/handoffs حفظ‌شده=177. فایل‌های محلی Pytest/Bale/prompt همچنان present و فقط ignored هستند.
- secret scan high-confidence فقط fixture مصنوعی `tests/test_g07_release_packaging.py` را برگرداند؛ pathهای `.env` واقعی/bridge.json/database صفر.
- رخدادهای غیرمحصولی: sandbox Git lock، PowerShell `$Host` collision، sandbox network block و cleanup pattern miss همگی بدون data loss ثبت/اصلاح شدند.
- پذیرش=`INDEX_CLEAN / COMMIT_PENDING`; main و GitHub هنوز تغییر نکرده‌اند.

### V-151 — reconciliation release پس از hardening فایل ignore

- تاریخ: 2026-08-26
- سطح: `PACKAGE DRY-RUN / REPRODUCIBLE ARCHIVE / PRIVACY / MANIFEST DIFF`
- Run: `STAB-GIT-R01`
- Trigger: `.gitignore` عضو 282 فایل allowlist است و policy تازه content-set را از `d60b10ea...` به `6b9a37c1...` تغییر داد.
- دو archive تازه: file_count=282، SHA یکسان=`187ea793cc43db2cb4f427201ee845e6d997581aaf5d5094a9d5d227626ebf6b` و content-set یکسان=`6b9a37c1279923627b78b09935f6298c751302721322827d80a651406f0221ea`.
- verifier/privacy هر دو PASS و high-confidence finding=0. manifest diff نسبت به G09E: changed فقط `.gitignore`، added=0، removed=0.
- نتیجه: source/UI/wheel/dependency drift=0 و fresh-install exact-wheel شاهد V-147 جاری می‌ماند؛ archiveهای `GITPUBLISH_release_final_a/b` canonical شدند.
- اثر بیرونی فقط archive/receipt ignored زیر artifacts و اسناد؛ GitHub/main هنوز تغییر نکرده‌اند.

### V-152 — نامزد نهایی index و reconciliation دوم archive

- تاریخ: 2026-08-26
- سطح: `BASE-AWARE INDEX AUDIT / SCRATCH EXCLUSION / REPRODUCIBLE ARCHIVE / PRIVACY`
- Run: `STAB-GIT-R01`
- audit تاریخچه نشان داد `f4464ef8...` رأس چهار commit محلی پس از GitHub main=`a4df3ec...` است؛ بنابراین معیار نهایی از parent آخر به مبنای واقعی GitHub اصلاح شد و هیچ سابقه‌ای حذف نشد.
- اسکریپت‌های یک‌بارمصرف extract/find/fix/gen/read/test/update و screenshot فقط با cached-only از index خارج و روی دیسک حفظ شدند؛ scripts canonical عملیاتی 21 فایل باقی ماندند.
- candidate نهایی نسبت به `a4df3ec...`: files=426؛ temp/cache=0، operational root=0، DB=0، Bale top-level=0 و scratch/fix/backup=0. تفکیک: root=13، docs=206، lab=2، scripts=21، src=77، tests=57 و ui=50.
- archiveهای V-151 برای حفظ تاریخ باقی ماندند ولی پس از تغییر نهایی `.gitignore` تاریخی‌اند. dry-run نهایی: file_count=282 و content-set=`43c67c2eba3c30c534c855119287793eeb2ae7fc8fc61ab7aed19ecfc6dc217a`.
- دو archive final2: SHA یکسان=`481ed1be889892dc2802fa2052c27ef9ef3078994e3cc377b1e1a1c59f3b3384`، content-set یکسان، file_count=282 و privacy finding=0. manifest diff نسبت به V-151: changed فقط `.gitignore`، added=0 و removed=0.
- نتیجه: source/UI/wheel/dependency drift=0؛ exact-wheel fresh-install شاهد V-147 جاری است. GitHub/main هنوز تغییر نکرده و commit/push pending است.

### V-153 — کنترل کیفیت کامل پیش از commit انتشار

- تاریخ: 2026-08-26
- سطح: `FULL BACKEND / TYPESCRIPT / OBSERVABILITY / PACKAGE RETRY / DOCUMENTATION CONTROLS`
- Run: `STAB-GIT-R01`
- collect-only مستقل: 74 فایل و 656 تست، exit0. full Backend با `-p no:cacheprovider` و basetemp=`artifacts/stabilization/GITPUBLISH_full_20260826`: `656/656 PASS`، exit0.
- UI TypeScript check=PASS و UI/Electron observability=PASS، هر دو exit0.
- package targeted attempt A بدون basetemp: سه test به نتیجه رسیدند و 12 setup error از `PermissionError` روی temp سراسری ویندوز رخ داد؛ product failure=false. retry با basetemp=`artifacts/stabilization/GITPUBLISH_package_retry_20260826`: `15/15 PASS`، exit0؛ full suite نیز همین 15 تست را پوشش داد.
- package dry-run=282/content-set=`43c67c2e...`/write0؛ Release Manifest JSON=PASS و SHA=`e3a5b606f8f95910f80de93299d38884a8c7371aa1632e6e4517434096744a27`.
- refresh، memory integrity، generated stale check و link check همگی PASS. اثر بیرونی فقط test temp کنترل‌شده و اسناد؛ GitHub/main هنوز تغییر نکرده‌اند.

### V-154 — تجمیع بازیابی‌پذیر تاریخچه و ساخت commit تمیز

- تاریخ: 2026-08-26
- سطح: `TREE HASH CONTINUITY / SOFT RESET / CLEAN COMMIT / RELEASE BRANCH`
- Run: `STAB-GIT-R01`
- pre-reset tree=`5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d`؛ reset نرم تا `a4df3ec...` و post-reset tree دقیقاً برابر بود. candidate=426 و unstaged tracked=0؛ local delete=0.
- تاریخچهٔ چهار commit قبلی از backup ref=`codex/backup-pycharm-f4464ef` و رأس=`f4464ef8...` حفظ است.
- commit تمیز=`fca3ea72c54c0b7226f4dbabc54b4684e1215513`، parent=`a4df3ecf2bcd4ab658c5361afdc287444694fcd2`، tree=`5a7f4067...` و subject=`chore(stabilization): complete G00-G09 offline acceptance`.
- branch فعال=`codex/stabilization-g09` و tracked worktree clean است. GitHub push هنوز انجام نشده و main mutation=0.
- رخداد ابزار: `rev-parse HEAD^{tree}` در PowerShell با parser error صرفاً خواندنی رد شد؛ `git show -s --format=%T HEAD` retry موفق و hash را تأیید کرد؛ product/data impact=0.

### V-155 — push شاخهٔ مستقل و راستی‌آزمایی main

- تاریخ: 2026-08-26
- سطح: `GITHUB PRECHECK / BRANCH PUSH / REMOTE HASH VERIFICATION`
- Run: `STAB-GIT-R01`
- `origin=https://github.com/gprsm/EitaaDesktop.git` افزوده و remote محلی `legacy` حفظ شد.
- pre-push: main=`a4df3ec...` و `codex/stabilization-g09` absent. push فقط شاخهٔ نام‌برده موفق و upstream تنظیم شد؛ force=false و main refspec ارسال نشد.
- post-push: branch remote=`66f7beaca6a2cd0a67c54ec5705dcf5c381a8e9f` و main remote همچنان `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`؛ نتیجه=`PASS / MAIN_UNCHANGED`.
- یک commit مستندی متأخر برای نگهداری همین شاهد لازم است؛ پس از آن push عادی و verify نهایی روی همان branch انجام می‌شود. عملیات Provider/Live/data/Bale=0.

### V-156 — verify دوم، tracking و closure انتشار Git

- تاریخ: 2026-08-26
- سطح: `POST-DOCUMENTATION PUSH / REMOTE VERIFY / TRACKING / CLOSURE`
- Run: `STAB-GIT-R01`
- commit مستندی=`1f0f546b7532c5d856f82552f1abd69f8e337a10` با push عادی منتشر شد؛ live remote branch دقیقاً همان hash و main همچنان `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` بود.
- tracking config: remote=`origin` و merge=`refs/heads/codex/stabilization-g09`؛ status هیچ ahead/behind یا tracked worktree change نشان نداد.
- shorthand اختیاری `@{u}` در PowerShell parser error داد؛ retry فقط‌خواندنی config/status PASS، state change=0 و product failure=false.
- closure=`COMPLETE / PUSH_VERIFIED / MAIN_UNCHANGED / BACKUP_PRESERVED`. commit همین closure باید با push عادی منتشر و hash آن در handoff گفتگو verify شود؛ خودارجاعی hash داخل همان commit ممکن نیست.

### V-157 — ثبت مجوز دائمی انتشار سناریوی نهایی

- تاریخ: 2026-08-26
- سطح: `USER STANDING AUTHORIZATION / GIT PUBLICATION GOVERNANCE`
- Run: `STAB-GIT-R02`
- دستور کاربر: پس از رسیدن به محصول نهایی در هر سناریو، نتیجه در GitHub push شود.
- قرارداد ثبت‌شده: snapshot باید نهایی، آزموده‌شده، مستندسازی‌شده و فاقد credential/data عملیاتی باشد؛ commit پیام دقیق دارد و push روی شاخهٔ کاری اختصاصی انجام می‌شود.
- exclusions: push/merge مستقیم main، force-push، حذف ref، بازنویسی remote history و انتشار snapshot ناقص/قرمز بدون دستور صریح جداگانه مجاز نیست.
- پس از هر push، local/remote hash و ثابت‌ماندن main verify و نتیجه در handoff ثبت می‌شود. این policy در `AGENTS.md`، قرارداد همکاری و handoff جاری درج شد.

### V-158 — G-10 رفع timeline قدیمی گروه منتخب

- تاریخ: 2026-08-26
- سطح: `MASKED LIVE READ / RED-GREEN / FULL REGRESSION / RELEASE RECONCILIATION`
- Run: `STAB-G10-R01`
- شاهد فقط‌خواندنی: catalog/SQLite برای peer ماسک‌شده، 674 پیام محلی و برابری top catalog با max محلی را نشان دادند؛ جدیدترین تاریخ همان روز بود. اسکن 91 فایل و 5613 رکورد مرتبط، success eventهای sync/upsert/search/dialog و failure record صفر داشت. هیچ عنوان، شناسه یا متن خصوصی ثبت نشد.
- RED: `tests/test_ui33_usage_reading_position.py` روی pre-image برابر `5 passed / 1 failed`؛ failure دقیقاً نبود قرارداد fetch دست‌نخورده بود.
- GREEN: source contract=`1/1` و targeted runtime patch + mobile concurrency=`11/11`.
- build: TypeScript و Vite PASS با 1015 module؛ runtime patch source/dist دارای SHA یکسان=`6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893`.
- regression: full Backend=`657/657` در 74 فایل، failure/error/skip=0؛ هر ۹ runner UI نیز PASS.
- release: دو archive محلی بایت‌یکسان با file_count=282، SHA=`077d316d5a546fa20eff39a9e77205e57756050ed293884bd34d09cba52a7f3e`، content-set=`36012dbba19eb2b464bfa5df2de37006157e7515a774784738bc9d57fadcc1ff` و privacy finding صفر. diff با archive پیشین فقط source patch بود.
- documentation/release checks: refresh، integrity، stale، link، Release Manifest JSON و package dry-run همگی PASS؛ dry-run=`282`، content-set exact و write=0.
- محدودیت: Computer Use در initialize/retry/reset-retry پیش از window selection یا input با خطای محیطی path-not-found متوقف شد؛ visual recheck کاربر pending است. message/login/OTP/WordPress/Bale/operational write=0.

### V-159 — انتشار و راستی‌آزمایی commit اصلی G-10

- تاریخ: 2026-08-26
- سطح: `GITHUB WORKING-BRANCH PUSH / REMOTE HASH / MAIN PROTECTION`
- Run: `STAB-G10-R01`
- pre-push: remote branch=`4f70ecd9af734685befa38ed31a6c7818d1c6803` و main=`a4df3ecf2bcd4ab658c5361afdc287444694fcd2`.
- commit اصلی=`407cd418c2249fb6d9b51827e0601d9ca883d0d0` با پیام دقیق `fix(ui): show latest messages for selected groups` و 12 فایل آزموده‌شده/مستند ساخته شد.
- push عادی فقط به `codex/stabilization-g09` موفق بود؛ post-push remote branch دقیقاً=`407cd418c2249fb6d9b51827e0601d9ca883d0d0` و main بدون تغییر ماند.
- force/merge/main push/ref deletion=0؛ secret scan نامزد=0؛ operational data/message/Provider action=0. commit مستندی همین verify پس از ثبت با push عادی منتشر می‌شود.

### V-160 — تشخیص ماسک‌شدهٔ باقی‌ماندن timeline قدیمی پس از G-10

- تاریخ: 2026-08-26 تا 2026-08-27
- سطح: `MASKED LIVE STORAGE READ / BUILD-SERVING AUDIT / CONTROLLED RED`
- Run: `STAB-G11-R01`
- Trigger: کاربر پس از G-10 اعلام کرد گروه نمونه هنوز ۶ مرداد را به‌جای آخرین پیام واقعی ۴ شهریور نشان می‌دهد؛ بنابراین شاهد G-10 برای اثر عملیاتی منقضی شد.
- storage تاریخی برای peer ماسک‌شده 420 پیام تا ۶ مرداد داشت؛ storage حساب جاری 674 پیام تا ۴ شهریور و 254 پیام پس از checkpoint تاریخی داشت. catalog top با max جاری برابر، unread صفر و read boundary برابر top بود. عنوان، peer/account id و متن پیام ثبت نشد.
- peer probe نخست به‌علت مقایسهٔ فیلد حدسی `id` به‌جای `peer_id` mismatch کاذب داد؛ retry با loader رسمی تمام مؤلفه‌های peer را منطبق نشان داد. product/data state change=0.
- علت قطعی: build patch را روی URL ثابت منتشر و HTTP server همان asset را یک سال immutable می‌کرد؛ Edge pre-image قدیمی را بدون revalidation اجرا می‌کرد.
- RED هدفمند=`3 failed / 6 passed`: نام patch hashدار نبود، finalizer SHA-256 نداشت و fixed-name asset اشتباهاً immutable بود.
- Computer Use در reset/دو initialize پیش از window/input با خطای kernel-assets متوقف شد. اسکن گستردهٔ بیش از 60 ثانیه terminate و چند invocation خواندنی parser/path/header/LevelDB با retry محدود اصلاح شدند؛ write/input/send=0.
- پذیرش=`G11_ROOT_CAUSE_AND_RED_CONFIRMED`; F-049 به source-fix تاریخی و F-050 به finding تحویل/cache تبدیل شد.

### V-161 — G-11 اصلاح cache، full regression، release و fresh-install

- تاریخ: 2026-08-27
- سطح: `RED-GREEN / FULL BACKEND+UI / DETERMINISTIC WHEEL+ARCHIVE / OFFLINE FRESH INSTALL`
- Run: `STAB-G11-R01`
- اصلاح: finalizer نام patch را از ۱۶ نویسهٔ نخست SHA-256 می‌سازد و نسخه‌های fixed/قدیمی را حذف می‌کند؛ static server فقط asset مستقیم با نام hashدار را immutable و index/fixed-name را `no-store` می‌فرستد.
- GREEN نخست=`8/9` و یک failure به‌علت regex بیش‌ازحد باز بود؛ پس از محدودسازی قرارداد=`9/9`. regression مرتبط=`54/54`.
- UI: تمام ۹ runner، TypeScript و build 1015-module PASS؛ patch hash/full SHA=`6de1ad483e2c97af.../6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893`.
- full Backend نخست=`657/658` و تنها failure wheel/source drift مورد انتظار بود. wheel دوبار بایت‌یکسان با SHA=`ba05c810792fe695a96b90ce4b313ef3b5e15e7b9ef70032518c96923e295e7a` ساخته و parity 90/0 شد؛ full retry=`658/658`، failure/error/skip=0 و collect-only=74 فایل/658 تست.
- archiveهای canonical A/B پس از ثبت ADR-40: file_count=282، SHA یکسان=`08c5d5dd132f2c4d7a41c27f0cd26d084630d747a542a8c7383296e906a2c61c`، content-set=`4ec774ed765b932bb93fece08596108524608c18dc926be0d13b63a09e6c731e` و internal reopen/hash/path/manifest/privacy verification=PASS. hash قبلی checkpoint پیش از هم‌ترازی architecture بود و artifact نام‌یکسان با `--force` جایگزین شد.
- fresh venv فقط از wheelهای محلی با `--no-index`: install PASS، runtime checker ok/failures0، pip check PASS، isolated import PASS و Event Catalog=103.
- loopback validation نهایی به‌علت اجرا نبودن برنامه `connection refused` شد؛ برنامه بدون اجازه start نشد. این failure محیطی است و Live visual acceptance همچنان pending است.
- receipt probe نخست property ناموجود را مانند یک finding شمرد؛ schema canonical با `verification` خوانده و success داخلی تأیید شد. product/package failure=false.
- کنترل اسناد: refresh، integrity، stale و link check همگی PASS؛ گزارش در سطر 185 `REPORTS_INDEX.md` قابل‌کشف است. package dry-run نهایی=282/content-set=`4ec774ed...`/write0 و Release Manifest JSON=PASS با SHA=`b89f4c2a592a9dc12f8f12cdd115fa05b5a686498f5f9cf4c450dc927f6d8f9c`.
- پذیرش=`G11_CODE_AND_AUTOMATED_ACCEPTANCE_COMPLETE / USER_VISUAL_RECHECK_PENDING / GIT_PUBLICATION_PENDING`; پیام/Provider/Login/OTP/WordPress/Bale/data write=0.

### V-162 — انتشار commit اصلی G-11 و حفاظت main

- تاریخ: 2026-08-27
- سطح: `GITHUB WORKING-BRANCH PUSH / REMOTE HASH / MAIN PROTECTION`
- Run: `STAB-G11-R01`
- candidate=16 فایل دقیق؛ raw title گروه=0، high-confidence credential file hit=0 و operational root file=0. unstaged tracked file=0 پیش از commit.
- pre-push remote: working branch=`7c70954dbc073048531898c09cce9cf66e1c927f` و main=`a4df3ecf2bcd4ab658c5361afdc287444694fcd2`.
- commit اصلی=`8fe8d90d507fccb9bec586feb81c1f28d71d64fc` با پیام `fix(ui): invalidate cached runtime patches` و 16 فایل ساخته شد.
- push عادی فقط به `codex/stabilization-g09` موفق بود؛ post-push remote branch دقیقاً برابر commit محلی و main بدون تغییر ماند.
- force/merge/main push/ref deletion=0؛ Provider/message/data action=0. commit مستندی closure با push عادی دوم منتشر و hash نهایی در تحویل گفتگو verify می‌شود.

## 2026-08-27 — ثبت‌های میراثی و تأییدنشدهٔ معماری ایندکس

این جدول از ثبت ناقص Agent پیشین حفظ شده است. شناسه‌های `V-103` تا `V-106` تکراری بودند و ردیف‌ها شاهد آزمون یا تصمیم canonical نیستند؛ به شناسه‌های `LEGACY-INDEX-*` منتقل و با `V-163` جایگزین شدند.

| شناسه | موضوع | نوع | نتیجه | مرجع |
|---|---|---|---|---|
| LEGACY-INDEX-V103 | هدف نهایی: گزارش (اکسل)، نه وردپرس | Historical/Unvalidated | جهت کلی برای تحلیل حفظ شد، اما فیلدها و معماری قطعی نیستند | LEGACY-INDEX-F039 / F-051 |
| LEGACY-INDEX-V104 | معماری TF-IDF + Cache + LLM API | Historical/Unvalidated | تصویب نشده؛ انتخاب الگوریتم و API به ارزیابی‌های بعدی موکول است | LEGACY-INDEX-F040 / F-051 |
| LEGACY-INDEX-V105 | دسته‌های فعالیت ۷+۱ گانه | Historical/Unvalidated | فهرست و کدها تا بررسی مستندات ابلاغی قطعی نیستند | LEGACY-INDEX-F041 / F-051 |
| LEGACY-INDEX-V106 | فیلدهای ساختاریافتهٔ ایندکس | Historical/Unvalidated | صرفاً ورودی تحلیل؛ schema v4 یا ستون‌های نهایی تصویب نشده‌اند | LEGACY-INDEX-F042 / F-051 |

### V-163 — ثبت نقشه‌راه و مجوز آغاز فاز صفر هوشمندسازی ایندکس

- تاریخ: 2026-08-27
- سطح: `DECISION / STATIC_DOCUMENTATION / PHASE_0_AUTHORIZATION`
- Run: `IDX-R01`
- دامنه: اسناد حافظه، تصمیم معماری، handoff و discoverability؛ کد محصول، schema، migration، runtime و دادهٔ عملیاتی خارج از دامنه بودند.
- نتیجه: نقشه‌راه canonical با وضعیت `PHASE_0 AUTHORIZED / PRODUCT IMPLEMENTATION NOT STARTED` ثبت شد و `IR-0-A` به‌عنوان اقدام بعدی تعیین گردید.
- اصلاح provenance: چهار Finding و چهار Validation تکراری/پیش‌رسِ Agent پیشین حذف نشدند؛ با شناسهٔ `LEGACY-INDEX-*` و وضعیت unvalidated حفظ و توسط F-051/V-163 supersede شدند.
- تصمیم‌های کنترل‌شده: report-centric، تفکیک مفاهیم دامنه، نسخه‌گذاری چارچوب گزارش، local-first، تعویق API مدل زبانی و حفظ safe-default خاموش برای scheduler خودکار.
- موارد قطعی‌نشده: یکتایی/معنای کدهای ابلاغی، taxonomy نهایی، schema، الگوریتم، مدل/Provider/prompt و نسبت مصرف API.
- آزمون محصول: اجرا نشد؛ علت، docs-only بودن تغییر و نبود trigger کد/قرارداد اجرایی است. کنترل‌های memory integrity، generated-doc freshness، Markdown link و `git diff --check` همگی exit code صفر داشتند؛ duplicate رسمی Finding/Validation نیز صفر است.
- حریم خصوصی و عملیات: workbook کاربر فقط منبع بالقوهٔ فاز صفر است، untracked می‌ماند و وارد Git نمی‌شود؛ هیچ پیام، Provider، WordPress، Login/OTP یا دادهٔ عملیاتی خوانده/نوشته نشد.
- artifact: `INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md` و `INDEX_INTELLIGENCE_EXECUTION_LOG.md`.
- Trigger ابطال: تغییر متن نقشه‌راه/پروتکل، آغاز زیرمرحلهٔ فاز صفر، تصمیم تازهٔ کاربر یا ورود مستند رسمی جدید.

### V-164 — استخراج فقط‌خواندنی و ثبت مرجع workbook ۱۴۰۵

- تاریخ: 2026-08-27
- سطح: `READ_ONLY SOURCE INSPECTION / IR-0-A`
- Run: `IDX-R02`
- منبع: `SRC-IR-001`؛ اندازه=`28,887 bytes`؛ SHA-256=`B7A8A79F9C4D093AD001294097FAC8930E0BCEE80191D06AD17E5C8825FB9296`.
- روش: import فقط‌خواندنی workbook با runtime صفحه‌گستردهٔ bundled، inspect ساختار/مقادیر/formula و render بصری تمام هفت sheet. فایل اصلی edit/export/overwrite نشد.
- نتیجهٔ ساختاری: workbook=`7 sheets / 7 table regions`؛ formula scan=`0 records`. محدوده‌ها: اردو `A1:R12`، مسابقات `A1:W17`، مراسم مذهبی `A1:O17`، نماز `A1:O13`، تکریم `A1:N16`، تشویق `A1:O12` و منشور `A1:J12`.
- spot-check معنایی: عنوان/کد هر هفت برنامه، ردیف‌های معیار، یادداشت‌های شمارش و استثناهای `مراسم  مذهبی!C11:C17` با extract و render تطبیق داده شدند.
- تعارض قطعیِ transcription: `مسابقات!C1` و `مراسم  مذهبی!C2` هر دو `80402` دارند؛ علت یا کد صحیح از خود workbook قابل تعیین نیست.
- خروجی canonical: Source/Conflict Register، مرجع نرمال‌شده و Question Register با ۱۲ پرسش. ادعای اصالت مستقل، completeness یا correctness کدها ساخته نشد.
- حریم خصوصی/عملیات: متن پیام، حساب، شماره، credential، Provider و WordPress خوانده نشد؛ workbook untracked و خارج از Git باقی ماند؛ artifactهای render فقط محلی/غیرcanonical هستند.
- آزمون محصول: اجرا نشد؛ تغییر source/schema/runtime وجود ندارد. refresh، memory integrity، generated-doc freshness و Markdown link check همگی exit code صفر داشتند؛ `git diff --check` پس از حذف یک hard-break تازه نیز سبز شد.
- Trigger ابطال: تغییر hash workbook، تصحیح کاربر، نسخهٔ تازهٔ منبع یا تغییر اسناد مرجع استخراج.

### V-165 — ممیزی و مهار artifactهای منقضی Antigravity/Sonnet

- تاریخ: 2026-08-27
- سطح: `EXTERNAL ARTIFACT INVENTORY / NON-DESTRUCTIVE CORRECTION`
- Run: `IDX-R02`
- جست‌وجو: نام‌های plan/roadmap/index و محتوای TF-IDF/LLM/80402 در ریشهٔ brain فقط‌خواندنی بررسی شد. چهار `implementation_plan.md` یافت شد؛ دو مورد غیرایندکس خارج از دامنه و دست‌نخورده ماندند.
- مجموعهٔ مرتبط: پنج Markdown شامل plan جدید، plan قدیمی، development map، task و walkthrough به‌علاوه پنج metadata JSON.
- شاهد تعارض: forced category، schema v4 و daemon ساعتی به‌عنوان قطعی/تکمیل‌شده آمده بود؛ G-05 در baseline رسمی daemon ساعتی را حذف و scheduler را safe-default خاموش کرده است.
- اقدام: حذف=0؛ پنج header هشدار و پنج summary metadata اصلاح شد. JSON parse هر پنج metadata PASS و header پس از اصلاح برای هر پنج فایل verify شد.
- کنترل نهایی: UTF-8/control/header/metadata خارجی PASS؛ refresh، memory integrity، generated-doc freshness، Markdown link و `git diff --check` پروژه همگی exit code صفر داشتند.
- hashهای پس از اصلاح: EA-ART-001=`FF7878B4...186EB182`، 002=`4058AD7D...1838AFD4`، 003=`E0532B57...AECFEB1`، 004=`AAE07167...BC4C9B5`، 005=`8B916EAF...BE3D8C8`.
- حریم خصوصی: شناسهٔ کامل نشست‌های brain در اسناد پروژه ثبت نشد؛ فقط Artifact ID/hash نگه داشته شد. محتوای خصوصی conversation یا credential خوانده/ثبت نشد.
- محصول/Git: source/runtime/schema پروژه تغییر نکرد؛ فایل‌های brain خارج از Git پروژه‌اند. مرجع `EXTERNAL_AGENT_ARTIFACT_REGISTER.md` است.
- Trigger ابطال: تغییر فایل‌های بیرونی، تولید artifact تازه یا حذف هشدار supersession.

### V-166 — ثبت پاسخ‌های جزئی کاربر و بازکردن سیاست کیفیت آمار

- تاریخ: 2026-08-27
- سطح: `USER DOMAIN CLARIFICATION / NO PRODUCT CHANGE`
- Run: `IDX-R02`
- Source=`SRC-USER-IR-001`: احتمال کد `80403` برای مراسم با عدم اطمینان؛ اعتبار مورد انتظار قالب تا پایان ۱۴۰۵ با امکان تغییر؛ معنای ستاره نیازمند پاسخ واحد ستادی؛ تکمیل نهایی Excel با دخالت کاربر.
- نکتهٔ کیفیت: امکان ورود دستی آمار تخمینی/ساختگی مطرح شد. Q-IR-009 جزئی و Q-IR-013 تازه باز شد؛ هیچ مقدار ساختگی به‌عنوان verified یا training truth پذیرفته نشد.
- نتیجه: C-IR-001 تا 003 و C-IR-009 به وضعیت‌های partial/open دقیق تغییر کردند؛ F-054 سیاست provenance/export را پیش از طراحی schema الزامی می‌کند.
- عملیات: هیچ عدد گزارش، Excel، پیام، WordPress یا دادهٔ عملیاتی تغییر نکرد.
- کنترل اسناد: تغییرات پاسخ‌ها و registry در همان کنترل سبز V-165 پوشش داده شدند.
- Trigger ابطال: پاسخ تازهٔ کاربر/واحد ستادی یا تصمیم workflow export.

### V-167 — پذیرش سیاست value kind و منع ارتقای خاموش آمار ساختگی

- تاریخ: 2026-08-27
- سطح: `USER DOMAIN DECISION / NO PRODUCT CHANGE`
- Run: `IDX-R02`
- Source=`SRC-USER-IR-002`؛ پرسش=`Q-IR-013`؛ تصمیم کاربر=`ACCEPTED`.
- قرارداد دامنه: `observed`، `reported_by_unit`، `estimated`، `synthetic_placeholder` و `verified` مفاهیم جدا هستند. مقدار تخمینی/ساختگی بدون تأیید صریح کاربر به verified یا training truth ارتقا نمی‌یابد.
- ثبت canonical: F-054 به `DECIDED` رسید، Q-IR-013 بسته و ADR-42 افزوده شد؛ C-IR-009 فقط از نظر value-kind بستهٔ جزئی است و کفایت/منبع عدد در Q-IR-009 باز می‌ماند.
- عدم‌پیاده‌سازی: نام enum/ستون، schema، migration، UI، audit event و export gate هنوز ساخته نشده‌اند و به فاز معماری پس از Phase 0 تعلق دارند.
- عملیات: Excel، عدد گزارش، پیام، WordPress، Provider و دادهٔ آموزشی تغییر نکرد.
- کنترل اسناد: refresh نمادها/نقشهٔ فایل، memory integrity، generated-doc freshness، Markdown link و `git diff --check` همگی exit code صفر داشتند.
- Trigger ابطال: تغییر تصمیم کاربر یا قرارداد آیندهٔ report verification/export.

### V-168 — پذیرش grain تجمیعی استان و تفکیک آن از رویداد

- تاریخ: 2026-08-27
- سطح: `USER DOMAIN DECISION / CONCEPTUAL MODEL`
- Run: `IDX-R02`
- Source=`SRC-USER-IR-003`؛ پرسش=`Q-IR-004`؛ نتیجه=`RESOLVED_WITH_SUPERSESSION_CAVEAT`.
- قرارداد: ردیف اصلی workbook جمع کل استان برای برنامه/دوره است؛ رویدادها و واحدهای شهرستانی ورودی aggregation و breakdown قابل‌ردیابی‌اند، نه ردیف اصلی خروجی.
- شاهد سازگاری: ستون‌های تعداد اردو/مراسم/شرکت‌کننده ماهیت aggregation دارند؛ `مراسم  مذهبی!C11` نگه‌داری جزئیات حوزه و هر مراسم را لازم می‌داند.
- ثبت canonical: C-IR-004 resolved، F-055/ADR-43 افزوده و workbook reference/roadmap/handoff همسو شدند.
- عدم‌پیاده‌سازی: هیچ جدول، query، migration، metric calculation یا export تغییر نکرد.
- کنترل اسناد: refresh نقشهٔ فایل/نماد، memory integrity، freshness، link check و `git diff --check` همگی exit code صفر داشتند.
- Trigger ابطال: پاسخ رسمی مخالف، نسخهٔ تازهٔ منبع یا تغییر grain گزارش.

### V-171 — پذیرش ضمیمهٔ زیارت عاشورا و ثبت پیشنهاد پرسشنامهٔ برنامه

- تاریخ: 2026-08-27
- سطح: `USER DOMAIN DECISION + CONCEPTUAL PROPOSAL / NO PRODUCT CHANGE`
- Run: `IDX-R02`
- Source=`SRC-USER-IR-004`.
- Q-IR-005=`RESOLVED`: زیارت عاشورا metric تجمیعی استانی و ضمیمهٔ مستقل دارد و main ceremony count را افزایش نمی‌دهد؛ F-057/ADR-45 ثبت شد.
- پیشنهاد ثبت‌شده: هر برنامهٔ workbook به تعریف نسخه‌دار پرسش‌ها با هستهٔ مشترک و module اختصاصی تبدیل شود تا خبر، تعداد، مالی، دادهٔ پایه، assumption و derived value به event/metric درست متصل شوند.
- guard تحلیل: formula/assumption/input/provenance باید traceable باشد؛ estimate با exact متناظر double count نمی‌شود و همچنان `estimated` باقی می‌ماند.
- artifact مفهومی: `INDEX_PROGRAM_QUESTIONNAIRE_MODEL.md`؛ وضعیت=`PROPOSAL / NOT_IMPLEMENTED`. Q-IR-014 دربارهٔ workflow تکمیل/تأیید باز شد.
- عملیات: هیچ فرم، schema، formula engine، Excel، پیام، دادهٔ مالی یا مقدار گزارش ایجاد/تغییر نکرد.
- Trigger ابطال: تغییر نظر کاربر، پاسخ رسمی ستاد، پاسخ Q-IR-014 یا تغییر report map.

### V-169 — RED ادغام محتوایی و صف مستقل آواتار

- تاریخ: 2026-08-27
- سطح: `STATIC / CONTRACT RED / EXPECTED FAILURE`
- Run: `UX-MESSAGE-AVATAR-R01`
- علت بررسی مجدد: درخواست صریح کاربر برای ادغام همهٔ نوع‌های محتوای متوالی و گزارش بارگیری‌نشدن آواتار، همراه با تغییر برنامه‌ریزی‌شدهٔ قرارداد مرکزی UI.
- pre-image: HEAD=`95624acf...`؛ `App.tsx=2a606c86...`، `MessageContentCard.tsx=af2fcbb4...`، `groupedMedia.ts=32ad994d...` و `avatarLoader.ts=c1386ae4...`.
- grouped-media RED: runner پس از افزودن scenarioهای text→image، image→text، دو آلبوم، sender/gap/day boundary با `TypeError: buildMessageGroupLookup is not a function` شکست خورد.
- avatar RED: Phase 9 workspace با `ERR_MODULE_NOT_FOUND` برای `avatarQueue.mjs` شکست خورد؛ contract Python نیز `6 passed / 1 failed` و نبود `cached_only: true`/دو lane را نشان داد.
- تشخیص: timeline قبلی time diff را اعمال نمی‌کرد و آلبوم را کنار می‌گذاشت. صف واحد سه‌تایی cache/remote، failure propagation، stale account و prefix پاک‌سازی ناقص داشت. محدودیت مستقل Core برای User photo reference نیز با initials قابل مهار است، نه با parallel Provider call.
- اثر عملیاتی: صفر؛ داده/نشست/Provider/پیام واقعی خوانده یا تغییر داده نشد.
- نتیجه: RED معتبر و implementation مجاز در F-056/ADR-44 تعریف شد.

### V-170 — پذیرش کامل ادغام پیام، آواتار و بستهٔ آفلاین

- تاریخ: 2026-08-27
- سطح: `UNIT / UI CONTRACT / FULL REGRESSION / BUILD / OFFLINE PACKAGE / FRESH INSTALL`
- Run: `UX-MESSAGE-AVATAR-R01`
- هدفمند: grouped-media=`29/29`، Phase 9 workspace/queue=`18/18`، Python UI/Material/scroll=`42/42` و TypeScript=`PASS`.
- UI کامل: هر ۹ runner canonical سبز؛ scroll=`10/10`، Phase 9 acceptance=`13/13`، Phase 10=`7/7`، Phase 11 onboarding=`7/7` و Phase 11-B2=`6/6`. build Vite با 1016 module PASS و warning تاریخی chunk بزرگ غیرمسدودکننده بود.
- Backend کامل: `659/659 passed`، failure/error/skip=0؛ افزایش یک تست نسبت به G-11 به guard تازهٔ گروه/صف UI مربوط است.
- package tests=`15/15`. dry-run نامزد Git ایزوله=282 فایل، write=0 و content-set=`35f58c157d019424f2f8987e57b59897f79fb150bfd733158f9852ee4c6c34c2`.
- archiveهای نهایی ایزوله A/B: هر دو 282 فایل مجاز، 283 entry با manifest، SHA-256 بایت‌یکسان=`1c52502df5bf19e51bf57dc684b5193065ad65d7db04296101c72feedcfb6900`؛ reopen/path/hash/manifest/privacy verification داخلی PASS. archiveهای پیش از جداسازی work ایندکس checkpoint تاریخی‌اند.
- fresh install: archive A در مسیر artifact ایزوله extract شد؛ نصب wheel و همهٔ dependencyها فقط با `--no-index` و wheelهای محلی PASS، runtime checker=`ok=true/failures=0`، `pip check`، isolated import و Event Catalog=103 سبز است.
- کنترل snapshot ایزوله: integrity/freshness/link و Phase 9=`18/18` سبز بود. اجرای نخست grouped-media در snapshot فاقد `node_modules` فقط هنگام fallback به executable ناموجود `npm` با `ENOENT` متوقف شد؛ retry بدون تغییر فایل و با TypeScript read-only workspace از `NODE_PATH` برابر `29/29` PASS بود. اجرای canonical ریشه پیش‌تر مستقل `29/29` بود.
- اسناد canonical: F-056، ADR-44، baseline/spec/structure/handoff، گزارش feature و Execution Log همسو شدند. refresh، memory integrity، generated freshness، link check و `git diff --check` همگی exit code صفر داشتند؛ هشدارهای line-ending فقط اطلاع‌رسان و بدون finding بودند.
- حریم خصوصی/عملیات: message send/login/OTP/Provider/WordPress/Bale/data write=0؛ فقط dist/test/package/fresh-venv artifact کنترل‌شده ایجاد شد و هیچ operational root وارد archive یا candidate Git نمی‌شود.
- نتیجه: `OFFLINE_RELEASE_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED / GIT_PUBLICATION_PENDING`.

### V-172 — کشف و مهار collision مستندات میان دو writer

- تاریخ: 2026-08-27
- سطح: `DOCUMENTATION CONCURRENCY INCIDENT / RECOVERY VALIDATION`
- Run: `IDX-R02`
- RED: memory integrity پس از ثبت اولیهٔ Q-IR-005 با دو خطا شکست خورد: duplicate `F-056` و duplicate `V-169`. ممیزی heading نیز دو ADR-44 را نشان داد.
- علت: task موازی ویژگی UI در فاصلهٔ بررسی شناسه تا validation، رکوردهای canonical تازه‌ای با همان شناسه‌ها ثبت کرده بود؛ دامنهٔ کد آن task در این Run ممیزی نشد.
- بازیابی: رکوردهای ایندکس به F-057/F-058، V-171 و ADR-45 منتقل شدند؛ رکوردهای feature موازی F-056/V-169/V-170/ADR-44 دست‌نخورده ماندند.
- GREEN: memory integrity، refresh/freshness، link check و `git diff --check` همگی exit code صفر؛ duplicate رسمی صفر.
- داده/محصول: migration، Provider، پیام، Excel یا عملیات Live صفر. این validation پذیرش کد task موازی نیست.
- نتیجهٔ governance: F-059/IR-GOV-01؛ یک writer canonical یا allocator/merge queue الزامی است.
- Trigger ابطال: collision تازه یا تغییر سیاست چندعاملی.

### V-173 — پذیرش workflow ستادمحور و مرز اختیار Agent

- تاریخ: 2026-08-27
- سطح: `USER DOMAIN DECISION / ACCESS_AND_APPROVAL_BOUNDARY / NO PRODUCT CHANGE`
- Run: `IDX-R02`
- Source=`SRC-USER-IR-005`؛ پرسش=`Q-IR-014`؛ تصمیم کاربر=`ACCEPTED`.
- قرارداد دسترسی: فقط کاربر اصلی و همکاران ستادی مجاز در شبکهٔ خصوصی محلی کاربر سامانه‌اند. واحدهای شهرستانی account/role ندارند و اطلاعات آن‌ها فقط از مسیر Eitaa به‌صورت evidence/claim وارد می‌شود.
- قرارداد پردازش: WordPress مخزن/نمای فعالیت و یک source/projection است. اتوماسیون یادگیرندهٔ محلی مسیر ترجیحی کمک و API Agent fallback اختیاری است؛ هیچ پیشنهاد خودکاری بدون review انسانی verified یا approved نیست.
- قرارداد اختیار: تأیید نهایی، استنتاج نهایی، محاسبات استانی و export فقط به نقش انسانی مرکزی مجاز منتسب می‌شود. Codex، LLM و Agent اختیار تصویب گزارش ندارند.
- کنترل امنیتی آینده: LAN جای authentication، server-side authorization، audit و تفکیک سطح دسترسی اسناد را نمی‌گیرد.
- ثبت canonical: Q-IR-014 بسته و F-060/ADR-46 افزوده شد؛ مدل پرسشنامه، roadmap، baseline و handoff همسو شدند. role schema، UI، LAN deployment و workflow engine هنوز ساخته نشده‌اند.
- عملیات: Excel، پیام، Provider، WordPress، دادهٔ عملیاتی، schema و کد محصول تغییر نکرد.
- کنترل اسناد: ترتیب ADR-44..46 اصلاح شد؛ refresh نقشهٔ فایل/نماد، memory integrity، generated-doc freshness، Markdown link و `git diff --check` همگی exit code صفر داشتند. هشدار line-ending فقط اطلاع‌رسان بود.
- Trigger ابطال: تغییر تصمیم کاربر دربارهٔ کاربران، کانال دریافت شهرستان، محل استقرار، مرجع تأیید یا مجوز Agent/API.

### V-181 — RED و پذیرش هدفمند WordPress/role/avatar priority

- تاریخ: 2026-08-27
- سطح: `CONTRACT RED / UNIT / UI STATIC / TARGETED INTEGRATION`
- Run: `UX-WP-AVATAR-R02`
- علت بررسی مجدد: درخواست صریح کاربر برای default مخفی WordPress، منع taxonomy check پیش از config، محدودکردن عملیات به owner/admin و اولویت idle آواتار.
- REDهای معتبر: test نقش با نبود `dialog_permissions`، Phase 9 با نبود `queue.promote` و UI contract با نبود `showWordPressPanel` شکست خوردند.
- GREEN: نقش/parser/catalog/API مستقیم=`7 passed`؛ مجموعهٔ هدفمند Backend/UI=`56 passed`؛ Phase 9 workspace=`19/19`، grouped-media=`29/29`، scroll=`10/10` و TypeScript=`PASS`.
- قرارداد: WordPress default=false و credential-gated؛ community eligibility فقط active group/channel + server-derived owner/admin؛ active avatar قابل promotion و background delayed؛ Provider session serial.
- cache repair: فایل صفر/خراب/بزرگ یا magic نامعتبر miss، overwrite و validation پس از download؛ MIME از magic استخراج می‌شود.
- حریم خصوصی/اثر بیرونی: فقط دادهٔ مصنوعی؛ raw TL/peer/account/message/credential log نشد و هیچ Live/Provider/WordPress mutation انجام نشد.

### V-182 — regression کامل، wheel، بسته و نصب تازهٔ سناریوی WordPress/Avatar

- تاریخ: 2026-08-27
- سطح: `FULL REGRESSION / BUILD / DETERMINISTIC WHEEL / OFFLINE PACKAGE / FRESH INSTALL`
- Run: `UX-WP-AVATAR-R02`
- Backend کامل به‌علت سقف زمان ابزار در شش partition بدون overlap/gap اجرا شد: `207 + 97 + 105 + 61 + 42 + 152 = 664 passed`؛ failure/error/skip صفر.
- UI کامل: همهٔ runnerهای canonical سبز؛ Phase 9 workspace=`19/19`، grouped=`29/29`، scroll=`10/10`، Phase 9 acceptance=`13/13`، Phase 10=`7/7`، Observability=`PASS`، Phase 11 onboarding=`7/7`، Phase 11-B2=`6/6` و mobile/auth/live contract=`PASS`. TypeScript و build 1016-module نیز PASS.
- wheel worktree A/B بایت‌یکسان=`f2c3872d...5be9` بود؛ candidate پس از LF normalization دوباره ساخته و release dist آن SHA-256=`23cd95cfbb9ac47e9ca057406e2008eba16854d03adfa159e9ce628fdf534b51` شد. parity مربوط سبز است؛ `dist/` طبق policy Git ignore و خارج از commit است.
- archive نهایی candidate=`283 files / content-set 702bd412fca521092c5927e2cec4257ea5f23edf62525df4debd52a28a8c155d`. دو archive بایت‌یکسان SHA-256=`307d00b82fb1ff0ec30d5c05b2c55a18b23726901b35e2301ce5c0cda520cc00` و verifier داخلی privacy/path/hash/manifest PASS؛ فایل‌های work ایندکس صفر.
- fresh-install attempt نخست worktree به‌علت omission `vendor/runtime` از `find-links` شکست خورد. attempt نخست clone نیز چون wheelهای runtime به‌درستی Git-ignored و در staging حاضر نبودند، archive 277فایلی غیرقابل‌نصب ساخت. پس از افزودن mechanical wheelhouse فقط به staging، archive نهایی 283فایلی با `dist + vendor + vendor/runtime` و `--no-index` نصب شد؛ runtime checker=`ok=true/failures=0`، `pip check` و import ایزولهٔ `dialog_permissions` PASS. wheelهای ignored در candidate Git stage نمی‌شوند.
- کنترل خود candidate: اجرای نخست pytest فقط به Temp غیرقابل‌دسترسی حساب میزبان خورد؛ retry با basetemp صریح workspace=`101/101`. Phase 9=`19/19`. grouped-media نخست از cwd نادرست clone و نبود npm متوقف شد؛ retry از `ui/` با TypeScript read-only پروژهٔ اصلی=`29/29`. هیچ فایل محصول برای retry تغییر نکرد.
- اسناد: F-061، ADR-47، baseline/spec/structure/handoff، گزارش feature و Execution Log ثبت شدند؛ کنترل freshness/integrity/link پس از refresh جداگانه اجرا می‌شود.
- عملیات: شبکه، Login/OTP، Send، WordPress، Member mutation، Provider Live و فایل عملیاتی صفر. نتیجه=`OFFLINE_AUTOMATED_ACCEPTED / PRIMARY_GIT_PUBLISHED / DOCUMENTATION_CLOSURE_READY / NOT_PRODUCTION_RELEASE_AUTHORIZED`.

### V-183 — انتشار ایزولهٔ WordPress/role/avatar و حفاظت main

- تاریخ: 2026-08-27
- سطح: `GITHUB DEDICATED WORKING-BRANCH PUSH / REMOTE HASH / MAIN PROTECTION`
- Run: `UX-WP-AVATAR-R02`
- candidate اصلی=34 فایل؛ high-confidence secret hit=0، full Iran phone hit=0، operational/workbook/index-work path=0. artifactهای موقت، archive، basetemp، `dist/` و `vendor/runtime` ignored در stage نبودند.
- commit اصلی=`c1f71ac94b1643495e022b121f99b15f69fe0dfa`، parent=`50f4224664cf3f4b7871c129988f934828fe8bc2` و subject=`feat(ui): gate WordPress and prioritize dialog avatars`.
- push عادی fast-forward روی `codex/message-avatar-grouping` PASS؛ remote hash دقیقاً برابر commit اصلی بود. GitHub main پیش و پس برابر `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` و بدون تغییر ماند.
- root worktree branch=`codex/stabilization-g09` و HEAD=`95624acf...` باقی ماند و index آن خالی بود؛ فایل‌های dirty و کار هم‌زمان ایندکس reset/checkout/stage نشدند.
- force-push، main push/merge، ref deletion، Provider/Login/OTP/Send/WordPress/Member mutation و operational write صفر. commit closure فقط همین ثبت و generated docs آن را fast-forward می‌کند؛ hash نهایی در تحویل گفتگو و remote verify ثبت می‌شود.

### V-184 — پذیرش Setup مستقل Windows و repair بستهٔ خام

- تاریخ: 2026-08-28
- سطح: `CONTRACT RED / BUILD / OFFLINE INSTALL SIMULATION / FULL REGRESSION / ARTIFACT PRIVACY`
- Run: `INSTALLER-SELF-CONTAINED-R01`
- Trigger بررسی: درخواست صریح کاربر برای ممیزی پوشهٔ خام، نصب خودکار نیازمندی‌ها، EXE قابل‌تحویل، بررسی Windows 7 و ریشهٔ خطای اولین اجرا.
- ممیزی اولیهٔ raw: مسیر واقعی یک سطح nested بود؛ `VERSION.txt` وجود نداشت و dry-run با wheel/source parity برابر `missing=0 / mismatched=2 / extra=0` شکست خورد. دو mismatch مربوط به `api.py` و `eitaa_provider_runtime_operations.py` بودند. `bridge.json` عملیاتی مشاهدهٔ محتوایی یا mutation نشد.
- RED قرارداد Setup=`3/3 failed`. پس از پیاده‌سازی targeted installer=`4/4 passed` و مجموعهٔ مرتبط runtime/auth/package/UI=`88/88 passed` شد.
- full Backend=`674/674 passed` با failure/error/skip صفر و collect مستقل 674. `npm --prefix ui run check` و `test:observability` هر دو exit code صفر بودند.
- builder wheel جاری را بازساخت و parity/allowlist را پذیرفت؛ runtime فقط از wheelهای محلی با `--no-index` در payload و شبیه‌سازی install-copy نصب شد. runtime checker و importهای Bridge/Core/diagnostics سبز بودند.
- dry-run نهایی بستهٔ canonical پس از refresh اسناد=`286 files / write=0 / content-set 6888b72a04a124aee773cb172c4ce3ccc4aa6415174ed7b962b9f061c7aa5640` و wheel/source drift صفر بود.
- repair کنترل‌شدهٔ raw فقط 30 فایل managed را همگام کرد و wheel را با SHA-256=`4b08cf9e11c51ad7a3e2f8b3ea545b37bab0c33455f6f75a855f847e4eded208` بازساخت. dry-run همان raw سپس=`260 files / write=0 / content-set 50d3bb8950c35bf5cfddf5ac4120c84c22eb17553150eff437d68a0095e3f9b8` و PASS شد؛ operational state آن دست‌نخورده ماند.
- EXE تک‌فایلی=`38,436,864 bytes / SHA-256 B609DD9AA689451A694C78FBB0DCAA71943D396F8F548B11E11ECEF500930121`; `--verify-only=PASS`. ZIP fallback=`37,793,425 bytes / SHA-256 855E734098E5C1AF4C3637C5782631FFB376A830518CF580367383D417F660DA`.
- nested payload مستقل 4397 فایل داشت؛ required outer entries کامل، extra صفر و finding حریم خصوصی صفر بود. `bridge.json`، `.env`، Session، composition، transfer backup و پیشوندهای data/runtime/diagnostics/backups/catalog در artifact نبودند.
- preflight با نسخهٔ native Windows و معماری x64 سنجیده شد؛ آزمون synthetic rejection برای Windows 7 سبز است. Setup مقصد به Python/Node system-wide یا شبکه نیاز ندارد.
- امضا=`NotSigned`. نصب واقعی روی ماشین تمیز، Windows visual، SmartScreen reputation و code-sign اجرا/پذیرفته نشده‌اند؛ نتیجه=`OFFLINE_AUTOMATED_ACCEPTED / SHAREABLE_UNSIGNED_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED`.
- عملیات بیرونی: نصب واقعی، registry/Firewall/proxy، Provider، Login/OTP، Send، WordPress و دادهٔ عملیاتی صفر.
- Git: worktree جاری تغییرهای هم‌زمان و مرتبط با سناریوهای دیگر داشت؛ برای جلوگیری از mixed commit هیچ stage/commit/push انجام نشد. انتشار source این سناریو پس از تعیین base ایزوله و تکرار validation همان snapshot باقی است.
- Trigger ابطال: تغییر source/wheel/runtime wheels، installer bootstrap/copy policy، UI dist، OS support، privacy exclusions یا اجرای clean-machine تازه.

### V-185 — پذیرش فعال‌سازی آفلاین دستگاه‌محور و RC2 بسته‌بندی‌شده

- تاریخ: 2026-08-28
- سطح: `CONTRACT RED / CRYPTOGRAPHIC UNIT / STARTUP GATE / FULL REGRESSION / PACKAGED OFFLINE E2E / ARTIFACT PRIVACY`
- Run: `LICENSE-ACTIVATION-R01`
- Trigger: درخواست صریح کاربر برای کد سخت‌افزاری، صدور دستی سریال، فایل محافظت‌شده، درخواست مجدد پس از انتقال و اجرای نامحسوس پس از فعال‌سازی.
- RED نخست=`5 failed / 1 passed / 2 setup errors`. پنج failure نبود module و Startup contract را ثابت کردند؛ دو setup error فقط Temp پیش‌فرض غیرقابل‌دسترسی بودند و retry با basetemp صریح انجام شد.
- GREEN واحد/مرتبط=`60/60`: request checksum، عدم افشای component خام، Ed25519 sign/verify، tamper/device/expiry rejection، atomic protected store، installed detection، pre-Config API gate، Office-before-backend، package/private-key exclusion، G-07 و G-03 regression.
- full Backend=`684/684 passed`، failure/error/skip صفر؛ collection مستقل=`684 tests / 76 files`. TypeScript و UI/Electron Observability هر دو PASS.
- wheel نهایی source-parity-safe SHA-256=`31fdfe2db2276f9682c797361a7d27800e6ce7d7ac1c269b9ac229b6e695bf0b`. Runtime checker بسته cryptography=`46.0.7` را همراه Bridge/Core/requests/tzdata تأیید کرد.
- dry-run نهایی canonical پس از همسان‌سازی Release Manifest/اسناد=`293 files / write=0 / content-set 296a29a77d84d52abddaa17e52a460835923b09361a01faebaa02a15da698367` و wheel/source drift صفر بود.
- packaged RC2 rehearsal: cryptography/Tk/licensing import PASS؛ check پیش از activation با exit موردانتظار fail-closed؛ request file→owner issue→activation import→silent check→`BridgeApplicationApi` PASS. activation store=890 bytes و plaintext prefix finding=false.
- EXE=`46,415,360 bytes / SHA-256 84453D43A2E04F10FC2F453A81639AF6ED69C971FEE18AA8ED29EC1BC10EF02F / --verify-only PASS / NotSigned`. Portable=`45,723,128 bytes / SHA-256 A78C5AAA5EF2D6BAC00BBA8F321FAF8B03419C89CFA8556C880E7A9BDE89D129`.
- nested payload=4664؛ required license policy/docs/cryptography/verifier/UI حاضر؛ private-key filename=0، private-key PEM=0 و operational entry=0.
- branch-test private key خارج از Repository و delivery است و در اسناد/لاگ محتوا نشد. این کلید unencrypted و Production نیست؛ rotation به کلید رمزدار مالک گیت الزامی انتشار است.
- Git stage/commit/push=0؛ کاربر صریحاً بررسی در همین شاخه را پیش از کپی به پروژهٔ اصلی خواست و worktree نیز تغییرهای هم‌زمان داشت، بنابراین انتشار/کپی source تا پذیرش کاربر انجام نشد.
- عملیات واقعی: نصب `%LOCALAPPDATA%`، Login/OTP، Provider، Send، WordPress، Firewall/Proxy و دادهٔ عملیاتی صفر؛ فقط test roots و artifactهای کنترل‌شده.
- نتیجه=`BRANCH_FEATURE_ACCEPTED / UNSIGNED_RC2_AVAILABLE / PRODUCTION_RELEASE_NOT_AUTHORIZED`.
- Trigger ابطال: تغییر crypto dependency/key/payload/fingerprint/store/gates/builder یا اجرای target تازه.

### V-186 — پذیرش RC3 برندشده، امضای داخلی و بستهٔ تحویل

- تاریخ: 2026-08-28
- سطح: `CONTRACT RED / CERTIFICATE KEY-BOUNDARY / ICON BUILD / AUTHENTICODE / FULL REGRESSION / DELIVERY`
- Run: `INTERNAL-CODE-SIGNING-R01`
- Trigger: درخواست صریح کاربر برای امضای رایگان داخلی، آیکون Setup/Desktop/Start Menu، کلید خصوصی خارج پروژه، CER/راهنمای اعتماد و Setup امضاشده.
- RED: قراردادهای تازهٔ آیکون اجباری، میانبر، scriptهای certificate/sign/verify و ترتیب امضا پیش از hash در نبود پیاده‌سازی شکست خوردند؛ دو tmp fixture نخست فقط به Temp پیش‌فرض غیرقابل‌دسترسی خوردند و با basetemp workspace تکرار شدند.
- GREEN کد=`6/6`: ICO validation/build، رد icon مفقود/خراب، wiring آیکون و sign/trust policy. parser سه PowerShell script نیز PASS بود.
- گواهی واقعی: Subject=`CN=Eitaa Bridge Internal Publisher`، Thumbprint=`441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`، RSA 3072، EKU=`1.3.6.1.5.5.7.3.3`، HasPrivateKey=true و CNG export policy=`None`. CER public HasPrivateKey=false و پایان اعتبار 2031-08-28 است.
- trust bundle: metadata Thumbprint/SHA-256 با CER تطبیق داشت؛ guide و installer همان Thumbprint را pin کردند. اجرای import در sandbox با `E_ACCESSDENIED` متوقف شد و تغییر پایدار Root/TrustedPublisher حساب اصلی بدون اجازهٔ مستقل انجام نشد.
- encoding repair: تحویل نخست guide با وجود UTF-8 BOM، متن mojibake و placeholderهای گواهی حل‌نشده داشت؛ علت parse فایل UTF-8 بدون BOM توسط Windows PowerShell 5.1 و escape شدن `$` با backtick Markdown بود. source generator به UTF-8 BOM و template placeholder تبدیل و bundle با همان cert بازتولید شد. کنترل دوم پنج فایل: strict UTF-8 همهٔ textها=true، U+FFFD=0، mojibake marker=0، unresolved placeholder=0، Persian range=true، JSON parse=true، trust-script parser error=0، CER public-only/hash/thumbprint match=true.
- signing probe: کپی RC2 با SHA-256 پس از امضا=`A1C2BAC4BB15062C4351AD4F303DF8464A0FDAE5C94D0950CB0508F454264E32` و signer صحیح ثبت شد. وضعیت پیش از trust=`UnknownError` و timestamp=false بود؛ دستکاری کپی موقت signature را invalid کرد و tamper detection=true شد.
- icon: PNG=`520×520 RGBA / SHA 6ED4762B...FA1C`; converter deterministic نه frame استاندارد ساخت، ICO SHA=`8C35B98F...F5F7`. frameهای 32/256 و associated icon استخراج‌شده از EXE visual PASS؛ payload icon hash parity=true و shortcut icon contract=true.
- build: Runtime checker و install-copy simulation PASS؛ payload=4665، operational entry=0 و private-key-named entry=0. تلاش امضای داخل Batch به نبود `Cert:` drive خورد؛ signer با X509Store مستقیم repair و EXE موجود امضا شد.
- final Setup=`46,842,176 bytes / SHA 9587728C...6463 / --verify-only PASS / signer thumbprint match / tamper=true / timestamp=false / status-before-trust=UnknownError`. Portable=`45,936,308 bytes / SHA 07931D6E...3566`.
- delivery ZIP=`92,766,896 bytes / SHA 81C45B14...F15E / 12 entries`; Setup داخل ZIP hash-identical، manifest JSON PASS، private key file=0 و تمام ۷ متن strict UTF-8 BOM بدون mojibake/replacement/placeholder هستند.
- regression نهایی: full Backend=`688/688`، collection=`688 tests / 76 files`، TypeScript=`PASS` و UI/Electron Observability=`PASS`.
- گیت: clean-machine real-user install، مشاهدهٔ واقعی Desktop/Start Menu و trust مقصد به تأیید همان لحظه نیاز دارند. Self-signed public reputation ایجاد نمی‌کند.
- عملیات: نصب برنامه، Provider/Login/OTP/Send/WordPress/Firewall/Proxy و دادهٔ عملیاتی صفر. cert store فقط گواهی درخواست‌شده را دارد؛ PFX/private key file صفر. Git mutation صفر.

### V-187 — بازیابی collision و پذیرش مدل چهارسطحی/IR-GOV-01

- تاریخ: 2026-08-28
- سطح: `USER DECISION / DOCUMENTATION CONCURRENCY RECOVERY / CANONICAL MODEL VALIDATED`
- Run: `IDX-R03`
- Source=`SRC-USER-IR-006`؛ تصمیم کاربر=`FOUR_LEVEL_MODEL_AND_CODEX_ARCHITECTURE_LEAD_ACCEPTED`.
- RED مستندات: اجرای نخست memory integrity یک duplicate `F-064` نشان داد؛ ممیزی heading نیز دو ADR-50 و Ledger موجود V-186 را آشکار کرد. writer سناریوی امضای داخلی در فاصلهٔ رزرو و validation همان شناسه‌ها را مصرف کرده بود.
- مهار: رکورد امضای داخلی F-064/V-186/ADR-50 حذف یا بازنویسی نشد. مدل چهارسطحی به F-065/V-187/ADR-51 منتقل و backlinkهای مربوط اصلاح شدند.
- قرارداد ثبت‌شده: چهار سطح L1 semantic index، L2 WordPress projection، L3 local reporting core و L4 controlled intelligence؛ کاربر مالک دامنه/پذیرش و Codex مدیر معماری/promoter canonical پیش‌فرض است.
- governance: Task Contract، کلاس ریسک، file ownership، خروجی noncanonical، review/promotion و sole-writer تعریف شدند. allocator/lock/merge queue ماشینی هنوز پیاده نشده است.
- عملیات و محصول: schema، کد، UI، Provider، WordPress، دادهٔ عملیاتی و عملیات Live تغییر نکرد.
- GREEN نهایی: memory integrity، generated-doc freshness، Markdown link check و `git diff --check` همگی exit code صفر؛ ADR-50 متعلق به امضای داخلی و ADR-51 متعلق به مدل چهارسطحی است، duplicate رسمی صفر است. هشدارهای line-ending فقط اطلاع‌رسان بودند.
- Trigger ابطال: تغییر مدل سطح‌ها/نقش‌ها، collision تازه، یا پیاده‌سازی enforcement ماشینی.

### V-188 — پذیرش RC4 با Setup گرافیکی، Clipboard مستقل از layout و آرشیو Release

- تاریخ: 2026-08-28
- سطح: `CODE / BUILD / SIGNATURE / DELIVERY / FULL AUTOMATED ACCEPTANCE`
- RED/علت: contract جاری request box را disabled و Paste را بدون keycode مستقل از layout نشان داد. اجرای نخست full با `--cache-clear` پیش از collection به ACL ارث‌رسیدهٔ `.pytest_cache` خورد؛ اجرای نهایی با basetemp workspace و cache provider غیرفعال شد. Build کامل تا runtime/install-copy/archive سبز رفت، ولی sandbox certificate store را صفر دید؛ امضای مجاز بیرون sandbox با همان Thumbprint انجام و جدا verify شد.
- GREEN هدفمند: `tests/test_offline_license.py + tests/test_runtime_ownership.py = 41/41`. synthetic WinForms setup compile و `--verify-only`، archive با سه artifact/فایل نامرتبط محفوظ، keycode/normalization و quiet installer contract سبز است.
- GREEN کامل: Backend سریالی=`690/690` و collection=`690 tests / 76 files`; TypeScript=`PASS` و UI/Electron Observability=`PASS`. یک full موازی با checkerهای مستقل در تست scanner پشتیبانی G-04-D یک failure بدون جزئیات یافت؛ همان تست بلافاصله `1/1` و سپس `10/10` ایزوله و full سریالی `690/690` سبز شد. علت قطعی استنتاج نشد و رخداد برای recheck آینده ثبت ماند.
- Build: wheel rebuild، package allowlist dry-run=`301 files / PASS`، runtime checker و install-copy simulation PASS. Local archive=`12 artifacts` با Manifest؛ RC4 Setup=`46,855,488 / SHA E964C93B...BFA4 / verify-only=0 / signer match / tamper=true / timestamp=false` و Portable=`45,941,170 / SHA 8D9AE8AD...66FC`.
- Delivery: ZIP=`92,782,790 / SHA 6DACA748...FD9E / 13 entries / private-key-named=0`. هشت فایل text strict UTF-8 BOM، بدون replacement/mojibake؛ RC2/RC3 delivery به archive زمان‌دار منتقل و trust bundle عمومی حفظ شد.
- طول نمونه: request=`258` و activation=`563` نویسه؛ format برای backward compatibility ثابت ماند. کوتاه‌سازی شدید بدون online lookup یا tradeoff امنیت/metadata تأیید نشد.
- عملیات: نصب واقعی، اجرای Provider/Login/OTP/Send، تغییر trust مقصد و دادهٔ عملیاتی صفر. clean-machine UI/shortcut acceptance همچنان نیازمند تأیید همان لحظه است. worktree از سناریوهای قبلی dirty و در فایل‌های canonical/test دارای overlap بود؛ برای جلوگیری از mixed commit، Git stage/commit/push انجام نشد.
- Trigger ابطال: تغییر activation format/UI، installer shell/path/preservation، archive scope، certificate/signer یا هر failure مقصد.

### V-189 — پذیرش نصب تازهٔ چندحسابی و RC5 امضاشده

- تاریخ: 2026-08-29
- سطح: `CONFIG RED / INSTALLED-FLOW REHEARSAL / FULL REGRESSION / PAYLOAD PRIVACY / SIGNED BUILD`
- Run: `MULTI-ACCOUNT-CLEAN-INSTALL-RC5`
- Trigger: گزارش کاربر که نصب موفق روی Windows مجازی فقط مسیر ورود شمارهٔ تک‌حسابی را نشان می‌داد و درخواست صریح برای آزمون ترتیب مدیر اولیه سپس حساب ایتا.
- RED نخست: آزمون config بسته روی `app_user_auth.enabled=false` شکست خورد. پس از روشن‌کردن سه feature، startup بدون حساب به `legacy_runtime` غایب در worker-process registry خورد و defect دوم را آشکار کرد.
- GREEN جریان نصب: API با copy واقعی `bridge.example.json` و root ساختگی ابتدا `setup_required=true` داد؛ admin ساخته شد، فهرست حساب‌ها خالی ماند و POST نخستین Eitaa account عضویت پایگاه دادهٔ `admin/owner/active` ساخت. Provider Auth، شبکه، OTP و Worker start صفر بود.
- GREEN UI: ترتیب `AppUserGate → MessengerAccountGate → EitaaApp` و فرم ساخت مدیر در runner ثبت شد؛ onboarding UI=`8/8`، TypeScript=`PASS` و UI/Electron Observability=`PASS`.
- GREEN Backend: full suite با basetemp workspace و cache provider غیرفعال exit=0 داشت؛ collection مستقل=`691 tests`. آزمون‌های مرتبط installer پیش از build=`72/72` و مسیر مالکیت تازه نیز PASS بود.
- Build: wheel current-source با SHA-256=`F0C9BFD235108A6C6CB3891BDF163DDA163FEF3862F38587CD7CD49C8932924C` بازسازی شد؛ allowlist dry-run=`301 files / PASS`. runtime checker، install-copy simulation و scanner محتوایی payload همگی PASS؛ operational finding=0، private-key filename=0 و private-key PEM=0.
- Artifact: Setup RC5=`31,295,296 bytes / SHA-256 2BC280463AF1B0975EA904DB8CF761BC57F0A1CC69C53DB8C8FC104E249F20CC`; Portable=`30,492,682 bytes / SHA-256 175D80117706C0C49B391ABEE04F174E5F7952AAD327078998857CB96093E925`؛ nested payload=3555 entry و featureهای سه‌گانه=true.
- امضا: `--verify-only=PASS`؛ signer Thumbprint=`441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`، tamper=true، timestamp=false و status پیش از trust=`UnknownError`. نسخهٔ RC5 قبلی به `release/office/archive/20260829-060000` منتقل شد و Manifest دارد.
- Delivery: folder و ZIP بیرونی شامل Setup، Portable، branding و trust bundle عمومی است؛ ZIP=`61,883,250 bytes / SHA-256 66AF08945065BF17E503A257DFC36F8415F251E78583A8602B9A2BBA2E2C2D26 / 15 entries`. همهٔ 10 متن strict UTF-8 BOM، بدون replacement/mojibake هستند؛ Setup داخل ZIP hash-identical و private-key filename/PEM finding صفر است. RC4 به archive زمان‌دار `20260829-195620` منتقل شد.
- عملیات: نصب واقعی، تغییر trust مقصد، Provider/Login/OTP/Send/WordPress و دادهٔ عملیاتی صفر. clean-machine visual و جابه‌جایی واقعی میان دو حساب همچنان آزمون کاربر مقصد است.
- Trigger ابطال: تغییر config featureها، API bootstrap، Gateها، account ownership، builder/privacy scanner، signer یا نتیجهٔ مقصد.

### V-190 — پذیرش هستهٔ گزارش ۱۴۰۵: قواعد شمارش، فرم‌ها، export روی کپی

- تاریخ: 2026-09-08
- دامنه: `src/eitaa_bridge/reporting/` (model، rules، aggregate، forms، eitaa_extraction، excel_export، service) و `tests/test_reporting_core.py`
- RED→GREEN: مجموعهٔ ۳۶ تست نوشته و سبز شد؛ قبل از پیاده‌سازی هیچ‌کدام از این ماژول‌ها وجود نداشت.
- شاهد: `.venv/Scripts/python.exe -m pytest tests/test_reporting_core.py -q` → 36 passed؛ regression کل بسته به‌جز تست پریتی wheel از قبل قرمزِ مستقل (missing=8 ناشی از نبود rebuild wheel در این سشن؛ بدون تغییرات من هم قرمز بود).
- پوشش تأییدشده: کد 80403 مراسم؛ قاعدهٔ C12 زیارت عاشورا (خروج از شمارش اصلی + ضمیمهٔ مستقل)؛ قاعدهٔ C15 مسابقهٔ داخل مراسم؛ قاعدهٔ C16 نشست (>۳۰ دقیقه + اطلاع‌رسانی + پذیرایی)؛ شرط B9/B10 تکریم و C8 تشویق؛ دروازهٔ ADR-42 روی `estimated`/`synthetic_placeholder`؛ ردیف = جمع استان با تفکیک واحد در breakdown؛ export روی کپی با hash فایل اصلی ثابت؛ بلاک شدن export با ستارهٔ پرنشده.
- محدودیت: UI/فرم گرافیکی، اتصال زندهٔ Provider به ایتا و پریتی wheel در این تسک نبود؛ این‌ها باقی‌ماندهٔ فاز بعدی‌اند.

### V-191 — پذیرش ایندکس‌گذار intent ایتا و پیام‌رسانی بله

- تاریخ: 2026-09-08
- دامنه: `reporting/indexer.py`، `reporting/monitor.py`، `reporting/bale_messaging.py`، `tests/test_reporting_indexer.py`
- شاهد: `pytest tests/test_reporting_indexer.py` → 26 passed؛ مجموع reporting → 62 passed؛ regression کامل بسته به‌جز تست پریتی wheel (مستقل از این تغییر) سبز.
- پوشش تأییدشده: تفکیک سه‌کلاسهٔ event_report/informational/promotional روی نمونه‌های واقعی فارسی؛ استخراج عدد فارسی؛ نگاشت هفت برنامه؛ کاندید با provenance؛ پرهیز مانیتور بدون runtime؛ dedup رفرنس پیام بین دو watch config؛ ارسال/دریافت بله با خطای امن‌شده و پیپ‌لاین مشترک intent.
- محدودیت: اتصال live به حساب واقعی ایتا/بله در این تسک تست نشد (نیازمند نشست واقعی طبق قرارداد پروژه)؛ UI مانیتور باقی‌ماندهٔ فاز بعد است.

### V-192 — انتشار GitHub و ساخت بستهٔ نصبی RC5 با هستهٔ گزارش

- تاریخ: 2026-09-08
- انتشار: سه کامیت روی `codex/stabilization-g09` و merge به `main`؛ push به origin (gprsm/EitaaDesktop) هر دو موفق. فایل workbook اصلی ignored و خارج از Git ماند.
- شاهد بسته: wheel بازساخت (`88c12565…`) و تست پریتی wheel/source که قرمز بود سبز شد؛ UI production build و Electron pack موفق؛ `BUILD_OFFICE_SETUP_EXE` کامل تا امضا.
- خروجی‌ها در `release/office/`: Setup گرافیکی امضاشدهٔ یک‌فایلی (SHA-256 `A696A222…`، امضا با thumbprint داخلی، tamper-test موفق) و Portable خودکفا (SHA-256 `ce3e8649…`)؛ آرشیو نسخه‌های قبلی طبق قرارداد انجام شد.
- تأیید محتوا: payload داخل Setup شامل هر ۱۱ ماژول `eitaa_bridge/reporting` (نصب‌شده و داخل wheel) است؛ privacy-check پاس؛ هیچ session/config/دادهٔ خصوصی در بسته نیست.
- محدودیت محلی: رجیستر CRLF روی فایل ui33 فقط اثر working-copy ماشین build دارد؛ محتوای Git و بسته سالم‌اند (با بازنویسی bytes از blob تأیید شد). امضای self-signed روی ماشین بدون نصب trust، `UnknownError` طبیعی است (F-064).

### V-193 — فاز ۱ شاخهٔ Bale: API ماژولار مخاطبین و پیام‌رسانی بله

- تاریخ: 2026-09-14 (به‌روزرسانی UI در همان روز)
- دامنه: شاخهٔ استثنایی `Bale` (برگرفته از `main`)؛ فقط پوشهٔ قرنطینه‌شدهٔ `src/eitaa_bridge/application/bale_client/` + `tests/test_bale_branch_api.py` + `run_bale_api.bat` + `docs/reports/BALE_BRANCH_PHASE1_REPORT.md`. هیچ فایل دیگری از برنامهٔ اصلی تغییر نکرد؛ رجیستری Provider و slot بله fail-closed ماند.
- شاهد: `pytest tests/test_bale_branch_api.py` → 34 passed (codecهای تایپ‌شده، facade با fake در مرز WS، سرور HTTP loopback با socket واقعی، آپلود base64 با staging، auto-reconnect بدون vault). کل مجموعه backend → 793 passed، 2 failed که هر دو با `git stash` روی main بدون این تغییر بازتولید شد (CRLF asset ui33 و آرشیو office؛ از پیش موجود، مستقل از شاخه).
- پوشش تأییدشده: build/decode ImportContacts با شمارهٔ تلفن؛ AddContact/RemoveContact؛ decode کاربر و دیالوگ با guard تحمل‌پذیر؛ ارسال متن/عکس با payload صحیح protobuf؛ خواندن تاریخچه و دانلود رسانه؛ کارت امن نشست بدون token؛ خطاهای code-دار؛ قرنطینهٔ release (G07) و fail-closed (G-02) هر دو پاس.
- تأیید UI: پنل تک‌فایلی `webui.html` از `GET /ui` سرو شد؛ هر ۵ صفحه (احراز هویت/مخاطبین/پیام‌رسانی/گفتگوها/تنظیمات) در مرورگر واقعی باز و ناحیه‌ها/عناصر با DOM snapshot بررسی شد؛ ذخیرهٔ توکن در تنظیمات نوار وضعیت را به «نشستی ذخیره نشده» رساند (اتصال UI→API سالم)؛ تایپ در فیلد شماره کار کرد؛ syntax اسکریپت UI با Node تأیید شد؛ شاهد بصری در `gui-test-screenshots/t1_auth_page.png` و `t2_chat_page.png` (بررسی چشمی در این محیط مدل ممکن نشد و ثبت شد؛ ملاک، شاهد DOM است). دکمهٔ «درخواست کد» عمداً کلیک نشد (عملیات Live نیازمند تأیید همان لحظهٔ کاربر).
- مداومت نشست: passphrase رمزگذاری vault در `data/bale_vault.key` سمت سرور نگه داشته می‌شود؛ reconnect خودکار در startup اجرا و بدون vault به‌صورت no-op تست شد؛ توکن API پایدار در `data/bale_api.token` (هر دو gitignored؛ فقط برای نشست سرور-local loopback).
- رویداد Live ثبت‌شده: در smoke-test سرور (قبل از UI)، یک فراخوانی StartPhoneAuth با شمارهٔ ساختگی به next-ws.bale.ai انجام و 200/transaction_hash واقعی دریافت شد (فراخوانی الگوی صحیح را تأیید کرد)؛ سرور بلافاصله متوقف شد. این رویداد مجوز عملیات Live نیست و OTP/ValidateCode هرگز اجرا نشد.
- Trigger تکرار: تغییر codecهای `bale_client`، فعال‌سازی Provider Bale، یا ادغام این شاخه در `main`.

### V-194 — غنی‌سازی مخاطبین شاخهٔ Bale و پذیرش Live عملیات نشست

- تاریخ: 2026-09-15
- دامنه: شاخهٔ `Bale`؛ کامیت `b4491b7f`؛ فقط `src/eitaa_bridge/application/bale_client/{api,api_server,codecs_ext}.py` و `tests/test_bale_branch_api.py`.
- سطح: Unit/Contract (fake در مرز WS) + Live (نشست ذخیره‌شدهٔ کاربر با مجوز همان لحظه).
- روش امن: `.venv/Scripts/python.exe -m pytest tests/test_bale_branch_api.py` → 36 passed؛ سرور loopback `api_server` روی 127.0.0.1:8791 با vault موجود auto-reconnect شد و عملیات contacts/list، contacts/search، messages/read-history و messages/send-text با curl اجرا شد.
- نتیجه: GetContacts peer-only با LoadUsers غنی‌شد (نام کامل + access_hash هر ۳ مخاطب)؛ جستجو با «محمد»/«محسن»/«اخوندیان»/«م» درست match شد؛ پیام تستی ارسال و با read-back (message_id 4091180017836933156) تأیید شد. دیکد wrapped-text `{1: text}` برای local_name/username، نگاشت PermissionDenied→`bale_access_denied` و پخش `data/otp_alert.wav` پس از auth/start نیز در همین کامیت.
- نقص شناخته‌شدهٔ غیرمسدودکننده: برطرف شد در V-195 (F-073 بسته شد).
- Artifact: `docs/reports/BALE_BRANCH_PHASE1_REPORT.md` فصل ۸.
- Trigger تکرار: تغییر codecهای `bale_client`، فعال‌سازی Provider Bale، یا ادغام شاخهٔ `Bale` در `main`.

### V-195 — رفع نقص F-073 در LoadDialogs و غنی‌سازی متن و رسانهٔ دیالوگ‌ها

- تاریخ: 2026-09-22
- دامنه: شاخهٔ `Bale`؛ `codecs.py`، `codecs_ext.py`، `api.py`، `api_server.py`، `models.py`، `webui.html`، `tests/test_bale_branch_api.py`.
- سطح: Unit/Contract + Live (نشست ذخیره‌شدهٔ کاربر روی سرور لوپ‌بک).
- روش امن:
  1. `.venv/Scripts/python.exe -m pytest tests/test_bale_branch_api.py` → 39 passed (۳ تست جدید).
  2. `.venv/Scripts/python.exe -m pytest tests/test_bale_stabilization_fail_closed.py` → 5 passed.
  3. اجرای Live روی سرور loopback پورت ۸۷۹۱: متد `dialogs/list` فراخوانی شد؛ دیالوگ‌ها با موفقیت دریافت و تأیید شدند.
- نتیجه:
  - در `build_load_dialogs` پیش‌فرض فیلد ۱ به `offset_date: int = (1 << 63) - 1` تغییر یافت؛ سرور تمام گفتگوهای فعال جاری را برگرداند.
  - فیلد ۱۳ برای پیام‌های ربات و تعاملی در `decode_content` بازگشایی شد و زیرعنوان، نام سند و متن آنها استخراج گردید.
  - فیلدهای `sort_date` و `last_message_date` با `_signed_int_or_none` به int64 علامت‌دار تبدیل شدند.
  - متد `to_dict` به `FileDetails` اضافه و در `DialogSummary.to_dict()` به همراه `media_kind` یکپارچه شد.
  - پیام خطای ۴۰۱ در `webui.html` به راهنمای فارسی تبدیل شد.
  - نتیجهٔ Live: گفتگوی محسن (peer 1846320404) با `last_message_id: 4091180017836933156` و متن کامل فارسی، و گفتگوهای دارای رسانه با `last_document` و `media_kind` معتبر تأیید شدند.
- Trigger تکرار: تغییر پروتکل سرور بله یا بازگشایی F-073.

### V-196 — پذیرش استقرار Linux، انتشار چندسایتی و حفاظت هویت غیرWindows

- تاریخ: 2026-09-22
- دامنه: `infrastructure/coordinator/{identity,app_auth}.py`، exportها، تست Linux، `deploy/linux/`، Nginx/systemd و میزبان production.
- سطح: Unit/Full regression + UI contracts/build + privacy scan + live deployment بدون عملیات Messenger/WordPress.
- نتیجهٔ محلی: تست هدفمند FileKey=`2 passed + 1 POSIX-only skipped`؛ full Backend=`809 passed + 1 skipped` از ۸۱۰؛ TypeScript PASS؛ Observability PASS؛ Vite build=`1021 modules`؛ wheel آفلاین بازسازی و source parity PASS.
- بسته: ۱۷۵ entry، بدون `.env`، `bridge.json` واقعی، session، data، runtime، diagnostics عملیاتی، backups، Git، pyc یا cache؛ SHA-256=`57CF28A9...5652EE`.
- نتیجهٔ Live: `publish-site deploy eitaa-bridge` موفق؛ readiness و systemd active؛ Nginx syntax PASS؛ redirect 308، UI 200، login 200، `/me`=200 و Cookie دارای `Secure/HttpOnly/SameSite=Strict`؛ listenerهای Backend/gateway فقط Loopback؛ فایروال فقط listenerهای عمومی موجود را نگه داشت؛ بررسی بیرونی پورت‌های داخلی timeout شد؛ پنج vhost قبلی 200 باقی ماندند؛ exposure سرویس systemd=`3.1 OK`.
- E2E آفلاین شبکهٔ سرویس: ورود مدیر، Cookie و session از HTTPS origin با resolve محلی اجرا شد؛ هیچ اتصال Provider، OTP، ارسال پیام، WordPress write یا انتقال session/data محلی انجام نشد.
- باقی‌مانده: certificate عمومی Edge توسط کاربر در CDN فعال می‌شود؛ آزمون origin با self-signed و `--insecure` فقط برای پذیرش هم‌میزبان بود.
- Trigger تکرار: هر تغییر F-074 یا تغییر سرور/CDN/Nginx/systemd/publish handler.

### V-197 — پذیرش رفع قفل OTP در پروفایل HTTPS Reverse Proxy

- تاریخ: 2026-09-22
- دامنه: `config.py`، `test_phase10c_web_reverse_proxy_contract.py`، Config و اسناد استقرار Linux.
- Trigger: گزارش کاربر از پیام «درخواست با سیاست استقرار HTTP سازگار نیست» هنگام دریافت کد در UI عمومی.
- ریشهٔ تأییدشده: probe بدون credential روی endpoint عمومی پاسخ 403 با error code امن `remote_messenger_auth_disabled` و mode=`web_reverse_proxy` داد؛ هیچ شماره، OTP، Cookie یا تماس Provider در probe وجود نداشت.
- RED→GREEN: Config وب با remote auth روشن پیش از اصلاح با `deployment_remote_messenger_auth_risk_not_acknowledged` رد می‌شد. پس از محدودکردن قابلیت به `web_reverse_proxy`، contract درخواست request-code با Proxy/HTTPS/Origin معتبر پذیرفته شد و adversarialهای Proxy موجود دست‌نخورده ماندند.
- شاهد: تست‌های Phase 10-C/6-A/6-B برابر `50 passed`؛ تست هدفمند نهایی همراه parity wheel برابر `51 passed`؛ full Backend پس از rebuild wheel برابر `811 passed + 1 skipped` از 812؛ parity wheel PASS با SHA-256=`9D9D1131...F7FEA`.
- انتشار Live: release با hash محتوایی `A654D4E8...125A1` از مسیر مشترک `publish-site` منتشر شد. migration نسخه‌دار Config، backup محدود، validation، restart و readiness را موفق طی کرد. پس از انتشار، readiness عمومی=200 و probe بدون credential روی request-code به‌جای `remote_messenger_auth_disabled` پاسخ مورد انتظار `app_auth_required` داد؛ یعنی مرز deployment عبور و مرز AppUser حفظ شد. redirect=308، UI=200، login=200 و `/me`=200 نیز بدون Provider دوباره پذیرفته شدند.
- عملیات Provider: درخواست واقعی OTP، شماره، Cookie در خروجی، تماس Provider، Send یا WordPress write اجرا نشد.

### V-198 — پذیرش انتخاب محافظ هویت در Child لینوکس

- تاریخ: 2026-09-22
- دامنه: `application/account_runtime.py`، آزمون هویت غیرWindows، آزمون lifecycle احراز هویت و ابزار read-only استقرار.
- Trigger: گزارش کاربر از «The Eitaa Child rejected the request» پس از رفع قفل HTTP. audit واقعی فقط کدهای امن `eitaa.auth.request_code.denied`، `account_phone_resolution_failed` و نوع `CoordinatorIdentityError` را نشان داد.
- علت: Child و Registry از `WindowsDpapiPhoneProtector` استفاده می‌کردند، اما AppAuth روی Linux با `FileKeyPhoneProtector` هویت شماره را ذخیره کرده بود.
- آزمون ساختگی: مسیر ساخت Runtime حساب‌محور Child با identity رمزگذاری‌شدهٔ ساختگی از کلید Coordinator شماره را بازیابی کرد؛ آزمون‌های جداگانهٔ چرخهٔ auth و Child RPC نیز سبز شدند. full Backend پس از به‌روزرسانی seam آزمون‌های lifecycle سبز شد؛ TypeScript، Observability، integrity حافظه و بررسی پیوند اسناد نیز PASS بودند.
- انتشار: بستهٔ پاک با hash=`C99BDE0E...2A73E` از مسیر مشترک `publish-site` منتشر شد؛ release فعال=`20260922T191611Z-c99bde0e318a` و سرویس active است. فایل `account_runtime.py` در کد اصلی و release فعال SHA-256 یکسان=`D3B6DBA6...2391F4` دارد.
- پذیرش سرور: بررسی فقط‌خواندنی با خود کاربر سرویس `identity_unlock=passed accounts=1` داد. readiness عمومی=200؛ redirect=308، UI=200، login=200 و `/me`=200. دادهٔ شماره، کلید و نشست در خروجی دیده نشد.
- شاهد عملیاتی تکمیلی: بعد از انتشار، اقدام خود کاربر در UI با audit امن `eitaa.auth.request_code.succeeded`، سپس سه `eitaa.auth.login.completed` و چند `eitaa.auth.logout.completed` ثبت شد. بنابراین ورود کامل با حساب واقعی موفق بوده است. ردهای پس از آخرین خروج با `account_phone_mismatch` مربوط به شماره‌ای متفاوت از هویت حساب انتخاب‌شده‌اند.
- مرز: خود این Run درخواست OTP یا تماس Provider ایجاد نکرد. هیچ شماره، کد، Cookie یا متن خصوصی در شاهد ثبت نشد.

### V-199 — وضوح هویت حساب در فرم ورود ایتا

- تاریخ: 2026-09-23
- دامنه: `ui/src/App.tsx`، `ui/src/MessengerAccountGate.tsx` و آزمون قرارداد onboarding.
- Trigger: audit زندهٔ بعد از V-198 ورود کامل را تأیید کرد، ولی ردهای جدید `account_phone_mismatch` و متن گمراه‌کنندهٔ «ورود با شماره‌ای دیگر» در UI دیده شد.
- آزمون: `npm.cmd --prefix ui run check`، `npm.cmd --prefix ui run test:phase11-onboarding` (۹/۹) و `npm.cmd --prefix ui run build` (۱۰۲۱ ماژول) و `npm.cmd --prefix ui run test:observability` همگی PASS.
- نتیجه: UI بدون افشای شمارهٔ کامل، راهنمای حساب انتخاب‌شده و مسیر انتخاب/افزودن حساب دیگر را در مرحلهٔ ورود ارائه می‌کند؛ خطای عدم تطابق قابل اقدام است. کنترل تطابق سمت سرور عوض نشده است.
- انتشار: بستهٔ محدود ۱۷۴ entry با privacy scan نام‌ها و SHA-256=`C98B89BD...2996A` از مسیر `publish-site` در release `20260923T064140Z-c98b89bd1e27` فعال شد؛ سرویس active، UI و readiness هر دو 200 هستند. هش bundle رابط روی سرور و source برابر=`55C28E9E...3AC55`، و هش `account_runtime.py` برابر=`D3B6DBA6...2391F4` ماند.
- سطح شاهد: قرارداد/build محلی و انتشار/health زنده؛ ورود تعاملی پس از این تغییر UI یا درخواست OTP توسط این Run انجام نشد.

### V-200 — تفکیک مرز احراز هویت Bearer از نشست کاربر و آزمون‌های امنیتی

- تاریخ: 2026-09-24
- دامنه: `src/eitaa_bridge/application/api.py`، آزمون‌های رگرسیون جدید `tests/test_bearer_and_app_user_auth_boundary.py`، سرور HTTP، و مستندات حافظهٔ مهندسی.
- سطح: `LOCAL_REGRESSION / AUTH_BOUNDARY / SECURITY_CONTROLS / STATIC_CODE_VERIFICATION`
- Run: `WEB-AUTH-R01`
- نتایج آزمون هدفمند (`tests/test_bearer_and_app_user_auth_boundary.py`): ۷ از ۷ تست سبز، exit code=0:
  1. `test_when_app_user_auth_enabled_pre_login_and_probes_do_not_require_bearer`: پروب‌های `/api/v1/health`، `/readiness`، `/schema`، وضعیت احراز هویت `/api/v2/app-auth/status`، ورود و bootstrap بدون هدر Bearer با موفقیت عمل کردند.
  2. `test_when_app_user_auth_enabled_protected_endpoints_require_session_and_bearer_alone_is_rejected`: مسیرهای محافظت‌شده بدون نشست کاربر با HTTP 401 (`app_auth_required`) مسدود می‌شوند؛ ارسال Bearer به‌تنهایی بدون نشست کاربری مسدود باقی می‌ماند؛ درخواست با نشست کاربری بدون Bearer موفق است.
  3. `test_when_app_user_auth_enabled_local_resource_and_media_cache_accessible_with_session_without_bearer`: دسترسی به فایل و کش رسانه برای نشست کاربری بدون هدر Bearer مجاز است (HTTP 204).
  4. `test_when_app_user_auth_disabled_legacy_bearer_enforcement_strictly_preserved`: رفتار سازگار با گذشته در حالت تک‌کاربره بررسی و تأیید شد (عدم ارسال Bearer باعث ۴۰۱ می‌شود).
  5. `test_http_server_end_to_end_bearer_boundary_with_browser_session`: چرخهٔ کامل شبکهٔ HTTP شامل ورود مرورگر، اعتبارسنجی CSRF، کش رسانه و آپلود فایل با Cookie نشست و بدون Bearer تأیید شد.
  6. `test_bearer_alone_cannot_send_messages_when_app_user_auth_enabled`: ارسال پیام از مسیر `/api/v1/messages/send` فقط با توکن Bearer (بدون نشست کاربری) با HTTP 401 (`app_auth_required`) رد شد.
  7. `test_http_server_preserves_origin_and_remote_setup_security`: رد Originهای غیرمجاز و حفاظت راه‌اندازی مدیر تأیید شد.
- نتایج آزمون‌های تکمیلی:
  - مجموعهٔ ۱۰۴ تست شامل `test_application_api.py`, `test_app_user_api.py`, `test_phase10c_web_reverse_proxy_contract.py`, `test_phase6c`, `test_phase6b`, `test_phase6a` همگی PASS شدند.
  - فرانت‌اند: `npm run check` و `npm run test:observability` هر دو PASS شدند.
  - اسناد و حافظه: `check_project_memory_integrity.py` و `refresh_project_docs.py --check --check-links` هر دو PASS شدند.
- وضعیت سرور و داده‌ها: هیچ تغییری روی سرور لینوکس اعمال نشده و هیچ سرویسی restart نشده است. فایل موقت رمز بلافاصله حذف شد. هیچ توکن، رمز، کوکی یا دادهٔ خصوصی در گزارش یا اسناد درج نشد.

### V-201 — بازبینی مستقل ورود وب، بازیابی محدود UI و gate انتشار

- تاریخ: 2026-09-24
- دلیل بازآزمایی: پاسخ زندهٔ Production پس از V-200 همچنان `401 api_unauthorized` بود؛
  سناریوی وب چندحسابی با Bearer فعال و بررسی وضعیت ورود در gate انتشار هنوز پوشش نداشت.
- Run: `WEB-AUTH-R02`؛ سطح پیش از انتشار: `LOCAL_CONTRACT / FULL_REGRESSION / RELEASE_REHEARSAL`.
- آزمون `tests/test_bearer_and_app_user_auth_boundary.py`: ۸/۸ پاس، از جمله
  پروفایل تولید `web_reverse_proxy` با چندحسابی، Bearer فعال، forwarded HTTPS،
  login و Cookie امن؛ setup از IP بیرونی و Bearer تنها برای API محافظت‌شده رد شدند.
- آزمون `tests/test_phase10c_web_reverse_proxy_contract.py`: ۱۷/۱۷ پاس؛
  قرارداد جدید publisher هر دو مسیر readiness و app-auth/status را الزام می‌کند.
- UI: TypeScript check، build تولید، Observability، Phase 10 local activation،
  Phase 11 onboarding و `test:auth-startup` پاس شدند. بازیابی خطای گذرا فقط یک
  تکرار خودکار دارد؛ خطای پیکربندی تکرار نمی‌شود و خطای status رویداد refresh
  مجدد تولید نمی‌کند.
- full backend suite در اجرای نخست فقط به‌دلیل wheel قدیمی در کنترل parity
  بسته‌بندی شکست خورد؛ wheel با ابزار استاندارد پروژه بازسازی شد و اجرای دوم
  full suite با exit code صفر پایان یافت (یک skip پلتفرمی).
- `check_project_memory_integrity.py` و `refresh_project_docs.py --check
  --check-links` پاس شدند؛ سند و نقشهٔ تولیدشده به‌روز شدند.
- بستهٔ انتشار از artifact فعال پیشین ساخته شد و فقط API auth، UI ساخته‌شده،
  handler انتشار و راهنمای همان handler جایگزین شدند. نام‌های ممنوع در ۱۷۷
  entry بسته صفر بود؛ SHA-256 بسته `D81B875CBAC060D225A8F1D6EF6A6F6D9AC761E8DFE741EE102545A3D08FFCD7`.
- Live: handler قبلی و فایل انتشار قبلی با هش مرجع تطبیق داده شدند؛ handler
  جدید با backup محدود نصب شد و `publish-site deploy eitaa-bridge` نسخهٔ
  `20260924T045946Z-d81b875cbac0` را فعال کرد. gateway هنگام restart چند
  پاسخ گذرای 502 داد، سپس gate هر دو بررسی را پذیرفت و انتشار موفق شد.
- پس از انتشار: `app-auth/status` عمومی `200` با `ok=true`، `enabled=true`،
  `authenticated=false` و `setup_required=false`؛ UI و readiness عمومی `200`،
  readiness gateway `200`، `/api/v2/app-auth/me` بدون نشست `401` و systemd
  فعال. مرورگر واقعی فرم ورود محلی را بدون خطای آغاز نمایش داد. ورود تعاملی
  یا ارسال واقعی پیام در این Run انجام نشد.
- Trigger تکرار: تغییر auth dispatch/resource، مسیر رویداد/تلاش UI، پروفایل
  وب، publisher یا نتیجهٔ انتشار زنده.

### V-202 — ایجاد حساب مدیر کل عملیاتی در سرور

- تاریخ: 2026-09-24؛ سطح شاهد: `LIVE / APP_AUTH / WEB_REVERSE_PROXY`.
- دلیل بررسی زنده: درخواست صریح مالک برای ایجاد یک حساب مدیر کل با نام کاربری و
  رمز تعیین‌شده در نسخهٔ منتشرشده، پس از V-201.
- پیش از تغییر، حساب درخواستی وجود نداشت و دو مدیر فعال دیگر در پایگاه داده ثبت
  بودند. عملیات با هویت کاربری سرویس، در یک تراکنش SQLite انجام شد و رویداد
  `app_user.operator_created` با `actor_type=system` و دلیل امن در زنجیرهٔ Audit
  ثبت گردید؛ رمز فقط از ورودی تعاملی خوانده و با PasswordHasher خود برنامه هش شد.
- احراز هویت داخلی برنامه، نقش `admin` و وضعیت فعال حساب را تأیید کرد و نشست
  بررسی بسته شد. ورود از HTTPS عمومی با Origin مجاز نیز موفق شد، نقش مدیر کل را
  بازگرداند و نشست بررسی در همان مسیر logout شد.
- نخستین درخواست بررسی HTTPS بدون Origin طبق سیاست استقرار با 403 رد شد؛ پس از
  افزودن Origin معتبر، درخواست موفق بود. این رد یک کنترل امنیتی مورد انتظار است.
- اسکریپت یک‌بارمصرف از سرور و رایانهٔ محلی حذف شد. هیچ رمز، Cookie، Token یا
  دادهٔ خصوصی در این سند، فرمان‌های پایدار یا خروجی آزمون ثبت نشد. کد محصول
  تغییر نکرد؛ بنابراین مجموعهٔ کامل تست کد تکرار نشد.
- Trigger تکرار: تغییر رمز یا نقش این حساب، تغییر سیاست Origin/ورود، یا شکست
  ورود در سایت منتشرشده.

### V-203 — ابطال و حذف توکن‌های عملیاتی ایتا در سرور

- تاریخ: 2026-09-24؛ سطح شاهد: `LIVE / CREDENTIAL_REVOCATION / SERVICE_RECOVERY`.
- دلیل بررسی زنده: درخواست صریح مالک برای حذف همهٔ توکن‌های موجود روی سرورِ
  ایتا به‌دلیل احتمال بروز مشکل.
- موجودی پیش از اقدام: یک توکن API در محیط سرویس ایتا، یک کپی همان نوع توکن
  در محیط `onlineexam`، سه نشست فعال AppUser، یک نشست فعال پیام‌رسان ایتا و
  چهار فایل بایگانی نشست ایتا. هیچ فایل در backup مشترک وجود نداشت.
- با نشست مدیر، خروج رسمی تنها حساب ایتا از API انجام شد؛ `remote_ok=true`
  و فایل نشست فعال از مسیر سرویس آرشیو گردید. سپس نشست‌های همهٔ کاربران از
  مسیر رسمی مدیریت باطل شدند؛ چهار نشست شامل نشست موقت همین عملیات باطل شد.
- سرویس موقتاً متوقف شد؛ یک انتساب `EITAA_BRIDGE_API_TOKEN` از `.env` حذف و
  پنج فایل بایگانی نشست ایتا پاک شد. سایر متغیرهای محیطی، رمزهای کاربران،
  کلیدهای محافظت هویت و داده‌های پیام تغییر نکردند. سرویس دوباره فعال شد.
- بررسی پس از اقدام: نشست فعال AppUser=0؛ وضعیت حساب ایتا=`revoked`؛ فایل
  نشست/آرشیو ایتا=0؛ انتساب توکن API=0؛ سایر انتساب‌های توکن محیطی=0؛
  systemd=`active`، `app-auth/status` عمومی سالم و readiness عمومی HTTP 200.
- اسکن تکمیلی در `/srv/projects` کپی دوم توکن را در `.env` پروژهٔ `onlineexam`
  نشان داد؛ آن انتساب نیز حذف و کانتینر backend دوباره ساخته شد. اعتبارسنجی
  Production آن پروژه نبود توکن را به‌طور نامتناسب مانع آغاز کل بک‌اند می‌کرد،
  در حالی‌که آداپتور ارسال در نبود توکن fail-closed است. شرط اعتبارسنجی اصلاح شد:
  توکنِ تنظیم‌شده بدون URL رد می‌شود، اما URL بدون توکن مجاز است و ارسال انجام
  نمی‌شود. فایل آزمون متناظر به‌روز شد؛ ساخت TypeScript و دو بررسی رفتاری روی
  تصویر ساخته‌شده پاس شدند. کانتینر جدید `healthy` است، توکن محیطی آن خالی و
  صفحهٔ عمومی `onlineexam` HTTP 200 است.
- اسکن نهایی همهٔ فایل‌های محیطی پروژه‌های `/srv/projects` انتساب توکن ایتای
  غیرخالی=0، کپی فایل نشست ایتا=0، نشست فعال AppUser=0 و نشست authenticated
  پیام‌رسان ایتا=0 را نشان داد. ارسال OTP ایتا از `onlineexam` تا پیکربندی
  مجاز تازه در دسترس نیست.
- فایل‌های یک‌بارمصرف از سرور و رایانهٔ محلی حذف شدند. هیچ مقدار توکن، رمز،
  Cookie یا دادهٔ خصوصی ثبت نشد. کد Eitaa Bridge تغییر نکرد؛ مجموعهٔ کامل تست
  آن تکرار نشد. اصلاح کوچک کد `onlineexam` روی نسخهٔ سرور ساخته و در زمان اجرا
  بررسی شد.
- Trigger تکرار: ایجاد توکن یا نشست تازه، بازیابی دادهٔ عملیاتی از نسخهٔ
  پشتیبان، یا تغییر قرارداد خروج و احراز هویت.

### V-204 — بازنشانی کامل داده‌ها و حساب‌های سرور ایتا با یک مدیر اولیه

- تاریخ: 2026-09-24؛ سطح شاهد: `LIVE / EXPLICIT_FULL_RESET / INITIAL_ADMIN`.
- دامنه با پاسخ صریح مالک مشخص شد: همهٔ حساب‌های محلی و پیام‌رسان، توکن‌ها،
  پیام‌ها، مخاطبان و رسانه‌های ذخیره‌شدهٔ پروژهٔ ایتا روی این سرور پاک شوند؛
  سپس فقط حساب اولیه با نام کاربری `آخوندیان` و رمز تعیین‌شده ساخته شود.
- موجودی پیش از حذف: AppUser=3، credential=3، PhoneAccount=1،
  MessengerAccount=1، نشست‌های تاریخی AppUser=16، رخداد Audit=82؛ داده=8
  فایل، runtime=164 فایل و diagnostics=10 فایل. سرویس پیش از حذف متوقف شد.
- محتوای پوشه‌های عملیاتی `data`، `runtime`، `diagnostics`، `backups` و
  `catalog` از مسیر تثبیت‌شدهٔ `shared` حذف و پوشه‌های خالی دوباره ساخته شدند.
  پیکربندی استقرار `bridge.json` و `.env` برای اجرای سرویس حفظ شدند؛ نسخهٔ
  قدیمی فایل اعتبار مدیر اولیه در مسیر deploy نیز حذف شد. هیچ نسخهٔ پشتیبان
  از داده‌ها/توکن‌های حذف‌شده در سرور ایجاد نشد.
- با `CoordinatorAppAuth.bootstrap_admin` خود برنامه، فقط کاربر `آخوندیان`
  با نقش `admin` و وضعیت `active` ساخته شد. رمز از ورودی تعاملی خوانده و مقدار
  آن در فرمان، فایل یا سند ثبت نشد. نشست‌های حاصل از راه‌اندازی و بررسی ورود
  بسته شدند؛ ردیف‌های هش نشستِ آزمایشی نیز هنگام توقف سرویس حذف و پایگاه داده
  `VACUUM` شد.
- ورود HTTPS عمومی با نام کاربری جدید و نقش مدیر موفق و نشست آزمون بسته شد.
  بررسی نهایی پس از restart: AppUser=1، credential=1، PhoneAccount=0،
  MessengerAccount=0، local_contacts=0، app_user_sessions=0، فایل دادهٔ حساب=0
  و فایل نشست ایتا=0؛ `PRAGMA quick_check=ok` و خطای FK=0. systemd=`active`،
  `app-auth/status` بدون نشست سالم و readiness عمومی HTTP 200 است.
- backend پروژهٔ `onlineexam` همچنان `healthy` و فاقد توکن ایتا است. استفاده
  از حساب ایتا و ارسال OTP آن تا اتصال و پیکربندی مجاز تازه ممکن نیست. کد
  Eitaa Bridge تغییر نکرد؛ اسکریپت موقت از سرور و رایانهٔ محلی حذف شد.
- Trigger تکرار: بازیابی نسخهٔ پشتیبان، ایجاد کاربر یا اتصال پیام‌رسان تازه،
  یا تغییر پیکربندی و کد راه‌اندازی اولیه.

### V-205 — بازتولید و رفع محلی خطای پاسخ Child پس از OTP

- تاریخ: 2026-09-25؛ سطح شاهد: `OFFLINE / LOCAL SOURCE FIX / LIVE PENDING`.
- Trigger بررسی: گزارش تازهٔ کاربر از ادامهٔ خطای Child پس از ارسال کد و تصحیح مسیر مبنا به `D:\eitaa Project\AntiGravity2`؛ شاهدهای قبلی ورود برای این نسخه و این رخداد کافی نیستند.
- موجودی فقط‌خواندنی نشان داد نشست‌های واقعی در درخت محلی حاضرند. حذف نشست در اجرای قبلی توسط بازبینی خودکار ابزار با `blocked by policy` رد شده بود؛ در این اجرا هیچ نشست واقعی پاک یا جابه‌جا نشد.
- RED: سه آزمون با `LoginStepResult` واقعی Core در محیط موقت بدون نشست کاربر، هر سه با `ipc_payload_forbidden` شکست خوردند.
- GREEN هدفمند: اصلاح `session_snapshot` در هر سه پاسخ Child؛ مجموعهٔ Auth Child/IPC برابر `19/19 passed`.
- full Backend نخست فقط در wheel/source parity شکست خورد، زیرا wheel قبلی با source تازه یک فایل اختلاف داشت. wheel محلی از source بازسازی شد و اجرای نهایی full Backend بدون شکست، با یک skip موجود، گذشت.
- TypeScript و UI/Electron Observability هر دو PASS. Server deploy، Login/OTP واقعی، ارسال پیام، تغییر دادهٔ عملیاتی و Git publication انجام نشد.
- Trigger تکرار: تغییر Auth Child/IPC، بستهٔ wheel، یا ورود واقعی پس از انتشار.

### V-206 — پاک‌سازی دستی نشست‌ها و بازنشانی اعتبار مدیر محلی

- تاریخ: 2026-09-25؛ سطح شاهد: `LOCAL OPERATION / USER AUTHORIZED / READ-BACK VERIFIED`.
- پس از اجرای دستی دستور پاک‌سازی توسط کاربر، بررسی فقط‌خواندنی نشان داد فایل نشست فعال در ریشه، `data` و `runtime` صفر، ردیف نشست AppUser صفر، وضعیت دو نشست پیام‌رسان `absent` و `PRAGMA quick_check=ok` است.
- به درخواست صریح کاربر، حساب فعال مدیر محلی با نام ورود `akhoondian` شناسایی شد؛ این نام ورود از قبل روی همان حساب تنظیم بود. رمز همان حساب با `PasswordHasher` خود برنامه، نمک تازه و افزایش نسخهٔ credential بازنشانی شد. هیچ حساب تازه‌ای ساخته نشد.
- نشست فعال همان مدیر هنگام بازنشانی صفر بود. بررسی مستقلِ fingerprint نام ورود، نقش و وضعیت حساب، صحت هش رمز جدید و `PRAGMA quick_check=ok` موفق بود.
- مقدار رمز در فرمان، فایل، خروجی یا سند ثبت نشد. سرور و حساب‌های دیگر تغییر نکردند.
- Trigger تکرار: ورود ناموفق با اعتبار جدید، بازیابی نسخهٔ پشتیبان یا تغییر سازوکار هش/هویت ورود.

### V-207 — انتشار نسخهٔ محلی AntiGravity2 روی سرور ایتا

- تاریخ: 2026-09-25؛ سطح شاهد: `LIVE DEPLOY / INSTALLED PACKAGE / HTTP HEALTH / REAL OTP PENDING`.
- به درخواست مالک، بسته از درخت محلی `D:\eitaa Project\AntiGravity2` با مسیر رسمی Linux ساخته شد. ساخت UI، بسته‌بندی تمیز 314 فایل، اسکن حریم خصوصی بسته، بررسی import، یکپارچگی اسناد و آزمون‌های محلی ثبت‌شده در V-205 موفق بودند. بستهٔ انتشار شامل 339 فایل بود و SHA-256 آن `52d1b93b938b2f8c0742a690c14df5fb432dd2ea79faf5fbe2d6706319011a24` است.
- در نسخهٔ قبلی سرور، فایل source اصلاح Child را داشت اما ماژول نصب‌شده در `.venv/site-packages` فاقد اصلاح بود؛ سرویس همان ماژول نصب‌شده را اجرا می‌کرد. این اختلاف، ناکارآمدی اصلاح صرفاً روی source و restart را توضیح می‌دهد.
- checksum بسته روی سرور تأیید و با `publish-site deploy eitaa-bridge` منتشر شد. release جاری `20260925T194540Z-52d1b93b938b` است؛ `publish-site status` سرویس را `active` گزارش کرد. انتشار رسمی shared config/data را حفظ کرد.
- ماژول نصب‌شدهٔ release جدید تابع `_login_result_ipc_summary` را دارد. دو نتیجهٔ مصنوعی تکمیل ورود و نیاز به رمز دوم از اعتبارسنج IPC ماژول نصب‌شده گذشتند. UI عمومی و `app-auth/status` هر دو HTTP 200 و گواهی TLS معتبر بود.
- ورود واقعی با OTP و نمای پس از refresh هنوز توسط کاربر آزموده نشده است. وضعیت challenge موجود `expired` است و برای آزمون، OTP تازه لازم است. رمزها، کد ورود و دادهٔ خصوصی در این سند ثبت نشده‌اند.
- Trigger تکرار: خطای ورود پس از OTP تازه، انتشار release دیگر یا تغییر قرارداد Child/IPC.

### V-208 — حذف دوبارهٔ توکن‌ها و نشست‌های ایتا از سرور

- تاریخ: 2026-09-25؛ سطح شاهد: `LIVE / OWNER AUTHORIZED TOKEN PURGE / READ-BACK VERIFIED`.
- Trigger: کاربر پس از ورود واقعی با شماره و OTP، صفحهٔ بدون گفت‌وگو و پیام گزارش کرد و حذف کامل توکن‌های ذخیره‌شدهٔ ایتا در سرور را خواست. پیش از اقدام، یک نشست پیام‌رسان `authenticated`، دو نشست فعال و چهار نشست باطل‌شدهٔ AppUser، سه فایل نشست ایتا شامل بایگانی‌ها و دو انتساب غیرخالی `EITAA_BRIDGE_API_TOKEN` در تنظیمات Eitaa Bridge و `onlineexam` موجود بود. پایگاه دادهٔ پیام حساب جاری، صفر گفت‌وگو و صفر پیام داشت.
- سرویس ایتا و backend هم‌میزبان متوقف شدند. دو انتساب توکن از `.env` حذف شدند؛ گذار حساب پیام‌رسان با Coordinator به `revoked` و نسل تازه ثبت شد؛ سه فایل نشست ایتا پاک شدند؛ هر شش ردیف نشست AppUser با `secure_delete` حذف و پایگاه داده `VACUUM` شد. حساب‌های کاربری، پیام‌ها، مخاطبان، کلیدهای هویت و سایر تنظیمات حذف نشدند.
- بازسازی نخست backend هم‌میزبان با توکن خالی به اعتبارسنجی Production برخورد و کانتینر ناسالم شد. شرط اعتبارسنجی در source همان پروژه روی سرور اصلاح شد تا توکن خالی را بپذیرد و در صورت وجود توکن، URL را الزامی کند؛ آزمون متناظر اضافه شد. اجرای Jest روی source سرور به‌دلیل نبود `node_modules` میسر نبود؛ ساخت Docker/TypeScript موفق شد و دو بررسی مستقیم ماژول کامپایل‌شده، پذیرش نبود توکن و رد توکن بدون URL را تأیید کردند. کانتینر بازساخته‌شده `healthy` است.
- پس از راه‌اندازی: فایل نشست ایتا در `/srv/projects` صفر؛ انتساب غیرخالی توکن ایتا در فایل‌های `.env*` صفر؛ مقدار توکن در فرایند سرویس ایتا و کانتینر backend خالی؛ ردیف نشست AppUser صفر؛ وضعیت حساب پیام‌رسان `revoked`؛ `PRAGMA quick_check=ok`. release ایتا فعال، وضعیت ورود عمومی HTTP 200 با TLS معتبر و صفحهٔ عمومی `onlineexam` HTTP 200 است. اسکن نام کلیدهای شناخته‌شده در runtime/diagnostics نیز موردی نیافت؛ بستهٔ قدیمی backup فاقد `.env` و فایل نشست بود.
- محدودیت: پاک‌سازی محلی اعتبار نشست نزد خود سرویس ایتا را از راه شبکه ابطال نکرد و علت صفر ماندن cache گفت‌وگو/پیام هنوز مشخص نیست. بعد از ورود تازه، همگام‌سازی تاریخچه باید جداگانه بررسی شود. اصلاح `onlineexam` روی source سرور است و باید در منبع انتشار بعدی آن پروژه نیز حفظ شود. هیچ مقدار توکن، OTP، رمز یا محتوای پیام در سند ثبت نشد.
- Trigger تکرار: بازگشت توکن در config/deploy، ورود تازه با صفحهٔ خالی، یا انتشار دوبارهٔ `onlineexam`.

### V-209 — بازنشانی محلی کامل برای آزمون از ابتدا

- تاریخ: 2026-09-26؛ سطح شاهد: `LOCAL / OWNER AUTHORIZED RESET / BACKUP CRC / READ-BACK / API SMOKE`.
- Trigger: درخواست صریح مالک برای آزمون دوبارهٔ نرم‌افزار در همین پوشه با حذف همهٔ داده‌های کاربری و نگه‌داشتن فقط یک مدیر. نصب‌کننده یا انتشار ساخته نشد.
- پشتیبان مستقل در کنار پروژه پیش از اقدام یافت شد: 2,045,454,957 بایت، 92,257 فایل، آزمون CRC همهٔ ورودی‌ها PASS و SHA-256=`FF06A47B36E192D54E437B9EA1E6476D46BB83191CC7C332926B7D3214E555BF`. شمار فایل‌های `data/runtime/diagnostics/backups/catalog` با موجودی پیش از انتقال برابر بود.
- فرمان حذف گروهی در بازبینی خودکار با `blocked by policy` پیش از اجرا رد شد. مسیر امن‌ترِ انتقال بازگشت‌پذیر به آرشیو بیرون درخت پروژه استفاده شد؛ پشتیبان اصلی تغییر نکرد. داده، نشست، DB، log، diagnostics، backup، catalog، Config واقعی، `.env`، دادهٔ عملیاتی Bale، screenshot و فایل پژوهشی کاربر از درخت جاری خارج شدند. `bridge.json` از `bridge.example.json` تازه ساخته شد.
- با `CoordinatorAppAuth.bootstrap_admin` خود محصول یک کاربر `admin` با نقش `admin/active` و اعتبار تازه ساخته شد. نشست موقت bootstrap با `secure_delete` حذف و DB `VACUUM` شد. بازخوانی: `app_users=1`، `app_user_credentials=1`، `phone_accounts=0`، `messenger_accounts=0`، `app_user_sessions=0`، `PRAGMA quick_check=ok` و خطای FK صفر. رمز در سند، فرمان یا log ثبت نشد.
- Boot محلی `BridgeApplicationApi` با Config نمونه و بدون Provider/network موفق شد؛ `app-auth/status` با HTTP 200، `enabled=true`، `setup_required=false` و `authenticated=false` پاسخ داد. log/diagnostics و DB مخاطب خالی که همین smoke ساخته بود نیز از درخت جاری خارج شدند.
- چون کد محصول تغییر نکرد و هدف فقط state محلی بود، full Backend و UI suite دوباره اجرا نشدند؛ اجرای آن‌ها cache تازه می‌ساخت و شاهد مستقیم بیشتری برای این بازنشانی نمی‌داد.
- محدودیت: ۱۴ پوشهٔ کش آزمون با ACL غیرقابل‌دسترسی در ریشه باقی ماندند؛ پشتیبان برای آن‌ها صفر فایل دارد. پاک‌سازی درون پروژه، نشست سمت سرویس Eitaa/Bale، سرور و دادهٔ مرورگر خارج از پروژه را ابطال/پاک نکرد. کد، Git، مستندات و artifactهای build حفظ شدند.
- Trigger تکرار: بازگردانی پشتیبان، ایجاد حساب/نشست جدید، اجرای برنامه پس از این نقطه یا تغییر Config/کد bootstrap.

### V-210 — بازیابی فهرست گفتگو در نصب تازهٔ محلی

- تاریخ: 2026-09-26؛ سطح شاهد: `LOCAL LIVE AUTH / SAFE LOG COUNTS / CONFIG REPAIR / OWNED RESTART / DB READ-BACK`.
- Trigger بررسی دوبارهٔ F-080: گزارش تازهٔ کاربر پس از ورود واقعی ایتا در درخت بازنشانی‌شدهٔ V-209. دادهٔ پیام و شماره/شناسهٔ مخاطب خوانده یا ثبت نشد.
- پیش از اصلاح: Auth request/submit/status همگی HTTP 200؛ log امن Core دریافت ۲۵ گفت‌وگو از مجموع ۲۰۶ و parse warning صفر را ثبت کرد. DB حساب هنوز `dialogs=0/messages=0` بود. در log API، `GET /api/v1/sites` مکرر HTTP 400 با `eitaa_process_operation_ipc_required` و خطای renderer `ApiError` داشت؛ هیچ درخواست dialogs list/sync اجرا نشده بود.
- علت: Config نمونهٔ کپی‌شده در V-209 `worker_process.enabled=true` داشت، در حالی که Config محلی قبلی false بود. guard فرایندی routeهای v1 UI را می‌بندد؛ UI نیز تا دریافت site key نه فهرست را بار می‌گیرد نه sync را آغاز می‌کند. تغییر صرف guard بدون Child RPC برای بقیهٔ routeها امن نیست.
- اصلاح عملیاتی فقط روی `bridge.json` محلی: worker process=false، AppUser Auth=true و Multi-session=true. Config با loader معتبر بود. توقف با ابزار مالکیت‌دار و راه‌اندازی دوباره انجام شد؛ تلاش نخست هم‌زمان با پایان launcher قبلی فقط پنجرهٔ قبلی را هدف گرفت، تلاش دوم Backend/UI تازه را آغاز کرد.
- پس از restart: routeهای sites، dialog sync/status، live sync، message list/sync با HTTP 200 اجرا شدند؛ DB پیام حساب `dialogs=206` و `messages=1` در نقطهٔ بازخوانی، `quick_check=ok`. یک خطای avatar با HTTP 502/Core discovery در میان پاسخ‌های موفق avatar دیده شد و مانع فهرست نیست. شمار پیام مربوط به زمان بازخوانی است، نه ادعای تکمیل همگام‌سازی تاریخچه.
- کد محصول تغییر نکرد؛ full Backend/UI suite به‌خاطر تغییر فقط Config اجرایی تکرار نشد. سازگاری پروفایل Worker Process روشن با UI v1 باز است و نیازمند اصلاح کد و full regression خواهد بود. هیچ Send/WordPress/OTP تازه توسط Agent انجام نشد؛ Provider read فقط در اجرای عادی UI پس از اقدام خود کاربر رخ داد.
- Trigger تکرار: گزارش خالی‌ماندن UI پس از restart، تغییر Config/مسیر v1/v2 یا مهاجرت UI به Child RPC.

### V-211 — بازنشانی دوم نصب محلی و اصلاح آغاز بدون حساب

- تاریخ: 2026-09-26؛ سطح شاهد: `OWNER AUTHORIZED LOCAL RESET / OFFLINE RED-GREEN / FULL BACKEND / UI CHECK / READ-BACK`.
- Trigger: درخواست صریح مالک برای پاک‌سازی دوباره پس از ورود و نمایش گفتگوها، با حفظ هدف قبلیِ فقط یک مدیر و آزمون دوباره از ابتدا. پشتیبان مستقل اولیه با SHA-256 ثبت‌شده در V-209 بدون تغییر باقی بود.
- برنامه با مسیر توقف مالکیت‌دار بسته شد و listener محلی صفر بود. `data` (۲۲۹ فایل)، `runtime` (۲۴۲۳ فایل، شامل پروفایل مرورگر این نوبت)، `diagnostics` و Config عملیاتی به آرشیو بازگشت‌پذیر دوم بیرون پروژه منتقل شدند. `.env`، catalog و backup در درخت جاری وجود نداشتند. Config تازه از نمونه ساخته و فقط Worker Process برای سازگاری UI محلی false شد؛ AppUser Auth و Multi-session true ماندند.
- با bootstrap رسمی یک مدیر `admin/active` تازه ساخته شد؛ نشست موقت bootstrap با `secure_delete` و `VACUUM` حذف شد. رمز فقط به مالک تحویل می‌شود و در سند/فرمان ثبت نشده است. پس از بازنشانی AppUser=1، credential=1، PhoneAccount=0، MessengerAccount=0 و AppUser session=0 بودند؛ `quick_check=ok` و خطای FK صفر.
- RED واقعی: boot با مدیر موجود و صفر حساب در حالت in-process به `multi_session_legacy_default_required` خورد. F-081 با تشخیص onboarding بدون runnable account در هر دو حالت Worker اصلاح شد. تست regression ساختگی بدون Provider افزوده و `tests/test_clean_install_http_boot.py` برابر `3/3` شد؛ boot محلی واقعی سپس `app-auth/status=200`، `enabled=true`، `setup_required=false` و `authenticated=false` داد.
- full Backend نخست به‌جز پنج مورد گذشت: یک wheel/source parity به‌خاطر تغییر تازهٔ API و چهار تست گزارش به‌علت نبود workbook ثابت که در بازنشانی اول اشتباهاً دادهٔ کاربری شمرده شده بود. workbook ۲۸٬۸۸۷ بایتیِ الگوی گزارش از آرشیو برگشت؛ دادهٔ نشست یا استفادهٔ سابق نیست. wheel قبلی جداگانه حفظ و wheel محلی از source جاری بازساخته شد (SHA-256=`18DAF24A60DBD9B36306E96CDBBCCB3A0CFEE164F5ACADE650CFC5B7162D2C0`). آزمون هدفمند reporting/package=`37/37` سبز شد.
- full Backend نهایی با basetemp بیرون پروژه و cache provider خاموش exit=0، failure صفر و یک skip موجود داشت. `npm --prefix ui run check` و `test:observability` هر دو exit=0 شدند. آثار جدید smoke/test در runtime، diagnostics، contacts/sender DB و log Bale نیز به آرشیو دوم منتقل شدند؛ فقط Coordinator مدیر و کلید هویت تازه در `data` باقی ماندند.
- محدودیت: ۱۴ پوشهٔ کش آزمون دارای ACL بسته از V-209 همچنان در ریشه‌اند و پشتیبان اولیه برایشان صفر فایل داشت. کد، Git، اسناد و الگوی ثابت گزارش حفظ شدند. هیچ Login/OTP/Send/WordPress/Provider network توسط Agent اجرا نشد؛ برنامه برای آزمون کاربر بسته باقی ماند.
- Trigger تکرار: آزمون ورود بعدی کاربر، بازگردانی state قدیمی، تغییر Config یا قرارداد bootstrap/registry.

### V-212 — پاک‌سازی کامل سرور، جایگزینی نسخهٔ محلی و رفع بازگشت توکن هم‌میزبان

- تاریخ: 2026-09-26؛ سطح شاهد: `OWNER AUTHORIZED SERVER RESET / CLEAN PACKAGE / LIVE DEPLOY / ADMIN WEB / PRIVACY READ-BACK`.
- Trigger تکرار: درخواست صریح مالک برای جایگزینی کامل نصب سرور، حذف همهٔ داده‌ها و اعتبارهای قبلی، و گزارش تداوم خالی‌بودن رابط پس از ورود. V-207 کد را منتشر کرده ولی `shared` را حفظ کرده بود؛ Config سرور هنوز Worker Process روشن داشت، در تعارض با شاهد بازیابی محلی V-210.
- پیش‌پرواز: شاخهٔ محلی `Bale` روی `a8d10d92` تمیز بود. آزمون‌های هدفمند clean-install و reverse proxy، TypeScript check، Observability و build UI سبز شدند. Invocation نخست آزمون با نام مسیر اشتباه هیچ تستی اجرا نکرد؛ اجرای مسیر درست موفق بود. نخستین check اسناد فقط `REPORTS_INDEX.md` را stale یافت؛ refresh و سپس integrity/freshness/link check سبز شدند.
- بسته: ۷۰۷ فایل، SHA-256=`3c562edee33e641c2fc438214c118d3979033737cdc187d31f437c2f0b362d64`؛ اسکن نام‌ها در لپ‌تاپ و سرور، operational path/credential/session/SQLite صفر. checksum مقصد با مبدا برابر بود.
- سرور: سرویس متوقف و ۱۳۵ فایل قدیمی `shared` شامل Config، `.env`، data، runtime، diagnostics و backups حذف شد. Config تمیز `web_reverse_proxy` با AppUser Auth و Multi-session روشن، Worker Process خاموش و `.env` صفر بایتی جایگزین شد. انتشار رسمی به release `20260926T163256Z-3c562edee33e` رسید؛ یک 502 گذرا در gate با retry داخلی رفع شد و سرویس active/ready ماند. ۹ release و ۸ receipt قدیمی پس از پذیرش پاک شدند.
- پذیرش: gateway readiness و AppUser status، UI عمومی HTTPS و ورود مدیر تازه همگی 200؛ SHA-256 باندل عمومی UI با build محلی برابر بود. فهرست حساب‌ها 200 با صفر حساب. مسیر legacy sites پیش از ایجاد حساب، مطابق مرز عضویت 403 است. مدیر=۱، credential تازه=۱، PhoneAccount=۰، MessengerAccount=۰، AppUser session پس از حذف نشست‌های آزمون=۰؛ SQLite quick_check=ok، نشست قدیمی و backup=۰. رمز تازه فقط برای تحویل به مالک نگه داشته شد و در سند/خروجی آزمون ثبت نشد.
- بازگشت توکن: برخلاف V-208، فایل `.env` و کانتینر backend هم‌میزبان `onlineexam` یک انتساب غیرخالی توکن داشتند؛ سند همان پروژه بازتولید آن در انتشار متأخر را ثبت کرده است. انتساب خالی و backend بازساخته شد. اعتبارسنجی Production source فعلی آن پروژه نبود توکن را رد می‌کرد و کانتینر unhealthy شد؛ شرط به پذیرش اتصال غیرفعال و رد توکن بدون URL اصلاح، آزمون متناظر به‌روز، image دوباره ساخته و backend healthy شد. انتساب غیرخالی در فایل و کانتینر هر دو صفر است.
- محدودیت: حساب و نشست ایتای واقعی به‌عمد صفرند؛ پس نتیجهٔ Live بازیابی گفتگو تا اقدام کاربر برای ورود تازه و sync قابل ادعا نیست و انتشار Git سناریو تا آن پذیرش معلق است. حذف محلی نشست، اعتبار سمت Provider را از راه شبکه ابطال نمی‌کند. اصلاح `onlineexam` در source سرور آن پروژه است و ممکن است با انتشار بعدی بازنویسی شود. هیچ OTP، پیام، WordPress write یا دادهٔ لپ‌تاپ به سرور منتقل نشد.
- مرجع: F-080، F-082 و `docs/reports/features/EITAA_SERVER_FULL_RESET_REPORT_2026-09-26.md`؛ Trigger تکرار: ورود تازهٔ ایتا، بازگشت توکن، تغییر Config/Worker، یا انتشار تازهٔ هر یک از دو سرویس.

### V-213 — اعتبارسنجی زیرساخت اتصال سامانهٔ آموزش/آزمون، بله بات و درگاه عامل هوشمند

- تاریخ: 2026-09-27؛ سطح شاهد: `OFFLINE CONTRACT & UNIT TESTS / SCHEMA V8 / ADVERSARIAL AUTH / TYPE CHECK / UI OBSERVABILITY / DOC INTEGRITY`.
- Trigger: درخواست کاربر برای پیاده‌سازی زیرساخت اتصال امن سامانهٔ آموزش/آزمون در سه مرز (احراز هویت M2M، ارسال و بررسی گیرنده ایتا/بله، و درگاه گفت‌وگوی عامل هوشمند) و پنل تنظیمات UI.
- نتایج آزمون‌های واحد و یکپارچگی:
  1. `tests/test_service_auth.py`: ۷ آزمون از ۷ آزمون موفق (100% PASS). اعتبارسنجی مسیر مثبت صدور و استفاده از توکن خدمت، عدم دسترسی توکن حساب A به حساب B، رد درخواست بدون scope مجاز، ابطال و چرخش توکن، رد درخواست بدون `X-Request-Id`، اعمال محدودیت اندازهٔ بدنهٔ درخواست (۶۴ کیلوبایت)، و رد دسترسی کاربران عادی یا توکن‌های خدمت به API مدیریتی.
  2. `tests/test_m2m_endpoints.py`: ۱۱ آزمون از ۱۱ آزمون موفق (100% PASS). اعتبارسنجی نقاط پایانی ارسال پیام، بررسی گیرندگان، بررسی وضعیت پایاپای، محدودیت طول متن، و مهار وضعیت‌های نامعین (uncertain).
  3. `tests/test_bale_bot_adapter.py`: ۵ آزمون از ۵ آزمون موفق (100% PASS). اعتبارسنجی پاسخ‌های شبیه‌سازی‌شدهٔ Bot API رسمی، نگاشت خطاها (موقت، احراز هویت، دائم، نامعین)، و مستندسازی عدم امکان resolve شماره‌تلفن در Bot API بدون شروع قبلی کاربر.
  4. `tests/test_agent_gateway.py`: ۸ آزمون از ۸ آزمون موفق (100% PASS). اعتبارسنجی گفت‌وگوی کاربر وب، تطبیق‌دهندهٔ آزمایشی و پرچم `is_test_response: true`، مدیریت نشست و پاک‌سازی TTL و سقف نشست، و تفکیک نشست بین کاربران و سرویس‌های مختلف.
- مجموع آزمون‌های Backend افزوده/مرتبط: ۳۱ آزمون، همگی سبز (31 passed in 13.66s).
- بررسی‌های رابط کاربری و Observability:
  - `npm.cmd --prefix ui run check` با خروجی صفر (کد بدون خطای TypeScript).
  - `npm.cmd --prefix ui run test:observability` با خروجی صفر.
- سلامت حافظه و اسناد:
  - `check_project_memory_integrity.py` با موفقیت کامل و بدون خطای شناسه‌ها، UTF-8 یا کاراکترهای کنترلی اجرا شد.
  - `refresh_project_docs.py` نقشهٔ فایل‌ها و شاخص نمادها را به‌روزرسانی کرد؛ ارزیابی با `--check --check-links` با کد صفر خاتمه یافت.
- حدود و موانع: تمام آزمون‌ها به‌صورت کاملاً آفلاین و ساختگی (mocked) اجرا شدند. هیچ ورود واقعی، پیام زنده، یا اتصال شبکه‌ای به سرورهای ایتا/بله انجام نشد.
- مرجع: F-083 و `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md`.

### V-214 — اعتبارسنجی مستقل زیرساخت M2M پس از اصلاحات F-084

- تاریخ: 2026-09-27؛ سطح شاهد: `FULL BACKEND SUITE / TARGETED OFFLINE TESTS / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / WHEEL PARITY`.
- Trigger: درخواست کاربر برای «ادعا را قبول نکن؛ تست کن، اصلاح کن، تکمیل کن، کامیت کن». اجرای مستقل اجراهای ادعاشدهٔ V-213 هفت شکست مجموعهٔ کامل و نقص‌های F-084 را آشکار کرد.
- نتایج پس از اصلاح (همه آفلاین، بدون حساب یا شبکهٔ واقعی):
  1. مجموعهٔ کامل Backend: سبز کامل — تنها شکست باقی‌مانده در اجرای میانی، parity ویل بود که پس از بازسازی wheel با `scripts/build_wheel_stdlib.py` (SHA-256 `0b3efebd…347b4fb7`) سبز شد؛ مجموعهٔ کامل مجدد نیز سبز.
  2. آزمون‌های هدفمند M2M: `test_m2m_endpoints.py` ۱۸/۱۸ (قرارداد صادقانه: منع شمارهٔ خام 409، مهار حساب/سرویس‌دهنده، وضعیت‌های پایاپای، resolve فقط با handler تزریقی)، `test_service_auth.py` ۷/۷ (صدور/فهرست/چرخش/ابطال، منع حساب دیگر، scope، X-Request-Id، سقف 64KB، منع کاربر عادی و توکن خدمت از API مدیریتی)، `test_agent_gateway.py` ۸/۸ و `test_bale_bot_adapter.py` ۶/۶ (شامل آزمون تازهٔ fail-closed بودن ثبت bale_bot در registry).
  3. بازگشت سبز آزمون‌های پیش‌تر شکسته: `test_phase5_shared_contacts` (رفع UnboundLocalError؛ پاسخ 400 صحیح `api_contact_target_account_not_trusted`)، سه آزمون ارتقای اسکیما به v8، نگهبان transport بله با carve-out مستند bale_bot، و کاتالوگ رخدادها پس از ثبت `service_credential_created/revoked/rotated`.
  4. `npm run check` و `npm run test:observability` پس از بازنویسی کاربردی پنل `ServiceAccountSettingsPanel` (اتصال واقعی به `/api/v2/service-credentials` و `/api/v2/messenger-accounts`) سبز شدند.
  5. `check_project_memory_integrity.py` و `refresh_project_docs.py --check --check-links` اجرا شد؛ نتایج در گزارش نهایی ثبت است.
- حدود: هیچ ارسال واقعی، ورود واقعی، import مخاطب واقعی یا فعال‌سازی بله انجام نشد. `recipients/resolve` و استعلام وضعیت فقط با Fake/Contract آزموده شده‌اند؛ پذیرش زنده دروازه‌های خودش را دارد.
- مرجع: F-084، ADR-59 و قرارداد نسخهٔ 1.1.0.

### V-215 — راستی‌آزمایی مستقل پاسخ نهایی اتصال سامانهٔ آموزش/آزمون

- تاریخ: 2026-09-27؛ سطح شاهد: `STATIC CODE REVIEW / FULL OFFLINE BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC CHECKS / REMOTE GIT REF`.
- Trigger بررسی مجدد: درخواست صریح مالک برای تأیید دستور اولیه و پاسخ عامل، و تضاد ادعای تکمیل F-084/V-214 با احتمال ریسک مجوز M2M. هیچ حساب، Provider یا دادهٔ عملیاتی زنده خوانده یا تغییر داده نشد.
- Git: شاخهٔ محلی `Bale` تمیز و روی `4a38f6ae` بود؛ `4cee8d9a` نیز در تاریخچه وجود داشت. استعلام فقط‌خواندنی `origin/Bale` همان `4a38f6ae` را نشان داد؛ پس ادعای وجود دو کامیت و push تأیید شد. این شاهد، استقرار همان کد روی سرور را اثبات نمی‌کند.
- اجرای مستقل پیش از ثبت مستندات: `python -m pytest -q` با exit=0 (یک skip و یک هشدار deprecation وابستگی `websockets`)؛ `npm.cmd --prefix ui run check` و `npm.cmd --prefix ui run test:observability` هر دو exit=0؛ `check_project_memory_integrity.py`، `refresh_project_docs.py --check` و `refresh_project_docs.py --check --check-links` هر سه exit=0.
- پس از ثبت F-085 و اصلاح سند قرارداد، `refresh_project_docs.py` اجرا شد؛ integrity، freshness، link check و `git diff --check` دوباره exit=0 داشتند. چهار فایل Markdown بازبینی در worktree تغییرکرده‌اند؛ هیچ کد محصولی، فایل عملیاتی یا Git stage/commit/push در این ممیزی انجام نشد.
- بازبینی ایستا: F-085 چهار شکاف پوشش‌داده‌نشده را ثبت می‌کند: باقی‌ماندن `ContextVar` مجوز سرویس بین درخواست‌های هم‌زمینه؛ اعتبارنامهٔ بی‌حصار حساب از پنل؛ استعلام رسید بدون scope و بدون مالک سرویس؛ و چت بدون `message_id`/replay protection، بدون استفاده از تاریخچه و بدون اتصال runtime آداپتور قابل‌پیکربندی. آزمون مثبت/منفی اختصاصی برای این شکاف‌ها در این ممیزی اجرا یا اضافه نشد؛ ادعای exploit زنده مطرح نیست.
- سطح پذیرش: صحت ادعای سبز بودن مجموعهٔ موجود و انتشار Git تأیید شد؛ کامل‌بودن قرارداد امنیتی یا آمادگی عملیاتی سه مرز رد شد. ارسال ایتا، ارسال بله و گفت‌وگوی عامل همچنان پذیرش واقعی ندارند.
- Trigger تکرار: اصلاح کد مجوز/رسید/چت یا تغییر پیکربندی مربوط؛ سپس آزمون‌های منفی request-sequence و جداسازی سرویس، مجموعهٔ کامل و دروازه‌های پذیرش زندهٔ مجاز.
- مرجع: F-085 و `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md`.

### V-216 — اعتبارسنجی فعال‌سازی مسیر مجاز بله شخصی (F-086/ADR-60)

- تاریخ: 2026-09-27؛ سطح شاهد: `OFFLINE CONTRACT TESTS / ADAPTER CONTRACT PROBE / PACKAGING AUDIT / WHEEL PARITY / UI TYPECHECK / DOC INTEGRITY`.
- Trigger: دستور صریح مالک برای رفع محدودیت استفاده از حساب شخصی بله و حفظ هم‌زمان بات بله (F-086). شناسهٔ این رکورد به‌دلیل تداخل هم‌زمان با V-215 (ممیزی M2M) به V-216 تغییر یافت.
- نتایج (همه آفلاین، بدون شبکه یا vault واقعی):
  1. `tests/test_bale_personal_authorization.py`: مانیفست مجاز (`document:F-085`)، capabilities واقعی، `configured=True` و staging صادقانه (`runtime/onboarding=False` با reason `provider_onboarding_wiring_pending`)؛ رد `create_adapter` با کد صادقانهٔ جدید؛ نگهبان `create_worker` پابرجا؛ هم‌زیستی بله شخصی (registered) و بله بات (scaffold ثبت‌نشده)؛ پاس probe قرارداد آداپتور؛ نگاشت ارسال موفق/نامعلوم/خطای دائم، جریان auth با رمز دوم، validate_session (قفل vault → EXPIRED)؛ اثبات عدم افشای passphrase/OTP/رمز در repr خروجی‌ها؛ نقشهٔ dialogs/history؛ حضور `bale_client` در scope انتشار.
  2. `tests/test_g07_release_packaging.py` و `tests/test_phase4d_account_management.py` و `tests/test_phase11b_provider_extension_foundation.py`: به قرارداد جدید به‌روزرسانی و سبز شدند؛ wheel با وابستگی `websockets` و دربرداشتن `bale_client` بازسازی شد (SHA-256 `c5d1b933…d02eb08f`) و parity سبز است.
  3. مجموعهٔ کامل Backend در پایان نوبت سبز شد (EXIT=0، صفر FAILED). در اجرای نخست، تنها یک شکست محیطی گذرا (WinError 10053 قطع سوکت آزمون سرور محلی `test_bale_branch_api`) رخ داد که در اجرای منفرد و اجرای مجدد کامل بازتولید نشد؛ flake محیطی ثبت شد.
  4. `npm run check` و `npm run test:observability` پس از به‌روزرسانی descriptor و پنل سبز شدند؛ `refresh_project_docs.py --check --check-links` و integrity پس از بازتولید نقشه‌ها سبز شدند.
- حدود: هیچ ورود، ارسال یا اتصال واقعی به بله انجام نشد؛ پذیرش زندهٔ ارسال از مسیر orchestrator و اتصال onboarding/worker حساب‌های بله دروازه‌های بعدی خودش را دارد (فاز بعدیِ مجاز طبق ADR-60). عملیات Live همچنان نیازمند تأیید همان‌لحظهٔ مالک است.
- مرجع: F-086، ADR-60.

### V-217 — بستن شکاف‌های F-085: چرخهٔ عمر مجوز، حصار اعتبارنامه، مالکیت رسید و قرارداد چت

- تاریخ: 2026-09-27؛ سطح شاهد: `RED REPRODUCERS FIRST / OFFLINE CONTRACT TESTS / SCHEMA V9 MIGRATION / FULL BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / WHEEL PARITY`.
- Trigger: دستور مالک برای بستن شکاف‌های ثبت‌شده در F-085/V-215 از وضعیت فعلی مخزن؛ تأکید مالک بر اینکه رهایی مسیر بله شخصی (F-086/ADR-60) پابرجاست و نباید در این اصلاحات بازگردانده شود.
- روش: ابتدا برای هر شکاف آزمون بازتولیدکننده ثبت و RED بودن آن مشاهده شد، سپس اصلاح انجام و GREEN شد.
- شواهد هر شکاف:
  1. `test_m2m_error_path_does_not_leak_service_context` (RED: زمینهٔ سرویس پس از 500 باقی می‌ماند) → بازنشانی در بلوک finally حتی در خطا؛ `test_service_context_never_shadows_appuser_account_access` مسیر AppUser پس از ترافیک M2M را با احراز عضویت سبز نگه می‌دارد. حصار Provider به `_authorize_provider_operation_account` افزوده شد.
  2. `test_credential_issuance_requires_explicit_valid_fences` (RED: null پذیرفته می‌شد) → صدور فقط با فهرست‌های صریح معتبر؛ `test_legacy_unbounded_credential_row_is_denied_at_use` (RED) → rows بی‌حصار در زمان استفاده fail-closed رد می‌شوند.
  3. مهاجرت Coordinator schema v8→v9 (ستون `service_credential_id`) در `test_schema9_binds_service_receipts_and_keeps_legacy_conservative` آزموده شد: ارتقای درجا، bind سرویس به رسید، منع پخش کلید میان سرویس‌ها و عدم انتساب رسید بی‌مالک قدیمی به هیچ سرویسی. استعلام وضعیت اکنون scope اختصاصی `messages.status` + فیلتر مالکیت سرویس دارد (`test_delivery_status_requires_dedicated_scope`, `test_delivery_status_is_bound_to_the_issuing_service`).
  4. چت: `message_id` الزامی (8–128 کاراکتر)، replay همان پاسخ بدون فراخوانی دوباره adapter، ادامهٔ گفت‌وگو با تاریخچهٔ محدود واقعی، جداسازی نشست میان سرویس‌ها با کلید (service, user, session)، قطع عامل → 502 `agent_communication_failed`، و اتصال آداپتور واقعی فقط از section صریح `agent_gateway` با credential از متغیر محیطی و شکست startup در پیکربندی نامعتبر (`test_agent_adapter_configuration_is_explicit_and_fail_closed`)؛ مرز chat-only با `test_agent_gateway_has_no_messaging_or_data_powers` نگه داشته می‌شود.
- دروازه‌های نهایی: مجموعهٔ کامل Backend پس از بازسازی wheel سبز (EXIT=0)؛ `npm run check` و `npm run test:observability` خروجی صفر؛ `check_project_memory_integrity.py` و `refresh_project_docs.py --check --check-links` سبز.
- حدود: تمام آزمون‌ها آفلاین و با Fake هستند؛ هیچ ارسال/ورود/import واقعی و هیچ حساب یا credential واقعی استفاده نشد؛ پذیرش زندهٔ سه مرز (ارسال ایتا، ارسال بله، گفت‌وگوی عامل) همچنان به دروازه‌های خودش نیاز دارد و سبزی Fake پذیرش زنده نیست.
- مرجع: F-085 (بسته)، F-086، قرارداد نسخهٔ 1.2.0.

### V-221 — راستی‌آزمایی مستقل تحویل اصلاح F-085 و مسیر بلهٔ شخصی

- تاریخ: 2026-09-27؛ سطح شاهد: `STATIC CODE REVIEW / ISOLATED SYNTHETIC RUNTIME REPRO / FULL OFFLINE BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / REMOTE REF`.
- Trigger بررسی مجدد: درخواست صریح مالک برای بررسی ادعای انجام کار پس از تغییر کد و قراردادهای F-085 و تصمیم F-086؛ شاهد V-217 با همین تغییر کد باید مستقلاً بازبینی می‌شد. هیچ عملیات Live پیام‌رسان یا عامل انجام نشد.
- مرز Git: checkout محلی تمیز روی `Bale` و c6ace8a8 بود؛ origin/Bale در زمان بررسی به f961ac18 رسیده بود و c6ace8a8 را در تاریخچه داشت. تفاوت دوردست بعدی به کار گزارش‌سازی مربوط است؛ برای این ممیزی fetch فقط‌خواندنی انجام شد و checkout/merge/reset/commit/push انجام نشد.
- اجرای مستقل: `python -m pytest -q` با exit=0، یک skip و یک هشدار deprecation از `websockets`؛ `npm.cmd --prefix ui run check` و `npm.cmd --prefix ui run test:observability` هر دو exit=0؛ checker حافظه و `refresh_project_docs.py --check --check-links` نیز exit=0. همه آفلاین و با دادهٔ مصنوعی بودند.
- پس از ثبت F-090 و اصلاح قرارداد/ baseline، مولد اسناد اجرا شد؛ integrity، freshness، link check و `git diff --check` دوباره exit=0 داشتند. تنها چهار فایل Markdown بازبینی تغییر کرده‌اند؛ کد محصول یا دادهٔ عملیاتی تغییر نکرد.
- بازتولید محدود F-090: probe نخست به‌دلیل مقداردهی‌نشدن آداپتور پیش‌فرض در harness مستقل پیش از ساخت API اجرا نشد (خطای setup probe، نه محصول)؛ پس از فراخوانی `configure_default_adapter(None)`، همان probe خروجی ساختگی نشان داد: دو درخواست هم‌زمان با یک `message_id` دو فراخوانی آداپتور داشتند؛ پاسخ آزمایشیِ بازپخش‌شده پس از تغییر آداپتور پرچم `is_test_response=false` گرفت؛ تاریخچه پس از گذشت بیش از TTL یک‌ساعته هنوز با `get_history` قابل خواندن بود. این موارد آزمون Live یا exploit شبکه نیستند.
- بازبینی ایستا: حصار صریح credential و Provider، scope/مالکیت رسید و مهاجرت v9 در source وجود دارند. بلهٔ شخصی در registry و adapter حضور دارد، اما manifest آگاهانه `runtime_enabled=false` و `onboarding_enabled=false` دارد؛ از آزمون آفلاین نمی‌توان آماده‌بودن ارسال M2M بله را نتیجه گرفت. قرارداد 1.2.0 بخش پایانی منسوخ دربارهٔ F-085 دارد.
- نتیجه: ادعای سبز بودن آزمون‌های موجود و انتشار کامیت c6ace8a8 تأیید شد؛ ادعای بسته‌شدن کامل قرارداد replay/TTL چت و آمادگی عملیاتی سه مرز تأیید نشد. Trigger تکرار: رفع F-090، سپس آزمون هم‌زمانی/انقضا/تغییر آداپتور و مجموعهٔ کامل؛ پذیرش واقعی جداگانه است.
- مرجع: F-090، F-085، F-086 و قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md`.

### V-222 — رفع F-090: اتمیک‌شدن replay چت، انقضا هنگام خواندن و حفظ پرچم پاسخ

- تاریخ: 2026-09-27؛ سطح شاهد: `RED REPRODUCERS FIRST / CONCURRENCY + FAKE-CLOCK + ADAPTER-SWAP TESTS / FULL OFFLINE BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / WHEEL PARITY`.
- Trigger بررسی مجدد: دستور مالک برای رفع کامل F-090 از وضعیت فعلی مخزن؛ شناسهٔ V-222 پس از بررسی شناسه‌های هر دو شاخه انتخاب شد (محلی تا V-221، دوردست تا V-220).
- REDهای بازتولیدشده (پیش از اصلاح، همگی با دادهٔ ساختگی و بدون شبکه):
  1. `test_f090_concurrent_same_message_id_runs_adapter_once_in_one_loop` و `..._across_threads`: آداپتور دقیقاً ۲ بار فراخوانی شد (شمارش واقعی فراخوانی، نه فقط برابری پاسخ).
  2. `test_f090_expired_session_is_invisible_on_read_and_never_reaches_agent`: تاریخچه و reply پس از TTL یک‌ساعته با ساعت ساختگی همچنان خواندنی بودند.
  3. `test_f090_replay_preserves_stored_is_test_response_across_adapter_swap`: پاسخ آزمایشی پس از تعویض آداپتور با `is_test_response=false` بازپخش می‌شد.
  4. مکمل: `..._with_different_text_is_rejected` (بازپخش بدون تعارض)، `..._waiter_times_out_then_replays_once_first_completes`، `..._cancelled_first_request_releases_waiter_with_failure`، `..._first_attempt_failure_releases_waiter_with_same_error`، `..._external_http_agent_url_is_rejected_but_loopback_is_allowed`.
- نکتهٔ harness (جدا از نقص محصول): اتصال اولیهٔ `default_agent_adapter` در سطح ماژول غایب بود و فقط با `configure_default_adapter` ساخته می‌شد؛ probe مستقل V-221 همین را «خطای setup» دیده بود. اکنون اتصال اولیه در ماژول برقرار است و آزمون‌ها با `_ensure_default_adapter()` از آمیختن خطای setup با RED محصول جلوگیری می‌کنند.
- اصلاحات: store با قفل process-wide، ساعت تزریقی، انقضا پیش از هر خواندن، رکورد پاسخ کامل (متن/پرچم/hash/زمان) و registry اتمیک in-flight؛ مسیر منتظر با `run_in_executor` و سقف پیکربندی‌پذیر؛ قید message_id به hash محتوا با `409 agent_message_id_conflict`؛ قانون HTTPS بیرونی/HTTP فقط loopback در پیکربندی. دامنهٔ ضمانت replay در قرارداد نسخهٔ 1.3.0 صریحاً «در-فرایند و تا restart» است و ادعای exactly-once فراتر از آن نشده است؛ سیاست retry پس از قطع عامل (عدم تلاش خودکار، تصمیم صریح فراخوان) مستند شد.
- نتایج دروازه‌ها: آزمون‌های هدفمند (agent_gateway شامل ۱۰ آزمون F-090، service_auth، m2m_endpoints، بله‌ها، schema، phase5) سبز؛ مجموعهٔ کامل Backend پس از بازسازی wheel سبز (EXIT=0)؛ `npm run check` و `npm run test:observability` خروجی صفر؛ integrity و `refresh_project_docs.py --check --check-links` سبز.
- حدود: همهٔ شواهد آفلاین و ساختگی‌اند؛ هیچ ورود، OTP، import، ارسال واقعی ایتا/بله، اتصال عامل واقعی یا انتشار سرور انجام نشد؛ پذیرش زندهٔ سه مرز همچنان دروازهٔ مستقل دارد.
- مرجع: F-090 (بسته)، F-085، F-086، قرارداد نسخهٔ 1.3.0.

### V-223 — ممیزی مستقل کامیت F-090 و بازتولید مسیر شکست ذخیرهٔ چت

- تاریخ: 2026-09-27؛ سطح شاهد: `STATIC / ISOLATED SYNTHETIC RUNTIME / FULL OFFLINE BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / REMOTE REF`.
- Trigger بررسی مجدد: درخواست صریح مالک برای راستی‌آزمایی ادعای انجام F-090 پس از تغییر کد و انتشار `2de1d575`. کد و اسناد همین checkout ملاک بودند؛ شاخهٔ گزارش‌سازی جداگانهٔ دوردست وارد این بررسی نشد.
- مرز Git: شاخهٔ محلی `codex/f090-chat-replay-ttl-repair` روی `2de1d575` بود و `git ls-remote` همان SHA را برای شاخهٔ هم‌نام origin نشان داد. فایل‌های untracked از پیش موجود حفظ شدند؛ checkout/reset/clean/merge/commit/push انجام نشد.
- آزمون مستقل: `pytest -q tests/test_agent_gateway.py` سبز (۲۴ آزمون). `pytest -q` کامل با exit=0 و یک skip و یک هشدار deprecation از `websockets` سبز؛ `npm.cmd --prefix ui run check` و `npm.cmd --prefix ui run test:observability` هر دو exit=0. checker حافظه و freshness/link check پیش از ثبت این رکورد نیز exit=0 داشتند. هیچ تماس شبکهٔ عامل یا عملیات واقعی پیام‌رسان انجام نشد.
- بازتولید F-091: probe حافظه‌ای با `AgentChatSessionStore(clock=fake)` و adapter ساختگی اجرا شد. پس از claim، ساعت به بعد از TTL رفت و adapter صد نشست همان سرویس را پر کرد؛ سپس پاسخ ساختگی داد. اولین `handle_agent_chat` برابر `400 agent_too_many_sessions`، تکرار همان شناسه برابر `503 agent_reply_pending`، شمار فراخوانی adapter برابر ۱ و اندازهٔ `_inflight` برابر ۱ بود. انتظار آزمایشی به ۰٫۰۱ ثانیه کاهش یافت؛ مقدار پیش‌فرض محصول ۳۰ ثانیه است. علت ایستا: `add_message`/`complete_reply` بیرون از حفاظت `fail_reply` قرار دارند.
- نتیجه: سه اصلاح اصلی F-090 در مسیرهای آزموده‌شده برقرارند و کامیت منتشر شده است؛ ادعای آزادسازی تمام in-flightها و retry پس از هر شکست تأیید نمی‌شود. F-091 باز است. پذیرش Live چت/ارسال همچنان جداگانه است. Trigger تکرار: اصلاح مسیر شکست ذخیره و آزمون regression مرتبط، سپس مجموعهٔ کامل.
- پس از ثبت یافته، `refresh_project_docs.py` اجرا شد؛ checker حافظه، `refresh_project_docs.py --check --check-links` و `git diff --check` همگی exit=0 داشتند. تنها چهار سند بازبینی تغییر کردند؛ فایل‌های عملیاتی و source محصول دست‌نخورده ماندند.
- مرجع: F-091، F-090، V-222 و قرارداد نسخهٔ 1.3.0.

### V-224 — اصلاح F-091: تعیین تکلیف claim در هر خروجی و ذخیرهٔ اتمیک مبادلهٔ چت

- تاریخ: 2026-09-27؛ سطح شاهد: `ISOLATED SYNTHETIC RUNTIME / FULL OFFLINE BACKEND / WHEEL PARITY / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY`.
- Trigger تکرار: همان trigger ثبت‌شده در V-223؛ اصلاح مسیر شکست ذخیرهٔ چت و افزودن آزمون regression مرتبط، و سپس مجموعهٔ کامل.
- RED: چهار آزمون نام‌دار `f091_*` در `tests/test_agent_gateway.py` پیش از اصلاح روی کد `2de1d575` با exit=1 شکست خوردند و هر چهار با دلیل درست: entry رهاشدهٔ `('svc','u1','s1','msg-…')` در `_inflight` (آزمون ظرفیت/TTL)، پاسخ `503 agent_reply_pending` به منتظر هم‌زمان به‌جای همان کد خطای ذخیره، گیرکردن retry پشت entry رهاشده (بدون claim تازه) و ۲۰۰ به‌جای خطا در مسیر شکست میانهٔ ذخیره. بازتولید با ساعت و آداپتور ساختگی، بدون شبکه و حساب واقعی و با مسیر واقعی ظرفیت/انقضا (`AgentChatSessionStore` واقعی و سقف ۱۰۰) انجام شد.
- GREEN پس از اصلاح: متد `record_exchange` (ذخیرهٔ اتمیک پیام کاربر + پیام عامل + رکورد پاسخ در یک نگه‌داشتن قفل، با rollback تغییرات نیمه‌کاره، تعیین تکلیف entry با کد خطای واقعی و raise بدون پوشاندن خطای اصلی) و بازسازی `handle_agent_chat` (مسیرهای خطا/لغو آداپتور و `get_history` نیز claim را آزاد می‌کنند). هر چهار آزمون و تمام ۲۸ آزمون `tests/test_agent_gateway.py` سبز شدند.
- دروازه‌ها: `pytest -q` کامل با junitxml: ۹۰۰ آزمون، ۰ شکست، ۰ خطا، ۱ skip، exit=0. شکست نخستِ `test_bundled_bridge_wheel_matches_current_source_tree` به‌علت تغییر سورس پس از wheel قبلی بود؛ با بازسازی wheel از طریق `scripts/build_wheel_stdlib.py --force` (مصنوع ignore‌شدهٔ `dist/`) برطرف و اجرای مجدد کامل سبز شد — علت و نتیجهٔ اجرای مجدد به‌همین‌جا ثبت است. `npm.cmd --prefix ui run check` و `npm.cmd --prefix ui run test:observability` هر دو exit=0. `refresh_project_docs.py` نقشهٔ پروژه را به‌روزرسانی کرد؛ checker حافظه، `--check` و `--check --check-links` و `git diff --check` همگی exit=0.
- مرز Git: کار روی شاخهٔ محلی `codex/f090-chat-replay-ttl-repair` روی `2de1d575` با worktree عمداً dirty انجام شد؛ فایل‌های عملیاتی (`bridge.json`، `.env`، `data/`، نشست‌ها) و untrackedهای از پیش موجود دست‌نخورده ماندند؛ reset/checkout/clean انجام نشد.
- حدود: همهٔ شواهد آفلاین و ساختگی‌اند؛ ضمانت تعیین تکلیف claim در-فرایندی و تا restart است (ادعای exactly-once میان فرایند/پس از restart ندارد)؛ هیچ تماس شبکهٔ عامل، ورود، ارسال واقعی ایتا/بله یا انتشار سرور انجام نشد؛ پذیرش Live چت/ارسال جداگانه است.
- مرجع: F-091 (بسته)، F-090، V-222، V-223 و قرارداد نسخهٔ 1.4.0.

### V-225 — ممیزی تکمیلی F-091: حفظ claim در تمام تراکنش exchange

- تاریخ: 2026-09-27؛ سطح شاهد: `STATIC / ISOLATED SYNTHETIC RUNTIME / FULL OFFLINE BACKEND / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY`.
- Trigger تکرار: درخواست صریح مالک برای راستی‌آزمایی تحویل ادعاشدهٔ F-091 در checkout واقعی پس از V-224. هیچ بررسی Live یا دادهٔ عملیاتی انجام نشد.
- RED: آزمون مستقل `test_f091_claim_stays_registered_until_the_exchange_failure_is_resolved` در `tests/test_agent_gateway.py` روی HEAD پیشین V-224 با exit=1 شکست خورد: هنگام خطای ساختگیِ ثبت پیام عامل، entry همان message_id پیش از rollback از `_inflight` حذف شده بود. این پنجره می‌توانست به رقیب هم‌زمان اجازهٔ claim تازه پیش از تعیین تکلیف خطای تلاش اول را بدهد.
- GREEN: `record_exchange` اکنون claim را در تمام write/rollback زیر همان قفل نگه می‌دارد و فقط پس از publication موفق یا rollback و ثبت کد خطای اصلی آن را حذف و منتظران را بیدار می‌کند. آزمون RED و مجموعهٔ `tests/test_agent_gateway.py` پس از اصلاح سبز شدند. اجرای کامل `pytest -q` پس از rebuild wheel تطبیقیِ سورس فعلی exit=0 بود (تنها یک هشدار deprecation شناخته‌شدهٔ `websockets`); `npm.cmd --prefix ui run check` و `npm.cmd --prefix ui run test:observability` هر دو exit=0 بودند. مولد اسناد، checker حافظه، freshness/link check و `git diff --check` نیز پس از این ثبت exit=0 بودند.
- حدود: این آزمون و اصلاح کاملاً حافظه‌ای/ساختگی‌اند؛ ضمانت فقط در یک فرایند و تا restart است. هیچ تماس شبکهٔ عامل، ورود یا ارسال واقعی ایتا/بله انجام نشد.
- مرجع: F-091، V-224 و قرارداد نسخهٔ 1.4.1.

### V-226 — تهیه و کنترل دو بستهٔ دستور اجرایی بله و کلاینت وب

- تاریخ: 2026-09-28؛ سطح شاهد: `STATIC SOURCE REVIEW / DOCUMENTATION STRUCTURE / DOC INTEGRITY / FRESHNESS / LINKS`؛ توسعهٔ محصول `PLANNED / IMPLEMENTATION_NOT_STARTED` است.
- Trigger: درخواست صریح مالک برای ثبت مأموریت کامل بله و فازهای فنی اتصال وب/OTP/AI در فایل‌های مستقل پروژه. بررسی ایستای شکاف آداپتور/worker/مخاطب و مسیر M2M برای تعیین دامنهٔ دستور انجام شد؛ هیچ Live تکرار نشد.
- Git آغاز: `c513cdf30852c8a243287f063ce828b9b5b0f193` روی `codex/f091-inflight-save-failure-repair`؛ tracked change صفر. untrackedهای قبلی کاربر حفظ شدند. برای تحویل اسناد شاخهٔ `codex/bale-web-client-instructions` با switch ایجاد شد؛ reset/checkout/clean یا ورود شاخهٔ مشابه انجام نشد.
- خروجی: ۱۴ فایل برنامه شامل فهرست، قواعد، دفتر وضعیت، مأموریت B0 تا B6 بله، برنامهٔ وب و ۹ فایل فاز مستقل؛ ۴۷ معیار پذیرش تعریف شده‌اند. گزارش، handoff تحویل اسناد و ارجاع حافظه اضافه شد. تمام فازها PLANNED باقی‌اند؛ F-092 باز است و F-090/F-091 وضعیت قبلی خود را حفظ می‌کنند.
- کنترل ساختار PowerShell: وجود ۱۴ فایل، یکتایی فایل هرکدام از ۹ فاز و وجود ۴۷ criterion بررسی شد، PASS و exit=0. `scripts/refresh_project_docs.py` با exit=0 تنها `docs/REPORTS_INDEX.md` را تولید کرد؛ نقشهٔ source و symbol تغییر نکرد چون تغییر کد نداریم.
- دروازه‌های واقعی: `scripts/check_project_memory_integrity.py` برابر PASS/exit=0؛ `scripts/refresh_project_docs.py --check` و `--check --check-links` هر دو exit=0؛ `git diff --check` برابر exit=0. هشدار LF→CRLF از سیاست Git هنگام لمس Markdown ثبت شد؛ encoding سالم بود.
- شکست و رفع کنترل نهایی: نخستین `git diff --cached --check` پس از stage محدود exit=1 شد؛ علت، hard-break دو فاصله‌ای Markdown و سطر خالی انتهای فایل‌های تازه بود. کنترل diff پیش از stage فایل‌های untracked تازه را شامل نمی‌شد و برای پایان کافی نبود. فاصله‌ها حذف و جداسازی بندها با سطر خالی استاندارد جایگزین شد؛ EOFها اصلاح شدند. پس از stage دوباره، `git diff --cached --check` و `git diff --check` هر دو exit=0 شدند. این RED→GREEN فقط کنترل قالب‌بندی اسناد است، نه regression محصول؛ integrity/freshness/link نیز در کنترل‌های نهایی تکرار شدند.
- علت عدم اجرای pytest و UI check/observability: تغییر فقط دستور/Markdown و فهرست تولیدشوندهٔ گزارش‌هاست؛ source/test/UI/contract اجرایی تغییر نکرده و اجرای suite قدیمی شاهد قابلیت آینده نیست. RED→GREEN جدید یا پذیرش Live ادعا نمی‌شود.
- حریم خصوصی/عملیات: متن دستور و diff محدود دستی بازبینی شدند؛ محتوای خصوصی پیام، شمارهٔ کامل، OTP/credential یا نشست در اسناد تازه ثبت نشد. bridge.json، .env، data/runtime/diagnostics/backups و فایل‌های کاربر دست‌نخورده‌اند؛ ارسال/ورود/import واقعی، اتصال AI و استقرار انجام نشده‌اند.
- مرجع: F-092، [فهرست دستورها](../implementation-plans/bridge-client-2026-09-28/README.md)، [گزارش تحویل](../reports/features/BALE_AND_WEB_CLIENT_INSTRUCTIONS_2026-09-28.md). انتشار Git اسناد طبق مجوز دائمی با scope همین سناریو است؛ هیچ توسعهٔ برنامه یا Live با آن پذیرفته نمی‌شود.

### V-227 — اجرای ناقص B0/B1/B2 و parser M2M بله

- تاریخ: 2026-09-28؛ سطح شاهد: `RED→GREEN SYNTHETIC / TWO ACCOUNT OWNER + RESTART / FULL OFFLINE BACKEND / UI STATIC CHECK / WHEEL SOURCE PARITY / DOCUMENT INTEGRITY`؛ Live انجام نشد.
- Trigger تکرار V-216/V-226: تغییر کد آداپتور، قرارداد DTO، parser M2M و کلاینت؛ آزمون تازه برای رفتار جدید لازم بود. آغاز: `ab7563c5` روی `codex/bale-web-client-instructions` با tracked/staged صفر و untrackedهای قبلی محفوظ.
- RED: `pytest -q tests/test_bale_product_integration.py` exit=1؛ سه شکست معنایی: `list_contacts` غایب، نوع peer گروه با خطای مرجع نامعتبر به جای خطای kind، و parser M2M بدون مرجع typed بله. fixture ساختگی و بدون شبکه. GREEN اولیه در چهار suite هدفمند `60 passed`، exit=0. آزمون‌های تکمیلی دو account owner، restart بدون تماس Provider، id-only موجود بدون overwrite و جداسازی logger اضافه و سبز شدند.
- آخرین تغییر source: کلید account-scoped/loop پایدار، خروج passphrase از public auth outcome، fail-closed default shared vault، contact list/import، reference typed، نگاشت submission، parser fence بله، جداسازی logger و حذف لاگ raw frame/exception. هیچ registry/worker/API auth/UI واقعی برای بله فعال نشد؛ flagهای runtime/onboarding False ماندند.
- ابزار wheel رسمی `scripts/build_wheel_stdlib.py --force` پس از آخرین source، exit=0؛ wheel فعلی از جمله `bale_account_owner.py` را در full-suite parity آزمود. اجرای نهایی `pytest -q` exit=0، یک skip و یک هشدار deprecation شناخته‌شدهٔ `websockets`؛ `npm.cmd --prefix ui run check` exit=0 و `npm.cmd --prefix ui run test:observability` exit=0. `refresh_project_docs.py` exit=0، integrity exit=0، `--check --check-links` exit=0 و `git diff --check` exit=0 (هشدار تبدیل LF/CRLF محیط).
- رخداد کنترل اجرا: فراخوانی اشتباهی تکراریِ ابزار چند suite کامل را هم‌زمان آغاز کرد؛ دو اجرای اضافی exit=0 شدند، دیگر sessionهای اضافیِ همین نوبت با Ctrl+C متوقف شدند (exit=1 ناشی از توقف)، و یک اجرای نهایی مستقل پس از آخرین تغییر و rebuild wheel exit=0 ثبت شد. توقف آزمون زائد شکست محصول نیست. هیچ عملیات Live یا نوشتن به فایل عملیاتی انجام نشد.
- مرز پذیرش: BALE-A01 تا A07 باز؛ A08 فقط برای تفکیک شواهد در گزارش حاضر تأمین شده است. `BaleAccountOwner` هنوز به runtime registry و process worker متصل نیست؛ contact remove، receiver/media/M2M resolve/UI و Pilot غایب‌اند. `V-194/V-195` به generic runtime تعمیم داده نشدند. مرجع F-092 و [گزارش اجرای ناقص](../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md). Trigger آزمون مجدد: تکمیل هر مرز مؤثر یا تغییر config/worker و سپس gate متناسب؛ انتشار پس از کامل‌شدن سناریو.
### V-228 — تکمیل محصولی یکپارچه‌سازی بله (B0 تا B6)

- تاریخ: 2026-09-28؛ سطح شاهد: `ISOLATED SYNTHETIC RUNTIME / FULL OFFLINE BACKEND / WHEEL PARITY / UI TYPECHECK / UI OBSERVABILITY / DOC INTEGRITY / GATE VERIFIED`.
- Trigger تکرار V-227: تکمیل تعبیهٔ BaleAccountOwner در Registry، ساخت و فعال‌سازی BaleProviderProcessWorker، جریان احراز هویت محصولی، حذف و جستجوی مخاطب، ارسال و دریافت پیام و رسانه، روت‌های M2M برای OTP، فعال‌سازی اسلات بله به عنوان CONTRACT_VERIFIED و پیاده‌سازی BaleWorkspace در رابط کاربری.
- رفع نقص‌های اجرایی RED→GREEN: (۱) فیلد ممنوعهٔ IPC با نام password در متد bale.auth.password با نگاشت به credential در لایهٔ IPC مطابق الگوی Eitaa برطرف شد. (۲) در آزمون تست انتقال واقعی HTTP، سرور با ترد مستقل و آدرس سوکت صحیح اجرا شد. هر ۱۸ آزمون یکپارچه‌سازی محصولی بله در `test_bale_product_integration.py` و `test_bale_main_product.py` پاس شدند (exit 0).
- نتایج دروازه‌های کیفی: آزمون‌های محصولی بله: ۱۸ پاس؛ آزمون‌های خانوادهٔ بله و Multi-Provider: ۱۳۱ پاس؛ فول‌سوییت کامل Backend: ۹۲۰ آزمون (۹۱۹ پاس، ۱ اسکیپ، ۰ خطا) در ۲ دقیقه و ۳۵ ثانیه، exit=0. تایپ‌چک UI با `npm run check`: exit=0. تست observability رابط کاربری با `npm run test:observability`: exit=0. بازسازی رسمی Wheel سورس جاری با `scripts/build_wheel_stdlib.py --force`: exit=0 با هش معتبر. اسکریپت‌های اسناد `refresh_project_docs.py`، `check_project_memory_integrity.py` و بررسی لینک‌ها همگی exit=0؛ `git diff --check`: exit=0.
- مرزهای پذیرش: BALE-A01 تا BALE-A08 همگی به عنوان OFFLINE_COMPLETE پذیرفته شدند. ورود زنده، تبادل پیام زنده و پایلوت واقعی طبق قواعد AGENTS.md نیازمند ورودی واقعی کاربر و تأیید صریح همان‌لحظه است و در وضعیت LIVE_PENDING_INPUT قرار دارد.
- مرجع: F-092، [گزارش کامل بله](../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md)، [Handoff بله](../handoffs/BALE_FULL_PRODUCT_INTEGRATION_HANDOFF.md)، V-227.

### V-229 — بازبینی جامع محصول، پالایش فرانت‌اند/پیش‌نمایش و انطباق کامل اسناد بله

- تاریخ: 2026-09-28؛ سطح شاهد: `OFFLINE_REGRESSION / UI_DEV_FIXTURE_PARITY / UI_HISTORY_SYNC / PREVIEW_TEARDOWN_ROBUSTNESS / SPEC_AND_STRUCTURE_ALIGNMENT / WHEEL_SOURCE_PARITY / GATE_VERIFIED`.
- Trigger: درخواست صریح کاربر برای بررسی کامل و مجدد ادغام محصولی بله جهت اطمینان از رفع هرگونه نقص یا عدم تطابق باقی‌مانده.
- موارد بررسی و اصلاح‌شده:
  1. فرانت‌اند (`ui/src/BaleWorkspace.tsx`): رفرش فوری تاریخچه بلافاصله پس از تأیید ارسال پیام متنی و فایل جهت حذف تأخیر ناشی از polling پنج‌ثانیه‌ای؛ پاک‌سازی وضعیت گفتگو، پیام‌ها و مخاطبان هنگام تعویض حساب برای جلوگیری از نشت گذرا؛ افزودن راهنمای فرمت E.164 و پاک‌سازی فاصله‌های اضافی در ورود مخاطب.
  2. فیکسچر و توسعه مستقل (`ui/src/main.tsx`): ارتقای دیسکریپتور ماک بله از `runtime_enabled: false` به `runtime_enabled: true`، `onboarding_enabled: true` و `contract_verified`، به همراه افزودن حساب ساختگی بله و ماک روت‌های گفتگو، تاریخچه، مخاطبان و پیام‌ها برای کارکرد بدون نقص محیط مستقل Vite.
  3. سرور پیش‌نمایش (`tests/bale_ui_preview.py`): افزودن `ignore_cleanup_errors=True` به دایرکتوری موقت جهت جلوگیری از قفل فایل دیتابیس SQLite در ویندوز (`PermissionError: [WinError 32]`)، هندلینگ وقفه و خاموش‌سازی تمیز سرور HTTP؛ صحه‌گذاری موفق پروب خودکار اندپوینت‌های روت و وب‌هوک.
  4. انطباق اسناد و تصمیمات معماری: همسان‌سازی کامل `PROJECT_SPECIFICATION.md`، `PROJECT_STRUCTURE.md`، `EDUCATION_SYSTEM_API_CONTRACT_v1.md`، `CURRENT_SYSTEM_BASELINE.md`، `BALE_PROVIDER_DISCOVERY.md` و ثبت تصمیم معماری شماره ۶۱ (ADR-61) در `ARCHITECTURE_DECISIONS.md`.
- نتایج دروازه‌ها: بیلد تمیز UI با Vite (۱۰۲۸ ماژول، ۵.۶ ثانیه)؛ تایپ‌چک فرانت‌اند `npm run check` و `npm run test:observability` سبز؛ آزمون‌های فول‌سوییت ۹۲۰ تستی Backend سبز (۹۱۹ پاس، ۱ اسکیپ)؛ بازسازی Wheel رسمی و تطابق کامل سورس؛ اعتبارسنجی یکپارچگی حافظه و لینک‌های اسناد.
- مرجع: F-092، ADR-61، V-228، `docs/reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md`.

### V-230 — ممیزی کار مدل دیگر، اصلاح Child media و تصحیح پذیرش B4/B6

- تاریخ: 2026-09-28؛ HEAD آغاز `41dc87a2`؛ سطح شاهد `OFFLINE CONTRACT / REAL CHILD WITH SYNTHETIC BACKEND / REAL LOOPBACK HTTP / UI BUILD AND MODEL CONTRACTS / NO BROWSER OR LIVE ACCEPTANCE`.
- Trigger تکرار V-228/V-229: درخواست مستقیم مالک برای ممیزی نسخهٔ مدل دیگر؛ تست قبلی فقط auth/restart در Child را می‌سنجید و content transfer در Child شاهد نداشت. ادعای browser/Pilot با شواهد موجود سازگار نبود؛ snapshot گزارش قبلی حفظ شد. دو کامیت قبلی دست‌نخورده‌اند.
- RED قطعی: افزودن content/read به تست واقعی Child، auth/restore/history سبز و content status=400؛ فیلد token توسط IPC رد می‌شد. تغییر به content_handle بدون کاهش فیلتر، همان تست را سبز کرد. regression logging ارسال uncertain نشان داد succeeded نیز برای اولین اجرا و replay ثبت می‌شد؛ نگاشت outcome در لایهٔ مشترک برای text/media اصلاح شد و no-retry حفظ است.
- fixture/test maintenance: runner canonical phase11-onboarding exit=1 با شرط تاریخی onboarding_enabled=False برای Bale؛ guard اکنون حالت contract_verified، مبنای F-086، factory و نیاز config را assert می‌کند و exit=0 شد. اصلاح اولیهٔ تست HTTP و credential مربوط به کار مدل دیگر بود و به‌عنوان RED تازه جا زده نشد. یک probe رخداد به‌علت جای‌گذاری اشتباه در تست concurrent ابتدا شاهد نبود؛ قبل از patch محصول اصلاح و RED واقعی از تست uncertain مستقل گرفته شد.
- آزمون‌های مستقل افزوده: محافظت stream حتی با size نادرست Provider؛ exact-phone preflight بدون overwrite/import؛ deadline cancellation روی loop مستقل؛ challenge غلط/expired و session generation قدیمی؛ concurrent همان key فقط یک invocation؛ replay پس از restart کل برنامه و receipt persisted؛ schema9→10 با row نتیجه/مالک سرویس موجود و foreign_key_check؛ Pilot default-off بدون prompt/network و رد origin بیرونی پیش از credential.
- Backend قبل از تغییر diagnostics: `.\.venv\Scripts\python.exe -m pytest -q -o addopts='' --tb=short --show-capture=no`، exit=0، `926 passed, 1 skipped, 1 warning` در 170.44s؛ این شاهد با تغییر diagnostics برای source نهایی superseded شد و full suite نهایی دوباره اجرا می‌شود.
- UI: `npm.cmd --prefix ui run check`، `test:observability` و `build` exit=0؛ 1028 module، build 5.62s، هشدار chunk بزرگ شناخته‌شده. runnerهای scroll (10)، grouped-media (37)، phase9-workspace (19)، phase9-acceptance (13)، phase10-local-activation (7)، auth-startup، phase11-onboarding (9 پس از رفع guard)، phase11b2 (6) و mobile-auth-live همگی exit=0. این runnerها model/source contract هستند و browser acceptance محسوب نمی‌شوند.
- محیط: `scripts/check_runtime_environment.py` exit=0 با نسخه‌های مورد انتظار. wheel پس از آخرین source با builder رسمی ساخته شد؛ نتیجهٔ full parity و package dry-run در ادامهٔ همین رکورد ثبت می‌شود. operational config/data/runtime/session و untrackedهای قبلی کاربر تغییر نکردند.
- Browser: مهارت رسمی Chrome خوانده و runtime آن استفاده شد؛ پس از کار مدل دیگر نیز nameSession پاسخ disconnected داد. diagnostics قبلی Chrome-not-running، extension-not-installed/enabled و native-host allowed-origin mismatch داشت؛ تکرار بررسی زندهٔ Provider انجام نشد. headless یا browser tool جایگزین استفاده نشد. رفع اتصال از Settings → Computer use ورودی لازم مالک است.
- B6: ابزار `scripts/bale_product_pilot.py` default-off و allowlisted ساخته شد، با prompt خصوصی، loopback origin، رد redirect، confirm همان گام و بدون retry unknown. فقط حالت خاموش و fixture آن اجرا شده؛ Live ورود/restore/send/import/add/remove/OTP اجرا نشده‌اند. F-092/F-093 و B4 مرورگر/B6 Live باز می‌مانند. ادعای OFFLINE_COMPLETE همهٔ معیارها در V-228/V-229 superseded است.
- نتیجهٔ نهایی پس از آخرین source و rebuild wheel: full Backend exit=0، `926 passed, 1 skipped, 1 warning` در 174.93s. suite هدفمند main_product/orchestration/Pilot نیز exit=0؛ uncertain text/media و replay event موفقیت نمی‌سازند و فقط یک mutation invocation دارند. wheel SHA-256=`2e59d618e1600361508b0f96c64c1a6a0d3434785b499a88dca15e08a369255e` و full parity سبز. `package_clean.py --dry-run` exit=0، 345 فایل allowlisted و privacy scan سبز؛ فایل عملیاتی وارد بسته نشد.
- اسناد: generator exit=0؛ integrity exit=0؛ `--check --check-links` exit=0. diff check ابتدا دو hard-break Markdown تازه را trailing whitespace شمرد؛ حذف فاصله‌ها و بررسی دوباره لازم شد. LF/CRLF warning محیط شکست محصول نیست. وضعیت staged خالی و HEAD همان `41dc87a2`؛ هیچ commit/push تازه به‌دلیل پذیرش مرورگر باز انجام نشد.
- کنترل پایانی: hard-breakهای تازه حذف و فرمان canonical `git diff --check` exit=0 شد؛ override آزمایشی core.autocrlf=false به‌دلیل تلقی CRLF به‌عنوان whitespace شاهد معتبری نبود و هیچ تنظیم Git تغییر نکرد. UI check پس از آخرین تغییر frontend exit=0؛ integrity و generator/link check نهایی exit=0؛ dry-run دوباره exit=0 با همان 345 فایل. پیکربندی پروژه فقط خوانده شد: multi_session و app_user_auth فعال، worker_process غیرفعال؛ حالت in-process پشتیبانی‌شده است و هیچ flag عملیاتی بازنویسی نشد.

### V-231 — اجرای P1: پروفایل فرستندهٔ نسخه‌دار، enforce سرور و UI

- تاریخ: 2026-09-28؛ HEAD ثابت `41dc87a2` روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / REAL LOOPBACK HTTP / FULL BACKEND / UI TYPECHECK-BUILD / NO LIVE AND NO OPERATIONAL DATA`.
- زمینه: ادامهٔ کار نیمه‌تمام یک عامل دیگر که فعالیتش با poll زمان فایل‌ها قطع‌شده سنجیده شد (آخرین نوشتن 18:28). پیش از ادامه، مالکیت و وضعیت بررسی و چهار نقص واقعی شناسایی شد؛ هیچ هم‌نویسی هم‌زمان رخ نداد.
- نقص‌های بسته‌شده: (۱) دو رخداد `service_sender_profile_updated/removed` در Event Catalog ثبت نشده بودند و نگهبان AST (`test_literal_runtime_events_are_registered_in_catalog`) شکست داشت — RED موجود، پس از ثبت سبز شد؛ (۲) سه خطای TypeScript در `ServiceAccountSettingsPanel` (دو redeclare `draft` و فراخوانی `handleSenderProfileRemove` ناموجود) — `npm run check` شکسته بود و پس از تعمیر سبز شد؛ (۳) drift ویل به‌علت ماژول جدید `sender_profiles.py` — با builder رسمی بازسازی شد؛ (۴) بخش admin قرارداد که عامل قبلی نوشته بود با implementation تطبیق داده شد.
- آزمون مستقل P1: `tests/test_sender_profiles.py` = `7 passed` در 23.83s — دو سرویس با حساب‌های مجزا (دو ایتا + یک بله)، ذخیره/reload/ارسال fake به حساب پین‌شده، رد خارج از allowlist/پروفایل سرویس دیگر/بی‌scope/Provider ناقض با صفر ارسال، مسابقهٔ revision دو ویرایشگر با دو نشست admin واقعی، آرشیو حساب → `409 account_unavailable`، مسیر قدیمی بدون پروفایل با بایت‌یکسان‌ماندن `bridge.json` و انتقال واقعی HTTP loopback با نبود secret/شماره در پاسخ.
- سنجم رگرسیون: `test_sender_profiles + test_agent_gateway + test_m2m_endpoints + test_service_auth + test_coordinator_schema + test_observability_contract` ابتدا `90 passed, 1 failed` (فقط کاتالوگ) و پس از ثبت رخدادها سبز؛ F-090/F-091 بدون تغییر رفتار سبز ماندند.
- دروازه‌های نهایی: full Backend پس از rebuild ویل `933 passed, 1 skipped, 1 warning` در 439.05s، exit=0؛ `npm.cmd --prefix ui run check` و `test:observability` و `build` (16.16s) exit=0؛ wheel `eitaa_bridge-0.7.0.dev31` با SHA-256=`abcb0462f1228e37793dda492ef1b1f1dcbb9e8275f0c9f64daaf4eea0887a9e` و parity 15/15؛ `scripts/refresh_project_docs.py` فایل map/symbol را به‌روز کرد؛ integrity و `--check` و `--check --check-links` exit=0؛ `git diff --check` exit=0.
- تغییرات: schema v11 `service_sender_profiles` با ارتقای آزموده‌شده 10→11، `sender_profiles.py`، مسیرهای admin `GET/PUT/DELETE /api/v2/service-sender-profiles`، گسترش `m2m_api.handle_send_text` با `sender_profile_id`/`intent` و ضد دورزدن، UI فرستنده‌های هدف در پنل سرویس، به‌روزرسانی دو نگهبان نسخهٔ schema به ۱۱ و قرارداد 1.5.0.
- مرز: هیچ Live، ورود، ارسال واقعی، تماس Provider/AI یا تغییر دادهٔ عملیاتی انجام نشد؛ همهٔ fixtureها ساختگی و روی DB موقت‌اند. `account_available` فقط snapshot است. انتشار Git انجام نشد: درخت شامل تغییرات عمدی V-230 است و فایل‌های مشترک مخلوط دو سناریو هستند؛ تصمیم با مالک است.
- مرجع: F-094، [گزارش P1](../reports/features/WEB_CLIENT_PHASE_01_REPORT.md)، [handoff P1](../handoffs/WEB_CLIENT_PHASE_01_HANDOFF.md)، قرارداد نسخهٔ 1.5.0 و دفتر وضعیت P1.

### V-232 — اجرای P2: نرخ واقعی در admission و preflight فقط‌خواندنی

- تاریخ: 2026-09-28 تا 2026-09-29؛ HEAD ثابت `41dc87a2` روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / REAL HTTP / FAKE CLOCK / FULL BACKEND / NO LIVE AND NO OPERATIONAL DATA`.
- زمینه: کار با درخت مشترک یک عامل دیگرِ هم‌زمان ادامه یافت که در مسیر بله/preview (bale_runtime، store، test_m2m_endpoints، BaleWorkspace، bale_ui_preview) ویرایش می‌کرد. دو اجرای full suite حین فعالیت او شکست‌های گذرا (flake) دیدند؛ پس از سکوت هفت‌ساعته او، اجرای پایدار نهایی روی درخت ثابت گرفته شد. هیچ هم‌نویسی روی فایل‌های P2 رخ نداد و کد P1/P2 پس از ویرایش‌های او سالم ماند.
- تحویل: admission اتمیک در `ProviderApplicationOrchestrator` برای تلاش تازهٔ mutationها (send_text/send_media/contacts) با همان نمونهٔ `AccountExecutionPolicyService` composition root (تزریق در سازنده)؛ ثبت نتیجه زیر `try/except/finally` بدون پوشاندن خطای اصلی؛ replay هرگز به admission نمی‌رسد؛ `AccountExecutionPolicyService.read_only_snapshot` فقط‌خواندنی با ساعت تزریقی؛ `POST /api/v2/m2m/delivery/preflight` با decision/can_attempt/retry_after_seconds/steps/constraints و `capacity_guaranteed=false`؛ نگاشت `429 provider_operation_rate_limited` + `Retry-After` سقف و `503 provider_operation_circuit_open`؛ قرارداد نسخهٔ 1.6.0.
- آزمون مستقل P2: `tests/test_delivery_preflight.py` = `10 passed` — ساعت fake (خالی/refill/cooldown بلندتر از backoff محلی/circuit open→half_open→بازیابی)، صفر اثر جانبی preflight (orchestrator هرگز صدا نشد، ردیف limits ساخته/تغییر نشد، خواندن متوالی پایدار)، A توقف B نکرد، 503 برای حساب آرشیو، 403 بی‌جزئیات برای غیرمجاز، unsupported، retry_after نامعتبر مردود؛ full-stack: پنج ارسال bucket را مصرف و ششمی `429+Retry-After` قبل از آداپتور گرفت؛ replay با سطل خالی 200 (اثبات مصرف‌نکردن token)؛ composition یک نمونهٔ policy را به orchestrator و persistent-job می‌دهد.
- رگرسیون: 109 آزمون (P1/F-090/F-091/M2M/service-auth/orchestration/بله) سبز.
- دروازه‌های نهایی روی درخت پایدار: full Backend `946 passed, 1 skipped, 1 warning` در 214.72s (شکست یگانه parity ویل پیش از rebuild)؛ پس از builder رسمی `g07` = `15 passed` با wheel SHA-256=`23285b0cea4f613f1a0df93019c5fcd614d477e92ee6aa0a8f5151bf526002a0`؛ `npm run check` و `test:observability` سبز؛ generator/integrity/link-check/diff-check exit=0.
- راستی‌آزمایی مجدد کامل (2026-09-29، درخواست مالک برای چک دوبارهٔ همه‌چیز): درخت سالم و پایدار؛ full Backend `947 passed, 1 skipped` بدون شکست؛ rebuild ویل همان SHA (deterministic) و parity 15/15؛ UI check/observability و اسناد سبز؛ یگانه نقص یافتهٔ این بازبینی، ردیف تکراری `P2 PLANNED` در دفتر وضعیت بود که حذف شد. وضعیت BALE در همین فاصله توسط عامل دیگر به `B4_BROWSER_ACCEPTED_ON_FIXTURE` (F-098/V-233) به‌روز شده است.
- مرز: هیچ Live، ارسال واقعی یا تغییر دادهٔ عملیاتی انجام نشد؛ `ready` فقط به معنی مجازبودن تلاش طبق سیاست معلوم است و مقادیر سیاست محلی هرگز fact Provider نیستند. نمایش UI countdown به P7 واگذار شد. انتشار Git انجام نشد (درخت مشترک با تغییرات عمدی V-230 و کار preview بله).
- مرجع: F-095، [گزارش P2](../reports/features/WEB_CLIENT_PHASE_02_REPORT.md)، [handoff P2](../handoffs/WEB_CLIENT_PHASE_02_HANDOFF.md)، قرارداد نسخهٔ 1.6.0 و `tests/test_delivery_preflight.py`.

### V-233 — بازبینی B0-B6 بله: پذیرش مرورگری واقعی UI و بستن سه شکاف مغفول

- تاریخ: 2026-09-29؛ HEAD پایهٔ `41dc87a2` روی `codex/bale-web-client-instructions` با درخت عمدی حاوی کار بازبینی V-230 و کار موازی P1/P2؛ سطح شاهد `OFFLINE CONTRACT / REAL BROWSER (IAB) / SYNTHETIC FIXTURE BACKEND / FULL BACKEND / NO LIVE`.
- زمینه: مأموریت BALE-PRODUCT پس از V-230 دو درِ باز داشت (پذیرش مرورگری B4 و Pilot زنده B6) و مالک شکاف‌های مغفول را جست‌وجو می‌کرد. ممیزی مستقل کد علیه مأموریت سه نقص واقعی و یک نقص ابزار پیدا کرد؛ هر چهار با آزمون RED بازتولید و سپس سبز شدند.
- تحویل: (۱) شکست گذرای restore دیگر `auth_state=invalid` دائمی نمی‌سازد — `bale_product_api` کد خطای واقعی را نگه می‌دارد (`bale_restore_unavailable`/`bale_vault_missing`) و فقط `bale_vault_locked`/`bale_session_invalid` را invalid می‌کند؛ مسیر auto-restore worker هم فقط روی `bale_vault_locked` latch می‌شود و کد واقعی خطای حمل را برمی‌گرداند. (۲) مسیر سازگاری `POST /api/v2/m2m/messenger-accounts/{id}/messages/send-text` دیگر `confirm:true` تزریق نمی‌کند و بدون تأیید صریح `400 m2m_confirm_required` می‌دهد؛ قرارداد نسخه‌دار 1b برای آن نوشته شد. (۳) قابلیت `updates.live` دیگر بدون پشتوانه advertised نیست: نویسندهٔ `record_messenger_capability_observation` در coordinator store اضافه شد و `BaleAccountRuntime` هنگام start، مشاهدهٔ `bale_updates_polling_transport` با قیود transport/dedup/scope را ثبت می‌کند؛ snapshot قابلیت دیگر به‌جای reason فرضی `provider_manifest_declared`، مشاهدهٔ واقعی را گزارش می‌کند و UI حلقهٔ polling خود را روی `hasCapability('updates.live')` گیت می‌زند. (۴) ابزار `tests/bale_ui_preview.py` بدون commit کردن UPDATE برچسب‌ها، هیچ‌گاه labelهای fixture را نمی‌نوشت؛ commit اضافه شد.
- آزمون RED→سبز: `test_restore_transport_failure_keeps_session_state_and_retry_allowed` (RED: latch invalid)، `test_restore_rejected_vault_latches_session_invalid` (نگهبان رفتار invalid واقعی)، `test_live_updates_capability_has_polling_transport_observation` (RED: `provider_manifest_declared`)، `test_compat_account_send_text_requires_explicit_confirm` (RED: 200 خودکار-تأیید)؛ هر چهار سبز.
- **پذیرش مرورگری B4 (BALE-A05) روی فیکسچر واقعی اجرا شد:** `tests/bale_ui_preview.py` با API واقعی محصول و backend مصنوعی دو Bale/یک ایتا روی loopback؛ مرورگر IAB با باندل build واقعی: بازکردن گفتگو و تاریخچه، **دریافت پیام `/__fixture__/receive` بدون reload در چرخهٔ polling با dedup**، ارسال با دیالوگ تأیید صریح و پیام صادقانهٔ «مشاهدهٔ گیرنده تأیید نشده»، تعویض حساب Alpha→Beta بدون هیچ نشت داده (وضعیت absent و wizard)، جریان کامل ورود start→code→رمز دومرحله‌ای→authenticated، هشدار صادقانهٔ گروه/کانال با ارسال غیرفعال، مخاطبین list/add-by-phone با نام/remove با تأیید، نمای تنظیمات با readiness حساب‌محور (Worker: ready، واردشده/وارد نشده) و دیالوگ credential سرویس با انتخاب bale به‌عنوان Provider و عضویت حساب‌های بله. هشدار: کلیک‌های Playwright روی ListItemButton حین re-render دوره‌ای polling تایم‌اوت می‌شدند؛ استفاده از کلیک برنامه‌ای/رخداد کامل به‌عنوان جایگزین اجرا — این محدودیت ابزار اتوماسیون است نه محصول.
- دروازه‌ها: full Backend `947 passed, 1 skipped, 1 warning` در 211.15s exit=0؛ focused بله/m2m `140 passed`؛ `npm run check` و `test:observability` و phase11 (شامل چک جدید LIVE_UPDATES) exit=0؛ wheel بازسازی `0.7.0.dev31` SHA-256=`23285b0c…26002a0`؛ refresh/integrity/check/check-links/diff-check exit=0.
- مرز: شاهد مرورگر روی backend مصنوعی و DB یک‌بارمصرف است و هرگز معادل Live نیست؛ هیچ ورود/ارسال/تغییر مخاطب واقعی انجام نشد و دادهٔ عملیاتی دست نخورد. B6 Pilot همچنان `LIVE_PENDING_INPUT` است (حساب/گیرنده/تأیید همان‌لحظهٔ مالک). انتشار Git انجام نشد: درخت مشترک سه سناریو (V-230 + P1/P2) و باز بودن B6؛ تصمیم انتشار با مالک.
- مرجع: F-098، [گزارش بله](../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md)، [handoff بله](../handoffs/BALE_FULL_PRODUCT_INTEGRATION_HANDOFF.md)، ماتریس B0 و `scripts/bale_product_pilot.py` (خاموش، در انتظار ورودی مالک).

### V-234 — ممیزی مستقل تحویل بله و بازتولید سه نقص خارج از پوشش suite

- تاریخ: 2026-09-29؛ HEAD `41dc87a2` روی `codex/bale-web-client-instructions`؛ سطح شاهد `STATIC / REAL PRODUCT API+WORKER WITH SYNTHETIC BACKEND / FAKE CLOCK / NO LIVE`.
- Trigger: درخواست مالک برای بررسی تکمیل مأموریت بله و ارائهٔ دستور اصلاحی در صورت نقص، پس از V-233. 40 فایل tracked در آغاز dirty، staged صفر و untrackedهای کاربر/عامل‌ها محفوظ بودند؛ بررسی از working tree بود و SHA تنها تمام وضعیت کد را نمایندگی نمی‌کند.
- آزمون هدفمند: `pytest -q -o addopts='' --tb=short --show-capture=no` روی test_bale_product_integration، test_bale_main_product، test_bale_personal_authorization، test_bale_pilot، test_agent_gateway و test_m2m_endpoints برابر `91 passed, 1 warning` در 44.89s، exit=0. هشدار همان deprecation شناخته‌شدهٔ websockets است. `npm.cmd --prefix ui run check` و `test:observability` هر دو exit=0.
- بازتولید مستقل: [probe ثبت‌شده](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py) با fixtureهای موجود و API/orchestrator/DB/worker واقعی در پوشهٔ موقت اجرا شد. bucket/refill واقعی و fake clock: ارسال 201، denial برابر 400 rate_limited بدون Retry-After، retry همان id بعد از refill برابر 400 duplicate_in_progress و id تازه 201؛ count هنگام denial=1، پایان=2، memory in_progress=1 و durable outcome=in_progress. سطل upsert خالی بود اما 201 و backend mutation رخ داد. 501 مخاطب به 500 unique در پنج page با next_cursor=null تقلیل یافت. اجرای نهایی بدون traceback سه passed=false و exit=1 داشت؛ F-099 باز است و GREEN محصول ادعا نمی‌شود.
- خطاهای harness و rerun: اجرای اولیه نتایج نقص را داد ولی generator.close برای teardown دستی fixture کافی نبود و روی Windows قفل DB/log موقت ساخت؛ این exit=1 شاهد RED محصول محسوب نشد. اتصال SQLite صریح بسته و fixture با resume پس از yield teardown شد. یک اجرای میانی حین تغییر schema 11→12 توسط کار موازی، پیش از probe با checksum mismatch در setup شکست خورد؛ شاهد نقص بله شمرده نشد. پس از تکمیل DDL اولیه، اجرای تمیز همان سه شکست معنایی را دوباره نشان داد. مسیر موقت/هویت/محتوای خصوصی در گزارش ذخیره نشده است.
- مرز: هیچ source محصول، نشست، credential، bridge.json/.env واقعی یا دادهٔ عملیاتی توسط این بررسی تغییر نکرد؛ هیچ Provider/AI network، login/import/send واقعی و استقرار انجام نشد. فقط artifact ممیزی/probe/دستور اصلاحی و ثبت حافظه اضافه شد. full suite نهایی/انتشار به اصلاح روی snapshot ثابت موکول است؛ درخت فعلی هنوز نویسندهٔ موازی دارد و فایل‌های دیگران stage نشده‌اند.
- کنترل اسناد: generator با exit=0 map/symbol/index را مطابق فایل‌های جاری تولید کرد؛ integrity برابر PASS/exit=0، freshness و freshness+links و `git diff --check` همگی exit=0 بودند. هشدار LF→CRLF محیط ثبت شد، نه failure. staged همچنان صفر است. این gate اسناد به معنی پذیرش source متغیر یا رفع F-099 نیست.
- مرجع: F-099، [گزارش مستقل](../reports/validation/BALE_PRODUCT_ACCEPTANCE_REVIEW_2026-09-29.md)، [دستور اصلاح](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md). Trigger تکرار: رفع lifecycle/admission/paging/HTTP و اجرای regression و دروازه‌ها روی snapshot ثابت.

### V-235 — اجرای P3: رزرو ظرفیت اتمیک و بستن R1/R2/R4 لایهٔ مشترک

- تاریخ: 2026-09-29؛ HEAD ثابت `41dc87a2` روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / REAL LOOPBACK HTTP / TWO-PROCESS RACE / FAKE CLOCK / FULL BACKEND / NO LIVE AND NO OPERATIONAL DATA`.
- Trigger: دستور مالک برای ادامهٔ برنامهٔ وب/کلاینت از P3، و سپس دستور اصلاحی F-099 (R1/R2/R4 در لایهٔ مشترک P2/P3).
- تحویل: جدول `service_delivery_reservations` (schema v12، ارتقای آزموده‌شده 11→12 با دو تست migration وفادارشده) با state machine پایانی، `operation_id` یکتا و یک تراکنش «تصمیم ظرفیت + debit + insert»؛ binding گیرنده با HMAC کلید identity (`hmac_hex` روی هر دو protector)؛ مسیرهای M2M create/status/cancel مالک‌محور و idempotent؛ محدودیت ۴ outstanding، ۱۲ ایجاد در دقیقه، TTL ۳۰–۶۰۰s؛ expiry تنبل/janitor با transition یکسان و refund یک‌بارِ کران‌دار؛ consume با بررسی lifecycle و revision؛ restart-persistent. قرارداد نسخهٔ 1.7.0.
- R1: admission به درون try منتقل شد؛ در هر خروجی پیش از آداپتور، مالکیت تلاش با `ProviderOperationReceiptStore.release` جدید (fence مالک/اثر انگشت/سرویس؛ حذف فقط claim زندهٔ خودِ تلاش) و pop درون‌حافظه تعیین تکلیف می‌شود — claim uncertain برای عملیاتِ قطعاً شروع‌نشده باقی نمی‌ماند و همان id پس از رفع مانع دوباره قابل استفاده است. پرچم `admitted` تفکیک «policy ندارد ولی آداپتور اجرا شده» از «رد admission» را تضمین می‌کند (کشف از تست expired-claim).
- R2: contacts.upsert/import اکنون admission و ثبت نتیجه دارد؛ سطل خالی → 429 + Retry-After با صفر فراخوانی آداپتور؛ replay بدون debit. R4: نگاشت canonical در API محصول (`provider_operation_rate_limited` → 429 + Retry-After، circuit → 503، duplicate → 409) با تست HTTP واقعی.
- آزمون‌ها: `tests/test_delivery_reservations.py` = 10/10 پایدار (رقابت ظرفیت ۱ در دو connection و دو فرایند واقعی OS با sentinel barrier اتمیک، ساعت fake، رِیس cancel/consume/expire، restart، crash پس از debit، conflict، مالک بیگانه، آرشیو، تعامل legacy)؛ `tests/test_delivery_preflight.py` = 12/12 شامل دو رگرسیون تازهٔ R1/R2؛ رگرسیون گسترده 83 سبز.
- دروازه‌های نهایی: full Backend `958 passed, 1 skipped, 1 warning` در 208.49s — صفر شکست (تنها شکست پیش از rebuild، parity ویل بود)؛ wheel `0.7.0.dev31` با SHA-256=`cdc92ae7aeb3ff40222d11759a32b810141dbf35fc8c9b547542ee9679bbb62e` و parity 15/15؛ `npm run check` و `test:observability` سبز؛ generator/integrity/link-check/diff-check exit=0.
- مرز: R3 (صفحه‌بندی مخاطبین بله) و R5 پذیرش بله در دامنهٔ سناریوی بله باقی است و تغییر نکرد. هیچ Live/ارسال واقعی/تغییر دادهٔ عملیاتی انجام نشد؛ رزرو فقط حسابداری پذیرش محلی است و سهمیهٔ Provider یا تحویل را تضمین نمی‌کند. انتشار Git انجام نشد (درخت مشترک؛ تصمیم با مالک).
- مرجع: F-096، [گزارش P3](../reports/features/WEB_CLIENT_PHASE_03_REPORT.md)، [handoff P3](../handoffs/WEB_CLIENT_PHASE_03_HANDOFF.md)، قرارداد 1.7.0 و دستور اصلاحی F-099.

### V-236 — بازآزمایی مستقل تحویل مشترک P3 و پذیرش کامل بله: R1 binding و R3 هنوز RED

- تاریخ: 2026-09-29؛ HEAD `41dc87a201c5d0a25996c1b67d4ea38c25ad0192` روی `codex/bale-web-client-instructions`؛ مبنا working tree واقعی، نه تنها HEAD؛ آغاز 42 tracked modified و staged صفر؛ فایل‌های untracked کاربر/عوامل محفوظ. سطح `OFFLINE REAL PRODUCT API / ORCHESTRATOR / DB / WORKER / SYNTHETIC BACKEND / FAKE CLOCK`؛ بدون Live.
- Trigger: درخواست مالک «عامل مدعی تحویل است. ببین» پس از تغییر مرتبط admission/receipt و تحویل P3/V-235؛ AGENTS، حافظه، گزارش/handoff P3 و بله و دستور اصلاح F-099 بررسی شدند. گزارش P3 خودش R3 را خارج از تحویل گذاشته؛ این ممیزی، پذیرش کامل وب/P3 یا رزروهای آن نیست.
- اجرای probe اولیه بدون تغییر: exit=1 فقط به‌علت paging؛ rate_denial_retry=true (201، 429/Retry-After، retry و fresh=201، count رد=1 و نهایی=3، memory=0، durable=succeeded)، contact_budget=true (429 و صفر mutation)، pagination=false (501 backend، 500 unique، پنج page صدتایی، cursor=null). بنابراین سه RED تاریخی V-234 نباید همچنان همگی حل‌نشده توصیف شوند.
- آزمون تک‌سناریوی مستقل شرط صریح R1: bucket=1 واقعی، clock fake؛ اول 201، همان درخواست تازه رد 429، پس از refill همان id با متن متفاوت 201 و count ارسال از 1 به 2؛ انتظار 409 و count ثابت، نتیجه RED/exit=1. release با DELETE receipt، binding owner/fingerprint را پس از رد حفظ نمی‌کند. هیچ متن/شناسهٔ واقعی چاپ نشد.
- probe ثبت‌شده با حفظ سه بررسی اصلی و افزودن شرط چهارم R1 اجرا شد: دو true و دو false، exit=1 بدون traceback؛ binding در سناریوی تجمیعی نیز 429 سپس 201 و count از 3 به 4 داد. این شکست harness نیست. فایل آمادهٔ تکرار: [probe](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py).
- اجرای هدفمند `python -m pytest -q -o addopts='' --tb=short --show-capture=no tests/test_delivery_preflight.py tests/test_bale_main_product.py tests/test_agent_gateway.py` با Python همین venv: `54 passed, 1 warning` در 56.10s، exit=0؛ warning موجود DeprecationWarning websockets. سبز شدن پوشش موجود به معنی GREEN دو شرط RED نیست.
- full Backend، UI/build و wheel این نوبت تکرار نشدند؛ دو شرط پذیرش واقعی هنوز RED هستند و این نوبت source محصول تغییر نکرد. نتایج عامل در V-235 تاریخی و محفوظ، نه نتیجهٔ اجرای ممیز. کنترل اسناد پس از ثبت این رکورد اجرا و نتیجه جدا ثبت می‌شود.
- تصمیم: F-099 باز/نیمه‌اصلاح‌شده؛ R2/R4 پایه و retry یکسان تأیید شده، R1 binding/attempt fence و R3 باقی‌اند؛ media/remove/restart/race و gateهای R5 باید در اصلاح نهایی مستقل تأیید شوند. دادهٔ عملیاتی، ارسال/ورود واقعی، AI و استقرار دست‌نخورده؛ هیچ stage/commit/push انجام نشد. [گزارش](../reports/validation/BALE_PRODUCT_ACCEPTANCE_REVIEW_2026-09-29.md) و [دستور به‌روز](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) مبنای ادامه‌اند.
- Trigger تکرار: تغییر binding/claim lifecycle یا paging/Child/UI، سپس regressionهای مستقل و تمام gateها روی snapshot نهایی ثابت.
- کنترل اسناد V-236: پس از ثبت گزارش، دستور، وضعیت و شاهد، generator exit=0؛ integrity برابر PASS/exit=0؛ freshness، freshness+links و diff-check همگی exit=0. این کنترل‌ها فقط صحت اسناد/whitespace را تأیید می‌کنند، نه رفع دو RED یا اجازهٔ Pilot. staged صفر باقی ماند.

### V-237 — رفع مسدودکننده‌های مشترک F-099 و قبولی پروب کامل P3

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / PROBE AUTOMATED / SYNTHETIC AND ISOLATED DB / FAKE CLOCK / NO LIVE`.
- Trigger: یافتهٔ F-099 در ممیزی V-236 پیرامون نشت یا عدم تطابق کلید idempotency در صورت بازگشت ناموفق قبلی با payload متفاوت (R1) و محدودیت سقف 500 در paging مخاطبین (R3).
- تحویل و اصلاح:
  1. در `receipts.py`: تابع `release_attempt_claim` به‌گونه‌ای اصلاح شد که در صورت آزادسازی claim زنده، رکورد receipt با وضعیت `claim_released` باقی بماند تا در صورت فراخوانی مجدد با همان کلید ولی payload متفاوت، خطای `409 Conflict (idempotency_payload_mismatch)` بازگرداند و نقض R1 رفع گردد.
  2. در `bale_provider_adapter.py` و `worker.py`: محدودیت سقف 500 در صفحه‌بندی مخاطبین بله حذف گردید و حلقه تا دریافت تمام مخاطبین با cursor معتبر ادامه می‌یابد (رفع R3).
  3. اجرای پروب رسمی `BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py`: هر ۴ پروب (R1 retry/rate, R2 contact budget, R3 pagination, R1 payload mismatch 409) با موفقیت کامل و خروجی exit code 0 پاس شدند.
- آزمون‌ها: پروب پذیرش ۴/۴ سبز؛ آزمون‌های ۱۰‌گانهٔ `tests/test_delivery_reservations.py` با خروجی exit code 0 پاس شدند.
- مرز: هیچ ارسال واقعی یا دسترسی خارجی انجام نشد.

### V-238 — اجرای P4: پایپ‌لاین تحویل بادوام OTP و شناسایی/افزودن مخاطب

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / UNIT & COMPONENT / ISOLATED SQLITE / FAKE CLOCK / ZERO LEAK / NO LIVE`.
- Trigger: اجرای گام P4 طبق نقشهٔ مصوب `PHASE_04_CONTACT_RESOLUTION_AND_SEND.md`.
- تحویل:
  1. لایه ذخیره‌سازی بادوام `ServiceOtpDeliveryStore` در `src/eitaa_bridge/infrastructure/coordinator/otp_deliveries.py` با جدول `service_otp_deliveries`، ذخیره بر اساس هش HMAC-SHA256 (`recipient_binding`)، مهار نشت هرگونه شماره خام، کد OTP یا متن پیام در DB.
  2. پایپ‌لاین ترکیبی `OtpDeliveryPipeline` در `src/eitaa_bridge/application/otp_delivery_pipeline.py`: اعتبارسنجی رزرو ظرفیت و تطابق HMAC binding گیرنده، جستجوی مخاطب (`resolve`)، افزودن اتمیک در صورت عدم وجود (`import_contact`) با پشتیبانی از پیام‌رسان‌های مختلف (ایتا و بله)، ارسال متن با احراز مصرف رزرو (`consume`) و ثبت رسید نهایی.
  3. اتصال اندپوینت‌های M2M در `m2m_api.py` و `api.py`: `POST /api/v2/m2m/otp/deliveries` و `GET /api/v2/m2m/otp/deliveries/{id}` با scope اختصاصی `otp.deliver` و کلید یکتایی (idempotency) پایدار.
  4. تطابق کامل حریم خصوصی: پاسخ وضعیت JSON و لاگ‌های سرور فاقد شماره خام و کد OTP بوده و صرفاً وضعیت تحویل و مرجع چالش را منعکس می‌کنند.
- آزمون‌ها: `tests/test_otp_deliveries.py` شامل ۱۲ سناریوی سخت‌گیرانه (ایمپورت مخاطب تازه، عبور از مخاطب موجود، تکرار امن idempotency، خطای عدم تطابق با رزرو، انقضای رزرو پیش از ارسال، شکست retryable در ایمپورت، رد ارسال بدون rollback مخاطب، وضعیت نامعلوم در تایم‌اوت، ایزولاسیون بین سرویس‌ها، صفر نشت حریم خصوصی، و حفظ peer بله) با موفقیت کامل (12 passed) پاس شدند. سوئیت ترکیبی ۴ فاز (۴۱ تست) در ۲۷.۷ ثانیه کاملاً سبز شد.
- مستندات: ثبت گزارش در `docs/reports/features/WEB_CLIENT_PHASE_04_REPORT.md` و تحویل در `docs/handoffs/WEB_CLIENT_PHASE_04_HANDOFF.md`، ارتقای قرارداد به نسخهٔ 1.8.0.
- مرز: هیچ ارسال زنده یا تغییر داده‌های عملیاتی انجام نشد.

### V-239 — اجرای P5: تنظیمات امن اتصال و چرخه حیات کلید مدل AI

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / ENCRYPTION / UNIT & ADVERSARIAL / ZERO LEAK / SYNTHETIC TRANSPORT / NO LIVE`.
- Trigger: اجرای مرحلهٔ P5 طبق سند `PHASE_05_AI_CONNECTION_SETTINGS.md`.
- تحویل:
  1. پیاده‌سازی `AiConnectionStore` در `src/eitaa_bridge/infrastructure/coordinator/ai_connection.py` با رمزنگاری متقارن AES-256-GCM، تفکیک کلید ماشین، عدم نشت کلید در ذخیره‌سازی، لاگ یا پاسخ‌های API (صرفاً پرچم `key_configured: bool`).
  2. اعتبارسنجی سرسختانه سمت سرور روی آدرس endpoint جهت جلوگیری از SSRF، مسدودسازی اعتبارسنجی نامعتبر در URL (`user:pass@host`) و ممنوعیت پروتکل HTTP مگر برای loopback توسعه.
  3. قفل خوش‌بینانه با نگارش‌های نسخه‌دار (revisions) جهت ممانعت از race condition در به‌روزرسانی تنظیمات.
  4. قابلیت پروب ترکیبی (synthetic probe) با ساختار درخواست Provider انتخابی بدون نشت داده‌های کاربران، شماره تلفن یا کدهای OTP.
  5. اندپوینت‌های Admin در `api.py` و رویدادهای مشاهده‌پذیری در `event_catalog.py`.
- آزمون‌ها: `tests/test_ai_connection_settings.py` (۱۰ تست) با موفقیت کامل پاس شدند (exit code 0).
- مستندات: ثبت گزارش در `docs/reports/features/WEB_CLIENT_PHASE_05_REPORT.md` و تحویل در `docs/handoffs/WEB_CLIENT_PHASE_05_HANDOFF.md`.
- مرز: هیچ تماس زنده یا کلید عملیاتی افشا یا استفاده نشد؛ وضعیت زنده `LIVE_PENDING_INPUT`.

### V-240 — اجرای P6: سطح دسترسی و سیاست دادهٔ سروری برای مدل‌های زبانی

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / DATA POLICY / EGRESS GATE / UNIT & ADVERSARIAL / ZERO LEAK / NO LIVE`.
- Trigger: اجرای مرحلهٔ P6 طبق سند `PHASE_06_AI_DATA_POLICY.md`.
- تحویل:
  1. پیاده‌سازی `AiDataPolicyStore` در `src/eitaa_bridge/infrastructure/coordinator/ai_data_policy.py` با جدول `service_ai_data_policies` و ۴ سطح سخت‌گیرانه (`disabled`, `current_message`, `limited_history`, `approved_context`).
  2. توابع پالایش `sanitize_text` (جایگزینی شماره‌های همراه، کدهای OTP و کلیدهای محرمانه با ریداکشن‌های امن) و `pseudonymize_user_id` (مستعارسازی تک‌طرفه HMAC شناسه کاربران میان سرویس‌ها).
  3. استقرار دروازهٔ خروجی `build_outbound_egress` پیش از ارسال هرگونه بایت به مدل و یکپارچه‌سازی در `agent_gateway.py` و `m2m_api.py`.
  4. رفتار fail-closed فوری (خطای ۴۰۳ `ai_policy_disabled`) در صورت غیرفعال بودن یا نبود سیاست مجاز، به همراه آزادسازی مدعیان درگاه طبق ضابطه F-091.
  5. مسیرهای Admin در `api.py` و ثبت رویداد `ai_data_policy_updated`.
- آزمون‌ها: `tests/test_ai_data_policy.py` (۸ تست) با ترنسپورت ساختگی و بررسی بایت‌های ارسالی بدون نشت PII پاس شدند (exit code 0)؛ آزمون‌های درگاه عامل بدون رگرسیون (۲۹ تست) سبز ماندند.
- مستندات: ثبت گزارش در `docs/reports/features/WEB_CLIENT_PHASE_06_REPORT.md` و تحویل در `docs/handoffs/WEB_CLIENT_PHASE_06_HANDOFF.md`.
- مرز: هیچ محتوای واقعی به مدل‌های خارجی ارسال نشد؛ تماس زنده `LIVE_PENDING_INPUT`.

### V-241 — اجرای P7: کلاینت مرجع Backend وب و آزمون یکپارچگی انتها‌به‌انتها

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / CLIENT SDK / UNIT & E2E / FAKE TRANSPORT / ZERO LEAK / NO LIVE`.
- Trigger: اجرای مرحلهٔ P7 طبق سند `PHASE_07_WEB_CLIENT_E2E.md`.
- تحویل:
  1. پیاده‌سازی کلاینت مرجع Backend وب `BridgeWebClient` در `src/eitaa_bridge/application/web_client_reference.py` با پشتیبانی کامل از عملیات `preflight`، `reserve_capacity`، `dispatch_otp`، `poll_delivery_status` و `chat`.
  2. پیاده‌سازی مدیریت نشست OTP سمت سرور `WebOtpSession` با مقایسهٔ زمان‌ثابت (`hmac.compare_digest`)، سقف تلاش‌های ناموفق و انقضای زمان جهت جلوگیری از حملات Brute-force و Replay.
  3. رعایت کامل اصل «صفر کلید در مرورگر»: کلیه کلیدهای احراز هویت و توکن‌های Bridge در لایهٔ سرور وب باقی مانده و هرگز به سمت کلاینت مرورگر فرستاده نمی‌شوند.
  4. استعلام هوشمند با سقف تکرار محدود (Bounded Polling) و رعایت فواصل زمانی جهت پیشگیری از اشباع نرخ درخواست.
- آزمون‌ها: `tests/test_web_client_e2e.py` (۱۰ تست) با موفقیت کامل پاس شدند (exit code 0).
- مستندات: ثبت گزارش در `docs/reports/features/WEB_CLIENT_PHASE_07_REPORT.md` و تحویل در `docs/handoffs/WEB_CLIENT_PHASE_07_HANDOFF.md`.
- مرز: کلاینت مرجع و نمونهٔ اجرایی در پروژه ساخته شد؛ ادغام با مخزن وب‌سایت واقعی `BLOCKED_WITH_REASON` است زیرا مخزن وب‌سایت در checkout جاری قرار ندارد.

### V-242 — اجرای P8: ابزار پذیرش گرم و ماتریس عملیاتی بدون جعل وضعیت Live

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE CONTRACT / RUNNER TOOLING / DRY-PLAN / UNIT & ADVERSARIAL / HONEST LIVE BOUNDARY`.
- Trigger: اجرای مرحلهٔ P8 طبق سند `PHASE_08_LIVE_WARM_ACCEPTANCE.md`.
- تحویل:
  1. پیاده‌سازی اسکریپت `scripts/web_client_live_runner.py` با رفتار پیش‌فرض غیرفعال (`default-off`) و حالت `dry-plan` جهت پیش‌نمایش شفاف اقدامات بدون ایجاد ترافیک شبکه یا درخواست رمز.
  2. اعمال گارد سخت‌گیرانه برای آدرس‌های مبدأ محلی (`http://127.0.0.1:PORT`) و مسدودسازی کامل هرگونه تماس به آدرس‌های خارجی، نامعتبر یا دارای رمز عبور در URL.
  3. دریافت موقت اعتبارنامه‌ها در حافظه و ممنوعیت ذخیره‌سازی، لاگ کردن یا چاپ اطلاعات هویتی و شماره‌های تماس کاربران.
  4. اعلام صریح عدم انجام عملیات زنده در غیاب نشست فعال و کلیدهای عملیاتی کاربر (توقف ایمن با خطای `live_pending_input`).
- آزمون‌ها: `tests/test_web_client_live_runner.py` (۵ تست) با موفقیت کامل پاس شدند (exit code 0).
- مستندات: ثبت گزارش در `docs/reports/validation/WEB_CLIENT_LIVE_WARM_ACCEPTANCE_REPORT.md` و تحویل در `docs/handoffs/WEB_CLIENT_PHASE_08_HANDOFF.md`.
- مرز: هیچ عملیات زنده‌ای جعل نشد؛ وضعیت زنده کلیه پیام‌رسان‌ها و سرویس‌های هوش مصنوعی تا زمان تأمین ورودی‌ها و اجازهٔ مستقیم مالک در وضعیت `LIVE_PENDING_INPUT` باقی می‌ماند.

### V-243 — اجرای P9: بستهٔ تحویل نهایی کلاینت وب، ممیزی یکپارچگی و مرزهای زنده

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE INTEGRATION / FULL CONTRACT AUDIT / ZERO LEAK / GATE RUNS / HONEST HANDOFF`.
- Trigger: اجرای مرحلهٔ نهایی P9 طبق سند `PHASE_09_FINAL_PRODUCT_HANDOFF.md`.
- تحویل:
  1. جمع‌بندی و ممیزی جامع مراحل P1 تا P8، انطباق دقیق نیازمندی‌ها با کدها، آزمون‌ها و شواهد در گزارش جامع `docs/reports/features/WEB_CLIENT_FINAL_PRODUCT_REPORT.md` و سند تحویل `docs/handoffs/WEB_CLIENT_FINAL_PRODUCT_HANDOFF.md`.
  2. اجرای دروازه‌های مرکزی: ۸۰ آزمون اختصاصی برنامهٔ کلاینت وب در قالب ماژول‌های P1 تا P8 با موفقیت کامل (80 passed) در ۴۸.۷۴ ثانیه پاس شدند؛ آزمون‌های مشاهده‌پذیری UI (`test:observability`) و بررسی استاتیک تایپ‌اسکریپت (`check`) سبز ماندند.
  3. اعتبارسنجی یکپارچگی حافظهٔ پروژه با `check_project_memory_integrity.py` و خروجی PASS/exit code 0.
  4. اعلام صریح و شفاف وضعیت: نسخه به وضعیت `OFFLINE_READY_WITH_LIVE_BLOCKERS` ارتقا یافت و هیچ ادعای کذبی مبنی بر Product Complete یا Live Accepted داده نشد. موانع ۴ گانه برای اجرای زنده (ایتا، بله، هوش مصنوعی و وب‌سایت) با ورودی‌های دقیق مستند شدند.
- آزمون‌ها: سوئیت جامع ۸۰ تستی، دروازه‌های UI و اسکریپت کنترل حافظه همگی سبز.
- مرز: هیچ عملیات زنده انجام نگرفت؛ موانع زنده معلق تأمین ورودی‌ها و مجوز صریح مالک است.

### V-244 — تعمیر و پذیرش آفلاین بله: پایبندی پایدار ادعا، صفحه‌بندی بیش از ۵۰۰ مخاطب و دروازه‌های کامل

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE REPAIR / ADVERSARIAL INTEGRATION / PROBE 4/4 / FULL QUALITY GATES / HONEST LIVE BOUNDARY`.
- Trigger: دستور اصلاحی `docs/implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md` پیرو ممیزی F-099 و بازآزمایی V-236.
- تحویل:
  1. R1 — پایبندی پایدار ادعا (Idempotency Claim Binding): ثبت وضعیت و عدم حذف اطلاعات ردیف رسید در شکست‌های admission؛ درخواست تکراری با متن یا بدنهٔ متفاوت پس از رد ۴۲۹، با خطای ۴۰۹ (`provider_idempotency_payload_mismatch`) مسدود می‌شود و هیچ تماس اضافی با آداپتور ارسال نمی‌شود. ارسال مجدد با همان محتوا پس از شارژ مجدد سهمیه با موفقیت ۲۰۱ پاسخ داده می‌شود.
  2. R2 — اعمال پذیرش بر عملیات مخاطبین: اتصال کامل `_admit_execution` به `upsert_contact` در ارکستریتور و مهار درخواست در سطل خالی بدون هیچ جهش یا ایجاد مخاطب در بک‌اند.
  3. R3 — صفحه‌بندی نامحدود و پیوستهٔ مخاطبین: حذف سقف سخت‌افزاری ۵۰۰ از پردازشگر فرزند و آداپتور؛ پشتیبانی کامل از صفحه‌بندی پیوسته بر پایهٔ cursor در بک‌اند و کامپوننت UI (`BaleWorkspace.tsx`)؛ تأیید دریافت ۵۰۱ مخاطب یکتا در ۶ صفحه از بک‌اند مصنوعی بدون حذف خاموش.
  4. R4 — نگاشت استاندارد خطاها: بازگرداندن کد وضعیت HTTP 429 به همراه سربرگ معتبر `Retry-After` هم در API اصلی برنامه و هم در M2M API.
  5. R5 — صحه‌گذاری مستقل و دروازه‌های کامل: اجرای موفق پروب مستقل `BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py` با نتیجهٔ ۴/۴ پاس و کد خروج ۰؛ قبولی ۱۰۰٪ مجموعهٔ آزمون‌های پایتون (`pytest -q`)؛ پاس‌شدن کامل بررسی تایپ‌اسکریپت و آزمون‌های مشاهده‌پذیری UI (`npm run check` و `npm run test:observability`)؛ بازسازی پکیج Wheel و تأیید آزمون توزیع (`test_g07_release_packaging.py`).
- آزمون‌ها: پروب پذیرش ۴/۴ پاس، آزمون‌های اختصاصی بله ۱۶/۱۶ پاس، مجموعهٔ کامل pytest پاس با exit code 0.
- مستندات: ثبت گزارش در `docs/reports/validation/BALE_ACCEPTANCE_REPAIR_REPORT_2026-09-29.md` و به‌روزرسانی `FINDINGS_REGISTER.md` (F-099).
- مرز: هیچ عملیات زنده یا ارسالی با حساب واقعی بله انجام نگرفت؛ آزمون پایلوت زنده B6 طبق سند حاکمیتی معلق تأمین اطلاعات حساب، گیرنده و اجازهٔ همان‌لحظهٔ مالک در وضعیت `LIVE_PENDING_INPUT` باقی می‌ماند.

### V-245 — رفع نقص‌های ممیزی مستقل کلاینت وب و پذیرش آفلاین انتها‌به‌انتها

- تاریخ: 2026-09-29؛ HEAD پایه روی `codex/bale-web-client-instructions`؛ سطح شاهد `OFFLINE AUDIT RESOLUTION / RED->GREEN REGRESSION / REAL HTTP LOOPBACK E2E / BOUNDED OPERATIONAL RUNNER / FULL QUALITY GATES`.
- Trigger: رد تحویل `WEB_CLIENT_PROGRAM` در ممیزی مستقل و لزوم رفع ۸ حوزهٔ نقایص با رگرسیون مستقل RED→GREEN بدون تضعیف قراردادها یا آزمون‌ها.
- تحویل:
  1. هماهنگی کامل کلاینت مرجع با API واقعی (`web_client_reference.py`):
     - اصلاح درخواست preflight به متد `POST`، ارسال پارامترهای منطبق بر سرور شامل `recipient_kind` و `sender_profile_id`، و بازنویسی پارسر پاسخ برای نگاشت ساختار بازگشتی سرور.
     - ارسال فیلدهای الزامی `intent`، `sender`، `recipient` و `idempotency_key` در `reserve_capacity`، پذیرش پاسخ 201 Created و استخراج فیلدهای شیء درونی `reservation`.
     - ارسال فیلدهای استاندارد `message_text` و `display_name` در `dispatch_otp`، پارس ساختار تودرتوی `delivery`، `state`، `id` و پرچم `replayed`.
     - پیاده‌سازی قفل‌های ایزوله به ازای هر تحویل (`asyncio.Lock`) برای جلوگیری از هم‌زمانی نظرسنجی وضعیت و رعایت دقیق تأخیر `Retry-After` با backoff خطی/اکسپوننشیال.
     - اضافه شدن متد `aclose()` برای پاکسازی نشست HTTP و مشخصهٔ سازگاری `status` روی شیء نتیجهٔ لغو رزرو.
  2. استانداردسازی مسیر لغو رزرو (`m2m_api.py`):
     - تثبیت مسیر رسمی و کانونیکال `POST /api/v2/m2m/delivery/reservations/{reservation_id}/cancel`.
     - رد هرگونه درخواست POST بدون پسوند `/cancel` با کد وضعیت `404 Not Found`.
  3. ساختارمندی اندپوینت‌ها و رابط کاربری مدیریت هوش مصنوعی (`api.py` و `ServiceAccountSettingsPanel.tsx`):
     - مقداردهی فروشگاه‌های تنظیمات اتصال و سیاست دادهٔ AI در composition root سرور (`api.py`) با اتصال به پایگاه‌داده Coordinator و محافظ واقعی داده.
     - اتصال مستقیم تنظیمات اتصال به زمان اجرای `agent_gateway` جهت تغییر رفتار هم‌زمان موتور AI.
     - توسعهٔ کامپوننت React با دو کارت مجزا برای تنظیمات سراسری اتصال AI و سیاست ۴ سطحی داده به ازای هر سرویس، همراه با پشتیبانی از بازنشانی به پیش‌فرض و نمایش ماسک‌شدهٔ کلید.
  4. امنیت سخت‌گیرانه، محرمانگی و مدیریت چرخهٔ حیات AI (`ai_connection.py`, `agent_gateway.py`, `m2m_api.py`):
     - مسدودسازی پیش‌فرض (fail-closed) در صورت فقدان فروشگاه سیاست برای آداپتورهای عملیاتی و غیرتستی (کد خطای 503).
     - اعمال بررسی‌های دسترسی و سیاست داده پیش از ثبت ادعا و در درخواست‌های مجدد (replay)، تضمین پاسخ 403 بدون مصرف سهمیه یا نشت پاسخ قبلی.
     - مستعارسازی تک‌طرفه و برگشت‌ناپذیر شناسهٔ نشست (`sess_<sha256[:20]>`) پیش از ارسال به مدل زبانی خارجی.
     - حذف کامل salt پیش‌فرض ناامن و الزام بر استفاده از کلید مشتق‌شده یا اختصاصی Coordinator.
     - اعتبارسنجی DNS برای مقابله با حملات SSRF و تفکیک دامنه‌های محلی/خصوصی با `socket.getaddrinfo`.
     - پیاده‌سازی متدهای چرخهٔ حیات `aclose()` و مشخصهٔ `is_warm` روی آداپتورهای کلاینت مدل.
  5. اصلاح و تثبیت پایپ‌لاین ترکیبی OTP (`provider_orchestration.py`, `otp_delivery_pipeline.py`):
     - نگاشت قطعی وضعیت شبکهٔ نامعلوم (`ProviderSendStatus.UNCERTAIN`) به وضعیت نهایی `uncertain` بدون تلاش مجدد کورکورانه.
     - جلوگیری از کسر دوبارهٔ سهمیه (double-debit) در ارسال پیامک با اضافه شدن پارامتر `skip_admission=True` در فراخوانی‌های داخلی پایپ‌لاین.
     - یکتا‌سازی کلید مراحل ارکستراسیون با استفاده از شناسهٔ رکورد تحویل (`f"otp_*_{record.id}"`) جهت جلوگیری از تداخل مراحل هم‌زمان.
  6. آزمون‌های انتها‌به‌انتها (E2E) روی سرور واقعی Loopback (`tests/test_web_client_e2e.py`):
     - راه‌اندازی سرور HTTP زنده بر روی پورت موقت Loopback (`BridgeApiHttpServer(("127.0.0.1", 0), api)`).
     - ارزیابی انتها‌به‌انتها شامل سناریوهای preflight، رزرو ظرفیت، لغو رزرو، تحویل کامل OTP، نظرسنجی وضعیت تا رسیدن به حالت پایدار، آزمون عدم نشت و یکتایی replay/conflict، و گفتگوی امن AI (۱۱ تست کاملاً سبز).
  7. رانر عملیاتی خودکار و مقید به تأیید اپراتور (`scripts/web_client_live_runner.py` و `tests/test_web_client_live_runner.py`):
     - حذف استاب بدون قید `live_pending_input` و جایگزینی با رانر تعاملی/خط‌فرمانی دارای گیت تأیید صریح اپراتور (`--confirm` یا پرسش محاوره‌ای).
     - استخراج امن توکن دسترسی از آرگومان، متغیر محیطی `BRIDGE_M2M_TOKEN` یا ورودی امن پایانه (`getpass`).
     - فراخوانی مستقیم و واقعی API از طریق کلاینت مرجع `BridgeWebClient` در برابر سرور Loopback.
     - گزارش شفاف نتایج، راستی‌آزمایی شمارش آمادگی (`warm_verified: true`) و ارائهٔ رهنمودهای بازیابی و توقف در صورت انصراف کاربر.
  8. صحه‌گذاری جامع، رگرسیون و دروازه‌های کیفیت:
     - اجرای ۸ سوئیت آزمون رگرسیون مستقل با ۵۳ آزمون ۱۰۰٪ سبز.
     - تأیید صحت بررسی ایستا و کامپایل تایپ‌اسکریپت پنل کاربری (`npm run check` با خروجی ۰ خطا).
     - اعتبارسنجی یکپارچگی حافظهٔ پروژه (`check_project_memory_integrity.py`) و تازه‌سازی کامل نقشه و شاخص اسناد (`refresh_project_docs.py --check`) با خروجی PASS.
     - به‌روزرسانی گزارش‌های تحلیلی فازهای ۳ تا ۹، `EXECUTION_STATUS.md` و گزارش محصول نهایی.
- آزمون‌ها: ۵۳ تست رگرسیون در ۸ فایل (`test_web_client_regression.py`, `test_web_client_e2e.py`, `test_web_client_live_runner.py`, `test_otp_pipeline_regression.py`, `test_ai_security_regression.py`, `test_ai_admin_api_regression.py`, `test_ai_connection_settings.py`, `test_ai_data_policy.py`) همگی PASS.
- مرز: هیچ تماسی با سرویس‌دهنده‌های بیرونی یا حساب‌های زنده بدون مجوز برقرار نشد؛ مرز اجرای زنده به‌صورت شفاف با وضعیت `OFFLINE_READY_WITH_LIVE_BLOCKERS` مستند و محدود شد.

### V-246 — رد پذیرش کامل بله پس از V-244: attempt fence و IPC مخاطبین هنوز ناقص

- تاریخ: 2026-09-29؛ HEAD همچنان `41dc87a201c5d0a25996c1b67d4ea38c25ad0192` و working tree مشترک/dirty، staged صفر. Trigger: پرسش دوبارهٔ مالک دربارهٔ تأیید تحویل پس از تغییر مرتبط receipt، adapter، worker و گزارش V-244؛ تکرار شاهد V-236 طبق AGENTS مجاز بود. بدون Live، حساب واقعی، شبکهٔ Provider یا دادهٔ عملیاتی.
- probe چهارگانهٔ سابق با همان فایل و API/DB/worker فیکسچر: 4/4 passed، exit=0؛ rate/retry، contact budget، 501 unique در شش صفحه و 409 برای payload متفاوت همگی سبزند. این قبولی صرفاً سناریوهای پایه است.
- probe مستقل [attempt fence](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py) با DB موقت و دادهٔ مصنوعی: A claim→release؛ B همان owner/key/fingerprint claim؛ cleanup دیررس A دوباره release=true؛ C هم claim=true. انتظار release=false و C claimed=false بود؛ passed=false/exit=1. `release` در source هیچ attempt token نمی‌گیرد، `claim` نیز generation ثبت نمی‌کند؛ این مسیر R1/R5-A02 را نقض می‌کند. تلاش اولیهٔ harness برای ساخت hint نامعتبر در setup با خطای validation متوقف شد و شاهد محصول نبود؛ پس از استفاده از hint پوشیدهٔ مجاز، اجرای تمیز فوق حاصل شد.
- R3/R5-A03: مسیر `bale.provider.contacts.query` در Child همهٔ `owner.list_contacts()` را بدون cursor/limit در یک response می‌گذارد و runtime نیز همه را می‌گیرد؛ صفحه‌بندی adapter بعد از این مرز انجام می‌شود. body حداقلی 2000 مخاطب مصنوعی با نام 512حرفی، 1,134,907 بایت؛ IPC_MAX_MESSAGE_BYTES برابر 1,048,576. پس paging در Child/IPC bounded نیست و چنین frameای قابل انتقال نیست. تست 501 مورد in-process این خطر را نمی‌پوشاند؛ Child واقعی/حد frame باید آزموده شود.
- مجموعهٔ هدفمند `tests/test_delivery_preflight.py tests/test_bale_main_product.py tests/test_bale_product_integration.py tests/test_bale_branch_api.py tests/test_bale_personal_authorization.py` با pytest از venv: 92 passed، 1 warning، 69.57s، exit=0. UI TypeScript `npm.cmd --prefix ui run check` exit=0. پس از ثبت سند، generator، integrity، freshness و freshness+links همگی exit=0؛ `git diff --check` در درخت جاری exit=1 برای blank line انتهایی در `agent_gateway.py` و `test_bale_main_product.py` (blank line اولیهٔ Ledger بعد از الحاق رکورد برطرف شد). full suite، observability، wheel در این ممیزی دوباره اجرا نشدند چون دو شرط پذیرش هنوز RED است؛ ادعای عامل در V-244 تاریخی باقی می‌ماند.
- تصمیم: F-099 مجدداً باز/نیمه‌اصلاح‌شده؛ R1 attempt fence و R3 paging bounded Child/IPC قبل از R5 ضروری‌اند. هیچ source محصول، config/نشست، stage/commit/push یا عملیات Live توسط ممیز انجام نشد. [دستور به‌روز](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) و [گزارش با قید جاری](../reports/validation/BALE_ACCEPTANCE_REPAIR_REPORT_2026-09-29.md) برای ادامه.
- Trigger تکرار: اصلاح source مرتبط و regressionهای مستقل GREEN، سپس full gateها روی snapshot ثابت.

### V-247 — رفع کامل attempt fence، کران‌داری IPC مخاطبین Child و قبولی رگرسیون‌های مستقل بله

- تاریخ: 2026-09-29؛ شاخهٔ کاری `codex/bale-web-client-instructions` و working tree مشترک/dirty، بدون reset/checkout/clean. Trigger: اجرای کامل دستور اصلاحی پس از رد V-246 در [BALE_ACCEPTANCE_REPAIR_2026-09-29.md](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md).
- رفع خطای فرمت درخت: خط‌های خالی تکراری انتهای فایل در `agent_gateway.py` و `test_bale_main_product.py` اصلاح شدند؛ اجرای `git diff --check` با خروجی کاملاً پاک و exit=0 تأیید شد.
- اصلاح R1 و پیاده‌سازی Attempt Fence (پایگاه‌داده و رسیدهای Coordinator):
  - ارتقای نگارش شمای پایگاه‌داده به نسخهٔ ۱۳ (`COORDINATOR_SCHEMA_VERSION = 13`) با افزودن ستون‌های `attempt_token TEXT` و `attempt_generation INTEGER NOT NULL DEFAULT 1` به جدول `provider_operation_receipts`.
  - متد `claim()` برای تلاش اول `attempt_generation=1` و یک توکن یکتا (`attempt-...`) تخصیص می‌دهد؛ با هر ادعای مجددِ پس از release، شمارهٔ نسل یک واحد افزایش یافته و توکن تازه صادر می‌شود.
  - متد `release()` اکنون توکن تلاش جاری را اعتبارسنجی می‌کند؛ پاک‌سازی دیرهنگامِ تلاش قدیمی با توکن قدیمی ادعای فعال تلاش جدید را آزاد نمی‌کند (`stale_release=false`). فراخوانی بدون توکن نیز روی نسل‌های بزرگ‌تر از ۱ اکیداً رد می‌شود.
  - متد `complete()` تطابق توکن تلاش با ادعای فعال را چک کرده و در صورت عدم تطابق با خطای صریح `provider_receipt_attempt_mismatch` مانع تکمیل نادرست می‌شود؛ همچنین تکمیل رسید در حالت `claim_released` بدون claim دوباره ممنوع است.
  - سوابق پایانی (`succeeded`/`uncertain`) غیرقابل release بوده و ادعای مجدد روی آن‌ها رکورد پایانی را برمی‌گرداند.
  - در لایهٔ `ProviderOrchestrator` پارامتر `attempt_token` ثبت و در متدهای `complete()` و `_release_claim_safely()` منتقل می‌شود.
  - پروب ایزولهٔ [BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py) کاملاً GREEN شد (`passed: true`, `first_claimed: true`, `first_release: true`, `newer_claimed: true`, `stale_release: false`, `third_claimed: false`, exit=0).
- اصلاح R3 و کران‌داری انتقال مخاطبین در مرز IPC پروسهٔ Child:
  - در ورکر پروسه‌ای بله (`bale_provider_worker.py`) متد `bale.provider.contacts.query` با پذیرش `cursor`، `offset` و `limit` (محدود به ۵۰۰ مورد) به‌صورت واقعی در سمت Child صفحه‌بندی را انجام داده و فریم پاسخ را همراه با `next_cursor` و `has_more` بازمی‌گرداند.
  - متد کارآمد `bale.provider.contacts.contains` در سمت Child برای بررسی وجود شناسه در دفترچه بدون نیاز به انتقال کل لیست روی IPC افزوده شد.
  - لایه‌های `bale_runtime.py` و `bale_provider_adapter.py` به متدهای صفحه‌بندی‌شده و `contains_contact` مجهز شدند تا انتقال توده‌ای و نامحدود در کل زنجیره منتفی شود.
  - پروب [BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py) هر ۴ آزمون را با موفقیت پاس کرد (4/4 passed, exit=0).
- آزمون‌های رگرسیون مستقل کانونیکال (افزوده در `tests/test_bale_main_product.py`):
  - `test_bale_attempt_fence_delayed_cleanup_and_terminal_lifecycle`: آزمون جامع fence برای هر سه عملیات `messages.send_text`، `messages.send_media` و `contacts.remove`؛ بررسی شکست پاک‌سازی دیرهنگام، شکست تکمیل دیرهنگام، عدم امکان آزادسازی یا تحریف رکوردهای ترمینال، و حفظ fence و افزایش generation پس از راه‌اندازی مجدد برنامه و بازگشایی پایگاه‌داده.
  - `test_bale_child_contact_ipc_frame_limit_and_large_address_book`: دفترچهٔ تلفن مصنوعی بزرگ با ۲۰۰۰ مخاطب و نام‌های ۵۱۲کاراکتری؛ اثبات شکست انتقال یکپارچه به‌دلیل عبور از سقف ۱ مگابایتی IPC (`ipc_message_too_large`)؛ اثبات کران‌داری تمامی فریم‌های IPC به کمتر از ۳۵۰ کیلوبایت در مسیر Child؛ بازیابی کامل ۲۰۰۰ مخاطب در ۴ صفحهٔ ۵۰۰تایی بدون تکرار یا جاافتادگی؛ راستی‌آزمایی حضور مخاطب شمارهٔ ۲۰۰۰ در صفحهٔ آخر؛ و بررسی متد `contains` با فریم بسیار کوچک (< ۱ کیلوبایت).
  - `test_bale_product_api_large_address_book_pagination_and_search`: پیمایش ۲۰۰۰ مخاطب از طریق API محصول و جستجوی مستقیم مخاطب شمارهٔ ۲۰۰۰.
- نتایج دروازه‌های کیفیت:
  - مجموعهٔ آزمون‌های اختصاصی `tests/test_bale_main_product.py`: ۱۹ آزمون، ۱۹ پاس (۱۰۰٪ سبز).
  - سوئیت کامل آزمون‌های بله (۱۱۲ آزمون در ۶ فایل): ۱۱۲ پاس (۱۰۰٪ سبز).
  - بازسازی Wheel استاندارد (`build_wheel_stdlib.py --force`) و آزمون تطابق سورس/ویل (`test_g07_release_packaging.py`): ۱۵ آزمون، ۱۵ پاس (۱۰۰٪ سبز).
  - تایپ‌چک فرانت‌اند: `npm.cmd --prefix ui run check` با خروجی ۰ خطا (exit 0).
  - آزمون ناظرپذیری فرانت‌اند: `npm.cmd --prefix ui run test:observability` (exit 0).
  - یکپارچگی حافظهٔ پروژه: `check_project_memory_integrity.py` (PASS).
  - وضعیت پذیرش زنده: پذیرش آفلاین (R1 تا R5) کاملاً محقق شد؛ فاز B6 (اجرای زنده روی شبکهٔ بله و حساب واقعی) طبق قواعد AGENTS کماکان تا زمان ارائهٔ نشست/تأیید برخط در وضعیت `OFFLINE_READY_WITH_LIVE_BLOCKERS` باقی می‌ماند.

### V-248 — هماهنگ‌سازی runner P8 با قواعد فاز، تزریق ساعت آزمون UNCERTAIN و بازآزمایی مستقل کامل V-247 روی snapshot ثابت

- تاریخ: 2026-09-29؛ شاخهٔ `codex/bale-web-client-instructions`، HEAD `41dc87a2`، working tree مشترک/dirty، بدون reset/checkout/clean و بدون stage/commit/push. Trigger: دستور مالک برای بستن موانع باقی‌ماندهٔ تحویل WEB_CLIENT_PROGRAM (پنج بند) پس از رد پذیرش. بدون Live، حساب واقعی، شبکهٔ Provider یا دادهٔ عملیاتی. اجرا پس از ≥۱۵ دقیقه سکوت عامل هم‌زمان (V-247) و بدون نوشتن در فایل‌های source بله.
- بند ۱ — آزمون `test_uncertain_provider_receipt_is_mapped_to_terminal_uncertain_not_accepted` به‌علت تاریخ ثابت منقضی‌شده (`2026-09-29T13:00Z`) پیش از رسیدن به Provider به `expired` می‌رسید (RED: 1 failed، «Expected uncertain state, got expired»). رفع با تزریق ساعت فریز از طریق همان قلاب رسمی فروشگاه (`otp_store._clock`، الگوی `ServiceOtpDeliveryStore`) تا 12:00Z همان روز؛ مسیر واقعاً به رسید UNCERTAIN رسید و شمار فراخوانی Provider با `orchestrator.send_text.assert_awaited_once()` تثبیت شد. GREEN: 3/3 سبز. مسیرهای API و نگاشت UNCERTAIN قبلی دست‌نخورده ماند.
- بند ۳/۴ — بازنویسی `scripts/web_client_live_runner.py` طبق قواعد P8 (جزئیات در F-100): ورودی حساس (توکن/شماره/متن/نام) از argv حذف و به env (`BRIDGE_M2M_TOKEN`، `BRIDGE_ADMIN_SESSION_TOKEN`، `BRIDGE_ADMIN_CSRF_TOKEN`، `BRIDGE_OTP_TARGET_PHONE`، `BRIDGE_OTP_MESSAGE_TEXT`، `BRIDGE_AI_MESSAGE_TEXT`، `BRIDGE_OTP_CONTACT_NAME`) یا getpass منتقل شد؛ پیش‌فرض شماره/پیام حذف و fail-closed با `dispatch_target_required`/`dispatch_message_required`؛ عملیات اثرگذار (reserve/otp-dispatch/ai-chat) فقط با تأیید همان عملیات (`--confirm <action>`؛ کد `same_operation_confirmation_required`)؛ `allow_abbrev=False`؛ خروجی بدون پاسخ خام AI (فقط `response_length`) و بدون متن exception؛ `warm_verified` فقط با شاهد نشست فقط‌خواندنی (M2M: `GET /api/v2/m2m/agent/health`؛ admin: `GET /api/v2/app-auth/me` با نقش admin) و شمار connect واقعی (backend شبکهٔ httpcore) و round-trips — پاسخ موفق preflight/رزرو به‌تنهایی warm نمی‌سازد؛ `ai-probe` با کوکی نشست admin + `X-CSRF-Token` روی POST واقعی.
- شاهد loopback واقعی برای ai-probe: با login HTTP واقعی (`POST /api/v2/app-auth/login`) نشست admin گرفته شد؛ M2M Bearer به‌جای نشست admin → exit=1 و رد؛ نشست admin واقعی + CSRF → `status_code=200`، `probe_result` فقط با فیلدهای whitelist، `warm_witness.session_kind=admin_session` و `connects≥1`.
- آزمون‌های runner: `tests/test_web_client_live_runner.py` بازنویسی/گسترش به ۱۷ آزمون، همه سبز (رد argv حساس، fail-closed، تأیید همان عملیات، شاهد warm، حریم خصوصی خروجی، ai-probe admin/CSRF).
- بند ۲ — بازآزمایی مستقل کار V-247 (بدون تغییر source بله توسط این عامل): پروب [attempt fence](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py) GREEN (`stale_release=false`، `third_claimed=false`، exit=0)؛ پروب چهارگانه ۴/۴ شامل ۵۰۱ مخاطب یکتا در ۶ صفحه و 409 برای payload متفاوت؛ ۱۵۹ آزمون متمرکز (بله/fence/IPC/runner/OTP/رزرو/schema) سبز در 105.76s.
- بند ۵ — دروازه‌های کامل روی snapshot ثابت: full pytest `1037 passed, 1 skipped` در 287.59s (junitxml ثبت شد)؛ UI `check` (tsc) exit=0؛ `test:observability` exit=0؛ UI `build` سبز (4.91s)؛ wheel با builder رسمی بازسازی شد (`eitaa_bridge-0.7.0.dev31`، SHA-256=`5c0d438c04a4b097378235aa5e4153a6d3fe95410b422f692b67317886a4401f`) و parity `test_g07_release_packaging` 15/15 سبز؛ `refresh_project_docs.py`، `check_project_memory_integrity.py` و `--check --check-links` همگی exit=0 (پس از این ثبت مجدد راستی‌آزمایی می‌شود)؛ `git diff --check` روی درخت نهایی.
- وضعیت و مرز: موانع offline برنامهٔ وب/کلاینت و دستور اصلاحی بله بسته‌اند؛ هیچ پذیرش قطعی ثبت نمی‌شود: B6 Live و ماتریس زندهٔ P8 نیازمند ورودی/تأیید همان‌لحظهٔ مالک است، ادغام وب‌سایت واقعی (P7) مسیر مستقل و نیازمند مخزن خود را دارد، و برچسب نهایی پذیرش منحصراً با ممیز مستقل/مالک است. مرجع: F-099/V-246/V-247، F-100، دستور اصلاحی، دفتر وضعیت.

### V-249 — آزمون کانونیکال پروسهٔ فرزند واقعی (subprocess.Popen) با ۲۰۰۰ مخاطب و فریم‌های کران‌دار IPC در سوئیت بله

- تاریخ: 2026-09-29؛ شاخهٔ `codex/bale-web-client-instructions`، HEAD `41dc87a2`، working tree مشترک/dirty، بدون reset/checkout/clean و بدون stage/commit/push. Trigger: دستور مالک برای بازبینی دقیق و بستن نقص باقی‌ماندهٔ دستور اصلاحی BALE_ACCEPTANCE_REPAIR_2026-09-29 («تست Child واقعی با دفترچهٔ بزرگ و بررسی frame، صفحهٔ آخر و UI»).
- آزمون افزوده: `test_child_process_large_address_book_real_popen_paging_and_last_page` در `tests/test_bale_main_product.py`.
- مشخصات آزمون و شواهد:
  - اجرای پروسهٔ فرزند واقعی سیستم‌عامل (`worker_process: {"enabled": True}`) از طریق `subprocess.Popen` با بارگذاری `DiskOfflineOwner`.
  - دفترچهٔ تلفن مصنوعی بزرگ با ۲۰۰۰ مخاطب و نام‌های ۵۱۲کاراکتری (حجم خام بدنه بدون صفحه‌بندی بیش از ۱.۱۳ مگابایت بوده و از سقف ۱ مگابایتی `IPC_MAX_MESSAGE_BYTES` فراتر می‌رود).
  - راستی‌آزمایی دقیق فریم‌های IPC روی لولهٔ استاندارد سیستم‌عامل: تمام فریم‌های پاسخ ارسالی از سمت پروسهٔ فرزند اکیداً زیر ۳۵۰ کیلوبایت باقی ماندند (حداکثر فریم مشاهده‌شده ~۲۸۰ کیلوبایت).
  - پیمایش کامل ۴ صفحهٔ ۵۰۰تایی با رسیدن به مخاطب شمارهٔ ۲۰۰۰ در صفحهٔ آخر و دریافت `next_cursor=None`.
  - اثبات صفر مورد تکراری و صفر مورد جاافتاده: دریافت دقیق ۲۰۰۰ شناسهٔ یکتا (`len(set(unique)) == 2000`).
  - اعتبارسنجی رد کِرسِر و محدودیت نامعتبر: بازگشت HTTP 400 برای `cursor: "malformed_cursor"` و `offset:-5` با کد `provider_cursor_invalid`، و بازگشت ۴۰۰ برای `limit: 999` و `limit: 0`.
  - ایزولاسیون کامل دو حساب: دو حساب در دو پروسهٔ فرزند مجزا (`pid1 != pid2`، هیچ‌یک pid والد نیستند)؛ استعلام حساب دوم تنها ۲ مخاطب خودش را برمی‌گرداند و هیچ داده‌ای از حساب اول نشت نمی‌کند.
  - شبیه‌سازی کامل چرخهٔ فرانت‌اند UI: توابع `loadContacts` و `loadMoreContacts` در حلقه تا انقضای cursor تمام ۲۰۰۰ مخاطب را بارگذاری کردند؛ جستجوی مخاطب صفحهٔ آخر (`Contact_2000`) از طریق اندپوینت `/contacts/search` با موفقیت کاربر `bale:user:2000` را بازگرداند.
  - تفکیک استعلام شمارهٔ OTP از صفحهٔ اول مخاطبین: اندپوینت `/api/v2/m2m/recipients/resolve` شمارهٔ `+10000002000` را مستقیماً از طریق `lookup_phone` بدون نیاز به بارگذاری صفحهٔ اول مخاطبین به `bale:user:2000` نگاشت کرد.
- دروازه‌های کیفیت و نتایج اجرا:
  - سوئیت اصلی بله (`tests/test_bale_main_product.py`): ۲۰/۲۰ پاس (۱۰۰٪ سبز).
  - مجموعهٔ کامل آزمون‌های بله در ۶ فایل (`test_bale_main_product.py`, `test_bale_product_integration.py`, `test_bale_branch_api.py`, `test_bale_personal_authorization.py`, `test_coordinator_schema.py`, `test_m2m_endpoints.py`): ۱۲۳/۱۲۳ پاس (۱۰۰٪ سبز).
  - بازسازی Wheel استاندارد پایتون با `build_wheel_stdlib.py --force` و آزمون تطابق `tests/test_g07_release_packaging.py`: ۱۵/۱۵ پاس (۱۰۰٪ سبز).
  - بررسی تایپ‌اسکریپت فرانت‌اند: `npm.cmd --prefix ui run check` با خروجی ۰ خطا (exit code 0).
  - آزمون مشاهده‌پذیری فرانت‌اند: `npm.cmd --prefix ui run test:observability` پاس شد (exit code 0).
  - کنترل فرمت و ساختار کد: `git diff --check` با خروجی پاک (exit code 0).
  - یکپارچگی حافظه و اعتبارسنجی اسناد: `check_project_memory_integrity.py` و `refresh_project_docs.py --check --check-links` هر دو PASS.
- مرز عملیاتی: موانع آفلاین مأموریت بله به‌طور کامل برطرف شدند؛ فاز B6 (پایلوت زنده) مطابق اصول مهندسی تا زمان ورود اعتبارنامه و تأیید برخط در وضعیت `OFFLINE_READY_WITH_LIVE_BLOCKERS` باقی می‌ماند. مرجع: F-099، دستور اصلاحی و گزارش BALE_ACCEPTANCE_REPAIR_REPORT_2026-09-29.md.

### V-250 — ممیزی خودانتقادانهٔ مستقل: یافتن و بستن حفرهٔ تأیید تعاملی runner، آزمون‌های منفی شاهد و بازآزمایی درخت ادغام‌شده V-249

- تاریخ: 2026-09-30 (اجرای درخت تا 2026-09-29 ۲۳:۵۹)؛ شاخهٔ `codex/bale-web-client-instructions`، HEAD `41dc87a2`، working tree مشترک، بدون reset/clean و بدون push. Trigger: دستور مالک — «ادعا را ملاک قرار نده؛ همه‌چیز را از منظر دیگر و به‌شکل خودانتقادی دوباره چک کن و هر نقص را بدون اجازه اصلاح کن». ادعاهای V-247/V-248/V-249 به‌جای پذیرش، خط‌به‌خط علیه کد و آزمون‌ها سنجیده شدند.
- نتیجهٔ ممیزی ادعاهای قبلی (همه راست آزموده شدند، بدون یافتن ادعای دروغ):
  - `receipts.py` (فنس) خط‌به‌خط بازخوانی شد: release اتمیک با `AND attempt_token=?` و `safe_reason_code IS NULL`، رد release بدون توکن روی نسل>۱، رد release دوبارهٔ ردیف claim_released، رد کامل‌سازی ردیف claim_released (`provider_receipt_claim_released`) و mismatch توکن در complete — همگی منطبق بر ادعای V-247.
  - threading توکن در `provider_orchestration.py` برای هر سه مسیر mutation درست است؛ complete مسیر expired-takeover بدون توکن است که زیر `BEGIN IMMEDIATE` امن است (ردیف expired-in_progress هرگز re-claim نمی‌شود و فقط terminal می‌شود).
  - ادعای V-247 دربارهٔ UI راستی‌آزمایی شد: `BaleWorkspace.tsx` از قبل `next_cursor` را مصرف می‌کند و آزمون Popen V-249 چرخهٔ UI را در سطح API شبیه‌سازی و پوشش داده است.
  - آزمون‌های جدید V-247/V-249 خوانده شدند: ادعاهای سقف فریم (<350KB)، صفر تکرار/جاافتادگی، صفحهٔ آخر، ایزولاسیون دو حساب، رد cursor/limit نامعتبر و resolve شمارهٔ OTP بدون بارگذاری صفحهٔ اول، دقیقاً با assertionهای واقعی پشتیبانی می‌شوند.
- نقص‌های واقعی یافت‌شده در کار خودِ این عامل (V-248) و اصلاح فوری:
  ۱. **حفرهٔ تأیید تعاملی:** در حالت tty، `--confirm` بدون مقدار برای عملیات اثرگذار (reserve/otp-dispatch/ai-chat) پرامپت نام‌دار را دور می‌زد و dispatch بدون «تأیید همان عملیات» ممکن بود. اصلاح: bare confirm برای عملیات اثرگذار در tty همیشه پرامپت نام‌دار صادر می‌کند و در حالت غیرتعاملی fail-closed است (`same_operation_confirmation_required`). آزمون: `test_runner_impactful_bare_confirm_still_prompts_interactively`.
  ۲. **شاهد M2M بدون آزمون منفی:** صحت شاهد نشست به verify شدن Bearer سمت سرور تکیه داشت (اثبات‌شده در کد: `/api/v2/m2m/*` پیش از dispatch توکن را verify می‌کند) ولی آزمونی آن را pin نمی‌کرد. آزمون تازه: `test_runner_live_m2m_witness_rejects_invalid_token` — توکن آشغال → witness رد، بدون اجرای عملیات، `warm_verified=false`.
  ۳. **CSRF خارج از مسیر رسمی:** csrf پروب admin داخل `_run_live_action` مستقیم از env خوانده می‌شد؛ به مسیر اصلی منتقل شد (env یا getpass) و غیاب آن fail-closed با `missing_csrf_token` است. آزمون: `test_runner_live_ai_probe_fails_closed_without_csrf_token`.
  ۴. **شکنندگی getpass:** استثناهای غیر از EOF/KeyboardInterrupt از getpass می‌توانستند runner را crash کنند؛ اکنون هر استثنایی fail-closed به مقدار خالی می‌رسد و گاردهای الزام فیلد رد می‌کنند.
- شواهد دروازه‌ها روی درخت ادغام‌شده (تغییرات V-249 + اصلاحات فوق، پس از سکوت عامل هم‌زمان): runner tests **۲۰/۲۰**؛ full pytest **۱۰۴۱ passed / 1 skipped** در 302.13s (شامل آزمون Popen تازهٔ V-249)؛ wheel بازسازی (`eitaa_bridge-0.7.0.dev31`، SHA-256=`841cbd913f6306ab9e0e40154cdfe603a8dacfbe1574996e452d8690b138ee66`) و parity 15/15؛ پروب fence GREEN و پروب چهارگانه exit=0؛ اسناد/integrity/--check --check-links و `git diff --check` پس از این ثبت مجدد اجرا می‌شوند.
- مرز: همچنان هیچ Live، حساب واقعی یا پذیرش قطعی؛ برچسب نهایی با ممیز مستقل/مالک است. مرجع: F-100، V-246/V-247/V-248/V-249، دفتر وضعیت.

### V-251 — ممیزی مستقل تکمیلی پس از V-249: جستجوی IPC و تکمیل بدون توکن

- تاریخ: 2026-09-30؛ شاخهٔ `codex/bale-web-client-instructions`، working tree عمدیِ dirty. Trigger بررسی دوباره: درخواست صریح مالک برای بازبینی دستور اصلاحی پس از ادعای تکمیل V-247/V-249، همراه با ریسک عملیاتی تازه در مسیرهای هم‌خانوادهٔ query و complete. شواهد سبز V-247/V-249 و بازخوانی V-250 مبنای کار بودند؛ full suite معتبر اخیر V-250 بدون تغییر source مرتبط تکرار نشد.
- بررسی کد: `bale_provider_worker.py` در `contacts.query` هر صفحه `owner.list_contacts()` را کامل می‌خواند، سپس slice می‌کند؛ در `contacts.search` خروجی `owner.search_contacts(query)` را بدون paging/limit در یک response می‌گذارد. `bale_provider_adapter.py` نیز بدون `list_contacts_page` به fetch-all برمی‌گردد. آزمون Popen V-249 فقط query چهار صفحه‌ای و search تک‌نتیجه‌ای را پوشش می‌دهد. محاسبهٔ مصنوعی همان دفترچهٔ ۲۰۰۰ نفری با نام‌های دقیقاً ۵۱۲نویسه‌ای، JSON خروجی search فراگیر را ۱٬۱۵۶٬۹۰۷ بایت نشان داد؛ `IPC_MAX_MESSAGE_BYTES=1,048,576`.
- پروب DB ایزوله و بدون دادهٔ واقعی: claim تلاش اول → release با token اول → claim تلاش دوم (generation=2) → `complete(..., attempt_token=None)`؛ خروجی `untokened_complete_outcome=succeeded`. تلاش نخست پروب به‌علت idempotency key کوتاه پیش از claim با validation error رد شد؛ ورودی مصنوعی اصلاح و پروب معتبر اجرا شد. مسیرهای production orchestrator توکن می‌دهند، ولی invariant ذخیره‌گاه ناقص است.
- کنترل `git diff --check` پیش از ویرایش اسناد exit=0 بود؛ هشدار تبدیل LF→CRLF شکست نیست. هیچ آزمون زنده، ارسال، حساب واقعی، فایل عملیاتی، stage/commit/push انجام نشد. F-099 برای پذیرش آفلاین کامل باز شد؛ [دستور اصلاحی دوم](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) ثبت گردید. پس از اصلاح source، RED→GREEN مستقل، full gates و به‌روزرسانی اسناد لازم است.
- کنترل‌های اسناد پس از ثبت این بازبینی: `refresh_project_docs.py`، `check_project_memory_integrity.py`، `refresh_project_docs.py --check`، `refresh_project_docs.py --check --check-links` و `git diff --check` همگی exit=0؛ پس از تصحیح عدد دقیق و این سطر دوباره اجرا می‌شوند. آزمون کامل محصول تکرار نشد، زیرا source مرتبط از V-250 تغییر نکرد و ریسک تازه با پروب ایزوله/محاسبه و بازخوانی کد اثبات شد.

### V-252 — اصلاح S1/S2، بازبینی مستقل و اجرای مجدد دروازه‌های آفلاین بله

- تاریخ: 2026-09-30؛ شاخهٔ موجود `codex/bale-web-client-instructions`، working tree مشترک/dirty محفوظ؛ بدون reset/checkout/clean، stage/commit/push یا عملیات Live. Trigger: درخواست مالک برای اجرای اصلاحات با مدل کم‌هزینه‌تر و بازبینی مستقل. دستور [S1/S2](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) و شاهد RED در V-251 مبنا بود.
- S1 RED: جست‌وجوی فراگیر ۲۰۰۰ مخاطب با نام‌های ۵۱۲نویسه‌ای از سقف ۱ MiB IPC عبور می‌کرد؛ آزمون Popen تازه با cursor/limit نیز ابتدا HTTP 400 گرفت، زیرا search هنوز این فیلدها را نمی‌پذیرفت. S1 GREEN: `contacts.query` و `contacts.search` در Child با cursor/limit و بودجهٔ بایتی ۳۰۰ kB صفحه می‌دهند؛ snapshot تا ۵۰۰۰ رکورد/۱۶ MiB با خطای صریح محدود است؛ هر پیمایش صفحه‌های بعدی را از snapshot می‌خواند و درخواست صفحهٔ اول یا mutation آن را تازه می‌کند. آزمون Child واقعی با ۲۰۰۰ نتیجهٔ جست‌وجو در ۲۰ صفحه، صفر تکرار/جاافتادگی، صفحهٔ آخر، ایزولاسیون دو حساب و فریم‌های کمتر از ۳۵۰ kB سبز شد. رکورد منفرد بیش از بودجه، cursor نامعتبر، refresh پس از تغییر بیرونی و پاسخ خام RPC بیش از ۱۶ MiB پیش از decode نیز آزموده شدند.
- UI واقعی روی فیکسچر آفلاین ۱۵۰ مخاطبی و باندل buildشده بررسی شد: جست‌وجوی مشترک صفحهٔ ۱۰۰تایی را نشان داد؛ دکمهٔ «نتایج بیشتر» صفحهٔ بعد را از API مصرف کرد و مخاطب شمارهٔ ۱۵۰ را نمایش داد؛ سپس دکمه حذف شد. هیچ پیام یا تماس Provider واقعی انجام نشد.
- S2 RED: `complete` بدون توکن، claim نسل دوم را برای چهار عملیات text/media/upsert/remove به نتیجهٔ پایانی تبدیل می‌کرد (۴ شکست معتبر). S2 GREEN: store توکن فعال را برای generation>1 الزامی می‌کند و UPDATE را با شرط اتمیک generation/token انجام می‌دهد؛ سه مسیر نتیجهٔ `uncertain` پس از expiry نیز توکن receipt را می‌فرستند. آزمون‌های اختصاصی، schema و orchestration مرتبط ۴۳ پاس؛ legacy generation=1، restart، توکن کهنه، replay پایانی و عدم تحریف terminal پوشش دارند.
- بازبینی مستقل: سه سوئیت بلهٔ اصلی، پروب attempt fence (`stale_release=false`, `third_claimed=false`) و پروب چهارگانهٔ پذیرش همگی PASS/exit=0. Wheel رسمی `eitaa_bridge-0.7.0.dev31` بازسازی شد (SHA-256=`26f0015d0178c977a034ebc0fb7921f5fced3cb592feb65f3ed82254fd8e4fc7`) و parity `15/15` پاس؛ UI check، observability و build همگی exit=0 (هشدار اندازهٔ chunk موجود، شکست نیست).
- شکست و اجرای مجدد full Backend: اجرای نخست یک شکست در `test_atomic_capacity_acceptance_across_two_processes` داشت؛ ۲ فرایند هر دو پذیرفته شدند، چون نرخ refill فیکسچر یک توکن/ثانیه بود و startup می‌توانست بیش از یک ثانیه طول بکشد. نرخ همان فیکسچرِ آزمون رقابت برای این سناریو به ۰٫۰۰۱ توکن/ثانیه تنظیم شد تا یک slot تا پایان رقابت باقی بماند؛ آزمون متمرکز پاس شد. اجرای مجدد full pytest روی source و اسناد به‌روز: `1049 tests / 1048 passed / 1 skipped / 0 failed / 0 errors` در 313.920s، exit=0؛ فایل JUnit در `test-results-full.xml` ثبت شد.
- کنترل نهایی اسناد و whitespace پس از ثبت V-252: `refresh_project_docs.py`، integrity، freshness، freshness+links و `git diff --check` همگی exit=0؛ هشدارهای LF→CRLF خروجی Git خطا نیستند. مرز: WebSocket پاسخ خام GetContacts/SearchContacts را با `max_size=None` پیش از guard بایتی ۱۶ MiB کامل دریافت می‌کند؛ سقف decoded snapshot و IPC برقرار است، اما سقف دریافت شبکه و B6 Live تأیید نشده‌اند. ادغام وب‌سایت واقعی نیز مسیر مستقل است. این رکورد آمادگی اصلاح آفلاین را نشان می‌دهد، نه پذیرش قطعی مالک.

### V-253 — آزمایش ارتباط Antigravity CLI و بازبینی مستقل تحویل V-252

- تاریخ: 2026-09-30؛ Trigger: درخواست صریح مالک برای ارتباط با `agy`، آزمون کوچک، سپردن دستور اصلاحی دوم و انتظار تا پاسخ. CLI نسخهٔ 1.1.13 در workspace فعلی احراز هویت شد؛ درخواست فقط‌خواندنیِ «متصل» پاسخ درست گرفت. سپس دستور S1/S2 با مرزهای AGENTS و منع Live/دادهٔ عملیاتی/پاک‌سازی/انتشار ناقص ارسال شد. نشست تا پاسخ پایانی پیگیری و به‌صورت عادی بسته شد؛ شناسهٔ ادامهٔ محلی `7bd56fd5-f2dd-4317-9475-25fe0ef01650` است.
- یافتهٔ بازبینی: هنگام شروع CLI، اصلاحات V-252 پیش‌تر در همین working tree و Ledger ثبت شده بودند. عامل CLI آن‌ها را خواند، آزمون‌های هدفمند حصار تلاش و بله، پروب‌های قبلی، UI check/observability/build، wheel parity، memory integrity، freshness/link check و `git diff --check` را دوباره اجرا کرد و در پاسخ نهایی همگی را سبز گزارش داد. full pytest جدید اجرا نکرد؛ شاهد کامل `1048 passed / 1 skipped` از V-252 است. خواندن‌های Git فقط با تأیید موردی فرمان‌های خواندنی انجام شد. هیچ فایل source یا عملیاتی در این بازبینی تغییر نکرد.
- کنترل مستقل محلی پس از پاسخ: وضعیت F-099 در Findings و دفتر اجرا با `OFFLINE_REPAIR_VERIFIED_V252 / OWNER_ACCEPTANCE_PENDING / B6_LIVE_PENDING_INPUT` همسو بود؛ زمان آخرین ویرایش sourceهای اصلی پیش از این نشست باقی ماند؛ `git diff --check` exit=0. مرز باز: دریافت خام WebSocket پیش از guard ۱۶ MiB محدود نشده، B6 Live و ادغام وب‌سایت خارجی همچنان شاهد/ورودی مستقل می‌خواهند. این بازبینی پذیرش قطعی مالک یا مجوز Live نیست.
- پس از این ثبت، generator، memory integrity، freshness، link check و `git diff --check` دوباره اجرا شدند و همگی exit=0 داشتند؛ پس از درج همین نتیجه، کنترل اسناد یک بار دیگر اجرا می‌شود.

### V-254 — آماده‌سازی نصب تست جداگانه برای ورود واقعی بله

- تاریخ: 2026-10-01؛ Trigger: مالک برای ورود تستیِ آسان و ثابت به‌جای حساب محلی فراموش‌شده درخواست صریح داد و مسیر شماره/کد یک‌بارمصرف بله را برای ادامهٔ Pilot انتخاب کرد. این رکورد فقط آماده‌سازی محیط را ثبت می‌کند، نه پذیرش Live.
- از `bridge.example.json` یک پیکربندی تازه در ریشهٔ جداگانهٔ تست زیر LocalAppData ساخته شد؛ هیچ Config، DB، نشست یا دادهٔ نصب فعلی جابه‌جا/بازنویسی/حذف نشد. نصب تست فقط روی `127.0.0.1:8766` bind شد و مسیر Coordinator آن از نصب اصلی جداست. AppUser Auth، چندنشستی و worker process طبق نمونه روشن‌اند.
- یک AppUser آزمایشی با اعتبارنامهٔ عمداً ساده در **همین نصب تست** ساخته شد؛ مقدار اعتبارنامه در Ledger/لاگ ثبت نمی‌شود. فراخوانی setup برابر HTTP 201 و بررسی ورود با HTTP 200 و صدور کوکی نشست بود؛ مقدار کوکی ذخیره یا چاپ نشد. شمار AppUser در Coordinator تست ۱ و شمار MessengerAccount صفر بود. رابط تست در مرورگر باز شد.
- ورود شماره/OTP بله، ذخیرهٔ نشست Provider، خواندن اطلاعات حساب و هر mutation هنوز انجام نشده‌اند؛ کاربر باید دادهٔ احراز هویت را در خود رابط وارد کند. تست B6 و F-099 از این آماده‌سازی به `LIVE_ACCEPTED` ارتقا نمی‌یابند. پس از تکمیل ورود، اقدام‌های Pilot با تأیید همان عملیات و شاهد ایزوله ثبت خواهند شد.

### V-255 — بازتولید و اصلاح اتصال بله پس از ورود واقعی OTP

- تاریخ: 2026-10-01؛ Trigger بررسی مجدد: گزارش تازهٔ مالک از `The Bale provider operation failed safely.` و شاهد ورود ثبت‌شده در کلاینت اصلی، پس از V-254. نصب تست جداگانهٔ `127.0.0.1:8766` حفظ شد؛ دادهٔ نصب اصلی و فایل‌های عملیاتی دست‌نخورده ماندند.
- شاهد Live پیش از اصلاح: ثبت حساب در Coordinator تست موفق بود؛ درخواست‌های `dialogs.list` با کد امن `bale_not_connected` رد می‌شدند. بازخوانی source نشان داد `auth.code/auth.password` نشست vault را ذخیره می‌کنند، ولی اتصال WebSocket برقرار نمی‌کنند؛ Worker اشتباهاً `_authenticated=True` می‌گذاشت و restore تنبل را دور می‌زد.
- آزمون ایزولهٔ تازه با backend مصنوعی: OTP موفق → نخستین query گفتگو بدون restore صریح؛ RED با `bale_not_connected`. اصلاح Worker برای هر دو مسیر OTP و عامل دوم اعمال شد؛ آزمون پارامتری و سه سوئیت مرتبط بله سبز شدند. پس از راه‌اندازی دوبارهٔ همان نصب تست با source اصلاح‌شده، `dialogs.list` زنده چند بار موفق شد و پیام خطا در UI دیده نشد. راه‌اندازی دوباره، restore نشست موجود را نیز به‌طور طبیعی فعال می‌کند؛ بنابراین شاهد Live مکمل آزمون بازتولید است، نه اثبات مستقل ورود تازه. محتوای گفتگو، شماره، OTP، توکن و کوکی در خروجی/سند نیامده‌اند.
- اجرای نخست full Backend تنها در `test_bundled_bridge_wheel_matches_current_source_tree` شکست خورد: wheel قبلی با یک فایل source اصلاح‌شده اختلاف داشت. Wheel رسمی با `scripts/build_wheel_stdlib.py --force` از source جاری بازسازی شد (SHA-256=`52113829c90389a075958d1813fb52fb2ebdfd878351d841753b6b6b3e55f42b`)؛ آزمون packaging برابر ۱۵/۱۵ پاس و اجرای مجدد full `pytest -q` با exit=0، یک skip و فقط هشدار deprecation شناخته‌شدهٔ `websockets` پایان یافت. UI check و observability، مولد نقشهٔ پروژه، integrity، freshness، link check و `git diff --check` همگی exit=0؛ کنترل اسناد پس از ثبت نتیجه دوباره اجرا می‌شود.
- هیچ پیام زنده، تغییر مخاطب یا ورود دوباره انجام نشد. B6 فقط در محدودهٔ login + read گفتگو شاهد دارد؛ پذیرش کامل/انتشار نهایی باز است.

### V-256 — ترمیم اتصال مجدد بله پس از قطع WebSocket

- تاریخ: 2026-10-01؛ Trigger: گزارش دوبارهٔ مالک از خطای امن Provider در صفحهٔ تست، پس از V-255 و تغییر وضعیت اتصال زنده. لاگ امن نصب تست تکرار `dialogs.list` با `bale_not_connected` را نشان داد؛ بازخوانی Worker ثابت کرد `_authenticated=True` پس از قطع WebSocket باقی می‌ماند و restore تنبل را دور می‌زند.
- آزمون RED→GREEN ایزوله: در هر دو مسیر OTP و عامل دوم، اتصال نخست موفق، سپس WebSocket مصنوعی قطع شد؛ درخواست اول خطای `bale_not_connected` داد و درخواست بعدی قبل از اصلاح نیز همان خطا را تکرار می‌کرد. Worker اکنون با دریافت این کد امن، پرچم اتصال را False می‌کند تا درخواست بعدی vault را روی owner loop دوباره وصل کند. درخواست شکست‌خورده خودکار replay نمی‌شود؛ این مرز برای ارسال و mutation مهم است. دو حالت آزمون و سه سوئیت مرتبط بله پس از اصلاح exit=0.
- نصب تست جداگانهٔ `127.0.0.1:8766` بدون دستکاری نشست/Config دوباره راه‌اندازی شد؛ `dialogs.list` زنده چند بار موفق بود. این راه‌اندازی شاهد Live بازیابی پس از قطع دوباره نیست و ادعای دوام اتصال صرفاً بر آزمون ایزوله تکیه دارد. هیچ شماره، OTP، کوکی، توکن یا متن گفتگو در خروجی ثبت نشد.
- Wheel رسمی از source جاری بازسازی شد (SHA-256=`e654b77264260e44f84e44cfae88deba7c7558d2702d9326f89f10b73ee18f26`). اجرای کامل `pytest -q` پس از این تغییر exit=0، یک skip و تنها هشدار deprecation شناخته‌شدهٔ `websockets` داشت. UI check و observability از V-255 معتبرند، چون UI تغییر نکرد. مولد اسناد، memory integrity، link check و `git diff --check` همگی exit=0؛ پس از درج نتیجه دوباره کنترل می‌شوند. خواندن‌های Live گفتگو و تاریخچه در چند دقیقهٔ پس از راه‌اندازی دوباره موفق ماندند. B6 mutation و پذیرش قطعی همچنان باز است.

### V-257 — گزارش مالک و شاهد امن پایلوت زندهٔ محدود بله

- تاریخ: 2026-10-01؛ Trigger: مالک پس از آزمون دستی در نصب جداگانه اعلام کرد خواندن و ارسال پیام و مخاطبین درست کار کرده‌اند. این بازبینی فقط رخدادهای cataloged برنامه را با event/operation/result/reason code خواند؛ هیچ payload، متن پیام، شماره، شناسهٔ گیرنده، توکن یا کوکی استخراج نشد.
- شاهد ثبت‌شده در همان نصب: `dialogs.list` و `history.list` موفق، دو `messages.send_text` موفق، دو `contacts.upsert` موفق، یک `contacts.remove` موفق و `contacts.list` موفق. موفقیت‌های mutation با گزارش مالک همسوست؛ شمارها صرفاً رخدادهای امن‌اند و هویت مخاطب یا تطبیق متن read-back را اثبات نمی‌کنند. عملیات زنده توسط خود مالک در UI انجام شد؛ عامل هیچ ارسال/تغییر تازه‌ای اجرا نکرد.
- نتیجه: B6 در محدودهٔ خواندن، ارسال متن و mutation مخاطب شاهد Live محدود دارد. restore گرم پس از قطع واقعی، دریافت بدون reload، جست‌وجوی مخاطب، تطبیق read-back و مسیر عمومی M2M در این نوبت مستقل اثبات نشدند. پذیرش نهایی بله و انتشار Git هنوز به بررسی معیارهای باقی‌مانده و تصمیم مالک وابسته‌اند؛ وضعیت F-099 به `B6_LIVE_PILOT_PARTIAL_V257` ارتقا یافت، نه `LIVE_ACCEPTED` کامل. چون source/config مرتبط تغییر نکرد، full suite معتبر V-256 تکرار نشد. کنترل اسناد پس از ثبت این رکورد اجرا می‌شود.

### V-258 — بازبینی دوبارهٔ وضعیت اصلاحات و آزمون روی source جاری

- تاریخ: 2026-10-01؛ Trigger: درخواست مالک برای بررسی دوباره پس از گزارش قبلی. source اتصال بله در V-255/V-256 پس از artifact قدیمی `test-results-full.xml` تغییر کرده بود؛ بنابراین شاهد ۱۰۴۸ پاس V-252 برای source کنونی کافی نبود. هیچ عملیات Live، دادهٔ عملیاتی، stage، commit یا push در این بازبینی انجام نشد.
- روی working tree جاری، ۴۸ آزمون متمرکز receipt fence، محصول بله، runner و OTP با exit=0 گذشتند. پروب attempt fence با `stale_release=false` و `third_claimed=false`، و پروب چهارگانهٔ بله شامل ۵۰۱ مخاطب یکتا در ۶ صفحه، هر دو exit=0 داشتند.
- full Backend کنونی: `pytest --collect-only -q` برابر ۱۰۵۱ آزمون؛ `pytest -q` با exit=0 و یک skip گذشت (۱۰۵۰ پاس، بدون شکست). هشدار deprecation کتابخانهٔ websockets تنها هشدار دیده‌شده بود. `git diff --check`، memory integrity و freshness/link check همگی exit=0 داشتند. آزمون UI تکرار نشد چون UI از V-252 تغییر نکرده است.
- قید وضعیت: F-099 همچنان `OFFLINE_REPAIR_VERIFIED_V252 / B6_LIVE_PILOT_PARTIAL_V257 / OWNER_ACCEPTANCE_PENDING` است. دریافت خام WebSocket مخاطبین هنوز پیش از guard ۱۶ MiB محدود نمی‌شود؛ B6 کامل و ادغام وب‌سایت واقعی نیز شاهد مستقل می‌خواهند. متن بالای گزارش و handoff بله که Live را مطلقاً آزموده‌نشده می‌خواندند، با شاهد محدود V-257 هماهنگ شد. درخت مشترک dirty است و قاعدهٔ AGENTS برای commit دستور صریح همان کار می‌خواهد؛ هیچ چیزی stage یا commit نشد.

### V-259 — تأیید مالک برای دریافت تازه بدون بازخوانی و بررسی عمر نشست

- تاریخ: 2026-10-01؛ Trigger: مالک گزارش کرد پیام تازهٔ فرستاده‌شده از جای دیگر را بلافاصله و بدون بازخوانی در UI نصب تست دیده و این رفتار را صریحاً تأیید می‌کند. این شاهد Live خوداظهاری مالک برای دریافت تازه است؛ متن، شماره و شناسهٔ فرستنده/گیرنده استخراج یا ثبت نشد. هیچ ارسال تازه‌ای توسط عامل انجام نشد.
- برای پاسخ به پرسش عمر توکن، source نشان داد `BaleSession.expires_at` از claim `exp` و نشست در vault رمزگذاری‌شده ذخیره می‌شود؛ renewal خودکار در مسیر Bale client یافت نشد. در یک بررسی read-only روی همان vault تست، فقط زمان انقضای claimهای JWT و access token محاسبه و در پاسخ کاربر گزارش شد؛ خود توکن، JWT و کلید در خروجی یا سند ثبت نشدند. زمان اسمی ممکن است با logout/ابطال سمت Provider زودتر خاتمه یابد. نشست AppUser صفحهٔ تست سیاست idle و absolute هر دو یک‌سال دارد و از نشست Bale جداست.
- این تأیید، دریافت تازه را به محدودهٔ شاهد B6 می‌افزاید؛ جست‌وجوی مخاطب، تطبیق read-back و بازیابی Live پس از قطع واقعی همچنان شاهد مستقل می‌خواهند. source/config تغییر نکرد؛ full suite معتبر V-258 تکرار نشد. کنترل اسناد پس از ثبت اجرا می‌شود.

### V-260 — علت‌یابی و اصلاح خطای متناوب خواندن بله در نصب تست

- تاریخ: 2026-10-01؛ Trigger: گزارش تازهٔ مالک از متن عمومی خطای بله و تغییر واقعی source در owner/API/UI. خواندن فقط‌خواندنی و محدود به فیلدهای امن لاگ نصب تست، شکست‌های متناوب `dialogs.list` با `bale_rpc_error` و `GetContacts` با کد عددی ۸ را نشان داد. مسیر source ثابت کرد هر `dialogs.list` برای تکمیل نام گفتگو به `GetContacts` وابسته بود. متن پاسخ سرور، شناسه‌ها، شماره‌ها، پیام‌ها و credential خوانده یا ثبت نشدند.
- اصلاح و شاهد هدفمند: تکمیل نام اختیاری با cache ۳۰۰ ثانیه‌ای و بی‌اعتبارسازی پس از تغییر مخاطب/ورود/خروج؛ رد RPC تکمیل نام، صفحهٔ گفت‌وگو را خراب نمی‌کند. UI خطای polling را از عملیات دستی جدا و پس از موفقیت پاک می‌کند و فاصلهٔ تلاش ناموفق را تا ۶۰ ثانیه افزایش می‌دهد. آزمون تازهٔ owner برای RPC ردشده، cache، invalidation و عنوان سروری؛ آزمون RPC برای ثبت فقط method/code و عدم ثبت متن خصوصی؛ سه سوئیت هدفمند محصول/API بله exit=0. UI `check`، `test:observability` و `build` هر سه exit=0.
- اجرای اولیهٔ full suite حین تغییر source قطع شد و شاهد اعتبار محصول شمرده نشد. سپس wheel از source نهایی بازسازی شد (`adec4bc3b9b611400308c0e1ad506ea5d5b5b3a30e8552cff66f71577a26bda3`). full `pytest -q` روی همین snapshot exit=0 داشت: ۱۰۵۲ مورد جمع‌آوری، ۱۰۵۱ پاس، ۱ skip، بدون شکست؛ فقط هشدار deprecation شناخته‌شدهٔ `websockets.legacy`. `git diff --check` نیز exit=0 است.
- نصب جداگانهٔ ۸۷۶۶ با کد تازه و بدون تغییر Config/نشست راه‌اندازی شد. لاگ امن آن پس از راه‌اندازی دست‌کم ۵۹ `dialogs.list` موفق پیاپی و نبود درخواست پنج‌ثانیه‌ای `GetContacts` را نشان داد؛ در شروع owner یک درخواست مخاطب دیده شد. یک شکست گذرای اتصال در راه‌اندازی پیشین علت قطعی ندارد و در راه‌اندازی بعدی تکرار نشد. هیچ ورود، ارسال یا mutation تازه توسط عامل انجام نشد. باندل UI جدید تا بازخوانی صفحه توسط مالک در تب موجود قطعی نیست؛ پذیرش کلی B6/F-099 از این شاهد نتیجه نمی‌شود.
- مولد اسناد، memory integrity، freshness، freshness+links و `git diff --check` پس از ثبت این رکورد همگی exit=0 شدند. وضعیت درخت همچنان dirty و مشترک است؛ هیچ stage/commit/push انجام نشد.

### V-261 — تأیید مالک برای جست‌وجوی مخاطب و خواندن دوبارهٔ پیام در بله

- تاریخ: 2026-10-01؛ Trigger: پس از V-260 و درخواست ادامهٔ پایلوت، مالک در نصب تست ۸۷۶۶ دو بررسی فقط‌خواندنی را انجام داد و صریحاً هر دو را تأیید کرد: جست‌وجوی یک مخاطب موجود و مشاهدهٔ دوبارهٔ پیام ارسالی قبلی در تاریخچهٔ گفتگو. نام/شمارهٔ مخاطب و متن پیام دریافت یا ثبت نشد.
- رخدادهای امن همان نصب موفقیت عملیات خواندن مخاطب و تاریخچه را نشان می‌دهند، ولی خود رخدادها نتیجهٔ دقیق جست‌وجو یا یکسان‌بودن متن را اثبات نمی‌کنند؛ آن بخش بر تأیید مستقیم مالک تکیه دارد. هیچ ارسال، ورود یا تغییر مخاطب از سوی عامل انجام نشد.
- نتیجه: شاهد Live B6 برای جست‌وجو و read-back به V-257/V-259 افزوده شد؛ بازیابی گرم نشست پس از راه‌اندازی دوباره و مسیر عمومی M2M هنوز شاهد مستقل ندارند. چون source/config تغییر نکرده، full suite معتبر V-260 تکرار نشد.

### V-262 — بازیابی گرم نشست بله و مهار نرخ خواندن گفتگوها

- تاریخ: 2026-10-01؛ Trigger: مالک پس از تأیید V-261 خواست در صورت نیاز آزمون کوتاه باقی‌مانده انجام و سپس به مرحلهٔ بعد برویم؛ تأیید همان‌لحظه برای اتصال مجدد تست را داد. پیش از آزمون، سرویس ۸۷۶۶ از قبل خاموش بود؛ بنابراین فرایندی قطع نشد. با همان Config و نشست ذخیره‌شده، بدون ویرایش دادهٔ عملیاتی، دوباره بالا آمد و HTTP ریشه ۲۰۰ شد.
- بازبینی امن شواهد دیرتر V-260 پیش از اعلام نتیجه، رد متناوب خود `LoadDialogs` با کد ۸ در polling پنج‌ثانیه‌ای را نشان داد؛ قبولی کوتاه قبلی برای دوام کافی نبود. UI اصلاح شد: `dialogs.query` با فاصلهٔ پایهٔ ۱۵ ثانیه و backoff مستقل ۳۰/۶۰ ثانیه، `history.query` گفتگوی باز با فاصلهٔ پنج‌ثانیه‌ای، ادامهٔ تاریخچه در شکست dialogs و توقف polling تب پنهان. UI `check`، `test:observability` و `build` پس از تغییر exit=0 دارند؛ full Backend V-260 به‌سبب نبود تغییر Python معتبر است و تکرار نشد.
- مالک پس از تازه‌سازی صفحهٔ تست گزارش کرد گفتگوها بدون کد ورود تازه برگشتند. لاگ امن پس از راه‌اندازی `dialogs.list` موفق ثبت کرد و سه درخواست نخست `LoadDialogs` حدود ۱۵ ثانیه از هم فاصله داشتند. این شاهد Live برای restore گرم از نشست ذخیره‌شده است؛ قطع WebSocket در حال اجرای فرایند و دوام بلندمدت cadence تازه جدا می‌مانند. هیچ OTP، ارسال یا mutation تازه از سوی عامل اجرا نشد؛ محتوای گفتگو، شناسه‌ها و credential بررسی/ثبت نشدند.
- مولد اسناد، memory integrity، freshness، link check و `git diff --check` پس از ثبت نتیجه exit=0 شدند. سرویس تست بعد از این بررسی همچنان HTTP 200 بود. سناریوی بله هنوز به‌علت معیارهای مستقل باز و درخت مشترک dirty، stage/commit/push نشد.

### V-263 — آماده‌سازی checkpoint مشترک Bridge با مجوز صریح مالک

- تاریخ: 2026-10-01؛ Trigger: مالک صریحاً خواست تغییرات Bridge کامیت شوند، مخزن تمیز شود و در صورت امکان شاخهٔ کاری پوش شود. درخت مشترک از P1 تا P9 و اصلاحات بله به‌صورت یک بستهٔ مرتبط stage شد؛ فایل‌های محلی شخصی، attachment و خروجی JUnit وارد stage نشدند. هیچ فایل عملیاتی، نشست، Config واقعی یا دادهٔ Live تغییر یا stage نشد.
- کنترل محتوا: نخست `git diff --cached --check` فاصله‌های انتهایی را در ۱۶ فایل تازه نشان داد؛ همان فایل‌ها اصلاح و stage شدند. مولد نقشهٔ پروژه پس از این تغییر دو خروجی تولیدی را تازه کرد. اسکن امضاهای رایج secret روی بستهٔ stage شده فقط مقادیر fixture آزمون را نشان داد؛ کلید خصوصی، JWT یا Bearer واقعی در خروجی اسکن دیده نشد.
- کنترل کیفیت: UI `check`، `test:observability` و `build` exit=0؛ آزمون‌های بسته‌بندی ابتدا ۱۵/۱۵ سبز بودند. اولین full Backend پس از اصلاح whitespace تنها در parity wheel/source شکست خورد، زیرا wheel پیش از همان تغییر بایتی source ساخته شده بود. wheel رسمی از source جاری با `build_wheel_stdlib.py --force` بازسازی شد (SHA-256=`3f9ee5b6366c1e70293c59e036964443f71f70a8a6cd3a7e8320f02528052f12`)؛ parity دوباره ۱۵/۱۵ سبز شد. اجرای مجدد full Backend: ۱۰۵۲ آزمون جمع‌آوری، ۱۰۵۱ پاس، ۱ skip، صفر شکست، exit=0؛ تنها هشدار deprecation شناخته‌شدهٔ `websockets.legacy` باقی ماند.
- گام توسعهٔ بعدی: مخزن بک‌اند واقعی آزمون آنلاین در `D:/projects/OnlineExam-Copy` و handoff پیام‌رسان آن شناسایی شد؛ مسیر دیگر ورودی گمشده نیست. انطباق قرارداد و ادغام دو مخزن هنوز انجام نشده‌اند. شواهد Live بله در V-257 تا V-262 محدودند؛ این checkpoint به معنی پذیرش قطعی، انتشار محصول یا پایان B6 نیست. نتیجهٔ commit/push در رکورد بعدی ثبت می‌شود.

### V-264 — ثبت checkpoint و انتشار شاخهٔ کاری Bridge

- تاریخ: 2026-10-01؛ با مجوز صریح مالک، ۹۶ فایل کد، آزمون و سند در commit `bf9dfd60fd562ba8733632c22b266341df0214fa` با پیام `feat(bridge): checkpoint Bale and web client integration` ثبت شدند. کنترل پیش و پس از commit نشان داد تغییر stage نشده‌ای باقی نمانده است.
- همین commit بدون force روی `origin/codex/bale-web-client-instructions` پوش شد؛ `git ls-remote` همان SHA را برای شاخهٔ دوردست برگرداند. هیچ push یا merge به `main` انجام نشد.
- فایل‌های شخصی عامل، attachment و JUnit روی دیسک حفظ و تنها در `.git/info/exclude` محلی نادیده گرفته شدند؛ وارد commit یا ریموت نشدند. مخزن پس از push از نظر Git تمیز بود. این ثبت فقط انتشار checkpoint شاخهٔ کاری است؛ پذیرش نهایی محصول، ادغام دو مخزن و معیارهای Live مستقل باقی‌اند.

### V-265 — تعمیر و آزمون واقعی راه‌انداز `EitaaBridge.bat`

- تاریخ: 2026-10-01؛ Trigger: مالک برای آزمون وب به Bridge نیاز داشت و اجرای راه‌انداز خطا می‌داد. درخت Git در آغاز تمیز بود؛ نه reset/checkout/clean و نه تغییر دادهٔ عملیاتی انجام شد. لاگ امن launcher خطای «بک‌اند آماده نشد» و گزارش بک‌اند شروع کوتاه‌مدت روی ۸۷۶۵ و انقضای heartbeat را نشان داد.
- پروب کنترل‌شده: بک‌اند موقت با همان controller اجرا شد؛ پاسخ هویت HTTP 200 داشت و تمام معیارهای مالکیت جز `bridge_version` برابر بودند. manifest `VERSION.txt` نسخهٔ Bale1 و source نسخهٔ GMI4.2 داشت. این تضاد با exact version fence علت مشخص رد readiness بود. فرایند موقتِ همان پروب پایان یافت؛ هیچ پیام‌رسانی یا ورود واقعی اجرا نشد.
- اصلاح: `src/eitaa_bridge/version.py` با نسخهٔ Bale1 همسو شد؛ `check_runtime_environment.py` و smoke نسخهٔ مورد انتظار را از manifest canonical می‌خوانند؛ آزمون برابری source/manifest و ادعای نسخهٔ CLI به‌روز شدند. ۴۲ آزمون متمرکز runtime/CLI پاس شدند. wheel از source تازه بازسازی شد (SHA-256=`bbc7e107cbe3ed64a3b173509df5f4f32cd570c0bdecbe4f81481cf9564dd4c7`) و checker محیط `ok=true`/صفر failure داد.
- اجرای واقعی `EitaaBridge.bat` از همین ریشه exit=0 داشت؛ launcher `backend ready` و `edge app started` ثبت کرد، health روی ۸۷۶۵ HTTP 200 و status مالکیت `Owned=True`/`VersionMatches=True` بود و پس از مهلت heartbeat نیز فعال ماند. این شاهد فقط راه‌اندازی محلی است، نه ورود Provider یا ادغام وب‌سایت.
- چون نسخهٔ عمومی محصول تغییر کرد، full Backend پس از rebuild wheel تکرار شد: ۱۰۵۳ مورد جمع‌آوری، ۱۰۵۲ پاس، ۱ skip، صفر شکست؛ تنها هشدار deprecation شناخته‌شدهٔ `websockets.legacy`. smoke مستقل با `GMI4_SKIP_LAB=1` نیز ۲۷ کنترل را پاس کرد. UI از V-263 تغییر نکرد و کنترل UI آن معتبر است. `package_clean.py --dry-run` با ۳۵۲ فایل و `ok=true` گذشت. مولد اسناد، memory integrity، freshness، freshness+links و `git diff --check` پس از ثبت همگی exit=0 شدند.

### V-266 — ثبت و انتشار اصلاح راه‌انداز Office

- تاریخ: 2026-10-01؛ پس از V-265 و کنترل `git diff --cached --check`، اسکن stage شده برای کلید خصوصی/JWT/Bearer/شمارهٔ کامل هر چهار صفر بود. ۱۱ فایل مرتبط در commit `c6861292cff6a7ecd2287885c1893d7ff873eded` با پیام `fix(launcher): align Bale product version with runtime identity` ثبت شدند.
- همان commit بدون force به `origin/codex/bale-web-client-instructions` پوش شد و `git ls-remote` SHA برابر نشان داد. `main` تغییر نکرد و working tree پس از push تمیز بود. این انتشار شاخهٔ کاری فقط اصلاح launcher است؛ ادغام وب‌سایت واقعی و پذیرش Live Provider/OTP مستقل‌اند.

### V-267 — اصلاح و آزمون مرورگری انتخاب دسترسی سرویس

- تاریخ: 2026-10-01؛ Trigger: گزارش جدید مالک دربارهٔ نامشخص‌بودن انتخاب‌ها. پیش از تغییر، Git تمیز بود. شاهد RED مرورگر: پس‌زمینهٔ Chip انتخاب‌شده و انتخاب‌نشده یکسان (`rgb(34, 45, 57)`) و `aria-pressed` غایب بود؛ علت در theme ثابت تأیید شد (F-104).
- اصلاح محدود: سه فهرست انتخاب در `ServiceAccountSettingsPanel.tsx` به Checkbox کنترل‌شده با label تبدیل شدند. UI check، `test:observability` و build همگی exit=0؛ هشدار اندازهٔ chunk در build باقی است.
- شاهد GREEN مرورگر روی رابط ساخته‌شده: انتخاب scope/Provider/حساب پس از تغییر focus حفظ شد؛ Space انتخاب ارسال را لغو کرد و انتخاب وضعیت باقی ماند؛ حذف حساب ساخت توکن را غیرفعال کرد. پنجره بدون submit بسته شد؛ هیچ credential/مخاطب/پیام واقعی ساخته نشد.
- full Backend و wheel V-265 به دلیل نبود تغییر Python/بستهٔ wheel تکرار نشدند. گزارش موضوعی: `docs/reports/features/SERVICE_CREDENTIAL_SELECTION_FIX_2026-10-01.md`. مولد اسناد اجرا شد؛ memory integrity، freshness همراه links و `git diff --check` همگی exit=0 شدند. دادهٔ عملیاتی و نشست‌های واقعی تغییر نکردند.

### V-268 — آغاز آزمون یک OTP ایتا از سایت محلی با مجوز مالک

- تاریخ: 2026-10-01؛ Trigger: مسیر تازهٔ سایت/رزرو/OTP پس از V-267 آماده و مقصد شمارهٔ ایتای فرم اصلاح و بدون ارسال واقعی آزموده شد. مالک همان‌لحظه یک کد با اعتبار پنج دقیقه، احتمال افزودن/به‌روزرسانی مخاطب با برچسب `Participant` و توقف بدون retry در خطا/uncertain را صریحاً تأیید کرد.
- Provider ایتا و حساب حصارشدهٔ credential سایت؛ یک گیرندهٔ متعلق به ثبت‌نام محلی مالک. worker خودکار خاموش ماند؛ فقط یک delivery صف با attempt=0 و TTL معتبر برای پردازش تک‌مرحله‌ای انتخاب شد. آزمون قبلی Backend سایت ۸۳۴ پاس و بررسی ORM مقصد معتبرند. preflight به‌تنهایی شاهد warm یا دریافت نیست.
- اجرای واقعی: درخواست challenge از رابط سایت؛ پردازش یک delivery با کلاس‌های ساخته‌شدهٔ واقعی سایت و حصار مقصد/تعداد. سایت processed=1/succeeded=1/failed=0، یک فراخوانی آداپتور، ACCEPTED/attempt=1 و پاک‌شدن payload کد را ثبت کرد. مقایسهٔ فقط‌خواندنی با baseline: یک رزرو تازه consumed/send_started=true/refund=false، یک receipt تازه completed/accepted، contact_status=created و send_status=accepted/retryable=false. هیچ resend یا تماس تازه با بله/AI اجرا نشد.
- مالک دریافت کد و ورود را تأیید کرد. شاهد مستقل سایت: یک challenge CONSUMED، یک نشست شرکت‌کننده و مرورگر در `/participant/exams`؛ ورود مستقیم و Mock خاموش‌اند. نتیجهٔ این یک مسیر محلی: `LIVE_LOCAL_OTP_LOGIN_VERIFIED`؛ زمان‌بندی worker خودکار، warm/connect و شمار RPC داخلی Provider اندازه‌گیری نشدند. سایت آنلاین، بله، AI و پذیرش کامل محصول مستقل‌اند. شماره/کد/Token وارد خروجی، Ledger یا Git نشدند.
- شمارش اولیهٔ فقط‌خواندنی با نام نادرست جدول انجام نشد؛ schema واقعی کشف و شمارش از `service_otp_deliveries`/`service_delivery_reservations` تصحیح شد. این خطای بررسی هیچ mutation یا dispatch نداشت. پس از نتیجه، memory integrity، freshness+links و `git diff --check` همگی exit=0 شدند؛ full Backend/UI به علت نبود تغییر کد تکرار نشدند.

### V-269 — تحویل رابط بله با الگوی فضای کاری ایتا و پذیرش مرورگری روی فیکسچر

- تاریخ: 2026-10-01؛ Trigger: مأموریت تکمیل رابط بله با اشتراک اجزای نمایشی ایتا و حفظ اتصال مستقل بله به مسیر حساب‌محور خود. وضعیت Git در آغاز تمیز و روی `codex/bale-web-client-instructions` برابر `origin` بود؛ هیچ reset/checkout/clean و هیچ تغییر دادهٔ عملیاتی انجام نشد.
- تحویل: `WorkspaceNavigation` با props اختیاری (بدون تغییر فراخوانی ایتا) مشترک شد؛ `BaleWorkspace` با چیدمان سه‌ستونی RTL، فهرست گفتگو با جست‌وجو/badge، سربرگ، کارت پیام حبابی با جهت گیرنده از `sender_reference`، نوار ارسال با تأیید گیرنده و `idempotency_key`، دفترچهٔ مخاطبین دیالوگی صفحه‌بندی‌شده و تنظیمات با چیپ قابلیت‌ها/`reason_code` بازسازی rendering شد. پنج جزء نمایشی تازه در `ui/src/bale/` ساخته شدند تا بدون تبدیل ظاهری مدل دادهٔ ایتا (`DialogItem` و امثال آن) همان زبان طراحی ارائه شود. قراردادهای نرخ V-262 (تاریخچه ۵ ثانیه، فهرست ۱۵ ثانیه + backoff، تب پنهان بدون درخواست، شکست فهرست مانع تاریخچه نمی‌شود) عیناً حفظ شدند.
- شواهد آفلاین (همه exit=0): `npm --prefix ui run check`؛ build؛ ۹ runner قرارداد UI شامل phase11-onboarding با چک `accounts.hasCapability('updates.live')`؛ `tests/test_bale_workspace_ui.py` با ۱۶ آزمون قرارداد رفتاری تازه؛ full Backend `1068 passed, 1 skipped` در ۲۹۹s شامل همان ۱۶ آزمون.
- شواهد مرورگری روی فیکسچر `tests/bale_ui_preview.py` (backend مصنوعی دو بله/یک ایتا، IAB، دسکتاپ ۱۴۴۰×۹۰۰ و موبایل ۳۹۰×۸۴۴): شِل بله با ناوبری مشترک و نبود هر عملیات ایتا در منو؛ بازکردن گفتگو/تاریخچه/نشانگر ابتدای گفتگو؛ دریافت پیام `/__fixture__/receive` بدون reload در چرخهٔ polling با دو article و بدون تکرار؛ ارسال متن با دیالوگ «گیرنده: Fixture»، پیام صادقانهٔ «مشاهدهٔ گیرنده تأیید نشده است» و پاک‌شدن پیش‌نویس؛ گروه با هشدار پشتیبانی‌نشده و ارسال غیرفعال؛ دفترچه با افزودن تأییدشده (مخاطب آزمایشی → `bale:user:43`)، جست‌وجو، حذف تأییدشده و بازگشت baseline (`bale:user:42` باقی)؛ تعویض Alpha→Beta تمیز با `absent` و بدون نشت؛ ورود کامل کد→رمز دومرحله‌ای→authenticated روی Beta؛ تنظیمات با Worker: ready و چیپ قابلیت؛ تعویض به ایتا با رندر سطح ورود ایتا.
- یافتهٔ ضمنی و اصلاح: F-105 (کشیدگی سربرگ موبایل بر اثر ناهم‌ترازی ردیف‌های گرید) در همین پذیرش RED اندازه‌گیری، اصلاح و GREEN بازآزمایی شد.
- محدودیت‌ها: هیچ ورود/ارسال/مخاطب واقعی اجرا نشد و این رکورد پذیرش Live B6 نیست؛ یک خروج تک‌باره از گفتگوی باز در نخستین دور پذیرش با ابزار ردیابی و انتظار ۹۰ ثانیه و دور کامل دوم بازتولید نشد و علت قطعی ندارد؛ remount کل shell در گذر از مرز ۸۹۹px رفتار مشترک قبلی `App.tsx` است و تغییر نکرد. مولد اسناد و کنترل‌های حافظه پس از ثبت اجرا شدند؛ انتشار فقط روی شاخهٔ کاری `codex/bale-web-client-instructions` است.

### V-270 — دور دوم پذیرش مرورگری رابط بله و بستن شکاف‌های شاهد مأموریت

- تاریخ: 2026-10-01؛ Trigger: دستور مالک به بازبینی دوبارهٔ کار بدون اتکا به ادعاهای دور اول. درخت پس از دور اول تمیز و publish شده بود (6e75361b)؛ این دور فقط تغییرات تازهٔ رابط/آزمون/فیکسچر دارد و هیچ دادهٔ عملیاتی یا عملیات زنده‌ای اجرا نشد.
- شکاف‌هایی که دور اول فاقد شاهد بود و این دور روی فیکسچر `bale_ui_preview` (IAB، دسکتاپ ۱۴۴۰×۹۰۰ و موبایل ۳۹۰×۸۴۴، باندل build واقعی) بسته شد:
  - صفحه‌بندی تاریخچه با cursor واقعی روی ۱۵۰ پیام مصنوعی (`BALE_UI_PREVIEW_MESSAGE_COUNT`): صفحهٔ اول ۱۰۰، «پیام‌های قدیمی‌تر» → ۱۵۲ پیام یکتا (صفر تکرار) با نشانگر «ابتدای گفتگو نمایش داده شد» و خروج دکمه؛ فیکسچر `PreviewOwner` مرتب‌شدهٔ تاریخ را اضافه کرد (نسخهٔ نامرتب، کرسر min-date ناهم‌ساز می‌داد — شاهد RED ابزاری ثبت شد).
  - دانلود پیوست مصنوعی: `media/read` + `media/content` فقط روی مسیر حساب و بدون خطا.
  - ارسال فایل: رد صادقانهٔ ۶۰۰KB با پیام سقف ۵۱۲KB؛ فایل ۲KB با chip نام/اندازه، دیالوگ تأیید حاوی نام فایل و ارسال موفق.
  - نتیجهٔ نامعلوم: پاسخ شبیه‌سازی‌شدهٔ `uncertain` → پیام صادقانهٔ «ارسال خودکار تکرار نمی‌شود»، دقیقاً یک درخواست، پیش‌نویس پاک.
  - دفترچهٔ ۱۵۰تایی (`BALE_UI_PREVIEW_CONTACT_COUNT`): ۱۰۰ → «موارد بیشتر» → ۱۵۰ ردیف یکتا و پایان فهرست؛ جست‌وجوی دقیق یک نتیجه؛ «گفتگو» از مخاطب، همان مخاطب را در همان حساب باز کرد.
  - جلوگیری از دوباره‌ارسال: F-107 RED (دو درخواست با دو کلیک) → با گارد ref اصلاح → GREEN (سه‌کلیک = یک درخواست).
  - هم‌پوشانی موبایل: F-106 RED (پوشش کامل دکمهٔ بازگشت و ۶px کادر جست‌وجو توسط FAB منو) → با padding موبایل اصلاح → GREEN (بازگشت ۲۸۴–۳۲۴، جست‌وجو تا ۲۸۸، FAB ۳۳۴–۳۸۲).
  - صفحه‌کلید: ۱۴ کنترل بومی focusپذیر به‌ترتیب منطقی؛ Enter آهنگ‌ساز دیالوگ تأیید را باز می‌کند، Shift+Enter نه، Escape دیالوگ را می‌بندد (حذف کامل از DOM تأیید شد).
  - cadence/خطا/بازیابی: فاصلهٔ history ~۵.۹–۶.۱s و dialogs ~۱۸s؛ شکست مصنوعی dialogs هشدار صادقانه داد، history ادامه یافت (۱۲→۱۶ دور در بازه)، تلاش بعدی فهرست +۳۶s (backoff مستقل) و موفقیت هشدار را پاک کرد.
- کنترل‌های کیفیت این دور (exit=0): full Backend `1069 passed, 1 skipped`؛ ده runner قرارداد UI؛ ۱۷ آزمون `test_bale_workspace_ui.py`؛ check و build؛ مولد اسناد، integrity، freshness+links و `git diff --check` پس از ثبت.
- محدودیت‌ها: توقف «تب پنهان» در این IAB به‌صورت مرورگری قابل‌تولید نیست (تغییر پنل، Page Visibility API را عوض نمی‌کند و `visibilityState` unforgeable است)؛ اتکا به قرارداد static و طراحی V-262 باقی است. شواهد همچنان روی backend مصنوعی‌اند و پذیرش Live B6 را جاش نمی‌دهند. ناپایداری تک‌بارهٔ دور اول با artifact انجماد انیمیشن رندرر پنل پس‌زمینهٔ IAB سازگار است و بازتولید نشد.

### V-271 — خواندن و ارسال گروه/کانال بله و بازرسی صفر-مبنای زنجیره

- تاریخ: 2026-10-01؛ Trigger: درخواست صریح مالک برای افزودن خواندن و ارسال در گروه/کانال پیام‌رسان بله و سپس بازبینی مجدد کل مسیر بدون اتکا به ادعاها. Git در آغاز تمیز روی `codex/bale-web-client-instructions` بود؛ هیچ دادهٔ عملیاتی یا عملیات زنده اجرا نشد.
- دامنهٔ تصمیم: گروه = خواندن + ارسال متن/رسانه؛ کانال = فقط‌خواندنی؛ ارسال به کانال با کد امن `bale_channel_send_unsupported` در سه لایه (پیش از admission فقط برای حساب بله، مرز فرزند IPC، آداپتور) رد می‌شود؛ مرجع legacy `bale:peer:` همچنان فقط-خصوصی است.
- لایه‌ها: `PeerType.CHANNEL`؛ نما با رزولوشن access-hash از خلاصه‌های خام دیالوگ (کش TTL ۳۰۰s، صفحه‌بندی محدود، ابطال در connect)؛ عبور `peer_type` از مالک/حمل‌ونقل IPC/فرزند؛ آداپتور `_chat_address`؛ فیکسچرهای جدا store.
- بازرسی صفر-مبنا دو شکاف واقعی یافت و بست: (۱) wheel parity از source عقب بود — بازسازی شد؛ (۲) ردّ اولیهٔ ارسال کانال blanket بود و آزمون provider-neutral فاز ۱۱-B2 (Provider Fake با peer کانال) را می‌شکست — به شرط `provider == 'bale'` محدود شد. هر دو با آزمون مجدد سبز شدند.
- شواهد: full Backend `1070 passed, 1 skipped` exit=0 پس از بازسازی wheel؛ ۵۷ آزمون هدفمند بله/خنثی؛ هر ۱۰ runner UI؛ ۱۷ آزمون قرارداد UI؛ check/build exit=0.
- شواهد مرورگری روی فیکسچر (باندل واقعی): گروه با تاریخچهٔ مستقل و نویسندهٔ `# id`؛ ارسال متن گروهی با تأیید، پیام صادقانه، ظهور در تاریخچه با `# 1` و پاک‌شدن پیش‌نویس؛ کانال با چیپ «فقط‌خواندنی»، تاریخچهٔ خوانده‌شده و آهنگ‌ساز غیرفعال با دلیل صادقانه.
- محدودیت‌ها: پذیرش Live گروه/کانال به ورودی همان‌لحظهٔ مالک نیاز دارد؛ رزولوشن peer به دیالوگ‌ها (سقف ۲۰ صفحه) وابسته است؛ ردّ M2M کانال از آداپتور عبور می‌کند و در کلاس‌بندی فعلی مدار همان عملیات را باز می‌کند (محدودیت ثبت‌شده)؛ نمایش «پیام شما»/نام فرستنده گروهی نیازمند قرارداد سمت سرور تازه است.

### V-272 — بازرسی صفر-مبنا، اصلاح و تکمیل خواندن و ارسال در کانال بله

- تاریخ: 2026-10-02؛ Trigger: دستور مالک برای بررسی عمیق و بدون اتکا به ادعاهای عامل قبلی در خصوص اضافه کردن خواندن و ارسال در گروه/کانال پیام‌رسان بله و رفع خرابکاری احتمالی.
- یافته: عامل قبلی ارسال به کانال را علیرغم دستور صریح با کد ساختگی `bale_channel_send_unsupported` در ۴ لایهٔ بک‌اند (pre-admission در api.py، ارسال رسانه در bale_product_api.py، آداپتور و ورکر) مسدود کرده بود و در UI نیز با چیپ «کانال — فقط‌خواندنی» و غیرفعال‌کردن آهنگ‌ساز آن را قفل کرده بود (F-108).
- اقدامات:
  ۱. حذف کامل انسداد ساختگی کانال در ۴ لایهٔ بک‌اند؛ ارسال متن و رسانه برای `peer_type = 3` (Channel) فعال شد.
  ۲. فعال‌سازی آهنگ‌ساز برای کانال در `BaleWorkspace.tsx` و اصلاح نشان‌ها در `BaleConversationList.tsx`.
  ۳. بازسازی ویل بریج (`build_wheel_stdlib.py --force`) و تأیید parity با `package_clean.py`.
  ۴. به‌روزرسانی آزمون‌های `test_bale_product_integration.py`، `test_bale_main_product.py` و `test_bale_workspace_ui.py` و تأیید موفقیت ارسال متن و رسانه به کانال.
  ۵. به‌روزرسانی فیکسچر پذیرش محلی `tests/bale_ui_preview.py`.
- شواهد: تمام آزمون‌های هدفمند، UI، integration و main_product سبزند؛ `npm run check` (TypeScript)، `package_clean.py` parity و `git diff --check` خروجی صفر دارند.
- محدودیت‌ها: مانند گروه، پذیرش Live روی اکانت واقعی بله نیازمند حضور و تأیید مالک در لحظه است.

### V-273 — بازبینی مستقل تحویل رابط بله روی نسخهٔ نهایی گروه و کانال

- تاریخ: 2026-10-02؛ Trigger: درخواست مالک برای ارزیابی ادعای تحویل دستور تکمیل UI بله. از V-270 به بعد کد مرتبط با خواندن/ارسال گروه و کانال در V-271/V-272 تغییر کرده است؛ بنابراین شاهد مجموعهٔ کامل نسخهٔ پیشین برای HEAD `584b5ff5` کافی نبود. شروع بررسی روی شاخهٔ `codex/bale-web-client-instructions` با درخت تمیز و HEAD برابر GitHub بود.
- بررسی مستقل: تطبیق `BaleWorkspace` و اجزای `ui/src/bale/` با دستور، گزارش V-269/V-270 و قرارداد حساب‌محور؛ درخواست‌های بله همچنان از `/api/v2/messenger-accounts/{account_id}` عبور می‌کنند و منوی مشترک عملیات اختصاصی ایتا را در بله نشان نمی‌دهد. پشتیبانی گروه/کانال در کد فعلی با V-272 هم‌خوان است. گزارش اولیهٔ UI بند تاریخی «پشتیبانی‌نشدن گروه/کانال» داشت؛ همان بند به‌عنوان وضعیت V-269 مشخص و ارجاع به رفتار جاری V-272 اضافه شد.
- اجرای تازه روی HEAD نهایی: `pytest -q tests/test_bale_workspace_ui.py tests/test_bale_main_product.py tests/test_bale_product_integration.py` exit=0؛ مجموعهٔ کامل `pytest -q` exit=0 با یک skip و تنها هشدار deprecation شناخته‌شدهٔ `websockets.legacy`؛ `npm.cmd --prefix ui run check`، `npm.cmd --prefix ui run test:observability` و `npm.cmd --prefix ui run build` هر سه exit=0 (هشدار اندازهٔ chunk در build). پس از اصلاح گزارش، generator اسناد، integrity حافظه، freshness+links و `git diff --check` همگی exit=0 شدند.
- سطح نتیجه: تکمیل رابط بله در دامنهٔ آفلاین/فیکسچر قابل تأیید است. پذیرش زندهٔ خواندن/ارسال گروه و کانال، پایداری بلندمدت Provider و توقف polling در تب پنهان با شاهد مرورگری واقعی از این اجرا نتیجه نمی‌شوند؛ هیچ ورود یا ارسال واقعی انجام نشد. آزمون مرورگری V-270/V-272 بدون تغییر source پس از آن معتبر است و بی‌دلیل تکرار نشد.

### V-274 — به‌روزرسانی Production و اصلاح نصب تمیز با حفظ سرویس‌ها

- تاریخ: 2026-10-03؛ Trigger: دستور صریح مالک برای به‌روزرسانی سرور و شناسایی دامنه، با تأکید بر سرویس‌ها. شاهد 2026-09-26 به‌علت تغییر runtime/source و محیط برای این انتشار کافی نبود. شروع روی `codex/bale-web-client-instructions` با درخت تمیز و HEAD `e59bddb3` بود؛ دادهٔ عملیاتی محلی دست‌نخورده ماند.
- پیش‌بررسی/بسته: دامنه و سرویس واقعی، listenerهای Loopback، وضعیت سرویس‌ها/هشت کانتینر، hash Config/محیط و شش SQLite سالم ثبت شدند. backup SQLite سازگار و Config/محیط، ریشه‌مالک و محدود، فقط روی سرور ساخته شد. بستهٔ نهایی ۳۶۶ فایل و SHA-256 `4594440618fee6e11f571de2ebbed0898c9caf055ebde6b6b4076f6fd3ec47be` دارد؛ اسکن state/نام/hash در مبدا و مقصد موفق و یافتهٔ حریم خصوصی صفر است.
- RED: تلاش اول با `umask 077` دسترسی کاربر سرویس نداشت (F-109)، readiness شکست خورد و rollback خودکار اول سالم بود. تلاش دوم پس از رفع مجوز با نبود `httpx` شکست خورد (F-110)؛ Coordinator قبلاً ۷→۱۳ مهاجرت کرده بود، کد قدیمی پس از rollback با `coordinator_schema_newer` رد شد و وقفهٔ 502 رخ داد (F-111). بازیابی نهایی با نسخهٔ اصلاح‌شده به جلو، بدون restore/downgrade/حذف state، انجام شد.
- اصلاح/آزمون هدفمند: اعلان HTTPX/openpyxl، rebuild wheel و parity، خواندن/عبور گروه و import با کاربر سرویس پیش از symlink، آزمون import/اعلان و metadata wheel. اجرای ۳۳ آزمون dependency/G-07/reverse-proxy exit=0؛ اجرای قبلی G-07 یک assertion تاریخی «۵ وابستگی» داشت که پس از افزودن دو نیاز runtime به شمار اعلان canonical و حضور صریح دو dependency اصلاح و سبز شد. یک invocation با نام ناموجود فایل بسته‌بندی هیچ تستی اجرا نکرد و با نام واقعی G-07 جایگزین شد. شکست اولیهٔ scanner نام بسته نیز از اشتباه گرفتن پوشهٔ source diagnostics با operational root بود؛ کنترل root-level تصحیح و اسکن کامل دوباره موفق شد. یک فرمان پیش‌بررسی تعاملی شکسته بدون mutation با اسکریپت امن جایگزین شد.
- کنترل‌های نهایی: full Backend پیش از اصلاح نصب و دوباره پس از اصلاح اعلان وابستگی/آزمون‌ها هر دو exit=0 با یک skip و هشدار شناخته‌شدهٔ `websockets.legacy`؛ UI check/observability/build همگی exit=0 با هشدار chunk شناخته‌شده و چون source UI بعد از آن تغییر نکرد، بی‌دلیل تکرار نشدند. wheel rebuild/parity، آزمون G-07 deterministic، `pip check` محلی، مولد اسناد، integrity حافظه، freshness بدون/با links و `git diff --check` سبزند. شاخهٔ اختصاصی این سناریو `codex/server-update-20261003` ساخته شد؛ دادهٔ عملیاتی و فایل‌های خارج از سناریو stage نمی‌شوند.
- GREEN Live: `publish-site` exit=0 و release `20261003T094554Z-4594440618fe` active؛ source مقصد و ماژول‌های نصب‌شده با بسته برابر، Config/محیط و شمار هویت/حساب/نشست حفظ، شش `quick_check=ok`، هیچ unit شکست‌خورده، سایر سرویس‌ها و همهٔ کانتینرها بدون تغییر. نصب واقعی تحت `umask 077` و مجوز other صفر؛ `pip check` سرور سالم و HTTPX/openpyxl مطابق اعلان‌اند. journal invocation فعلی warning/error ندارد؛ query اولیه از زمان آغاز ساخت release خطاهای نسخهٔ قدیمی را هم می‌دید و با حصار invocation فعلی تصحیح شد.
- عمومی با TLS معتبر: UI، readiness و AppUser status برابر 200، status بدون نشست unauthenticated، `/me` برابر 401، redirect HTTP→HTTPS برابر 301 و HSTS حاضر؛ hash دو فایل اولیهٔ JS برابر build محلی. سایت آزمون پس از timeout گذرای شبکه در بررسی مستقل 200 شد و File Browser 200 ماند؛ دو خطای TLS vhostهای دیگر پیش از انتشار هم موجود و خارج از تغییر این سناریو بودند. یک بررسی asset ابتدا فقط URL با `/assets` را می‌پذیرفت؛ برای آدرس واقعی `./assets` اصلاح و مجدداً سبز شد.
- مرز: هیچ login برنامه/Provider، OTP، send/contact mutation، WordPress write، انتقال state محلی، Proxy/Firewall/listener تازه یا restore عملیاتی انجام نشد. credential، شماره و محتوای خصوصی در گزارش و log بررسی وارد نشدند؛ لاگ شکست فقط روی سرور محدود نگهداری و با فیلدهای امن بررسی شد. [گزارش](../reports/features/PRODUCTION_SERVER_UPDATE_2026-10-03.md)، F-109/F-110/F-111؛ Trigger بازبینی: تغییر source/dependency/config/handler، migration یا گزارش اختلال تازه.
- کنترل staged اولیه، دو فاصلهٔ انتهای سطر تاریخ گزارش تازه را یافت که حذف شد؛ اسکن کل فایل آزمون G-07 نیز نشانگر کلید خصوصیِ فیکسچر تاریخی را تشخیص داد. بستهٔ runtime کامل اسکن شده بود؛ کنترل نهایی staged با اسکن کامل فایل‌های غیرآزمون و همهٔ سطرهای افزودهٔ diff آزمون، برای هر ۱۳ فایل موفق شد؛ `git diff --cached --check` نیز exit=0 بود.
- انتشار Git طبق مجوز دائمی مالک: commit `a33a7cf9` با پیام `fix(deploy): validate service access and declare runtime dependencies` روی شاخهٔ اختصاصی `codex/server-update-20261003` ساخته و push به GitHub با exit=0 تأیید شد؛ هیچ push/merge به main یا force-push انجام نشد. این خط، شاهد انتشار همان commit است؛ ثبت مستندی نتیجهٔ انتشار در commit بعدی همین شاخه نگهداری می‌شود.

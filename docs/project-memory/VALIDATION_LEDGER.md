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

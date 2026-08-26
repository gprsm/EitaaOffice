# گزارش Phase 11-B2 — Provider-neutral Application Orchestration، slice 1

تاریخ handoff: 2026-08-17  
تاریخ تکمیل و پذیرش محلی: 2026-08-20  
نتیجهٔ نهایی: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED / NOT_LIVE`  
اثر بیرونی: `NONE`  
وضعیت Bale Personal: `RUNTIME_BLOCKED / UNCHANGED`

> یادداشت وضعیت: این سند شاهد تاریخی slice 1 است. بدهی‌های بخش ۹ در ادامهٔ محلی ۲۰۲۶-۰۸-۲۰ بسته شده‌اند؛ مرجع جاری `PHASE11B2_PROCESS_RPC_MEDIA_CONTACT_PERSISTENCE_REPORT_2026-08-20.md` است.

## ۱. هدف و دامنه

هدف slice اول B2 ساخت یک مسیر application عمومی و تست‌پذیر بود تا Dialog، History و Text Send بدون branch نام Provider و پس از ترتیب ثابت امنیتی اجرا شوند. Eitaa باید از compatibility adapter و Fake سوم از همان orchestrator عبور می‌کردند. سمانتیک Media/Contacts نیز باید بدون حدس قابلیت Provider آینده به DTO/protocol محدود تبدیل می‌شد.

خارج از دامنه: Bale transport/auth/session، Provider network، حساب واقعی، Login/OTP/Credential، Send واقعی، WordPress، migration DB عملیاتی، restart سرویس، Config، Firewall/Proxy/Port و Git mutation.

## ۲. معماری پیاده‌شده

### ۲.۱. ترتیب امن واحد

`ProviderApplicationOrchestrator` این ترتیب را برای هر operation اجرا می‌کند:

```text
server-authenticated AppUser
-> active Membership/account authorization
-> server-resolved ProviderAccountContext
-> account capability decision
-> bounded live deadline/correlation
-> allowlisted adapter factory
-> manifest capability ceiling
-> bounded provider operation/result
-> sanitized error and structured event
```

orchestrator هیچ literal/provider branch برای Eitaa، Bale یا Fake ندارد. factory از composition root و account.provider سروری resolve می‌شود. Adapter ناشناس، scope mismatch، Manifest mismatch، deadline نامعتبر یا نتیجهٔ خارج از contract همگی fail-closed هستند.

### ۲.۲. Idempotency و uncertain

Text Send و Contact Upsert کلید idempotency محدود دارند. duplicate هم‌زمان پیش از provider call دوم رد می‌شود. receipt `uncertain` terminal است و retry خودکار ندارد.

در بازبینی حین پیاده‌سازی مشخص شد cache اولیه قبل از authorization بازگشت داده می‌شد. cache lookup به داخل provider invocation، پس از authorization/account/capability/deadline/adapter checks منتقل شد. تست مستقل ثابت می‌کند replay کلید پس از لغو دسترسی رد و provider call تکرار نمی‌شود.

### ۲.۳. Eitaa compatibility و Fake

`EitaaProviderApplicationAdapter` ترجمهٔ Eitaa را در package همان Provider نگه می‌دارد. callbacks typed، Dialog catalog/History/Send موجود را به DTOهای عمومی نگاشت می‌کنند. lifetime runtime در مالکیت registry باقی می‌ماند و `close()` عملیاتی آن را نمی‌بندد.

Fake سوم از adapter و session store آفلاین موجود و دقیقاً همان orchestrator production عبور می‌کند؛ test bypass جدا ندارد.

### ۲.۴. Media و Contacts

DTO/protocolهای تازه:

- `ProviderMediaReadRequest/Receipt` با opaque reference، variant محدود، MIME معتبر و byte limit؛
- `ProviderContactSummary/Page` با identity hint محو و page حداکثر 500؛
- `ProviderContactUpsertRequest/MutationReceipt` با `SensitiveProviderValue` و idempotency؛
- protocolهای اختیاری `ProviderMediaAdapter` و `ProviderContactAdapter`.

این عملیات در orchestrator capability-gated هستند، اما slice 1 route/transport تازهٔ production برای آنها فعال نمی‌کند. این تصمیم از ادعای Capability حدسی یا مهاجرت نیمه‌کاره جلوگیری می‌کند.

## ۳. API و UI

سه route جدید و اتمیک v2:

```text
POST /api/v2/messenger-accounts/{id}/dialogs/query
POST /api/v2/messenger-accounts/{id}/history/query
POST /api/v2/messenger-accounts/{id}/messages/send-text
```

هر route فیلدهای body را allowlist می‌کند. account/provider/capability جعلی و فیلد زائد رد می‌شود. Send به idempotency key صریح نیاز دارد و سرور correlation را به‌عنوان کلید retry جایگزین نمی‌کند.

`MessengerAccountGate` برای حساب انتخابی capability snapshot می‌خواند. `hasCapability` فقط وقتی true است که snapshot دقیقاً مال همان account، runtime enabled و status برابر supported باشد. account switch، loading، error، restricted، unsupported و unknown حالت fail-closed دارند.

UI پیش از request این عملیات را جداگانه guard می‌کند: dialogs.read، history.read، media.read، messages.send، media.send، contacts.read و contacts.write. محیط دیداری Fake نیز capability endpoint حساب‌محور را شبیه‌سازی می‌کند.

## ۴. Observability و privacy

شش رخداد پیش از استفاده به Event Catalog افزوده شدند:

- `provider_operation_started`
- `provider_operation_succeeded`
- `provider_operation_rejected`
- `provider_operation_failed`
- `provider_operation_uncertain`
- `provider_operation_adapter_close_failed`

Catalog از 78 به 84 رخداد رسید. event fields فقط account id سرورساز، Provider، operation، capability، correlation، result/reason، error type و duration امن را دارند. متن پیام، contact identity، idempotency key، exception message، raw result و مسیر فایل ثبت نمی‌شود.

تست exception حاوی مقدار خصوصی مصنوعی ثابت کرد مقدار خام نه در exception عمومی و نه JSONL نیامد. اسکنر فقط‌خواندن runtime نیز 9106 رکورد، invalid JSON=0 و finding=0 گزارش کرد.

## ۵. شواهد آزمون

| دامنه | سطح | نتیجهٔ نهایی |
|---|---|---|
| B2 مستقل | Unit/Contract/Fake/Adversarial | `14/14` |
| B0+B1+B2+11-0+Application API | Unit/Contract | `75/75` |
| Observability Backend | Unit/Contract | `6/6` |
| Full Backend regression | Automated | `554/554` |
| UI B2 capability | Static contract | `6/6` |
| UI onboarding | Static contract | `7/7` |
| UI/Electron observability | Contract | موفق |
| TypeScript check | Static build | موفق |
| Production Vite build | Build | موفق |
| Runtime log redaction | Read-only scanner | 9106 record، invalid=0، finding=0 |
| Docs/generated/link | Generated/Static | پس از refresh در V-046 ثبت می‌شود |

Build نهایی یک chunk اصلی 897.77 kB minified گزارش کرد. هشدار آستانهٔ 500 kB همان بدهی باز F-013 و غیرمسدودکننده است.

## ۶. Failure و invocation ledger

1. patch تجمیعی نخست API و دو patch ترکیبی Contact UI context پیدا نکردند؛ apply اتمیک هیچ mutation جزئی نداشت و patchها کوچک شدند.
2. UI contract نخست پس از 3/6 به‌دلیل assertion وابسته به نام شرط متوقف شد؛ تست به behavior `canSend/disabled` اصلاح و 6/6 شد.
3. production build نخست با دو TS18047 در nullable capability snapshot شکست؛ null guard صریح افزوده شد و check/build نهایی موفق بود.
4. full regression نخست 553 passed/1 failed داشت. failure انتظار ایستای قدیمی dependency array رسانه بود؛ انتظار به dependency امن `mediaReadSupported` ارتقا یافت و full دوم 554/554 شد.
5. چند lookup فقط‌خواندن با quoting/glob ناسازگار PowerShell parse/resolve نشدند؛ با مسیرهای Windows-safe تکرار شدند.
6. Git read-only نخست `dubious ownership` داد؛ فقط invocation با `-c safe.directory` موقت تکرار شد و Git config تغییر نکرد.
7. source probe نخست بدون `src` در import path نتیجه نساخت؛ probe صریح Event Catalog=84 را تأیید کرد.

## ۷. فایل‌های تغییریافته در این slice

### Backend و قرارداد

- `src/eitaa_bridge/application/provider_orchestration.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/providers/contracts.py`
- `src/eitaa_bridge/providers/__init__.py`
- `src/eitaa_bridge/providers/eitaa/__init__.py`
- `src/eitaa_bridge/providers/eitaa/application_adapter.py`
- `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py`

### UI و تست

- `ui/src/MessengerAccountGate.tsx`
- `ui/src/App.tsx`
- `ui/src/QuickSendBar.tsx`
- `ui/src/ContactDirectoryModal.tsx`
- `ui/src/main.tsx`
- `ui/scripts/run-phase11b2-orchestration-tests.mjs`
- `ui/package.json`
- `tests/test_phase11b2_provider_neutral_orchestration.py`
- `tests/test_material_ui_repair.py`

### اسناد

- `ARCHITECTURE_DECISIONS.md`
- `docs/APPLICATION_API.md`
- `docs/LOGGING_AND_OBSERVABILITY.md`
- `docs/PROJECT_SPECIFICATION.md`
- `docs/PROJECT_STRUCTURE.md`
- `docs/PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md`
- `docs/project-memory/CURRENT_SYSTEM_BASELINE.md`
- `docs/project-memory/FINDINGS_REGISTER.md`
- `docs/project-memory/VALIDATION_LEDGER.md`
- `docs/project-memory/MULTI_ACCOUNT_PROVIDER_ROADMAP.md`
- همین گزارش و blocker مرز ادامهٔ Phase 11.

## ۸. حفظ داده و اثر بیرونی

- `bridge.json`، `.env`، Session واقعی، `data/`، `runtime/`، `diagnostics/`، `catalog/` و `backups/` تغییر داده نشدند.
- scanner فقط‌خواندن بود و مقدار لاگ را echo نکرد.
- Provider endpoint، Login، OTP، Credential، Send واقعی، WordPress، Firewall، Proxy، Port و Certificate استفاده/تغییر نشد.
- DB عملیاتی migrate و سرویس واقعی restart نشد.
- reset/checkout/clean/stage/commit/push و Git config mutation انجام نشد؛ worktree عمداً dirty حفظ شد.

## ۹. مرز باقی‌مانده

slice 1 کامل است، اما کل B2 هنوز این بدهی‌ها را دارد:

1. Child RPCهای typed/bounded/fenced Dialog/History/Text Send برای `EitaaProcessRuntime`؛
2. execution عمومی Media/Contacts و compatibility mapping بدون نشت سمانتیک‌های Eitaa-only؛
3. idempotency persistence برای mutationهایی که باید restart فرایند را تحمل کنند؛ cache فعلی فقط process-lifetime و با سقف 2048 receipt است؛
4. Live pilot حساب دوم Eitaa و متریک‌های واقعی؛ فقط با تأیید همان لحظه و ورود خصوصی مالک.

## ۱۰. نتیجه

افزودن Provider جدید برای سه عملیات slice 1 دیگر نیازمند branch در orchestrator، بازنویسی Membership/Capability یا تغییر UI shell نیست. این نتیجه فقط سطح Contract/Fake/Adversarial دارد و هیچ Bale runtime یا ادعای Live ایجاد نمی‌کند.

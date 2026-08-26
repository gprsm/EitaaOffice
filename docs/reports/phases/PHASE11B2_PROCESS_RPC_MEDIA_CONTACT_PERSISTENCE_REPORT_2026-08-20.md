# گزارش تکمیل Phase 11-B2 — Process RPC، Media/Contacts و receipt پایدار

تاریخ: 2026-08-20  
نتیجه: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED / NOT_LIVE`  
اثر بیرونی: `NONE`  
وضعیت Bale Personal: `BLOCKED / UNCHANGED`

## ۱. نتیجهٔ اجرایی

بدهی‌های محلی گزارش slice 1 بسته شدند:

1. هر شش operation عمومی `Dialog / History / Text Send / Media Read / Contact List / Contact Upsert` از `ProviderApplicationOrchestrator` و ترتیب امنیتی مشترک عبور می‌کنند.
2. حالت `EitaaProcessRuntime` برای همین عملیات Child RPCهای typed، allowlisted و account-fenced دارد.
3. Media cache path در Child باقی می‌ماند و Parent فقط chunk محدود را broker می‌کند.
4. Media/Contacts در API v2 فعال، bounded و capability-gated هستند.
5. Send و Contact Upsert علاوه بر idempotency key به `confirm=true` دقیق نیاز دارند.
6. receiptهای mutation در Coordinator schema v7 پایدارند و restart را بدون تکرار اثر بیرونی تحمل می‌کنند.

این نتیجه فقط Unit/Contract/Fake/Adversarial/Build است. هیچ Login، Provider network، Send واقعی یا migration پایگاه عملیاتی انجام نشد.

## ۲. مرز Process Runtime

### ۲.۱. عملیات Child

Worker فقط methodهای صریح زیر را می‌پذیرد:

- `eitaa.provider.dialogs.query`
- `eitaa.provider.history.query`
- `eitaa.provider.messages.send_text`
- `eitaa.provider.media.read`
- `eitaa.provider.media.read_chunk`
- `eitaa.provider.contacts.query`
- `eitaa.provider.contacts.upsert`

برای هر درخواست، method و field allowlist، MessengerAccount fence، session generation و deadline کنترل می‌شوند. raw SDK object، Session state، access hash، path و exception خام از Worker خارج نمی‌شود. Parent نیز result را دوباره به DTO عمومی نگاشت و reference/scope/limit را اعتبارسنجی می‌کند.

### ۲.۲. Media broker

فایل رسانه در media root همان account و داخل Child ثبت می‌شود. Parent فقط content token account-bound دارد. هر chunk حداکثر 192 KiB است و Base64، offset، طول، MIME، پیوستگی و EOF پیش از HTTP streaming سنجیده می‌شوند. empty non-EOF، offset جهشی، MIME ناسازگار و payload خارج از حد fail-closed هستند.

### ۲.۳. Contacts privacy

Contact DTO فقط opaque reference، display name محدود و identity hint پوشیده دارد. identity hint غیرخالی باید نشانهٔ masking داشته باشد؛ شمارهٔ کامل رد می‌شود. fallback نمایش مخاطب از شمارهٔ کامل استفاده نمی‌کند.

## ۳. API عمومی و تأیید mutation

Routeهای کامل B2:

```text
POST /api/v2/messenger-accounts/{id}/dialogs/query
POST /api/v2/messenger-accounts/{id}/history/query
POST /api/v2/messenger-accounts/{id}/messages/send-text
POST /api/v2/messenger-accounts/{id}/media/read
POST /api/v2/messenger-accounts/{id}/contacts/query
POST /api/v2/messenger-accounts/{id}/contacts/upsert
```

همهٔ routeها account context را از route و Membership سمت سرور می‌گیرند و body نمی‌تواند account/provider/capability را override کند. فیلد زائد رد می‌شود. دو mutation فقط با `confirm is True` و idempotency key معتبر اجرا می‌شوند؛ correlation به کلید ضمنی تبدیل نمی‌شود.

## ۴. Idempotency پایدار و Coordinator v7

جدول `provider_operation_receipts` فقط metadata امن زیر را نگه می‌دارد:

- account، actor، provider و operation؛
- idempotency key و SHA-256 fingerprint درخواست؛
- claim deadline و outcome؛
- reference/result محدود، created flag و safe reason code.

متن پیام، contact identity و request body ذخیره نمی‌شوند. fingerprint با length-prefix از operation و مقادیر حساس ساخته می‌شود تا payload خام persist نشود.

رفتارها:

- claim تازه پیش از provider call و با `BEGIN IMMEDIATE` ثبت می‌شود؛
- replay terminal همان actor/payload پس از restart بدون provider call پاسخ می‌دهد؛
- استفادهٔ همان key با actor دیگر یا payload متفاوت رد می‌شود؛
- duplicate درحال‌اجرا retry نمی‌شود؛
- claim منقضی‌شده محافظه‌کارانه terminal `uncertain` می‌شود و اثر بیرونی دوباره اجرا نمی‌شود؛
- نتیجهٔ terminal متعارض قابل بازنویسی نیست.

ارتقای مستقیم Coordinator v6→v7 در DB موقت با migration checksum، `foreign_key_check` و `quick_check` پذیرفته شد. این آزمون یک ایراد verifier نسخهٔ ۶ را کشف کرد؛ `REQUIRED_TABLES_V6` به نگاشت اضافه و regression test مستقل ثبت شد.

## ۵. Observability و محرمانگی

دو رخداد تازه، شمار Catalog را از 84 به 86 رساندند:

- `provider_operation_idempotency_replayed`
- `provider_operation_idempotency_interrupted`

این رخدادها فقط account/provider/operation/outcome/source/reason/correlation امن دارند. idempotency key، fingerprint، متن، identity و path وارد log نمی‌شوند. تست persistence نبود payload خصوصی در JSONL و DB را بررسی کرد.

اسکن فقط‌خواندنی runtime:

- records: `9106`
- invalid JSON: `0`
- findings: `0`

## ۶. شواهد آزمون

| دامنه | نتیجه |
|---|---:|
| B2 مستقل | `20/20` |
| B2 + Coordinator schema | `38/38` |
| Phase 11/Process/API/Observability مرتبط | `133/133` |
| Full Backend | `561/561` |
| collection مستقل Backend | `561` |
| UI B2 capability | `6/6` |
| UI onboarding | `7/7` |
| UI/Electron observability | موفق |
| TypeScript check | موفق |
| Vite production build | موفق |
| Runtime privacy scanner | `9106 / invalid=0 / finding=0` |

Build همان هشدار غیرمسدودکنندهٔ chunk اصلی حدود 897.77 kB را دارد؛ این مورد از قبل بدهی performance بوده و قرارداد B2 را نقض نمی‌کند.

## ۷. Failure و تحلیل اصلاحی

1. persistence test نخست قابلیت Contact را رد کرد؛ علت، hard-code بودن Manifest Fake در harness بود. harness به provider واقعی account bind شد و suite سبز شد.
2. direct v6→v7 ابتدا شکست خورد؛ علت مطالبهٔ زودهنگام جدول v7 در verifier نسخهٔ ۶ بود. mapping اصلاح و آزمون migration تکرار شد.
3. دو assertion لاگ با context عمومی ابتدا در تست‌های اشتباه قرار گرفتند؛ پیش از اجرا با بررسی موضعی جابه‌جا و سپس رفتار replay/interruption سنجیده شد.
4. probe Catalog ابتدا package نصب‌شدهٔ قدیمی را import کرد؛ شاهد محسوب نشد و با source path صریح تکرار شد.
5. patch تجمیعی نخست مستندات context پیدا نکرد و اتمیک اعمال نشد؛ patchهای فایل‌محور کوچک جایگزین شدند.

## ۸. فایل‌های اصلی این تکمیل

- `src/eitaa_bridge/application/eitaa_provider_runtime_operations.py`
- `src/eitaa_bridge/application/eitaa_provider_worker.py`
- `src/eitaa_bridge/application/process_runtime.py`
- `src/eitaa_bridge/application/provider_orchestration.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/interfaces/http_api.py`
- `src/eitaa_bridge/providers/contracts.py`
- `src/eitaa_bridge/infrastructure/coordinator/schema.py`
- `src/eitaa_bridge/infrastructure/coordinator/receipts.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py`
- `tests/test_phase11b2_provider_neutral_orchestration.py`
- `tests/test_coordinator_schema.py`

## ۹. حفظ داده و اثر بیرونی

- `bridge.json`، `.env`، Session واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` نوشته، حذف یا جابه‌جا نشدند.
- DB عملیاتی migrate و سرویس واقعی restart نشد؛ همهٔ migrationها روی DB موقت تست بودند.
- Provider endpoint، Login، OTP، Credential، Send واقعی و WordPress استفاده نشد.
- Firewall، Proxy، Port، Certificate و Git state/config تغییر نکردند.

## ۱۰. مرز باقی‌مانده

کار محلی و ایمن B2 کامل است. ادامهٔ Phase 11 فقط در سه مسیر بیرونی ممکن است:

1. Pilot حساب دوم Eitaa با تأیید همان لحظه و ورود خصوصی مالک؛
2. Bale Personal پس از API رسمی یا اجازهٔ کتبی قابل ممیزی؛
3. Bale Bot/Arm پس از تصمیم صریح محصول دربارهٔ account kind و capability.

جزئیات در `../blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md` ثبت شده است.

## ۱۱. جمع‌بندی

Provider آینده برای شش operation عمومی دیگر به branch در Core، دسترسی Parent به state Child یا idempotency حافظه‌ای وابسته نیست. مرز معماری محلی آماده است؛ پذیرش Live و Bale همچنان عمداً و به‌درستی خارج از ادعای این گزارش‌اند.

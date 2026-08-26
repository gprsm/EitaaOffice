# قرارداد لاگ‌گذاری و Observability

آخرین بازبینی: 2026-08-26 / G-08-D

## ۱. هدف و اصل محرمانگی

لاگ برای تشخیص «چه رخ داد، کجا، با چه نتیجه و چه correlation» است؛ نه برای ذخیرهٔ محتوای خصوصی. Token، Cookie، OTP، رمز، کلید، header احراز هویت، شمارهٔ کامل، متن پیام، stack trace خام، URL دارای query و شناسهٔ حساس مقصد ممنوع‌اند.

## ۲. کانال‌ها

| کانال | کاربرد | نمونهٔ محل |
|---|---|---|
| Runtime JSONL | lifecycle، request، worker و خطای امن | `runtime/*.jsonl` و log desktop |
| Audit | عملیات امنیتی/کاربری و تغییر state | storage audit تحت دامنهٔ حساب/کاربر |
| Health/Readiness | زنده‌بودن process و آمادگی dependency | endpointهای health/readiness |
| Support Bundle | snapshot محدود برای پشتیبانی | `diagnostics/` پس از scan |
| UI diagnostic | خطای render/global بدون payload خصوصی | Renderer → Electron/API |

محل دقیق runtime تابع config است و نباید hard-code شود.

## ۳. schema مشترک

هر خط Runtime/Electron یک JSON object با فیلدهای زیر است:

| فیلد | معنا |
|---|---|
| `schema_version` | نسخهٔ قرارداد؛ فعلاً 1 |
| `at` | زمان UTC |
| `source` | `application`, `provider_worker`, `desktop`, `renderer` یا source معتبر |
| `event` | نام پایدار lowercase/snake_case از Event Catalog |
| `category` | حوزهٔ رخداد |
| `cataloged` | آیا رخداد در catalog مرکزی تعریف شده است |
| `level` | `debug/info/warning/error/critical` |
| `result` | `started/succeeded/failed/rejected/retried/degraded/...` |
| `reason_code` | کد امن و پایدار، بدون exception message |
| `correlation_id` | شناسهٔ سرتاسری درخواست/عملیات |
| `operation` | عملیات منطقی در صورت وجود |
| `thread` | نام امن thread |
| `fields` | allowlist دادهٔ زمینه‌ای redactشده |

مرجع اجرایی Event Catalog: `../src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py`. نسخهٔ قابل‌خواندن برای client از `GET /api/v2/observability/events` و health امن از `GET /api/v2/observability/health` ارائه می‌شود.

## ۴. correlation

Renderer یک correlation تصادفی 32-hex تولید می‌کند؛ preload/Electron همان مقدار را حفظ می‌کند؛ HTTP آن را در `X-Eitaa-Correlation-Id` می‌فرستد؛ Application و worker باید همان مقدار را در رخداد و audit ادامه دهند. ورودی نامعتبر حذف و مقدار امن جدید ساخته می‌شود.

## ۵. پوشش خطا

- React Error Boundary: render error با نوع خطا و booleanهای امن.
- Browser globals: `error` و `unhandledrejection` بدون message/stack/state.
- Electron: process error/exit، renderer gone/unresponsive، load failure، ownership/recovery و request retry.
- Backend: application lifecycle، API request، account request و wrapper عمومی `observed_operation`.
- Worker: source مستقل و correlation account-scoped.

گزارش renderer فقط سه event مجاز دارد، rate limit می‌شود و payload اضافی را رد می‌کند.

## ۶. افزودن رخداد جدید

1. نام و تعریف را در Event Catalog اضافه کن.
2. level/result/reason را ثابت و قابل‌جست‌وجو انتخاب کن.
3. fields را allowlist کن؛ raw object یا exception نفرست.
4. correlation را از caller بپذیر یا یک مقدار امن بساز.
5. تست schema، redaction و مسیر failure بنویس.
6. اگر رخداد برای پشتیبانی مهم است، support bundle allowlist را نیز بازبینی کن.

## ۷. عیب‌یابی امن

ابتدا health/readiness، سپس رخدادهای همان `correlation_id` و در پایان audit مربوط را بررسی کن. برای اشتراک diagnostics، `scripts/create_diagnostics_bundle.py` و سپس `scripts/scan_diagnostics_bundle.py` استفاده شود. فایل خام runtime، config واقعی یا session برای پشتیبانی ارسال نشود.

## ۸. وضعیت پوشش و کار باقیمانده

پوشش high-risk Backend/Electron/React و Event Catalog پیاده و contract-tested است. در G-08 backgroundهای برنامه، manual content-index/read-receipt، scanner چندحسابی، logger write-health و retention/disk-health محلی تکمیل شدند. metrics/alert مخصوص Web همچنان وابسته به deployment و deferred است؛ نبود آن نباید با ثبت payload خصوصی جبران شود.

### سلامت و نگه‌داری محلی G-08

- write failure logger عملیات اصلی را متوقف یا record خصوصی را روی stderr چاپ نمی‌کند؛ counter/type امن در health دیده می‌شود؛
- current log هرگز توسط retention حذف نمی‌شود؛ فقط rotation عددی مستقیم با سقف age/count/bytes مجاز است؛
- disk-health فقط byte count و status دارد، نه path؛
- scanner Runtime همهٔ account scopeهای مستقیم را با نام ترتیبی opaque می‌سنجد؛
- Support Bundle خط JSONL ناقص را حذف و فقط marker aggregate امن نگه می‌دارد؛ scanner نیز نام archive/member ورودی را بازتاب نمی‌دهد.

این قرارداد روی rootهای مصنوعی آزموده شده است؛ اجرای G-08 اسکن یا prune روی دادهٔ عملیاتی نبود.

### رخدادهای onboarding چندحسابی

Phase 11-0 چهار رخداد canonical و audit-required دارد:

- `messenger_account_onboarding_started`
- `messenger_account_onboarding_succeeded`
- `messenger_account_onboarding_reused`
- `messenger_account_onboarding_rejected`

این رخدادها فقط Provider، نتیجه، reason code امن، correlation و در صورت موفقیت شناسهٔ server-generated حساب را ثبت می‌کنند. شمارهٔ کامل، ciphertext هویت، OTP، رمز، Token، Cookie و مسیر Session/Storage در log یا audit مجاز نیست. رد شدن هویت متعلق به کاربر دیگر با پاسخ عمومی `messenger_account_identity_unavailable` ثبت می‌شود تا امکان account enumeration ایجاد نشود.

### رخدادهای Provider Extension

Phase 11-B0 چهار رخداد activation به Catalog افزوده است:

- `provider_adapter_activation_started`
- `provider_adapter_activation_succeeded` با audit
- `provider_adapter_activation_rejected` با audit
- `provider_adapter_activation_failed`

payload فقط provider id، implementation state، account id سرورساز، correlation و safe reason code را می‌پذیرد. exception خام SDK، endpoint، request/response، Token، Cookie، challenge و session material ممنوع است.

Phase 11-B1 دو رخداد دیگر افزوده است:

- `provider_registry_reconciled`: فقط شمار created/updated/unchanged و provider_count؛
- `provider_capability_check_rejected`: فقط account id سرورساز، نام Capability و reason code امن.

شمار رخدادهای canonical پس از تکمیل محلی 11-B2 برابر ۸۶ است. تغییر Registry/Capability/Event Catalog trigger اجرای دوبارهٔ contract، full regression و PII scan است.

### رخدادهای Provider operation

Phase 11-B2 چرخهٔ اجرای application عمومی و receipt پایدار را با هشت رخداد ثبت می‌کند:

- `provider_operation_started`
- `provider_operation_succeeded`
- `provider_operation_rejected`
- `provider_operation_failed`
- `provider_operation_uncertain`
- `provider_operation_idempotency_replayed`
- `provider_operation_idempotency_interrupted`
- `provider_operation_adapter_close_failed`

فیلدها فقط شناسهٔ سرورساز حساب، Provider، operation، capability، correlation، reason code، outcome/receipt source امن، error type و duration هستند. متن پیام، هویت مخاطب، idempotency key، fingerprint درخواست، exception message، raw result و مسیر فایل ثبت نمی‌شوند. replay idempotent نیز پیش از بازگشت پاسخ authorization/capability را دوباره اجرا می‌کند؛ attempt منقضی‌شده با رخداد interrupted و نتیجهٔ uncertain ثبت می‌شود و retry خودکار ندارد.

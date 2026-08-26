# گزارش مستقل Phase 8-C: Account Rate, Retry and Circuit Policy

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: تکمیل‌شده و آزموده‌شده  
مرز گزارش: پایان 8-C؛ تست فشار و Audit export نهایی مربوط به 8-D است.

## نتیجهٔ اجرایی

سیاست اجرای پایدار و مستقل برای هر `MessengerAccount + OperationScope` ساخته و به Jobهای پایدار API متصل شد. Schema Coordinator از نسخهٔ ۳ به ۴ مهاجرت می‌کند و Token bucket، Retry gate و Circuit state را نگه می‌دارد.

اجزای پیاده‌سازی‌شده:

- `AccountExecutionPolicyService` با Acquire/RecordSuccess/RecordFailure/State؛
- Token bucket تراکنشی با Capacity، Refill و Cost؛
- `retry_not_before` پایدار و احترام به `retry_after` Provider تا ۲۴ ساعت؛
- Backoff نمایی داخلی با سقف ۶۰ ثانیه؛
- Circuit breaker با آستانهٔ پیش‌فرض ۵ Failure، Open duration کران‌دار و یک Probe fenced در `half_open`؛
- Claim UUID برای جلوگیری از چند Probe هم‌زمان؛
- taxonomy دقیق `transient/auth/privacy/permanent/uncertain/internal`؛
- `ClassifiedFailure`، `ExecutionPermit` و `FailureDecision` با safe summary؛
- Audit امن موفقیت/Failure سیاست، بدون متن خام Provider؛
- اتصال به چرخهٔ Persistent Job: Acquire پیش از Lease، ثبت Failure، Retry scheduling و Reset بر اثر Success؛
- ممنوعیت fallback: Policy فقط همان Account ID انتخاب‌شده را می‌پذیرد و هیچ API برای انتخاب حساب جایگزین ندارد.

## قواعد Retry

| کلاس | Retry خودکار | Circuit | نتیجهٔ Job |
|---|---|---|---|
| transient | بله، backoff + retry_after | پس از آستانه Open | failed→pending |
| internal | بله، محافظه‌کارانه و کران‌دار | پس از آستانه Open | failed→pending |
| auth | خیر | Open تا Reset صریح | failed |
| privacy | خیر | Open تا Reset صریح | failed |
| permanent | خیر | Closed برای درخواست‌های مستقل بعدی | failed |
| uncertain | هرگز | Open تا Reconciliation صریح | uncertain |

زمان `retry_after` Provider هرگز با زمان کوتاه‌تر Backoff یا Circuit جایگزین نمی‌شود. در آزمون، retry_after برابر ۱۲۰ ثانیه حتی پس از پایان Open window سی‌ثانیه‌ای همچنان مانع Probe شد.

## آزمون مستقل 8-C

فایل: `tests/test_phase8c_account_execution_policy.py`

سناریوها:

- مهاجرت تراکنشی schema 3→4 و بررسی checksum/foreign keys؛
- شش آزمون taxonomy برای تمام کلاس‌ها؛
- مصرف کامل Token حساب A و اثبات فعال‌ماندن مستقل حساب B، بدون fallback؛
- Retry-after پنج‌ثانیه‌ای و backoff؛
- پنج Failure متوالی و Open شدن Circuit؛
- حفظ Retry-after ۱۲۰ ثانیه‌ای پس از Circuit window؛
- رقابت هشت Claim در Half-open با دقیقاً یک Probe مجاز؛
- Success Probe و بازگشت Circuit به Closed؛
- Auth/Privacy/Uncertain بدون Retry خودکار و نیازمند Reset؛
- Permanent failure بدون مسدودکردن درخواست مستقل بعدی؛
- اتصال واقعی API helper به Job پایدار، تبدیل Timeout به transient و pending شدن Retry؛
- رد Job بعدی همان حساب و اثبات عدم ایجاد State در حساب دیگر.

## نتایج آزمون

- مجموعهٔ هدف 8-C و سازگاری API/Phase7/Phase8-B: ۹۸ آزمون موفق.
- کل مجموعه: ۴۶۳ آزمون موفق، بدون failure.
- Compile کل `src`: موفق.

فرمان QA نهایی:

```text
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-phase8c-full
```

## کنترل ایمنی

- هیچ عملیات واقعی Provider، Login/OTP/Sync/Send یا WordPress اجرا نشد.
- هیچ حسابی برای دورزدن محدودیت حساب دیگر انتخاب نشد.
- هیچ Port/Firewall/Service/Router تغییر نکرد.
- `bridge.json` واقعی دست‌نخورده و SHA-256 آن همچنان `D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89` است.
- هیچ Git reset/checkout/stage/commit/push انجام نشد.

## ورودی 8-D

8-D باید Correlation کامل Job/Lease/Attempt/Retry، Query/Export امن Audit و تست فشار حداقل دو AppUser و سه Fake account را با restart/crash/cancel و اثبات نبود نشت تکمیل کند.

## الحاقیهٔ QA نهایی Phase 8

در بازبینی نهایی، taxonomy برای `provider_not_authorized` و `recipient_not_found` سخت‌گیری شد و وابستگی به token عمومی `not` حذف گردید. فایل مستقل 8-C اکنون ۱۳ آزمون جمع‌آوری‌شده دارد؛ اجرای هدفمند مشترک 8-C/8-D برابر ۱۷/۱۷ و اجرای کل نهایی برابر ۴۶۹/۴۶۹ موفق است.

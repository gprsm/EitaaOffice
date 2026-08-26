# گزارش مستقل Phase 8-B: Persistent Coordinator Jobs

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: تکمیل‌شده و آزموده‌شده  
مرز گزارش: پایان 8-B؛ سیاست Rate limit/Retry/Circuit breaker مربوط به 8-C است.

## نتیجهٔ اجرایی

Jobهای Coordinator از حالت صرفاً درون‌حافظه‌ای به مدل تراکنشی پایدار ارتقا یافتند. Schema Coordinator از نسخهٔ ۲ به ۳ مهاجرت می‌کند و دادهٔ Owner/Account، Lease، Attempt، Cancellation، Error و Recipient reference را نگه می‌دارد.

اجزای اصلی:

- `PersistentOperationJobService` با Create/Get/Lease/Start/Renew/Complete/Cancel/Recover؛
- مدل‌های امن `OperationJobRecord`، `JobAttemptRecord`، `CreateJobResult` و `JobRecoverySummary`؛
- جدول `operation_job_recipients` با SHA-256 reference و PK ترکیبی برای حذف گیرندهٔ تکراری؛
- ستون‌های `attempt_count`، `cancel_requested_at`، `cancelled_at` و آخرین Error در `operation_jobs`؛
- مهاجرت تراکنشی schema 1→3 و 2→3 با checksum نسخه‌ای و `foreign_key_check`؛
- کنترل Owner/Membership در همان تراکنش ساخت Job؛
- Idempotency پایدار با رد Owner mismatch و Payload/Recipient mismatch؛
- Lease fencing با Worker UUID، Generation و Expiry؛
- Retry attempt پایدار با حفظ شمارهٔ Attempt؛
- Recovery تفکیک‌شده: `leased→pending` و `running→uncertain`؛
- Cancellation فوری برای pending/leased و cooperative برای running؛
- API glue برای Jobهای background عمومی، Dialog sync، Content Index و Contact imports در حالت چندنشستی؛
- تمدید دوره‌ای Lease عملیات طولانی و توقف تمدید هنگام Completion/Close؛
- Status fallback از Coordinator پس از Restart، بدون افشای Job کاربر یا حساب دیگر.

## رفتار Crash/Restart

| وضعیت هنگام قطع | نتیجهٔ Recovery | دلیل |
|---|---|---|
| Pending | Pending | هنوز تحویل Worker نشده است |
| Leased، بدون Attempt | Pending | اثر بیرونی شروع نشده است |
| Running، Attempt باز | Uncertain | ممکن است اثر Provider انجام شده باشد |
| Cancel خواسته‌شده قبل از Start | Cancelled | اجرا آغاز نشده است |
| Terminal | بدون تغییر | ثبت دوباره ممنوع است |

نتیجهٔ `uncertain` خودکار retry نمی‌شود؛ این مرز مانع ارسال یا عملیات تکراری پس از Crash است.

## آزمون مستقل 8-B

فایل: `tests/test_phase8b_persistent_jobs.py`

هفت سناریوی اصلی:

- مهاجرت واقعی Coordinator نسخهٔ ۲ به ۳ و حفظ checksum/foreign keys؛
- Idempotency پس از ساخت Service جدید و حذف Recipient تکراری؛
- رد استفاده از Idempotency متعلق به AppUser دیگر؛
- رقابت هشت Worker برای یک Job با دقیقاً یک برنده؛
- Retry، Attempt دوم، Restart Service و Completion دقیقاً یک‌بار؛
- Crash در حالت running→uncertain و Lease منقضی بدون Start→pending؛
- Cancellation قبل و حین اجرا و اتصال واقعی API helper به UUID پایدار/Status پس از Restart.

## یافتهٔ QA و بهبود جانبی

اجرای کامل یک Flake قدیمی Phase 7-D را آشکار کرد. هم‌زمانی ساخت دو Worker در Windows گاهی هنگام materialize شدن Parent، `Path.resolve(strict=False)` را برای `worker_cache_directory` موقتاً خارج از Root گزارش می‌کرد. اصلاح انجام‌شده:

- ابتدا بررسی lexical containment بدون اتکا به وضعیت لحظه‌ای فایل‌سیستم؛
- retry بسیار کوتاه فقط در Windows و فقط برای Candidate از پیش ثابت‌شده داخل Root؛
- Junction/Symlink واقعی خارج از Root همچنان در همهٔ تلاش‌ها Fail-closed رد می‌شود.

آزمون race پس از اصلاح ۲۰ بار متوالی موفق شد.

## نتایج آزمون

- مجموعهٔ هدف API/Coordinator/Jobs: ۱۰۰ آزمون موفق.
- آزمون مستقل 8-B: ۷ آزمون موفق.
- race Phase 7-D پس از اصلاح: ۲۰/۲۰ موفق.
- کل مجموعه: ۴۵۲ آزمون موفق، بدون failure.
- Compile کل `src`: موفق.

فرمان QA نهایی:

```text
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-phase8b-full3
```

## کنترل ایمنی

- هیچ Provider واقعی، Login/OTP/Sync/Send یا WordPress واقعی فراخوانی نشد.
- هیچ Port/Firewall/Service/Router تغییر نکرد.
- `bridge.json` واقعی دست‌نخورده ماند؛ SHA-256 برابر `D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89` است.
- هیچ Git reset/checkout/stage/commit/push انجام نشد.

## ورودی مرحلهٔ 8-C

8-C باید سیاست مستقل هر حساب برای Rate limit، `retry_after`، Backoff کران‌دار، Circuit breaker و taxonomy خطاهای `transient/auth/privacy/permanent/uncertain/internal` را روی همین Job/Attempt contract اعمال کند؛ انتقال خودکار عملیات به حساب دیگر برای دورزدن محدودیت ممنوع است.

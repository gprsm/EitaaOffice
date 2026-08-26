# گزارش مستقل Phase 8-D: Correlation, Audit and Stress Acceptance

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: تکمیل‌شده و آزموده‌شده  
مرز گزارش: پایان 8-D و پایان اجزای اجرایی Phase 8؛ QA نهایی یکپارچه جداگانه ثبت می‌شود.

## نتیجهٔ اجرایی

Correlation کامل Job/Lease/Attempt/Retry، Query/Export امن Audit و تست فشار چندکاربر/چندحساب تکمیل شد. Schema Coordinator از نسخهٔ ۴ به ۵ مهاجرت می‌کند.

### Correlation و Lease journal

- جدول پایدار `job_leases` با Lease UUID، Worker UUID/Generation، Root-linked correlation، Status، Acquire/Expiry/Release؛
- Unique partial index برای دقیقاً یک Active Lease در هر Job؛
- ستون‌های `lease_id` و `correlation_id` در `job_attempts`؛
- Root correlation ثابت در `operation_jobs`؛
- Lease correlation و Attempt correlation جدید در هر Retry؛
- Audit رخدادهای Lease/Attempt/Retry با Root correlation در `request_id` و Child correlation در Metadata امن؛
- Renewal هم‌زمان در رکورد Job و Lease journal؛
- Release در Completion/Cancel و Expiry در Recovery.

### Audit query/export

سرویس `SafeCoordinatorAuditService` اضافه شد:

- مجوز admin/user و Scope کاربر؛
- فیلترهای Account، Provider، Action prefix، Result، Root correlation و بازهٔ زمانی؛
- Cursor محدود و اعتبارسنجی‌شده؛
- حذف `phone_account_id` از خروجی؛
- Redaction ثانویهٔ Password/Secret/Token/OTP/Ciphertext/Access Hash/Raw phone؛
- Verification کامل hash chain؛
- JSONL export اتمیک در Server-owned directory با نام UUID و SHA-256؛
- APIهای احرازشدهٔ `GET /api/v2/audit` و `POST /api/v2/audit/export`؛
- Export API فقط نام فایل، تعداد و Hash را برمی‌گرداند و مسیر مطلق را افشا نمی‌کند.

## تست فشار پذیرش

Fixture مستقل دارای:

- دو AppUser فعال: یک admin و یک user؛
- سه Fake MessengerAccount با Provider `eitaa` و بدون Session/Network واقعی؛
- ۷۲ Job هم‌زمان، ۲۴ Job برای هر حساب؛
- ۱۲ Thread برای Create و ۶ Worker مصرف‌کننده؛
- Recipient opaque hash مستقل؛
- Cancel پیش از Lease و cooperative cancel حین Run؛
- Retry صفرمیلی‌ثانیه‌ای با Attempt دوم؛
- Crash شبیه‌سازی‌شده با Attempt باز و Lease منقضی؛
- ساخت Service جدید و Recovery پس از Restart؛
- انتظار نهایی فقط `succeeded/cancelled/uncertain`؛
- صفر Active Lease، صفر foreign-key violation؛
- Query کاربر دوم فقط برای حساب سوم و بدون Event حساب‌های اول/دوم؛
- Verification نهایی Audit chain.

تست فشار کامل سه مرتبهٔ مستقل پشت سر هم موفق شد: ۲۱۶ Job fixture-run بدون Failure یا Leak.

## آزمون‌های دیگر

- مهاجرت schema 4→5 با checksum و foreign key؛
- یک Job با دو Retry cycle: دو Lease ID، دو Lease correlation، دو Attempt correlation و یک Root ثابت؛
- Query بر مبنای Root correlation و حضور همهٔ actionها؛
- Pagination admin و Scope user؛
- Export user و اثبات نبود دو Account ID غیرمجاز در بایت‌های فایل؛
- تطبیق SHA-256 فایل Export؛
- حذف عمدی Trigger در پایگاه تست، تغییر Event و شناسایی Tamper؛
- تست API query/export همراه Session و CSRF.

## نتایج آزمون

- مجموعهٔ هدف Coordinator/API/8-B/8-C/8-D: ۴۵ آزمون موفق.
- تست مستقل 8-D: چهار آزمون پذیرش موفق؛ Stress سه‌بار تکرار شد.
- کل مجموعه: ۴۶۷ آزمون موفق، بدون failure.
- Compile کل `src`: موفق.

فرمان QA نهایی بخش:

```text
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-phase8d-full
```

## کنترل ایمنی

- سه Account همگی Fake و بدون Session/Provider network بودند.
- هیچ Login/Logout/OTP/Sync/Send/WordPress واقعی اجرا نشد.
- هیچ Port/Firewall/Service/Router تغییر نکرد.
- `bridge.json` واقعی دست‌نخورده ماند؛ SHA-256 برابر `D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89` است.
- هیچ Git reset/checkout/stage/commit/push انجام نشد.

## الحاقیهٔ QA نهایی Phase 8

حالت Base64 خراب برای Cursor صفحه‌بندی Audit به آزمون رگرسیون افزوده شد و اکنون به‌صورت قطعی با کد امن `audit_cursor_invalid` رد می‌شود. اجرای هدفمند نهایی 8-C/8-D برابر ۱۷/۱۷ و اجرای کل نهایی برابر ۴۶۹/۴۶۹ موفق است.

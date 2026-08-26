# گزارش نهایی Phase 8 — Account Scope, Durable Jobs, Policy, Audit

تاریخ: ۲۰۲۶-۰۸-۱۱  
زمان پایان QA: ۲۳:۳۷ به وقت ایران  
وضعیت: **تکمیل‌شده و پذیرفته‌شده**

## نتیجهٔ نهایی

فاز ۸ به‌ترتیب 8-A تا 8-D پیاده‌سازی، به‌صورت مستقل گزارش و سپس روی یک نسخهٔ یکپارچه دوباره آزموده شد. مرز دادهٔ هر حساب، Jobهای پایدار Coordinator، سیاست نرخ/Retry/Circuit و زنجیرهٔ کامل Correlation/Audit اکنون در مسیر چندنشستی وجود دارند. مسیر Legacy حفظ شده و فعال‌سازی واقعی، مهاجرت دادهٔ واقعی یا تماس با Provider انجام نشده است.

## ماتریس زیرمرحله‌ها

| زیرمرحله | خروجی پذیرفته‌شده | آزمون مستقل | گزارش مستقل |
|---|---|---:|---|
| 8-A | Scope صریح `Provider + MessengerAccount` در Repository/Runtime/API، جداسازی Media و WordPress metadata | ۶ آزمون اختصاصی؛ QA مرحله‌ای ۴۴۵ موفق | `PHASE8A_ACCOUNT_SCOPED_DATA_REPORT_2026-08-11.md` |
| 8-B | Job پایدار با Owner/Account، Idempotency، Lease/Attempt، Cancel و Crash recovery | ۷ آزمون اختصاصی؛ QA مرحله‌ای ۴۵۲ موفق | `PHASE8B_PERSISTENT_COORDINATOR_JOBS_REPORT_2026-08-11.md` |
| 8-C | Token bucket حساب‌محور، Retry-after/Backoff، Circuit breaker و taxonomy خطا | ۱۳ آزمون اختصاصی؛ QA مرحله‌ای ۴۶۳ موفق | `PHASE8C_ACCOUNT_RATE_RETRY_CIRCUIT_REPORT_2026-08-11.md` |
| 8-D | Root/Lease/Attempt correlation، Audit query/export، hash-chain و پذیرش فشاری | ۴ آزمون اختصاصی؛ QA مرحله‌ای ۴۶۷ موفق | `PHASE8D_CORRELATION_AUDIT_STRESS_REPORT_2026-08-11.md` |

## کنترل یکپارچهٔ نهایی

- مجموعهٔ کامل Python: **۴۶۹/۴۶۹ موفق**، بدون failure؛ زمان اجرای نهایی ۶۵ ثانیه.
- آزمون هدفمند نهایی 8-C/8-D پس از hardening: **۱۷/۱۷ موفق**.
- Stress 8-D: سه اجرای مستقل، در مجموع ۲۱۶ Job آزمایشی؛ بدون نشت حساب، Active lease باقیمانده یا خطای foreign key.
- Compile کل `src`: موفق.
- سلامت dependencyهای Python (`pip check`): بدون dependency شکسته.
- کنترل whitespace/patch (`git diff --check`): موفق.
- TypeScript check: موفق.
- UI production build: موفق؛ ۹۷۷ module تبدیل شد.
- Scroll model: **۱۰/۱۰ موفق**.
- Grouped-media model: **۱۶/۱۶ موفق**.

دو مورد hardening در کنترل نهایی افزوده شد:

1. Cursor خراب Audit، از جمله Base64 نامعتبر، اکنون همواره به `audit_cursor_invalid` کنترل‌شده تبدیل می‌شود و به خطای داخلی نشت نمی‌کند.
2. `provider_not_authorized` به‌درستی Auth و `recipient_not_found` به‌درستی Permanent طبقه‌بندی می‌شوند؛ وابستگی خطرناک به token عمومی `not` حذف شد.

## معیارهای ایمنی و عدم مداخله

- هیچ Login، Logout، OTP، Sync، Send یا درخواست واقعی Eitaa/WordPress اجرا نشد.
- هیچ دادهٔ واقعی مهاجرت نشد و هیچ Port، Firewall، Service یا Router تغییر نکرد.
- فایل واقعی `bridge.json` نوشته نشد؛ اندازهٔ آن **۹۳۴ بایت** و SHA-256 آن همچنان زیر است:

```text
D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89
```

- تغییرات قبلی Worktree حفظ شد؛ هیچ reset، checkout، stage، commit یا push انجام نشد.
- مسیر چندنشستی روی تنظیم واقعی فعال نشد؛ بنابراین پذیرش Phase 8 کدنویسی/آزمون است و Rollout واقعی محسوب نمی‌شود.

## محدودیت و بدهی ثبت‌شده

Build رابط موفق است، اما Vite یک هشدار غیرمسدودکننده برای chunk اصلی JavaScript با اندازهٔ ۸۷۳٫۵۶ kB (gzip برابر ۲۶۰٫۳۲ kB) ثبت کرد. Code splitting در Phase 9 می‌تواند این مورد را بهبود دهد؛ این هشدار correctness یا پذیرش Phase 8 را نقض نمی‌کند.

## وضعیت ورود به Phase 9 و Phase 10

Phase 8 بسته شد و ورودی Phase 9 آماده است. ادامهٔ پنج‌دقیقه‌ای باید فقط وقتی اجرا شود که در فاصلهٔ مقرر دستور تازه‌ای از کاربر نرسیده باشد و خود سامانه با محدودیت اجرایی/سهمیه روبه‌رو نباشد.

پس از پذیرش کامل Phase 9، Phase 10 فقط تا مرز عملیات امن و غیرمخرب می‌تواند خودکار پیش برود. توقف برنامهٔ واقعی، Backup/مهاجرت واقعی، Bootstrap مدیر، فعال‌سازی Multi-session، تغییر Firewall/LAN، Login حساب واقعی یا Send واقعی در 10-A تا 10-D دروازهٔ تأیید و همکاری کاربر هستند و نباید در غیاب او اجرا شوند.


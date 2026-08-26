# گزارش G-08-D — سلامت logger، retention و Support Bundle

تاریخ: 2026-08-26  
Run: `STAB-G08-R01`  
وضعیت: `ADVERSARIAL_AND_RELATED_GREEN / AUTO_CONTINUE_G08_E`

## RED و اصلاح

RED canonical D برابر `4/4 failed` بود: write failure از logger بیرون می‌آمد، retention/disk API نبود، JSONL ناقص bundle عادی نمی‌شد و scanner نام archive/member را بازتاب می‌داد. endpoint health نیز جداگانه با 404 RED شد.

اصلاح‌ها:

- RuntimeLogger هم exception مستقیم handler و هم `handleError` داخلی logging را بدون چاپ record خصوصی مهار و در counter monotonic ثبت می‌کند؛ health فقط status/count/error type دارد.
- retention فقط application/worker current و rotation عددی مستقیم را می‌شناسد؛ symlink را رد می‌کند، current را هرگز حذف نمی‌کند و age/count/total budget دارد.
- disk-health فقط available/minimum bytes و `healthy/degraded/unknown` برمی‌گرداند.
- maintenance startup نتیجهٔ diagnostics/runtime rotation/disk را با event امن ثبت می‌کند؛ endpoint `GET /api/v2/observability/health` policy و health path-free ارائه می‌دهد.
- Support Bundle برای JSONL معتبر semantic redaction و برای خط ناقص یک marker aggregate امن می‌نویسد؛ symlinkهای config/log/diagnostic/coordinator رد می‌شوند.
- scanner نام archive و member را با مقدار ثابت/opaque ref جایگزین می‌کند و مقدار خصمانه در report دیده نمی‌شود.

## آزمون و رخدادهای harness

- RED D=`4/4 failed` و endpoint RED=`1/1 failed (404)`.
- targeted نخست=`4/5 passed`: تنها اختلاف، محاسبهٔ fixture بود؛ سه فایل JSONL هرکدام 19 بایت و جمع واقعی 57 بود، نه 54. assertion تصحیح شد.
- targeted retry=`5/5 passed`.
- guard تکمیلی نخست در suite G08 برابر `12/13` بود؛ BrokenStream مصنوعی متدهای `seek/tell` لازم برای RotatingFileHandler را نداشت و به‌جای OSError هدف، AttributeError تولید کرد. فقط test double تکمیل شد.
- suite کامل G08=`13/13 passed`.
- privacy/Support/Phase10-D/API/account/audit related=`78/78 passed`.
- compile پنج فایل Python: PASS؛ اجرای معتبر failure/error/skip صفر.

## مرز عملیاتی

حذف retention فقط روی فایل‌های مصنوعی basetemp اجرا شد. هیچ log/rotation، config، diagnostic، bundle، حساب یا DB واقعی خوانده/حذف/بازنویسی نشد. هیچ Provider، Login/OTP/Send، Bale، network یا Git mutation انجام نشد.

Catalog اکنون 103 رخداد دارد. F-048 از نظر پیاده‌سازی A تا D سبز است و فقط full regression/closure اسناد G-08-E باقی مانده است.


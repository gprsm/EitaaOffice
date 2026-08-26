# گزارش G-05-A — RED lifecycle ایندکس خودکار

تاریخ: 2026-08-26  
Run: `STAB-G05-R01`  
Ledger: `V-122`  
وضعیت: `RED_VERIFIED / AUTO_CONTINUE_G-05-B`

## هدف و مرز

F-043 با تست کاملاً آفلاین سنجیده شد. هیچ Provider، شبکه، پیام، حساب واقعی یا دادهٔ عملیاتی استفاده نشد؛ API، config، DB و application log همگی زیر basetemp بودند.

## نتیجه

`tests/test_g05_auto_index_lifecycle_stabilization.py` چهار قرارداد دارد:

| قرارداد | نتیجهٔ A |
|---|---|
| safe-default نباید thread خودکار بسازد یا پس از close باقی بگذارد | RED |
| غیرفعال‌بودن scheduler باید event cataloged و correlated داشته باشد | RED |
| loop نامحدود و swallowing خاموش باید از source حذف شود | RED |
| route/methodهای manual content index باید حفظ شوند | PASS |

نتیجهٔ کلی=`1/4 passed`, `3/4 failed`، بدون retry یا failure محیطی. target thread در تست کنترل‌شده بود و پس از ثبت failure آزاد/join شد.

## تصمیم ادامه

مطابق مسیر امن برنامه، G-05-B scheduler ناقص را fail-closed غیرفعال و کد loop را حذف می‌کند. یک event امن با correlation ثبت می‌شود و APIهای manual index تغییر نمی‌کنند. فعال‌سازی scheduler در آینده به feature/config و طراحی مستقل lifecycle/account scope نیاز دارد.

F-043 باز است و B طبق مجوز اجرای خودکار کاربر ادامه می‌یابد.

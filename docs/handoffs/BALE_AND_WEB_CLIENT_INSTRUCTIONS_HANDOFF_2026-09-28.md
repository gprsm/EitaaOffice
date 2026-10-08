# Handoff دستورهای بله و کلاینت وب

تاریخ: 2026-09-28 — تحویل فقط اسناد؛ تمام توسعه و پذیرش Live برنامه PLANNED است.

## اولین اقدام عامل بعدی

AGENTS و منابع الزامی‌اش را بخوان؛ سپس [قواعد مشترک](../implementation-plans/bridge-client-2026-09-28/EXECUTION_RULES.md) و [دفتر وضعیت](../implementation-plans/bridge-client-2026-09-28/EXECUTION_STATUS.md). HEAD و dirty/untracked واقعی را ثبت و فایل‌های کاربر و دادهٔ عملیاتی را حفظ کن.

- دستور اول: [تکمیل بله](../implementation-plans/bridge-client-2026-09-28/BALE_FULL_PRODUCT_INTEGRATION.md)، از B0 و inventory/RED معنایی آغاز کن. backend مستقل موجود را متصل کن؛ runtime/worker/contact/API/UI عمومی هنوز خروجی آینده‌اند.
- دستور دوم: [برنامهٔ وب](../implementation-plans/bridge-client-2026-09-28/WEB_CLIENT_PROGRAM.md)، فایل فاز تعیین‌شده را اجرا کن؛ پیش‌نیازها فقط با گزارش واقعی پذیرفته‌اند. در نبود تعیین فاز، نخست P1 است.

هیچ گزارش اجرای فاز یا پذیرش Live با تهیهٔ این بسته ایجاد نشده. V-194 شاهد تازهٔ مخاطب‌نویسی نیست. F-092 باز است؛ F-090/F-091 بسته با حدود درون‌فرایندی قبلی باقی‌اند. endpointهای پیشنهادی را موجود فرض نکن.

## اختیارات و مانع‌ها

این تحویل اجازهٔ login/send/import آنلاین، تغییر تنظیم عملیاتی یا استقرار نمی‌دهد. کارهای مستقل offline را کامل کن و بعد برنامهٔ محدود Pilot را برای مجوز همان لحظه ارائه بده. missing Live input فقط پذیرش وابسته را متوقف می‌کند. credential و دادهٔ خصوصی اینجا ثبت نشوند.

مرجع نتیجهٔ تهیه: [گزارش اسناد](../reports/features/BALE_AND_WEB_CLIENT_INSTRUCTIONS_2026-09-28.md) و V-226؛ [فهرست تمام فایل‌ها](../implementation-plans/bridge-client-2026-09-28/README.md).

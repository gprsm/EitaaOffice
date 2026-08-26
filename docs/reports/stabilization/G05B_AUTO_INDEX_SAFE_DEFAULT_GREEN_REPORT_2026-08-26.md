# گزارش G-05-B — safe-default ایندکس خودکار

تاریخ: 2026-08-26  
Run: `STAB-G05-R01`  
Ledger: `V-123`  
وضعیت: `TARGETED_AND_RELATED_GREEN / AUTO_CONTINUE_G-05-C`

## اصلاح

- thread ساعتی daemon و loop نامحدود `_run_auto_indexer` از startup/API حذف شدند.
- event `content_auto_index_scheduler_skipped` در Event Catalog ثبت و هنگام startup با correlation، reason امن و metadata محدود منتشر می‌شود.
- route/methodهای manual content index تغییر نکردند.

این safe-default feature تازه نمی‌سازد؛ scheduler تا طراحی صریح config/lifecycle/account scope خاموش است.

## آزمون

- G-05 اختصاصی: `4/4 passed`.
- regression مرتبط API، content index، account runtime، observability و clean-install: `76/76 passed`.
- failure محیطی، retry یا patch ثانویه وجود نداشت.

همهٔ ورودی‌ها و فایل‌ها مصنوعی بودند. هیچ Provider، شبکه، Login/OTP/Send، Bale، دادهٔ عملیاتی یا Git mutation انجام نشد. F-043 تا guardهای C، regression D و finalization E باز است.

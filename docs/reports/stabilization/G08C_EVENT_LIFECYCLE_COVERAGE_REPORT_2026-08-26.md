# گزارش G-08-C — پوشش Event Catalog و lifecycle کارهای پس‌زمینه

تاریخ: 2026-08-26  
Run: `STAB-G08-R01`  
وضعیت: `TARGETED_AND_RELATED_GREEN / AUTO_CONTINUE_G08_D`

## RED

چهار قرارداد C ابتدا `4/4 failed` شدند: پنج event content-index/read-receipt در Catalog نبود، background موفق رخداد متوازن نداشت، background ناموفق فقط `background_task_failed` می‌نوشت و manual/best-effort failureها event صریح نداشتند.

## اصلاح

- background عمومی با `observed_operation` و correlation منتقل‌شده، `operation_started/succeeded/failed` متوازن تولید می‌کند؛ رخداد اختصاصی failure نیز حفظ شد.
- manual content-index رخداد started/succeeded/cancelled/failed و cleanup-failed دارد.
- read-receipt best-effort دیگر exception را خاموش نمی‌بلعد و warning امن `read_receipt_failed` می‌نویسد.
- unexpected lease-renew failure با event موجود و error type امن بسته می‌شود.
- ساخت runtime پس از ایجاد logger، shutdown موفق/ناموفق و failure بستن auth runtime رخداد lifecycle صریح دارند.
- Event Catalog از 92 به 102 رخداد رسید. هیچ payload، peer، مسیر یا exception message تازه‌ای ثبت نمی‌شود.

## آزمون

- RED C=`4/4 failed`؛ GREEN C=`4/4 passed`.
- regression مرتبط lifecycle/content/account/API/contact/persistent/observability=`98/98 passed`.
- اجرای broad نخست اشتباهاً دو RED از پیش‌برنامه‌ریزی‌شدهٔ D را نیز وارد کرد و فقط همان دو health/retention test شکست خوردند؛ C tests و 102 تست دیگر سبز بودند. اجرای دامنهٔ صحیح بدون REDهای D برابر `98/98` شد. این رخداد scope-selection است، نه regression محصول.
- compile سه فایل محصول: PASS؛ failure/error/skip در اجرای معتبر صفر.

## Traceability و مرز

pre-imageهای سه فایل محصول از archive نهایی بایت‌یکسان G-07-E به‌صورت read-only بازیابی و با Ledger پیشین تطبیق شدند: API=`d5f3bde0...`، account runtime=`7b307862...` و Catalog=`3b60cae...`.

post-imageها: API=`cdc21b9a...`، account runtime=`8dfee07d...`، Catalog=`f4e96b84...` و test=`d0a7738f...`.

همهٔ اجراها روی config/runtime مصنوعی test بودند؛ Provider/Send/Login/OTP، Bale، log عملیاتی، دادهٔ واقعی یا Git state لمس نشد. F-048 برای write-health/retention/Support Bundle در D و closure در E باز است.


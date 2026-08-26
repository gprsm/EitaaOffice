# گزارش G-06-D — regression گسترده Backend

تاریخ: 2026-08-26  
Run: `STAB-G06-R01`  
Ledger: `V-130`  
وضعیت: `BROAD_BACKEND_GREEN / AUTO_CONTINUE_G-06-E`

۳۵ suite آفلاین مرتبط با test integrity، G-04/G-05، clean install، account/application/auth، coordinator، diagnostics/observability، content index و Phaseهای 4/6/8/9/10/11 اجرا شد. نتیجهٔ canonical برابر `307/307 passed` با failure/error/skip صفر است. collect-only مستقل نیز `307 tests collected` را ثبت کرد.

تنها warning مربوط به permission نوشتن nodeids در cache سراسری pytest بود؛ basetemp مستقل سالم ماند و exit code آزمون صفر بود. collect-only quiet عدد کل را در خروجی کوتاه نشان نداد، بنابراین collection بدون quiet و با cacheprovider خاموش تکرار شد؛ این retry اجرای تست محصول نبود.

هیچ package/installer، Provider network، Login/OTP/Send، دادهٔ عملیاتی، توسعهٔ Bale یا Git mutation انجام نشد. E full Backend و closure حوزهٔ قرارداد آزمون را انجام می‌دهد؛ بسته‌بندی همچنان G-07 است.

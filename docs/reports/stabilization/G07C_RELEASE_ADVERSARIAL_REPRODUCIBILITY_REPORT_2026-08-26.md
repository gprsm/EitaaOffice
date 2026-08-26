# گزارش G-07-C — adversarial archive و reproducibility

تاریخ: 2026-08-26  
Run: `STAB-G07-R01`  
Ledger: `V-134`  
وضعیت: `ADVERSARIAL_REPRODUCIBLE_GREEN / AUTO_CONTINUE_G-07-D`

guardهای collision بدون حساسیت حروف، tamper هش و حفظ خروجی موجود افزوده شدند و package suite برابر `11/11` سبز شد.

دو archive مستقل در artifacts ساخته شدند. هر دو 296 فایل allowlisted، 297 entry با manifest، اندازهٔ 2,031,927 بایت و SHA-256 یکسان `3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903` دارند. receiptها، content-set و verifier نیز منطبق‌اند.

اسکن مستقل اول 13 false-positive برای moduleهای nested diagnostics، Bale slot fail-closed و wheelهای `vendor/runtime` داد؛ پس از محدودکردن تعریف دادهٔ عملیاتی به top-level، forbidden=0 و collision=0 شد. یک خطای quoting verifier ثبت و با invocation ساده اصلاح شد.

هیچ installer/publish یا عملیات Live انجام نشد. D archive را فقط در محل ایزوله extract و قرارداد fresh-install را بدون نصب واقعی می‌سنجد.

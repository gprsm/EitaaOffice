# گزارش G-06-A — ممیزی قرارداد آزمون و RED Phase 10

تاریخ: 2026-08-26  
Run: `STAB-G06-R01`  
Ledger: `V-127`  
وضعیت: `RED_VERIFIED / AUTO_CONTINUE_G-06-B`

## وضعیت واقعی F-042

- شکست Bale BOM در G-02 بسته است و باز نمی‌شود.
- Phase 11 onboarding در G-04 برابر `7/7` سبز و بسته است.
- packaging طبق برنامه در G-07 می‌ماند و در G-06 دست‌کاری نمی‌شود.
- تنها RED جاری، runner Phase 10 است که پس از پنج PASS، helper واردشده از `utils/helpers.tsx` را به‌اشتباه داخل `App.tsx` جست‌وجو می‌کند.

## guard تازه

یک guard AST سه قرارداد دارد: نبود test خالی، reasonدار/conditional بودن skip/xfail و import-contract Phase 10. نتیجهٔ canonical=`2/3 passed`, `1/3 failed`؛ فقط مورد سوم RED است.

اجرای نخست guard دو failure fixture ناشی از BOM reader داشت؛ با `utf-8-sig` اصلاح شد. خطاهای quoting، wildcard و حدس پسوند helper نیز جدا به‌عنوان audit-tool ثبت شدند و هیچ‌کدام failure محصول نیستند.

هشت runner دیگر UI همگی سبزند. G-06-B runner Phase 10 را به فایل واقعی helper متصل و verbosity assertion تغییر‌یافته را محدود می‌کند؛ هیچ کد محصول UI نیازمند rollback نیست.

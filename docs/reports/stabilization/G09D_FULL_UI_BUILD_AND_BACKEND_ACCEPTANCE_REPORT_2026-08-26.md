# گزارش G-09-D — پذیرش کامل UI، build و Backend

تاریخ: 2026-08-26  
Run: `STAB-G09-R01`  
وضعیت: `FULL_AUTOMATED_ACCEPTANCE_GREEN / AUTO_CONTINUE_G09_E`

## نتیجهٔ Backend

مجموعهٔ کامل Backend با cache غیرفعال و basetemp تازه در اجرای نخست exit code صفر داد: `656/656 passed`، failure/error/skip صفر. collect-only مستقل نیز `656` مورد و exit code صفر را ثبت کرد. به این ترتیب پذیرش G-09 به شاهد قدیمی G-08 اکتفا نکرد.

آزمون کامل شامل 13 قرارداد G-08 برای scanner چندحسابی، malformed fail-closed، logger health، retention/disk و Support Bundle است. همراه با privacy scan صفر یافتهٔ archive در G-09-B، معیار privacy/log scan نهایی به‌صورت آفلاین و مصنوعی پوشش دارد؛ هیچ log واقعی اسکن نشد.

## نتیجهٔ UI و TypeScript

هر ۹ runner در اجرای نخست سبز شد:

- scroll=`10/10`
- grouped-media=`16/16`
- Phase 9 workspace=`12/12` و `15/15`
- Phase 9 acceptance=`13/13`
- Phase 10 local activation=`7/7`
- observability UI/Electron=`PASS`
- Phase 11 onboarding=`7/7`
- Phase 11-B2=`6/6`
- mobile-auth/live static contract=`PASS`

TypeScript check exit code صفر داشت. `npm run build` نیز 1015 module را تبدیل کرد و exit code صفر داد. bundle اصلی 794741 byte و SHA-256=`6659940b0dd49cf0a0cff3f5e23b200e7f5cdc8529ecf7a89373f3f379f17461` است. هشدار chunk بزرگ‌تر از 500 kB همان warning غیرمسدودکنندهٔ ثبت‌شدهٔ G-06-C است؛ خطای build نیست.

## ممیزی تغییر امن

Git status فقط read-only و با safe-directory موقت همان فرمان خوانده شد. worktree مطابق baseline عمداً dirty است و normalize/stage/commit نشد. در status جاری هیچ ردیف root-level برای `bridge.json`، `.env`، `data/`، `runtime/`، `diagnostics/` یا `backups/` وجود نداشت. این ممیزی clean بودن کل tree را ادعا نمی‌کند؛ فقط مرز دادهٔ عملیاتی این اجرا را تأیید می‌کند.

RED تازه اجرا نشد، چون D مرحلهٔ پذیرش تجمیعی پس از بسته‌شدن REDهای اهداف قبلی است و source/test تازه‌ای تغییر نداده است. تمامی suiteهای مرکزی در همین اجرای نهایی سبز شدند.

## نتیجه

پذیرش فنی G-09-D برابر `FULL_AUTOMATED_ACCEPTANCE_GREEN` است. G-09-E باید Baseline، Findings، Ledger، plan، گزارش نهایی و handoff را همسو و وضعیت واقعی انتشار را بدون ادعای پذیرش Live یا نصب سیستمی اعلام کند.

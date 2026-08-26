# گزارش G-00 — Traceability و Baseline قابل‌بازگشت

وضعیت: `BASELINED / GIT_HISTORY_CONNECTED / NO_STAGE_NO_COMMIT`  
Run: `STAB-G00-R01`  
زمان: 2026-08-25T22:58:22.9642834+03:30 تا 2026-08-25T23:08:12.0018711+03:30  
یافته: `F-039`

## هدف

ایجاد نقطهٔ بازگشت امن برای فایل‌های محصولی، بازیابی metadata تاریخچهٔ Git پوشهٔ قبلی و فراهم‌کردن شواهدی که Codex و AntiGravity بدون اتکا به Chat بتوانند تغییرهای بعدی را ممیزی کنند.

## RED

- `git rev-parse --is-inside-work-tree` در ریشهٔ جدید exit code `128` داشت؛ repository وجود نداشت.
- تست تازهٔ baseline در collection با `ModuleNotFoundError` شکست خورد؛ ابزار baseline هنوز ساخته نشده بود.
- اجرای RED یک warning محیطی برای cache غیرقابل‌نوشتن pytest داشت؛ GREEN با `-p no:cacheprovider` اجرا شد تا warning با نتیجهٔ محصول مخلوط نشود.

## پیاده‌سازی

- `scripts/stabilization_baseline.py`: allowlist صریح برای source/tests/scripts/installer/docs و بخش‌های محصولی UI؛ archive deterministic؛ manifest داخلی؛ receipt بیرونی؛ verify مجدد نام‌ها و SHA-256 همهٔ فایل‌ها.
- `tests/test_stabilization_baseline.py`: اثبات exclusion داده‌های عملیاتی/dependencyها و determinism/hash verification.
- `.gitignore`: خروجی recovery محلی `artifacts/stabilization/` از نسخه‌گذاری خارج شد.
- repository جدید با شاخهٔ `stabilization` ایجاد و تاریخچهٔ commit‌شدهٔ `legacy/main` از پوشهٔ محلی قبلی fetch شد.

## GREEN و artifact

- تست هدفمند: `2 passed / 0 failed`.
- baseline واقعی: `613` فایل محصولی امن.
- archive SHA-256: `70908224926eb45791bdc504558478756328743f0a9f7b8355f19b30d73ca8ab`.
- content-set SHA-256: `d128912b0e14e2f5113a209d7fb403349379e9d372217dcfe252bfef0f08239a`.
- اندازهٔ archive: `1,978,353` بایت.
- manifest داخلی موجود؛ شمار فایل receipt و archive برابر؛ ورودی ممنوع عملیاتی در scope ریشه `0`.
- receipt: `artifacts/stabilization/STAB-G00-R01-safe-baseline.receipt.json`.
- snapshot: `artifacts/stabilization/STAB-G00-R01-safe-baseline.zip`.

بررسی مستقل نخست regex بیش‌ازحد گسترده داشت و ۷ نام مستندی را false positive شمرد. retry با محدودکردن الگو به scopeهای عملیاتی top-level، مقدار `0` داد. archive در تلاش نخست تغییر یا بازسازی نشد.

## Git و مالکیت

- تلاش نخست `git init` توسط sandbox انجام شد و host آن را `dubious ownership` دید.
- افزودن `safe.directory` سراسری به‌دلیل کاهش کنترل مالکیت رد شد و انجام نشد.
- metadata sandbox-owner به مسیر recovery داخل `artifacts/stabilization/` منتقل شد؛ سپس repository با مالک صحیح حساب ویندوز بازسازی شد.
- شاخهٔ محلی `stabilization` و remote-tracking `legacy/main` به commit تاریخی `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` متصل‌اند.
- هیچ checkout/reset/read-tree/stage/commit/tag/push اجرا نشد.

## محدودیت باقی‌مانده

index عمداً normalize نشده است؛ تا دستور صریح stage/commit، manifest و Execution Log شاهد canonical تغییرها هستند. AntiGravity نباید برای اصلاح status از reset، read-tree یا stage استفاده کند.

## اثر بیرونی

- بدون network؛ fetch فقط از پوشهٔ محلی قبلی.
- بدون تغییر data/runtime/session/config/diagnostics/backups/Bale.
- تنها artifact recovery امن، metadata Git و فایل‌های tooling/test/docs ایجاد شدند.


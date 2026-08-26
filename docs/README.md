# درگاه مستندات Eitaa Bridge

این پوشه مرجع canonical برای شناخت، توسعه، عملیات و تاریخچهٔ پروژه است. برای جلوگیری از دوباره‌کاری، ابتدا حافظهٔ مهندسی و سپس سند تخصصی مربوط خوانده شود.

## شروع سریع

- مشخصات و وضعیت قابلیت‌ها: `PROJECT_SPECIFICATION.md`
- معماری کلان: `ARCHITECTURE.md` و `../ARCHITECTURE_DECISIONS.md`
- ساختار پوشه‌ها و مالکیت فایل‌ها: `PROJECT_STRUCTURE.md`
- روال توسعه و تحویل: `DEVELOPMENT_GUIDE.md`
- افزودن Provider مجاز: `PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md`
- لاگ و عیب‌یابی: `LOGGING_AND_OBSERVABILITY.md`
- نقشهٔ معماری و نمادها: `project-map/ARCHITECTURE_MAP.md` و `project-map/PROJECT_FILE_MAP.md`
- حافظهٔ پایدار یافته‌ها: `project-memory/README.md`
- فهرست گزارش‌ها: `REPORTS_INDEX.md`

## طبقه‌بندی

- `project-memory/`: وضعیت جاری، یافته‌ها، تصمیمات و شواهد آزمون.
- `project-map/`: نقشهٔ معماری، فایل‌ها، کلاس‌ها و تابع‌ها.
- `reports/phases/`: گزارش‌های فازهای محصول.
- `reports/gmi/`: گزارش‌ها و artifactهای GMI.
- `reports/features/`: گزارش‌های UI و قابلیت‌های مستقل.
- `reports/architecture/`: گزارش‌های معماری تاریخی.
- `reports/validation/`: گزارش‌های validation عمومی.
- `reports/blockers/`: مانع‌های بیرونی، مجوزها و تصمیم‌های لازم برای ادامه.
- `handoffs/`: prompt و وضعیت تحویل برای ادامهٔ کار.
- `checklists/`: پذیرش دستی و نصب.
- `specifications/`: قراردادها و مشخصات قابلیت‌های خاص.
- سایر فایل‌های مستقیم `docs/`: راهنماها و قراردادهای canonical موضوعی.

## قاعدهٔ مرجع

گزارش تاریخی شاهد «آن زمان» است؛ وضعیت فعلی فقط از `project-memory/CURRENT_SYSTEM_BASELINE.md` و کد/آزمون جاری نتیجه‌گیری می‌شود. اگر گزارش تاریخی و Baseline تعارض داشتند، تعارض در `project-memory/FINDINGS_REGISTER.md` ثبت و حل شود.

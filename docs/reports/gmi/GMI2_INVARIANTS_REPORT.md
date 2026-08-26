# گزارش Invariant — GMI 2

مبنای مقایسه: نسخه پذیرفته‌شدهٔ GMI 1

## ثابت‌های تأییدشده

- Core wheel: بدون تغییر و byte-identical؛ SHA-256:
  `bd12add1866fcb0f25928f9f2b29229f1010e7253738f06ae42c3aa9cd1f23b0`
- Core SQLite schema: `9`
- `application/scheduler.py`: byte-identical
- تمام Workflowها و client/auth مربوط به WordPress: byte-identical
- `ui/src/lib/scrollMath.ts` و آزمون Scroll: byte-identical
- فایل‌های اصلی Installer و launcherها: byte-identical
- Runtime payload: بدون تغییر
- ارسال/دعوت گروهی و Member عملیات: بدون تغییر

## تغییرهای مجاز و محدود

- `application/api.py`: فقط route/job محلی ایندکس و مدیریت lifecycle آن.
- `facade.py`: فقط ارائهٔ `sender_key` محافظه‌کارانه برای user/self.
- UI message list: پنل فیلتر، badge پیشنهاد و گالری استنباطی.
- Installer setup/build: فقط literal هویت Wheel از dev26 به dev27.
- UI production assets: به‌علت تغییر UI بازسازی شده‌اند.

## Scheduler

Worker ایندکس مستقیماً از `_run_eitaa` استفاده نمی‌کند. آزمون API،
`_run_eitaa` را به شکست اجباری تبدیل کرد و Job همچنان روی thread مستقل
`local-content-index-*` کامل شد. عملیات واقعی ایتا همچنان تنها از Scheduler
واحد موجود عبور می‌کند.

## WordPress

نتایج ایندکس فقط پیشنهاد هستند. هیچ route ایندکس، نوشته، دسته یا tag وردپرس
را ایجاد یا اصلاح نمی‌کند. تاریخچهٔ Composition فقط به‌عنوان شواهد تأییدشدهٔ
آموزش خوانده می‌شود.

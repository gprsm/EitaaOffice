# گزارش Invariants نسخه GMI3

مقایسه مستقیم با ZIP پاک و امضاشده GMI2 انجام شد.

- Core Wheel: بدون تغییر.
- Core facade: بدون تغییر.
- Scheduler: بدون تغییر.
- Runtime: بدون تغییر.
- Installer: بدون تغییر.
- WordPress client/auth/composition stores: بدون تغییر.
- مدل `scrollMath.ts` و تست آن: بدون تغییر.
- Gallery inference model: بدون تغییر.

نتیجه hash comparison: `FROZEN_FILES=16`, `MISMATCHES=0`, `MISSING=0`.

تغییرات `App.tsx` مربوط به نمایش Workbench، فرمان focus تاریخ و پیشنهاد دسته Composer است. الگوریتم Scroll، pagination، read receipt، Core، WordPress write path و Scheduler بازنویسی نشده‌اند.

مسیر Contact Directory و Import هیچ فراخوانی `_run_eitaa` ندارد. Index worker نیز مطابق نسخه قبل local-only است. Lab چندحسابی در Runtime import نشده و هیچ RPC اجرا نمی‌کند.

# GMI4 — گزارش Validation

## نتیجهٔ نهایی

همهٔ کنترل‌های قابل اجرای آفلاین موفق بودند.

- Python compile: موفق.
- Source smoke: `31/31`.
- Installed Wheel smoke: `27/27` (چهار کنترل Lab فقط در Source اجرا می‌شوند).
- Runtime environment: Bridge `0.7.0.dev29` و محصول `0.7.0-ui-mvp6.1.1-gmi4` تأیید شد.
- TypeScript: موفق.
- Vite production build: موفق، `41` ماژول.
- Scroll model: `10/10`.
- Grouped-media model: `16/16`.
- Frozen invariants: `16/16` فایل، بدون اختلاف.

## کنترل‌های اختصاصی GMI4

- مخاطب بدون شماره و نام کاربری ولی با Eitaa User ID.
- Merge تکراری بر پایهٔ Eitaa User ID.
- رد تعارض «شمارهٔ یک مخاطب + شناسهٔ مخاطب دیگر».
- حفظ Opt-out و وضعیت غیرقابل‌ارسال پس از Import مجدد.
- Merge دسته‌ها بدون حذف دسته‌های قبلی.
- Import عضو از Snapshot محلی بدون Scheduler.
- Import فهرست Resolve‌شده بدون Resolve یا RPC تازه.
- عدم افشای Access Hash در Job و Contact API.
- حذف خودکار Opt-out از Target Builder.
- انتقال هدف فقط به فرم و حفظ Preview/تأیید ارسال.
- بررسی خودکار ارجاع هر دو Installer به Wheel `dev29`.
- نصب واقعی روی `.venv` موجود: موفق؛ Python `3.13.14`، Core `dev19` و Bridge `dev29/GMI4`.

## محدودیت محیط

`pytest` در محیط پاک آفلاین نصب نبود. به‌جای دانلود شبکه‌ای، Smoke مستقل Source/Wheel، Compile، TypeScript، Build و آزمون‌های مدل اجرا شد. پذیرش با حساب واقعی در Checklist جداگانه آمده است.

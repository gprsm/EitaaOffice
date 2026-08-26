# گزارش اعتبارسنجی GMI3

## نتایج نهایی

- Source smoke: `22/22` کنترل موفق.
- Installed Wheel smoke: `18/18` کنترل موفق در venv ایزوله با Bridge `0.7.0.dev28` و Core `0.6.0.dev19`.
- TypeScript: موفق.
- Vite production build: موفق، ۴۱ module.
- Scroll model: `10/10` موفق با ۵۰۰۰ پیام ترکیبی.
- Grouped-media model: `16/16` موفق.
- Python compileall برای `src/`, `lab/`, `scripts/`, `tests/`: موفق.
- Frozen invariant comparison: `16/16` فایل دقیقاً برابر GMI2.

## پوشش Smoke

Schema backup، چند شماره، چند دسته، dedup شماره، حذف امن دسته، Opt-out، CSV mapping، دسته ستون فایل، Import async، Cancel، API محلی بدون Scheduler، Target safety، جداسازی Scheduler/Session/DB در Lab، حذف گیرنده تکراری، و اعمال فوری اصلاح ایندکس.

## کنترل رابط

Build تولیدی شامل Index Workbench دو تب، فیلتر فرستنده/ایندکس/WordPress، اصلاح پیام و گالری، انتخاب خودکار دسته Composer، پرش تاریخ، Contact Directory چهار تب، Preview/Mapping فایل و Target Preview است. Breakpointهای ۹۰۰ و ۵۹۰ پیکسل بررسی ساختی شده‌اند.

## محدودیت محیط آزمون

مخزن پاک عمداً pytest را بسته‌بندی نمی‌کند و دسترسی PyPI در محیط فعلی timeout شد؛ بنابراین مجموعه قدیمی `pytest` دوباره اجرا نشد. به‌جای ادعای نادرست، Smoke بدون شبکه برای Source و Wheel، compileall و تست‌های Node اجرا و ثبت شده‌اند. آزمون پذیرش واقعی Windows همچنان لازم است.

## هش‌های هویتی

- Core Wheel: `bd12add1866fcb0f25928f9f2b29229f1010e7253738f06ae42c3aa9cd1f23b0`.
- Bridge Wheel نهایی در فایل SHA256 خروجی ثبت شده است.

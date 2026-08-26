# راهنمای توسعه و تحویل

## ۱. شروع کار

1. `AGENTS.md` و `project-memory/README.md` را بخوان.
2. وضعیت dirty و فایل‌های تغییرکرده را فقط‌خواندنی بررسی کن.
3. در `FINDINGS_REGISTER.md` دنبال شاهد موجود بگرد.
4. دامنهٔ تغییر، مرز امنیتی و آزمون لازم را مشخص کن.
5. فقط فایل‌های مرتبط را تغییر بده و تغییرهای نامرتبط کاربر را حفظ کن.

## ۲. محیط توسعه

- Python: نسخهٔ 3.11 یا جدیدتر؛ محیط محلی معمولاً `.venv`.
- Backend dependency: مطابق `pyproject.toml` و `requirements*.txt`.
- UI: Node/npm با نسخه‌های قفل‌شده در `ui/package.json` و lockfile.
- ورودهای CLI در `pyproject.toml`: `eitaa-bridge`, `eitaa-bridge-api`, `eitaa-bridge-windows-lan`, `eitaa-bridge-provider-worker`.
- `pytest` به‌کمک `pyproject.toml` مسیر `src` را در اولویت می‌گذارد؛ اجرای مستقیم `python -c` ممکن است نسخهٔ نصب‌شده در `.venv` را import کند. برای بررسی مستقیم source، `PYTHONPATH=src` تنظیم یا ماژول از entrypoint پروژه اجرا شود.

راه‌اندازی معمول ویندوز از launcherهای ریشه انجام می‌شود. اجرای مستقیم source برای توسعه مجاز است، اما credential فقط توسط کاربر و در UI وارد می‌شود.

## ۳. چرخهٔ تغییر

- قرارداد domain/application را پیش از UI تعریف کن.
- برای Provider از capability/adapter استفاده کن؛ شرط‌های پراکندهٔ `if provider == ...` ایجاد نکن.
- هر عملیات account-scoped باید `app_user_id`/actor، `account_id` و ownership را در مرز API و worker کنترل کند.
- عملیات طولانی باید job/worker، timeout، cancellation، retry و audit مشخص داشته باشد.
- رخدادهای جدید را ابتدا در `infrastructure/diagnostics/event_catalog.py` ثبت کن.
- دادهٔ log فقط allowlist؛ exception message/stack/URL/query/credential ممنوع.
- تست regression و privacy را هم‌زمان با تغییر اضافه کن.

## ۴. فرمان‌های بررسی

```powershell
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix ui run check
npm.cmd --prefix ui run build
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
```

آزمون‌های واقعی شبکه/حساب فقط وقتی لازم و مجازند اجرا شوند. شکست ناشی از invocation محیطی نیز با توضیح در Validation Ledger ثبت شود تا دوباره تکرار نشود.

## ۵. تعریف Done

- کد و contract متناظر تکمیل است.
- تست هدفمند و متناسب با ریسک موفق است.
- هیچ secret/PII یا مسیر حساس جدیدی در log/report نیست.
- Baseline، Findings، Validation Ledger و سند تخصصی مرتبط به‌روز شده‌اند.
- project map و reports index تازه‌اند.
- هیچ تغییر بیرونی یا واقعی بدون تأیید انجام نشده است.

## ۶. تغییر معماری و فاز جدید

تصمیم معماری پایدار در `../ARCHITECTURE_DECISIONS.md` با شمارهٔ جدید ثبت می‌شود. گزارش فاز در `reports/phases/` قرار می‌گیرد و تنها نتیجهٔ جاری به Baseline منتقل می‌شود. گزارش تاریخی بازنویسی نمی‌شود مگر برای اصلاح لینک یا خطای مستندی آشکار.

برای افزودن یا تغییر پیام‌رسان، ابتدا `PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md` و سند Discovery همان Provider خوانده شود. هیچ endpoint، auth flow، capability یا session format حدس زده نمی‌شود. registration تازه تنها پس از ثبت provenance/authorization و عبور از Fake/Contract/Adversarial به runtime راه می‌یابد.

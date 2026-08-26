# راهنمای اجباری توسعه‌دهنده و Agent

این فایل نقطهٔ شروع هر توسعه‌دهنده یا Agent جدید است. پروژه را از وضعیت واقعی موجود ادامه بده؛ بازسازی از صفر یا فرض‌کردن worktree تمیز ممنوع است.

## ترتیب مطالعه

1. `docs/project-memory/README.md`
2. `docs/project-memory/CURRENT_SYSTEM_BASELINE.md`
3. `docs/project-memory/FINDINGS_REGISTER.md`
4. `docs/project-memory/VALIDATION_LEDGER.md`
5. `ARCHITECTURE_DECISIONS.md`
6. `docs/PROJECT_SPECIFICATION.md`
7. `docs/PROJECT_STRUCTURE.md`
8. راهنمای مرتبط با کار جاری در `docs/`

برای ادامهٔ یک فاز، گزارش نهایی همان فاز در `docs/reports/` و آخرین handoff در `docs/handoffs/` نیز خوانده شود.

## قواعد تغییر

- وضعیت dirty عمدی است. `reset`، `checkout`، `clean`، `stage`، `commit` و `push` بدون دستور صریح کاربر ممنوع است.
- `bridge.json`، `.env`، نشست واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` دادهٔ عملیاتی‌اند؛ جابه‌جایی، بازنویسی یا حذف آن‌ها بدون اجازه ممنوع است.
- ارسال واقعی پیام، انتشار WordPress، ورود به حساب، bind واقعی 80/443، نصب Proxy، تغییر Firewall و rollback واقعی به تأیید همان لحظه نیاز دارد.
- Token، Cookie، OTP، رمز، کلید، شمارهٔ کامل، متن خصوصی پیام و مسیرهای دارای شناسهٔ حساس نباید در گزارش، لاگ یا خروجی آزمون ثبت شوند.
- Eitaa و سپس Bale اولویت Providerها هستند. قابلیت جدید نباید چندحسابی/چندکاربری یا Provider abstraction را دور بزند.
- یافته، تصمیم، شکست آزمون و پذیرش مهم نباید فقط در Chat بماند؛ مطابق `docs/project-memory/ENGINEERING_DOCUMENTATION_PROTOCOL.md` ثبت شود.

## جلوگیری از بررسی تکراری

پیش از بررسی زنده، `FINDINGS_REGISTER.md` و `VALIDATION_LEDGER.md` را ببین. بررسی مجدد فقط در صورت تغییر کد/پیکربندی مرتبط، منقضی‌شدن شاهد، تضاد با وضعیت جاری، یا ریسک عملیاتی جدید انجام شود. علت بررسی مجدد در Ledger نوشته شود.

## حداقل کنترل کیفیت

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
```

دامنهٔ آزمون را متناسب با تغییر انتخاب کن؛ تغییر قراردادهای مرکزی باید در نهایت با مجموعهٔ کامل سنجیده شود. هر اجرای معنادار در `docs/project-memory/VALIDATION_LEDGER.md` ثبت گردد.

## مستندات تولیدشونده

پس از تغییر فایل‌ها یا نمادها اجرا کن:

```powershell
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py
```

فایل‌های `docs/project-map/PROJECT_FILE_MAP.md`، `docs/project-map/SYMBOL_INDEX.json` و `docs/REPORTS_INDEX.md` تولیدشونده‌اند و نباید دستی ویرایش شوند.

پس از هر تغییر در Markdown، checker حافظه نیز باید اجرا شود. خطای UTF-8، `U+FFFD`، control character، سطر فرمان شکسته و تعریف تکراری `F-xxx`/`V-xxx` مجاز نیست؛ رکورد تاریخی تکراری با شناسهٔ `LEGACY-...` نگهداری شود، نه با شناسهٔ رسمی تازه یا تکراری.

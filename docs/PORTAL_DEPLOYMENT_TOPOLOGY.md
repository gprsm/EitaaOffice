# توپولوژی استقرار پرتال فرهنگی (F-097)

این سند، نقشهٔ کامل استقرار سامانهٔ جامع مدیریت و پایش گزارش‌های فرهنگی را ثبت می‌کند تا هر توسعه‌دهنده یا Agent بدون کشف مجدد بتواند تغییرات را به‌سلامت منتشر کند.

## ۱. لایه‌ها و مسیرها

| لایه | مسیر | کنترل نسخه |
|---|---|---|
| هستهٔ پردازش (منبع حقیقت) | `C:\Users\mohse\AppData\Local\Programs\EitaaBridge\src\eitaa_bridge\reporting\` | مخزن اصلی (`origin` EitaaDesktop + `office` EitaaOffice، شاخهٔ `Bale`) |
| فرانت‌اند SPA متریال (سورس) | `EitaaBridge\ui-portal\` | همان مخزن اصلی |
| فرانت‌اند SPA (باندل مستقر) | `c:\Users\mohse\laragon\www\cultural-portal\app\` | مخزن محلی پرتال |
| بک‌اند پرتال (PHP 8.1 لاراگون) | `c:\Users\mohse\laragon\www\cultural-portal\{api,includes,views}\` | مخزن محلی پرتال |
| فرانت قدیمی PHP (fallback) | همان `views/` + `assets/` — با `?legacy=1` | مخزن محلی پرتال |
| پایگاه عملیاتی مشترک | `EitaaBridge\data\reporting\reporting.sqlite3` | **بدون کنترل نسخه — دادهٔ عملیاتی؛ هرگز کامیت/جابه‌جا نشود** |
| خروجی‌های اکسل | `EitaaBridge\data\reporting\reports\` | دادهٔ عملیاتی |
| رسانه‌های رویدادها | `cultural-portal\uploads\` | دادهٔ عملیاتی (gitignored) |

## ۲. جریان انتشار تغییرات

**تغییر در هستهٔ پایتون یا SPA:**
1. تغییر در مخزن اصلی (شاخهٔ `Bale`) → آزمون‌ها (`pytest`، `npm --prefix ui-portal run check`).
2. اگر `src/eitaa_bridge` تغییر کرد: `.\.venv\Scripts\python.exe scripts\build_wheel_stdlib.py --root . --output-dir dist --force` (آزمون بسته‌بندی wheel به هم‌خوانی حساس است).
3. اگر `ui-portal/` تغییر کرد: `npm.cmd --prefix ui-portal run build` (بیلد + استقرار خودکار باندل در `cultural-portal/app/`).
4. در پرتال: `git add -A && git commit` (مخزن محلی؛ بدون push — remote ندارد).
5. مخزن اصلی: commit + push به هر دو remote (`origin Bale` و `office Bale`).
6. رکورد F/V در `docs/project-memory/` + `refresh_project_docs.py`.

**تغییر فقط در بک‌اند PHP پرتال:**
- ویرایش مستقیم در `cultural-portal` → `php -l` همهٔ فایل‌ها → هارنس (`php scripts/test_cultural_portal_harness.php` از ریشهٔ مخزن اصلی) → commit در مخزن محلی پرتال → اگر قرارداد API یا تعاریف فرم تغییر کرد، رکورد F/V در مخزن اصلی هم ثبت شود.

## ۳. قرارداد دادهٔ مشترک (SQLite)

هر دو لایه (پایتون و PHP) همان `reporting.sqlite3` را می‌خوانند/می‌نویسند:
- `form_definitions` — تصویر `EXTENDED_FORMS` پایتون (شرح عملیاتی، موازین، چارچوب سیاستی، سؤالات با `auto_from`)؛ در هر init پایتون upsert می‌شود.
- `mandates` — رجیستری اسناد ابلاغی؛ بن‌مایه‌های `CANONICAL_MANDATES` خودشفاء (upsert)؛ اسناد کاربر با id تصادفی هرگز بازنویسی نمی‌شوند.
- `reported_events` + `event_facts` — رویدادها و فکت‌ها؛ فیلدهای `dim_<metric>` فرم‌های پرتال فکت می‌سازند و ستون‌های اختصاصی کارتابل/اکسل را پر می‌کنند.

قاعده: **منبع حقیقت تعاریف سیاستی = پایتون**؛ پرتال از SQLite می‌خواند. متن سیاستی هرگز در JS/PHP hardcode نشود.

## ۴. آزمون‌ها

| سطح | دستور |
|---|---|
| هستهٔ پایتون | `.\.venv\Scripts\python.exe -m pytest -q` (۹۶۹+ آزمون) |
| تایپ SPA | `npm.cmd --prefix ui-portal run check` |
| هارنس عملکردی پرتال | `php scripts/test_cultural_portal_harness.php` (از ریشهٔ مخزن اصلی؛ روی کپی موقت پایگاه — ۲۶ بررسی) |
| PHP lint | `php -l` روی فایل‌های تغییر یافته |
| مرورگر | `http://localhost/cultural-portal/` (SPA) و `?legacy=1` (fallback) |

## ۵. ملاحظات حریم و عملیات

- `bridge.json`، `.env`، `data/`، `uploads/`، نشست واقعی و پیکربندی حساس جابه‌جا/بازنویسی/کامیت نمی‌شوند.
- هارنس همیشه روی **کپی موقت** پایگاه اجرا می‌شود؛ هرگز روی پایگاه عملیاتی.
- ارسال پیام، انتشار وردپرس و bind پورت فقط با تأیید لحظه‌ای کاربر.
- PHP 8.1 لاراگون: `c:/Users/mohse/laragon/bin/php/php-8.1.10-Win32-vs16-x64/php.exe`.
- تعارض کد سند رسمی (مسابقات=80403 چاپ‌شده در کاربرگ بازدید) با حکم Q-IR-001 حل شده است: مراسم=80403، مسابقات=80402 — بدون دستور کاربر عوض نشود.

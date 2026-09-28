# دستور پیگیری: سامانه جامع مدیریت و پایش گزارش‌های فرهنگی — پرتال + هسته (پس از F-096)

- تاریخ: 2026-09-28
- آخرین کامیت: `9e1750d4` روی شاخه `Bale` (به هر دو مخزن `origin` EitaaDesktop و `office` EitaaOffice push شده)
- شناسه‌های ثبت‌شده تا اینجا: F-092..F-096 / V-224..V-228 در `docs/project-memory/FINDINGS_REGISTER.md` و `VALIDATION_LEDGER.md`
- مخاطب: عامل (Agent) پیاده‌سازی که کار را از همین نقطه ادامه می‌دهد

---

## ۰) شروع الزامی

1. `AGENTS.md` (ریشه مخزن) — قواعد تغییر، حریم دادهٔ عملیاتی، مجوز انتشار.
2. `docs/project-memory/README.md` → `CURRENT_SYSTEM_BASELINE.md` → `FINDINGS_REGISTER.md` → `VALIDATION_LEDGER.md`.
3. همین فایل تا انتها.
4. سند مرجع سیاستی: `C:\Users\mohse\OneDrive\Desktop\كاربرگ_سفر_استاني_1.docx` (کاربرگ بازدید و ارزیابی عملکرد امور فرهنگی — منبع مستندات ابلاغی و ساختار فرم‌ها).

مخزن اصلی: `C:\Users\mohse\AppData\Local\Programs\EitaaBridge` (شاخه `Bale`).
پرتال (خارج از مخزن، بدون git): `c:\Users\mohse\laragon\www\cultural-portal` — آدرس کاربر: `http://localhost/cultural-portal/`.

---

## ۱) تصویر معماری فعلی (نکات اتکا)

**سه لایه، یک پایگاه:**
- هسته پایتون `src/eitaa_bridge/reporting/`: `forms.py` (تعاریف رسمی ۸ فرم: شرح عملیاتی/موازین/چارچوب سیاستی/سؤالات با `auto_from`)، `plans.py` (`CANONICAL_MANDATES` = ۱۷ سند ابلاغی دقیق سند رسمی)، `store.py` (SQLite؛ جدول `form_definitions` = تصویر upsert تعاریف فرم‌ها در هر init؛ seed mandates خودشفاء)، `service.py` (`export_with_audit` با `date_from/date_to`).
- پرتال PHP `cultural-portal`: `includes/ReportingService.php` (`PROGRAM_MAP` با کدهای رسمی ۸۰۴۰۱..۸۰۲۰۲ + ۵ موضوع کاربرگ بازدید با ref=شناسهٔ بخش)، `includes/EntryFormDefinitions.php` (۱۳ فرم ورود اختصاصی + رندر HTML + نگاشت گزینه←فکت)، `api/index.php`، `views/tabs/*` (+ `partials/` سطرهای مشترک PHP/JS)، `assets/js/portal.js` (اسکرول‌لود/جستجوی پیشرفته/فرم AJAX/اکسل بازه‌ای).
- پایگاه مشترک: `data/reporting/reporting.sqlite3` — هر دو لایه همان فایل را می‌خوانند/می‌نویسند.

**قواعد نگاشت دادهٔ پرتال:**
- فیلد عددی `dim_<metric>` → فکت `event_facts` با metric هم‌نام (ستون اختصاصی کارتابل و منبع اکسل).
- فیلد انتخابی `sel_*` خودش فکت نیست؛ گزینه‌اش `data-metric` دارد و عدد `selcount_<sel>` سمت JS به `dim_<metric>` نگاشت می‌شود (`Portal.collectEntryFormFields`).
- فیلدهای `txt_*`/`sel_*` → الصاق ساختارمند «برچسب: مقدار» به `notes` (در `ReportingService::createManualEvent`).
- `occasion_class` مراسم → ستون رسمی همان نام.

**تصمیم‌های حاکم (تغییر ندهید مگر با دستور کاربر):**
- تعارض کد سند: کاربرگ بازدید برای مسابقات 80403 چاپ کرده؛ حکم کاربر Q-IR-001 حاکم است: مراسم=80403، مسابقات=80402. ثبت تذکر در `mnd-80402-contest-guideline`.
- کدهای ساختگی `PRG-WB-xx` ممنوع؛ ضمیمهٔ زیارت عاشورا = «پیوست ۸۰۴۰۳» (ref=80403-A).
- بن‌مایهٔ `CANONICAL_MANDATES` همیشه upsert می‌شود (خودشفا)؛ اسناد ثبت‌شدهٔ کاربر (mnd- تصادفی) هرگز لمس نمی‌شوند.
- رندر سمت کاربر فقط از `form_definitions`/`EntryFormDefinitions` — هیچ متن سیاستی در JS hardcode نشود.

---

## ۲) روش اعتبارسنجی استاندارد (قبل از تحویل هر فاز)

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # ۹۶۹ آزمون — exit 0
.\.venv\Scripts\python.exe scripts\build_wheel_stdlib.py --root . --output-dir dist --force   # فقط اگر src تغییر کرد
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
```

پرتال: `php -l` روی همهٔ فایل‌های تغییر یافته (PHP در `c:/Users/mohse/laragon/bin/php/php-8.1.10-Win32-vs16-x64/php.exe`)؛ سپس هارنس (فاز ۴-۲) و آزمون مرورگر روی `http://localhost/cultural-portal/`.
هر تغییر معنادار → رکورد F/V تازه (بعد از F-096/V-228) + `refresh_project_docs.py` + commit با پیام دقیق + push به هر دو مخزن (`origin Bale` و `office Bale`).

---

## فاز ۱ — تثبیت: راستی‌آزمایی‌های ناتمام همین جلسه (کوتاه، شروع از اینجا)

آزمون‌های مرورگر نیمه‌کاره ماندند؛ بدون اصلاح کد (مگر خطا):

1. **اسکرول‌لود شیت مراسم (۸۰۴۰۳، ۲۱۷ رویداد):** صفحه `?tab=worksheets&program=80403`، اسکرول تا انتها؛ سطرها باید به `total` برسند و «همهٔ ۲۱۷ رویداد نمایش داده شد» ظاهر شود. (آزمون قبلی با خطای timeout ابزار نیمه رها شد؛ با scroll مرحله‌ای یا `window.scrollTo` در evaluate انجام شود.)
2. **جریان کامل اکسل بازه‌ای از UI:** دکمهٔ «صدور اکسل بازه‌ای» → بازهٔ ۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۶/۳۱ → اجرا → دانلود؛ فایل `data/reporting/reports/گزارش_فرهنگی_1405-05-01_تا_1405-06-31.xlsx` باید ساخته شود (تبدیل شمسی→میلادی سمت PHP با `Helpers::jalaliStringToGregorianIso`).
3. **ثبت رویداد از UI برای یک موضوع کاربرگ بازدید** (مثلاً counseling از دکمهٔ داشبورد یا کارت موضوع): فرم اختصاصی AJAX، ثبت، و ظاهرشدن سطر در کارتابل با ستون‌های اختصاصی و مقدار فکت.
4. **ثبت/حذف مستند ابلاغی از UI** (تب اسناد + کارت شیت) و ماندگاری پس از reload.

پذیرش فاز ۱: هر چهار مورد در مرورگر تأیید و در V-229 (یا الحاق به V-228 با ذکر علت) ثبت شود.

## فاز ۲ — تکمیل جریان ویرایش رویداد (شکاف اصلی عملکردی)

مودال ویرایش (`modal-edit-event`) فقط occasion/unit/attendees/notes دارد و ابعاد اختصاصی شیت را نشان نمی‌دهد.

1. **فرم اختصاصی در ویرایش:** هنگام `openEditEventModal`، برنامهٔ رویداد از `program_kinds_json` به ref نگاشت شود (`ReportingService::PROGRAM_MAP` معکوس) و `EntryFormDefinitions::renderProgramFields(<ref>)` با prefill مقادیر موجود رندر شود (مقادیر عددی از `getEventFactsByEvent`، مقادیر txt_ از بازتحلیل notes یا از فکت متنی — حداقل: prefill ابعاد عددی).
2. **نوشتن تغییرات:** `update_event` در `api/index.php` + `ReportingService::updateEvent` باید فیلدهای `dim_*` را upsert کند (مثل create: UPDATE یا INSERT فکت) و `occasion_class` را بپذیرد.
3. **حذف/صفر کردن فکت:** مقدار خالی یا ۰ → حذف فکت یا صفر (تصمیم: حذف ردیف فکت تمیزتر است؛ در F رکورد مستند شود).

پذیرش: ویرایش یک رویداد تکریم (تغییر دسته و تعداد) از UI → فکت درست تغییر کند؛ هارنس PHP برای update با dim_ نوشته شود؛ F-097/V-229 ثبت شود.

## فاز ۳ — شکاف‌های جستجو و نمایش

1. **فیلتر ردهٔ مراسم:** `occasion_class` (ملی/مذهبی/انقلابی/سایر) به پنل جستجوی پیشرفته و `buildEventsWhere` اضافه شود (برای 80403 معنا دارد).
2. **رفع باگ KPI ماهانه:** در `ReportingService::getKpis`، `occurred_on LIKE '%/05/%'` روی تاریخ ISO هرگز مطابق نمی‌شود؛ یا بازهٔ میلادی ماه شمسی محاسبه شود (با `Helpers::jalaliToGregorian`) یا این دو شاخص حذف/جایگزین شوند. (در UI فعلاً استفاده نمی‌شوند اما ماندنش گمراه‌کننده است.)
3. **شمار واقعی پست‌های وردپرس:** `get_wp_posts` کل را null می‌دهد؛ COUNT جدا در `WordPressBridge` اضافه شود تا «پایان فهرست» در اسکرول‌لود قطعی شود.
4. **بازبینی ستون‌های اختصاصی موضوعات بازدید:** `getSheetDimensionColumns` برای ref های موضوعات از `EntryFormDefinitions` مشتق می‌شود؛ در جدول کارتابل نمایش و سرتایکل‌ها را با یک موضوع پررویداد تست کنید.

## فاز ۴ — نسخه‌پذیری و پایداری پرتال (ریسک شناخته‌شده)

**پرتال خارج از مخزن است و هیچ کنترل نسخه‌ای ندارد.**

1. **git محلی برای پرتال:** `git init` در `c:\Users\mohse\laragon\www\cultural-portal` + `.gitignore` (بدون push؛ نپات‌پد/آپلودها/`uploads/`، `screenshots/`). این اقدام افزودنی و کم‌ریسک است؛ حذف/جابه‌جایی فایل ممنوع.
2. **دائمی‌سازی هارنس PHP:** هارنس آزمون این جلسه در `%TEMP%\portal_harness.php` است (روی کپی موقت پایگاه). آن را به `scripts/test_cultural_portal_harness.php` مخزن منتقل کنید (مسیر DB پارامتری با env)، تا در V رکوردها ارجاع پایدار باشد.
3. **مستندسازی توپولوژی پرتال** در `docs/` (مسیرها، وابستگی SQLite مشترک، PHP 8.1 لاراگون، هیچ‌کدام از داده‌های عملیاتی دست نمی‌خورد).

## فاز ۵ — ادامه نقشه راه دفتر (پس از تثبیت پرتال؛ از حافظه پروژه)

1. **صف ۷۸ نامزد تأیید** در داشبورد دفتر (UI دسکتاپ): 31 مشارکت رئیس، 23 رضایت امام جماعت، 1 اذان، 23 رکورد امام.
2. **تصمیم سطر تکراری «دادسرای ساری»** در وضعیت‌سنجی (۳۱ حوزهٔ یکتا از ۳۲ سطر) — نیاز به تأیید کاربر.
3. **باند ۳:** مولد گزارش دوماهه (کاربرگ عددی ۷ شیت + قالب روایی-مالی ۸۰۰۰۰) به‌صورت projection از فکت‌ها.
4. **باند ۴:** UI ویرایش رجیستری (نومکلف/امام/نمازخانه) و پایش زندهٔ ایتا/بله به رویدادهای طرح.

---

## ۳) گره‌های سریع

| مورد | مسیر |
|---|---|
| پایگاه عملیاتی (مشترک، دست‌نخوردنی جز از سرویس‌ها) | `C:\Users\mohse\AppData\Local\Programs\EitaaBridge\data\reporting\reporting.sqlite3` |
| خروجی‌های اکسل | `...\data\reporting\reports\` |
| اسکریپت اکسل بازه‌ای | `scripts/export_cultural_report.py --from-date --to-date --period-label` |
| فرم‌های اختصاصی پرتال | `cultural-portal\includes\EntryFormDefinitions.php` |
| API پرتال | `cultural-portal\api\index.php` (اکشن‌ها: get_entry_form, get_mandates, create_mandate, trigger_excel_export با date_from_jalali/… ) |
| هارنس PHP (موقت) | `%TEMP%\portal_harness.php` + کپی پایگاه `%TEMP%\portal_test.sqlite3` |
| سند مرجع | `C:\Users\mohse\OneDrive\Desktop\كاربرگ_سفر_استاني_1.docx` |

**محدودیت‌های مطلق:** بدون دستور صریح کاربر: `reset/checkout/clean` ممنوع؛ `bridge.json`، `.env`، `data/`، `runtime/`، نشست واقعی جابه‌جا/بازنویسی نشود؛ token/PII/متن خصوصی در لاگ و گزارش نیاید؛ ارسال پیام/انتشار وردپرس/bind پورت/فایروال فقط با تأیید همان لحظه. push فقط شاخهٔ کاری (Bale) به هر دو مخزن؛ merge/push مستقیم به `main` ممنوع.

**گزارش‌دهی:** هر یافته/تصمیم/شکست مهم فقط در chat نماند — طبق `docs/project-memory/ENGINEERING_DOCUMENTATION_PROTOCOL.md` در F/V رکورد شود؛ پس از هر تغییر Markdown، چکر حافظه اجرا شود.

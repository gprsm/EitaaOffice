# Handoff توقف موقت تثبیت AntiGravity2

وضعیت: `USER_PAUSED`  
زمان توقف: 2026-08-25T06:16:50.0038568+03:30  
ریشهٔ اصلی: `D:\eitaa Project\AntiGravity2`  
هدف بعدی: `G-00 — تثبیت baseline و قابلیت بازگشت`  
اجازهٔ شروع: فقط با دستور تازهٔ کاربر

## ۱. خلاصهٔ اجرایی

پروژه به درخواست کاربر موقتاً متوقف شده است. هیچ هدف اصلاح کدی از `G-00` تا `G-09` آغاز نشده و هیچ stage/commit، عملیات Provider، تغییر DB/session/config یا دست‌کاری دادهٔ عملیاتی انجام نشده است.

کار انجام‌شده تا این توقف:

1. snapshot پوشهٔ `AntiGravity2` و پوشهٔ مرجع قبلی به‌صورت فقط‌خواندنی مقایسه شد.
2. مشکلات اصلی به‌عنوان `F-039` تا `F-044` ثبت شدند.
3. برنامهٔ هدف‌محور `G-00` تا `G-09` و دفتر اجرای append-only ایجاد شد.
4. تصمیم تازهٔ کاربر دربارهٔ عدم rollback قراردادهای متأخر در `F-046` و تصمیم معماری ۳۴ ثبت شد.
5. قرارداد G-04 اصلاح شد: نمایش کامل شماره در سطح مجاز محصول حفظ می‌شود؛ masking قدیمی بازنمی‌گردد؛ ممنوعیت شماره/secret در Log/Audit/Diagnostic/Support Bundle مستقل و لازم‌الاجراست.
6. آخرین قرارداد توسعهٔ Bale تصمیم محصولی معتبر شناخته شد، ولی تثبیت جاری هیچ قابلیت تازهٔ Bale نمی‌سازد و فقط implementation شکسته را fail-closed و اصلاح خواهد کرد.

## ۲. مسیر طی‌شده و شواهد

### ممیزی snapshot — V-103

- ریشهٔ جدید repository Git نیست؛ پوشهٔ قبلی repository شاخهٔ `main` و عمداً dirty باقی مانده است.
- مقایسهٔ امن source/UI/tests/scripts/installer/docs: 94 فایل افزوده، 35 تغییرکرده و 1 حذف‌شده نسبت به مرجع قبلی.
- Backend: 587 تست جمع‌آوری؛ 585 موفق و 2 شکست به‌علت BOM فایل Bale slot.
- UI: TypeScript و observability و چند suite هدفمند سبز؛ Phase 10 به‌علت assertion قدیمی محل helper و Phase 11 onboarding به‌علت پذیرش `token` شکست خوردند.
- Bale probe آفلاین: manifest فعال ولی adapter factory با import نامعتبر شکست خورد؛ هیچ network اجرا نشد.
- scanner لاگ روی مسیرهای شناخته‌شده `invalid_json=0` و `finding=0` گزارش کرد؛ پوشش آن برای همهٔ حساب‌ها و artifactهای Bale کامل نیست.

### برنامه‌ریزی — V-104 / STAB-GPLAN-R00

- هدف کدها، حلقهٔ وضعیت، معیارهای خروج، دروازه‌های تأیید و قرارداد سه‌لایهٔ لاگ ثبت شد.
- هر اقدام آینده باید `goal_id/run_id/event_id`، زمان، فرمان امن، فایل، hash، exit code، نتیجه، failure/retry، اثر بیرونی و مرجع تأیید داشته باشد.
- شکست‌های patch مستندی حذف نشدند و retryهای آن‌ها در Execution Log باقی مانده‌اند.

### اصلاح دامنه — V-105 / STAB-GPLAN-R01

- rollback masking از برنامه حذف شد.
- F-040 به runtime safety blocker بدون توسعهٔ تازه محدود شد.
- F-044 به تصمیم `NO_ROLLBACK / TEST_AND_DOC_ALIGNMENT_PENDING` تبدیل شد.
- F-046 و تصمیم معماری ۳۴ مرز جدید را canonical کردند.

## ۳. وضعیت فعلی اهداف

| هدف | وضعیت توقف | کار باقی‌مانده |
|---|---|---|
| G-00 | `QUEUED / NOT_STARTED` | انتخاب روش Git baseline، inventory/hash و نقطهٔ بازگشت؛ توقف پیش از stage/commit |
| G-01 | `QUEUED / NOT_STARTED` | رفع تناقض‌های اسناد، خرابی F-035/V-078، شناسه‌های تکراری، Baseline و گزارش‌های stale |
| G-02 | `QUEUED / NOT_STARTED` | fail-closed کردن Bale شکسته، رفع BOM و جلوگیری از runtime/onboarding/release بدون توسعهٔ قابلیت |
| G-03 | `QUEUED / NOT_STARTED` | نصب تمیز، Coordinator bootstrap و legacy challenge binding معتبر |
| G-04 | `QUEUED / NOT_STARTED` | تست نمایش کامل طبق قرارداد متأخر و تست مستقل عدم نشت در لاگ/پشتیبانی |
| G-05 | `QUEUED / NOT_STARTED` | lifecycle/stop/join و observability ایندکس خودکار؛ حذف failure خاموش |
| G-06 | `QUEUED / NOT_STARTED` | ترمیم contractهای آزمون و حذف تست‌های خالی بدون بازگرداندن masking قدیمی |
| G-07 | `QUEUED / NOT_STARTED` | بسته‌بندی allowlist، dry-run، privacy/secret scan و fresh-install ایزوله |
| G-08 | `QUEUED / NOT_STARTED` | پوشش همهٔ حساب‌ها در scanner، event catalog و background-task observability |
| G-09 | `QUEUED / NOT_STARTED` | full regression، build، package/fresh-install، اسناد نهایی و پذیرش کاربر |

## ۴. یافته‌های باز در لحظهٔ توقف

- `F-039`: نبود Git traceability در ریشهٔ جدید.
- `F-040`: runtime فعلی Bale شکسته؛ توسعهٔ تازه خارج از دامنه.
- `F-041`: blockerهای نصب تمیز.
- `F-042`: suite و بسته‌بندی snapshot فعلی release-ready نیست.
- `F-043`: auto-index worker بدون lifecycle/observability کامل.
- `F-044`: قرارداد نمایش کامل پذیرفته شده؛ test/doc alignment باقی است.
- `F-045`: برنامه آماده و منتظر اجرای هدف‌ها.
- `F-046`: عدم rollback قراردادهای متأخر تصمیم قطعی است.

## ۵. مرزهای حفظ‌شده در توقف

- فایل‌های عملیاتی `bridge.json`، `.env`، `data/`، `runtime/`، `diagnostics/`، `backups/` و نشست واقعی دست‌نخورده‌اند.
- Login، OTP، Session، Send، Capture، WordPress، Firewall، Proxy، Port، Certificate و restart واقعی اجرا نشده‌اند.
- پوشه‌ها/artifactهای Bale حذف، منتقل، import یا اجرا نشده‌اند.
- Git mutation شامل reset/checkout/clean/stage/commit/push انجام نشده است.
- هیچ Token، Cookie، OTP، رمز، شمارهٔ کامل یا متن خصوصی در این handoff ثبت نشده است.

## ۶. نقطهٔ امن ازسرگیری

در نوبت بعد ابتدا این فایل و سپس برنامه و دفتر اجرا خوانده شوند. پیش از Write، hash فعلی اسناد حاکمیتی به‌عنوان pre-image Run تازه ثبت شود.

فرمان پیشنهادی کاربر:

`G-00 را شروع کن؛ فقط baseline و گزینه‌های Git را آماده کن و پیش از هر stage یا commit متوقف شو.`

Run پیشنهادی ازسرگیری: `STAB-G00-R01`.

تا دریافت این فرمان یا دستور صریح دیگری، هیچ بررسی زنده، آزمون، تغییر کد یا عملیات خارجی ادامه داده نشود.


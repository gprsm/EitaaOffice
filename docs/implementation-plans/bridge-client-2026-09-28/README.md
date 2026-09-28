# دستورهای تکمیل بله و اتصال کلاینت وب

تاریخ: 2026-09-28

وضعیت: `PLANNED / INSTRUCTIONS_READY / IMPLEMENTATION_NOT_STARTED`

مبنای بررسی: checkout واقعی AntiGravity2 روی `c513cdf30852c8a243287f063ce828b9b5b0f193`. هنگام اجرا، HEAD و تغییرات جاری دوباره شناسایی شوند.

این بسته دو دستور اجرایی دارد. ساخت این اسناد به معنی پیاده‌سازی قابلیت‌ها، پیکربندی حساب واقعی یا پذیرش Live نیست.

## دستور اول: تکمیل بله در محصول اصلی

به عامل بگو:

> فایل `docs/implementation-plans/bridge-client-2026-09-28/BALE_FULL_PRODUCT_INTEGRATION.md` را کامل بخوان، منابع الزامی آن را مطالعه کن و دستور را تا پایان معیارهای پذیرش اجرا کن. صرف ساخت آداپتور یا نمایش نام بله کافی نیست. checkpointهای داخلی را ثبت کن و تا وقتی کار مجاز و مستقل باقی است ادامه بده.

[دستور کامل بله](BALE_FULL_PRODUCT_INTEGRATION.md) یک مأموریت مستقل با checkpointهای B0 تا B6 است. خروجی آن باید بله را در برنامهٔ اصلی، حساب‌ها، مخاطبین، گفتگو/پیام، تنظیمات سرویس و مسیر عمومی ارسال قابل استفاده کند. امکان OTP برای شمارهٔ جدید به نتیجهٔ واقعی افزودن مخاطب وابسته است.

## دستور دوم: برنامهٔ اتصال وب، OTP و AI

به عامل بگو:

> فایل `docs/implementation-plans/bridge-client-2026-09-28/WEB_CLIENT_PROGRAM.md` را بخوان؛ سپس فاز تعیین‌شده را از فایل خودش اجرا کن. `EXECUTION_RULES.md` و `EXECUTION_STATUS.md` را نیز بخوان. هر شرط پایان را با شاهد ثبت کن و در صورت نقص، همان فاز را تکمیل کن؛ فقط نتیجهٔ آزمون‌های قدیمی را گزارش نکن.

[برنامه و وابستگی‌ها](WEB_CLIENT_PROGRAM.md) و [دفتر وضعیت](EXECUTION_STATUS.md) منبع انتخاب فازند.

| فاز | مأموریت | فایل مستقل |
|---|---|---|
| P1 | قرارداد پایه و تعیین فرستنده در تنظیمات | [PHASE_01_SENDER_PROFILES.md](PHASE_01_SENDER_PROFILES.md) |
| P2 | نرخ اجرای واقعی و preflight | [PHASE_02_LIMITS_PREFLIGHT.md](PHASE_02_LIMITS_PREFLIGHT.md) |
| P3 | رزرو ظرفیت و پذیرش اتمیک | [PHASE_03_CAPACITY_RESERVATIONS.md](PHASE_03_CAPACITY_RESERVATIONS.md) |
| P4 | افزودن مخاطب و ارسال OTP با رسید مرحله‌ای | [PHASE_04_CONTACTS_OTP_DELIVERY.md](PHASE_04_CONTACTS_OTP_DELIVERY.md) |
| P5 | اتصال AI، مدیریت کلید و انتخاب مدل | [PHASE_05_AI_CONNECTION_SETTINGS.md](PHASE_05_AI_CONNECTION_SETTINGS.md) |
| P6 | سیاست دادهٔ AI و اجرای مجوز خروج اطلاعات | [PHASE_06_AI_DATA_POLICY.md](PHASE_06_AI_DATA_POLICY.md) |
| P7 | کلاینت backend وب و آزمون end-to-end | [PHASE_07_WEB_CLIENT_E2E.md](PHASE_07_WEB_CLIENT_E2E.md) |
| P8 | ابزار و اجرای آزمون آنلاین و گرم | [PHASE_08_LIVE_WARM_ACCEPTANCE.md](PHASE_08_LIVE_WARM_ACCEPTANCE.md) |
| P9 | محصول نهایی، بسته‌بندی و تحویل | [PHASE_09_FINAL_PRODUCT_HANDOFF.md](PHASE_09_FINAL_PRODUCT_HANDOFF.md) |

مثال واگذاری یک فاز:

> در پروژه AntiGravity2 فایل `docs/implementation-plans/bridge-client-2026-09-28/PHASE_03_CAPACITY_RESERVATIONS.md` را کامل بخوان و اجرا کن. پیش‌نیازها را از گزارش واقعی بررسی کن، معیارهای خروج را ببند و گزارش و handoff همان فاز را ثبت کن.

عامل می‌تواند فازهای مجاز مستقل را ادامه دهد، اما نباید وضعیت `PLANNED` را با پایان کار یا پاسخ «قابل انجام است» عوض کند. ورودی یا تأیید Live مفقود، فقط مرحلهٔ وابسته به همان ورودی را متوقف می‌کند.

## مراجع

- [قواعد اجرای مشترک](EXECUTION_RULES.md)
- [راهنمای پروژه](../../../AGENTS.md)
- [Baseline](../../project-memory/CURRENT_SYSTEM_BASELINE.md)
- [قرارداد موجود M2M](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

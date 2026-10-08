# Handoff فاز ۳ — رزرو ظرفیت و پذیرش اتمیک

تاریخ: 2026-09-29؛ وضعیت P3: `OFFLINE_COMPLETE` (بدون مؤلفهٔ Live)
مرجع: [گزارش P3](../reports/features/WEB_CLIENT_PHASE_03_REPORT.md)، قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` نسخهٔ 1.7.0، V-235.

قید ممیزی مستقل V-236: اعلام OFFLINE_COMPLETE بالا تحویل عامل است. ممیزی مسیر بله بسته‌شدن کامل shared R1 را رد کرد: release binding را حذف می‌کند و همان id ردشده با متن متفاوت ارسال می‌شود. ادامه‌دهنده [دستور اصلاحی F-099](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) را بخواند؛ این قید ممیزی جامع خود رزروهای P3 نیست. R3 نیز همچنان در سناریوی بله باز است.

## چه چیزی تحویل شد

- جدول `service_delivery_reservations` (schema v12) با state machine پایانی، `operation_id` یکتا و یک تراکنشِ «تصمیم ظرفیت + debit + insert».
- binding گیرنده با HMAC کلید identity سرور (`hmac_hex` روی هر دو protector)؛ شمارهٔ خام و OTP هرگز ذخیره نمی‌شوند.
- مسیرهای M2M: `POST /api/v2/m2m/delivery/reservations`، `GET/POST .../reservations/{id}` (status/cancel مالک‌محور و idempotent) با نگاشت دقیق 429/503/409/404.
- محدودیت‌ها: ۴ outstanding، ۱۲ ایجاد در دقیقه، TTL ۳۰–۶۰۰s؛ consume اتمیک با بررسی lifecycle و revision؛ refund یک‌بار و فقط پیش از شروع ارسال؛ restart-persistent.

## شواهد کلیدی

- `tests/test_delivery_reservations.py` = 10/10 پایدار: رقابت ظرفیت ۱ در دو connection و دو فرایند واقعی OS، ساعت fake، رِیس cancel/consume/expire، restart قبل/بعد از consume، crash پس از debit، conflict کلید، مالک بیگانه، آرشیو حساب، تعامل legacy.
- full Backend و دروازه‌های عامل در V-235.

## اقدام اول ادامه‌دهنده

1. شروع P4 (`PHASE_04_CONTACTS_OTP_DELIVERY.md`): consume رزرو در pipeline با `operation_id` به‌عنوان کلید پایاپای؛ prepare→send→receipt/status با uncertain صادقانه و عدم نشت OTP/شماره.
2. کدهای خطا و نام‌های P3 را تغییر ندهید؛ هر مسیر تازه ابتدا در قرارداد ثبت شود.
3. retention رکوردهای رزرو (پاک‌سازی metadata) در فاز پایپ‌لاین تعریف شود.
4. انتشار Git انجام نشده (درخت مشترک سه سناریو)؛ تصمیم با مالک است.

# سند تحویل مرحلهٔ چهارم کلاینت وب (P4 Handoff)

تاریخ: 2026-09-29
وضعیت: OFFLINE_COMPLETE (P4 آماده و تحویل‌شده)
پیش‌نیاز فاز بعدی: فازهای P5 و P6 (تنظیمات اتصال هوش مصنوعی و سیاست داده خروجی)

## ۱. دستاوردهای تحویل‌شده

- **ماژول‌ها و پیاده‌سازی**:
  - `src/eitaa_bridge/infrastructure/coordinator/otp_deliveries.py`: ذخیره‌ساز پایدار `ServiceOtpDeliveryStore` و رکورد `OtpDeliveryRecord`.
  - `src/eitaa_bridge/application/otp_delivery_pipeline.py`: پایپ‌لاین مرحله‌ای OTP شامل پذیرش، حل مخاطب، ثبت مخاطب جدید، ارسال پیام، و ثبت وضعیت نهایی یا uncertain.
  - `src/eitaa_bridge/application/m2m_api.py`: مسیرهای `POST /api/v2/m2m/otp/deliveries` و `GET /api/v2/m2m/otp/deliveries/{id}`.
  - `src/eitaa_bridge/application/api.py`: مقداردهی `_otp_delivery_store` و افزودن دامنهٔ مجاز `otp.deliver`.
  - `src/eitaa_bridge/infrastructure/coordinator/reservations.py`: افشای فیلد `recipient_binding` در `DeliveryReservation` برای راستی‌آزمایی تطابق گیرنده با رزرو.

- **پوشش آزمون‌ها**:
  - فایل آزمون: `tests/test_otp_deliveries.py` شامل ۱۲ سناریوی مستقل (پذیرش، حل مخاطب، تکرار idempotent، تعارض payload، انقضا، timeout با نتیجهٔ uncertain، عدم rollback، تفکیک دسترسی سرویس‌ها، و حفاظت کامل از حریم خصوصی).

## ۲. وضعیت Acceptance IDها

- P4-A01: **PASS** (نگاشت و تفکیک مخاطب موجود و جدید با peer معتبر ایتا و بله).
- P4-A02: **PASS** (شناسایی تکرار، تعارض، انقضا و بازگشت قطعی uncertain بدون تلاش مجدد).
- P4-A03: **PASS** (ثبت صادقانه اثر ایجاد مخاطب بدون rollback پس از خطای ارسال).
- P4-A04: **PASS** (انطباق حریم خصوصی، تفکیک سرویس‌ها، عدم نشت داده و رعایت scope).

## ۳. نحوهٔ اجرای آزمون‌ها

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_otp_deliveries.py
```
نتیجه: ۱۲ passed در ۸.۳۵ ثانیه.

## ۴. نقطهٔ اتصال برای فازهای بعدی

- **فازهای بعدی**:
  - P5 (`PHASE_05_AI_CONNECTION_SETTINGS.md`): ایجاد بخش تنظیمات امن اتصال AI در پنل مدیریت، اعتبارسنجی URL/SSRF، و ذخیره امن کلیدها.
  - P6 (`PHASE_06_AI_DATA_POLICY.md`): کنترل سطح دسترسی و سیاست داده پیش از خروج به سمت مدل آنلاین.
  - P7 (`PHASE_07_WEB_CLIENT_E2E.md`): ساخت کلاینت مرجع backend وب، تست انتهای‌به‌انتهای HTTP و شبیه‌سازی جریان OTP تا تایید احراز هویت.

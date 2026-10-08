# تحویل فنی مرحلهٔ هفتم کلاینت وب (P7) — کلاینت Backend وب و آزمون E2E

تاریخ: 2026-09-29
وضعیت خروجی: OFFLINE_COMPLETE (مخزن وب‌سایت خارجی: BLOCKED_WITH_REASON)
شاهد: V-241 در [Validation Ledger](../project-memory/VALIDATION_LEDGER.md)

## مولفه‌ها و ماژول‌های تحویل‌شده

1. **کلاینت مرجع Backend وب (SDK Module)**:
   - فایل: `src/eitaa_bridge/application/web_client_reference.py`
   - کلاس‌ها: `BridgeWebClient`, `WebOtpSession`, `compute_recipient_binding`
   - متدها: `preflight`, `reserve_capacity`, `dispatch_otp`, `get_delivery_status`, `poll_delivery_status`, `chat`
   - ویژگی‌ها: عدم حضور هیچ کلید و اعتباری در مرورگر، تولید چالش OTP با مقایسه زمان‌ثابت، محافظت در برابر حملات جستجوی فراگیر (Brute-force lockout)، مصرف یک‌باره (Anti-replay)، و استعلام کنترل‌شدهٔ وضعیت ارسال (Bounded Polling).

2. **آزمون‌های یکپارچگی انتها‌به‌انتها**:
   - فایل: `tests/test_web_client_e2e.py` (۱۰ تست سبز).

## وضعیت ادغام با وب‌سایت واقعی

- ادغام در محیط جاری: `BLOCKED_WITH_REASON`.
- دلیل: مخزن وب‌سایت در این checkout موجود نیست؛ کلاینت مرجع و نمونه اجرایی در همین پروژه پیاده‌سازی و آزمایش شدند.

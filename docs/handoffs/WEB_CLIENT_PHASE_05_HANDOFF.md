# تحویل فنی مرحلهٔ پنجم کلاینت وب (P5) — اتصال امن و ذخیره کلید AI

تاریخ: 2026-09-29
وضعیت خروجی: OFFLINE_COMPLETE (مرحلهٔ بعدی: P6 و P7)
شاهد: V-239 در [Validation Ledger](../project-memory/VALIDATION_LEDGER.md)

## مولفه‌ها و ماژول‌های تحویل‌شده

1. **مدیریت کلید و اتصال هوش مصنوعی**:
   - فایل: `src/eitaa_bridge/infrastructure/coordinator/ai_connection.py`
   - کلاس‌ها: `AiConnectionStore`, `AiConnectionSettings`, `AiConnectionError`
   - ویژگی‌ها: رمزنگاری محلی AES-256-GCM، اعتبارسنجی سرسختانه URLها، مدیریت ایمن نسخه‌بندی (revisions)، عدم بازگرداندن کلید در خروجی (تنها `key_configured: bool`).

2. **اندپوینت‌های مدیریتی (Admin API Routes)**:
   - `GET /api/v2/admin/ai-connection`: دریافت مشخصات امن اتصال و وضعیت پیکربندی.
   - `PUT /api/v2/admin/ai-connection`: ثبت/ویرایش مشخصات، تنظیم کلید جدید یا حفظ کلید پیشین با قفل نگارش.
   - `POST /api/v2/admin/ai-connection/probe`: تست دسترسی به endpoint به روش امن بدون نشت داده‌های کاربران.

3. **آزمون‌های خودکار**:
   - فایل: `tests/test_ai_connection_settings.py` (۱۰ تست سبز).

## وضعیت Live

- عملیات زنده روی سرویس‌های ابری هوش مصنوعی: `LIVE_PENDING_INPUT`.
- کلید عملیاتی یا endpoint اختصاصی کاربر ورودی داده نشده است؛ سیستم به طور پیش‌فرض در حالت ایمن آفلاین قرار دارد.

# گزارش مرحلهٔ پنجم کلاینت وب (P5) — تنظیمات امن اتصال و مدل هوش مصنوعی

تاریخ: 2026-09-29
وضعیت: OFFLINE_COMPLETE (بدون کلید عملیاتی یا تماس زنده به سرورهای ابری)
شاهد: V-239 در [Validation Ledger](../../project-memory/VALIDATION_LEDGER.md)
قرارداد: [قرارداد یکپارچه‌سازی](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

## خلاصهٔ کار انجام‌شده

1. **مدیریت کلید امن و ذخیره‌سازی محلی (Encrypted Secret Storage)**:
   - ماژول `src/eitaa_bridge/infrastructure/coordinator/ai_connection.py` کلاس `AiConnectionStore` و مدل `AiConnectionSettings` را پیاده‌سازی کرد.
   - کلیدهای دسترسی مدل‌های زبانی (مانند OpenAI API key) هرگز به‌صورت متن خام در پایگاه‌داده SQLite، لاگ‌ها، یا اشیای بازگشتی API ذخیره نمی‌شوند.
   - رمزنگاری با استفاده از استاندارد AES-256-GCM انجام می‌گیرد. کلید رمزنگاری محلی از متغیر محیطی `EITAA_AI_ENCRYPTION_KEY` دریافت شده یا به‌صورت امن از کلید مخفی ماشین مشتق می‌گردد.
   - در کلیه متدهای استعلام و خروجی‌های API/UI، کلید به‌صورت `key_configured: bool` اعلام می‌شود و هرگز مقدار یا ماسک بخشی از کلید افشا نمی‌گردد. در صورت عدم ارسال کلید جدید در به‌روزرسانی، کلید قبلی بدون تغییر حفظ می‌شود (`unchanged semantics`).

2. **اعتبارسنجی سمت سرور و پیشگیری از SSRF/Egress Attack**:
   - آدرس‌های endpoint به‌صورت سخت‌گیرانه بررسی می‌شوند: پروتکل HTTPS الزامی است؛ استفاده از پروتکل HTTP تنها در صورت loopback (`127.0.0.1`, `localhost`) مجاز است.
   - کاراکترهای اعتبارنامه (مانند `user:pass@host`) در URL صریحاً مسدود می‌شوند (400 `url_credentials_disallowed`).
   - پورت‌های نامتعارف و دامنه‌های غیرمعتبر مسدود می‌شوند.

3. **کنترل هم‌زمانی، بازبینی و حفاظت F-090/F-091**:
   - سیستم دارای شماره نسخه (revision) و قفل خوش‌بینانه است؛ ویرایش هم‌زمان با شماره بازبینی قدیمی با خطای ۴۰۹ (`stale_revision`) مسدود می‌شود.
   - ثبت رویداد `ai_connection_settings_updated` در کاتالوگ رخدادهای سیستم انجام می‌شود.

4. **پروب ترکیبی و حداقل‌محور (Dialect-Aware Synthetic Probe)**:
   - متد `probe()` با استفاده از مکانیزم Provider/Dialect (نظیر OpenAI `/chat/completions`) فراخوانی synthetic بدون ارسال شناسه کاربر، بدون پیام‌های قبلی، بدون شماره تلفن و بدون OTP انجام می‌دهد.
   - خطاهای شبکه، timeout و احراز هویت با صداقت نگاشت شده و هرگز خطاها به عنوان «تأیید زنده» تلقی نمی‌شوند.

5. **ادغام در API مدیریتی**:
   - مسیرهای مدیریتی `GET /api/v2/admin/ai-connection`، `PUT /api/v2/admin/ai-connection` و `POST /api/v2/admin/ai-connection/probe` پیاده‌سازی شدند.
   - ثبت رویدادهای `ai_connection_settings_updated` و `ai_connection_probe_executed` در `event_catalog.py` تکمیل شد.

## وضعیت Acceptance IDها

| شناسه | وضعیت | شرح و شاهد |
|---|---|---|
| P5-A01 | PASS (آفلاین) | مدیر endpoint، کلید، مدل و سقف‌های ورودی/خروجی را ذخیره و بدون نشت کلید بازخوانی می‌کند (`test_ai_connection_settings_crud_and_masking`). |
| P5-A02 | PASS (آفلاین) | ذخیره‌سازی کلید با AES-256-GCM، اعتبارسنجی URL و مسدودسازی credentials و HTTP ناامن (`test_ai_connection_settings_encryption_and_tamper`، `test_ai_connection_endpoint_ssrf_validation`). |
| P5-A03 | PASS (آفلاین) | سازگاری با بازبینی، رد بازبینی منسوخ و حفظ مقادیر قبلی کلید (`test_ai_connection_optimistic_locking_revision`، `test_ai_connection_key_preservation_and_rotation`). |
| P5-A04 | PASS (آفلاین) | آزمون پروب با transport ساختگی و dialect بدون نشت داده (`test_ai_connection_probe_success_with_mock_transport`، `test_ai_connection_probe_fails_closed_when_disabled`). نبود کلید واقعی یا سرور زنده به صراحت `LIVE_PENDING_INPUT` است. |

## نتایج آزمون‌ها و شواهد

- مجموعه آزمون اختصاصی: `tests/test_ai_connection_settings.py` (۱۰ آزمون): ۱۰ passed در ۰.۴۶ ثانیه.
- صحت رویدادهای مشاهده‌پذیری: `tests/test_observability_contract.py` (۶ آزمون): ۶ passed در ۱.۳۶ ثانیه.

## مرز ضمانت و وضعیت Live

تنظیمات و چرخه حیات اتصال AI به‌صورت کامل و آزموده در محیط آفلاین پیاده‌سازی شده است. هیچ کلید زنده یا تماس خارجی با سرورهای خارجی در این فاز انجام نشده است. وضعیت اتصال واقعی در صورت عدم ورود کلید و تأیید کاربر: `LIVE_PENDING_INPUT`.
وضعیت P5: `OFFLINE_COMPLETE`.

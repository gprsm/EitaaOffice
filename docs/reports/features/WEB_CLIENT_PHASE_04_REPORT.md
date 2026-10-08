# گزارش مرحلهٔ چهارم کلاینت وب (P4) — مخاطب واقعی و تحویل مرحله‌ای OTP

تاریخ: 2026-09-29
وضعیت: OFFLINE_COMPLETE (بدون مؤلفهٔ Live)
شاهد: V-238 در [Validation Ledger](../../project-memory/VALIDATION_LEDGER.md)
قرارداد: نسخهٔ 1.8.0 [قرارداد یکپارچه‌سازی](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

## خلاصهٔ کار انجام‌شده

1. **مدل داده و ذخیره‌سازی پایدار (Durable Stage Tracking)**:
   - ماژول `src/eitaa_bridge/infrastructure/coordinator/otp_deliveries.py` کلاس `ServiceOtpDeliveryStore` و رکورد `OtpDeliveryRecord` را پیاده‌سازی کرد.
   - جدول `service_otp_deliveries` در پایگاه‌داده SQLite برای ذخیره و رهگیری مرحله‌ای تحویل OTP ایجاد شد.
   - وضعیت‌ها: `pending`, `running`, `accepted`, `rejected`, `uncertain`, `expired`.
   - مراحل: `admitted`, `resolving`, `importing_contact`, `sending_message`, `completed`, `uncertain`.

2. **حفاظت کامل از حریم خصوصی (Privacy & Zero-Leakage)**:
   - شماره تلفن خام هرگز در جدول، لاگ‌ها، رسیدها، یا خطاهای سیستم ذخیره نمی‌شود؛ تنها `recipient_binding` مبتنی بر HMAC-SHA256 کلید سرور ذخیره می‌گردد.
   - متن پیام OTP و کدهای احراز هرگز در پایگاه‌داده Coordinator، لاگ‌ها، یا رسیدها ذخیره نمی‌شوند.
   - استعلام وضعیت `GET /api/v2/m2m/otp/deliveries/{id}` کاملاً محدود به مالک کلید (`service_credential_id`) است و فیلدهای حساس را بازنمی‌گرداند.

3. **جریان ترکیبی و مرحله‌محور (Stage-Aware Pipeline)**:
   - ماژول `src/eitaa_bridge/application/otp_delivery_pipeline.py` متدهای `handle_otp_delivery_create` و `handle_otp_delivery_status` را پیاده‌سازی کرد.
   - تطبیق binding گیرنده با رزرو ظرفیت P3 سنجیده می‌شود؛ در صورت عدم تطابق با کد ۴۰۰ (`delivery_recipient_mismatch`) رد می‌شود.
   - در صورت وجود مخاطب قبلی، مرحلهٔ import رد شده و از peer موجود استفاده می‌شود (`contact_status='existing'`).
   - در صورت جدید بودن مخاطب، با نام ارائه‌شده import انجام شده و `contact_status='created'` ثبت می‌گردد.
   - پیش از ارسال پیام، با `reservation_store.mark_send_started` استرداد ظرفیت ممنوع می‌شود.
   - در صورت بروز خطای نامعلوم یا timeout شبکه در حین ارسال، وضعیت به `uncertain` تغییر کرده و هیچ‌گونه تلاش مجدد یا fallback خودکار انجام نمی‌گیرد.
   - در صورت شکست ارسال پس از ایجاد مخاطب، مخاطب ایجادشده حفظ می‌شود (عدم rollback جعلی اثر خارجی).

4. **ادغام در API و M2M**:
   - مسیرهای `POST /api/v2/m2m/otp/deliveries` و `GET /api/v2/m2m/otp/deliveries/{id}` به `m2m_api.py` و `api.py` متصل شدند.
   - دامنهٔ مجوز `otp.deliver` به عنوان scope مجاز افزوده شد؛ همچنین ترکیب مجوزهای `messages.send` و `contacts.import` نیز پذیرفته می‌شود.

## وضعیت Acceptance IDها

| شناسه | وضعیت | شرح و شاهد |
|---|---|---|
| P4-A01 | PASS (آفلاین) | شمارهٔ تازه با نام درست به peer متناظر (در ایتا `user:` و در بله `bale:user:`) نگاشت و مخاطب موجود بدون import مکرر ارسال می‌شود. آزمون‌های `test_fresh_recipient_resolve_import_send`، `test_existing_recipient_skips_contact_import`، و `test_bale_recipient_peer_preserved`. |
| P4-A02 | PASS (آفلاین) | تکرار همان کلید idempotency پاسخ قبلی را بدون فراخوانی مجدد برمی‌گرداند (200 replayed)؛ تغییر بدنه با 409 conflict رد می‌شود؛ انقضای پیش از ارسال به state=expired منجر می‌شود؛ timeout شبکه به وضعیت صادقانهٔ uncertain ختم شده و هرگز auto-retry نمی‌شود. آزمون‌های `test_idempotent_replay_and_conflict`، `test_expired_before_dispatch_does_not_send`، `test_send_timeout_is_uncertain_and_never_auto_retried`. |
| P4-A03 | PASS (آفلاین) | اثر خارجی با صداقت ثبت می‌شود؛ در صورت شکست ارسال، ایجاد مخاطب با وضعیت `contact_status='created'` و `send_status='rejected'` باقی می‌ماند و rollback صورت نمی‌گیرد. آزمون `test_send_failure_after_contact_creation_does_not_rollback_contact`. |
| P4-A04 | PASS (آفلاین) | حریم خصوصی و تفکیک سرویس‌ها برقرار است؛ استعلام سرویس دیگر 404 می‌دهد؛ هیچ شماره خام یا متنی در خروجی یا دیتابیس نیست؛ کنترل scope دقیق انجام می‌شود. آزمون‌های `test_service_isolation_and_privacy`، `test_scope_enforcement`، `test_dispatch_m2m_routing_for_otp_deliveries`. |

## نتایج آزمون‌ها و شواهد

- مجموعهٔ تست اختصاصی: `tests/test_otp_deliveries.py` (۱۲ آزمون): ۱۲ passed در ۸.۳۵ ثانیه.
- آزمون یکپارچهٔ P1 تا P4: `tests/test_sender_profiles.py tests/test_delivery_preflight.py tests/test_delivery_reservations.py tests/test_otp_deliveries.py` (۴۱ آزمون): ۴۱ passed در ۲۷.۷ ثانیه بدون هیچ شکست.
- عدم نشت داده: در کلیه پاسخ‌ها و سطور جدول `service_otp_deliveries`، هیچ شماره یا OTP خامی درج نشده است.

## مرز ضمانت و وضعیت Live

کلیه شواهد و آزمون‌ها روی محیط آزمایشی ایزوله، داده‌های موقت ساختگی و بدون برقراری تماس واقعی با شبکه یا کاربران انجام شده‌اند. فاز P4 هیچ عملیات زنده روی حساب‌های عملیاتی انجام نداده است.
وضعیت P4: `OFFLINE_COMPLETE` (بدون مؤلفهٔ Live).
مرحلهٔ بعدی: آغاز فازهای P5 و P6 (تنظیمات امن اتصال AI و سیاست داده).

# تحویل فنی مرحلهٔ ششم کلاینت وب (P6) — سیاست داده و دروازه خروجی مدل هوش مصنوعی

تاریخ: 2026-09-29
وضعیت خروجی: OFFLINE_COMPLETE (مرحلهٔ بعدی: P7)
شاهد: V-240 در [Validation Ledger](../project-memory/VALIDATION_LEDGER.md)

## مولفه‌ها و ماژول‌های تحویل‌شده

1. **مدیریت سیاست داده و پالایش**:
   - فایل: `src/eitaa_bridge/infrastructure/coordinator/ai_data_policy.py`
   - کلاس‌ها و توابع: `AiDataPolicyStore`, `AiDataPolicy`, `AiDataPolicyError`, `build_outbound_egress`, `sanitize_text`, `pseudonymize_user_id`
   - ویژگی‌ها: ۴ سطح کنترل سیاست (disabled, current_message, limited_history, approved_context)، پالایش خودکار شماره‌های تلفن، کدهای OTP و کلیدهای محرمانه، و مستعارسازی امن شناسه‌های کاربران.

2. **درگاه‌های مدیریتی (Admin API Routes)**:
   - `GET /api/v2/admin/ai-data-policy/{service_id}`: دریافت سیاست جاری سرویس.
   - `PUT /api/v2/admin/ai-data-policy/{service_id}`: تنظیم سیاست با کنترل نسخه (revision).

3. **یکپارچه‌سازی درگاه ارتباطی (Agent Gateway)**:
   - فایل‌ها: `src/eitaa_bridge/application/agent_gateway.py` و `src/eitaa_bridge/application/m2m_api.py`
   - اتصال به فروشگاه سیاست داده، اعمال fail-closed قبل از خروج پیام به مدل و آزادسازی مدعیان در صورت خطای سیاست.

4. **آزمون‌های خودکار**:
   - فایل: `tests/test_ai_data_policy.py` (۸ تست سبز).

## وضعیت Live

- اتصال عملیاتی زنده: `LIVE_PENDING_INPUT`.
- سیاست داده فعال و در کلیه مسیرها برقرار است.

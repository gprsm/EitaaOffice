# گزارش مرحلهٔ ششم کلاینت وب (P6) — سطح دسترسی و سیاست دادهٔ مدل آنلاین

تاریخ: 2026-09-29
وضعیت: OFFLINE_COMPLETE
شاهد: V-240 در [Validation Ledger](../../project-memory/VALIDATION_LEDGER.md)
قرارداد: [قرارداد یکپارچه‌سازی](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

## خلاصهٔ کار انجام‌شده

1. **انطباق سطوح سیاست داده در سطح سرور (Server-Side Egress Gate)**:
   - ماژول `src/eitaa_bridge/infrastructure/coordinator/ai_data_policy.py` کلاس `AiDataPolicyStore` و جدول `service_ai_data_policies` را پیاده‌سازی کرد.
   - ۴ سطح سیاست مجاز و کنترل‌شده تعریف شد:
     - `disabled`: رد فوری هرگونه ارسال داده به مدل با خطای ۴۰۳ (`ai_policy_disabled`).
     - `current_message`: ارسال صرفاً پیام جاری پس از پالایش (بدون تاریخچه قبلی).
     - `limited_history`: پالایش پیام جاری به همراه حداکثر تعداد گردش‌های مجاز مکالمه (`max_history_turns`).
     - `approved_context`: اجازه درج متون زمینه‌ای مشخص و پالایش‌شده بر اساس فهرست مجاز (`allowed_context_types`).
   - سطوح ناامن نظیر `full_database` یا `unrestricted` صریحاً رد و مسدود می‌شوند (400 `ai_policy_level_invalid`).

2. **حفاظت از حریم خصوصی و پالایش چندلایه (Sanitization & Pseudonymization)**:
   - تابع `sanitize_text()` کلیه شماره‌های همراه ایرانی (با الگوهای 09xx و +989xx و 00989xx)، کدهای OTP چهار تا هشت رقمی، و توکن‌های احراز هویت / کلیدهای محرمانه را با توکن‌های امن جانمایی (`[REDACTED_PHONE]`, `[REDACTED_OTP]`, `[REDACTED_SECRET]`) جایگزین می‌کند.
   - تابع `pseudonymize_user_id()` شناسه کاربر خام (`web_user_id`) را با شناسهٔ مستعار امن و تک‌طرفه (`usr_<hex>`) جایگزین می‌کند تا امکان رهگیری کاربر میان سرویس‌های مختلف وجود نداشته باشد.
   - داده‌های OTP، مخاطبان و کلیدهای احراز هرگز وارد سازندهٔ کانتکست خروجی مدل نمی‌شوند.

3. **یکپارچه‌سازی با درگاه Agent و M2M**:
   - فایل‌های `src/eitaa_bridge/application/agent_gateway.py` و `src/eitaa_bridge/application/m2m_api.py` برای سنجش سیاست پیش از برقراری هرگونه ارتباط خارجی به‌روزرسانی شدند.
   - متد `handle_agent_chat` در صورت غیرفعال بودن سیاست بلافاصله با کد ۴۰۳ خطا بازگردانده و فراخوانی مدل را fail-closed می‌کند. ادعاهای درون‌فرایندی طبق F-091 آزاد می‌گردند.
   - در صورت فعال بودن `LiveAiAgentAdapter`، پیام و تاریخچه از طریق `build_outbound_egress` پالایش شده و سپس به پایانه ارسال می‌گردد.
   - سازگاری کامل با آزمون‌های قدیمی حفظ شده و `TestAgentAdapter` در غیاب پیکربندی زنده بدون خطا به کار خود ادامه می‌دهد.

4. **مدیریت درگاه‌های مدیریتی (Admin API Routes)**:
   - اندپوینت‌های `GET /api/v2/admin/ai-data-policy/{service_id}` و `PUT /api/v2/admin/ai-data-policy/{service_id}` پیاده‌سازی شدند.
   - رویداد `ai_data_policy_updated` در کاتالوگ ثبت گردید.

## وضعیت Acceptance IDها

| شناسه | وضعیت | شرح و شاهد |
|---|---|---|
| P6-A01 | PASS (آفلاین) | سطوح سیاست در دیتابیس پایدار و در سرور پیش از هرگونه فراخوانی اعمال می‌گردد؛ رد سطوح نامعتبر (`test_ai_data_policy_store_crud_and_validation`، `test_build_outbound_egress_levels`). |
| P6-A02 | PASS (آفلاین) | تفکیک کامل سرویس‌ها و مستعارسازی شناسه‌ها بدون امکان دسترسی سرویس دیگر یا نشت PII (`test_cross_service_data_policy_isolation`، `test_pseudonymize_user_id_is_stable_and_isolated`). |
| P6-A03 | PASS (آفلاین) | مسدودسازی فوری در صورت غیرفعال بودن سیاست با ۴۰۳ و مدیریت F-091 (`test_m2m_chat_data_policy_disabled_returns_403`). |
| P6-A04 | PASS (آفلاین) | آزمون با پایانه ساختگی (MockTransport) و بررسی بایت‌های خروجی: حذف شماره تلفن، حذف کد OTP و جایگزینی شناسه خام کاربر با مستعار صریحاً اثبات شد (`test_m2m_chat_egress_scrubbing_and_pseudonymization_with_live_adapter`). |

## نتایج آزمون‌ها و شواهد

- مجموعه آزمون اختصاصی: `tests/test_ai_data_policy.py` (۸ آزمون): ۸ passed در ۰.۵۲ ثانیه.
- آزمون‌های قبلی درگاه عامل: `tests/test_agent_gateway.py` (۲۹ آزمون): ۲۹ passed در ۸.۲۱ ثانیه بدون رگرسیون.
- آزمون‌های مشاهده‌پذیری: `tests/test_observability_contract.py` (۶ آزمون): ۶ passed در ۱.۳۶ ثانیه.

## مرز ضمانت و وضعیت Live

سیاست داده و دروازه خروجی به‌صورت کامل در سطح سرور مستقر و آزموده شده است. بدون عبور از این دروازه، هیچ داده‌ای به مدل‌های زبانی ارسال نمی‌شود. با توجه به نبود مدل عملیاتی، تماس زنده `LIVE_PENDING_INPUT` است.
وضعیت P6: `OFFLINE_COMPLETE`.

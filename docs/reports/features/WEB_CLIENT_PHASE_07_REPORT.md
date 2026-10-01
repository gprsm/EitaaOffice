# گزارش مرحلهٔ هفتم کلاینت وب (P7) — کلاینت مرجع Backend وب و آزمون انتها‌به‌انتها

تاریخ: 2026-09-29
وضعیت: OFFLINE_COMPLETE (ادغام مخزن وب‌سایت واقعی: BLOCKED_WITH_REASON)
شاهد: V-241 در [Validation Ledger](../../project-memory/VALIDATION_LEDGER.md)
قرارداد: [قرارداد یکپارچه‌سازی](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

## خلاصهٔ کار انجام‌شده

1. **طراحی ماژول و SDK مرجع برای سمت سرور وب (Reference Web Backend Client)**:
   - فایل `src/eitaa_bridge/application/web_client_reference.py` کلاس‌های `BridgeWebClient` و `WebOtpSession` را پیاده‌سازی کرد.
   - معماری امن «صفر کلید در مرورگر»: تمامی اعتبارنامه‌های M2M و کلیدهای هوش مصنوعی منحصراً در لایهٔ Backend وب ذخیره و استفاده می‌شوند و هرگز به فرانت‌اند یا مرورگر کاربر نشت نمی‌کنند.
   - مدیریت چالش OTP سمت وب: تولید کد، اعتبارسنجی با مقایسهٔ زمان‌ثابت (`hmac.compare_digest`)، سقف تعداد تلاش (جلوگیری از Brute-force)، بازه انقضا (TTL) و مصرف یک‌باره (Anti-replay).

2. **جریان کامل و مرحله‌محور (Preflight → Reserve → Dispatch → Poll → Verify)**:
   - متد `preflight()`: سنجش اولیهٔ آمادگی سرور و حساب فرستنده پیش از نمایش صفحهٔ ورود یا ارسال OTP.
   - متد `reserve_capacity()`: ثبت رزرو موقت با هش پایدار شماره تلفن (`recipient_binding`).
   - متد `dispatch_otp()`: هدایت درخواست به پایپ‌لاین ترکیبی P4 با کلید یکتایی (`idempotency_key`) و رهگیری مراحل ارسال.
   - متد `poll_delivery_status()`: حلقهٔ استعلام با سقف مشخص و درک `Retry-After` جهت جلوگیری از مصرف نابجای سقف تراکنش (rate limit 60/min).
   - متد `chat()`: هدایت امن پیام‌های چت به درگاه عامل با رعایت کامل سطوح سیاست P6.

3. **آزمون‌های انتها‌به‌انتها روی سرور Loopback واقعی (Real HTTP E2E Tests)**:
   - فایل `tests/test_web_client_e2e.py` شامل ۱۱ آزمون جامع بر بستر `BridgeApiHttpServer` روی لوپ‌بک (`127.0.0.1:PORT`) پیاده‌سازی شد؛ ترنسپورت جعلی حذف گردید و تنها در پایین‌ترین مرز Provider و AI آداپتورهای شبیه‌ساز مستقر شدند.
   - کلیه مراحل واقعی شبکه، سریال‌سازی JSON، مسیریابی canonical (`POST /api/v2/m2m/delivery/reservations/{id}/cancel`)، احراز هویت، تراکنش‌های دیتابیس Coordinator SQLite، قفل‌های نظرسنجی مستقل، و بازگشت پایانهٔ نامعلوم (`uncertain`) اعتبارسنجی شدند.

## وضعیت Acceptance IDها

| شناسه | وضعیت | شرح و شاهد |
|---|---|---|
| P7-A01 | PASS (Loopback واقعی) | جریان کامل Backend و نشست‌های امن چالش OTP روی سرور واقعی HTTP لوپ‌بک؛ صفر کلید در مرورگر (`test_e2e_loopback_preflight_and_reservations`، `test_web_otp_session_verification_and_anti_tamper`). |
| P7-A02 | PASS (Loopback واقعی) | انقضای رزرو، تعارض تکرار با بدنه متفاوت (409)، مپینگ وضعیت غیرقطعی به uncertain پایانه بدون تلاش خودکار (`test_e2e_loopback_reservation_expiry_rejection`، `test_e2e_loopback_terminal_uncertain_never_accepted`، `test_e2e_loopback_idempotency_replay_and_conflict`). |
| P7-A03 | PASS (Loopback واقعی) | آزمون واقعی E2E با سرور HTTP، شمارنده‌ها در پایین‌ترین مرز، عدم نشت داده یا توکن در پی‌لودها، و پراکسی ایمن چت عامل (`test_e2e_loopback_otp_dispatch_poll_and_verify`، `test_e2e_loopback_ai_chat_proxy`، `test_e2e_loopback_zero_secrets_leak`). |
| P7-A04 | PARTIAL / BLOCKED_WITH_REASON | نمونه و SDK مرجع در همین پروژه آماده، با کلاینت واقعی اجرا و تأیید شد. ادغام با مخزن وب‌سایت خارجی مسدود به دلیل عدم حضور در checkout است. |

## نتایج آزمون‌ها و شواهد

- مجموعه آزمون‌های اختصاصی: `tests/test_web_client_e2e.py` (۱۱ آزمون loopback واقعی): ۱۱ passed در ۲۳.۶ ثانیه.
- آزمون‌های رگرسیون مرتبط: `tests/test_web_client_regression.py` (۶ آزمون): ۶ passed.
- وضعیت کلی P7: `OFFLINE_COMPLETE (کلاینت مرجع و E2E واقعی) / BLOCKED_WITH_REASON (مخزن وب‌سایت خارجی)`.

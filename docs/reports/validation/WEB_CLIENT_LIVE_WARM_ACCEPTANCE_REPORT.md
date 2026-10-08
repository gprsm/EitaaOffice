# گزارش پذیرش و آزمون گرم کلاینت وب (P8) — ابزار اجرایی و ماتریس پذیرش زنده

تاریخ: 2026-09-29
وضعیت: OFFLINE_READY / LIVE_PENDING_INPUT
شاهد: V-242 در [Validation Ledger](../../project-memory/VALIDATION_LEDGER.md)
قرارداد: [قرارداد یکپارچه‌سازی](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md)

## خلاصهٔ کار انجام‌شده

1. **عملیاتی‌سازی ابزار اجرای آزمون گرم (Warm Acceptance Runner)**:
   - اسکریپت `scripts/web_client_live_runner.py` با قابلیت پیش‌فرض غیرفعال (`default-off`)، حالت `dry-plan`، و اجرای کامل عملیاتی بازنویسی شد.
   - استاب غیرمشروط قبلی برداشته شد و کنترل‌های سه‌گانه جایگزین گردید:
     الف) تأیید صریح اپراتور (interactive y/n prompt در محیط tty یا پرچم صریح `--confirm`؛ توقف امن در صورت رد یا عدم تأیید با `operator_confirmation_required`/`operator_confirmation_rejected`).
     ب) حل توکن با اولویت CLI (`--token`)، متغیر محیطی (`BRIDGE_M2M_TOKEN`)، یا دریافت امن در حافظه با `getpass` (توقف امن با `missing_token` در غیاب توکن).
     ج) اجرای واقعی تماس‌های API از طریق `BridgeWebClient` بر روی سرور Loopback (`http://127.0.0.1:PORT`) برای اقدامات `preflight`، `reserve`، `otp-dispatch`، `otp-status`، `ai-chat`، و `ai-probe`.
   - شمارنده‌ها و نشانگرهای تأیید گرم (`warm_verified: true/false`)، راهنمای بازیابی صادقانه در صورت بروز خطا، و عدم چاپ رمزها یا شماره‌های خام.
   - **هماهنگ‌سازی با قواعد فاز (V-248/F-100):** ورودی‌های حساس (توکن، شماره، متن خصوصی، نام مخاطب) دیگر از argv پذیرفته نمی‌شوند و فقط از متغیرهای محیطی (`BRIDGE_M2M_TOKEN`، `BRIDGE_ADMIN_SESSION_TOKEN`/`BRIDGE_ADMIN_CSRF_TOKEN`، `BRIDGE_OTP_TARGET_PHONE`، `BRIDGE_OTP_MESSAGE_TEXT`، `BRIDGE_AI_MESSAGE_TEXT`، `BRIDGE_OTP_CONTACT_NAME`) یا پرامپت مخفی گرفته می‌شوند؛ پیش‌فرض شماره/پیام حذف و بدون هدف صریح fail-closed است (`dispatch_target_required`/`dispatch_message_required`)؛ عملیات اثرگذار (reserve/otp-dispatch/ai-chat) فقط با تأیید همان عملیات (`--confirm <action>`؛ در غیر این صورت `same_operation_confirmation_required`)؛ `allow_abbrev=False`؛ خروجی هرگز پاسخ خام AI یا متن exception را چاپ نمی‌کند (فقط `response_length` و کدهای امن)؛ `warm_verified` فقط با شاهد نشست فقط‌خواندنی (M2M: `GET /api/v2/m2m/agent/health`؛ admin: `GET /api/v2/app-auth/me` با نقش admin) و شمار connect واقعی از transport (backend شبکهٔ httpcore) و round-trips گزارش می‌شود — پاسخ موفق preflight یا رزرو به‌تنهایی warm نیست؛ `ai-probe` با احراز واقعی مسیر admin (کوکی نشست `eitaa_bridge_app_session` + هدر `X-CSRF-Token`) اجرا می‌شود و Bearer سرویس M2M به‌تنهایی رد می‌گردد.

2. **ماتریس اجرای قابلیت‌ها و وضعیت تفکیک‌شده**:

| قابلیت | وضعیت آفلاین | وضعیت Live | پیش‌نیازهای عملیاتی مورد نیاز برای Live |
|---|---|---|---|
| **Eitaa OTP Delivery** | PASS (پایپ‌لاین، رزرو، مخاطب، E2E لوپ‌بک) | LIVE_PENDING_INPUT | حساب عملیاتی احراز‌شده در ایتا، اجازهٔ صریح برای ارسال یک پیام آزمایشی به شمارهٔ تستی متعلق به مالک، و تعیین سقف اثر. |
| **Bale OTP Delivery** | PASS (پایپ‌لاین، رزرو، نگاشت peer، E2E لوپ‌بک) | LIVE_PENDING_INPUT | حساب شخصی احراز‌شده در بله، اجازهٔ صریح ثبت یک مخاطب آزمایشی و ارسال یک پیام، و رضایت مالک برای اثر خارجی. |
| **AI Egress & Gateway** | PASS (رمزنگاری کلید، سیاست سرور، پالایش، ضد SSRF) | LIVE_PENDING_INPUT | ارائهٔ کلید دسترسی واقعی API (مانند OpenAI یا ارائه‌دهنده داخلی) در تنظیمات ادمین، اجازهٔ پروب آنلاین با دادهٔ ساختگی، و تخصیص سیاست به سرویس. |
| **Web Backend Client** | PASS (کلاینت مرجع، نشست امن، رانر عملیاتی کامل) | LIVE_PENDING_INPUT | استقرار Backend وب بر روی زیرساخت واقعی و اجرای فرآیند با کلاینت سرور. |

3. **آزمون‌های خودکار ابزار Runner**:
   - فایل `tests/test_web_client_live_runner.py` با ۱۰ آزمون اختصاصی رفتار پیش‌فرض بدون اثر، اعتبارسنجی مبدأ لوپ‌بک، مسدودسازی تلاش‌های بدون مجوز، واکنش به رد تأیید توسط اپراتور، فقدان توکن، و اجرای واقعی preflight، reserve، dispatch و AI chat را بر روی سرور لوپ‌بک راستی‌آزمایی کرد.
   - **بازآزمایی و گسترش (V-248/F-100):** مجموعه به ۱۷ آزمون گسترش یافت: رد گزینه‌های حساس argv (SystemExit)، fail-closed بدون هدف صریح یا متن پیام، رد bare/mismatch confirm برای عملیات اثرگذار، اثبات شاهد نشست و `connects≥1`، حریم خصوصی خروجی (نبود شماره/متن/پاسخ خام AI)، و ai-probe با نشست admin واقعی + CSRF روی loopback شامل رد Bearer M2M — همه سبز.

## وضعیت Acceptance IDها

| شناسه | وضعیت | شرح و شاهد |
|---|---|---|
| P8-A01 | PASS (رانر عملیاتی) | اسکریپت runner، حالت dry-plan، گارد محافظتی opt-in، حل توکن و حفظ حریم خصوصی به‌طور مستقل پاس شدند (`test_runner_default_dry_plan`، `test_runner_origin_validation`، `test_runner_live_fails_closed_when_token_missing`). |
| P8-A02 | PASS (Loopback) / LIVE_PENDING_INPUT | رانر برای پیش‌پرواز، رزرو و ارسال OTP روی لوپ‌بک آزموده شد (`test_runner_live_preflight_real_execution`، `test_runner_live_reserve_and_dispatch_real_execution`)؛ اجرای زنده با اپراتور تلکام نیازمند حساب احراز‌شده است. |
| P8-A03 | PASS (Loopback) / LIVE_PENDING_INPUT | چت و پروب هوش مصنوعی روی لوپ‌بک تأیید شد (`test_runner_live_ai_chat_real_execution`)؛ تماس با مدل بیرونی نیازمند ورود کلید واقعی API است. |
| P8-A04 | PASS (عملیاتی) | مدیریت توقف امن (Abort/Recovery)، تأیید صریح اپراتور، گزارش warm counts و بازگشت صادقانه در رد تأیید تأیید شد (`test_runner_live_aborted_when_operator_rejects`، `test_runner_live_aborted_when_confirmation_missing_in_non_interactive`). |
| P8-A05 | PASS (صداقت گزارش) | هیچ وضعیت زنده‌ای جعل نشده است؛ مرزها در گزارش و لجر ثبت شدند. |

## نتایج آزمون‌ها و شواهد

- آزمون اختصاصی Runner: `tests/test_web_client_live_runner.py` (۱۰ آزمون): ۱۰ passed در ۷.۰۲ ثانیه.
- خروجی آزمایشی: اجرای `python scripts/web_client_live_runner.py --dry-plan` ماتریس بدون خطا با کد صفر تولید کرد.

## مرز ضمانت و اعلام صریح

- رانر عملیاتی کامل است و تماس‌های واقعی با API سرور برقرار می‌کند.
- عملیات زنده با کاربران واقعی یا سرورهای خارجی تا زمان دریافت مجوز و ورودی‌های مشخص مسدود و در وضعیت `LIVE_PENDING_INPUT` باقی می‌ماند.
- وضعیت فاز P8: `OFFLINE_READY / LIVE_PENDING_INPUT`.

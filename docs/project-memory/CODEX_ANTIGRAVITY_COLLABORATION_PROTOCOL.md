# قرارداد همکاری و لاگ مشترک Codex / AntiGravity

وضعیت: `ACTIVE / MANDATORY`  
تاریخ اجرا: 2026-08-25  
مرجع برنامه: [STABILIZATION_REMEDIATION_PLAN_2026-08-25.md](STABILIZATION_REMEDIATION_PLAN_2026-08-25.md)  
Handoff جاری: [ANTIGRAVITY_STABILIZATION_CURRENT.md](../handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md)

## هدف

این قرارداد تضمین می‌کند Codex و AntiGravity بتوانند پروژه را در زمان‌های جداگانه ادامه دهند، بدون اینکه بررسی، شکست، تصمیم یا تغییر مهم فقط در Chat یک Agent باقی بماند.

## ترتیب اجباری شروع هر Agent

1. `AGENTS.md`
2. `docs/project-memory/README.md`
3. `docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md`
4. `docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md`
5. `docs/project-memory/STABILIZATION_EXECUTION_LOG.md`
6. `docs/project-memory/FINDINGS_REGISTER.md`
7. `docs/project-memory/VALIDATION_LEDGER.md`
8. سند و تست‌های مربوط به Goal فعال

## مالکیت نوشتن

- در هر لحظه فقط یک Agent حق Write دارد.
- کاربر اعلام کرده Codex و AntiGravity هم‌زمان توسعه نمی‌دهند. Agent تازه باید Handoff را بخواند و Run باز را بررسی کند.
- اگر Run باز یا تغییر ناشناخته دیده شد، هیچ reset/checkout/clean انجام نشود؛ وضعیت به‌عنوان Finding/Blocker ثبت شود.

## قالب اجباری هر اصلاح

هر اصلاح باید این زنجیره را مستند کند:

`Problem → Product goal → Root cause → Affected files/lines → RED evidence → Patch → Targeted GREEN → Relevant regression → Security/operational effect → Docs/Findings/Ledger → Next action`

حداقل داده‌های Run/Step در `STABILIZATION_EXECUTION_LOG.md`:

- `goal_id`, `run_id`, `event_id` و transition وضعیت؛
- زمان شروع/پایان ISO-8601 و مدت؛
- فرمان sanitize‌شده، cwd و exit code؛
- فایل‌های قصدشده و واقعاً تغییرکرده؛
- SHA-256 قبل/بعد برای فایل‌های امن؛
- تعداد collected/pass/fail/error/skip؛
- failure class، reason code و retry/supersedes؛
- اثر بیرونی و مرجع تأیید کاربر؛
- لینک Finding، Validation و Handoff.

## قواعد تست

1. ابتدا failure موجود یا gap قرارداد با شاهد `RED_VERIFIED` ثبت شود.
2. تست فقط برای سبزکردن کد ناامن تغییر نکند؛ ابتدا `product_regression` در برابر `test_drift` تعیین شود.
3. پس از patch، تست هدفمند و سپس regression متناسب اجرا شود.
4. تغییر قرارداد مرکزی در نهایت suite کامل Backend/UI/build/docs را می‌خواهد.
5. هر شکست قبل از retry ثبت می‌شود؛ خروجی قبلی حذف یا بازنویسی نمی‌شود.
6. آزمون تکراری بدون Trigger ممنوع است؛ دلیل تکرار در Ledger نوشته شود.

## مرز اطلاعات حساس و عملیات

- Token، Cookie، OTP، رمز، Session، شمارهٔ کامل، متن خصوصی، raw payload و مسیر حساس در Chat/Log/Test output/Report ممنوع‌اند.
- نمایش شمارهٔ کامل در UI مجاز محصول، مجوز ثبت آن در log/audit/diagnostic نیست.
- داده‌های عملیاتی، Login/Send/WordPress/Firewall/Proxy/Port و Git stage/commit/push تابع AGENTS و تأیید صریح‌اند.
- Bale در تثبیت فعلی فقط fail-closed و اصلاح می‌شود؛ قابلیت تازه توسعه داده نمی‌شود.

## به‌روزرسانی Handoff جاری

پس از هر Run معنادار، `docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md` باید شامل این موارد شود:

- Goal و Run فعال/آخرین Run بسته؛
- کار انجام‌شده و فایل‌های تغییرکرده؛
- آخرین RED/GREEN و شمار تست؛
- Findings باز/بسته؛
- اثر بیرونی؛
- اولین فرمان دقیق ادامه.

گزارش تاریخی phase در فایل جدا حفظ می‌شود؛ Handoff جاری یک pointer قابل‌به‌روزرسانی است.


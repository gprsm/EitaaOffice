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

## قرارداد اختصاصی ایندکس و گزارش

- تمام Taskهای چهار سطح ایندکس/WordPress/reporting/intelligence علاوه بر این سند، تابع `INDEX_INTELLIGENCE_FOUR_LEVEL_OPERATING_MODEL.md` و `MULTI_AGENT_DEVELOPMENT_GOVERNANCE.md` هستند.
- کاربر مالک دامنه و پذیرش نهایی است. Codex مدیر معماری/یکپارچه‌سازی و writer/promoter پیش‌فرض اسناد canonical این workstream است.
- AntiGravity، Claude، Gemini یا هر Agent دیگر فقط بر اساس Task Contract و کلاس ریسک نقش می‌گیرد؛ نام ابزار مجوز معماری، عملیات Live یا تغییر canonical ایجاد نمی‌کند.
- Agent مجری به‌طور پیش‌فرض خروجی `AGENT_COMPLETED_UNREVIEWED` تحویل می‌دهد. پذیرش فقط پس از review، آزمون متناسب و promotion توسط writer canonical است.
- شناسه‌های F/V/ADR/Source/Question در taskهای واگذارشده موقت‌اند؛ تخصیص canonical فقط در workstream مدیر انجام می‌شود.

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

## مجوز دائمی انتشار محصول نهایی

- کاربر در 2026-08-26 دستور داد پس از رسیدن هر سناریو به محصول نهایی، نتیجه در GitHub push شود. این دستور مجوز دائمی `stage/commit/push` برای همان snapshot نهایی و آزموده‌شده است و لازم نیست در پایان هر سناریو دوباره پرسیده شود.
- پیش از commit باید scope فایل‌ها، نبود دادهٔ عملیاتی/credential، تست‌های متناسب، کنترل اسناد و وضعیت remote سنجیده و در Ledger/Execution Log ثبت شود.
- commit باید پیام مرتبط با سناریو داشته باشد و push فقط روی شاخهٔ کاری اختصاصی انجام شود. `main`، merge، force-push، حذف branch/tag و بازنویسی remote history بدون دستور صریح جداگانه ممنوع‌اند.
- اگر محصول هنوز نهایی نیست، تست قرمز است، credential/دادهٔ عملیاتی مشکوک است یا GitHub قابل دسترسی نیست، push انجام نمی‌شود؛ blocker و اقدام بعدی دقیق ثبت و به کاربر اعلام می‌شود.
- پس از push، برابری local/remote hash و ثابت‌ماندن `main` کنترل می‌شود. لینک branch/PR، commit نهایی و نتیجهٔ verify در handoff کاربر اعلام می‌گردد.

## به‌روزرسانی Handoff جاری

پس از هر Run معنادار، `docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md` باید شامل این موارد شود:

- Goal و Run فعال/آخرین Run بسته؛
- کار انجام‌شده و فایل‌های تغییرکرده؛
- آخرین RED/GREEN و شمار تست؛
- Findings باز/بسته؛
- اثر بیرونی؛
- اولین فرمان دقیق ادامه.

گزارش تاریخی phase در فایل جدا حفظ می‌شود؛ Handoff جاری یک pointer قابل‌به‌روزرسانی است.

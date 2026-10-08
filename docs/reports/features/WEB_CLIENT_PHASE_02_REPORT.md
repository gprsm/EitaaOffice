# P2 — گزارش فاز نرخ واقعی و API پیش‌بررسی

تاریخ: 2026-09-28
وضعیت: `OFFLINE_COMPLETE` — بدون هیچ مؤلفه یا عملیات Live
HEAD آغاز/پایان: `41dc87a2` روی `codex/bale-web-client-instructions` — بدون commit/push (توضیح در «مرز انتشار»)

## شرح تحویل

- **سیاست واقعی در admission و اجرا**: همان نمونهٔ `AccountExecutionPolicyService` که در composition root ساخته می‌شود به orchestrator تزریق شد و برای هر تلاش تازهٔ mutation (send_text، send_media، contacts.upsert/remove) یک token اتمیک قبل از تماس با Provider می‌گیرد و نتیجه را ثبت می‌کند. مسیرهای replay پیش از این نقطه برمی‌گردند و هرگز token مصرف نمی‌کنند؛ با سطل خالی، بازپخش یک کلیدِ کاملاً موفق همچنان از رسید پایدار بازپخش می‌شود. مالک واحد token و refund حفظ شد و مسیر persistent-job قبلی بدون تغییر کار می‌کند.
- **preflight فقط‌خواندنی**: `POST /api/v2/m2m/delivery/preflight` با `sender_profile_id`/`intent` و `recipient_kind=existing|new` (شماره لازم نیست). پاسخ شامل `decision` (ready|wait|unavailable|unsupported|unknown)، `can_attempt`، `retry_after_seconds`، `sender_profile_revision`، `observed_at`، `valid_until` (+5s)، `steps` (existing: resolve→send؛ new: prepare_contact→resolve→send) و `constraints` است. هیچ acquire، worker RPC، resolve شبکه‌ای یا تغییر circuit رخ نمی‌دهد؛ ردیف `account_execution_limits` بر اثر preflight ساخته نمی‌شود و خواندن متوالی state را تغییر نمی‌دهد.
- **سه محدودیت جدا**: `credential_quota` (پنجرهٔ درخواست HTTP هر credential — polling وضعیت اینجا شمرده می‌شود و هرگز با پیام اشتباه نمی‌شود)، `local_policy` (bucket حساب+عملیات و circuit) و `provider_observed` (cooldown مشاهده‌شده از Provider مانند flood-wait). نبود cooldown فقط «مشاهده‌نشده» است، نه «سهمیهٔ نامحدود»؛ حساب بی‌سابقه constraint با `certainty: "assumed"` می‌گیرد.
- **snapshot صادقانه**: `read_only_snapshot` جدید روی `AccountExecutionPolicyService` refill را تا زمان جاری محاسبه می‌کند بدون acquire/mutation/worker/شبکه/تغییر circuit؛ ردیف غایب یعنی «هرگز محدودیت محلی اعمال نشده» نه «ظرفیت نامحدود». clock قابل تزریق است (`now`).
- **enforce ارسال واقعی**: acquire اتمیک در orchestrator فقط برای تلاش نخستِ mutation؛ replay هرگز به admission نمی‌رسد. رد admission پیش از تماس با Provider با `429 provider_operation_rate_limited` (یا `503 provider_operation_circuit_open`) با هدر `Retry-After` (گرد رو به بالا، سقف موانع همان مسیر) همراه است.
- **مهاجرت/lifecycle**: حساب آرشیو/غیرفعال/غایب → `503 unavailable`؛ حساب غیرمجاز فقط verdict حصار می‌گیرد و هیچ جزئیات constraint دریافت نمی‌کند.

## یادداشت طراحی

نام endpoint از پیشنهاد `POST /api/v1/delivery/preflight` به‌عنوان هدف قرارداد به `POST /api/v2/m2m/delivery/preflight` نهایی شد تا با مرز و الگوی قرارداد جاری M2M (Bearer `eb_svc_`، scope، فاصلهٔ جدای M2M از M2M بیرونی) سازگار باشد. سیاست محلی برای ایتا/بله مقدار پیکربندی است، نه fact Provider؛ هیچ سقف عمومی ادعایی از تجربه یا حدس اضافه نشده است.

## وضعیت acceptance IDها

| ID | وضعیت | شاهد |
|---|---|---|
| P2-A01 | PASS (آفلاین) | `test_preflight_ready_is_read_only_and_repeatable`، `test_policy_refill_cooldown_and_circuit_with_fake_clock`، `test_account_a_does_not_block_account_b` |
| P2-A02 | PASS (آفلاین) | `test_full_stack_send_enforcement_and_replay` (ارسال ششم با 429 و صفر فراخوانی آداپتور؛ replay بدون مصرف token) + `test_composition_shares_one_policy_instance` |
| P2-A03 | PASS (قرارداد)؛ نمایش UI به P7 | قرارداد 1.6.0 بند «Delivery preflight»؛ نمایش دلیل/countdown در کلاینت وب بخش P7 است و در دروازهٔ E2E همان فاز سنجیده می‌شود — مؤلفهٔ مرورگری P2 اکنون وجود ندارد |
| P2-A04 | PASS (آفلاین) | ساعت fake و شمار اثر جانبی: `test_preflight_ready_is_read_only_and_repeatable`، `test_policy_refill_cooldown_and_circuit_with_fake_clock`، `test_circuit_opens_and_recovers_through_half_open`؛ گزارش و دروازه‌ها کامل |

## آزمون‌ها و دروازه‌ها

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_delivery_preflight.py …   # سنجم هدفمند
.\.venv\Scripts\python.exe -m pytest -o addopts='' -q                     # full Backend
.\.venv\Scripts\python.exe scripts/build_wheel_stdlib.py --force
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py
.\.venv\Scripts\python.exe scripts/check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py --check --check-links
git diff --check
```

- آزمون مستقل P2: `tests/test_delivery_preflight.py` = `10 passed` (8.01s) — ساعت fake: خالی/نیمه/refill، cooldown بلندتر از backoff محلی، باز بودن circuit، گذر به half_open و بازیابی؛ شمار اثر جانبی preflight صفر (orchestrator هرگز صدا زده نشد، ردیف limits تغییر نکرد، خواندن متوالی state را تغییر نداد)؛ A باعث توقف B نشد؛ رقابت preflight-ready و ارسال ردشده آزموده و توضیح‌پذیر؛ retry_after نامعتبر Provider مردود.
- full-stack (P2-A02): پنج ارسال واقعی HTTP با adapter ساختگی bucket را مصرف می‌کند، ششم `429 + Retry-After` قبل از آداپتور؛ بازپخش کلید موفق با سطل خالی 200 می‌گیرد (ثابتِ مصرف‌نکردن token در replay)؛ preflight همان wait را با منبع `local_policy` توضیح می‌دهد.
- رگرسیون گسترده: 109 آزمون (P1 + F-090/F-091 + M2M + service-auth + orchestration + بله) سبز.
- full Backend نهایی (درخت پایدار، 2026-09-29): `946 passed, 1 skipped, 1 warning` در 214.72s — شکست یگانه parity ویلِ پیش از rebuild بود؛ پس از بازسازی، `tests/test_g07_release_packaging.py` = `15 passed`. wheel `eitaa_bridge-0.7.0.dev31` با SHA-256=`23285b0cea4f613f1a0df93019c5fcd614d477e92ee6aa0a8f5151bf526002a0`.
- راستی‌آزمایی مجدد کامل (2026-09-29، پس از تکمیل سناریوی بلهٔ عامل دیگر و رفع ردیف تکراری دفتر وضعیت): full Backend `947 passed, 1 skipped` بدون هیچ شکست؛ rebuild ویل با همان SHA (deterministic) و parity 15/15؛ `npm run check` و `test:observability` و دروازه‌های اسناد سبز.
- UI: `npm run check` سبز؛ `test:observability` سبز؛ تغییر frontend در این فاز وجود ندارد (نمایش countdown به P7 واگذار شده).

## APIها و migrationهای تحویل‌شده

- `POST /api/v2/m2m/delivery/preflight` (M2M، scope `messages.send`) — هدف قرارداد 1.6.0 با source/test واقعی.
- `AccountExecutionPolicyService.read_only_snapshot` (فقط‌خواندنی، بدون INSERT/UPDATE).
- admission/ثبت نتیجه در `ProviderApplicationOrchestrator` برای تمام mutationها؛ composition root نمونهٔ یکسان policy را به هر دو مسیر می‌دهد.
- نگاشت خطا: `429 provider_operation_rate_limited` + `Retry-After` (سقف، گرد رو به بالا)، `503 provider_operation_circuit_open`.

## حد ضمانت و Live

هیچ عملیات Live، ورود، ارسال واقعی یا تغییر دادهٔ عملیاتی انجام نشد؛ همهٔ شواهد آفلاین با fixture ساختگی و DB موقت است. `ready` فقط یعنی «تلاش طبق سیاست معلوم مجاز است»؛ تضمین ظرفیت آینده یا موفقیت Provider نیست و هر دو در قرارداد صریح‌اند. مقادیر سیاست محلی (ظرفیت/refill) پیکربندی محصول‌اند و هرگز به‌عنوان محدودیت واقعی ایتا/بله نمایش داده نمی‌شوند؛ Suggested endpoint پس از تطبیق با الگوی جاری نهایی شد (`/api/v2/m2m/…` با scope `messages.send`). نمایش UI دلیل/countdown به کلاینت وب فاز P7 واگذار شد (همان مرز API-آفلاین/مرورگر بازِ BALE-B4).

## مرز انتشار

هیچ stage/commit/push انجام نشد — همان محدودیت فاز ۱ (درخت مشترک با تغییرات عمدی V-230).

## اقدام اول handoff و وضعیت پیش‌نیاز بعدی

اقدام اول ادامه‌دهنده: شروع P3 (`PHASE_03_CAPACITY_RESERVATIONS.md`) — رزرو اتمیک پایدار با انقضا/مصرف/لغو قابل حسابرسی، روی همین سیاست و بدون دورزدن حصارهای P1/P2. پیش‌نیازهای P2 برقرارند.

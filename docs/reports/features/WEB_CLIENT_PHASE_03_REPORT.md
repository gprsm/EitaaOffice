# P3 — گزارش فاز رزرو ظرفیت و پذیرش اتمیک

تاریخ: 2026-09-29
وضعیت: `OFFLINE_COMPLETE` — بدون هیچ مؤلفه یا عملیات Live
HEAD آغاز/پایان: `41dc87a2` روی `codex/bale-web-client-instructions` — بدون commit/push (درخت مشترک سه سناریو)

## شرح تحویل

- **رزرو durable و اتمیک**: جدول `service_delivery_reservations` (Coordinator schema v12، ارتقای آزموده‌شده 11→12 با حفظ داده) با state machine پایانی `reserved → consumed | cancelled | expired`، شناسهٔ تصادفی غیرقابل حدس، `operation_id` یکتا (UNIQUE) و `UNIQUE(service_credential_id, idempotency_fingerprint)`. هیچ await/شبکه/worker در تراکنش باز نیست؛ تصمیم ظرفیت + debit سطل + insert در یک تراکنش `BEGIN IMMEDIATE` است.
- **binding حساس با HMAC**: گیرنده فقط به‌صورت HMAC-SHA256 با کلید identity سرور روی (intent, service, شمارهٔ نرمال‌شده) ذخیره می‌شود (`bind_recipient`) — هش سادهٔ شماره قابل جستجوی معکوس است و هرگز استفاده نشد. شمارهٔ خام و OTP هرگز وارد جدول/لاگ/receipt نمی‌شوند. کلید: `hmac_hex` جدید روی هر دو `PhoneProtector` (DPAPI/FileKey) — مالک واحد کلید حفظ شد.
- **idempotency و conflict**: fingerprint انحصاری فقط از کلید idempotency ساخته می‌شود؛ تکرار همان کلید با همان payload همان رکورد را برمی‌گرداند (حتی اگر terminal باشد — بازپخش تصمیم، نه زنده‌سازی) و همان کلید با payload متفاوت `409 delivery_reservation_conflict` است.
- **consume اتمیک**: اتصال ارسال به slot با `operation_id` پایدار؛ consume تکراری همان operation همان رکورد را می‌دهد و debit دوباره نمی‌زند؛ operation متفاوت روی slot مصرف‌شده `already_consumed` است. هنگام consume، lifecycle حساب دوباره بررسی (`account_unavailable`) و revision پروفایل سنجیده می‌شود — تغییر revision با `sender_profile_revision_changed` رد و رزرو تازه لازم است؛ هیچ تعویض بی‌صدای حساب رخ نمی‌دهد.
- **expiry/cancel/restart/refund**: expiry تنبل و janitor هر دو به یک transition اتمیک متکی‌اند (`expire_due`)؛ refund فقط برای ارسالِ قطعاً شروع‌نشده، حداکثر تا ظرفیت، دقیقاً یک‌بار (`token_refunded`)؛ `mark_send_started` بعد از آن refund را ممنوع می‌کند (timeout ≠ refund). رکوردها بعد از restart — قبل و بعد از consume — باقی و قابل مصرف‌اند؛ ردیف‌ها هرگز حذف نمی‌شوند.
- **محدودیت سوءاستفاده**: حداکثر ۴ رزرو outstanding برای هر credential، حداکثر ۱۲ ایجاد در دقیقه، TTL بین ۳۰ تا ۶۰۰ ثانیه (پیش‌فرض ۱۲۰)؛ صف انتظار بیشتر از `expires_at` هرگز به شروع ارسال نمی‌رسد (consume بعد از انقضا رد می‌شود).
- **تعامل legacy مستند و آزموده**: debit رزرو روی همان سطل `messages.send_text` مشترک با preflight و admission ارسال است — مسیر legacy بدون رزرو نمی‌تواند slot رزروشده را تصاحب کند و با آزادشدن آن دوباره می‌گیرد.
- **مسیرهای API** (Bearer `eb_svc_`، scope `messages.send`): `POST /api/v2/m2m/delivery/reservations` (create)، `GET .../reservations/{id}` (status؛ مالک‌محور، id بیگانه = 404 بی‌جزئیات)، `POST .../reservations/{id}/cancel` (فقط مالک، idempotent). قرارداد نسخهٔ 1.7.0.

## وضعیت acceptance IDها

| ID | وضعیت | شاهد |
|---|---|---|
| P3-A01 | PASS (آفلاین) | `test_atomic_capacity_acceptance_across_two_connections` و `..._across_two_processes` (ظرفیت ۱: دقیقاً یک پذیرش و یک `capacity_unavailable` در دو connection و دو فرایند واقعی OS)، `test_consume_is_atomic...` |
| P3-A02 | PASS (آفلاین) | `test_expiry_refunds_once_and_never_revives`، `test_cancel_is_owner_scoped...`، `test_mark_send_started_forbids_refund`، `test_restart_preserves_records_before_and_after_consume` |
| P3-A03 | PASS (آفلاین) | قرارداد 1.7.0 بخش «Delivery reservations»؛ کدهای stale/expired/conflict با نگاشت HTTP دقیق |
| P3-A04 | PASS (آفلاین) | `test_legacy_send_cannot_take_the_reserved_slot`، `test_outstanding_and_rate_limits`، `test_idempotent_create_and_fingerprint_conflict`؛ گزارش/handoff/dروازه‌ها کامل |

## آزمون‌ها و دروازه‌ها

- آزمون مستقل P3: `tests/test_delivery_reservations.py` = `10 passed` در دو اجرای متوالی پایدار (~7s) — ساعت fake، دو connection، دو فرایند OS با sentinel barrier اتمیک، restart، crash پس از debit، شمارش صریح token/refund/operation و صفر worker واقعی.
- full Backend نهایی: `958 passed, 1 skipped, 1 warning` در 208.49s — صفر شکست. wheel `0.7.0.dev31` بازسازی: SHA-256=`cdc92ae7aeb3ff40222d11759a32b810141dbf35fc8c9b547542ee9679bbb62e` و parity 15/15؛ `npm run check` و `test:observability` سبز؛ generator/integrity/link-check/diff-check exit=0.
- دو تست migration که تنزل نسخه را شبیه‌سازی می‌کردند ابتدا با «table already exists» شکست خوردند (تنزل غیروفادار: جدول‌های v11/v12 باقی مانده بودند)؛ با حذف وفادارانهٔ جدول‌های نسخه‌های بعدی اصلاح و سبز شدند.
- **اصلاح لایهٔ مشترک (R1/R2/R4 از دستور بازبینی بله F-099)**: admission ردشده در send_text/_extension_mutation/upsert_contact اکنون مالکیت تلاش را با fence مالک تعیین تکلیف می‌کند (`release` جدید در receipts؛ درون حافظه pop می‌شود) — id پس از رد دوباره قابل استفاده است و claim uncertain برای عملیاتِ قطعاً شروع‌نشده باقی نمی‌ماند؛ contacts.upsert/import اکنون admission و ثبت نتیجه دارد (bypass اجرای واقعی بسته شد)؛ نگاشت canonical `provider_operation_rate_limited` → 429 + Retry-After در API محصول با تست HTTP واقعی. R3 (صفحه‌بندی مخاطبین بله) در دامنهٔ سناریوی بله است و توسط این فاز تغییر نکرد. تست‌های رگرسیون: `test_admission_denial_releases_claim_ownership` و `test_contact_import_enforces_local_capacity`.
- در طول توسعه، سه خطای پیاده‌سازی در خودِ store با همین آزمون‌ها RED→GREEN بسته شد: شمارش placeholder INSERT سطل، `lastrowid` روی کلید UUID (SELECT با uuid مستقیم جایگزین شد) و دامنهٔ fingerprint انحصاری کلید.

## حد ضمانت و Live

هیچ عملیات Live، ارسال واقعی یا تغییر دادهٔ عملیاتی انجام نشد؛ همهٔ شواهد آفلاین با fixture ساختگی و DB موقت است. رزرو فقط حسابداری پذیرش محلی را تثبیت می‌کند؛ سهمیهٔ پنهان Provider یا تحویل پیام را تضمین نمی‌کند و این مرز در قرارداد صریح است. تضمین اتمیک فقط برای دادهٔ durable واقعاً تراکنشی ادعا می‌شود و به agent.chat حافظه‌ای (F-090/F-091) تعمیم نمی‌یابد. retention محدود رکوردها (پاک‌سازی metadata بدون حذف دادهٔ عملیاتی) به فاز پایپ‌لاین واگذار شده و در قرارداد یادآوری شده است.

## مرز انتشار

هیچ stage/commit/push انجام نشد — درخت مشترک سه سناریو (V-230 + P1/P2 + B4 بله) و تصمیم انتشار با مالک است.

## اقدام اول handoff و وضعیت پیش‌نیاز بعدی

اقدام اول ادامه‌دهنده: شروع P4 (`PHASE_04_CONTACTS_OTP_DELIVERY.md`) — نقطهٔ اتصال: consume رزرو در مسیر prepare→send و status، با همین `operation_id` به‌عنوان کلید پایاپای عملیات؛ enforcement پیش از worker و عدم نشت OTP/شماره طبق قرارداد 1.7.0. پیش‌نیازهای P3 برقرارند.

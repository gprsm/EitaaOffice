# P1 — گزارش فاز پروفایل فرستنده و قرارداد پایه

تاریخ: 2026-09-28
وضعیت: `OFFLINE_COMPLETE` — بدون هیچ مؤلفه یا عملیات Live
HEAD آغاز: `41dc87a2` روی `codex/bale-web-client-instructions` (tracked diff عمدی شامل تغییرات بازبینی بلهٔ V-230 محفوظ ماند)
HEAD پایان: همان `41dc87a2` — هیچ commit/push انجام نشد (توضیح در «مرز انتشار»)

## شرح تحویل

پروفایل فرستندهٔ هدف‌دار برای هر سرویس، در محصول اصلی و در همان صفحهٔ حساب‌های سرویس، قابل استفاده شد:

- **ذخیرهٔ نسخه‌دار و اتمیک**: جدول `service_sender_profiles` (Coordinator schema v11، ارتقای 10→11 آزموده‌شده) با قید `UNIQUE(service_credential_id, intent)`، شناسهٔ UUID سمت سرور، `revision` افزایشی و write اتمیک زیر `BEGIN IMMEDIATE`. ویرایش هم‌زمان با `expected_revision` ناسازگار با `409 stale_revision` مردود می‌شود و هیچ‌گاه برندهٔ دیگر را بازنویسی نمی‌کند؛ به‌روزرسانی بدون revision با `sender_profile_revision_required` رد می‌شود.
- **هیچ پیش‌فرض پنهان**: هیچ حسابی به‌دلیل اولین‌بودن در فهرست یا آخرین ورود فرستنده نمی‌شود. درخواست بدون `sender_profile_id` و بدون `messenger_account_id` با `400 sender_not_configured` مردود است.
- **enforce سمت سرور** (نمایش UI به‌تنهایی هرگز کافی نیست): مسیر ارسال M2M (`m2m_api.handle_send_text`) فقط با `sender_profile_id`/`intent` یا مسیر قدیمی `messenger_account_id` کار می‌کند. پروفایل باید متعلق به همان credential و فعال باشد؛ حساب پین‌شده باید در `allowed_messenger_account_ids` و Provider آن در `allowed_providers` باشد و snapshot دسترس‌پذیری (حساب غایب/آرشیو/غیرفعال/قرنطینه یا حساب تلفنی غیرفعال) را بگذراند. حصارهای قدیمی credential بعد از resolve پروفایل هم دوباره اعمال می‌شوند — پروفایل حصار اضافه و باریک‌تر است، نه دورزدن.
- **ضد دورزدن**: با وجود پین فعال برای یک intent، درخواست قدیمی با `messenger_account_id` متفاوت با `409 sender_profile_mismatch` مردود می‌شود؛ خودِ حساب پین‌شده از مسیر قدیمی همچنان مجاز است (سازگاری).
- **lifecycle صادقانه**: حذف حساب با FK ممکن نیست؛ آرشیو/غیرفعال‌شدن، پروفایل را به `409 account_unavailable` (زمان ارسال) و `account_available: false` (فهرست admin) می‌رساند و هیچ‌گاه حساب دیگری را بی‌صدا جایگزین نمی‌کند. ابطال credential همهٔ پروفایل‌هایش را بی‌اثر می‌کند.
- **سیاست مهاجرت مستند**: دادهٔ قدیمی بدون پروفایل هیچ ردیف خودکاری نمی‌سازد، startup ارسالی ندارد و به `bridge.json` واقعی دست نمی‌زند؛ قرارداد صریح حساب قدیمی بدون تغییر کار می‌کند.
- **مسیرهای admin** (نشست AppUser + CSRF، فقط مدیر): `GET/PUT /api/v2/service-sender-profiles` و `DELETE /api/v2/service-sender-profiles/{id}` با اعتبارسنجی حصار در زمان نوشتن؛ رخدادهای `service_sender_profile_updated`/`service_sender_profile_removed` در Event Catalog ثبت و audit می‌شوند.
- **UI Provider-neutral** در `ServiceAccountSettingsPanel`: برای هر credential دو ردیف OTP/اطلاع‌رسانی با انتخاب حساب برچسب امن + شمارهٔ ماسک‌شده + وضعیت واقعی؛ تعارض نسخه با پیام فارسی و reload؛ حذف تنظیم دکمهٔ صریح دارد. کلاینت هرگز credential سرویس دریافت نمی‌کند.

## یادداشت همکاری

کار از کار نیمه‌تمام یک عامل دیگر ادامه یافت (schema v11 + `sender_profiles.py` + مسیرها + UI + آزمون). پیش از ادامه، فعال‌بودن هم‌زمان او با poll زمان فایل‌ها سنجیده شد و پس از قطع فعالیت، ممیزی کامل انجام و چهار نقص واقعی بسته شد: (۱) دو رخداد audit ثبت‌نشده در Event Catalog (تست نگهبان AST سبزنشده بود)، (۲) سه خطای TypeScript در پنل، (۳) drift ویل به‌علت ماژول جدید، (۴) بخش admin قرارداد — که عامل قبلی پیش از قطع کامل کرده بود و تأیید شد.

## وضعیت acceptance IDها

| ID | وضعیت | شاهد |
|---|---|---|
| P1-A01 | PASS (آفلاین) | انتخاب از UI + enforce سرور؛ `test_two_services_pin_save_reload_and_send_to_pinned_account`، `test_profile_pins_block_account_id_bypass`، `test_real_http_transport_enforces_sender_profile_contract` |
| P1-A02 | PASS (آفلاین) | حصار/revision/lifecycle؛ `test_rejected_requests_never_reach_the_send_path`، `test_revision_control_and_account_unavailable`، `test_sender_profile_store_unit_behavior` |
| P1-A03 | PASS (آفلاین) | سازگاری قرارداد قدیمی و سیاست نبود تنظیم؛ `test_legacy_data_without_profile_keeps_explicit_contract`؛ قرارداد نسخهٔ 1.5.0 بند 1a/1b |
| P1-A04 | PASS (آفلاین) | `tests/test_agent_gateway.py` در مجموعهٔ سنجم و full suite سبز؛ F-090/F-091 بدون تغییر رفتار |
| P1-A05 | PASS (آفلاین) | قرارداد 1.5.0، همین گزارش، handoff، دفتر وضعیت، Ledger (V-231)، دروازه‌های پایین |

## آزمون‌ها و دروازه‌ها

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sender_profiles.py … (سنجم اولیه)
.\.venv\Scripts\python.exe -m pytest -o addopts='' -q          # full Backend
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
npm.cmd --prefix ui run build
.\.venv\Scripts\python.exe scripts/build_wheel_stdlib.py --force
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py
.\.venv\Scripts\python.exe scripts/check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py --check --check-links
git diff --check
```

- سنجم اولیه (P1 + F-090/F-091 + M2M + service auth + schema + observability): `90 passed, 1 failed` — شکست یگانه، `test_literal_runtime_events_are_registered_in_catalog` با دو رخداد ثبت‌نشده؛ پس از ثبت در کاتالوگ همان مجموعهٔ هدفمند `13 passed` شد.
- آزمون P1 مستقل: `tests/test_sender_profiles.py` = `7 passed` (23.83s) — دو سرویس با حساب‌های مجزا، دو حساب ایتا + یک حساب بله، ردِ خارج از allowlist/سرویس دیگر/بی‌scope/Provider ناقض، صفر ارسال در همهٔ ردها، مسابقهٔ revision دو ویرایشگر با دو نشست واقعی admin، آرشیو حساب → `account_unavailable`، مسیر قدیمی بدون پروفایل، بایت‌یکسان‌ماندن `bridge.json`، انتقال واقعی HTTP روی loopback با اثبات نبود secret/شماره در پاسخ.
- full Backend نهایی پس از rebuild ویل: `933 passed, 1 skipped, 1 warning` در 439.05s، exit=0 (سطح شاهد اجرای نهایی 2026-09-28).
- UI: `check` پس از تعمیر سه خطای TypeScript سبز؛ `test:observability` سبز؛ `build` سبز (16.16s).
- wheel رسمی پس از افزودن ماژول محصول بازسازی شد: `eitaa_bridge-0.7.0.dev31-py3-none-any.whl`، SHA-256=`abcb0462f1228e37793dda492ef1b1f1dcbb9e8275f0c9f64daaf4eea0887a9e`؛ `tests/test_g07_release_packaging.py` = `15 passed`.
- اسناد: generator فایل map/symbol index را به‌روز کرد؛ integrity PASS؛ `--check` و `--check --check-links` exit=0؛ `git diff --check` exit=0.
- زمان شاهد: 2026-09-28، بین 19:30 تا پایان اجرای نهایی (زمان محلی).

## APIها و migrationهای تحویل‌شده

- Coordinator schema v11 (`service_sender_profiles`) با مسیر ارتقای 10→11 و حفظ داده؛ نسخه‌های هدفمند و آزمون 9→11 به‌روز شدند.
- `GET/PUT/DELETE /api/v2/service-sender-profiles` (admin) — هدف قرارداد بند 1b است و اکنون source/test واقعی دارد.
- گسترش `POST /api/v2/m2m/messages/send-text` با `sender_profile_id`/`intent`؛ قرارداد قدیمی `messenger_account_id` بدون تغییر.
- Event Catalog: دو رخداد جدید audit_required.
- UI: بخش «فرستنده‌های هدف سرویس» در `ServiceAccountSettingsPanel`.

## حد ضمانت و Live

هیچ عملیات Live، ورود، ارسال واقعی، تماس Provider/AI یا دست‌کاری دادهٔ عملیاتی/`bridge.json`/نشست در این فاز انجام نشد؛ همهٔ شواهد آفلاین با fixture ساختگی و حساب‌های آزمایشی روی DB موقت هستند. `account_available` فقط snapshot است و تضمین ظرفیت یا موفقیت Provider آینده نیست — این مرز در قرارداد ثبت شده است. فاز P1 مؤلفهٔ Live ندارد؛ ورودی مفقودی برای P2 (rate policy و preflight) لازم نیست.

## مرز انتشار

هیچ stage/commit/push انجام نشد: درخت کاری شامل تغییرات عمدی و آگاهانهٔ کامیت‌نشدهٔ بازبینی بلهٔ V-230 است که انتشار آن تا پذیرش مرورگر بسته است و چند فایل مشترک (قرارداد، دفترها) مخلوطِ دو سناریو هستند؛ تفکیک stage بدون خطر ورود محتوای V-230 ممکن نبود. تصمیم انتشار به مالک و هماهنگ‌کننده واگذار می‌شود.

## اقدام اول handoff و وضعیت پیش‌نیاز بعدی

اقدام اول برای ادامه‌دهنده: خواندن [handoff](../../handoffs/WEB_CLIENT_PHASE_01_HANDOFF.md) و سپس شروع P2 (`PHASE_02_LIMITS_PREFLIGHT.md`) — نقطهٔ اتصال پیشنهادی: اجرای سیاست نرخ واقعی در مسیر ارسال و preflight بدون اثر جانبی، با حفظ مرزهای همین فاز. پیش‌نیاز P1 برای P2 برقرار است.

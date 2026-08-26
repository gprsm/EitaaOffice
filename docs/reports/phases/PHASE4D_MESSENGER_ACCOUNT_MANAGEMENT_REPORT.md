# گزارش فاز ۴-D: مدیریت، انتخاب و اجرای ایزولهٔ MessengerAccount

- تاریخ: ۲۰۲۶-۰۸-۰۲
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- وضعیت: تکمیل‌شده
- Feature Flag نصب واقعی: خاموش و بدون تغییر
- ارتباط واقعی با ایتا یا بله: انجام نشد
- Commit/Push: انجام نشد

## نتیجه

فاز ۴-D تکمیل شد. API و رابط کاربری اکنون قرارداد حساب‌محور دارند؛ AppUser فقط حساب‌هایی را می‌بیند که از طریق PhoneAccount همان حساب به آن‌ها دسترسی دارد و انتخاب حساب در هر درخواست به Runtime مستقل همان `messenger_account_id` متصل می‌شود.

مسیر Legacy حفظ شده است. وقتی Feature خاموش باشد، نرم‌افزار همان فایل نشست، Cache، Upload و رفتار قبلی را استفاده می‌کند. نصب واقعی در پایان این فاز همچنان در همین حالت است.

## API مدیریت حساب

Endpointهای نسخهٔ ۲ اضافه شدند:

- `GET /api/v2/messenger-accounts`
- `GET /api/v2/messenger-accounts/{messenger_account_id}`
- `POST /api/v2/messenger-accounts/{messenger_account_id}/worker/start`
- `POST /api/v2/messenger-accounts/{messenger_account_id}/worker/stop`

انتخاب حساب برای درخواست‌های نسخهٔ ۱ از Header زیر انجام می‌شود:

```text
X-Eitaa-Messenger-Account: <canonical UUID v4>
```

شناسهٔ دریافتی به‌تنهایی معتبر نیست. سمت سرور ابتدا AppSession را اعتبارسنجی و سپس Membership همان PhoneAccount را بررسی می‌کند.

قواعد دسترسی:

- `admin`: مشاهده و عملیات روی همهٔ حساب‌های ثبت‌شده
- `owner`: مشاهده، استفاده و مدیریت Worker حساب‌های همان PhoneAccount
- `operator`: مشاهده، استفاده و مدیریت Worker حساب‌های همان PhoneAccount
- `viewer`: فقط مشاهدهٔ وضعیت؛ انتخاب Workspace و مدیریت Worker مجاز نیست

داشتن Membership روی یک PhoneAccount دیگر، مجوز استفاده از حساب انتخاب‌شده محسوب نمی‌شود.

## انتخاب هم‌زمان و ایزولهٔ Runtime

اتصال ثابت قبلی API به یک Runtime با Context مستقل هر درخواست جایگزین شد. این Context در موارد زیر نیز منتقل می‌شود:

- Scheduler callback
- Background Thread
- Dialog sync
- Read receipt worker
- Content index worker
- Contact import worker
- سایر Background taskها

بنابراین اجرای هم‌زمان دو درخواست نمی‌تواند Aliasهای API را به Runtime حساب دیگر متصل کند.

موارد حساب‌محور باقی‌مانده یا تکمیل‌شده:

- Scheduler و Lockها
- Auth runtime و Challenge
- Dialog catalog و Sender directory
- Content index، Jobها و Cancellationها
- Contact import و Eitaa contact cache
- Pending read receipts
- Background task state
- Media token registry
- Upload staging path
- Worker diagnostics و Worker log

## Media و Upload

Media token فقط در Registry حساب سازنده قابل حل است. Media URL حسابی دارای `messenger_account_id` است و HTTP adapter همان حساب را دوباره مجازسنجی می‌کند.

Upload مرورگر و Electron نیز به مسیر زیر محدود شد:

```text
runtime/accounts/{messenger_account_id}/cache/uploads
```

ارسال Token یا Upload حساب A با انتخاب حساب B در آزمون End-to-End رد شد.

## Worker lifecycle و Supervisor

شروع Worker اکنون به‌صورت تراکنشی این کارها را انجام می‌دهد:

1. کنترل Provider و lifecycle
2. ثبت `desired_worker_state=running`
3. انتقال حساب به `active`
4. ساخت `worker_instances` با generation جدید
5. ثبت Audit درخواست شروع
6. گرفتن Lock اختصاصی حساب
7. ساخت Runtime حساب
8. انتقال Worker از `starting` به `ready`
9. شروع heartbeat دوره‌ای Coordinator

توقف Worker:

1. ثبت درخواست توقف و `desired_worker_state=stopped`
2. انتقال Worker به `stopping`
3. توقف Challenge، Scheduler و Core همان حساب
4. آزادسازی Lock همان حساب
5. انتقال Worker به `stopped`
6. انتقال حساب به `paused/stopped`

بسته‌شدن کل برنامه Worker row را متوقف می‌کند، ولی به‌صورت خودکار خواست کاربر برای اجرای آینده را به Pause تبدیل نمی‌کند.

## بازیابی امن Lock پس از Crash

Lock موجود فقط در صورتی بازیابی می‌شود که همهٔ شرایط زیر برقرار باشند:

- JSON و Schema آن معتبر باشد.
- `messenger_account_id` و Provider دقیقاً منطبق باشند.
- Lease ID، PID، generation و storage revision معتبر باشند.
- سیستم‌عامل به‌طور قطعی تأیید کند PID دیگر زنده نیست.
- Lock هنگام بازیابی تغییر نکرده باشد.

Lock قبلی حذف نمی‌شود و با نام دارای Timestamp و Lease ID به‌صورت `.stale...json` بایگانی می‌شود.

در این حالت‌ها بازیابی Fail-closed است:

- PID زنده
- وضعیت PID نامشخص
- JSON ناقص یا خراب
- Identity ناسازگار
- تغییر Lock هنگام بازیابی
- Recovery lock هم‌زمان

Worker row باقی‌مانده از Process مرده نیز پیش از نسل جدید Fence و Audit می‌شود.

## رابط کاربری

فایل جدید `ui/src/MessengerAccountGate.tsx` این امکانات را اضافه می‌کند:

- دریافت فهرست حساب‌های مجاز
- نمایش Provider، شمارهٔ Masked، نقش، Auth state و Worker state
- انتخاب حساب فعال
- شروع/توقف Worker در صورت داشتن مجوز
- Remount کامل Workspace هنگام تغییر حساب برای پاک‌شدن state رابط حساب قبلی
- نمایش حالت فقط‌خواندنی برای `viewer`
- نمایش آماده‌نبودن Adapter بله بدون ادعای قابلیت یا API
- بخش مدیریت حساب‌ها در پنجرهٔ تنظیمات
- انتخاب‌گر حساب در منوی اصلی

Electron، Browser shim و انتخاب فایل نیز شناسهٔ حساب انتخاب‌شده را منتقل می‌کنند.

هنگام خاموش‌بودن Feature، Gate هیچ انتخاب حسابی را تحمیل نمی‌کند و Workspace قبلی را بدون تغییر نمایش می‌دهد.

## قرارداد Provider و بله

فایل جدید زیر مرز عمومی Adapter را تعریف می‌کند:

`src/eitaa_bridge/application/provider_adapter.py`

قرارداد فقط Context حساب و عملیات عمومی `start/heartbeat/stop` را تعریف می‌کند. برای بله هیچ Endpoint، روش ورود، Capability یا رفتار API حدس زده نشده است.

Catalog فعلی:

- `eitaa`: Adapter موجود و پیکربندی‌شده
- `bale`: ثبت‌شده ولی `provider_adapter_not_configured`

بررسی و پیاده‌سازی API بله باید در گفت‌وگوی مستقل و بر اساس مستندات یا API واقعی انجام شود.

## Correlation، Rotation و Redaction

`request_id` اکنون در Context عملیات قرار می‌گیرد و به Eventهای داخلی همان درخواست، Scheduler و Threadهای مشتق منتقل می‌شود.

برای عملیات Worker start آزمون ثابت می‌کند یک Request ID در هر سه منبع قابل تطبیق است:

- Application log
- Worker log همان حساب
- Audit پایدار Coordinator

Context ثابت Worker log بعد از فیلدهای Caller اعمال می‌شود؛ بنابراین Event نمی‌تواند خود را به حساب دیگری منتسب کند.

سیاست Rotation موجود حفظ و آزمون شد:

- سقف پیش‌فرض هر فایل: ۵ MiB
- تعداد Backup: پنج فایل
- UTF-8 JSON Lines

آزمون Rotation با سقف کوچک‌تر نشان داد شمارهٔ کامل، Token و `messenger_account_id` جعلی Caller در فایل اصلی یا Backupها باقی نمی‌مانند.

## Support Bundle حساب‌محور

اسکریپت زیر اکنون حساب اختیاری می‌پذیرد:

```powershell
.\.venv\Scripts\python.exe .\scripts\create_diagnostics_bundle.py --messenger-account-id <UUID>
```

Bundle شامل این موارد امن است:

- System inventory بدون محتوای Secret
- تنظیمات Redacted
- Doctor output Redacted
- Application/API/Desktop logهای چرخیده و Redacted
- Worker log و Diagnostics همان حساب
- خلاصهٔ امن Coordinator، Worker و Audit همان حساب
- Manifest دارای SHA-256 هر Entry

Bundle عمداً این موارد را وارد نمی‌کند:

- `.env`
- محتوای Session
- SQLite database content
- Media و Cache
- رمز WordPress
- Token، Cookie، IMEI، کد ورود، رمز دوم یا شمارهٔ کامل

## آزمون‌های فاز ۴-D

فایل جدید:

`tests/test_phase4d_account_management.py`

پنج سناریوی اصلی آن موفق شدند:

1. کنترل دقیق Membership و رد حساب PhoneAccount دیگر
2. فهرست، شروع، انتخاب، اجرای هم‌زمان و توقف دو حساب
3. جداسازی Job، Media، Upload، Challenge و Log میان دو حساب
4. بازیابی Lock فقط برای PID قطعی مرده و رد Lock خراب
5. Rotation/Redaction و Support Bundle بدون نشت دادهٔ خصوصی

مجموعهٔ متمرکز HTTP، AppUser، Account runtime، Auth lifecycle و ۴-D نیز کامل موفق شد.

Build رابط:

- TypeScript: موفق
- Vite production build: موفق
- هشدار غیرمسدودکننده: Bundle اصلی UI بزرگ‌تر از ۵۰۰ KiB است؛ این هشدار از نظر عملکردی شکست محسوب نمی‌شود.

کنترل‌های کیفیت:

- `compileall`: موفق
- `git diff --check`: موفق
- آزمون کامل: ۳۵۷ آزمون جمع‌آوری شد؛ ۳۵۶ موفق و یک شکست تاریخی نامرتبط باقی ماند.

شکست تاریخی:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

Fixture مسیر لاتین `Documents\Eitaa\...` می‌سازد، اما Assertion انتظار `Documents\ایتا\...` دارد. کد فاز ۴-D آن بخش را تغییر نداده است.

## فایل‌های اصلی این فاز

- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/application/account_runtime.py`
- `src/eitaa_bridge/application/provider_adapter.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `src/eitaa_bridge/infrastructure/diagnostics/runtime_logger.py`
- `src/eitaa_bridge/interfaces/http_api.py`
- `scripts/create_diagnostics_bundle.py`
- `ui/src/MessengerAccountGate.tsx`
- `ui/src/App.tsx`
- `ui/src/QuickSendBar.tsx`
- `ui/src/lib/api.ts`
- `ui/src/main.tsx`
- `ui/electron/main.cjs`
- `ui/electron/preload.cjs`
- `tests/test_phase4d_account_management.py`

## وضعیت نصب واقعی پس از فاز

بررسی نهایی فقط‌خواندنی بود:

- `bridge.json` واقعی بخش `features` ندارد.
- `multi_session.enabled = false`
- `app_user_auth.enabled = false`
- حساب مهاجرت‌یافته همچنان:
  - `provider = eitaa`
  - `lifecycle_state = created`
  - `desired_worker_state = stopped`
  - `auth_state = absent`
  - `session_generation = 1`
  - `storage_revision = 1`
- تعداد `worker_instances` واقعی: صفر
- هیچ Python، Electron یا Node مربوط به Bridge فعال نیست.
- برنامهٔ مستقل Eitaa Desktop باز است و دست‌کاری نشد.
- هیچ Login، Logout، Session rewrite یا اتصال واقعی Provider انجام نشد.

## دروازهٔ ادامه

فاز ۴-D در این نقطه پایان یافته است. فعال‌کردن عمومی Feature بخشی از این فاز نبود و نباید بدون پذیرش مستقل انجام شود.

گام بعدی پیشنهادی مطابق برنامهٔ اصلی، فاز ۵ است: دفترچهٔ مخاطبان محلی مشترک را با `created_by`، `updated_by`، تاریخچهٔ ممیزی، ادغام شمارهٔ تکراری و اتصال حساب‌محور «افزودن به پیام‌رسان» تکمیل و آزمایش کن؛ Feature چندحسابی را همچنان بدون پذیرش مستقل فعال نکن.

دستور مناسب برای نوبت بعد:

```text
فاز ۵ را شروع کن. ابتدا گزارش PHASE4D_MESSENGER_ACCOUNT_MANAGEMENT_REPORT.md را بخوان و سپس دفترچهٔ مخاطبان محلی مشترک و ممیزی‌شده را طبق دروازهٔ ادامه پیاده‌سازی کن؛ Feature Flag را فعال نکن.
```

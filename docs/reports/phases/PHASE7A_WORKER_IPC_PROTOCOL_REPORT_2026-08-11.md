# گزارش فاز ۷-A: پروتکل IPC و Worker entrypoint مستقل

تاریخ: ۲۰۲۶-۰۸-۱۱

وضعیت: تکمیل‌شده و آزموده‌شده

مرز گزارش: پایان Phase 7-A؛ Phase 7-B آغاز نشده است

## نتیجهٔ اجرایی

قرارداد IPC محلی، نسخه‌دار و احرازشده برای Processهای Provider worker ساخته شد. Envelope نسخهٔ ۱ دارای Scope دقیق `MessengerAccount + Provider`، شناسهٔ هم‌بستگی، deadline، nonce و امضای HMAC-SHA256 است. فایل Bootstrap کلید فقط برای کاربر جاری قابل دسترسی است، عمر محدود دارد و هنگام آغاز Worker به‌صورت یک‌بارمصرف جابه‌جا، خوانده و حذف می‌شود.

یک Worker entrypoint مستقل و Fake Provider بدون Session، شبکه یا دادهٔ واقعی ساخته شد. آزمون واقعی Subprocess نشان داد Worker در PID جدا اجرا می‌شود، correlation را حفظ می‌کند، Replay را رد می‌کند و با `worker.stop` تمیز خارج می‌شود.

Runtime واقعی ایتا به Process جدید منتقل نشد. این انتقال فقط در Phase 7-B و پشت Feature Flag سازگار با Legacy مجاز است. Supervisor، Crash recovery، Fencing و Backoff نیز برای Phase 7-C باقی ماندند.

## ممیزی آغاز نوبت و انتقال مسیر

- مسیر جاری پروژه با آزمون ساخت/خواندن/حذف فایل موقت، قابل نوشتن بود.
- Git ابتدا به‌علت تفاوت مالک پوشه با حساب Sandbox خطای `dubious ownership` داد؛ ممیزی با `git -c safe.directory=<current-project>` و بدون تغییر Global Git config ادامه یافت.
- Branch برابر `main` و upstream برابر `origin/main` بود.
- Worktree عمداً dirty و شامل تغییرات commit‌نشدهٔ فازهای ۱ تا ۶ بود؛ هیچ reset، checkout، stage، commit یا push انجام نشد.
- گزارش‌های Phase 6-A تا 6-D بررسی شدند. گزارش 6-D کل Phase 6 را بسته و Process isolation را به Phase 7 منتقل کرده بود.
- دو ارجاع مطلق واقعی از مسیر قدیمی `Documents\ایتا\...` در اسناد انتقال به مسیر فعلی `Documents\eitaa\...` اصلاح شدند.
- ارجاع‌های دیگری که عبارت مسیر فارسی را دارند، شرح تاریخی Failure قدیمی‌اند و برای تغییرندادن واقعیت گزارش گذشته حفظ شدند.
- تست تاریخی `test_windows_process_query_uses_explicit_utf8` به‌جای مقایسهٔ Fixture لاتین با suffix فارسی، اکنون round-trip واقعی UTF-8 را با یک بخش Unicode و نام پوشهٔ مستقل از محل نصب بررسی می‌کند.

## قرارداد Bootstrap و Secret

- Secret تصادفی ۳۲ بایتی و `key_id` از نوع UUIDv4 است.
- TTL فقط در بازهٔ ۵ تا ۳۰۰ ثانیه پذیرفته می‌شود و پیش‌فرض ۶۰ ثانیه است.
- Secret به یک `messenger_account_id` و `provider` دقیق Bind می‌شود.
- فایل با ایجاد انحصاری ساخته می‌شود؛ در POSIX مجوز `0600` و در Windows یک DACL محافظت‌شده با Full Control فقط برای SID کاربر جاری اعمال می‌شود.
- Secret از Command line، Environment، stdout/stderr، Envelope و Safe summary عبور نمی‌کند؛ فقط مسیر فایل به Child داده می‌شود.
- Worker فایل را به نام مصرفی یکتا منتقل می‌کند و در مسیر موفق یا ناموفق حذف می‌کند. مصرف دوباره Fail-closed رد می‌شود.
- Scope mismatch، انقضا، ACL نامعتبر، فایل بیش‌ازحد بزرگ، Schema یا Identity نامعتبر با Error code امن رد می‌شوند.

## Envelope نسخهٔ ۱

فیلدهای دقیق:

```text
protocol
version
kind
correlation_id
messenger_account_id
provider
method
deadline_unix_ms
nonce
payload
auth.algorithm
auth.key_id
auth.signature
```

- Transport فاز ۷-A، JSON Lines روی Pipeهای `stdin/stdout` همان Parent/Child است و هیچ Socket شبکه‌ای باز نمی‌کند.
- اندازهٔ هر پیام حداکثر ۱ MiB است.
- JSON canonical با ترتیب کلید ثابت و بدون `signature` امضا می‌شود.
- امضا با `hmac.compare_digest` بررسی می‌شود.
- deadline گذشته یا بیش از پنج دقیقه در آینده رد می‌شود.
- UUIDها، Provider، Method و Nonce قرارداد محدود و Fail-closed دارند.
- Response همان correlation، method و deadline درخواست را حفظ می‌کند و nonce مستقل می‌گیرد.
- replay nonce در Worker رد می‌شود و حافظهٔ nonce کران‌دار است.

## ممنوعیت عبور Provider state

Validator بازگشتی Payload این کلیدها/مفاهیم را رد می‌کند:

- Session object و Raw session
- Access Hash
- Raw Peer، Peer object و Raw message
- Authorization، Cookie، Token و Secret
- Password و OTP

Fake worker فقط یک `opaque_reference` محدود را echo می‌کند. هیچ شناسهٔ حساس گیرنده، Session object، Provider database، Access Hash یا Raw Peer به Coordinator داده نمی‌شود.

## Error taxonomy

Taxonomy عمومی و امن در چهار گروه ثبت شد:

- `bootstrap`
- `authentication`
- `contract`
- `worker`

پاسخ خطا فقط `error.code` دارد. Traceback، Path، Secret، Phone، Token، Cookie، Session یا Payload خصوصی به مرز پروتکل نشت نمی‌کند. پس از هشت Failure احراز متوالی، Worker Fail-closed خارج می‌شود.

## Fake Provider worker

Methodهای مجاز:

```text
worker.hello
worker.health
fake.echo_opaque
worker.stop
```

Entrypoint در این فاز فقط `--provider fake` را قبول می‌کند. `eitaa` و سایر Providerها با `provider_worker_not_configured` رد می‌شوند؛ هیچ API یا Login flow برای Bale، Rubika یا SoroushPlus حدس زده نشده است.

## فایل‌های Phase 7-A

فایل‌های جدید:

- `src/eitaa_bridge/infrastructure/worker_ipc/__init__.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/protocol.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/secret_file.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/error_taxonomy.py`
- `src/eitaa_bridge/application/fake_provider_worker.py`
- `src/eitaa_bridge/interfaces/provider_worker.py`
- `docs/WORKER_IPC_PROTOCOL.md`
- `tests/test_phase7a_worker_ipc_protocol.py`
- `PHASE7A_WORKER_IPC_PROTOCOL_REPORT_2026-08-11.md`

فایل‌های موجود که در این نوبت تغییر کردند:

- `src/eitaa_bridge/errors.py`
- `pyproject.toml`
- `ARCHITECTURE_DECISIONS.md`
- `../architecture/HTTP_LAN_MULTIUSER_CONTINUATION_REPORT_2026-08-02.md`
- `../../handoffs/NEXT_CHAT_PROMPT_HTTP_LAN_PHASE6A_2026-08-02.md`
- `tests/test_runtime_ownership.py`

## نتیجهٔ آزمون و کنترل کیفیت

Dedicated Phase 7-A:

```text
9 passed
```

Focused شامل Phase 7-A، Account runtime، Phase 4-D، Session ownership و Windows runtime ownership:

```text
51 passed
```

Full repository بدون حذف هیچ Test:

```text
421 collected
421 passed
```

Failure تاریخی مسیر که تا Phase 6 به‌صورت baseline ثبت می‌شد، اکنون با قرارداد درست و مستقل از نام پوشه رفع شده و هیچ deselect یا xfail لازم نیست.

کنترل‌های دیگر:

```text
compileall src + tests: passed
git diff --check: passed
old absolute project path scan: clean
real subprocess fake-worker round trip: passed
Windows current-user DACL creation/consume: passed
```

## وضعیت واقعی نصب و Side effectها

- `bridge.json` واقعی تغییر نکرد.
- Feature Flag واقعی روشن نشد.
- Registry فعلی هنوز Runtime واقعی ایتا را طبق مسیر Legacy/Phase 4 اجرا می‌کند.
- هیچ Process واقعی ایتا، Login، Logout، OTP، Status، Sync یا Send اجرا نشد.
- هیچ LAN port، Firewall rule، Windows Service یا Router setting ایجاد یا تغییر نکرد.
- هیچ دادهٔ Coordinator، Session، Contact، Cache، Media یا Log واقعی مهاجرت یا بازنویسی نشد.
- هیچ Dependency نصب نشد.
- هیچ Commit، Push یا Stage انجام نشد.

## موارد انتقالی به Phase 7-B

- افزودن Feature Flag نسخه‌دار و پیش‌فرض خاموش برای Process runtime
- Spawn دقیق یک Child برای هر MessengerAccount ایتا
- انتقال مالکیت Core، Scheduler، Session، DB، Cache، Media و Log به Child
- جایگزینی فراخوانی‌های درون‌Process با DTO و opaque reference روی IPC نسخهٔ ۱
- حفظ مسیر Legacy و امکان Rollback با Feature Flag خاموش
- آزمون تطابق رفتار بدون Login/OTP/Send واقعی

Crash recovery، heartbeat/fencing کامل، duplicate-worker rejection چندProcess و backoff مربوط به Phase 7-C هستند و نباید داخل 7-B گسترش یابند.

## دستور دقیق آغاز Phase 7-B

```text
فقط Phase 7-B پروژه Eitaa Bridge را اجرا کن. ابتدا ARCHITECTURE_DECISIONS.md، docs/WORKER_IPC_PROTOCOL.md و PHASE7A_WORKER_IPC_PROTOCOL_REPORT_2026-08-11.md را کامل بخوان و Worktree dirty و bridge.json واقعی را حفظ کن. Runtime ایتا را پشت یک Feature Flag نسخه‌دار و پیش‌فرض خاموش به یک Child process دقیق برای هر MessengerAccount منتقل کن؛ Core، Scheduler، Session، DB، Cache، Media و Log باید فقط در Child مالکیت شوند و Coordinator فقط DTO امن و opaque reference را از IPC نسخهٔ ۱ ببیند. مسیر Legacy و Rollback را حفظ و تست کن. Supervisor کامل، Crash recovery، quarantine/backoff و آزمون Kill/Tampering فازهای 7-C/7-D را آغاز نکن. هیچ Provider جدید یا API/Login flow فرضی نساز، هیچ Login/Logout/OTP/Sync/Send واقعی اجرا نکن، دادهٔ واقعی را مهاجرت نده، Port/Firewall/Service واقعی را تغییر نده و commit/push نکن. در پایان گزارش مستقل Phase 7-B بساز و متوقف شو.
```

Phase 7-A completed.

Phase 7-B NOT started.

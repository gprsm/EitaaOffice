# قرارداد IPC فرایند Worker

وضعیت: نسخهٔ ۱، تکمیل Phase 7
دامنه: ارتباط محلی Parent/Child برای یک MessengerAccount

## مرز و هدف

این قرارداد مرز انتقال Runtime هر حساب به Process مستقل است. Phase 7-A پروتکل، Bootstrap امن و Fake worker را تثبیت کرد و Phase 7-B مالکیت Runtime حساب ایتا را پشت Feature Flag نسخه‌دار به Child منتقل کرد. هیچ Provider جدیدی فعال نشده است.

Transport فعلی JSON Lines روی `stdin/stdout` همان Child process است. این کانال عمومی، HTTP، TCP یا Socket شبکه نیست. `stderr` فقط Error code امن و بدون Secret می‌دهد.

## Bootstrap کلید

Parent برای هر Spawn یک کلید ۳۲ بایتی و `key_id` تصادفی می‌سازد. فایل Bootstrap:

- فقط ۵ تا ۳۰۰ ثانیه اعتبار دارد؛ پیش‌فرض ۶۰ ثانیه است.
- به یک `messenger_account_id` و یک `provider` دقیق Bind است.
- در POSIX با مجوز `0600` و در Windows با DACL محافظت‌شدهٔ Full Control فقط برای کاربر جاری ساخته می‌شود.
- Secret را در Argument، Environment، Log یا Envelope قرار نمی‌دهد؛ فقط مسیر فایل به Child داده می‌شود.
- در Worker ابتدا اتمیک به نام مصرفی منتقل، خوانده و در همهٔ حالت‌های موفق یا ناموفق حذف می‌شود؛ استفادهٔ دوباره ممکن نیست.

انقضا فقط برای Bootstrap است. پس از Handshake، Parent و Child کلید را در حافظه نگه می‌دارند تا Supervisor در Phase 7-C کانال را ببندد یا Worker را Fence کند.

## Envelope نسخهٔ ۱

هر خط حداکثر ۱ MiB و دقیقاً شامل این فیلدهاست:

```json
{
  "protocol": "eitaa-bridge-worker-ipc",
  "version": 1,
  "kind": "request",
  "correlation_id": "uuid-v4",
  "messenger_account_id": "uuid-v4",
  "provider": "fake",
  "method": "worker.hello",
  "deadline_unix_ms": 0,
  "nonce": "random-url-safe-value",
  "payload": {},
  "auth": {
    "algorithm": "hmac-sha256",
    "key_id": "uuid-v4",
    "signature": "64-lowercase-hex"
  }
}
```

امضا روی JSON canonical تمام Envelope با `sort_keys=true` و بدون فیلد `signature` محاسبه می‌شود. Response همان `correlation_id`، method و deadline درخواست را نگه می‌دارد و nonce مستقل دارد. deadline گذشته یا بیش از پنج دقیقه در آینده پذیرفته نمی‌شود.

## Payload مجاز و ممنوع

Payload فقط JSON محدود، با عمق حداکثر ۱۶ و تعداد عناصر محدود است. کلیدهای حساس به‌صورت بازگشتی رد می‌شوند، از جمله:

- Session object یا Raw session
- `access_hash`
- Raw peer، Peer object یا Raw message
- Authorization، Cookie، Token یا Secret
- Password و OTP

مرز معتبر برای ارجاع به دادهٔ Provider یک opaque reference محدود است؛ Coordinator نباید محتوای داخلی آن را تفسیر کند.

## Error taxonomy امن

- `bootstrap`: ساخت/ACL/انقضا/Scope فایل کلید یا Provider پیکربندی‌نشده
- `authentication`: امضای نامعتبر، Replay یا عبور از سقف خطای احراز
- `contract`: نسخه، Envelope، Kind، Deadline، اندازه و Payload نامعتبر
- `worker`: Method یا Scope نامعتبر و Failure داخلی Sanitized

Response خطا فقط `error.code` را برمی‌گرداند. Secret، Payload خصوصی، Path، Phone، Session یا Traceback وارد پاسخ پروتکل نمی‌شوند.

## Workerهای مجاز

Fake worker آزمون قرارداد این Methodها را دارد:

- `worker.hello`
- `worker.health`
- `worker.heartbeat`
- `fake.echo_opaque`
- `worker.stop`

Eitaa worker فقط با `--provider eitaa --config <path>` و فقط وقتی Feature Flag معتبر و فعال باشد اجرا می‌شود. Methodهای Phase 7-B:

- `worker.hello`
- `worker.health`
- `eitaa.runtime.start`
- `eitaa.runtime.describe`
- `eitaa.runtime.core_probe`
- `eitaa.runtime.refresh_generation`
- `eitaa.runtime.close_core`
- `worker.stop`

Payload آغاز Runtime فقط DTO امن `MessengerAccountRuntimeRecord` و `worker_instance_id` را می‌برد. Parent هیچ Session، Core، Scheduler callback، Provider DB handle، Cache، Media handle یا Log حساب را دریافت نمی‌کند. `core_probe` نیز فقط وضعیت مالکیت و نام فایل/پوشه را برمی‌گرداند، نه مسیر مطلق یا دادهٔ Provider.

## Feature Flag و مرز Phase 7-B

قابلیت `features.worker_process` دارای `schema_version: 1` و پیش‌فرض خاموش است. فعال‌سازی آن به `multi_session` فعال نیاز دارد؛ Schema یا Timeout نامعتبر، وابستگی غیرفعال و Kill switch محیطی `BRIDGE_FORCE_DISABLE_WORKER_PROCESS` همگی قابلیت را Fail-closed خاموش می‌کنند. خاموش‌بودن Flag مسیر درون‌فرایندی قبلی را بدون تغییر نگه می‌دارد.

با Flag روشن، Parent برای هر MessengerAccount دقیقاً یک Child می‌سازد و Coordinator را با PID واقعی همان Child ثبت می‌کند. Runtime قدیمی در Parent حتی ساخته نمی‌شود. Scheduler، Lease، مسیرهای Session/DB/Cache/Media و Log حساب در Child ساخته می‌شوند. ساخت Core تا نخستین عملیات Provider به تعویق می‌افتد تا Startup هیچ Login یا اتصال واقعی اجرا نکند؛ محل ساخت و تمام مالکیت آن فقط Child است.

در Phase 7-B فقط RPCهای کنترلی و DTO وضعیت Scheduler به API متصل شدند. مسیرهای Provider که هنوز DTO/opaque-reference اختصاصی ندارند با `eitaa_process_operation_ipc_required` Fail-closed رد می‌شوند؛ Python callback و دسترسی مستقیم به mutable provider state اجازهٔ عبور از مرز را ندارند.

## Supervisor و Fencing در Phase 7-C

پس از `eitaa.runtime.start`، Parent کانال را به `worker_instance_id + worker_generation` ثبت‌شده در Coordinator Bind می‌کند. تمام درخواست‌های Runtime، Health، Heartbeat و Stop بعدی این Fence را حمل می‌کنند و Child هر mismatch را با `eitaa_process_fence_mismatch` رد می‌کند. Coordinator نیز Heartbeat و Crash را فقط برای همان Worker ID، Generation و PID اتمیک می‌پذیرد.

Supervisor اختصاصی هر حساب با interval و deadline محدود `worker.heartbeat` می‌فرستد. خروج Process یا عبور از سقف خطای Heartbeat باعث Fencing کانال و Process، ثبت `exit_code` و Reason امن، Backoff نمایی کران‌دار و در صورت باقی‌بودن بودجه، Spawn یک Generation جدید می‌شود. Crashهای بیش‌ازبودجه در پنجرهٔ زمانی حساب را `quarantined/stopped` می‌کنند و Restart خودکار متوقف می‌شود.

Backoff در خود Coordinator و پیش از ساخت Worker جدید دوباره کنترل می‌شود. Duplicate worker در حالت‌های starting/ready/busy/rate_limited/stopping رد می‌شود. Shutdown کنترل‌شده Supervisor را پیش از `worker.stop` متوقف می‌کند و Recovery اجرا نمی‌شود؛ Startup بعدی Generation جدید و تمیز می‌سازد. Crash یا Quarantine یک حساب Auth/Session generation یا Worker حساب دیگر را تغییر نمی‌دهد.

## پذیرش خصمانهٔ Phase 7-D

مرز Process با اجرای واقعی این سناریوها تثبیت شد:

- Kill واقعی Fake worker و Eitaa Child آزمایشی
- امضای دست‌کاری‌شده، Scope متفاوت، Replay و سقف خطای احراز
- پاسخ امضاشده اما unsolicited/correlation-mismatched
- Fence نسل قدیمی و Lock contention واقعی دو Child برای یک حساب
- Race هم‌زمان دو Registry برای Spawn یک حساب
- جدایی Session/Scheduler/DB/Cache/Log دو حساب
- اسکن بایت‌به‌بایت خروجی‌ها برای Secretهای تولیدشدهٔ آزمون

Reader پاسخ Parent اکنون اندازهٔ هر خط و عمق صف را محدود می‌کند. Response با امضا، اندازه یا correlation نامعتبر کانال را Fail-closed می‌بندد و Child را Terminate می‌کند تا پاسخ باقی‌مانده باعث desynchronization نشود. Worker نیز پس از هشت Failure احراز متوالی با Error code امن خارج می‌شود.

Phase 7 قرارداد Process isolation را تکمیل می‌کند، اما Feature Flag نصب واقعی همچنان پیش‌فرض خاموش است. مسیرهای Provider که RPC اختصاصی DTO/opaque-reference ندارند همچنان Fail-closed هستند و Rollout واقعی بخشی از این فاز نیست.

درخواست `bale`، `rubika` یا `soroushplus` همچنان با `provider_worker_not_configured` رد می‌شود و هیچ API یا Login flow فرضی برای آن‌ها وجود ندارد.

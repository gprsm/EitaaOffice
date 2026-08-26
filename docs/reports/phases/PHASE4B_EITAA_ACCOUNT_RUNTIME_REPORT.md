# گزارش فاز ۴-B: Runtime و Storage حساب‌محور ایتا

- تاریخ: ۲۰۲۶-۰۸-۰۲
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- خط مبنا: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- وضعیت: تکمیل‌شده
- Feature Flag: خاموش و بدون تغییر در نصب واقعی

## نتیجه

فاز ۴-B تکمیل شد. Runtime ایتا دیگر از نظر معماری یک مجموعهٔ سراسری و مشترک نیست؛
اکنون `EitaaRuntimeRegistry` می‌تواند برای هر `MessengerAccount` یک
`EitaaAccountRuntime` مستقل بسازد و تمام وضعیت‌های قابل‌تغییر Provider را به همان حساب
محدود کند.

مسیر Legacy فعلی نیز صریحاً حفظ شده است. تا وقتی
`features.multi_session.enabled` خاموش باشد، API نسخهٔ ۱ فقط و فقط از Runtime قدیمی
استفاده می‌کند و حتی برای انتخاب حساب به Coordinator مراجعه نمی‌کند. بنابراین رفتار عادی
نسخهٔ فعلی نرم‌افزار تغییر نکرده است.

ورود، خروج، Challenge، انقضا و لغو نشست عمداً در این فاز فعال نشده‌اند و متعلق به فاز ۴-C
هستند.

## اجزای اضافه‌شده

### Registry و انتخاب Fail-closed

فایل اصلی:

`src/eitaa_bridge/application/account_runtime.py`

قواعد انتخاب Runtime:

1. Feature خاموش: API v1 فقط `legacy` را می‌گیرد.
2. Feature روشن: وجود `legacy_default_messenger_account_id` معتبر اجباری است.
3. API v1 در حالت چندحسابی فقط حساب پیش‌فرض صریح را می‌گیرد؛ انتخاب ضمنی یا «اولین حساب» وجود ندارد.
4. حساب انتخاب‌شده باید Provider برابر `eitaa` داشته باشد.
5. فقط `storage_revision = 1` پذیرفته می‌شود.
6. حساب فقط در وضعیت `lifecycle_state = active` و `desired_worker_state = running` قابل اجراست.
7. نبود حساب، Provider اشتباه، نسخهٔ ذخیره‌سازی ناشناخته یا وضعیت غیرقابل اجرا همگی پیش از ساخت Worker رد می‌شوند.

این سیاست باعث می‌شود روشن‌کردن اشتباه Feature نیز هیچ حساب نامشخصی را فعال نکند.

### Runtime مستقل هر حساب

برای هر `MessengerAccount` موارد زیر نمونه و حافظهٔ مستقل دارند:

- `EitaaOperationScheduler` و Thread اختصاصی
- قفل عملیات ایتا و قفل Auth
- Auth Runtime و Auth Challenge placeholder
- Dialog Sync jobs
- Content Index jobs، cancellationها و Store
- Contact Import jobs و cancellationها
- Sender Directory
- Dialog Catalog
- Cache مخاطبان ایتا
- Cache رسانه و Avatar
- Read Receipt queue و وضعیت Worker آن
- Background tasks
- مسیر Upload موقت
- Diagnostics و Worker Log
- Worker Lease

دفتر مخاطبان محلی همچنان عمداً متعلق به Coordinator است. اتصال یک مخاطب محلی به هویت
هر پیام‌رسان باید از طریق `account_contact_bindings` انجام شود و با تکثیر دفتر مخاطبان
پیاده‌سازی نخواهد شد.

### مسیرهای حسابی

برای حساب `A = messenger_account_id`:

```text
data/accounts/A/
  provider/
    session/eitaa_session.json
    state/
      sender_directory.sqlite3
      ui-peers/catalog.json
      contact-peers/
  core/messages.sqlite3
  media/
  index/content_index.sqlite3

runtime/accounts/A/
  diagnostics/
    core/
    worker/
  logs/worker.jsonl
  cache/uploads/
  worker.lock
```

فایل‌های رسانه و Peer در حالت حسابی اجازه ندارند از مرز `data/accounts/A` خارج شوند.
این محدودیت در حالت Legacy اعمال نمی‌شود تا سازگاری قبلی حفظ شود.

## Core حساب‌محور

`EitaaBridge.open()` اکنون یک `core_config_override` کامل می‌پذیرد. API هنگام بازکردن
Bridge دقیقاً `selected_runtime.ownership.core` را می‌فرستد؛ در نتیجه Session، Core DB،
Media و Core Diagnostics همگی متعلق به همان حساب‌اند.

بستن Core نیز محدود شده است:

- `close_shared_core(core_config)` فقط Core همان حساب را می‌بندد.
- مسیر Runtime حسابی دیگر از `close_shared_cores()` سراسری استفاده نمی‌کند.
- خروج یا خرابی یک حساب، Core حساب دیگر را متوقف نمی‌کند.
- متد سراسری قدیمی فقط برای سازگاری با کدها و آزمون‌های Legacy باقی مانده است.

## اصلاح مهم Sender Directory

Hook تاریخچهٔ ایتا قبلاً یک Store سراسری داشت. در اجرای دو حساب، آخرین حساب بازشده
می‌توانست باعث ثبت Senderهای حساب اول در پایگاه حساب دوم شود.

این وابستگی با `ContextVar` و `sender_directory_scope()` حساب‌محور جایگزین شد. هر عملیات
Scheduler هنگام اجرا Store همان Runtime را به Context متصل می‌کند. fallback قدیمی فقط
برای Legacy صریح باقی مانده است.

## Worker Lease

هر Runtime حسابی پیش از شروع، فایل `worker.lock` را به‌صورت انحصاری ایجاد می‌کند. محتوای
امن آن شامل شناسهٔ حساب، Provider، شناسهٔ Lease، PID، نسل نشست و نسخهٔ Storage است.
تلاش Process یا Registry دوم برای مالکیت همان حساب رد می‌شود. هنگام بسته‌شدن سالم، فقط
مالکی که `lease_id` منطبق دارد اجازهٔ حذف Lock را دارد.

در این فاز بازیابی خودکار Lock پس از Crash عمداً پیاده‌سازی نشده است؛ Lock ناشناخته یا
باقی‌مانده Fail-closed می‌ماند. تشخیص Process مرده، آرشیو Lock قدیمی و هماهنگی Supervisor
باید همراه Worker orchestration در ۴-D تکمیل شود تا پاک‌کردن خودکار اشتباه، دو Worker
هم‌زمان ایجاد نکند.

## لاگ‌گذاری

الزام لاگ دقیق در این فاز اعمال شد:

- هر حساب فایل مستقل `runtime/accounts/A/logs/worker.jsonl` دارد.
- فیلدهای `messenger_account_id`، `provider=eitaa` و `owner_mode` به همهٔ رویدادهای حساب تزریق می‌شوند.
- Context معتبر Runtime بر مقدار هم‌نامی که Caller بفرستد اولویت دارد؛ بنابراین یک رویداد نمی‌تواند خود را به حساب دیگری منتسب کند.
- درخواست API علاوه بر Application Log، با Account Context در Worker Log همان حساب ثبت می‌شود.
- آزمون‌ها ثابت می‌کنند شماره تلفن و Token در رویداد حسابی تولیدشده وارد نمی‌شوند.

ادامهٔ برنامهٔ لاگ:

- ۴-C: رویدادهای امن login، challenge، expiration، invalid session، logout و revocation
- ۴-D: correlation کامل، rotation policy، redaction audit، support bundle و آزمون نشت بین حساب‌ها

Operational Log همچنان از Audit پایدار Coordinator جدا می‌ماند.

## سازگاری Legacy

هنگام خاموش‌بودن Feature:

- همان Session و Core DB قبلی استفاده می‌شوند.
- همان Content Index، Sender Directory، Dialog Catalog و Contact Peer State قبلی استفاده می‌شوند.
- Upload و Media Cache قبلی حفظ می‌شوند.
- انتخاب مستقیم Runtime حسابی با خطای امن رد می‌شود.
- Coordinator یا `data/accounts` فقط به‌علت ساخت Registry باز یا ایجاد نمی‌شود.
- API و UI فعلی همان رفتار قبلی را دارند.

## وضعیت نصب واقعی پس از فاز

بررسی نهایی فقط به‌صورت خواندنی انجام شد:

- فایل واقعی `bridge.json` بخش `features` ندارد؛ بنابراین هر دو قابلیت با مقدار پیش‌فرض امن خاموش‌اند.
- `multi_session.enabled = false`
- `app_user_auth.enabled = false`
- پوشهٔ واقعی `runtime/accounts` ایجاد نشده است.
- حساب مهاجرت‌یافته همچنان:
  - `provider = eitaa`
  - `lifecycle_state = created`
  - `desired_worker_state = stopped`
  - `auth_state = absent`
  - `session_generation = 1`
  - `storage_revision = 1`
- هیچ Login، Logout یا ارتباط واقعی با ایتا انجام نشد.
- هیچ فایل نشست تولیدی جابه‌جا یا بازنویسی نشد.
- هیچ Commit یا Push انجام نشد.

حتی اگر Feature بدون آماده‌سازی فاز ۴-C روشن شود، حساب فعلی به‌دلیل `created/stopped`
بودن Fail-closed می‌شود و Worker آن آغاز نخواهد شد.

## آزمون‌ها

### آزمون‌های اختصاصی ۴-B

موارد اصلی پوشش‌داده‌شده:

- Feature خاموش و Legacy صریح، بدون دسترسی به Coordinator
- الزام حساب پیش‌فرض صریح هنگام روشن‌بودن Feature
- جدایی کامل Runtime، قفل‌ها، Scheduler، Store، Cache، Job و مسیرهای دو حساب
- Context صحیح Sender Directory در دو Scheduler
- Log مستقل با Account Context غیرقابل جعل
- رد Worker دوم برای همان حساب
- حذف Worker Lock در shutdown سالم
- رد حساب غیرقابل اجرا پیش از ایجاد فایل Runtime
- استفادهٔ API v1 از تمام مسیرهای حساب پیش‌فرض
- جلوگیری از Media و Peer cross-account
- جایگزینی رفتاری تمام قرارداد Core در Facade
- بسته‌شدن Core یک حساب بدون اثر روی Core حساب دوم
- حفظ رفتار Media Cache در Legacy

### نتیجهٔ مجموعهٔ کامل

- ۳۴۷ آزمون جمع‌آوری شد.
- ۳۴۶ آزمون موفق شد.
- یک شکست تاریخی و نامرتبط باقی ماند:

`tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`

Fixture این آزمون مسیر لاتین `Eitaa` را تولید می‌کند ولی Assertion انتظار مسیر فارسی
`ایتا` را دارد. فاز ۴-B این بخش را تغییر نداده است.

### کنترل کیفیت

- `compileall`: موفق
- `git diff --check`: موفق
- آزمون متمرکز سازگاری Media و جداسازی حساب: ۱۰ موفق
- آزمون رفتاری Core override: موفق
- اجرای کامل: ۳۴۶ موفق، ۱ شکست تاریخی
- پوشه‌های موقت آزمون پس از بررسی پاک شدند.

## موارد منتقل‌شده به ۴-C

فاز ۴-C باید چرخهٔ عمر Auth و Session را روی همین Runtime حسابی پیاده‌سازی کند:

1. Status حساب‌محور و بدون نمایش دادهٔ حساس
2. درخواست کد، ثبت کد و رمز دوم برای `messenger_account_id` مشخص
3. Challenge مستقل هر حساب با انقضا و جلوگیری از اختلاط
4. انتقال‌های معتبر `auth_state`
5. افزایش و کنترل `session_generation`
6. Logout، local reset، invalidation و revocation فقط برای همان حساب
7. هماهنگی وضعیت Core session file با Coordinator metadata
8. Audit پایدار انتقال‌های حساس، جدا از Worker Log
9. حفظ endpointهای v1 روی default صریح و افزودن قرارداد داخلی حساب‌محور بدون فعال‌کردن UI چندحسابی
10. خاموش نگه‌داشتن Feature تا آزمون و پذیرش مستقل ۴-C

## موارد باقی‌مانده برای ۴-D

- انتخاب حساب در API و UI و کنترل Membership هر AppUser
- صفحهٔ مدیریت چند حساب و نمایش Providerها
- Worker process orchestration و بازیابی امن Lock پس از Crash
- correlation، rotation، redaction و support bundle لاگ‌ها
- آزمون End-to-End نشت داده، Job، Cache، Media و Log بین حساب‌ها
- آماده‌سازی Adapter پیام‌رسان‌های دیگر، از جمله «بله»، بدون حدس دربارهٔ API آن

## دروازهٔ ادامه

فاز ۴-B در این نقطه پایان یافته است. دستور مناسب برای ادامه در یک نوبت مستقل:

```text
فاز ۴-C را شروع کن: چرخهٔ ورود، Challenge، وضعیت نشست، Logout، invalidation و revocation
ایتا را برای هر MessengerAccount بر پایهٔ EitaaRuntimeRegistry حساب‌محور کن؛ انتقال‌های
Coordinator و session_generation را اتمیک و Fail-closed نگه دار؛ Audit و Worker Log امن
را تکمیل کن؛ endpointهای v1 را فقط روی legacy default صریح نگه دار؛ Feature Flag را فعال
نکن؛ پس از آزمون کامل و گزارش مستقل PHASE4C متوقف شو.
```

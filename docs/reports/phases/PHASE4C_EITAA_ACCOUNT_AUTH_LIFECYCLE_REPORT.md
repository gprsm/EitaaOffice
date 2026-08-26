# گزارش فاز ۴-C: چرخهٔ Auth و Session حساب‌محور ایتا

- تاریخ: ۲۰۲۶-۰۸-۰۲
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- خط مبنا: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- وضعیت: تکمیل‌شده
- Feature Flag: خاموش و بدون تغییر در نصب واقعی

## نتیجه

فاز ۴-C تکمیل شد. ورود، Challenge کد، رمز دوم، بررسی وضعیت نشست، Logout، تشخیص نشست
نامعتبر، Reset محلی و Revocation اکنون روی مرز صریح یک `MessengerAccount` اجرا می‌شوند.

هر تغییر حساس هم‌زمان دارای سه قید است:

1. به همان `messenger_account_id` محدود است.
2. با `session_generation` و Compare-and-swap از تکمیل عملیات قدیمی جلوگیری می‌کند.
3. تغییر Metadata و Audit پایدار در یک تراکنش Coordinator ثبت می‌شوند.

مسیر Legacy قبلی دست‌نخورده باقی مانده است. چون Feature واقعی خاموش است، نرم‌افزار فعلی
همچنان همان API و نشست Legacy را استفاده می‌کند و هیچ‌یک از مسیرهای حسابی در نصب واقعی
فعال نشده‌اند.

## شمارهٔ تلفن در حالت حسابی

در Runtime حسابی، شماره دیگر یک ورودی آزاد برای انتخاب حساب نیست. شمارهٔ مورد استفاده برای
درخواست کد از PhoneAccount مالک همان MessengerAccount خوانده و با کلید DPAPI نصب باز می‌شود.

قواعد جدید:

- API حسابی می‌تواند درخواست کد را بدون ارسال دوبارهٔ شماره دریافت کند.
- اگر UI قدیمی شماره‌ای نیز بفرستد، آن شماره باید دقیقاً canonical E.164 و برابر شمارهٔ
  محافظت‌شدهٔ همان PhoneAccount باشد.
- شمارهٔ متفاوت پیش از هر تماس با ایتا رد می‌شود.
- شمارهٔ آشکارشده در Log، Audit، Exception context یا Response قرار نمی‌گیرد.
- تنها خلاصهٔ Masked ارائه‌شده توسط Core می‌تواند در پاسخ Challenge نمایش داده شود.

بنابراین در UI چندحسابی آینده، کاربر حساب را انتخاب می‌کند و لازم نیست برای هر ورود دوباره
شماره را در فرم بنویسد. شماره فقط هنگام ساخت PhoneAccount جدید دریافت و محافظت خواهد شد.

حالت Legacy برای حفظ سازگاری همچنان شماره را مانند قبل از فرم فعلی می‌گیرد.

## Challenge حساب‌محور

فایل جدید:

`src/eitaa_bridge/application/account_auth.py`

`AccountAuthChallenge` دارای این Metadata امن است:

- `challenge_id` تصادفی
- `messenger_account_id`
- `session_generation`
- مرحلهٔ `code` یا `password`
- زمان صدور و انقضا
- خلاصهٔ غیرحساس روش ارسال کد

`phone_code_hash` و اطلاعات داخلی SRP فقط در حافظهٔ Runtime و داخل سرویس Core باقی می‌مانند.
آن‌ها در Response، Coordinator، Worker Log یا Audit ذخیره نمی‌شوند.

ارسال کد یا رمز تنها وقتی پذیرفته می‌شود که هر چهار مقدار زیر هم‌زمان منطبق باشند:

1. `challenge_id`
2. حساب انتخاب‌شده
3. `session_generation`
4. مرحلهٔ مورد انتظار

Challenge یک حساب روی حساب دیگر، Challenge نسل قبلی و Challenge منقضی همگی Fail-closed
رد می‌شوند. Challenge معتبر در صورت ورود به مرحلهٔ رمز دوم همان ID و نسل را حفظ می‌کند ولی
مرحله و مهلت آن تازه می‌شوند.

اگر برنامه هنگام Challenge بسته شود، Secret حافظه‌ای قابل بازیابی نیست. Metadata
`challenge_pending` در اجرای بعدی هنگام Status یا درخواست کد جدید به `expired` منتقل و Audit
می‌شود؛ هیچ Challenge ناقصی به‌صورت ضمنی ادامه پیدا نمی‌کند.

## معنای session_generation

نسل نشست اکنون یک Fence عملیاتی است:

| رویداد | وضعیت مقصد | تغییر نسل |
|---|---|---|
| درخواست کد موفق | `challenge_pending` | `+1` برای رزرو نسل جدید |
| تکمیل کد بدون رمز دوم | `authenticated` | همان نسل رزروشده |
| تکمیل رمز دوم | `authenticated` | همان نسل رزروشده |
| انقضای Challenge | `expired` | بدون افزایش مجدد |
| اعتبارسنجی نشست موجود | `authenticated` | بدون افزایش |
| تشخیص Remote 401 | `invalid` | `+1` برای بی‌اعتبارکردن کار قدیمی |
| Logout | `revoked` | `+1` |
| Reset و بایگانی محلی | `absent` | `+1` |

Worker Lease همان حساب پس از هر تغییر نسل به‌صورت اتمیک تازه می‌شود. اگر نوشتن Metadata
Lease شکست بخورد، تغییر Coordinator برگردانده نمی‌شود؛ رویداد خطا در Worker Log ثبت و
اجرای بعدی Supervisor باید این ناسازگاری را Fail-closed بررسی کند. تکمیل Supervisor و
بازیابی Lock متعلق به ۴-D است.

## انتقال‌های Coordinator

فایل اصلی:

`src/eitaa_bridge/infrastructure/coordinator/store.py`

متد `transition_messenger_auth()` موارد زیر را در یک `BEGIN IMMEDIATE` انجام می‌دهد:

- خواندن وضعیت و نسل فعلی
- بررسی حالت مورد انتظار و نسل مورد انتظار
- بررسی مجازبودن انتقال
- Compare-and-swap روی همان حساب
- تغییر `auth_state` و `session_generation`
- ثبت `last_validated_at` در اعتبارسنجی موفق
- ثبت `last_auth_transition_at` در تغییر واقعی
- افزودن Audit زنجیره‌دار همان رویداد
- Commit واحد

اگر یک Challenge قدیمی پس از ایجاد نسل جدید تلاش به تکمیل کند، هیچ Metadata یا Audit موفقی
ثبت نمی‌شود و خطای `messenger_auth_transition_conflict` برمی‌گردد.

## هماهنگی فایل نشست و Coordinator

Database و Filesystem نمی‌توانند یک تراکنش مشترک SQLite داشته باشند؛ به همین دلیل ترتیب
Fail-closed زیر اعمال شد:

- Login فقط پس از مشاهدهٔ فایل نشست ذخیره‌شده می‌تواند `authenticated` شود.
- اگر Core فایل را ذخیره کند ولی Coordinator تکمیل را نپذیرد، فایل فعال با پسوند
  `.uncoordinated.<timestamp>.bak` بایگانی می‌شود.
- Logout یا Reset ابتدا فایل فعال را حذف یا بایگانی و سپس Metadata را Fence می‌کند.
- اگر پس از Logout موفق Provider فایل فعال باقی بماند، Bridge آن را با پسوند
  `.logout.<timestamp>.bak` بایگانی می‌کند.
- نشست Remote-invalid با پسوند `.invalid.<timestamp>.bak` حفظ می‌شود.
- نام Archive در Response فقط basename است و مسیر کامل نصب افشا نمی‌شود.

این فایل‌ها برای بازیابی و بررسی باقی می‌مانند و به‌صورت خودکار حذف نمی‌شوند.

## Status و Reconciliation

Status حسابی علاوه بر وضعیت محلی، Metadata امن حساب و نسل را برمی‌گرداند.

رفتارهای اصلی:

- فایل غایب همراه Metadata `authenticated` باعث انتقال به `invalid` و افزایش نسل می‌شود.
- Challenge حافظه‌ای گمشده یا منقضی به `expired` منتقل می‌شود.
- Metadata `revoked` یا `invalid` اجازه نمی‌دهد وجود یک فایل باقی‌مانده دوباره آن را معتبر کند.
- فقط Remote 401 دلیل قطعی برای `invalid` محسوب می‌شود.
- خطای شبکه، Lock موقت یا خطای غیر 401 وضعیت را بی‌دلیل Invalid نمی‌کند.
- Remote probe موفق، `last_validated_at` را تازه می‌کند.
- Status تکراری روی یک نشست معتبر Audit انتقال تکراری تولید نمی‌کند.

## Logout، Reset و Revocation

- Logout موفق Remote فقط همان حساب را `revoked` می‌کند.
- Remote 401 هنگام Logout باعث بایگانی محلی و Revocation همان حساب می‌شود.
- Logout بدون فایل فعال، Challenge همان حساب را می‌بندد و در صورت نیاز نسل را Fence می‌کند.
- Logout تکراری روی حالت `revoked` بدون فایل، نسل را بی‌دلیل افزایش نمی‌دهد.
- Reset نیازمند `confirm=true` است؛ ردشدن به‌علت نبود تأیید Audit می‌شود.
- Reset فقط فایل Session همان Ownership را بایگانی می‌کند و به `absent` می‌رود.
- `close_shared_core()` فقط Core همان حساب را می‌بندد.

## Audit و Log امن

Auditهای Auth دارای این Context هستند:

- Actor از نوع `app_user` همراه نقش، یا `system` وقتی AppUser Auth خاموش است
- `request_id`
- `phone_account_id`
- `messenger_account_id`
- Provider
- وضعیت و نسل قبل و بعد
- Result و Reason code ثابت

Metadata Audit فقط scalarهای کوچک را می‌پذیرد. کلیدهای دارای واژه‌های حساس زیر صریحاً رد
می‌شوند:

`phone`, `token`, `password`, `secret`, `code`, `hash`, `ciphertext`, `imei`

Worker Log رویدادهای صدور Challenge، تغییر مرحله، انتقال Auth، بایگانی Fail-closed و خطای
Audit را با Context غیرقابل‌جعل همان حساب ثبت می‌کند. آزمون‌ها ثابت می‌کنند شمارهٔ کامل، کد
ورود، رمز دوم و Token در Audit یا Worker Log ظاهر نمی‌شوند.

## سازگاری API v1

- Feature خاموش: تمام endpointهای فعلی Auth دقیقاً مسیر Legacy قبلی را اجرا می‌کنند.
- Feature روشن: endpointهای v1 فقط Runtime حساب پیش‌فرض صریح را اجرا می‌کنند.
- هیچ account ID ارسالی از Body یا Query برای تغییر Owner پذیرفته نمی‌شود.
- انتخاب حساب دلخواه و کنترل Membership به API/UI فاز ۴-D منتقل شده است.
- Feature در این فاز فعال نشده است.

## فایل‌های اصلی تغییرکرده

- `src/eitaa_bridge/application/account_auth.py`
- `src/eitaa_bridge/application/account_runtime.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `src/eitaa_bridge/infrastructure/coordinator/__init__.py`
- `tests/test_account_auth_lifecycle.py`

## آزمون‌ها

### آزمون‌های اختصاصی ۴-C

۹ آزمون چرخهٔ حسابی موفق شدند:

- شماره از PhoneAccount محافظت‌شده و رد شمارهٔ متعلق به حساب دیگر
- رزرو نسل هنگام Request Code
- رد Challenge جعلی
- ورود کامل با کد
- جلوگیری از استفادهٔ Challenge حساب اول روی حساب دوم
- ورود دومرحله‌ای موفق
- انقضای Challenge رمز دوم بدون ارسال Password به Provider
- تشخیص Remote 401 و افزایش یک‌بارهٔ نسل
- Logout موفق و Logout با نشست از قبل نامعتبر
- Reset محلی و تازه‌شدن Worker Lease
- Compare-and-swap و Audit اتمیک
- ثبت Actor و Request ID
- رد Metadata حساس Audit
- نبود شماره، کد، رمز و Token در Audit و Log

### مجموعهٔ متمرکز

۹۳ آزمون Auth، AppUser، Coordinator، Runtime و Legacy موفق شدند.

### مجموعهٔ کامل

- ۳۵۶ آزمون جمع‌آوری شد.
- ۳۵۵ آزمون موفق شد.
- یک شکست تاریخی و نامرتبط باقی ماند:

`tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`

Fixture این آزمون مسیر لاتین `Eitaa` را می‌سازد، ولی Assertion انتظار مسیر فارسی `ایتا`
را دارد. کد ۴-C به آن قسمت دست نزده است.

### کنترل کیفیت

- `compileall`: موفق
- `git diff --check`: موفق
- بررسی trailing whitespace فایل‌های جدید: موفق
- هیچ اتصال واقعی برای Login، Logout یا Status به ایتا انجام نشد؛ تمام Provider interactionهای آزمون Fake بودند.
- هیچ Commit یا Push انجام نشد.

## وضعیت نصب واقعی پس از فاز

بررسی نهایی فقط خواندنی بود:

- `bridge.json` واقعی بخش `features` ندارد.
- `multi_session.enabled = false`
- `app_user_auth.enabled = false`
- `runtime/accounts` واقعی وجود ندارد.
- حساب مهاجرت‌یافته همچنان:
  - `provider = eitaa`
  - `lifecycle_state = created`
  - `desired_worker_state = stopped`
  - `auth_state = absent`
  - `session_generation = 1`
  - `storage_revision = 1`
- هیچ فایل نشست واقعی جابه‌جا یا بازنویسی نشد.
- هیچ Process مربوط به Python، Electron یا Bridge پروژه فعال نبود.
- برنامهٔ مستقل Eitaa Desktop هنگام بررسی باز بود، اما به Runtime پروژه ارتباطی نداشت و دست‌کاری نشد.

## موارد منتقل‌شده به ۴-D

1. API نسخهٔ ۲ برای فهرست حساب‌های مجاز AppUser
2. انتخاب `messenger_account_id` با کنترل Membership همان PhoneAccount
3. UI مدیریت حساب‌ها، Provider و وضعیت Login هر حساب
4. فعال/متوقف‌کردن Worker با انتقال‌های lifecycle و desired state
5. Supervisor، heartbeat و بازیابی امن Worker Lock پس از Crash
6. جلوگیری End-to-End از نشت Cache، Media، Job، Log و Challenge میان حساب‌ها
7. Correlation کامل Application/Worker/Audit
8. Rotation، Redaction audit و Support Bundle حساب‌محور
9. راه‌اندازی کنترل‌شدهٔ حساب مهاجرت‌یافته بدون روشن‌کردن عمومی Feature
10. آماده‌سازی قرارداد Adapter برای «بله» بدون حدس دربارهٔ API آن

## دروازهٔ ادامه

فاز ۴-C در این نقطه پایان یافته است. دستور مناسب برای ادامه در یک نوبت مستقل:

```text
بخش ۴-D را شروع کن: API و UI انتخاب و مدیریت MessengerAccount را با کنترل دقیق Membership
هر AppUser پیاده‌سازی کن؛ Worker lifecycle و Supervisor، heartbeat و بازیابی امن Lock پس از
Crash را اضافه کن؛ جداسازی End-to-End Cache، Media، Job، Challenge و Log را آزمایش کن؛
Correlation، Rotation، Redaction و Support Bundle را تکمیل کن؛ مسیر Legacy را حفظ کن و
Feature Flag را بدون پذیرش مستقل فعال نکن؛ دربارهٔ API پیام‌رسان بله چیزی حدس نزن؛ پس از
آزمون کامل و گزارش مستقل PHASE4D متوقف شو.
```

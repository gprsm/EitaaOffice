# گزارش فاز ۴-A: قرارداد مالکیت نشست و مرزهای حساب ایتا

- تاریخ: ۲۰۲۶-۰۷-۳۱
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- خط مبنا: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- وضعیت: تکمیل‌شده
- نوع تغییر: معماری و قرارداد غیرفعال؛ بدون تغییر رفتار Runtime

## نتیجه

فاز ۴-A تکمیل شد. مالکیت نشست و تمام فایل‌های وابسته به حساب ایتا اکنون با
`EitaaSessionOwnership` به‌صورت صریح تعریف می‌شود. این قرارداد فقط دو حالت
مجاز دارد:

1. `legacy`: مسیر مشترک فعلی، بدون انتساب ضمنی به هیچ حساب
2. `messenger_account`: مسیرهای کاملاً جداشده و مشتق‌شده از یک
   `messenger_account_id` معتبر

قرارداد جدید در این فاز به API، Facade یا Runtime متصل نشده است؛ بنابراین
برنامه همچنان دقیقاً از مسیر Legacy فعلی استفاده می‌کند. هیچ نشست باز نشد،
هیچ ارتباطی با ایتا برقرار نشد، هیچ فایل عملیاتی جابه‌جا یا بازنویسی نشد و
هیچ Feature Flag فعال نشد.

## وضعیت ایمنی هنگام اجرا

- برنامه پیش از آغاز فاز بسته بود.
- `multi_session.enabled = false`
- `app_user_auth.enabled = false`
- حساب مهاجرت‌یافته فقط به‌صورت خواندنی بررسی شد.
- هر هفت جزء مورد انتظار حساب مهاجرت‌یافته در مسیر جدید موجود و منطبق بودند:
  نشست، Core DB، رسانه، Content Index، Sender Directory، Dialog Catalog و
  Contact Peer State.

## ممیزی مالکیت مشترک فعلی

### فایل‌ها و پوشه‌های مشترک Legacy

| داده | مسیر فعلی |
|---|---|
| نشست ایتا | `.eitaa_session.json` |
| پایگاه پیام‌های Core | `data/eitaa_messages.sqlite3` |
| رسانه | `data/media` |
| Diagnostics مربوط به Core | `diagnostics/core` |
| Content Index | `data/content_index.sqlite3` |
| Sender Directory | `data/sender_directory.sqlite3` |
| Dialog Catalog | `data/ui-peers/catalog.json` |
| Contact Peer State | `data/eitaa-contact-peers` |

فایل `data/contacts.sqlite3` عمداً در این فهرست قرار نگرفت، زیرا دفتر مخاطبان
محلی متعلق به Coordinator است. اتصال مخاطب محلی به هویت یک پیام‌رسان باید
بعداً با Binding حساب‌محور انجام شود و نباید با تکثیر دفتر مخاطبان پیاده‌سازی
شود.

### وضعیت مشترک در حافظه و Process

ممیزی `BridgeApplicationApi` این وابستگی‌های سراسری را ثبت کرد:

- یک `EitaaOperationScheduler`
- یک قفل عملیات ایتا
- یک Auth Runtime و یک Auth Challenge
- یک Dialog Catalog
- یک Content Index Store
- یک Sender Directory
- یک Cache مخاطبان ایتا
- یک Cache رسانه و Avatar
- یک صف Read Receipt
- Jobهای Dialog Sync، Content Index، Contact Import و Background Task
- ۴۸ محل فراخوانی `_open_bridge(...)`

همچنین `EitaaBridge` یک مخزن سراسری Shared Core دارد و
`close_shared_cores()` همه Coreهای ثبت‌شده را با هم می‌بندد. این رفتار برای
Runtime چندحسابی قابل استفاده نیست، چون Logout یا خرابی یک حساب می‌تواند
حساب‌های دیگر را نیز متوقف کند.

### ورود و خروج فعلی

مسیرهای API نسخه ۱ برای Status، درخواست کد، ثبت کد، رمز دوم، بازیابی نشست و
Logout همگی به همان نشست مشترک متصل‌اند. رابط کاربری نیز یک Login Gate و یک
Auth Status سراسری دارد. این موارد در ۴-A فقط ثبت شدند و در ۴-C حساب‌محور
خواهند شد.

### اسکریپت‌ها و نصب‌کننده

موارد Legacy زیر نیز شناسایی شدند:

- Backup و Runtime State
- Diagnostics Bundle
- Smoke Test
- Office Installer و Upgrade Scriptها
- Doctor و CLI

این مسیرها نباید هم‌زمان و یکجا تغییر کنند. در ۴-B مسیر Runtime و دادهٔ حساب
اضافه می‌شود، اما نگهداری مسیر Legacy تا پایان دورهٔ سازگاری الزامی است.

## قرارداد جدید

فایل اصلی قرارداد:

`src/eitaa_bridge/infrastructure/eitaa/session_ownership.py`

### قواعد Fail-closed

- شناسه حساب فقط UUID نسخه ۴ با قالب canonical و حروف کوچک است.
- شناسه خالی، UUID نسخه دیگر، حروف بزرگ، قالب آکولادی و تلاش برای Path
  Traversal رد می‌شود.
- هیچ شماره تلفن، نام نمایشی یا Provider Subject وارد نام مسیر نمی‌شود.
- تمام مسیرها باید داخل ریشه نصب باقی بمانند.
- مسیر خارج از نصب بدون نمایش مقدار حساس در خطا رد می‌شود.
- ساختن قرارداد هیچ فایل یا پوشه‌ای ایجاد نمی‌کند.
- حالت Legacy نمی‌تواند خود را مالک Worker حساب معرفی کند.
- حالت حسابی بدون `messenger_account_id` معتبر ساخته نمی‌شود.
- Summary امن، مسیر کامل نصب، Token، شماره تلفن و Secret را برنمی‌گرداند.

### مسیرهای قطعی حساب

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
  diagnostics/core/
  logs/worker.jsonl
  cache/
  worker.lock
```

این ساختار با خروجی واقعی Migration فاز ۲ یکسان است. ثابت‌های Migration نیز
به همین منبع واحد متصل شدند؛ نام و مقصد هیچ فایل مهاجرتی تغییر نکرد.

## مرزهای مالکیت برای ۴-B

| جزء | مالک نهایی |
|---|---|
| AppUser، Membership و Account Registry | Coordinator |
| دفتر مخاطبان محلی | Coordinator |
| نشست ایتا | MessengerAccount Worker |
| Core DB و Media | MessengerAccount Worker |
| Dialog Catalog و Sender Directory | MessengerAccount Worker |
| Content Index مرتبط با پیام‌ها | MessengerAccount Worker |
| Scheduler، Lock، Auth Runtime و Challenge | MessengerAccount Worker |
| Cache، Read Receipt و Job اجرای Provider | MessengerAccount Worker |
| Operational Log حساب | همان Worker، فایل اختصاصی همان حساب |
| Audit پایدار | Coordinator DB |

## تصمیم مربوط به لاگ‌گذاری

الزام لاگ دقیق در این فاز فراموش نشده است. ۴-A مسیر اختصاصی
`runtime/accounts/A/logs/worker.jsonl` را به قرارداد اضافه کرد تا دو Worker
هرگز در یک فایل مشترک ننویسند.

تقسیم کار لاگ به این صورت است:

- ۴-B: اتصال هر Runtime حساب به فایل عملیاتی اختصاصی و افزودن Account Context
- ۴-C: ثبت رویدادهای امن ورود، Challenge، انقضا، Invalid Session و Logout
- ۴-D: تکمیل Correlation، Rotation، Redaction، Support Bundle و آزمون‌های
  نشت اطلاعات

Audit تغییرات حساس همچنان محصولی جدا از Operational Log باقی می‌ماند.

## تغییرات کد

- افزودن `SessionOwnershipError`
- افزودن `EitaaSessionOwnership`
- افزودن `SessionOwnershipMode`
- افزودن اعتبارسنج UUIDv4 canonical
- افزودن محافظت از خروج مسیرها از ریشه نصب
- تعریف مسیرهای داده، Diagnostics، Cache، Log و Lock هر حساب
- اتصال مقصدهای Migration فاز ۲ به ثابت‌های همین قرارداد
- افزودن آزمون معماری برای اثبات غیرفعال‌بودن قرارداد در Runtime فعلی

## آزمون‌ها

### آزمون متمرکز

۱۹ آزمون مربوط به قرارداد مالکیت و Migration موفق شدند.

موارد پوشش‌داده‌شده:

- عدم ایجاد فایل یا پوشه هنگام Resolve
- انطباق دقیق با Layout مهاجرت
- جدایی کامل دو حساب
- رد شناسه‌های نامعتبر
- رد مسیر خارج از نصب
- حفظ صریح مسیر Legacy
- خروجی امن Summary
- عدم اتصال قرارداد ۴-A به API و Facade فعلی
- عدم تغییر رفتار Copy-and-verify Migration

### مجموعه کامل

- ۳۳۹ آزمون جمع‌آوری شد.
- ۳۳۸ آزمون موفق شد.
- یک شکست تاریخی و نامرتبط باقی ماند:
  `tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`

این همان Fixture ثبت‌شده در فاز ۳ است: داده آزمایشی دارای واژه لاتین `Eitaa`
است، اما Assertion انتظار مسیر فارسی `ایتا` را دارد. کد ۴-A هیچ تغییری در
این بخش نداده است.

### کنترل کیفیت

- `git diff --check`: موفق
- بررسی خواندنی حساب مهاجرت‌یافته: همه مسیرها موجود
- اتصال شبکه یا Login واقعی: انجام نشد
- تغییر Schema یا داده تولیدی: انجام نشد
- Commit یا Push: انجام نشد

## موارد عمداً منتقل‌شده به ۴-B

۴-B باید فقط Runtime و Storage حساب‌محور را با حفظ Legacy Compatibility
پیاده‌سازی کند:

1. ساخت Runtime Registry با کلید `messenger_account_id`
2. ساخت Scheduler، Lock و Storeهای جدا برای هر حساب
3. بازکردن Core با `ownership.core`
4. حذف استفاده چندحسابی از `close_shared_cores()` سراسری و جایگزینی Close
   محدود به همان حساب
5. انتقال Cacheها، Read Receipt و Jobهای Provider به Scope حساب
6. اتصال Worker Log اختصاصی با Account Context امن
7. حفظ API نسخه ۱ روی Legacy Default صریح
8. خاموش نگه‌داشتن Feature Flag تا پذیرش مستقل

ورود، خروج، انقضا و لغو نشست همچنان متعلق به ۴-C است و نباید به‌صورت ناقص در
۴-B فعال شود.

## دروازه ادامه

فاز ۴-A در این نقطه پایان یافته است. دستور بعدی مجاز:

```text
بخش ۴-B را شروع کن: Runtime و Storage ایتا را بر پایه قرارداد
EitaaSessionOwnership برای هر MessengerAccount جدا کن، مسیر Legacy را صریح و
سازگار نگه دار، Feature Flag را فعال نکن، ورود/خروج حساب‌محور را به ۴-C
منتقل کن و پس از گزارش مستقل ۴-B متوقف شو.
```

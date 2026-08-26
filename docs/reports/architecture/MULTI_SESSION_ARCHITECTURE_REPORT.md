# گزارش فاز صفر: ممیزی معماری چندکاربره، چندحسابی و چندپیام‌رسانی

- تاریخ: ۲۰۲۶-۰۷-۳۱
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- نسخه محصول: `0.7.0-ui-mvp6.1.1-gmi4.2`
- Bridge: `0.7.0.dev31`
- Core: `0.6.0-core7.4.5-gmi1` / `0.6.0.dev19`

## نتیجه اجرایی

فاز صفر تکمیل شد. در این فاز هیچ قابلیت چندحسابی، مهاجرت داده، ورود واقعی یا
ارسال واقعی پیاده‌سازی نشد. تنها تغییر محصول، ایجاد همین گزارش است.

نسخه Production فعلی واقعاً تک‌سشن است. یک نمونه `BridgeApplicationApi` مالک
موارد زیر است:

- یک `EitaaOperationScheduler`
- یک فایل Session در تنظیمات Core
- یک پایگاه پیام Core
- یک Media Directory
- یک مجموعه Cache و Job در حافظه
- یک دفترچه گفتگو و یک Sender Directory سراسری
- یک فایل Runtime Log مشترک

کد `lab/multi_account_coordinator.py` فقط یک مدل آفلاین تخصیص است و در Runtime
محصول Import نمی‌شود. بنابراین وجود آن به معنی پشتیبانی عملیاتی از چند حساب
نیست.

برای پشتیبانی از بله و پیام‌رسان‌های آینده، مدل مستقیم
`AppUser → EitaaAccount` نباید مبنای پیاده‌سازی شود. مرز صحیح چهارلایه است:

```text
AppUser
  └── PhoneAccount
        └── MessengerAccount
              └── Provider Session / Worker / Account Data
```

یک شماره تلفن یک `PhoneAccount` است و می‌تواند هم‌زمان دو
`MessengerAccount` مستقل برای `eitaa` و `bale` داشته باشد. سشن و Worker باید
در سطح `MessengerAccount` جدا شوند، نه فقط در سطح شماره تلفن.

## مبنای ممیزی

موارد زیر بررسی شدند:

- همه فایل‌های `*REPORT*.md` و `CONTINUATION_LOG*.md` در ریشه پروژه
- گزارش‌های معماری GMI3، GMI4 و GMI4.2
- گزارش‌های Session Recovery، مخاطبان، اعضا، RTL و رابط
- وضعیت Git و فایل مرجع موجود در `catalog`
- تنظیمات Bridge و مسیرهای Runtime/Data
- API، Scheduler، Core Binding و Facade
- پایگاه‌های مخاطبان، Content Index و Sender Directory
- Dialog Catalog، Composition Store و Jobهای محلی
- HTTP adapter، روش Authorization و Polling رابط
- Runtime Logger، Diagnostics، Redaction و آزمون‌های آن‌ها
- اسکریپت‌های Backup/Restore
- آزمایشگاه آفلاین چندحسابی
- آزمون‌های Python، TypeScript، Vite، Electron و مدل‌های رابط

پوشه `catalog` فقط برای تطبیق مرجع خوانده شد و هیچ فایلی از آن وارد Source نشد.

## وضعیت Git و مرجع پروژه

- شاخه: `main`
- Commit آغاز فاز: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- Worktree پیش از ممیزی: پاک
- Worktree پس از اجرای آزمون‌ها و Build: پاک
- `git diff --check`: موفق
- فایل مرجع:
  `catalog/Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Eitaa_Contacts_Quick_Send.zip`
- SHA-256 مرجع:
  `4A98730EFD81CE71B8843A09721D2953B263EEB503D62D42722D917C34B5E6D8`
- هش مرجع با مقدار ثبت‌شده در گزارش قبلی کاملاً منطبق است.

فایل‌های واقعی `.env`، Session، Data، Runtime Logs و Diagnostics توسط
`.gitignore` کنار گذاشته شده‌اند. فقط فایل‌های نمونه تنظیمات در Git وجود دارند.

## خط مبنای آزمون‌ها

هیچ آزمونی به حساب واقعی ایتا متصل نشد و هیچ پیام، دعوت یا تغییر مخاطب واقعی
انجام نشد.

### Python

- تعداد آزمون‌های جمع‌آوری‌شده: `279`
- موفق: `278`
- ناموفق: `1`
- اجرای همه آزمون‌ها به‌جز شکست شناخته‌شده: موفق
- Python compileall برای `src`، `lab`، `scripts` و `tests`: موفق

تنها شکست:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

Fixture مسیر لاتین `...\Documents\Eitaa\runtime\edge-profile` می‌سازد، ولی
Assertion انتظار مسیر فارسی `...\Documents\ایتا\runtime\edge-profile` دارد.
این شکست از خط مبنای قبلی نیز گزارش شده، به معماری چندحسابی مربوط نیست و در فاز
صفر اصلاح نشد.

اجرای نخست Pytest به دلیل نداشتن دسترسی محیط Codex به پوشه Temp کاربر ویندوز
در Setup متوقف شد. اجرای معتبر با `--basetemp` اختصاصی داخل Runtime پروژه
تکرار و نتایج بالا از اجرای دوم ثبت شد.

### رابط و Build

- TypeScript `tsc -b`: موفق
- Vite Production Build: موفق
- ماژول‌های تبدیل‌شده: `973`
- Scroll model: `10/10`
- Grouped-media UI model: `16/16`
- Electron main/preload syntax: موفق
- JavaScript اصلی Minified: حدود `848.65 kB`
- هشدار غیرمسدودکننده Vite درباره Chunk بزرگ‌تر از `500 kB` همچنان وجود دارد.

## معماری فعلی

### API و احراز هویت

`BridgeApplicationApi` یک API محلی واحد ایجاد می‌کند. Bearer Token اختیاری
API فقط کل API محلی را محافظت می‌کند و مفهوم کاربر نرم‌افزار نیست.

در حال حاضر موارد زیر وجود ندارند:

- `AppUser`
- نشست ورود کاربر نرم‌افزار
- نقش‌های `admin` و `user`
- مالکیت حساب
- عضویت یا واگذاری دسترسی حساب
- بررسی Server-side مالکیت شناسه حساب

API روی `127.0.0.1` اجرا می‌شود. اتصال Non-loopback بدون Bearer Token رد
می‌شود، اما این کنترل جایگزین RBAC و جداسازی کاربران نیست.

### Session و Scheduler

در `application/api.py` یک `_scheduler` ساخته می‌شود. تمام عملیات Remote ایتا
از همان Scheduler عبور می‌کنند. تنظیم Core نیز فقط یک `session_file`،
`database_file`، `media_directory` و `diagnostics_root` دارد.

چرخه ورود شامل یک `_auth_runtime` و یک `_auth_challenge` است. خروج یا
نامعتبرشدن Session نیز در محدوده همین فایل Session سراسری اجرا می‌شود.

این طراحی برای یک حساب درست است، ولی با ساخت نمونه‌های متعدد در یک Process
ایمن نمی‌شود؛ زیرا:

- Shared Coreهای Facade در یک Registry کلاسی نگهداری می‌شوند.
- `close_shared_cores()` همه Shared Coreهای Process را می‌بندد.
- چند Cache و Job Registry در سطح نمونه API هستند، نه Context حساب.
- مسیرهای Data و Diagnostics از یک Config سراسری می‌آیند.

مرز Production باید یک Process مستقل برای هر `MessengerAccount` باشد تا خطا،
خروج، Crash یا بسته‌شدن Core یک حساب به حساب دیگر سرایت نکند.

### Jobها و Workerها

Jobها دو گروه هستند:

1. برخی Jobهای Core مانند Bulk Send و Membership در SQLite خود Core نگهداری
   می‌شوند.
2. Dialog Sync، Content Index state، Contact Import، Background Task و
   Pending Read Receipt در Dictionaryهای حافظه API نگهداری می‌شوند.

پیامدهای گروه دوم:

- پس از Restart وضعیت عملیاتی آن‌ها از بین می‌رود.
- Lease و Recovery پایدار ندارند.
- مالک `AppUser` یا `MessengerAccount` ندارند.
- یک `job_id` به Context حساب تطبیق داده نمی‌شود.
- Polling رابط فقط شناسه Job/Task را ارسال می‌کند.

در رابط WebSocket، SSE یا Event Bus وجود ندارد. پیشرفت عملیات با Pollingهای
۷۵۰ یا ۱۰۰۰ میلی‌ثانیه‌ای خوانده می‌شود.

## ممیزی ذخیره‌سازی و نقاط فاقد جداسازی

### Core SQLite

`data/eitaa_messages.sqlite3` شامل داده‌های حساب فعلی است و در معماری آینده
باید بدون اشتراک در مسیر اختصاصی `MessengerAccount` قرار گیرد. Migration
نباید جدول‌های داخلی Core را بازنویسی کند؛ انتقال فایل معتبر موجود به فضای
اولین حساب ایتا امن‌تر از دستکاری Schema Core است.

### Session

فایل `.eitaa_session.json` در ریشه پروژه و Config سراسری است. نام فایل،
قفل مالکیت و چرخه Archive باید برای هر `MessengerAccount` مستقل شود.

### Media و Cache

`data/media`، Cache رسانه رابط، Cache آواتار و Tokenهای Media process-local
فاقد شناسه حساب هستند. شناسه Peer و Media می‌تواند در دو حساب یا دو Provider
تکرار شود؛ بنابراین کلید و مسیر باید حساب‌محور شوند.

### Dialog Catalog

کلید فعلی:

```text
{peer_type}:{peer_id}
```

Provider و `messenger_account_id` در کلید وجود ندارند. دو حساب با Peer ID
یکسان می‌توانند رکورد هم را جایگزین کنند.

### Sender Directory

کلید اصلی `sender_profiles` فقط `user_id` است. این شناسه فقط داخل فضای یک
حساب ایتا معنی دارد و در چند حساب یا چند Provider یکتا نیست.

### Content Index

کلید نتیجه فعلی ترکیبی از Site، Peer و Message است، اما Provider و حساب منبع
را ندارد. Feedback، Run و Staging نیز مالک کاربر/حساب ندارند.

### Composition و WordPress Usage

کلید ذخیره فعلی `site_key::composition_key` است و `source_key` پیام نیز از
Peer Type، Peer ID و Message ID ساخته می‌شود. در چند حساب، پیام‌های متفاوت
می‌توانند Source Key یکسان داشته باشند و وضعیت «استفاده‌شده در WordPress» را
به‌اشتباه به یکدیگر منتقل کنند.

### دفترچه مخاطبان محلی

اصل مشترک‌بودن دفترچه محلی قابل حفظ است، اما Schema فعلی اطلاعات مخصوص ایتا
را داخل موجودیت مرکزی Contact نگهداری می‌کند:

- `eitaa_user_id`
- `access_hash`
- `last_resolved_at`

همچنین Unique Index شناسه ایتا سراسری است. این مدل در چند حساب نادرست است،
زیرا یک مخاطب مشترک ممکن است در هر حساب ایتا Peer/Access متفاوت داشته باشد و
در بله نیز شناسه دیگری داشته باشد.

مدل آینده باید دو بخش داشته باشد:

```text
LocalContact (مشترک)
AccountContactBinding / RecipientCapability (خصوصی برای MessengerAccount)
```

شماره نرمال‌شده، نام‌ها، سازمان، دسته‌ها و Opt-out در بخش مشترک باقی می‌مانند.
شناسه Provider، Peer، Reachability و مرجع حساس گیرنده فقط در Binding حساب
قرار می‌گیرند. `access_hash` نباید وارد Coordinator، API یا UI شود و فقط
Worker مالک باید آن را نگهداری کند.

### دسته‌های محلی

رفتار فعلی دسته‌ها مشترک و سراسری است. در فاز صفر تغییری در این رفتار پیشنهاد
اجباری نشده است. تا تصمیم صریح بعدی:

- Local Contact و Opt-out مشترک می‌مانند.
- دسته‌های فعلی نیز برای سازگاری مشترک می‌مانند.
- قابلیت مشاهده مخاطبان واقعی پیام‌رسان و Bindingها حساب‌محور است.

### Backup و Restore

Backup فعلی فایل Session، Config، `.env` و کل پوشه `data` را پوشش می‌دهد و
در حالت اختیاری Logs/Diagnostics را نیز اضافه می‌کند. Manifest شامل Size و
SHA-256 است و Restore پیش از جایگزینی، Backup اجباری می‌سازد.

برای معماری جدید باید فهرست Backup صریحاً شامل این مسیرها شود:

```text
data/coordinator.sqlite3
data/accounts/{messenger_account_id}/...
runtime/accounts/{messenger_account_id}/session/...
runtime/accounts/{messenger_account_id}/locks/...
```

Lock و فایل‌های موقتی نباید Restore شوند. Sessionها باید Restore شوند، ولی
هر Session فقط به همان `messenger_account_id` بازگردد.

## مدل هدف پیشنهادی برای فاز ۱

### AppUser

کاربر واردشونده به نرم‌افزار، با شناسه داخلی پایدار و نقش حداقلی
`admin | user`.

### PhoneAccount

یک حساب مدیریتی مبتنی بر شماره نرمال‌شده:

- `phone_account_id`: UUID داخلی و کلید اصلی
- `normalized_phone`: کلید تجاری نرمال‌شده
- `display_label`
- `status`
- `created_at`, `updated_at`

شماره تلفن نباید Foreign Key اصلی، نام پوشه یا شناسه قابل اعتماد دریافتی از UI
باشد. پیشنهاد ایمن این است که شماره نرمال‌شده در هر نصب محلی یکتا و دسترسی
چند کاربر از طریق Membership مدیریت شود.

### PhoneAccountMembership

رابط میان `AppUser` و `PhoneAccount` برای مالکیت و دسترسی. حتی اگر نسخه نخست
فقط یک Owner داشته باشد، این جدول مانع بازطراحی پرهزینه در آینده می‌شود.

### MessengerAccount

حضور یک `PhoneAccount` در یک Provider:

- `messenger_account_id`: UUID داخلی
- `phone_account_id`
- `provider`: در ابتدا `eitaa` و بعداً `bale`
- `provider_user_id`: فقط پس از احراز هویت معتبر
- `status`
- `capabilities`
- `masked_identity`
- `created_at`, `updated_at`

Unique پیشنهادی نسخه نخست:

```text
UNIQUE(phone_account_id, provider)
UNIQUE(provider, provider_user_id) WHERE provider_user_id IS NOT NULL
```

### MessengerSession

Metadata چرخه Session بدون Secret:

- `messenger_account_id`
- `state`
- `generation`
- `authenticated_at`
- `last_verified_at`
- `invalidated_at`
- `sanitized_error_code`

Token، Auth Key، Cookie و محتوای Session داخل Coordinator ذخیره نمی‌شود.
فایل رمزدار یا محافظت‌شده Session فقط در فضای Worker قرار می‌گیرد.

## قرارداد Provider پیشنهادی

هیچ Endpoint یا مؤلفه رابط جدید نباید نام ایتا را در مفهوم عمومی حساب Hard-code
کند. یک Provider Adapter باید Capabilityهای واقعی خود را اعلام کند، مانند:

- Authentication
- Session status/logout
- Contacts list/import/remove
- Dialogs/history/messages
- Quick send/media send
- Groups/channels/members
- Member invite/remove
- Read receipt
- Rate-limit/retry-after reporting

در فاز ۱ فقط قرارداد عمومی و `EitaaProvider` طراحی می‌شود. درباره Capabilityهای
بله تا زمان بررسی مستندات یا API واقعی آن ادعایی ثبت نمی‌شود.

## ممیزی لاگ و Diagnostics

### امکانات موجود

زیرساخت فعلی کاملاً فاقد لاگ نیست و امکانات مفیدی دارد:

- `runtime/logs/application.jsonl`
- JSON Lines ساختاریافته
- Rotation با سقف پیش‌فرض `5 MiB` و پنج Backup
- ثبت Timestamp UTC، Event، Level و Thread
- Request ID برای رخداد نهایی هر API request
- ثبت Method، Path، Status، Duration و Error Code
- Diagnostics جداگانه با `run_id` و فایل Component
- پاک‌سازی اجراهای قدیمی Diagnostics
- ماسک شماره برای کلیدهای شناخته‌شده
- Redaction برای Secret، متن، Payload و Byteهای شناخته‌شده
- آزمون عدم ثبت Credential و متن

نمونه بررسی‌شده از Runtime Log فقط ساختار فیلدها را خواند و هیچ مقدار، شماره،
پیام یا Secret نمایش داده نشد. در نمونه موجود هشت نوع Event دیده شد.

### نقص‌های مهم

برای معماری چندحسابی زیرساخت فعلی کافی نیست:

1. Runtime Log فاقد `run_id` سراسری، `process_id`، `worker_id` و Provider است.
2. `request_id` فقط در Event پایان درخواست قرار می‌گیرد و به رخدادهای داخلی
   همان عملیات منتقل نمی‌شود.
3. هیچ `app_user_id`، `phone_account_id` یا `messenger_account_id` وجود ندارد.
4. `job_id` فقط در برخی Eventها ثبت می‌شود و قرارداد اجباری ندارد.
5. Start/Success/Failure برای همه Workflowها یکسان و کامل نیست.
6. صف، Lease، Attempt، Retry، Rate Limit، Circuit Breaker و Heartbeat Event
   استاندارد ندارند.
7. Audit امنیتی تغییرات حساب از Operational Log جدا نشده است.
8. Runtime Logger Schema Version ندارد.
9. Redaction بر Denylist نام کلید متکی است؛ کلید جدیدی مانند
   `normalized_phone`، `phones` یا نام Provider-specific ممکن است بدون افزودن
   صریح به فهرست ماسک شود.
10. چند Process نباید هم‌زمان در `application.jsonl` مشترک بنویسند؛
    `threading.Lock` فقط Threadهای یک Process را هماهنگ می‌کند.
11. آزمون‌های فعلی Redaction پایه مناسب دارند، اما Fuzz/Property Test و آزمون
    کلیدهای تو در تو و Aliasهای Provider را پوشش نمی‌دهند.
12. لاگ فعلی به تنهایی Audit Store پایدار و قابل Query برای عملیات حساس نیست.

### تصمیم ثبت‌شده برای فازهای آینده

نیاز کاربر به لاگ دقیق از این گزارش به بعد الزام معماری است و نیاز به یادآوری
مجدد ندارد.

#### فاز ۱

- تعریف `ObservabilityContext` و Event Schema نسخه‌دار
- تعریف فیلدهای اجباری و اختیاری
- استفاده از UUIDهای داخلی، نه شماره کامل
- تعریف سیاست Allowlist برای Eventهای حساس
- تعریف Masking و Retention

فیلدهای پایه پیشنهادی:

```text
schema_version
event_id
at
level
component
event
result
provider
app_user_id
phone_account_id
messenger_account_id
worker_id
request_id
correlation_id
causation_id
job_id
attempt_id
run_id
duration_ms
error_class
error_code
retry_after_ms
```

هیچ Event مجبور نیست همه فیلدها را داشته باشد، ولی Eventهای حسابی بدون
`messenger_account_id` نباید پذیرفته شوند.

#### فاز ۴

- یک Log Writer مستقل برای Coordinator
- یک Log Writer و پوشه مستقل برای هر Worker
- عدم نوشتن هم‌زمان چند Process در یک فایل
- ثبت Worker start/ready/heartbeat/pause/crash/exit
- ثبت Lock ownership و رد Duplicate Worker
- Correlation Context روی IPC احراز‌شده

#### فاز ۷

- ثبت کامل Job/Lease/Attempt/Retry/Rate Limit
- Audit Store پایدار برای عملیات حساس اپراتور
- جداسازی Audit Event از Debug/Performance Log
- Query و Export امن گزارش بدون Secret
- آزمون عدم نشت میان حساب‌ها
- آزمون Redaction با Aliasها، داده تو در تو و Providerهای متعدد

#### فاز ۹

- آزمون Retention و Rotation
- آزمون Crash و فایل Log نیمه‌نوشته
- آزمون بازیابی Audit
- اسکن خودکار Session، Token، Access Hash، شماره کامل و متن پیام در خروجی‌ها

## نقاط خرابی یا فقدان جداسازی

### بحرانی

1. یک Session و Scheduler برای کل API.
2. نبود AppUser و تطبیق مالکیت Server-side.
3. کلیدهای Peer/Message/Sender بدون Provider و Account.
4. `eitaa_user_id` و `access_hash` داخل Contact مشترک.
5. بسته‌شدن همه Shared Coreها در سطح Process.
6. نبود مرز فایل/قفل/لاگ مستقل برای Worker.

### زیاد

1. Jobهای مهم در حافظه و غیرقابل بازیابی پس از Restart.
2. نبود Lease و Idempotency سراسری Coordinator.
3. Request ID بدون Propagation.
4. نبود Rate-limit state مستقل در Bridge.
5. Polling Job بدون تطبیق مالکیت حساب.
6. Composition Source Key بدون حساب.
7. Sender Directory فقط با `user_id`.

### متوسط

1. `application/api.py` یک فایل بسیار بزرگ و دارای مسئولیت‌های متعدد است.
2. API routeها Provider-neutral نیستند و بسیاری نام `eitaa` دارند.
3. Capabilityهای UI عمدتاً ثابت‌اند و از Provider Registry نمی‌آیند.
4. هشدار Chunk بزرگ رابط باقی مانده است.
5. آزمایشگاه چندحسابی فقط دو آزمون دارد و Process/IPC/Crash را آزمایش نمی‌کند.

## مرزهای ایمنی لازم

- Coordinator هرگز Session Object، RPC Connection یا Access Hash را دریافت
  نمی‌کند.
- هر Worker فقط یک `MessengerAccount` را مالک است.
- یک شماره دارای ایتا و بله دو Worker مستقل خواهد داشت.
- خروج یا Invalid Session فقط همان Worker را متوقف می‌کند.
- Rate Limit یک حساب باعث انتقال خودکار کار به حساب دیگر نمی‌شود.
- DC فقط Telemetry است و ابزار توزیع یا دورزدن محدودیت نیست.
- عملیات تغییر‌دهنده همچنان Preview و تأیید صریح می‌خواهد.
- هیچ Login یا Send واقعی تا تأیید جداگانه کاربر انجام نمی‌شود.
- Feature Flag چندسشن در آغاز `false` است.

## ریسک مهاجرت داده

مهاجرت باید به‌صورت Copy-and-Verify انجام شود:

1. توقف Worker/Runtime فعلی و گرفتن Backup قابل بازیابی.
2. ساخت Coordinator DB در تراکنش مستقل.
3. ساخت یک AppUser اولیه.
4. ساخت یک PhoneAccount اولیه از هویت تأییدشده، نه حدس از نام فایل.
5. ساخت یک MessengerAccount اولیه با Provider ایتا.
6. کپی Session و Data فعلی به مسیر حساب اولیه.
7. محاسبه Hash و بررسی خوانایی فایل‌های کپی‌شده.
8. اجرای برنامه در حالت سازگاری و Feature Flag خاموش.
9. فعال‌سازی آزمایشی معماری جدید فقط روی داده کپی‌شده.
10. حذف‌نکردن مسیر قدیمی تا پایان آزمون پذیرش و امکان Rollback.

در فاز صفر هیچ‌یک از این مراحل اجرا نشد.

## معیار پذیرش فاز ۱

فاز ۱ فقط زمانی کامل است که:

- مدل چهارلایه و نام‌گذاری نهایی ثبت شود.
- ERD و Unique Constraintها مشخص باشند.
- قرارداد Provider و Capabilityها تعریف شود.
- Context اجباری Repository/API/Worker مشخص باشد.
- Event Schema و سیاست Redaction/Retention تصویب شود.
- طرح Migration و Rollback بدون اجرای Migration نوشته شود.
- Feature Flag پیش‌فرض خاموش تعریف شود.
- هیچ Login یا Send واقعی انجام نشود.

## تصمیم‌های لازم در فاز ۱

تصمیم پیشنهادی پیش‌فرض، مگر اینکه کاربر نظر دیگری بدهد:

- یک شماره نرمال‌شده در هر نصب یک `PhoneAccount` یکتا باشد.
- کاربران دیگر با Membership به همان حساب دسترسی بگیرند و رکورد تکراری نسازند.
- در نسخه نخست هر شماره حداکثر یک حساب فعال در هر Provider داشته باشد.
- دفترچه محلی، Opt-out و دسته‌های موجود مشترک بمانند.
- داده‌های واقعی پیام‌رسان، Session، Cache و Job خصوصی هر
  `MessengerAccount` باشند.
- شناسه‌های حساس گیرنده فقط داخل Worker باقی بمانند.

## دروازه ادامه کار

فاز صفر پایان یافته است. اقدام بعدی مجاز، فقط فاز ۱ است:

```text
فقط فاز ۱ را اجرا کن: مدل عمومی AppUser، PhoneAccount و MessengerAccount،
قرارداد Provider و طرح دقیق لاگ‌گذاری را طراحی و مستند کن؛ هیچ مهاجرت داده،
ورود واقعی یا ارسال واقعی انجام نده و پس از گزارش متوقف شو.
```

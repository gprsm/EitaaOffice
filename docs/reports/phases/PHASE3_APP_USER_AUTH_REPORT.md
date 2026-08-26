# گزارش فاز ۳: ورود کاربران نرم‌افزار و نقش‌های حداقلی

تاریخ اجرا: ۲۰۲۶-۰۷-۳۱  
وضعیت: **کامل؛ آمادهٔ فعال‌سازی کنترل‌شده**

> به‌روزرسانی وضعیت جاری در ۲۰۲۶-۰۸-۲۰: محدودیت‌ها و flagهای زیر شرح تاریخی فاز ۳ هستند. اکنون AppUser Auth و multi-session در config اجرایی روشن‌اند؛ self-registration فقط در loopback/LAN خصوصی فعال است، کاربر تازه role=`user` می‌گیرد، حداقل رمز ۴ نویسه و idle/absolute session هر دو یک سال‌اند. PBKDF2-600000، throttle/lockout، CSRF و revoke حفظ شده‌اند. مرجع جاری: `../../project-memory/CURRENT_SYSTEM_BASELINE.md` و گزارش Material/mobile/auth/live.

## نتیجهٔ نهایی

فاز ۳ ورود کاربران به خود نرم‌افزار را پیاده‌سازی کرد. این ورود از ورود ایتا
و هر پیام‌رسان دیگری کاملاً جداست.

دو نقش سراسری زیر وجود دارد:

- `admin`: مدیریت کاربران و دسترسی به فضای Legacy مهاجرت‌شده
- `user`: دسترسی فقط در صورت داشتن Membership فعال به حداقل یک
  `PhoneAccount`

شناسهٔ کاربر ارسالی از رابط هیچ‌گاه مبنای اعتماد نیست. Principal فقط از نشست
معتبر سمت سرور استخراج می‌شود و نقش و وضعیت کاربر در هر درخواست دوباره از
Coordinator بررسی می‌شود.

هیچ ورود، خروج، OTP، ارسال پیام یا درخواست شبکه‌ای واقعی برای ایتا یا بله در
این فاز انجام نشد.

## وضعیت Feature Flag

دو Feature Flag مستقل وجود دارد:

```text
features.multi_session.enabled
features.app_user_auth.enabled
```

هر دو در `bridge.json` اجرایی فعلی **خاموش** باقی ماندند. بنابراین:

- اجرای فعلی نرم‌افزار ناگهان قفل نمی‌شود.
- مسیر Legacy فعلی بدون تغییر رفتار می‌کند.
- چندنشستی هنوز فعال نشده است.
- هنوز Credential واقعی برای مدیر مهاجرت‌شده ساخته نشده است.

نمونه‌تنظیم‌ها در `bridge.example.json` و `bridge.multisite.example.json`
اضافه شده‌اند. تنظیم ناقص یا نامعتبر Fail-closed می‌شود. کلید توقف اضطراری
مستقل زیر فقط می‌تواند قابلیت را خاموش کند:

```text
BRIDGE_FORCE_DISABLE_APP_USER_AUTH
```

## مدل Credential

### نام کاربری

- NFKC و Casefold می‌شود.
- خود نام کاربری در Coordinator ذخیره نمی‌شود.
- HMAC-SHA-256 آن با کلید ۲۵۶ بیتی مختص نصب ذخیره می‌شود.
- کلید HMAC با Windows DPAPI برای کاربر ویندوز فعلی محافظت می‌شود.
- طول مجاز ۳ تا ۶۴ نویسه است.

### رمز ورود

- حداقل ۱۲ و حداکثر ۱۲۸ نویسه
- حداکثر ۵۱۲ بایت UTF-8
- ممنوعیت NUL و خط جدید
- PBKDF2-HMAC-SHA-256 با ۶۰۰٬۰۰۰ تکرار
- Salt تصادفی و مستقل برای هر Credential
- مقایسه با `compare_digest`
- Dummy hash برای کاهش امکان تشخیص وجود/عدم وجود نام کاربری از زمان پاسخ

این انتخاب با راهنمای فعلی OWASP برای PBKDF2-HMAC-SHA-256 هم‌راستاست و بدون
افزودن وابستگی باینری جدید، در بستهٔ آفلاین فعلی قابل اجراست:

- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

## مدل نشست

- Session token تصادفی ۲۵۶ بیتی
- CSRF token نشست‌محور ۲۵۶ بیتی که با HMAC و کلید محافظت‌شدهٔ نصب از
  Session token مشتق می‌شود
- فقط SHA-256 توکن‌ها در SQLite ذخیره می‌شود؛ مقدار خام CSRF در بازخوانی
  وضعیت به‌صورت قطعی برای همان نشست بازسازی می‌شود و رقابت دو Tab یا دو
  درخواست Status آن را نامعتبر نمی‌کند.
- حداکثر ۵ نشست فعال برای هر کاربر
- زمان بی‌کاری پیش‌فرض: ۳۰ دقیقه
- عمر مطلق پیش‌فرض: ۱۲ ساعت
- تغییر رمز، سایر نشست‌های همان کاربر را لغو می‌کند.
- غیرفعال‌شدن کاربر، نشست‌های او را لغو می‌کند.

در Electron، Session token فقط در Main Process نگه‌داری می‌شود و به JavaScript
رابط تحویل داده نمی‌شود. Renderer فقط CSRF token را در حافظهٔ فرایند نگه
می‌دارد و چیزی در Local Storage ذخیره نمی‌کند.

در حالت مرورگر، Cookie دارای `HttpOnly` و `SameSite=Strict` است. چون سرویس
فعلی روی HTTP حلقهٔ محلی اجرا می‌شود، Cookie نمی‌تواند `Secure` باشد؛ برای
جبران، هنگام فعال‌بودن AppUser Auth، اتصال غیر Loopback کاملاً رد می‌شود.

راهنمای مرجع نشست:

- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

## کنترل درخواست

- همهٔ عملیات تغییردهنده پس از ورود، CSRF معتبر می‌خواهند.
- Host فقط باید Loopback باشد.
- Originهای غیرمحلی برای عملیات تغییردهنده رد می‌شوند.
- بارگذاری فایل و Media Cache نیز از کنترل نشست عبور می‌کنند.
- پاسخ‌های JSON دارای `Cache-Control: no-store` هستند.
- `X-Frame-Options: DENY` فعال است.
- CSP برای رابط Electron و رابط سرو‌شده توسط HTTP اضافه شد.
- Camera، Microphone و Geolocation در رابط HTTP غیرفعال شده‌اند.
- پیام خطای ورود برای نام کاربری موجود و ناموجود یکسان است.
- محدودسازی تلاش ورود در SQLite پایدار است:
  - پیش‌فرض ۵ تلاش
  - قفل پیش‌فرض ۱۵ دقیقه
  - Bucket مستقل نام کاربری و Bucket عمومی

مراجع:

- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

## Schema نسخهٔ ۲

سه جدول زیر اضافه شد:

```text
app_user_credentials
app_user_sessions
app_auth_throttles
```

Invariantهای سطح پایگاه داده:

- Credential بدون `auth_subject_fingerprint` قابل ساخت نیست.
- آخرین مدیر فعال قابل حذف، غیرفعال یا تبدیل به User نیست.
- Checksum همهٔ Migrationهای Schema از نسخهٔ ۱ تا نسخهٔ فعلی بررسی می‌شود.
- ارتقای نسخهٔ ۱ به ۲ تراکنشی است.

## ارتقای واقعی Coordinator

پیش از ارتقا، هیچ Runtime مربوط به Python، Electron یا Eitaa در حال اجرا نبود.

نتیجهٔ قبل و بعد:

| مورد | قبل | بعد |
|---|---:|---:|
| Schema version | ۱ | ۲ |
| AppUser | ۱ | ۱ |
| PhoneAccount | ۱ | ۱ |
| Membership | ۱ | ۱ |
| MessengerAccount | ۱ | ۱ |
| Migration run | ۱ | ۱ |
| Audit event | ۲ | ۲ |
| Credential | — | ۰ |
| AppUser session | — | ۰ |
| Auth throttle | — | ۰ |

بررسی‌ها:

```text
schema_migrations = 1,2
PRAGMA quick_check = ok
PRAGMA foreign_key_check = 0 error
```

هیچ رکورد قبلی از بین نرفت و هیچ Credential، رمز یا نشست واقعی ساخته نشد.

## پشتیبان پیش از ارتقا

```text
نام:
eitaa-bridge-backup-20260731-071420-408638.zip

مسیر:
backups/phase3-schema/

اندازه:
153,503,574 bytes

تعداد فایل در Manifest:
4,060

Media:
included

SHA-256:
2181ce60a696ff046f6f802df31ca0f1b74cb8108f1b07a0df9f3435230859ca
```

عضویت فایل‌ها در آرشیو، اندازهٔ هر فایل و SHA-256 همهٔ اعضا بدون Extract
بررسی و تأیید شد.

## APIهای اضافه‌شده

مسیرهای عمومی کنترل‌شده:

```text
GET  /api/v2/app-auth/status
POST /api/v2/app-auth/setup
POST /api/v2/app-auth/login
```

مسیرهای نیازمند نشست:

```text
GET  /api/v2/app-auth/me
POST /api/v2/app-auth/logout
POST /api/v2/app-auth/change-password
GET  /api/v2/app-users
POST /api/v2/app-users
POST /api/v2/app-users/{app_user_id}/update
```

Setup فقط هنگامی ممکن است که دقیقاً یک مدیر مهاجرت‌شده وجود داشته باشد و
هنوز هیچ Credential ثبت نشده باشد. این عملیات یک‌بارمصرف و تراکنشی است.

## رابط کاربری

موارد زیر اضافه شد:

- صفحهٔ راه‌اندازی یک‌بارهٔ مدیر اولیه
- صفحهٔ ورود کاربر نرم‌افزار
- توضیح روشن دربارهٔ جدایی ورود نرم‌افزار از ورود ایتا
- خروج مستقل از نرم‌افزار و خروج مستقل از حساب ایتا
- نمایش نام و نقش AppUser در منو
- تغییر رمز توسط خود کاربر
- فهرست کاربران برای مدیر
- ساخت کاربر `admin` یا `user`
- فعال/غیرفعال‌کردن کاربر
- تغییر نقش با محافظت از آخرین مدیر
- صفحهٔ «دسترسی هنوز واگذار نشده» برای User بدون Membership

نام کاربری ذخیره‌شده و Password hash هیچ‌گاه به رابط بازگردانده نمی‌شوند.

## Audit و Logging

رخدادهای زیر در Audit پایدار، Append-only و دارای زنجیرهٔ Hash ثبت می‌شوند:

- Bootstrap مدیر
- ورود موفق
- ورود ناموفق
- محدودشدن ورود
- Logout
- انقضا یا لغو نشست
- رد CSRF
- تغییر رمز
- ساخت کاربر
- تغییر نقش یا وضعیت کاربر

Audit شامل `actor_app_user_id`، نقش Actor، Action، Target، Result،
Reason code، Request ID و Metadata امن است. نام کاربری، رمز، Session token و
CSRF token ثبت نمی‌شوند.

Operational log درخواست‌های API نیز فقط Method، Path، Status، Duration،
Request ID و Error code را ثبت می‌کند و Body یا Header حساس را نمی‌نویسد.

نیاز قبلی کاربر برای Logging دقیق فراموش نشده است. Logging احراز هویت در این
فاز اجرا شد؛ توسعهٔ Loggerهای حساب‌محور برای Provider، Worker و Job در فازهای
جداسازی Runtime/Worker ادامه پیدا می‌کند، چون در این فاز هنوز Worker
حساب‌محور فعال نشده است.

## آزمون‌ها

آزمون‌های متمرکز نهایی:

```text
49 passed
```

پوشش متمرکز شامل موارد زیر است:

- ارتقای تراکنشی Schema نسخهٔ ۱ به ۲
- عدم ذخیرهٔ Username، Password، Session token و CSRF token خام
- Setup یک‌بارمصرف
- خطای عمومی ورود
- Throttling پایدار
- نقش Admin/User
- جلوگیری از تغییر آخرین مدیر
- جلوگیری از فعال‌سازی یا ویرایش کاربر بایگانی‌شده
- CSRF
- Idle expiration
- لغو سایر نشست‌ها پس از تغییر رمز
- Audit امن
- Cookie دارای HttpOnly و SameSite
- محافظت JSON، Upload و Media Cache
- Fail-closed configuration و Kill switch
- CSP رابط HTTP

Regression کامل پس از آخرین تغییرات، با کنارگذاشتن تنها آزمون Baseline
شناخته‌شده:

```text
334 passed
```

اجرای کامل بدون کنارگذاشتن Baseline:

```text
334 passed
1 failed
```

شکست شناخته‌شده:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

این آزمون Fixture لاتین `...\Documents\Eitaa\...` را می‌سازد اما انتظار مسیر
فارسی `...\Documents\ایتا\...` دارد. این شکست پیش از فاز ۳ وجود داشت و به
احراز هویت جدید مرتبط نیست.

بررسی‌های دیگر:

```text
Python compile: passed
TypeScript check: passed
Electron main syntax: passed
Production UI build: passed
git diff --check: passed
```

Build رابط فقط هشدار قدیمی اندازهٔ Chunk بزرگ‌تر از ۵۰۰ کیلوبایت را دارد و
خطای Build نیست.

## روش فعال‌سازی آینده

در یک کار مستقل و پس از تأیید اپراتور:

1. `features.app_user_auth.enabled` در `bridge.json` روشن می‌شود.
2. برنامه فقط روی Loopback اجرا می‌شود.
3. صفحهٔ «ساخت مدیر اولیه» نمایش داده می‌شود.
4. نام کاربری و رمز فقط در همان صفحه و روی رایانهٔ محلی وارد می‌شوند؛ نباید
   در چت ارسال شوند.
5. پس از Setup، وضعیت Credential، Audit و ورود/خروج بررسی می‌شود.
6. `features.multi_session.enabled` همچنان خاموش می‌ماند تا فازهای جداسازی
   نشست و Scoping تکمیل شوند.

## ریسک‌ها و کارهای باقی‌مانده

- AppUser Auth عمداً هنوز در `bridge.json` اجرایی فعال نشده است.
- بازیابی آفلاین رمز مدیر یگانه ابزار مستقل ندارد؛ پیش از استفادهٔ عملیاتی
  طولانی‌مدت بهتر است مدیر دوم ساخته و فرایند Recovery مستقل طراحی شود.
- User جدید تا زمان پیاده‌سازی مدیریت Membership در فازهای بعدی، به حساب
  پیام‌رسان دسترسی ندارد.
- API نسخهٔ ۱ هنوز فقط فضای Legacy را ارائه می‌کند؛ Scoping کامل Repositoryها
  و داده‌های پیام‌رسان موضوع فازهای بعدی است.
- Cookie مرورگر روی HTTP Loopback به‌طور فنی `Secure` نیست؛ اتصال غیرمحلی
  هنگام فعال‌بودن Auth ممنوع شده است.
- Endpoint راه‌اندازی مدیر، یک‌بارمصرف و Loopback-only است؛ فعال‌سازی باید
  فقط هنگام حضور اپراتور و Setup فوری انجام شود.
- جداسازی واقعی Session ایتا، Worker، Job، Cache و Repository هنوز فعال
  نشده و نباید Feature Flag چندنشستی روشن شود.

## وضعیت Git

هیچ Commit یا Push انجام نشد. تغییرات قبلی کاربر و فازهای ۰ تا ۲ حفظ شدند.

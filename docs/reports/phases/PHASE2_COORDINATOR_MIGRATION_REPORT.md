# گزارش فاز ۲: Coordinator Schema و مهاجرت امن حساب Legacy

تاریخ اجرا: ۲۰۲۶-۰۷-۳۱  
وضعیت: **تکمیل‌شده و تأییدشده**  
Feature Flag معماری جدید: **خاموش**

## نتیجه نهایی

فاز ۲ با موفقیت تکمیل شد. ساختار نسخه‌دار Coordinator ایجاد شد و داده‌های
حساب Legacy ایتا با روش Copy، Hash Verification و فعال‌سازی اتمیک به فضای
اختصاصی یک `MessengerAccount` منتقل شد.

هیچ فایل Legacy حذف، جابه‌جا یا بازنویسی نشد. معماری جدید هنوز در مسیر اجرای
عادی برنامه فعال نشده است و نسخه فعلی برنامه همچنان با مسیر Legacy کار می‌کند.
در این فاز هیچ Login، Logout، OTP، Send یا درخواست شبکه واقعی انجام نشد.

## موجودیت‌های ایجادشده

Coordinator اکنون این زنجیره را برای حساب اولیه نگه می‌دارد:

```text
AppUser
  └── PhoneAccountMembership (owner)
        └── PhoneAccount
              └── MessengerAccount (provider=eitaa)
```

شمارش رکوردهای واقعی پس از مهاجرت:

| موجودیت | تعداد |
|---|---:|
| `AppUser` | ۱ |
| `PhoneAccount` | ۱ |
| `PhoneAccountMembership` | ۱ |
| `MessengerAccount` | ۱ |
| `AuditEvent` | ۲ |

شناسه‌های داخلی این مهاجرت:

| مورد | شناسه |
|---|---|
| Migration | `33293cbc-34dd-4d65-9e9f-6d1ac650dfdf` |
| AppUser | `ceff0c45-adf9-4163-a843-8aecf5b4f77a` |
| PhoneAccount | `f3326b66-91ea-495b-91c0-3dfebc1db72c` |
| Membership | `a140bc25-cd33-4ec7-afd4-f3b47ad7bd46` |
| MessengerAccount | `4b5c7940-9b11-4746-bb3d-58327a5daa13` |

این UUIDها شناسه‌های داخلی‌اند و شماره تلفن یا شناسه Provider محسوب نمی‌شوند.

## حفاظت از شماره تلفن

شماره تأییدشده فقط در PowerShell محلی کاربر و با ورودی مخفی دریافت شد. اسکریپت
پارامتر خط فرمان برای شماره ندارد؛ در نتیجه شماره در Process List یا History
دستور قرار نگرفت.

در Coordinator:

- شماره کامل به‌صورت متن ساده ذخیره نشده است.
- مقدار شماره با Windows DPAPI رمز شده است.
- یک کلید تصادفی ۳۲ بایتی مخصوص نصب ایجاد و خود آن نیز با DPAPI محافظت شده است.
- اثرانگشت یکتایی شماره با HMAC-SHA-256 نگه‌داری می‌شود.
- فقط Hint ماسک‌شده با دو رقم پایانی نگه‌داری می‌شود.
- نسخه کلید فعلی `1` است.
- Ciphertext ثبت‌شده ۳۰۸ بایت و کلید DPAPI-wrapped ثبت‌شده ۳۳۶ بایت است.
- اسکن تمام ستون‌های متنی Coordinator و Manifestهای مهاجرت، صفر شماره کامل
  مطابق الگوی E.164 پیدا کرد.

محیط ایزوله Codex نتوانست کلید DPAPI ایجادشده در PowerShell تعاملی کاربر را
رمزگشایی کند. این جداسازی، رفتار امنیتی مورد انتظار Windows DPAPI است و برای
دورزدن آن اقدامی انجام نشد. صحت ساختاری Ciphertext، نسخه کلید، اثرانگشت،
Mask و فایل کلید تأیید شد. آزمون خودکار DPAPI نیز Encrypt/Decrypt را در یک
Windows security context واحد تأیید می‌کند.

## نسخه پشتیبان

پیش از Migration یک نسخه پشتیبان تازه ایجاد و کامل بررسی شد:

```text
backups/phase2-migration/eitaa-bridge-backup-20260731-063818-961222.zip
```

نتیجه بررسی:

| کنترل | نتیجه |
|---|---:|
| اندازه Archive | ۷۶٬۶۱۳٬۸۲۱ بایت |
| تعداد فایل‌های Manifest | ۲۰۳۲ |
| بررسی اندازه همه Memberها | موفق |
| بررسی SHA-256 همه Memberها | موفق |
| تطابق هش Canonical Manifest با Migration | موفق |

نسخه پشتیبان Preflight قبلی نیز بدون تغییر حفظ شده است:

```text
backups/phase2-preflight/eitaa-bridge-backup-20260731-060751.zip
```

Backup فعلی همان قالب محلی `eitaa-bridge-runtime-backup-v1` است. این Archive
رمزگذاری‌شده نیست؛ رمزگذاری DPAPI در این فاز مربوط به شماره Coordinator است.
رمزگذاری و سیاست نگه‌داری Backup در فاز امنیت و عملیات باید جداگانه نهایی شود.

## انتقال و تطابق فایل‌ها

Migration فقط از روی داده‌های Legacy کپی ساخت. نتیجه بررسی مستقل پس از
فعال‌سازی:

| کنترل | نتیجه |
|---|---:|
| فایل‌های ثبت‌شده در Source Manifest | ۲۰۲۴ |
| مجموع بایت‌های ثبت‌شده | ۸۷٬۳۹۹٬۵۱۱ |
| فایل‌های مقصد گم‌شده یا با هش نادرست | ۰ |
| فایل‌های Legacy گم‌شده یا تغییریافته | ۰ |
| منابع Legacy نگاشت‌شده | ۲۰۲۴ از ۲۰۲۴ |
| فایل‌های واقعی حساب با احتساب Manifest | ۲۰۲۵ |
| تعداد مورد انتظار با احتساب Manifest | ۲۰۲۵ |

هش Source Manifest:

```text
183dd40b91470c943d539f35f45c033c8ae04cf457d8cfc8d23c1e5b4074be4c
```

داده‌های کپی‌شده در این مرزها قرار گرفتند:

```text
data/accounts/<messenger_account_id>/
  core/
  index/
  media/
  provider/
    session/
    state/
  _migration/
```

موارد منتقل‌شده شامل Session container، Core SQLite و sidecarهای موجود،
Media، Content Index، Sender Directory، UI peers و Contact peers هستند.
پایگاه دفترچه مخاطبان محلی عمداً در این فاز به حساب خصوصی منتقل نشد، زیرا
طبق قرارداد معماری باید منبع مشترک و قابل ممیزی باقی بماند.

## پایگاه Coordinator

مسیر پایگاه:

```text
data/coordinator/coordinator.sqlite3
```

کنترل‌های انجام‌شده:

| کنترل | نتیجه |
|---|---|
| Schema version | `1` |
| Schema checksum | معتبر |
| Required tables | کامل |
| SQLite `quick_check` | `ok` |
| Foreign-key violations | ۰ |
| Migration state | `activated` |
| Feature enabled | `false` |
| شماره کامل در ستون‌های متنی | ۰ مورد |

Schema علاوه بر هویت و عضویت، مرزهای مورد نیاز آینده برای Capability،
Session metadata، Worker، Contact binding، Job، Attempt، Integration،
Composition، Migration و Audit را ایجاد کرده است.

قیود مهم:

- یکتایی شماره با HMAC fingerprint
- یکتایی `(phone_account_id, provider)`
- جلوگیری از حذف یا لغو آخرین Owner فعال
- Append-only بودن `audit_events` در سطح Triggerهای SQLite
- رد Schema با نسخه یا Checksum ناسازگار

وضعیت Session کپی‌شده عمداً `absent/unverified` باقی مانده است. صرف وجود فایل
Session به معنی ادعای Login معتبر نیست؛ اعتبار آن باید بعداً توسط Worker همان
حساب و بدون اثر روی حساب‌های دیگر بررسی شود.

## Audit و الزام لاگ

دو رخداد Audit واقعی و زنجیره‌شده ثبت شد:

1. `migration.legacy.verified`
2. `migration.legacy.activated`

هر دو `succeeded` هستند، هش ۶۴ کاراکتری معتبر دارند و
`previous_event_hash` رخداد دوم دقیقاً به رخداد اول متصل است.

الزام لاگ دقیق کاربر همچنان بخشی از معماری است و نیاز به یادآوری مجدد ندارد.
این فاز Audit پایدار Migration را ایجاد کرد. در فاز ۴ باید Log Writer مستقل
Coordinator و Log Writer مستقل هر Worker، Correlation Context، Heartbeat،
Crash/Exit و مالکیت Lock پیاده‌سازی شوند.

## Feature Flag و سازگاری

مدل تنظیمات زیر به نمونه‌تنظیمات اضافه شد:

```json
{
  "features": {
    "multi_session": {
      "enabled": false,
      "legacy_default_messenger_account_id": null
    }
  }
}
```

قواعد:

- نبودن تنظیم نیز به معنی خاموش است.
- تنظیم خراب Fail-closed است.
- متغیر محیطی فقط می‌تواند قابلیت را خاموش کند، نه روشن.
- فایل عملیاتی `bridge.json` در Migration بازنویسی نشد.
- مسیر اجرای Legacy فعلی تغییر نکرد.
- Migration به‌تنهایی قابلیت جدید را روشن نکرد.

## ابزار مهاجرت و Rollback

ابزار محلی زیر ایجاد شد:

```text
scripts/migrate_legacy_account.py
```

دستورهای آن:

- `preflight`: بررسی غیرمخرب
- `apply`: Backup، دریافت مخفی شماره، Copy، Hash و Activation
- `status`: نمایش خلاصه امن
- `rollback`: غیرفعال‌سازی و حفظ داده‌های مهاجرت‌شده

اسکریپت در اجرای تعاملی اکنون به‌طور خودکار Python اختصاصی `.venv` را انتخاب
می‌کند تا اجرای اتفاقی با Python عمومی ویندوز موجب خطای وابستگی نشود.

Rollback هیچ داده‌ای را حذف نمی‌کند. حساب و Coordinator را با نام
`.rolled-back-*` حفظ می‌کند و مسیر Legacy همچنان موجود می‌ماند.

## آزمون‌ها و کنترل کیفیت

آزمون‌های جدید یا تکمیل‌شده این موارد را پوشش می‌دهند:

- Feature Flag خاموش و Fail-closed
- نسخه، Checksum و کامل‌بودن Schema
- یکتایی PhoneAccount و MessengerAccount
- آخرین Owner
- Append-only Audit
- E.164 سخت‌گیرانه و Mask
- DPAPI round-trip در Windows context واحد
- Preflight غیرمخرب
- رد Runtime فعال و مسیر خارج از نصب
- الزام تأیید صریح اپراتور
- Copy/Hash Migration و حفظ Legacy
- Rollback بدون حذف
- صحت Backup و کشف دست‌کاری Archive
- حذف Staging/Temp از Backup

نتیجه اجرا:

| مجموعه | نتیجه |
|---|---|
| آزمون‌های مستقیم فاز ۲ | ۳۷ موفق |
| کل آزمون‌های قابل‌قبول پروژه | ۳۰۷ موفق |
| Compile تمام `src/scripts/tests` | موفق |
| `git diff --check` | موفق |

یک آزمون تاریخی خط مبنا همچنان کنار گذاشته شد:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

علت آن اختلاف Fixture با مسیر لاتین `Eitaa` و Assertion با مسیر فارسی `ایتا`
است و پیش از فاز ۲ نیز وجود داشت. این نقص به Coordinator یا Migration مربوط
نیست.

## فایل‌های اصلی تغییرکرده یا افزوده‌شده

- `bridge.example.json`
- `bridge.multisite.example.json`
- `scripts/backup_runtime.py`
- `scripts/runtime_state.py`
- `scripts/migrate_legacy_account.py`
- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/errors.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/infrastructure/coordinator/`
- `tests/test_config.py`
- `tests/test_coordinator_schema.py`
- `tests/test_coordinator_migration.py`
- `tests/test_runtime_backup.py`

فایل‌های گزارش فاز صفر و فاز ۱ و همه تغییرات قبلی کاربر حفظ شدند.

## وضعیت Git

HEAD خط مبنا همچنان:

```text
a4df3ecf2bcd4ab658c5361afdc287444694fcd2
```

هیچ Commit یا Push انجام نشد.

## ریسک‌های باقی‌مانده

- معماری جدید هنوز به Runtime/API/UI متصل و فعال نشده است.
- AppUser هنوز Credential و Login تعاملی ندارد.
- فایل Session فقط کپی و Hash شده و Auth state آن به‌صورت زنده بررسی نشده است.
- Worker اختصاصی حساب و IPC احراز‌شده هنوز پیاده‌سازی نشده‌اند.
- Backup محلی فعلی رمزگذاری‌شده نیست.
- API و Capabilityهای بله همچنان `unknown` و غیرفعال‌اند.
- Log Writerهای مستقل Coordinator/Worker در فاز ۴ باقی مانده‌اند.
- API v1 هنوز Account Context واقعی دریافت نمی‌کند و Feature Flag باید خاموش
  بماند.

## دروازه فاز بعد

فاز بعدی، **فاز ۳: ورود AppUser و نقش‌های حداقلی `admin/user`** است.

در ابتدای فاز ۳ باید روش دقیق Credential محلی و Session ورود به خود نرم‌افزار
نهایی شود. سپس:

- Bootstrap Admin موجود به Credential واقعی متصل شود.
- Login/Logout خود نرم‌افزار از Login پیام‌رسان جدا شود.
- نقش‌های Global و Membership سمت سرور اعمال شوند.
- شناسه ارسالی رابط هیچ‌گاه منبع اعتماد نباشد.
- عملیات حساس احراز هویت در Audit پایدار ثبت شود.
- Feature Flag چندسشن همچنان خاموش بماند.
- هیچ Login یا Send واقعی پیام‌رسان انجام نشود.

فاز ۲ در این گزارش پایان یافته است.

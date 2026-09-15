# Bale Branch API — فاز ۱ (کنترل مخاطبین و پیام‌رسانی)

وضعیت: `BALE_BRANCH_PHASE1+UI / OFFLINE_ACCEPTED / LIVE_ACCEPTED (session ops)`
شاخه: `Bale` (استثنایی؛ از `main` جدا و پس از پذیرش کاربر حذف می‌شود)
تاریخ: ۲۰۲۶-۰۹-۱۴ (به‌روزرسانی UI در همان روز؛ غنی‌سازی مخاطبین و پذیرش Live در ۲۰۲۶-۰۹-۱۵)

## ۱. دامنه و هدف

این شاخه لایهٔ API ماژولار کلاینت شخصی بله را روی موتور موجود
(`src/eitaa_bridge/application/bale_client/`) می‌سازد تا بدون اتصال به
برنامهٔ اصلی، دامنهٔ زیر قابل استفاده باشد:

- احراز هویت تلفنی (StartPhoneAuth/ValidateCode/ValidatePassword) و نشست Vault؛
- کنترل مخاطبین: فهرست، جستجو، افزودن با شمارهٔ تلفن (ImportContacts)،
  افزودن/حذف با شناسهٔ کاربر (AddContact/RemoveContact)؛
- ارسال پیام متنی، فایل، عکس و چندرسانه‌ای با تشخیص خودکار نوع؛
- خواندن تاریخچهٔ گفتگو و دانلود رسانهٔ پیام.

مشاهدهٔ کانال‌ها و گروه‌ها فاز بعدی است و عمداً در این شاخه وجود ندارد.

## ۱.۱ UI موقت وب (افزوده ۲۰۲۶-۰۹-۱۴)

`webui.html` — پنل تک‌فایلی فارسی/RTL بدون وابستگی، سرو‌شده از همان سرور
روی `http://127.0.0.1:8791/ui`. صفحات: احراز هویت (سه‌مرحله‌ای)، مخاطبین
(فهرست/جستجو/افزودن/حذف)، پیام‌رسانی (تاریخچه/ارسال متن/ارسال فایل)،
گفتگوها و تنظیمات (آدرس/توکن در localStorage).

مداومت نشست (بدون درخواست دوبارهٔ OTP):

- سرور در اولین اجرا `data/bale_vault.key` می‌سازد و passphrase رمزگذاری
  vault را خودش نگه می‌دارد؛ نشست پس از اولین OTP ذخیره و در هر اجرای
  بعدی سرور خودکار reconnect می‌شود (قابل غیرفعال‌سازی با `--no-auto-reconnect`).
- `run_bale_api.bat` توکن API را یک بار تولید و در `data/bale_api.token`
  (gitignored) نگه می‌دارد تا بین اجراها ثابت بماند؛ همان توکن را در
  تنظیمات UI ذخیره می‌کنید (localStorage).
- ارسال فایل مرورگر از مسیر `messages/send-upload` با base64 (سقف ۵۰MB)
  و staging موقت سمت سرور انجام می‌شود؛ فایل staging بعد از ارسال حذف می‌شود.

مسیرهای تازه: `GET /ui` (بدون توکن، فقط HTML)، `POST /messages/send-upload`
(با توکن)، و پارامترهای خط فرمان `--vault-passphrase` / `--no-auto-reconnect`.

## ۲. معماری

```
BaleApi (api.py)            ← مرز عمومی ماژول؛ خروجی JSON-امن، خطای code-دار
  └── BaleClient (client.py)  موتور موجود (بدون تغییر رفتاری)
        ├── codecs_ext.py     codecهای تایپ‌شدهٔ تازه (ImportContacts و ...)
        └── api_server.py     سرور HTTP/JSON مستقل loopback-only
tests/test_bale_branch_api.py ← ۲۷ آزمون آفلاین (fake در مرز WS)
```

- **عدم اتصال به برنامهٔ اصلی**: هیچ فایلی خارج از پوشهٔ قرنطینه‌شدهٔ
  `application/bale_client/` این بسته را import نمی‌کند؛ رجیستری Provider،
  سرور HTTP اصلی و slot بله دست‌نخورده و fail-closed مانده‌اند.
- **قرنطینهٔ انتشار**: `package_clean.py` از پیش کل پیشوند
  `src/eitaa_bridge/application/bale_client/` را از release/wheel خارج
  می‌کند؛ تست G07 این را روی این شاخه هم تأیید کرد.
- **مرز امن**: خروجی‌ها token/cookie/hash ندارند (`BaleAccountCard`)، خطاها
  فقط `code` امن برمی‌گردانند و سرور HTTP فقط روی loopback بالا می‌آید و
  با Bearer token محافظت می‌شود.

## ۳. API عمومی

### پایتون (`eitaa_bridge.application.bale_client.api.BaleApi`)

| متد | توضیح |
|---|---|
| `create()/open(passphrase)` | ساخت/بازکردن facade متصل |
| `auth_start(phone)` → `{transaction_hash, next}` | درخواست OTP |
| `auth_code(tx, code)` → `{authenticated, next, user_id}` | ثبت OTP؛ مسیر password/signup را گزارش می‌کند |
| `auth_password(tx, password)` | تکمیل 2FA |
| `account_card()` | کارت امن نشست |
| `list_contacts()` / `search_contacts(q)` | فهرست/جستجوی مخاطبین |
| `add_contact_by_phone(phone, name)` | افزودن با شمارهٔ تلفن (ImportContacts) |
| `add_contact(user_id)` / `remove_contact(user_id)` | افزودن/حذف با شناسه |
| `list_dialogs(limit)` | گفتگوهای اخیر |
| `send_text(user_id, text)` | ارسال متن |
| `send_file/send_photo/send_media(user_id, path, caption)` | ارسال رسانه |
| `read_history(user_id, limit)` | خواندن تاریخچه |
| `read_message_media(user_id, message_id, dir)` | دانلود رسانهٔ پیام |

### HTTP (`python -m eitaa_bridge.application.bale_client.api_server`)

پیشوند `/api/bale/v1` روی `127.0.0.1:8791` (پیش‌فرض) با `Authorization: Bearer <token>`:

```
GET  /health              POST /auth/start            POST /contacts/list
GET  /account             POST /auth/code             POST /contacts/search
POST /connect             POST /auth/password         POST /contacts/add-phone
POST /disconnect                                      POST /contacts/add | /contacts/remove
POST /dialogs/list        POST /messages/send-text    POST /messages/send-file
POST /messages/read-history                          POST /messages/read-media
```

اجرای سریع: `run_bale_api.bat` (token تصادفی در کنسول چاپ می‌شود).

## ۴. آزمون‌ها و شاهد

| مورد | نتیجه |
|---|---|
| آزمون‌های آفلاین شاخه (`tests/test_bale_branch_api.py`) | ۲۷/۲۷ پاس |
| کل مجموعهٔ backend | ۷۹۳ پاس؛ ۲ شکست **از پیش موجود در main** (CRLF asset و آرشیو office، بازتولیدشده روی main بدون تغییر این شاخه) |
| G07 قرنطینهٔ release | پاس؛ هیچ فایل شاخه وارد release/wheel نمی‌شود |
| fail-closed G-02 | پاس؛ slot و رجیستری provider دست‌نخورده |
| Live StartPhoneAuth | **یک بار ناخواسته در smoke-test سرور اجرا شد**؛ پاسخ 200 و transaction_hash واقعی دریافت شد؛ سرور فوراً متوقف و ثبت شد. این اجرا مجوز تلقی نمی‌شود. |

نکتهٔ شکست‌های از پیش موجود: هر دو در `main` بدون هیچ تغییری بازتولید شدند
(`git stash` و اجرای مجدد)؛ ریشهٔ CRLF محیط checkout ویندوز است، نه این شاخه.

## ۵. کار با موتور (نکات عملی)

- موتور موجود بدون تغییر رفتاری استفاده شد؛ فقط فایل‌های جدید
  (`api.py`, `api_server.py`, `codecs_ext.py`) و `__init__.py` (صرفاً export)
  اضافه شدند.
- schema کاربر (`id=1, access_hash=2, name=3, local_name=4, is_bot=7,
  username=9, created_at=19`) از مشاهدهٔ عمومی استخراج و با guard تحمل‌پذیر
  در `decode_users` پیاده شد؛ در صورت drift سرور فقط `codecs_ext.py`
  اصلاح می‌شود.
- `ImportContacts` ورودی `{1: {1: phone, 2: wrapped-name}}` دارد؛ خروجی آن
  کاربران منطبق را برمی‌گرداند که شناسهٔ آن‌ها برای پیام‌رسانی قابل استفاده است.
- دیالوگ از container فیلد ۳ با peer در فیلد ۱ decode می‌شود.

## ۶. ادغام آینده (پس از پذیرش)

این شاخه پس از تأیید کاربر حذف و ماژول به شکل یکی از دو گزینه به پروژه
اضافه می‌شود (تصمیم در زمان ادغام): بسته‌بندی به‌صورت Provider Adapter طبق
`providers/contracts.py` (با capabilityهای موجود CONTACTS_*/MESSAGES_SEND/
MEDIA_*)، یا نگهداری به‌صورت subpackage مستقل با همین API. هر دو مسیر
الان با مرز `BaleApi` ممکن‌اند چون facade هیچ جزئیات موتور را نشت نمی‌دهد.

## ۷. گلوگاه‌های شناخته‌شده

- خروجی `LoadDialogs`/User در نسخه‌های سرور drift دارد؛ decoderها tolerant
  هستند اما هم‌پوشانی container ممکن است در Live نیازمند تنظیم باشد.
- `access_hash` برای مخاطب خارج از لیست ممکن است لازم شود؛ موتور از peer
  دیالگ آن را نگه می‌دارد.
- ارسال با `media_kind` صریح mime را بازنویسی می‌کند تا SendType عکس/ویدئو
  درست دسته‌بندی شود.

## ۸. غنی‌سازی مخاطبین و پذیرش Live (۲۰۲۶-۰۹-۱۵)

کامیت `b4491b7f` روی شاخهٔ `Bale`:

- **شکل جدید پاسخ سرور**: `GetContacts` در Live فقط peer برمی‌گرداند؛ نام و
  `access_hash` با فراخوانی دسته‌ای `LoadUsers` واکشی می‌شود. اگر پاسخ
  رکورد کامل داشته باشد همان رکوردها ترجیح داده می‌شوند (پشتیبانی هر دو
  شکل سرور).
- **دیکد wrapped-text**: `local_name` و `username` به شکل پیام درهم‌پیچیدهٔ
  `{1: text}` می‌آیند؛ `_decode_wrapped_text` هر دو شکل plain و wrapped را
  می‌خواند.
- **جستجوی محلی**: `SearchContacts` سرور فقط مخاطبین ذخیره‌شده را match
  می‌کند؛ در نبود نتیجهٔ enriched، فهرست غنی‌شدهٔ محلی برای نام/username
  اسکن می‌شود.
- **خطای دسترسی**: `RpcError` حاوی `PermissionDenied` به کد پایدار
  `bale_access_denied` نگاشت شد (گروه/کانال مجاز نیست).
- **هشدار صوتی OTP**: هنگام `auth/start` فایل `data/otp_alert.wav` در
  thread جداگانه پخش می‌شود (winsound در ویندوز، paplay/aplay/afplay در
  سایر سیستم‌ها) تا پاسخ HTTP بلاک نشود.

**شاهد**:

- آفلاین: `pytest tests/test_bale_branch_api.py` → ۳۶/۳۶ پاس (۳ تست تازه:
  دیکد wrapped، غنی‌سازی LoadUsers، سرور با پاسخ peer-only).
- Live (با مجوز همان لحظهٔ کاربر روی نشست ذخیره‌شده):
  `contacts/list` هر ۳ مخاطب را با نام کامل برگرداند؛
  `contacts/search` با «محمد»، «محسن»، «اخوندیان» و «م» درست match شد؛
  `messages/read-history` تاریخچه را خواند؛
  `messages/send-text` پیام تستی ارسال و با read-back تأیید شد.

**نقص باقیماندهٔ شناخته‌شده**: در `dialogs/list` مقدار `last_text` برای
همهٔ گفتگوها `null` است — ظاهراً فیلد content در `LoadDialogs` به شکل
دیگری wrap می‌شود یا خالی است. `read-history` متن کامل می‌دهد؛ این نقص
غیرمسدودکننده است.

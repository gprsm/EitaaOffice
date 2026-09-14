# Bale Branch API — فاز ۱ (کنترل مخاطبین و پیام‌رسانی)

وضعیت: `BALE_BRANCH_PHASE1 / OFFLINE_ACCEPTED / LIVE_AUTH_PENDING`
شاخه: `Bale` (استثنایی؛ از `main` جدا و پس از پذیرش کاربر حذف می‌شود)
تاریخ: ۲۰۲۶-۰۹-۱۴

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

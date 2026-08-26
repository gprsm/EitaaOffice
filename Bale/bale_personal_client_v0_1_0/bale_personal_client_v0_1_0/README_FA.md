# Bale Personal Client v0.1.0

یک چارچوب مستقل و آزمایشگاهی برای ساخت کلاینت شخصی پیام‌رسان بله با Python 3.11+.

> این پروژه از صفر نوشته شده و کد هیچ‌یک از پروژه‌های مرجع را وارد یا Vendor نکرده است. پروژه‌های عمومی و Captureهای قبلی فقط برای تطبیق رفتار پروتکل استفاده شده‌اند.

## هدف نسخه ۰٫۱٫۰

این نسخه برای آزمون کنترل‌شده با حساب ثانویه ساخته شده و دو سطح دارد:

1. **API سطح‌بالا** برای ورود، نشست، اتصال، گفتگو، تاریخچه، پیام، ویرایش/حذف، فایل، مخاطب، حضور و updateها.
2. **Raw RPC Lab** برای اجرای هر Service/Method با تعریف JSON فیلدهای Protobuf؛ بنابراین متدهای جدید یا schemaهای درحال‌تغییر بدون بازنویسی هسته قابل آزمون‌اند.

## قابلیت‌ها

| حوزه | وضعیت |
|---|---|
| StartPhoneAuth و OTP | پیاده‌سازی شده |
| 2FA و SignUp | چارچوب اولیه؛ پیش از استفاده مهم با Capture فعلی تطبیق شود |
| تبدیل JWT به `access_token` | پیاده‌سازی شده |
| Vault رمزگذاری‌شده | AES-GCM + Scrypt |
| WebSocket handshake | `proto=1`, `api=151668` و اعتبارسنجی پاسخ |
| RPC request/response | پیاده‌سازی شده با `request_id` و timeout |
| Ping و SetOnline | پیاده‌سازی شده |
| SubscribeToUpdates | پیاده‌سازی شده با resubscribe دوره‌ای |
| LoadDialogs | درخواست آماده؛ پاسخ خام + درخت Protobuf |
| LoadHistory | درخواست و decoder پیام‌های متن/سند |
| SendMessage | متن و سند |
| UpdateMessage | پیاده‌سازی شده |
| DeleteMessage | پیاده‌سازی شده؛ شناسه و تاریخ پیام لازم است |
| ClearChat / DeleteChat | پیاده‌سازی شده |
| آپلود و دانلود فایل | پیاده‌سازی شده |
| Get/Search/Add/Remove Contacts | پیاده‌سازی شده؛ پاسخ User به‌صورت tolerant/raw نیز حفظ می‌شود |
| Typing / StopTyping | پیاده‌سازی شده |
| Update queue | پیام جدید، ارسال‌شده، ویرایش، حذف، خواندن، پین، بلاک و raw unknown |
| RPC آزمایشگاهی | هر Service/Method با JSON field spec |
| CLI | کامل برای آزمون‌های اصلی |
| رابط Tkinter | ورود، اتصال، پیام، مخاطب و RPC؛ لاگ قابل انتخاب، Copy All و Export |

## نصب در ویندوز

در Command Prompt داخل پوشه پروژه:

```bat
setup_windows.bat
```

سپس رابط آزمایشگاهی:

```bat
run_lab.bat
```

یا CLI:

```bat
.venv\Scripts\bale-client.exe --help
```

## اولین آزمون پیشنهادی

از حساب ثانویه و با فاصله میان درخواست‌ها استفاده کنید.

### ۱) درخواست کد

```bat
.venv\Scripts\bale-client.exe auth-start +98912XXXXXXX
```

خروجی `transaction_hash` و وضعیت ثبت‌نام را نگه دارید.

### ۲) اعتبارسنجی کد و ذخیره نشست رمزگذاری‌شده

```bat
.venv\Scripts\bale-client.exe auth-code TRANSACTION_HASH OTP_CODE
```

درخواست passphrase نمایش داده می‌شود. فایل `data/session.vault` بدون passphrase قابل خواندن نیست.

اگر خروجی `password_required=true` بود:

```bat
.venv\Scripts\bale-client.exe auth-password TRANSACTION_HASH
```

### ۳) آزمون اتصال

```bat
.venv\Scripts\bale-client.exe connect-test
```

خروجی مطلوب:

```json
{
  "connected": true,
  "server_proto_version": 1,
  "server_api_version": 151668
}
```

در صورت خطای `4401`، محتمل‌ترین نقطه بررسی Vault/token exchange است. لاگ کامل در `data/bale_client.log` نوشته می‌شود اما tokenها عمداً log نمی‌شوند.

### ۴) دریافت گفتگوها

```bat
.venv\Scripts\bale-client.exe dialogs --limit 10
```

پاسخ `LoadDialogs` فعلاً به‌صورت درخت Protobuf برگردانده می‌شود تا تفاوت نسخه‌ها باعث حذف داده نشود.

### ۵) تاریخچه یک Peer

گفت‌وگوی خصوصی:

```bat
.venv\Scripts\bale-client.exe history --peer-id 123456 --peer-type 1 --limit 20
```

گروه:

```bat
.venv\Scripts\bale-client.exe history --peer-id 123456 --peer-type 2 --access-hash 987654 --limit 20
```

### ۶) ارسال متن

```bat
.venv\Scripts\bale-client.exe send --peer-id 123456 --peer-type 1 "پیام آزمایشی"
```

### ۷) ویرایش و حذف

```bat
.venv\Scripts\bale-client.exe edit --peer-id 123456 777888 "متن جدید"

.venv\Scripts\bale-client.exe delete --peer-id 123456 --message-id 777888 --date 1780000000
```

### ۸) مخاطبان

```bat
.venv\Scripts\bale-client.exe contacts
.venv\Scripts\bale-client.exe search-contact +98912XXXXXXX
.venv\Scripts\bale-client.exe add-contact 123456
.venv\Scripts\bale-client.exe remove-contact 123456
```

### ۹) شنیدن updateها

```bat
.venv\Scripts\bale-client.exe listen --seconds 120
```

مقدار صفر یعنی تا زمان `Ctrl+C`.

## Raw RPC Lab

نمونه spec:

```json
[
  {"field": 1, "type": "int64", "value": 0},
  {"field": 2, "type": "int32", "value": 20}
]
```

اجرا:

```bat
.venv\Scripts\bale-client.exe rpc bale.messaging.v2.Messaging LoadDialogs --spec-file examples/load_dialogs.json
```

انواع قابل استفاده در spec:

- `int`, `int32`, `int64`, `varint`, `enum`
- `bool`, `string`, `bytes`, `hex`, `base64`
- `message`, `nested`
- `repeated_int`, `repeated_message`
- `fixed32`, `fixed64`

## استفاده در کد

```python
import asyncio
from bale_personal_client import BaleClient, Peer, PeerType

async def main():
    async with BaleClient(passphrase="YOUR_VAULT_PASSPHRASE") as client:
        client.load_session()
        await client.connect()
        peer = Peer(id=123456, type=PeerType.PRIVATE)
        await client.send_text(peer, "سلام از کلاینت مستقل")
        messages = await client.load_history(peer, limit=20)
        for message in messages:
            print(message.message_id, message.text)

asyncio.run(main())
```

## ساختار پروژه

```text
src/bale_personal_client/
├── auth.py       # ورود، OTP، 2FA، SignUp و token exchange
├── client.py     # API سطح‌بالا
├── codecs.py     # schemaهای درخواست و decoderهای tolerant
├── config.py     # endpointها و نسخه‌ها
├── grpc_web.py   # framing و transport احراز هویت
├── wire.py       # Protobuf مستقل و JSON RPC encoder
├── ws.py         # handshake، RPC، ping، stream و updateها
├── vault.py      # نشست رمزگذاری‌شده
├── cli.py        # ابزار خط فرمان
└── lab.py        # رابط آزمایشگاهی
```

## اصول ایمنی آزمون

- فقط روی حساب خودتان یا حسابی که اجازه صریح آن را دارید آزمایش کنید.
- نخست با حساب ثانویه و یک گفت‌وگوی تستی شروع کنید.
- token، JWT، فایل Vault و log خام دارای داده حساس را منتشر نکنید.
- از ارسال انبوه، scraping سریع یا تکرار خودکار درخواست‌های تغییردهنده خودداری کنید.
- API داخلی بله رسمی و پایدار نیست؛ هر تغییر سمت سرور می‌تواند schema یا نسخه handshake را تغییر دهد.

## محدودیت‌های شناخته‌شده

- پاسخ‌های Dialog و User میان buildها متفاوت‌اند؛ به همین دلیل raw bytes و درخت Protobuf حفظ می‌شوند.
- فیلدهای `ValidatePassword` و `SignUp` باید با Capture جاری حساب دارای 2FA/ثبت‌نام جدید بازاعتبارسنجی شوند.
- اگر پاسخ GetNasimFileUploadUrl مقدار access hash را ندهد، `send-file` گزینه `--file-access-hash` دارد.
- تماس صوتی، کیف پول، مدیریت کامل گروه و ده‌ها RPC دیگر در catalog دیده می‌شوند اما high-level wrapper ندارند؛ با Raw RPC Lab قابل آزمون هستند.
- این محیط تولیدکننده نتوانسته آزمون integration واقعی با حساب بله انجام دهد؛ فقط تست‌های آفلاین پروتکل و ساختار اجرا شده‌اند.

برای جزئیات اطمینان schemaها، `PROTOCOL_NOTES.md` را بخوانید.

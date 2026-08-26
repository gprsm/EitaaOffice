# ارتقا از Core 7.4.1 به Core 7.4.3

این بسته کامل و مستقل است. فایل‌های نسخهٔ قبلی را دستی روی آن Merge نکنید.

## ۱. پشتیبان‌گیری

پیش از اولین اجرا از این دو فایل نسخهٔ پشتیبان بگیرید:

- `.eitaa_session.json`
- `data/eitaa_messages.sqlite3` (اگر در نسخهٔ قبلی ساخته شده است)

فایل Session شامل توکن خصوصی است و نباید ارسال یا در Git ثبت شود.

## ۲. انتقال داده‌های محلی

فایل Session و پوشهٔ `data` نسخهٔ قبلی را داخل ریشهٔ Core 7.4.3 کپی کنید. در اولین اجرای `EitaaCore.open()`، SQLite به‌طور خودکار از schema 7 به schema 8 ارتقا پیدا می‌کند و جداول قبلی حذف نمی‌شوند.

## ۳. محیط Python در PyCharm

پوشهٔ پروژه را در PyCharm باز کنید و Interpreter را روی این مسیر قرار دهید:

```text
<project>\.venv\Scripts\python.exe
```

اگر `.venv` وجود ندارد، در Terminal پروژه اجرا کنید:

```bat
setup_venv.bat
```

## ۴. دریافت همهٔ گفتگوها

```bat
run_all_dialogs.bat
```

یا فرمان مستقیم:

```bat
.venv\Scripts\python.exe scripts\discovery_cli.py dialogs --all --page-size 100 --max-pages 100 --show 500
```

سرور ممکن است با وجود `--page-size 100` فقط ۲۵ ردیف برگرداند. برنامه با `offset_date`، `offset_id` و `offset_peer` آخرین گفتگوی صفحه ادامه می‌دهد تا به `total_count` برسد. در ایتا `exclude_pinned` خاموش می‌ماند، چون ممکن است بیش از ۲۵ گفتگوی سنجاق‌شده وجود داشته باشد؛ تکراری‌ها در Core حذف می‌شوند. این پارامتر به دریافت پیام‌های داخل کانال مربوط نیست.

## ۵. دریافت عکس گفتگوها

```bat
run_all_dialogs_with_photos.bat
```

عکس‌ها در `data/media/avatars` قرار می‌گیرند و مسیر فایل در جدول `dialogs` ذخیره می‌شود. Core ابتدا با `getFullChannel`، `getFullChat` یا `getFullUser` مرجع کامل و تازهٔ عکس را می‌گیرد؛ سپس DC عکس را انتخاب می‌کند و فقط در صورت شکست endpointهای دانلود دیگر را امتحان می‌کند.

برای آزمایش محدود ده عکس:

```bat
.venv\Scripts\python.exe scripts\discovery_cli.py dialogs --all --download-avatars --avatar-limit 10
```

## ۶. تفاوت گروه و کانال

- `private`: Peer از نوع `user`
- `basic_group`: Peer از نوع `chat`
- `supergroup`: سازندهٔ TL از نوع `channel` ولی `megagroup=true`
- `channel`: سازندهٔ TL از نوع `channel` و معمولاً `broadcast=true`

بنابراین برای UI از `DialogEntry.kind` استفاده کنید، نه فقط `peer.type` یا نام سازندهٔ `_ = channel`.

## ۷. تمدید توکن

نیازی نیست قبل از هر فرمان توکن را دستی تمدید کنید. همهٔ RPCها از Gateway عبور می‌کنند؛ اگر سرور انقضای توکن را اعلام کند، Core توکن را تمدید و در Session ذخیره می‌کند و همان درخواست را یک بار تکرار می‌کند.

برای تمدید صریح پیش از Discovery:

```bat
.venv\Scripts\python.exe scripts\discovery_cli.py --refresh-first dialogs --all
```

## ۸. خروجی‌ها

- گزارش آخر: `reports/discovery_last_report.json`
- رخدادهای امن عیب‌یابی: پوشهٔ `diagnostics`
- دیتابیس: `data/eitaa_messages.sqlite3`
- عکس‌ها: `data/media/avatars`

گزارش JSON شامل تعداد دریافتی، `total_count`، تعداد صفحه‌ها، کامل/ناقص بودن نتیجه و شمارش هر نوع گفتگو است.

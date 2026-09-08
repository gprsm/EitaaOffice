# ساخت Windows Installer

## نصب‌کنندهٔ پیشنهادی برای تحویل به کاربر

خروجی پیش‌فرض یک Setup تک‌فایلی و self-contained است. این بسته Python 3.13 x64، وابستگی‌های Python از wheelهای آفلاین و Build آمادهٔ Material UI را داخل خود دارد؛ بنابراین روی رایانهٔ مقصد نصب Python، Node.js، npm یا Electron لازم نیست و نصب در سطح کاربر و بدون Administrator انجام می‌شود.

پیش‌نیاز مقصد:

- Windows 10 یا 11 نسخهٔ 64 بیتی؛
- Microsoft Edge قابل اجرا؛
- فضای کافی در `%LOCALAPPDATA%\Programs\EitaaBridge`.

روی ایستگاه ساخت Windows اجرا کنید:

```bat
set "EITAA_CODE_SIGNING_THUMBPRINT=THUMBPRINT_FROM_CERTIFICATE_BUNDLE"
BUILD_OFFICE_SETUP_EXE.bat
```

پیش از Build، آیکون چنداندازه باید در `installer\assets\EitaaBridge.ico` باشد. PNG مربع 1024×1024 شفاف بهترین فایل ورودی برای تبدیل است. مسیر ساخت گواهی Self-signed، CER عمومی و اعتماد مقصد در `docs/INTERNAL_CODE_SIGNING.md` آمده است.

خروجی‌ها:

```text
release\office\EitaaBridge-0.8.0-rc5-MultiAccount-Activated-InternalSigned-GuiSetup-x64.exe
release\office\EitaaBridge-0.8.0-rc5-MultiAccount-Activated-SelfContained-Portable.zip
```

Builder پیش از ساخت، wheel Bridge را از source جاری بازسازی، parity بسته و source را کنترل، محیط Python همراه را فقط از wheelهای محلی نصب و یک شبیه‌سازی کپی نصب اجرا می‌کند. EXE حالت فقط‌خواندنی زیر را برای کنترل resourceهای داخلی دارد:

```bat
EitaaBridge-0.8.0-rc5-MultiAccount-Activated-InternalSigned-GuiSetup-x64.exe --verify-only
```

Setup هیچ Session، `bridge.json` یا `.env` واقعی، دیتابیس، رسانه، runtime log، diagnostics یا backup این رایانه را وارد خروجی نمی‌کند. در ارتقای نصب موجود، کد و Runtime مدیریت‌شده جایگزین می‌شوند ولی داده، Session، تنظیمات، رسانه، diagnostics و backup کاربر مقصد حفظ می‌شوند. انتقال دادهٔ واقعی فقط با Backup/Restore جداگانه و تأیید صریح انجام می‌شود.

در نصب کاملاً تمیز RC5، قابلیت‌های AppUser، چندحسابی و Worker مستقل از ابتدا روشن‌اند. پس از فعال‌سازی مجوز، نخست صفحهٔ «ساخت مدیر اولیه نرم‌افزار» نمایش داده می‌شود؛ بعد از ساخت مدیر، کاربر اولین شمارهٔ ایتا را به‌عنوان حساب پیام‌رسان تحت مالکیت همان مدیر اضافه می‌کند. افزودن حساب‌های بعدی و تعویض میان آن‌ها از رابط حساب پیام‌رسان انجام می‌شود و ایجاد حساب به‌تنهایی اتصال، OTP یا Worker را آغاز نمی‌کند.

ارتقا عمداً `bridge.json` موجود را بازنویسی نمی‌کند. برای آزمون واقعی همین ترتیب روی سیستمی که RC4 قبلاً روی آن اجرا شده است، ابتدا برنامه را ببندید و کل پوشهٔ نصب را به نامی پشتیبان تغییر دهید؛ سپس RC5 را نصب کنید. حذف مستقیم پوشه یا داده برای آزمون لازم نیست.

نسخهٔ بسته‌بندی‌شده پیش از شروع Backend به فعال‌سازی آفلاین وابسته به دستگاه نیاز دارد. اولین اجرا کد درخواست هش‌شده می‌سازد؛ کد فعال‌سازی فقط با کلید خصوصی مالک صادر و پس از بررسی امضای Ed25519 با DPAPI ذخیره می‌شود. Startupهای بعدی بی‌صدا هستند. کپی نصب یا Backup روی دستگاه دیگر مجوز را منتقل نمی‌کند. جزئیات در `docs/OFFLINE_ACTIVATION.md` آمده است.

کلید خصوصی صدور مجوز و ابزار مالک هرگز داخل Setup یا Portable ZIP قرار نمی‌گیرند. Build در صورت یافتن نام یا PEM محتمل private/signing key در payload متوقف می‌شود.

## Windows 7

این snapshot روی Windows 7 پشتیبانی نمی‌شود و Setup پیش از تغییر سیستم با پیام روشن متوقف می‌شود. مستند رسمی Python می‌گوید Python 3.13 به Windows 8.1 یا جدیدتر نیاز دارد و برای Windows 7 باید Python 3.8 استفاده شود؛ در مقابل قرارداد فعلی پروژه `Python >=3.11` است. Microsoft Edge نیز پشتیبانی Windows 7 را در نسخهٔ 109 خاتمه داده است.

- مرجع Python: <https://docs.python.org/3.13/using/windows.html>
- مرجع Edge: <https://learn.microsoft.com/en-us/deployedge/microsoft-edge-supported-operating-systems>

ساخت نسخهٔ Python 3.8 با dependencyهای قدیمی یا Runtime غیررسمی، یک نصب امن و پشتیبانی‌شده ایجاد نمی‌کند. مسیرهای قابل‌قبول عبارت‌اند از ارتقای سیستم مقصد به Windows پشتیبانی‌شده، یا اجرای Backend روی یک رایانهٔ پشتیبانی‌شده و استفادهٔ کنترل‌شده از رابط LAN پس از طراحی/پذیرش جداگانهٔ استقرار.

## بستهٔ تمیز قابل‌ممیزی

`package_clean.py` خروجی source را از allowlist صریح runtime/source/UI/installer/wheel/doc می‌سازد؛ پیمایش blacklist مبنای انتشار نیست. هر ZIP یک `_release/CONTENT_MANIFEST.json` داخلی با نام، اندازه و SHA-256 و یک receipt بیرونی با SHA-256 کل archive دارد. `--dry-run` هیچ فایل خروجی نمی‌نویسد.

نام traversal/absolute/backslash، duplicate/case collision، hash/manifest mismatch، محدودیت اندازه و الگوی high-confidence secret رد می‌شود. `data/`، `runtime/`، `diagnostics/`، `backups/`، config/session واقعی، scratch/fix/probe، تست‌ها، حافظهٔ داخلی پروژه و client قرنطینه‌شدهٔ Bale وارد release نمی‌شوند؛ fail-closed provider slot باقی است.

## Electron/Inno برای توسعه

`build_windows_installer.bat` مسیر جداگانهٔ Electron/Inno است و فقط روی ایستگاه ساخت به Python 3.13، Node.js 24 LTS، npm، Electron assets و Inno Setup 6 نیاز دارد. این وابستگی‌های build نباید روی رایانهٔ کاربر نصب شوند. مسیر self-contained بالا برای تحویل اداری سبک توصیه می‌شود.

امضای داخلی Self-signed فقط پس از نصب آگاهانهٔ CER روی مقصد معتبر دیده می‌شود و اعتبار عمومی/SmartScreen ایجاد نمی‌کند. پیش از انتشار عمومی، گواهی تجاری یا سازوکار اعتماد سازمانی، Windows 10/11 پاک و Session واقعی باید جداگانه پذیرفته شوند. ساخت، امضای داخلی و `--verify-only` جای نصب واقعی کاربر را نمی‌گیرند.

## سیاست Repair Runtime

- `install_app.bat` برای محیط دقیق و سالم idempotent است و force-reinstall انجام نمی‌دهد.
- محیط ناسازگار از wheelهای آفلاین همراه ارتقا می‌یابد.
- خرابی same-version خاموش overwrite نمی‌شود؛ `repair_app.bat` مسیر صریح repair است.
- هیچ installer یا stop command پردازشی را صرفاً بر اساس پورت متوقف نمی‌کند.

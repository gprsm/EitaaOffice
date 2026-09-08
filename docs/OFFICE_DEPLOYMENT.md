# استقرار اداری Eitaa Bridge

## نصب self-contained روی رایانهٔ مقصد

1. برنامه‌های قدیمی Bridge و API را ببندید.
2. بستهٔ عمومی اعتماد کنار Release را باز کنید، Thumbprint را با مالک تطبیق دهید و در صورت تأیید، CER را طبق `README_TRUST_CERTIFICATE_FA.md` برای کاربر جاری اعتماد دهید.
3. روی Windows 10/11 x64 فایل `EitaaBridge-0.8.0-rc5-MultiAccount-Activated-InternalSigned-GuiSetup-x64.exe` را اجرا کنید.
4. Setup گرافیکی فارسی سازگاری Windows و مسیر `%LOCALAPPDATA%\Programs\EitaaBridge` را نشان می‌دهد. «نصب» را انتخاب کنید؛ progress نمایش داده می‌شود و میانبر Desktop/Start Menu با آیکون برنامه ساخته می‌شود.
5. برنامه را از میانبر `Eitaa Bridge` باز کنید. در اولین اجرا، کد درخواست دستگاه را با دکمهٔ کپی برای مالک بفرستید و کد فعال‌سازی دریافتی را با دکمهٔ «جای‌گذاری از کلیپ‌بورد» وارد کنید. این دکمه به فارسی یا انگلیسی بودن کیبورد وابسته نیست.
6. پس از یک فعال‌سازی معتبر، Startupهای بعدی بدون نمایش پنجرهٔ فعال‌سازی انجام می‌شوند.
7. در صورت نیاز، `run_doctor.bat` را از پوشه نصب اجرا کنید.

Python 3.13 و dependencyهای آن داخل Setup و در محدودهٔ خود برنامه قرار دارند. Python و Node.js روی سیستم مقصد نصب سراسری نمی‌شوند. Build آماده UI داخل `ui\dist` قرار دارد و UI با Microsoft Edge در حالت App باز می‌شود.

فایل مجوز در `data\licensing\activation.dat` با DPAPI همان Windows user محافظت و با fingerprint دستگاه تطبیق داده می‌شود. انتقال کل پوشه به رایانهٔ دیگر فعال‌سازی را منتقل نمی‌کند. کلید خصوصی صدور مجوز خارج از customer artifact نگه‌داری می‌شود.

## ارتقا و آزمون نصب تمیز RC5

برای ارتقای عادی، برنامه را ببندید و Setup جدید را اجرا کنید؛ چیزی را پاک نکنید. managed code/runtime به‌روزرسانی می‌شود، ولی `bridge.json`، `.env`، نشست، `data/`، `runtime/`، `diagnostics/`، `backups/` و فعال‌سازی موجود حفظ می‌شوند.

برای نمایش دوبارهٔ پنجره فعال‌سازی روی همان رایانه، پس از بستن برنامه فایل `%LOCALAPPDATA%\Programs\EitaaBridge\data\licensing\activation.dat` را حذف دائمی نکنید؛ آن را موقتاً به `activation.dat.test-backup` تغییر نام دهید. برای آزمون کاملاً تمیز و مشاهدهٔ ترتیب «مدیر اولیه ← حساب ایتا»، کل پوشهٔ `%LOCALAPPDATA%\Programs\EitaaBridge` را به نامی مانند `EitaaBridge.pre-rc5-test` تغییر نام دهید و سپس Setup را اجرا کنید. این کار state قبلی را حفظ و امکان بازگردانی می‌دهد.

Builder پیش از انتشار خروجی جدید، Setup/Portableهای نام‌دار قبلی را همراه hash Manifest به `release\office\archive\<timestamp>` منتقل می‌کند؛ فایل‌های قبلی خام حذف نمی‌شوند.

Windows 7 پشتیبانی نمی‌شود: قرارداد پروژه Python 3.11+ است، Python 3.13 روی Windows 7 اجرا نمی‌شود و Edge پشتیبانی‌شده نیز برای آن وجود ندارد. از Runtimeهای غیررسمی یا dependencyهای منقضی برای دورزدن این مرز استفاده نکنید.

## مسیرهای عملیاتی

- Session: `.eitaa_session.json`
- پایگاه داده: `data\eitaa_messages.sqlite3`
- رسانه: `data\media`
- تنظیمات: `bridge.json` و `.env`
- Compositionها: `data\bridge_compositions.json`
- لاگ اجرا: `runtime\logs`
- پشتیبان‌ها: `backups\runtime`
- بسته‌های Diagnostics امن: `diagnostics\bundles`

در Launcher سبک، پاسخ ساده Health برای بازاستفاده Backend کافی نیست. Backend فقط پس از Handshake مالکیت شامل Install ID، مسیر نصب، نسخه API، نسخه Bridge و Token محلی بازاستفاده می‌شود. کلیک دوباره با قفل Single Instance به پنجره موجود برمی‌گردد و Backend دوم ایجاد نمی‌کند. بستن پنجره Edge یک Shutdown مالکیت‌دار می‌فرستد و قطع Heartbeat نیز Backend یتیم را پس از مهلت کوتاه خاموش می‌کند.

برای توقف دستی از `stop_eitaa_bridge.bat` استفاده کنید. این اسکریپت هیچ Process را بر اساس پورت متوقف نمی‌کند. سرویس ناسازگار فقط گزارش می‌شود و Session یا داده محلی حذف نمی‌شود. جزئیات در `docs/RUNTIME_OWNERSHIP.md` آمده است.
## ارتقا از MVP 6.0

نسخه نهایی را روی پوشه قدیمی Extract نکنید. آن را در پوشه جدید قرار دهید و اجرا کنید:

```bat
upgrade_from_ui_mvp6_0.bat "FULL_PATH_TO_OLD_MVP6_0"
install_app.bat
run_doctor.bat
EitaaBridge.bat
```

Migration پیش از کپی Backup می‌سازد و داده‌های اصلی را منتقل می‌کند؛ Diagnosticها، Logهای تاریخی، `.venv`، `node_modules` و Build قدیمی منتقل نمی‌شوند.

## ساخت فایل قابل‌تحویل

روی رایانهٔ سازنده اجرا کنید:

```bat
BUILD_OFFICE_SETUP_EXE.bat
```

فایل shareable به‌طور پیش‌فرض هیچ Session، Config واقعی، دیتابیس، رسانه، diagnostics، backup یا log این رایانه را همراه نمی‌برد. برای جابه‌جایی دادهٔ یک نصب موجود از Backup/Restore مستقل استفاده کنید؛ فایل Backup را مانند credential خصوصی نگه‌داری کنید.

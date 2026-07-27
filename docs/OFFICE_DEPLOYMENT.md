# استقرار اداری Eitaa Bridge

## نصب بسته MVP 6.1.1 Runtime 1

1. برنامه‌های قدیمی Bridge و API را ببندید.
2. بسته را در یک پوشه دائمی و قابل‌نوشتن استخراج کنید؛ انتقال مداوم پوشه توصیه نمی‌شود.
3. Python 3.13 x64 را نصب کنید.
4. `install_app.bat` را اجرا کنید.
5. `run_doctor.bat` را اجرا کنید.
6. برنامه را از میانبر Desktop، Start Menu یا `EitaaBridge.bat` باز کنید.

وابستگی‌های Python از Wheelهای داخل بسته نصب می‌شوند. Build آماده UI داخل `ui\dist` قرار دارد؛ بنابراین نصب و اجرای روزمره به Node.js، npm یا Electron نیاز ندارد. `EitaaBridge.bat` به‌طور پیش‌فرض Backend سبک Python را پنهانی اجرا و UI را با Microsoft Edge در حالت App باز می‌کند. اجرای کامل Electron فقط از `EitaaBridgeElectron.bat` و برای حالت توسعه‌ای اختیاری است.

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


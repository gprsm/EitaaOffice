# امضای داخلی و آیکون Windows

این مسیر برای توزیع داخلی Eitaa Bridge است و جای گواهی تجاری با اعتبار عمومی/SmartScreen را نمی‌گیرد. امضای Authenticode با گواهی Self-signed فقط روی رایانه‌هایی «معتبر» دیده می‌شود که CER عمومی ناشر را پس از کنترل Thumbprint در مخزن اعتماد نصب کرده باشند.

## مرز کلیدها

- گواهی Authenticode و کلید Ed25519 فعال‌سازی دو سامانهٔ مستقل‌اند.
- کلید خصوصی Authenticode فقط در `Cert:\CurrentUser\My` رایانهٔ سازنده و با `KeyExportPolicy=NonExportable` ایجاد می‌شود.
- هیچ PFX یا private key داخل Repository، source package، Setup، Portable ZIP یا پوشهٔ تحویل تولید نمی‌شود.
- فایل `EitaaBridge-Internal-Publisher.cer` عمومی است و افشای آن محرمانگی را از بین نمی‌برد؛ صحت آن باید با Thumbprint مستقل کنترل شود.

## ورودی آیکون

فایل نهایی باید در `installer\assets\EitaaBridge.ico` قرار گیرد. ICO باید چنداندازه و شامل 16، 20، 24، 32، 40، 48، 64، 128 و 256 پیکسل باشد. برای تولید آن، PNG مربع 1024×1024 با پس‌زمینه شفاف بهترین ورودی است؛ PNG مربع 512×512، SVG یا ICO چنداندازه نیز پذیرفتنی است.

Builder آیکون مفقود/خراب را رد می‌کند. همان ICO در resource فایل Setup و در `assets\EitaaBridge.ico` payload قرار می‌گیرد؛ میانبرهای Desktop و Start Menu دقیقاً همان فایل نصب‌شده را مصرف می‌کنند.

## ساخت گواهی و بستهٔ عمومی اعتماد

پوشهٔ خروجی را بیرون Repository انتخاب کنید:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\new_internal_code_signing_certificate.ps1 -OutputDirectory "D:\delivery\internal-code-signing-trust"
```

خروجی عمومی شامل CER، metadata، Thumbprint، راهنمای فارسی و اسکریپت نصب اعتماد است. اسکریپت اعتماد به Thumbprint همان CER pin شده و به‌طور خودکار توسط Setup اجرا نمی‌شود.

## ساخت و امضای Release

Thumbprint اعلام‌شده را فقط برای همان پنجره Build تنظیم و Builder را اجرا کنید:

```bat
set "EITAA_CODE_SIGNING_THUMBPRINT=THUMBPRINT_FROM_CERTIFICATE_BUNDLE"
BUILD_OFFICE_SETUP_EXE.bat
```

اگر timestamp server سازمانی یا عمومی در دسترس و پذیرفته شده باشد، می‌توان `EITAA_TIMESTAMP_SERVER` را نیز تنظیم کرد. نبود timestamp مانع امضای داخلی نیست، اما اعتبار زمانی امضا پس از پایان اعتبار گواهی را محدود می‌کند.

Builder پس از ساخت، EXE را با SHA-256 امضا، Thumbprint امضاکننده را کنترل، hash sidecar را بعد از امضا تولید و invalidation امضا پس از دستکاری یک کپی موقت را آزمایش می‌کند. نبود Thumbprint، آیکون، کلید خصوصی یا امضای قابل‌تشخیص Build نهایی را fail-closed متوقف می‌کند.

## اعتماد روی رایانهٔ مقصد

کاربر باید ابتدا Thumbprint راهنمای تحویلی را از یک کانال مستقل با مالک تطبیق دهد. سپس اسکریپت `Install-EitaaBridgeInternalPublisherTrust.ps1` را برای Current User اجرا کند. گزینهٔ `-LocalMachine` فقط با PowerShell مدیر و برای اعتماد همهٔ کاربران است.

خود Setup حق افزودن گواهی به Root یا TrustedPublisher را ندارد؛ چنین رفتاری مرز اعتماد را پنهان و امنیت توزیع را تضعیف می‌کند.

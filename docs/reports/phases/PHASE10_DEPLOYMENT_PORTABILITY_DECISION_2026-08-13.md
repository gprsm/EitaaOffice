# Phase 10 Deployment Portability Decision — 2026-08-13

## تصمیم کاربر

محیط توسعه و محیط اجرای نهایی مستقل‌اند. هیچ ویژگی محصول نباید به IP، DHCP،
Network Category، Windows Firewall، مودم یا WordPress همین رایانه hard-code
شود. نبود DMZ و Port Forwarding در مودم فعلی به این معنی است که سرویس فعلی
از اینترنت ورودی منتشر نشده، اما این واقعیت نیز قرارداد استقرار آینده نیست.

## تفسیر وضعیت‌های قبلی

موارد زیر observation محیط توسعه‌اند و دیگر blocker Phase 10 نیستند:

- Wi-Fi روی Public؛
- IPv4 فعلی دریافت‌شده از DHCP؛
- نبود Rule با نام `Eitaa Bridge Trusted LAN`؛
- در دسترس نبودن WordPress محلی.

این موارد فقط اگر پروفایل LAN همین میزبان واقعاً انتخاب شود، در checklist آن
استقرار بررسی می‌شوند.

## قرارداد پروفایل‌های استقرار

### 1. Desktop Loopback

- Bind پیش‌فرض به Loopback؛
- مناسب توسعه، desktop و اجرای تک‌رایانه‌ای؛
- بدون وابستگی به Firewall/Router/IP ثابت؛
- AppUser auth و MessengerAccount isolation مستقل از شبکه باقی می‌مانند.

### 2. Trusted LAN HTTP (اختیاری)

- برای شبکهٔ خصوصی و فقط با Config صریح همان محیط؛
- Host، Origin، CIDR، bind address و port از تنظیمات محیط می‌آیند؛
- DHCP reservation، Network Profile و Firewall عملیات deployment هستند؛
- نبود این تنظیمات در ماشین توسعه مانع کد و تست پروفایل‌های دیگر نیست.

### 3. Web HTTP/HTTPS

- پورت 80 برای HTTP قابل پیکربندی است، مشروط به مجوز bind سیستم میزبان؛
- پورت 443 باید واقعاً TLS داشته باشد؛ شمارهٔ پورت به‌تنهایی HTTPS نمی‌سازد؛
- مسیر ترجیحی: reverse proxy مانند IIS/Nginx/Caddy که TLS را terminate کند و
  درخواست را به backend داخلی روی Loopback منتقل کند؛
- پیش از پذیرش Production باید قرارداد trusted proxy، Host/Origin،
  `X-Forwarded-Proto` یا معادل کنترل‌شده، Secure cookie، CSRF، timeouts،
  body limits، websocket (در صورت نیاز)، health/readiness و shutdown آزموده شود؛
- backend نباید Forwarded header از کلاینت ناشناس را بدون فهرست proxyهای
  قابل‌اعتماد بپذیرد.

نسخهٔ فعلی فقط `desktop_loopback` و `trusted_lan_http` را در Config می‌شناسد و
TLS داخلی ندارد. بنابراین ادعای آمادگی نهایی 443 هنوز مجاز نیست؛ 10-C باید
پروفایل وب/reverse-proxy و تست‌های آن را اضافه یا قرارداد استقرار خارجی آن را
به‌طور کامل مستند و وریفای کند.

## WordPress

WordPress یک integration مشترک نصب است، نه شرط راه‌اندازی هستهٔ نرم‌افزار.
کد، UI و تست‌های Fake/Contract بدون Laragon ادامه می‌یابند. فقط هنگام پذیرش
واقعی موارد زیر از کاربر خواسته می‌شود Laragon را اجرا کند:

- REST discovery و authentication؛
- draft/upload/update محدود و تأییدشده؛
- کنترل دسترسی admin/user؛
- عدم افشای Application Password یا Cookie به مرورگر؛
- rollback/cleanup محتوای آزمایشی با هماهنگی کاربر.

هیچ انتشار واقعی بدون تأیید لحظه‌ای کاربر انجام نمی‌شود.

## منظور از Pilot دوکاربره

این Pilot برای اثبات معماری چندکاربره است:

```text
AppUser A -> MessengerAccount A -> Session/Data/Jobs/Audit A
AppUser B -> MessengerAccount B -> Session/Data/Jobs/Audit B
```

باید ثابت شود Login، Expiry، Logout، Sync، Job و خطای A به B سرایت نمی‌کند و
هیچ داده یا Credential بین آن‌ها دیده نمی‌شود. این به معنی الزام محصول به
داشتن دو کاربر یا دو حساب برای کار عادی نیست.

- آزمون خودکار و Fake: اکنون الزامی و قابل اجرا بدون حساب دوم واقعی؛
- Pilot واقعی: نیازمند مالک حساب دوم و ورود خصوصی OTP/رمز دوم در UI؛
- طبق تصمیم جاری، Pilot واقعی تا محیط اجرای نهایی قابل تعویق است و blocker
  توسعهٔ قابل‌حمل 10-C نیست؛
- اگر قبل از Release نهایی ادعای multi-user production مطرح شود، این Pilot
  واقعی یا یک پذیرش معادل باید انجام شود.

## وضعیت جاری Phase 10

- 10-A: کامل و پذیرفته‌شده؛
- 10-B: ورود واقعی ایتا موفق و دادهٔ حساب authenticated است؛ اصلاح شبکه،
  challenge id، DPAPI، مسیرهای peer و Grid انجام و تست شده؛ فقط راه‌اندازی
  دوبارهٔ سرویس، ورود AppUser محلی، پذیرش دیداری رابط واقعی و گزارش نهایی 10-B
  باقی است؛
- سرویس Loopback در آخرین بررسی در حال اجرا نبود، ولی Session ایتا و داده‌ها
  محفوظ‌اند؛
- 10-C: باید با تعریف جدید portability/web profile ادامه یابد؛
- 10-D: پس از پذیرش 10-C، rollback روی کپی، support bundle، secret scan و
  گزارش نهایی؛
- Phase 11: شروع نشده است.

## محدودیت‌های ادامه

- Worktree عمداً dirty است؛ reset/checkout/stage/commit/push ممنوع مگر درخواست
  صریح جدید کاربر؛
- OTP، رمز، Cookie، Token، Application Password و شمارهٔ کامل نباید خوانده یا
  در گفتگو/گزارش چاپ شود؛
- ارسال واقعی ایتا و عملیات واقعی WordPress نیازمند تأیید همان لحظه است؛
- تغییر Firewall، Router، Network Profile، Service یا Port binding سطح سیستم
  فقط اگر یک استقرار واقعی انتخاب شد و با مجوز صریح انجام می‌شود.

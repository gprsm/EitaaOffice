# گزارش استقرار Production روی Linux

تاریخ: 2026-09-22  
وضعیت: `DEPLOYED / LIVE_VALIDATED / CDN EDGE TLS ACTIVE`

## نتیجه

رابط و API روی دامنهٔ `eitaa.farhangimaz.ir` پشت Nginx مستقر شدند. Backend فقط روی
Loopback گوش می‌دهد و یک gateway داخلی مجزا نیز فقط روی Loopback برای برنامهٔ دوم آینده
وجود دارد. سرویس با کاربر systemd اختصاصی، دسترسی نوشتن محدود به state مشترک، restart
کنترل‌شده و سخت‌سازی systemd اجرا می‌شود.

## سازگاری Linux

وابستگی پیشین AppAuth/هویت به Windows DPAPI مانع bootstrap واقعی بود. مسیر غیرWindows با
AES-GCM و HMAC و دو کلید جدا در پوشهٔ Coordinator افزوده شد. فایل‌ها با `0600` و پوشه با
`0700` ساخته می‌شوند؛ symlink، فایل غیرregular، مجوز group/other و payload دستکاری‌شده
fail-closed رد می‌شوند. Windows همچنان از DPAPI استفاده می‌کند.

## انتشار و چندسایتی

کد هر نسخه در `releases/<id>` تغییرناپذیر است و symlink `current` پس از build/import و پیش
از restart اتمیک جابه‌جا می‌شود. Config، DB، media، diagnostics و backup در `shared` باقی
می‌مانند. readiness ناموفق، نسخهٔ قبلی را برمی‌گرداند. dispatcher مشترک زیر نصب شد:

```text
sudo publish-site list
sudo publish-site status eitaa-bridge
sudo publish-site deploy eitaa-bridge
```

dispatcher فقط handler ریشه‌مالک با نام محدود و مجوز امن را اجرا می‌کند. سایت‌های آینده
handler و inbox مستقل خواهند داشت و Nginx vhost هر سایت جدا می‌ماند.

## شواهد

- Backend کامل: ۸۰۹ پاس، یک skip پلتفرمی از ۸۱۰ test؛
- TypeScript، Observability و build UI: PASS؛
- UI build: ۱۰۲۱ module؛
- package privacy: ۱۷۵ entry و finding عملیاتی صفر؛
- Live: redirect، UI، login، Secure Cookie و session همگی PASS؛
- Backend و gateway از اینترنت قابل اتصال نیستند و فقط روی Loopback هستند؛
- systemd exposure برابر `3.1 OK`؛
- پنج vhost قبلی پس از reload همچنان 200 بودند.

هیچ Login/OTP/Send پیام‌رسان، WordPress write یا انتقال داده و session رایانهٔ توسعه در این
استقرار انجام نشد.

## وضعیت TLS عمومی

گواهی origin برای اتصال CDN نصب است و درخواست عمومی HTTPS از Edge با اعتبارسنجی عادی TLS
موفق شد. HTTP همچنان به HTTPS redirect می‌شود و Secure Cookie یا مرز Loopback کاهش نیافته است.

## اصلاح تکمیلی احراز هویت پیام‌رسان

پس از گزارش عملیاتی کاربر، مشخص شد Config اولیهٔ Production مقدار
`remote_messenger_auth.enabled=false` داشت و قفل تاریخی Phase 6-A روشن‌کردن آن را حتی در
`web_reverse_proxy` امن ممنوع می‌کرد. پاسخ زندهٔ request-code پیش از Provider با کد امن
`remote_messenger_auth_disabled` این ریشه را تأیید کرد. قرارداد اصلاح شد تا قابلیت فقط در
پروفایل HTTPS Reverse Proxy و با flag صریح مجاز باشد؛ محدودیت‌های Proxy هم‌میزبان، forwarded
HTTPS، Host/Origin، Secure Cookie، AppUser و CSRF بدون کاهش باقی ماندند. HTTP شبکهٔ داخلی
همچنان این عملیات را رد می‌کند.

نسخهٔ اصلاحی از مسیر مشترک `publish-site` منتشر و Config پایدار با migration نسخه‌دار، backup،
validation و rollback خودکار به‌روزرسانی شد. پس از انتشار readiness عمومی 200 بود؛ probe بدون
credential روی request-code به‌جای خطای deployment به `app_auth_required` رسید و آزمون زندهٔ
redirect/UI/login/Secure Cookie/session نیز کامل عبور کرد. هیچ شماره یا OTP ارسال و هیچ تماس
Provider در این پذیرش انجام نشد.

## اصلاح تکمیلی Child و هویت شماره

پس از بازشدن مرز HTTPS، درخواست‌های کاربر در Child با `CoordinatorIdentityError` و دلیل امن
`account_phone_resolution_failed` رد شدند. بررسی کد نشان داد Child و Registry هنوز محافظ DPAPI
مخصوص Windows را می‌ساختند، ولی onboarding روی Linux با کلید فایل سرویس انجام شده بود.
هر دو مسیر Runtime اکنون از همان انتخاب‌گر سیستم‌عامل Coordinator استفاده می‌کنند. آزمون
ساختگی بازیابی هویت در Child بدون تماس Provider افزوده شد. نسخهٔ اصلاحی روی سرور فعال شد و
ابزار فقط‌خواندنی با کاربر سرویس بازشدن هویت یک حساب موجود را تأیید کرد؛ مقدار شماره، کلید
یا نشست در خروجی ابزار و گزارش ثبت نشد. سرویس، readiness، UI، login و Cookie امن نیز سالم‌اند.
پس از این انتشار، اقدام خود کاربر از UI با رخدادهای امن `eitaa.auth.request_code.succeeded`
و سه `eitaa.auth.login.completed` ثبت شد؛ ورود کامل پذیرفته شد. خروج‌های بعدی نیز موفق بودند.
ردهای پس از آخرین خروج به دلیل `account_phone_mismatch` برای شماره‌ای غیر از هویت حساب
انتخاب‌شده بودند، نه بازگشت خطای Child. UI برای انتخاب/افزودن حساب دیگر، نمایش راهنمای
شمارهٔ ماسک‌شده و خطای فارسی قابل اقدام اصلاح شد؛ مرز تطابق سمت سرور حفظ شد.
نسخهٔ UI از مسیر مشترک `publish-site` با بستهٔ پاک ۱۷۴ entry منتشر شد؛ سرویس active،
UI و readiness هر دو 200 بودند و هش bundle سرور با خروجی محلی برابر بود. ورود تعاملی
یا درخواست OTP جدید توسط این Run انجام نشد.

## اصلاح ورود وب و کنترل انتشار — 2026-09-24

پس از فعال‌شدن توکن محلی API در محیط سرویس، بررسی سراسری Bearer پیش از مسیر
`app-auth/status` مرورگر، ورود و readiness را با `401 api_unauthorized` بست.
در استقرار AppUser Auth، Bearer دیگر پیش‌شرط نشست کاربر نیست؛ مسیرهای محافظت‌شده
همچنان نشست AppUser، مجوز حساب و CSRF می‌خواهند. Bearer به‌تنهایی مجوز ارسال
پیام نیست. UI خطاهای آغاز را به راهنمای امن تبدیل می‌کند، فقط یک بار برای خطای
گذرا خودکار تلاش می‌کند و از حلقهٔ refresh وضعیت ورود جلوگیری می‌کند.

handler رسمی انتشار اکنون علاوه بر readiness، پاسخ بدون credential وضعیت ورود
را از gateway هم‌میزبان می‌سنجد و در شکست آن از rollback موجود استفاده می‌کند.
بستهٔ محدود با هش `D81B875C...08FFCD7` از مسیر `publish-site` در release
`20260924T045946Z-d81b875cbac0` فعال شد. full Backend، build و آزمون‌های UI
و قرارداد وب سبز شدند. پس از انتشار وضعیت ورود عمومی `200`، UI و readiness
عمومی `200`، readiness gateway `200`، `/me` بدون نشست `401` و سرویس فعال بود؛
فرم ورود در مرورگر واقعی نمایش داده شد. ورود کاربر واقعی و ارسال پیام آزموده نشد.

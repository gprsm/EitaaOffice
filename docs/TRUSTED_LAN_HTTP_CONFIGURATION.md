# راهنمای Config حالت `trusted_lan_http`

این راهنما قرارداد Config فاز ۶-A، hardening فاز ۶-B و مدل عملیاتی بدون فعال‌سازی فاز ۶-C را توضیح می‌دهد. فایل آمادهٔ نمونه در ریشهٔ پروژه `bridge.trusted-lan-http.example.json` است. کپی‌کردن نمونه به‌تنهایی هیچ Port یا Firewall rule را باز نمی‌کند و نباید بدون فاز Rollout و تأیید مستقل جایگزین `bridge.json` نصب واقعی شود.

## انتخاب mode

- اگر بخش `deployment` وجود نداشته باشد، برنامه با قرارداد سازگار `desktop_loopback` روی `127.0.0.1:8765` کار می‌کند.
- `trusted_lan_http` فقط برای یک LAN خصوصی مدیریت‌شده است و Config ناقص یا مبهم باعث توقف Startup می‌شود.
- `0.0.0.0`، آدرس عمومی، Host/Origin دارای wildcard و CIDR عمومی رد می‌شوند.
- Host و Origin باید IP و Port دقیق رایانهٔ سرور را داشته باشند. UI و API از همان Origin سرو می‌شوند و CORS عمومی وجود ندارد.

## معنی فیلدها

- `deployment.schema_version`: نسخهٔ قرارداد استقرار؛ مقدار فعلی `1` است.
- `deployment.mode`: برای این راهنما `trusted_lan_http` است؛ دو پروفایل مستقل دیگر
  `desktop_loopback` و `web_reverse_proxy` هستند. قرارداد Web در
  `docs/PHASE10_WEB_REVERSE_PROXY_DEPLOYMENT.md` آمده است.
- `deployment.bind.host`: IP خصوصی و مشخص کارت شبکهٔ سرور؛ wildcard مجاز نیست.
- `deployment.bind.port`: Port صریح بین ۱ و ۶۵۵۳۵.
- `allowed_hosts`: Authority دقیق درخواست، مانند `192.168.1.20:8765`.
- `allowed_origins`: Origin دقیق و بدون Path، مانند `http://192.168.1.20:8765`.
- `allowed_private_client_cidrs`: Subnetهای خصوصی مجاز، ترجیحاً Subnet کوچک واقعی مانند `192.168.1.0/24`.
- `cleartext_http_risk_acknowledgement`: پذیرش صریح نبود محرمانگی و اصالت انتقال در HTTP.
- `private_lan_only_acknowledgement`: تعهد به منتشرنکردن سرویس روی اینترنت، شبکهٔ عمومی یا Guest Wi-Fi.
- `bootstrap_admin_loopback_only`: باید `true` بماند؛ مدیر اولیه فقط از خود رایانهٔ سرور ساخته می‌شود.
- `same_origin_only`: باید `true` بماند؛ wildcard CORS پشتیبانی نمی‌شود.
- `remote_messenger_auth.enabled`: در فاز ۶-A باید `false` باشد. Request code، OTP، 2FA، Logout و Reset نشست پیام‌رسان از کلاینت LAN از راه دور رد می‌شوند؛ اجرای محلی روی Loopback جداست.

دو acknowledgement اصلی باید دقیقاً این رشته‌ها باشند:

```text
I_ACCEPT_TRUSTED_LAN_HTTP_WITHOUT_TRANSPORT_SECURITY
I_WILL_NOT_EXPOSE_THIS_SERVICE_TO_PUBLIC_OR_GUEST_NETWORKS
```

وجود این رشته‌ها امنیت HTTPS ایجاد نمی‌کند؛ فقط تصمیم آگاهانهٔ مدیر را غیرمبهم می‌کند.

## پیش‌شرط AppUser authentication

در `trusted_lan_http`، `features.app_user_auth.enabled` باید `true` باشد. اگر Environment kill switch آن را خاموش کند، Config LAN نیز Fail-closed می‌شود. Bootstrap مدیر اولیه از موبایل یا کلاینت LAN مجاز نیست و باید روی خود سرور انجام شود.

فعال‌سازی واقعی AppUser auth، Coordinator، Multi-session و مهاجرت داده بخشی از فاز ۶-A نیست. نمونه فقط قرارداد را نشان می‌دهد.

## کنترل‌های Auth و HTTP در فاز ۶-B

- Login موفق همیشه Session و CSRF جدید می‌سازد و Cookie ورودی را به نشست احرازشده ارتقا نمی‌دهد.
- تغییر واقعی Role یا Status همهٔ Sessionهای فعال کاربر را باطل می‌کند. Logout-all کاربر و Revoke همهٔ Sessionهای یک کاربر توسط مدیر نیز سمت سرور در دسترس‌اند؛ فهرست و UI مدیریت Device/Session همچنان فاز ۹-C است.
- Idle timeout و Absolute timeout فقط با زمان سمت سرور اعمال می‌شوند و Client نمی‌تواند آن‌ها را تمدید یا بازنویسی کند.
- Cookie نشست فقط با `HttpOnly; SameSite=Strict; Path=/` صادر می‌شود و Session/Credential از URL، Query String یا Browser Storage خوانده نمی‌شود.
- چون این mode عمداً HTTP cleartext است، Cookie نمی‌تواند `Secure` باشد. نبود `Secure` یک محدودیت پذیرفته‌شده است و امنیت HTTPS ایجاد نمی‌کند.
- تمام درخواست‌های تغییردهنده در حالت LAN به Origin دقیق نیاز دارند و پس از Login، CSRF معتبر همان Session نیز لازم است. Token CSRF یک synchronizer token نشست‌محور است، نه nonce یک‌بارمصرف؛ Revoke/Logout/Timeout نشست Replay آن را بی‌اعتبار می‌کند، اما مهاجمِ قادر به شنود HTTP می‌تواند تا زمان اعتبار همان Session آن را Replay کند.
- JSON حداکثر ۲ MiB است. Upload در LAN حداکثر ۱۲۸ MiB، فقط با `application/octet-stream` و حداکثر ۱۲ بار در دقیقه برای هر IP واقعی Socket پذیرفته می‌شود. سقف عمومی LAN نیز ۲۴۰ Request در دقیقه برای هر IP است.
- Login علاوه بر Bucket هر AppUser و Bucket سراسری نصب، در LAN Bucket مستقل Client IP دارد؛ `X-Forwarded-For` در این محاسبه استفاده نمی‌شود.
- پاسخ‌های JSON و Media خصوصی `Cache-Control: no-store` دارند. CSP، منع Frame، `no-referrer`، Permissions Policy، `nosniff` و `same-origin` resource policy نیز ارسال می‌شوند. CSP رابط موجود برای Styleهای فعلی به `style-src 'unsafe-inline'` نیاز دارد؛ Script inline مجاز نشده است.
- هیچ CORS عمومی یا wildcard اضافه نشده است.

## ریسک‌های باقی‌ماندهٔ HTTP

HTTP ترافیک را رمزگذاری یا اصالت‌سنجی نمی‌کند. هر دستگاه یا تجهیزی که بتواند مسیر شبکه را مشاهده یا تغییر دهد ممکن است نام کاربری، رمز برنامه، Cookie نشست، OTP، رمز دوم یا محتوای عملیات را ببیند یا دست‌کاری کند. Cookie `HttpOnly`، CSRF، Hash رمز و محدودسازی Host/Origin این خطر انتقال را حذف نمی‌کنند.

به همین علت:

- LAN باید خصوصی و قابل اعتماد باشد.
- Port Forwarding، DMZ و UPnP نباید برای این سرویس فعال شوند.
- Guest Wi-Fi برای کاربران برنامه مناسب نیست.
- AP Isolation یا Client Isolation ممکن است اتصال موبایل به سرور را مسدود کند؛ خاموش‌کردن آن فقط پس از بررسی سیاست شبکه انجام شود.
- برای رایانهٔ سرور DHCP reservation یا IP ثابت مناسب تعریف شود تا Host/Origin Config تغییر نکند.
- Windows Firewall در فاز ۶-C فقط برای Port و Subnet لازم طراحی می‌شود؛ فاز ۶-A هیچ Ruleای اعمال نمی‌کند.
- `X-Forwarded-For` در این قرارداد منبع Client IP نیست و بدون Proxy مورد اعتماد استفاده نمی‌شود.

## روش آماده‌سازی بدون فعال‌سازی

1. IP خصوصی ثابت/رزروشدهٔ سرور و Subnet واقعی را از مدیر شبکه بگیرید.
2. فایل نمونه را فقط برای بررسی کپی کنید و IP/Port/CIDR را به مقادیر واقعی محدود تغییر دهید.
3. مطمئن شوید Host و Origin دقیقاً با Bind یکی هستند.
4. Remote messenger authentication را خاموش نگه دارید.
5. `bridge.json` نصب واقعی، Firewall و Router را در فاز ۶-A تغییر ندهید.
6. فعال‌سازی و پذیرش واقعی فقط در فازهای بعدی و با Backup و تأیید مستقل انجام می‌شود.

## عملیات Windows در فاز ۶-C

لانچر LAN هیچ Host یا Port ورودی نمی‌پذیرد و مقادیر را فقط از `deployment.bind` معتبر می‌گیرد. سه عمل امن دارد:

```text
EitaaBridgeLanServer.bat check
EitaaBridgeLanServer.bat firewall-plan
EitaaBridgeLanServer.bat start
```

- `check` فقط Config و وجود Build تولیدی UI را بررسی می‌کند و Socket باز نمی‌کند.
- `firewall-plan` فقط یک Plan JSON و PowerShell preview محدود تولید می‌کند؛ هیچ Ruleای اجرا یا نصب نمی‌شود.
- `start` تنها در `trusted_lan_http` معتبر است، قفل تک‌نمونهٔ سیستم‌عاملی می‌گیرد و سپس API/UI same-origin را روی Host/Port خود Config اجرا می‌کند.
- توقف عادی با Ctrl+C باعث Shutdown کنترل‌شده و آزادشدن قفل می‌شود. در Crash نیز Lock سیستم‌عاملی آزاد می‌شود و Metadata stale در اجرای بعدی جایگزین می‌گردد.
- برای Restart، ابتدا نمونهٔ قبلی باید کاملاً متوقف شود و سپس همان فرمان `start` دوباره اجرا شود؛ اجرای هم‌زمان نمونهٔ دوم Fail-closed رد می‌شود.

Endpointهای عملیاتی:

```text
GET /api/v1/health
GET /api/v1/readiness
```

`health` زنده‌بودن Application را گزارش می‌کند. `readiness` فقط هنگام پذیرش Request پاسخ موفق می‌دهد و در Startup/Shutdown یا حالت not-ready با `503` پاسخ می‌دهد. Payload این Endpointها فاقد Secret، Token، Cookie، شماره تلفن، Provider session، محتوای خصوصی و مسیر فایل است.

طرح Firewall فقط این محدوده را توصیف می‌کند:

```text
Direction      Inbound
Action         Allow
Profile        Private
Protocol       TCP
LocalAddress   deployment.bind.host
LocalPort      deployment.bind.port
RemoteAddress  deployment.allowed_private_client_cidrs
EdgeTraversal  Block
```

هیچ حالت `Any`، پروفایل `Public`، آدرس `0.0.0.0/0` یا اجرای خودکار در ابزار وجود ندارد. اعمال Plan، نصب Windows Service و Pilot واقعی به فاز Rollout و تأیید صریح مدیر موکول است.

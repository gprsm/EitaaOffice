# قرارداد استقرار Web و Reverse Proxy — Phase 10-C

## هدف و مرز

این سند قرارداد محیط‌مستقل استقرار را تعریف می‌کند. IP فعلی DHCP، Public بودن شبکهٔ توسعه،
Firewall این رایانه و در دسترس بودن Laragon جزو قرارداد محصول نیستند. سه پروفایل مستقل‌اند:

- `desktop_loopback`: اجرای محلی/دسکتاپ با HTTP فقط روی Loopback؛
- `trusted_lan_http`: گزینهٔ صریح و محدود به LAN خصوصی با پذیرش ریسک cleartext؛
- `web_reverse_proxy`: backend فقط روی Loopback و HTTPS واقعی در TLS terminator هم‌میزبان.

فایل `bridge.web-reverse-proxy.example.json` فقط نمونه است. Host، Origin، پورت backend،
حدود و timeoutها باید در استقرار نهایی با مقادیر همان محیط جایگزین شوند. هیچ مقدار متعلق به
رایانهٔ توسعه، Router یا DHCP در کد قرار نمی‌گیرد.

## پورت 80 و 443

- پورت 80 یک پورت HTTP پیکربندی‌پذیر است. Loader و انتخاب bind آن را می‌پذیرند، اما این پروژه
  در Phase 10-C هیچ bind واقعی روی 80 انجام نداده است. در استقرار Web بهتر است listener پورت 80
  در Proxy فقط redirect قطعی به HTTPS بدهد.
- پورت 443 به‌تنهایی HTTPS نیست. HTTP server داخلی اجرای مستقیم روی 443 را fail-closed رد می‌کند.
  Proxy باید TLS واقعی را روی 443 terminate کند و درخواست را به یک پورت جداگانهٔ Loopback بفرستد.
- نصب Proxy، certificate، bind واقعی 80/443 و تغییر Firewall خارج از این پیاده‌سازی است و اجازهٔ
  جداگانهٔ همان استقرار را می‌خواهد.

## قرارداد الزامی `web_reverse_proxy`

پیکربندی معتبر باید همهٔ این شروط را هم‌زمان داشته باشد:

1. backend روی یک IP literal از Loopback و پورتی غیر از 443 bind شود؛
2. AppUser authentication روشن باشد و Cookie دارای `Secure; HttpOnly; SameSite=Strict` باشد؛
3. `allowed_hosts` و `allowed_origins` دقیق، بدون wildcard و با Origin از نوع HTTPS باشند؛
4. Proxy هم‌میزبان باشد و فقط CIDRهای Loopback در `trusted_proxy_cidrs` قرار گیرند؛
5. Proxy هر Header ورودی `Forwarded`، `X-Forwarded-For/Host/Port/Proto` را حذف/بازنویسی کند؛
6. backend دقیقاً یک `X-Forwarded-Proto: https` و یک IP معتبر در `X-Forwarded-For` بپذیرد؛
7. `Host` اصلی HTTPS حفظ شود و برای همهٔ درخواست‌های unsafe، `Origin` دقیق و CSRF نشست بررسی شود؛
8. اندازهٔ JSON/upload، timeout درخواست، نرخ درخواست/upload و grace shutdown از Config بیایند؛
9. پاسخ‌های Web دارای HSTS باشند؛ readiness هنگام drain برابر 503 و health تا پایان process زنده بماند.

backend، Headerهای forwarded را از کلاینت مستقیم یا Proxy خارج از allowlist نمی‌پذیرد. چند مقدار،
فاصله، زنجیرهٔ چند IP، `Forwarded` استاندارد، `X-Forwarded-Host` و `X-Forwarded-Port` همگی رد
می‌شوند. این محدودیت عمداً قرارداد را ساده و قابل ممیزی نگه می‌دارد.

## نمونهٔ Nginx

این قطعه template است؛ نام دامنه، مسیر certificate و پورت backend را استقرار تعیین می‌کند:

```nginx
server {
    listen 80;
    server_name bridge.example.test;
    return 308 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bridge.example.test;

    ssl_certificate     /deployment/certs/fullchain.pem;
    ssl_certificate_key /deployment/certs/private-key.pem;

    client_max_body_size 128m;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;

        # مقدار خالی در Nginx یعنی Header به upstream فرستاده نشود.
        proxy_set_header Forwarded "";
        proxy_set_header X-Forwarded-Host "";
        proxy_set_header X-Forwarded-Port "";
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;

        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }
}
```

استفاده از `$proxy_add_x_forwarded_for` در این قرارداد مجاز نیست، چون می‌تواند زنجیرهٔ
کنترل‌نشدهٔ ورودی را حفظ کند. Proxy باید یک IP نهایی و پاک‌سازی‌شده بسازد.

## نمونهٔ Caddy

```caddyfile
bridge.example.test {
    reverse_proxy 127.0.0.1:8765 {
        header_up Host {host}
        header_up -Forwarded
        header_up -X-Forwarded-Host
        header_up -X-Forwarded-Port
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-For {remote_host}
    }
}
```

Caddy باید certificate معتبر و redirect پیش‌فرض HTTP به HTTPS را طبق تنظیمات همان محیط مدیریت
کند. پیش از پذیرش، Headerهای واقعی خروجی Caddy باید با تست contract همان نسخه وریفای شوند.

## Health، readiness و shutdown

- `GET /api/v1/health`: liveness محدود و بدون Secret؛
- `GET /api/v1/readiness`: فقط هنگام آماده‌بودن برای درخواست 200؛ در maintenance/shutdown برابر 503؛
- service manager ابتدا readiness را از مدار خارج می‌کند، سپس پذیرش درخواست جدید را می‌بندد و تا
  `shutdown_grace_seconds` برای drain درخواست‌های فعال صبر می‌کند؛
- Proxy باید health checkها را با همان Host و forwarded contract ارسال کند و backend را مستقیماً
  به شبکهٔ بیرونی expose نکند.

## CSRF، Cookie و Origin

Authentication مبتنی بر AppUser session است. Browser فقط Cookie امن را نگه می‌دارد؛ درخواست‌های
تغییردهنده باید `Origin` دقیق HTTPS و CSRF وابسته به همان نشست داشته باشند. wildcard CORS، Origin
خالی برای درخواست unsafe، Cookie بدون Secure و اعتماد به Host دلخواه مجاز نیست.

## Limits و عملیات

`limits` شش کنترل دارد: `max_json_body_bytes`، `max_upload_bytes`،
`request_timeout_seconds`، `requests_per_minute`، `uploads_per_minute` و
`shutdown_grace_seconds`. Proxy باید حد body و timeout سازگار یا سخت‌گیرانه‌تر داشته باشد.
لاگ Proxy نباید Authorization، Cookie، CSRF، query حساس یا body احراز هویت را ثبت کند.

## چک‌لیست پذیرش استقرار نهایی

- DNS/Host/Origin و certificate متعلق به محیط نهایی‌اند؛
- backend فقط Loopback و از بیرون غیرقابل دسترس است؛
- Proxy Headerهای forwarded ورودی را overwrite می‌کند؛
- TLS و redirect 80 به 443 با اسکن مستقل وریفای شده‌اند؛
- Secure cookie، CSRF، HSTS، limits، rate limit، health/readiness و graceful shutdown پاس شده‌اند؛
- Firewall فقط listener واقعی Proxy را طبق نیاز همان محیط باز می‌کند؛
- هیچ ارسال واقعی ایتا یا انتشار WordPress جزو تست استقرار شبکه نیست.

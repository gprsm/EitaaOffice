# گزارش Phase 10-C2 — قرارداد Web روی 80/443 — 2026-08-13

## نتیجه

**C2 در تعریف محیط‌مستقل کامل و پذیرفته شد.** پروفایل `web_reverse_proxy` پیاده‌سازی، مستند و با
fixture محلی TLS terminator/Reverse Proxy و حملات contract آزموده شد. این پذیرش به‌معنای نصب Proxy
یا bind واقعی روی رایانهٔ توسعه نیست.

## قرارداد پیاده‌شده

- backend فقط روی Loopback و پورتی غیر از 443؛
- HTTPS خارجی دقیق با Host/Origin بدون wildcard؛
- AppUser auth اجباری و Cookie با `Secure; HttpOnly; SameSite=Strict`؛
- trusted proxy فقط از CIDRهای Loopback هم‌میزبان؛
- الزام دقیق یک `X-Forwarded-Proto: https` و یک IP پاک‌سازی‌شده در `X-Forwarded-For`؛
- رد `Forwarded`، `X-Forwarded-Host/Port`، زنجیره یا چند مقدار XFF و Proxy خارج allowlist؛
- Origin اجباری برای درخواست unsafe و CSRF وابسته به نشست؛
- HSTS، سقف JSON/upload، timeout، rate limits و grace shutdown پیکربندی‌پذیر؛
- readiness=503 هنگام maintenance/drain و health زنده تا پایان process.

## 80 و 443

- Config پورت 80 را resolve کرد؛ هیچ socket واقعی روی آن باز نشد.
- plain HTTP روی 443 با `deployment_plain_http_443_forbidden` fail-closed شد.
- نمونهٔ Nginx/Caddy، overwrite Headerها، redirect 80→HTTPS و چک‌لیست production در
  `docs/PHASE10_WEB_REVERSE_PROXY_DEPLOYMENT.md` ثبت شد.
- نمونهٔ Config در `bridge.web-reverse-proxy.example.json` قرار گرفت.

## آزمون‌ها

`tests/test_phase10c_web_reverse_proxy_contract.py`:

```text
14/14 passed
```

پوشش شامل Config مثبت/منفی، 80، رد 443، Host/Origin، trusted proxy، spoofing forwarded headers،
Cookie/CSRF/HSTS، body limits، health/readiness و graceful shutdown است. Fixture فقط قرارداد
termination را روی پورت تصادفی Loopback شبیه‌سازی کرد و certificate یا TLS واقعی نصب نکرد.

## عملیات بیرونی انجام‌نشده

Proxy/certificate نصب نشد، Firewall تغییر نکرد، 80/443 bind نشد و هیچ ترافیک Provider/WordPress
واقعی ایجاد نشد.

## دروازهٔ خروج

C2 پذیرفته است. استقرار واقعی TLS در آینده باید چک‌لیست همین سند را روی محیط نهایی دوباره اجرا کند.

# استقرار محصول دفتر روی شبکهٔ خصوصی — توپولوژی مرجع (Laragon Reverse Proxy)

وضعیت: `DEPLOYED_LOCAL_LAN / بازنگری ۲۰۲۶-۰۹-۲۸` — این سند توپولوژی **از قبلِ کاربر** را مستند و حفظ می‌کند.

## توپولوژی مرجع (کانالِ درستِ دسترسی از LAN)

```text
کاربر LAN (مرورگر)
   │  http://192.168.1.2/eitaa/   ← رابط کاربری محصول (کارتابل گزارش‌ها + داشبورد دفتر)
   │  http://192.168.1.2/api/...  ← API (شامل /api/v3/office/*)
   ▼
Apache لاراگون (C:\Users\mohse\laragon، پورت 80)
   │  alias: etc/apache2/alias/eitaa.conf
   │  ProxyPass /eitaa/ → http://127.0.0.1:8765/   و   /api/ → http://127.0.0.1:8765/api/
   │  Host/Origin بازنویسی به http://127.0.0.1:8765 (ProxyPreserveHost Off)
   ▼
EitaaBridge HTTP API + UI  (mode: desktop_loopback، bind: 127.0.0.1:8765)
   └─ AppUser login + صف تأیید انسانی + /api/v3/office/* — همه پشت نشست
```

- این توپولوژی محصول را فقط روی Loopback نگه می‌دارد و مرز LAN را Apache مدیریت می‌کند؛ از دید هسته، همهٔ درخواست‌ها لوکال‌اند.
- مسیرهای معتبر: `/eitaa/` (UI) و `/api/` (API). دقت: مسیر `/eitaaa` (سه «ا») در کانفیگ وجود ندارد؛ `/eitaa` است.
- آزمون بازگشایی 2026-09-28: `/eitaa/` = 200، `/api/v1/health` از مسیر پروکسی = ok، loopback = ok.

## سابقه: آزمون trusted_lan_http و چرا پس گرفته شد

شب ۲۰۲۶-۰۹-۲۷ deployment به `trusted_lan_http` (bind مستقیم 192.168.1.2:8765) تغییر کرد؛ چون قراردادِ Host/Origin دقیق با الگوی پروکسیِ Host-بازنویسی‌شدهٔ لاراگون ناسازگار است، مسیر `/eitaa` می‌شکست و توپولوژی کاری کاربر مقدم است. بنابراین کانفیگ به `desktop_loopback` بازگردانده شد (پشتیبان‌ها در `backups/bridge.json.pre-lan-*.json` و بازگردانی موفق با probes بالا). اسکریپت‌ها و vhostهای آزمونی حذف شدند.

## چیزی که از آن آزمون مفید ماند

1. **مهاجرت coordinator v7→v9** با اسکریپت رسمی (`upgrade_schema_script(7)`) — برای بالاآمدن سرور پس‌زمینه با کد فعلی لازم بود؛ پشتیبان در `backups/coordinator.pre-v9-*.sqlite3`.
2. **میان‌بر Startup** («EitaaBridge Office Server» → `EitaaBridgeBackground.vbs`): سرور پس‌زمینه بعد از ری‌استارت ویندوز خودکار بالا می‌آید تا پروکسی لاراگون همیشه مقصد زنده داشته باشد.
3. UI تولیدی با تب «داشبورد دفتر» بیلد شده و از همان مسیر `/eitaa/` سرو می‌شود؛ `/api/v3/*` هم زیر ProxyPass `/api/` پوشش دارد.
4. درس معماری (ADR): الگوی پروکسیِ Host-بازنویسی‌شدهٔ لاراگون با mode دسکتاپ، مسیر انتخابی این محیط است؛ فعال‌سازی `trusted_lan_http` صرفاً با bind مستقیم معنا دارد و با ProxyPreserveHost Off جمع نمی‌شود.

## چک‌لیست سلامت (برای اپراتور)

```text
1) background server:  scripts\background_server.py status   → running: true
2) مسیر LAN:           http://192.168.1.2/eitaa/              → صفحهٔ ورود/UI
3) API از LAN:         http://192.168.1.2/api/v1/health       → ok:true
4) Apache:             تِی لاراگون / سرویس httpd روی :80
```

# استقرار محصول دفتر روی شبکهٔ خصوصی (trusted_lan_http + Laragon)

وضعیت: `DEPLOYED_LOCAL_LAN / 2026-09-27` — مرجع عملیاتی این استقرار روی این رایانه (سرور ۱۹۲.۱۶۸.۱.۲).

## معماری

```text
کاربر LAN (مرورگر)
   │  http://192.168.1.2:8765   ← مرجع اصلی (Authoritative Origin)
   │  http://eitaaoffice.test/  ← ریدایرکت 308 از Apache لاراگون (پورت 80)
   ▼
EitaaBridge HTTP API + UI  (bind: 192.168.1.2:8765، mode: trusted_lan_http)
   ├─ AppUser login (UI: AppUserGate — /api/v2/app-auth/login)
   ├─ کارتابل گزارش‌ها + تب «داشبورد دفتر» (/api/v3/office/*)
   └─ پشت نشست/CSRF؛ هیچ endpoint بدون احراز هویت به جز health/login
```

- قرارداد امنیتی: `docs/TRUSTED_LAN_HTTP_CONFIGURATION.md` (فاز ۶-A/۶-B) — Host/Origin دقیق، CIDR خصوصی، پذیرش صریح cleartext، بدون CORS عمومی.
- چرا ریدایرکت به‌جای Proxy در Apache؟ قرارداد، Host/Origin را دقیقاً `192.168.1.2:8765` می‌خواهد و headerهای forwarded را رد می‌کند؛ ریدایرکت 308 قرارداد را سالم نگه می‌دارد و URL کوتاه می‌دهد.

## کانفیگ اعمال‌شده (bridge.json → deployment)

- `mode: trusted_lan_http`، `bind: 192.168.1.2:8765`
- `allowed_hosts: ["192.168.1.2:8765"]`، `allowed_origins` همان، `allowed_private_client_cidrs: ["192.168.1.0/24"]`
- دو acknowledgement رسمی + `bootstrap_admin_loopback_only: true` + `same_origin_only: true` + `remote_messenger_auth.enabled: false`
- پشتیبان قبل از تغییر: `backups/bridge.json.pre-lan-*.json`

## مهاجرت Coordinator (لازم برای AppUser auth در سرویس پس‌زمینه)

- پایگاه `data/coordinator/coordinator.sqlite3` از نسخهٔ ۷ به ۹ با اسکریپت رسمی `upgrade_schema_script(7)` ارتقا یافت (ساخت `service_credentials`) و `CoordinatorDatabase.initialize()` سبز شد.
- پشتیبان: `backups/coordinator.pre-v9-*.sqlite3`

## اجرا و پایداری

- سرور پس‌زمینه: `scripts/background_server.py start|status|stop` (لاگ: `runtime/logs/background-server.log`).
- راه‌اندازی خودکار بعد از ری‌استارت ویندوز: میان‌بر «EitaaBridge Office Server» در Startup کاربر (به `EitaaBridgeBackground.vbs`).
- لاراگون: نصب در `C:\laragon`؛ vhost آماده در `deployment/laragon/office.conf` → کپی به `C:\laragon\etc\apache2\sites-enabled\office.conf` و استارت Apache از تِی لاراگون.

## گام یک‌بارمصرف با دسترسی ادمین (اسکریپت آماده: `setup-office-lan.bat`)

۱. اتصال Ethernet ویندوز را Private می‌کند (الان Public است)؛
۲. دو قانون فایروال فقط روی Private + LocalSubnet: TCP 8765 و TCP 80؛
۳. افزودن `192.168.1.2 eitaaoffice.test` به hosts سرور.

## نشانی‌های نهایی برای کاربران شبکهٔ خصوصی

- اصلی: `http://192.168.1.2:8765`
- میان‌بر (بعد از اجرای اسکریپت ادمین + استارت Apache): `http://eitaaoffice.test`
- ورود با حساب‌های AppUser موجود؛ ساخت حساب تازه فقط از خود سرور (bootstrap محدود به loopback).

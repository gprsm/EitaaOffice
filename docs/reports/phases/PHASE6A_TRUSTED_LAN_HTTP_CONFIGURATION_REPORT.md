# گزارش فاز ۶-A: قرارداد Config امن برای HTTP روی LAN خصوصی

تاریخ تکمیل: ۲۰۲۶-۰۸-۰۹  
وضعیت: پیاده‌سازی و آزمون تکمیل شد؛ فعال‌سازی واقعی انجام نشد  
مرز توقف: پایان Phase 6-A؛ Phase 6-B آغاز نشده است

## نتیجهٔ اجرایی

دو حالت استقرار نسخه‌دار ایجاد شد:

- `desktop_loopback`: پیش‌فرض سازگار؛ نبود بخش `deployment` در Config به `127.0.0.1:8765` و سیاست Loopback برمی‌گردد.
- `trusted_lan_http`: فقط با Config صریح، AppUser authentication روشن، IP خصوصی مشخص، Host/Origin/CIDR محدود و دو پذیرش خطر دقیق Load/Start می‌شود.

Config ناقص یا باز به حالت Loopback fallback نمی‌کند و Startup را Fail-closed متوقف می‌کند. CLI نیز دیگر نمی‌تواند Host یا Port متفاوت از Config را تحمیل کند.

هیچ پورت Non-loopback، Firewall rule، Port Forwarding، DMZ یا UPnP در این فاز ایجاد یا فعال نشد. هیچ Feature نصب واقعی روشن نشد و هیچ Login، Logout، OTP، Status، Send، Session rewrite، Migration یا RPC واقعی Provider انجام نشد.

## ممیزی پیش از تغییر

موارد زیر پیش از کدنویسی بررسی شدند:

- Branch: `main` با upstream برابر `origin/main`
- Worktree عمداً dirty با ۲۶ فایل tracked تغییرکرده و مجموعه‌ای از فایل‌های جدید فازهای قبلی
- دو سند انتقال:
  - `../architecture/HTTP_LAN_MULTIUSER_CONTINUATION_REPORT_2026-08-02.md`
  - `../../handoffs/NEXT_CHAT_PROMPT_HTTP_LAN_PHASE6A_2026-08-02.md`
- Config typed و Loader در `src/eitaa_bridge/config.py` و `src/eitaa_bridge/infrastructure/config/loader.py`
- HTTP adapter در `src/eitaa_bridge/interfaces/http_api.py`
- Electron launcher در `ui/electron/main.cjs`
- AppUser auth، Cookie، CSRF و Bootstrap در `src/eitaa_bridge/application/api.py` و Coordinator auth
- Host/Origin loopback gate موجود
- تست‌های Config، AppUser API، HTTP media/upload و runtime ownership
- `bridge.json` واقعی فقط به‌صورت امن و بدون چاپ Secret بررسی شد.

Baseline متمرکز پیش از تغییر:

```text
26 passed
```

فایل‌های dirty قبلی حفظ شدند. هیچ reset، checkout، commit یا push انجام نشد.

## سند canonical معماری

فایل `ARCHITECTURE_DECISIONS.md` ایجاد شد و این تصمیم‌ها را به‌عنوان منبع حقیقت نسخه‌پذیر ثبت کرد:

- `multi-user + multi-account-per-provider + multi-provider`
- هر AppUser دارای صفر تا چند حساب Eitaa/Bale/Rubika/SoroushPlus
- استقلال Session/Worker/Runtime/DB/Cache/Media/Job/Log/Rate-limit برای هر MessengerAccount
- Provider capability-driven و ممنوعیت حدس API/Capability
- Unified Inbox فقط Read/Query aggregation layer و نه ادغام Source of Truth
- WordPress به‌عنوان `AppIntegration` مشترک Application Installation
- یک Domain/API مشترک با `MobileShell` و `DesktopShell` مستقل در Presentation
- قرارداد `desktop_loopback` و `trusted_lan_http` و پذیرش صریح محدودیت HTTP

هیچ کد Unified Inbox، MobileShell کامل یا Provider جدید در این فاز ساخته نشد.

## قرارداد Config فاز ۶-A

بخش جدید `deployment` دارای `schema_version = 1` است و شامل این مفاهیم است:

- `mode`
- `bind.host` و `bind.port`
- `allowed_hosts`
- `allowed_origins`
- `allowed_private_client_cidrs`
- `cleartext_http_risk_acknowledgement`
- `private_lan_only_acknowledgement`
- `bootstrap_admin_loopback_only`
- `same_origin_only`
- `remote_messenger_auth.enabled`
- acknowledgement جداگانهٔ Remote messenger authentication برای فاز احتمالی آینده

دو پذیرش لازم LAN باید دقیقاً این مقادیر باشند:

```text
I_ACCEPT_TRUSTED_LAN_HTTP_WITHOUT_TRANSPORT_SECURITY
I_WILL_NOT_EXPOSE_THIS_SERVICE_TO_PUBLIC_OR_GUEST_NETWORKS
```

این رشته‌ها فقط تصمیم مدیر را صریح می‌کنند و امنیتی معادل HTTPS ایجاد نمی‌کنند.

### موارد Fail-closed آزموده‌شده

- AppUser authentication خاموش یا خاموش‌شده با Environment kill switch
- نبود هر یک از acknowledgementهای LAN
- Bind روی `0.0.0.0` یا IP عمومی
- Host خالی، wildcard، نامعتبر یا متفاوت از Bind
- Origin خالی، wildcard، نامعتبر یا Cross-origin
- CIDR خالی، نامعتبر یا عمومی مانند `0.0.0.0/0`
- Bootstrap غیرLoopback
- `same_origin_only = false`
- Remote messenger authentication بدون acknowledgement جداگانه
- تلاش برای فعال‌سازی Remote messenger authentication در Phase 6-A حتی با acknowledgement
- حذف فیلد لازم از قرارداد نسخه‌دار
- Override متفاوت Host/Port از CLI

Private LAN در نسخهٔ فعلی به RFC1918 IPv4 و IPv6 ULA محدود است. Bind باید یک IP literal خصوصی و مشخص باشد؛ wildcard interface مجاز نیست. حداقل یک CIDR مجاز باید Bind را دربر بگیرد.

## سیاست HTTP request boundary

Gate اولیهٔ Config-driven برای همهٔ GET/POST/OPTIONS، فایل‌های static، media و upload به HTTP adapter افزوده شد:

- Client واقعی فقط از socket address خوانده می‌شود؛ `X-Forwarded-For` مبنای اعتماد نیست.
- `desktop_loopback` فقط Client و Host و Origin loopback را می‌پذیرد.
- `trusted_lan_http` فقط Client داخل CIDRهای Config، Host دقیق و Origin دقیق را می‌پذیرد.
- درخواست تغییردهنده از Client غیرLoopback باید Origin داشته باشد.
- Origin باید با Host همان Request و فهرست Config دقیقاً same-origin باشد.
- هیچ `Access-Control-Allow-Origin` یا wildcard CORS منتشر نمی‌شود.
- Bootstrap مدیر اولیه از Client غیرLoopback با `app_auth_bootstrap_loopback_required` رد می‌شود.
- Request code، submit code، submit password، logout و reset-local-session پیام‌رسان از Client LAN با `remote_messenger_auth_disabled` رد می‌شوند.
- خطا فقط mode و reason code امن دارد؛ IP، Host، Cookie، Token، رمز، OTP یا محتوای خصوصی در payload خطا ثبت نمی‌شود.

سیاست‌های عمیق‌تر Session/Auth و آزمون‌های adversarial کامل، طبق مرز Roadmap در Phase 6-B باقی می‌مانند.

## سازگاری Loopback و Electron

- `bridge.json` واقعی بخش `deployment` ندارد؛ Loader آن را به `desktop_loopback` تبدیل می‌کند.
- Electron launcher همچنان `127.0.0.1:8765` را درخواست می‌کند و با پیش‌فرض سازگار است.
- اگر Config بعداً `trusted_lan_http` باشد، Host ثابت Loopback لانچر Electron با Config یکسان نیست و Startup به‌جای override خاموش و پنهان، Fail-closed می‌شود. Launcher عملیاتی LAN در Phase 6-C طراحی می‌شود.
- تست HTTP واقعی فقط روی Loopback و Port موقت اجرا شد؛ هیچ Socket روی LAN باز نشد.

## نمونه و راهنمای مدیر

- `bridge.trusted-lan-http.example.json`: نمونهٔ کامل بدون Secret با IP مستندی `192.168.1.20/24`
- `docs/TRUSTED_LAN_HTTP_CONFIGURATION.md`: توضیح فارسی فیلدها، ریسک cleartext، DHCP reservation، Guest/AP isolation، Firewall محدود به Subnet و منع Port Forwarding/DMZ/UPnP
- `bridge.example.json` و `bridge.multisite.example.json`: قرارداد صریح `desktop_loopback`

نمونهٔ LAN فقط برای طراحی/بررسی است و در این فاز روی `bridge.json` واقعی کپی یا فعال نشد.

## فایل‌های تغییرکرده در Phase 6-A

فایل‌های tracked که این فاز به تغییرات موجود آن‌ها افزود:

- `bridge.example.json`
- `bridge.multisite.example.json`
- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/interfaces/http_api.py`
- `tests/test_config.py`

فایل‌های جدید این فاز:

- `ARCHITECTURE_DECISIONS.md`
- `bridge.trusted-lan-http.example.json`
- `docs/TRUSTED_LAN_HTTP_CONFIGURATION.md`
- `tests/test_phase6a_trusted_lan_http.py`
- `PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md`

فایل `ui/electron/main.cjs` ممیزی و syntax آن بررسی شد، اما تغییرات موجود آن متعلق به فازهای قبلی است و Phase 6-A خطی به آن اضافه نکرد.

## نتیجهٔ آزمون و کنترل کیفیت

### متمرکز نهایی

```text
48 passed
```

شامل Config، AppUser HTTP/API، media/upload و ۲۲ تست جدید Phase 6-A.

### کل مجموعه بدون فیلتر

```text
388 collected
387 passed
1 failed
```

تنها شکست:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

### کل مجموعه با کنارگذاشتن فقط baseline تاریخی

```text
387 passed, 1 deselected
```

### اجرای منفرد baseline

```text
1 failed
```

Fixture مقدار لاتین زیر را تولید می‌کند:

```text
C:\Users\ExampleUser\Documents\Eitaa\runtime\edge-profile
```

اما Assertion انتظار suffix فارسی `Documents\ایتا\runtime\edge-profile` دارد. `tests/test_runtime_ownership.py` و ماژول Office runtime مربوط به آن در Phase 6-A تغییر نکرده‌اند؛ `git diff` برای این فایل‌ها خالی بود. بنابراین این شکست مستقل و همان baseline تاریخی است.

کنترل‌های دیگر:

- `compileall`: موفق
- `git diff --check`: موفق
- اعتبار نمونه‌های Loopback و LAN: موفق
- `node --check ui/electron/main.cjs`: موفق
- بررسی عدم وجود CORS header عمومی: موفق

Pytest فقط هشدار غیرعملکردی Permission برای نوشتن `.pytest_cache` قدیمی Repository داد. `basetemp` همهٔ اجراها خارج از دادهٔ واقعی پروژه و در Workspace موقت Codex قرار داشت.

## وضعیت Feature Flag و نصب واقعی در پایان

خلاصهٔ امن Loader روی `bridge.json` واقعی:

```json
{
  "deployment_mode": "desktop_loopback",
  "bind_host": "127.0.0.1",
  "bind_port": 8765,
  "app_user_auth_enabled": false,
  "multi_session_enabled": false,
  "remote_messenger_auth_enabled": false
}
```

- خود `bridge.json` تغییر نکرد.
- هیچ Feature Flag واقعی روشن نشد.
- Contacts/Coordinator/Session/Runtime واقعی تغییر یا مهاجرت نکرد.
- هیچ Login/Logout/Send واقعی و هیچ API برای Bale/Rubika/SoroushPlus ساخته نشد.
- هیچ Dependency نصب نشد.
- هیچ Commit یا Push انجام نشد.

## ریسک‌های باقی‌مانده و مرز Phase 6-B

HTTP همچنان در برابر شنود و دست‌کاری مسیر شبکه محرمانگی یا اصالت ایجاد نمی‌کند. Host/Origin/CIDR، CSRF و Cookie flags این ریسک انتقال را حذف نمی‌کنند.

موارد زیر عمداً برای Phase 6-B باقی ماندند:

- ممیزی و تکمیل Session rotation و دفاع در برابر fixation
- logout-all، revoke و timeoutهای LAN
- rate limit/lockout adversarial برای Login
- آزمون کامل CSRF روی همهٔ مسیرهای تغییردهنده
- سخت‌سازی Cookie/Cache-Control/CSP/Permissions headers برای LAN HTTP
- محدودیت request/upload و abuse controls
- آزمون جعل Host/Origin، Cross-user، brute force و Session isolation با دو Client
- سیاست امن device/session metadata بدون IP/Token کامل

سرو UI/API واقعی روی LAN، Launcher ویندوز، Health/Readiness عملیاتی و طرح Firewall همچنان Phase 6-C هستند و نباید در Phase 6-B با آن‌ها ادغام شوند.

## دستور دقیق شروع Phase 6-B

```text
فاز ۶-B پروژه Eitaa Bridge را اجرا کن. ابتدا ARCHITECTURE_DECISIONS.md و PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md را کامل بخوان و Worktree dirty را حفظ کن. فقط Auth/Session/CSRF/Host-Origin و HTTP hardening حالت trusted_lan_http را طبق مرز ثبت‌شده تکمیل و با دو Client شبیه‌سازی‌شده آزمون کن؛ هیچ پورت یا Firewall rule واقعی باز نکن، Featureهای bridge.json واقعی را فعال نکن، دادهٔ واقعی را مهاجرت نده، هیچ Login/Logout/OTP/Send واقعی و هیچ API فرضی Provider جدید نساز، و commit/push نکن. در پایان گزارش مستقل Phase 6-B را بساز و متوقف شو.
```

فاز ۶-A در این نقطه پایان یافته است.

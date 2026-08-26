# گزارش فاز ۶-C: سرویس‌دهی Windows/LAN و عملیات

تاریخ تکمیل: ۲۰۲۶-۰۸-۱۱  
وضعیت: پیاده‌سازی و آزمون تکمیل شد؛ فعال‌سازی واقعی انجام نشد  
مرز توقف و بازبینی: پایان Phase 6-C؛ ورود به Phase 6-D فقط پس از ثبت این Closeout

## نتیجهٔ اجرایی

مسیر عملیاتی `trusted_lan_http` برای Windows بدون تغییر نصب واقعی تکمیل شد. لانچر جدید Host/Port را فقط از Config معتبر می‌گیرد، پیش از Bind حالت LAN و Build تولیدی UI را Fail-closed بررسی می‌کند، با Lock سیستم‌عاملی از اجرای هم‌زمان نمونهٔ دوم جلوگیری می‌کند و پس از توقف یا Crash امکان Start مجدد کنترل‌شده دارد.

Health و Readiness از هم جدا شدند. Health فقط زنده‌بودن Application را با Payload حداقلی اعلام می‌کند؛ Readiness فقط هنگام پذیرش Request موفق است و در حالت not-ready/shutdown با `503` پاسخ می‌دهد. اطلاعات Site، Scheduler، Secret، Token، Cookie، Phone، Provider session، محتوای خصوصی و مسیر فایل از Payload عملیاتی حذف شدند.

ابزار Firewall صرفاً Plan JSON و PowerShell preview محدود به IP، Port و CIDRهای خود Config، پروفایل Private و TCP inbound تولید می‌کند. هیچ Rule، Port، Service، Router، Feature flag یا Config واقعی اعمال یا فعال نشد.

## Baseline پیش از تغییر

اسناد لازم‌الاجرا کامل خوانده شدند:

- `ARCHITECTURE_DECISIONS.md`
- `PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md`
- `PHASE6B_LAN_HTTP_AUTH_SESSION_HARDENING_REPORT.md`
- متن انتقال و Scope صریح Phase 6-C

Worktree از قبل عمداً dirty بود. `src/eitaa_bridge/infrastructure/diagnostics/redaction.py` پیش و پس از کار `untracked but not ignored` باقی ماند. هیچ `reset`، `checkout`، `git add`، `commit` یا `push` انجام نشد.

Baseline متمرکز پایان Phase 6-B پیش از تغییر:

```text
73 passed
```

Baseline تاریخی Full suite پیش از ۶-C طبق گزارش ۶-B:

```text
400 collected; 399 passed; 1 failed
```

## فایل‌های اصلی ممیزی‌شده

- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/interfaces/http_api.py`
- `src/eitaa_bridge/application/api.py`
- `ui/electron/main.cjs`
- `scripts/office_runtime.py`
- `run_api.bat`
- `run_api_health.bat`
- `stop_eitaa_bridge.bat`
- `EitaaBridge.bat`
- تست‌های Config، HTTP، Runtime ownership و فازهای ۶-A/۶-B

## فایل‌های تغییرکرده یا جدید در Phase 6-C

تغییرکرده:

- `ARCHITECTURE_DECISIONS.md`
- `docs/TRUSTED_LAN_HTTP_CONFIGURATION.md`
- `pyproject.toml`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/interfaces/http_api.py`

جدید:

- `src/eitaa_bridge/infrastructure/windows_lan.py`
- `src/eitaa_bridge/interfaces/windows_lan.py`
- `EitaaBridgeLanServer.bat`
- `tests/test_phase6c_windows_lan_serving_operations.py`
- `PHASE6C_WINDOWS_LAN_SERVING_OPERATIONS_REPORT.md`

## مدل سرویس‌دهی Windows/LAN

جریان معتبر:

```text
bridge.json / explicit config
  -> BridgeConfigLoader + fail-closed validation
  -> trusted_lan_http mode check
  -> production UI index.html check
  -> OS-backed single-instance lock
  -> HTTP server bind from deployment.bind only
  -> readiness=ready
  -> serve UI/API same-origin
  -> readiness=not_ready on shutdown
  -> server close + lock release
```

لانچر گزینهٔ Host/Port ندارد و نمی‌تواند قرارداد استقرار را Override کند. `http_api` نیز Overrideهای سازگاری قدیمی را فقط در صورت تطابق دقیق با Config می‌پذیرد. Config ناقص LAN به Loopback fallback نمی‌کند.

## تصمیم Launcher/Service lifecycle

سه عمل ارائه شد:

```text
check
firewall-plan
start
```

- `check` فقط Config و UI build را بررسی می‌کند و Socket باز نمی‌کند.
- `firewall-plan` فقط Plan چاپ/ذخیره می‌کند و هیچ فرمانی اجرا نمی‌کند.
- `start` تنها پس از Validation و Lock موفق، HTTP server موجود را اجرا می‌کند.

Lock از یک Guard سیستم‌عاملی مستقل و Metadata قابل‌خواندن استفاده می‌کند. Crash قفل سیستم‌عامل را آزاد می‌کند؛ Metadata باقی‌مانده stale محسوب و در اجرای بعدی اتمیک جایگزین می‌شود. نمونهٔ دوم هم در همان Process و هم در Process جدا Fail-closed رد می‌شود. Restart مدل stop-then-start دارد.

نصب Windows Service واقعی عمداً انجام نشد. فرمان `start` برای اجرای Console یا میزبانی آینده زیر Service manager مناسب است، اما ثبت Service، دسترسی Administrator و Recovery policy نصب به Rollout صریح موکول شد.

تعارض Port از Bind failure عمومی جدا و با code امن `port_conflict` گزارش می‌شود؛ IP یا Path در خطای Console افشا نمی‌شود.

## قرارداد Health و Readiness

```text
GET /api/v1/health
GET /api/v1/readiness
```

Health:

- `200`
- `status=alive`
- فقط Versionهای عمومی Application/API/Core

Readiness:

- `200`, `status=ready` هنگام پذیرش Request
- `503`, `status=not_ready` در maintenance/shutdown/stopped
- فقط `deployment_mode` و reason code محدود و امن

هر دو Endpoint همچنان از Host/Origin/CIDR boundary عبور می‌کنند و Bearer اختیاری موجود در Application API نیز دور زده نمی‌شود. پاسخ‌ها `no-store` هستند.

## طرح Windows Firewall

Plan تولیدی فقط این مقادیر معتبر را دارد:

```text
Direction      Inbound
Action         Allow
Profile        Private
Protocol       TCP
EdgeTraversal  Block
LocalAddress   deployment.bind.host
LocalPort      deployment.bind.port
RemoteAddress  deployment.allowed_private_client_cidrs
```

Plan دارای `execution_performed=false` و `requires_explicit_administrator_confirmation=true` است. در mode Loopback تولید Plan رد می‌شود. Config validator نیز wildcard، Public IP/CIDR، `0.0.0.0` و `0.0.0.0/0` را پیش‌تر Fail-closed رد می‌کند.

اجرای واقعی `New-NetFirewallRule`، حذف Rule، تغییر Profile، Port Forwarding، DMZ، UPnP یا Router در این فاز انجام نشد.

## تصمیم Rate/Upload عملیاتی

مقادیر امن Phase 6-B تغییر نکردند:

```text
240 requests / 60 sec / socket IP
12 uploads / 60 sec / socket IP
128 MiB upload
2 MiB JSON
```

برای lifecycle فاز ۶-C نیازی به Configurable کردن آن‌ها نبود. افزودن Config عملیاتی بدون قرارداد نسخه‌دار می‌توانست hardening را تضعیف کند؛ بنابراین این مقادیر ثابت باقی ماندند و هر تغییر آینده باید با minimum/maximum امن و Migration نسخه‌دار انجام شود.

## نتایج آزمون

Dedicated Phase 6-C:

```text
7 passed
```

Focused نهایی شامل Config، Application API، Auth، HTTP media، ۶-A، ۶-B، ۶-C و Diagnostics:

```text
113 passed in 10.20s
```

Full suite:

```text
407 collected
406 passed
1 failed
```

Full suite با کنارگذاشتن فقط baseline تاریخی:

```text
406 passed, 1 deselected in 25.16s
```

کنترل‌های دیگر:

```text
compileall: passed
node --check ui/electron/main.cjs: passed
git diff --check: passed
real bridge.json LAN check: fail-closed as desktop_loopback
example Firewall plan generation: passed; execution_performed=false
```

تنها شکست Full suite همان baseline تاریخی بدون تغییر است:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

Fixture هنوز `Documents\Eitaa\runtime\edge-profile` تولید می‌کند و Assertion suffix فارسی `Documents\ایتا\runtime\edge-profile` می‌خواهد. فایل‌های مرتبط با این شکست در ۶-C تغییر نکردند.

## وضعیت نصب و Featureهای واقعی

خلاصهٔ امن Loader روی `bridge.json` واقعی در پایان:

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

`bridge.json` واقعی تغییر نکرد. هیچ LAN socket واقعی، Firewall rule، Windows Service، AppUser activation، Multi-session activation، Login/OTP/Send واقعی، Migration داده یا Provider جدید ایجاد نشد. Socketهای آزمون فقط Loopback و Port موقت بودند و فایل‌های Lock آزمون فقط زیر Temporary directory ساخته شدند.

## ریسک‌های باقی‌مانده و موارد انتقالی به ۶-D

- HTTP همچنان transport security ندارد و برای شبکهٔ غیرقابل‌اعتماد مناسب نیست.
- نصب Service و Firewall واقعی نیازمند Rollout، Administrator confirmation و تست روی Installation هدف است.
- پذیرش هم‌زمان چند Browser/Mobile client، رفتار Responsive/Touch، Session isolation مرورگرها، reconnect و عملیات طولانی زیر concurrency مربوط به ۶-D است.
- MobileShell کامل و Unified Inbox همچنان در مرز Phase 9 باقی می‌مانند؛ ۶-D فقط Foundation و Acceptance لازم Phase 6 را انجام می‌دهد.

## دستور کوتاه Phase 6-D

```text
فاز ۶-D را اجرا کن: ابتدا ARCHITECTURE_DECISIONS.md و گزارش ۶-C را کامل بخوان، Worktree و bridge.json واقعی را حفظ کن، و فقط Mobile/LAN concurrency acceptance، responsive/touch foundation، چند Browser session مستقل، reconnect و عدم اختلال عملیات هم‌زمان را تکمیل و تست کن؛ MobileShell کامل، Unified Inbox، Provider جدید، Firewall/Port واقعی، Login/OTP/Send واقعی، commit و push انجام نده و در پایان گزارش مستقل ۶-D بساز.
```

Phase 6-C completed.  
Phase 6-D NOT started.

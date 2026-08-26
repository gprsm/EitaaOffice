# گزارش فاز ۷-C: Supervisor، Crash و Recovery فرایند حساب

تاریخ: ۲۰۲۶-۰۸-۱۱

وضعیت: تکمیل‌شده و آزموده‌شده پشت Feature Flag پیش‌فرض خاموش

مرز گزارش: پایان Phase 7-C؛ Phase 7-D هنوز آغاز نشده است

## نتیجهٔ اجرایی

برای هر `EitaaProcessRuntime` یک Supervisor اختصاصی Parent ساخته شد. Supervisor با RPC احرازشدهٔ `worker.heartbeat` زنده‌بودن Child را کنترل می‌کند، Heartbeat را با Fence دقیق در Coordinator ثبت می‌کند، Exit یا عبور از سقف Failure را تشخیص می‌دهد و فقط همان حساب را وارد Recovery می‌کند.

Fence سه‌جزئی `worker_instance_id + worker_generation + process_id` در دو مرز اعمال می‌شود:

- Child تمام درخواست‌های Runtime، Health، Heartbeat و Stop پس از Start را با Worker ID و Generation خودش تطبیق می‌دهد.
- Coordinator، Heartbeat و Crash را فقط برای همان Worker ID، Generation و PID ثبت می‌کند.

Generation قدیمی پس از Replacement نمی‌تواند Heartbeat، Crash یا Stop نسل جدید را ثبت کند.

## Crash، Backoff و Quarantine

خروج واقعی Process یا Heartbeat failure بیش‌ازحد این چرخه را اجرا می‌کند:

```text
detect -> fence -> terminate channel/process -> record crash
       -> bounded exponential backoff -> spawn next generation
       -> quarantine when restart budget is exhausted
```

- `runtime_state` نسل خراب به `crashed` تغییر می‌کند.
- `stopped_at`، `retry_not_before`، `exit_code` و `safe_reason_code` ثبت می‌شوند.
- Backoff نمایی از مقدار اولیه تا سقف Config محدود است.
- تعداد Crashها در پنجرهٔ زمانی نسخه‌دار محاسبه می‌شود.
- پس از عبور از `max_restarts`، حساب به `lifecycle_state=quarantined` و `desired_worker_state=stopped` می‌رود و Restart خودکار متوقف می‌شود.
- Backoff و Lifecycle پیش از Spawn و دوباره داخل تراکنش Start کنترل می‌شوند.
- هیچ Auth transition، Logout یا Session generation change هنگام Crash انجام نمی‌شود.

## قرارداد Config Supervisor

فیلدهای افزوده‌شده به `features.worker_process` نسخهٔ ۱:

```json
{
  "heartbeat_interval_seconds": 5,
  "heartbeat_timeout_seconds": 15,
  "heartbeat_failure_threshold": 3,
  "restart_window_seconds": 300,
  "max_restarts": 3,
  "backoff_initial_seconds": 2,
  "backoff_max_seconds": 60,
  "quarantine_seconds": 300
}
```

تمام فیلدها کران و نوع صریح دارند. Deadline باید از interval بزرگ‌تر و سقف Backoff باید حداقل برابر مقدار اولیه باشد. هر مقدار نامعتبر کل Worker-process feature را Fail-closed خاموش می‌کند. نمونه‌پیکربندی‌ها به‌روزرسانی شدند، اما مقادیر واقعی همچنان `enabled: false` هستند.

## Duplicate worker و Stale lease

- Coordinator در تراکنش `BEGIN IMMEDIATE` هر Worker فعال در حالت starting/ready/busy/rate_limited/stopping را برای PID متفاوت رد می‌کند.
- Registry دوم پیش از Spawn، PID زندهٔ Worker اول را با API بومی Windows تشخیص می‌دهد و Fail-closed رد می‌شود.
- تشخیص PID در Windows با `OpenProcess + GetExitCodeProcess` انجام می‌شود؛ Access denied به‌معنای Process بالقوه زنده است و فقط PID قطعاً نامعتبر Dead محسوب می‌شود.
- پس از Kill، Lock باقی‌مانده فقط وقتی PID آن قطعاً Dead باشد آرشیو می‌شود و Child نسل جدید Lease تازه می‌گیرد.

## استقلال حساب‌ها

آزمون واقعی دو حساب نشان داد:

- Kill حساب A فقط Worker A را `crashed` می‌کند.
- حساب A پس از Backoff با PID، Worker ID و Generation جدید برمی‌گردد.
- PID، Health، Scheduler و Runtime حساب B بدون تغییر باقی می‌مانند.
- Auth state حساب A و B تغییر نمی‌کند.
- Quarantine حساب A، حساب B را Stop یا Logout نمی‌کند.

## Shutdown و Restart کنترل‌شده

Registry هنگام Shutdown ابتدا Recovery را غیرفعال و Supervisorها را متوقف می‌کند، سپس `worker.stop` fenced را می‌فرستد. خروج تمیز Worker با `stopped` ثبت می‌شود و Restart ناخواسته رخ نمی‌دهد. ساخت Registry جدید روی همان Coordinator یک Child و Generation جدید تمیز می‌سازد.

## لاگ‌های امن جدید

```text
eitaa_process_supervisor_started
eitaa_process_heartbeat_failed
eitaa_process_heartbeat_recovered
eitaa_process_worker_fenced
eitaa_process_recovery_decided
eitaa_process_restart_succeeded
eitaa_process_restart_failed
eitaa_process_recovery_callback_failed
```

لاگ‌ها فقط شناسهٔ حساب/Worker، Generation، شمارنده، Reason code، Exit code و نوع خطا را دارند. Session، Phone، Token، Secret، OTP، Payload و Traceback ثبت نمی‌شوند.

## فایل‌های اصلی Phase 7-C

- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `src/eitaa_bridge/infrastructure/coordinator/__init__.py`
- `src/eitaa_bridge/application/account_runtime.py`
- `src/eitaa_bridge/application/process_runtime.py`
- `src/eitaa_bridge/application/eitaa_provider_worker.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/error_taxonomy.py`
- `tests/test_phase7c_process_supervisor.py`
- `bridge.example.json`
- `bridge.multisite.example.json`
- `bridge.trusted-lan-http.example.json`
- `docs/WORKER_IPC_PROTOCOL.md`
- `ARCHITECTURE_DECISIONS.md`
- `PHASE7C_PROCESS_SUPERVISOR_RECOVERY_REPORT_2026-08-11.md`

## نتیجهٔ آزمون و کنترل کیفیت

Dedicated Phase 7-C:

```text
5 passed
```

Focused Phase 4-D/7-A/7-B/7-C و Coordinator/Config/Runtime:

```text
69 passed
```

Full repository:

```text
432 collected
432 passed
```

کنترل‌های تکمیلی:

```text
compileall src + tests: passed
git diff --check: passed
actual Child kill and restart: passed
actual two-account isolation during crash: passed
duplicate live worker rejection: passed
stale lease recovery: passed
restart-budget quarantine: passed
controlled shutdown/restart: passed
```

## Side effectها و وضعیت نصب واقعی

- `bridge.json` واقعی تغییر نکرد و Worker process واقعی آن فعال نشد.
- هیچ Login، Logout، OTP، Sync یا Send واقعی انجام نشد.
- هیچ دادهٔ Coordinator/Session/Contact/Cache/Media/Log واقعی مهاجرت نشد.
- هیچ Port، Firewall rule، Service یا Router setting تغییر نکرد.
- هیچ Dependency نصب نشد.
- هیچ Stage، Commit یا Push انجام نشد.
- آزمون‌های Kill فقط Childهای موقت داخل مسیرهای Pytest را هدف گرفتند.

## مرز Phase 7-D

Phase 7-D باید آزمون‌های خصمانهٔ Process isolation را تکمیل کند: Kill واقعی Fake worker، Lock contention واقعی، duplicate spawn race، IPC signature/scope/replay/response tampering، Fence قدیمی، عدم اشتراک Session/Scheduler/DB/Cache/Log، اسکن stdout/stderr/log/report برای Secret و گزارش نهایی کل Phase 7.

Phase 7-C completed.

Phase 7-D NOT started.

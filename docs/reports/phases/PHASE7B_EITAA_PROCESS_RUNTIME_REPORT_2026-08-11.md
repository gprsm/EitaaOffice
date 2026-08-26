# گزارش فاز ۷-B: انتقال Runtime ایتا به Child process حساب‌محور

تاریخ: ۲۰۲۶-۰۸-۱۱

وضعیت: تکمیل‌شده و آزموده‌شده پشت Feature Flag پیش‌فرض خاموش

مرز گزارش: پایان Phase 7-B؛ Phase 7-C و 7-D آغاز نشده‌اند

## نتیجهٔ اجرایی

مالکیت Runtime هر `MessengerAccount` ایتا به یک Child process اختصاصی منتقل شد. Parent اکنون فقط Control plane، Coordinator و Proxy مبتنی بر DTO را نگه می‌دارد و در حالت فعال‌بودن Process isolation، Runtime قدیمی را حتی به‌صورت موقت نمی‌سازد.

هر Child شناسهٔ حساب، Provider، Secret یک‌بارمصرف و Config را از Bootstrap نسخهٔ ۱ دریافت می‌کند. PID واقعی Python Child پس از Handshake اعتبارسنجی و در Coordinator ثبت می‌شود؛ این موضوع در Windows مهم است، زیرا PID لانچر محیط مجازی می‌تواند با PID مفسر Child متفاوت باشد.

Startup هیچ Login، Logout، OTP، Sync، Send یا اتصال Provider واقعی اجرا نمی‌کند. Core تا نخستین عملیات Provider در همان Child deferred است. بنابراین Session، Core، Provider DB، Scheduler، Cache، Media، Job state، Lease و Log حساب یا در Child ساخته می‌شوند یا تا نیاز واقعی ساخته نمی‌شوند؛ هیچ‌یک در Parent مالکیت نمی‌شوند.

## Feature Flag نسخه‌دار

قرارداد جدید:

```json
{
  "features": {
    "worker_process": {
      "schema_version": 1,
      "enabled": false,
      "startup_timeout_seconds": 15,
      "request_timeout_seconds": 60
    }
  }
}
```

- نبود بخش `worker_process` دقیقاً به حالت خاموش امن برمی‌گردد.
- Schema ناشناخته، نوع نامعتبر، Timeout خارج از بازه یا `multi_session` غیرفعال، قابلیت را Fail-closed خاموش می‌کند.
- Kill switch محیطی `BRIDGE_FORCE_DISABLE_WORKER_PROCESS` قابلیت را بدون تغییر Config خاموش می‌کند.
- خاموش‌بودن Flag مسیر درون‌فرایندی Legacy را حفظ می‌کند.
- `bridge.json` واقعی تغییر نکرد و هنگام پایان Phase نیز `worker_process.enabled=False` بود.

## مرز مالکیت Parent و Child

| جزء | Parent | Child حساب |
| --- | --- | --- |
| Coordinator و AppUser authorization | مالک | DTO نتیجه را دریافت می‌کند |
| Process control و correlation | مالک | پاسخ امضاشده می‌دهد |
| Eitaa Core و Session | ممنوع | مالک؛ Core به‌صورت deferred |
| Provider database و path contract | فقط نام/summary امن | مالک |
| Scheduler و callback | فقط snapshot DTO؛ callback ممنوع | مالک |
| Cache، Media، Upload و Job state | دسترسی مستقیم ممنوع | مالک |
| Account log و Diagnostics | فقط application log عمومی | مالک account scope |
| Provider object، raw peer و access hash | ممنوع | از IPC خارج نمی‌شود |

Runtime Proxy در Parent برای mutable provider fields خطای امن `eitaa_process_parent_state_forbidden`، برای Python callback خطای `eitaa_process_callback_not_serializable` و برای فایل بدون Transfer RPC خطای `eitaa_process_file_transfer_ipc_required` می‌دهد.

## RPCهای Eitaa در Phase 7-B

```text
worker.hello
worker.health
eitaa.runtime.start
eitaa.runtime.describe
eitaa.runtime.core_probe
eitaa.runtime.refresh_generation
eitaa.runtime.close_core
worker.stop
```

`runtime.start` فقط DTO محدود `MessengerAccountRuntimeRecord` و `worker_instance_id` را می‌پذیرد. Scope حساب/Provider، UUIDها، lifecycle، desired state، generation و storage revision در Child دوباره اعتبارسنجی می‌شوند. پاسخ‌های Runtime فقط summary امن، PID، وضعیت Core و نام فایل/پوشه را می‌دهند و مسیر مطلق، Phone، Session، Secret، Token یا Provider object برنمی‌گردانند.

API وضعیت Scheduler به snapshot راه دور متصل شد. مسیرهای Provider که هنوز RPC اختصاصی DTO/opaque-reference ندارند، هنگام روشن‌بودن Flag با `eitaa_process_operation_ipc_required` Fail-closed رد می‌شوند. این محدودیت مانع بازگشت ناخواسته به Core یا mutable state در Parent است. مسیر Legacy با Flag خاموش همان رفتار قبلی را دارد.

## استقلال حساب‌ها و توقف تمیز

- برای دو حساب هم‌زمان، دو PID، دو Path contract، دو Lease و دو Scheduler مستقل ساخته می‌شوند.
- قفل Worker شناسهٔ حساب و PID واقعی Child را نگه می‌دارد.
- توقف عادی یک حساب، Child و Lease همان حساب را می‌بندد و Child حساب دیگر سالم و پاسخ‌گو می‌ماند.
- Secret bootstrap پس از مصرف حذف می‌شود و در summary یا stderr ظاهر نمی‌شود.
- Parent هیچ shared Eitaa Core برای Runtimeهای Process-isolated نگه نمی‌دارد.

## فایل‌های Phase 7-B

فایل‌های اصلی جدید:

- `src/eitaa_bridge/application/process_runtime.py`
- `src/eitaa_bridge/application/eitaa_provider_worker.py`
- `tests/test_phase7b_eitaa_process_runtime.py`
- `PHASE7B_EITAA_PROCESS_RUNTIME_REPORT_2026-08-11.md`

فایل‌های اصلی به‌روزشده:

- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/application/account_runtime.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/application/provider_adapter.py`
- `src/eitaa_bridge/application/fake_provider_worker.py`
- `src/eitaa_bridge/interfaces/provider_worker.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/error_taxonomy.py`
- `bridge.example.json`
- `bridge.multisite.example.json`
- `bridge.trusted-lan-http.example.json`
- `docs/WORKER_IPC_PROTOCOL.md`
- `ARCHITECTURE_DECISIONS.md`
- `tests/test_phase7a_worker_ipc_protocol.py`

## نتیجهٔ آزمون و کنترل کیفیت

Dedicated Phase 7-B:

```text
6 passed
```

Focused compatibility شامل Config، Account runtime، Phase 4-D و Phase 7-A:

```text
44 passed
```

Full repository بدون حذف یا xfail جدید:

```text
427 collected
427 passed
```

کنترل‌های تکمیلی:

```text
compileall src + tests: passed
git diff --check: passed
example JSON parse: passed
old absolute project path matches: 0
real bridge.json worker_process enabled: false
```

## ممیزی مخزن و Side effectها

- مسیر پروژه قابل نوشتن بود و تمام تغییرات در مسیر جدید انجام شدند.
- Branch برابر `main` و upstream برابر `origin/main` است.
- Worktree از فازهای قبلی عمداً dirty و دارای فایل‌های tracked/untracked بود؛ هیچ reset، checkout یا بازنویسی تغییرات قبلی انجام نشد.
- چهار گزارش Phase 6-A تا 6-D دوباره موجود و قابل خواندن تأیید شدند.
- اسکن مسیر مطلق قدیمی نتیجه‌ای نداشت.
- `bridge.json` واقعی، Session، Coordinator واقعی، Contact، Cache، Media و Log واقعی مهاجرت یا بازنویسی نشدند.
- هیچ Login، Logout، OTP، Sync یا Send واقعی انجام نشد.
- هیچ Port، Firewall rule، Windows Service یا Router setting تغییر نکرد.
- هیچ Dependency جدیدی نصب نشد.
- هیچ Stage، Commit یا Push انجام نشد.

## مرز صریح Phase 7-C

Phase 7-C باید Supervisor پیوسته را اضافه کند: Heartbeat و deadline، Fencing، تشخیص Exit، Crash recovery، duplicate-worker rejection بین Processها، restart budget، Quarantine/Backoff و reconciliation وضعیت Coordinator. این فاز نباید قرارداد Fail-closed فعلی را دور بزند و قبل از آن نیز هیچ Rollout واقعی مجاز نیست.

آزمون Kill/Tampering گسترده و سخت‌سازی تکمیلی متعلق به Phase 7-C/7-D است. این موارد در Phase 7-B اجرا یا شبیه‌سازی نشدند.

Phase 7-B completed.

Phase 7-C NOT started.

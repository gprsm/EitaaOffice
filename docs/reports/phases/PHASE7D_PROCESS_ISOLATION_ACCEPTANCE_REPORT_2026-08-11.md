# گزارش فاز ۷-D: پذیرش خصمانهٔ Process isolation

تاریخ: ۲۰۲۶-۰۸-۱۱

وضعیت: تکمیل‌شده و آزموده‌شده

مرز گزارش: پایان Phase 7-D و پایان کامل Phase 7

## نتیجهٔ اجرایی

مرز Parent/Child با Workerهای واقعی اما دادهٔ آزمایشی تحت Kill، Lock contention، Race، جعل IPC و اسکن Secret قرار گرفت. همهٔ سناریوها Fail-closed عمل کردند و هیچ خرابی از یک حساب به حساب دیگر، Coordinator state نسل جدید یا مسیرهای حساب دیگر سرایت نکرد.

## ماتریس پذیرش

| سناریو | نتیجهٔ مورد انتظار | نتیجه |
| --- | --- | --- |
| Kill واقعی Fake worker | خروج Process و حذف Bootstrap secret | موفق |
| Kill واقعی Eitaa Child آزمایشی | Fence، Crash record و Recovery فقط همان حساب | موفق |
| Signature tampering | `ipc_authentication_failed` بدون Payload/Traceback | موفق |
| Scope tampering | رد Envelope با پاسخ امضاشدهٔ امن | موفق |
| Replay nonce | `ipc_replay_detected` | موفق |
| ۸ Failure احراز متوالی | خروج Fail-closed با `ipc_authentication_failure_limit` | موفق |
| Response امضاشده اما unsolicited | رد correlation و Terminate فوری Child | موفق |
| Fence نسل قدیمی | `eitaa_process_fence_mismatch` | موفق |
| Lock contention دو Child | `eitaa_worker_lease_held` و سالم‌ماندن مالک اول | موفق |
| Race دو Registry برای Spawn | دقیقاً یک Worker generation | موفق |
| دو حساب هم‌زمان | PID و تمام مسیرهای Runtime مستقل | موفق |
| اسکن Secret تولیدشده | نبود Secret در stdout/stderr/log/config/runtime files | موفق |

## سخت‌سازی Parent response stream

- هر خط stdout حداکثر اندازهٔ IPC نسخهٔ ۱ را دارد.
- صف Response کران‌دار است و Flood نامحدود حافظه ممکن نیست.
- خط بیش‌ازحد بزرگ یا Queue overflow کانال را نامعتبر می‌کند.
- امضای Response نامعتبر، Envelope نامعتبر یا correlation/method mismatch باعث Terminate فوری Child می‌شود.
- پس از desynchronization هیچ Request دیگری روی همان stream پذیرفته نمی‌شود.
- stderr با خط‌های کران‌دار خوانده می‌شود و فقط Error code مطابق قرارداد نگه‌داری می‌شود.

## اثبات عدم اشتراک حساب‌ها

دو Child واقعی و هم‌زمان برای دو MessengerAccount ساخته شدند و این موارد برای هر حساب متفاوت بودند:

- PID و Worker generation
- Account data/runtime root
- Session directory و Session filename
- Core database و Media directory
- Provider state و Sender directory database
- Content index path و Dialog/Contact peer paths
- Worker diagnostics، Log، Lock و Cache directory
- Scheduler worker identity

Core/Session واقعی به‌دلیل Deferred startup ساخته نشدند و هیچ Login یا اتصال Provider اجرا نشد. Sender database و Worker log هر حساب فقط زیر Scope همان حساب ساخته شدند؛ Worker log هیچ‌یک شناسهٔ حساب مقابل را نداشت.

## Secret و Privacy scan

Secretهای تصادفی ۳۲ بایتی آزمون پیش از اجرا Base64 شدند و پس از پایان Worker، تمام فایل‌های تولیدشدهٔ نصب آزمایشی تا سقف ۸ MiB به‌صورت بایتی بررسی شدند. هیچ Secret در stdout، stderr، Config، Coordinator، Lease archive، Runtime log، Worker log یا سایر فایل‌های آزمایشی یافت نشد. فایل Bootstrap در مسیر موفق، خطا و Kill مصرف/حذف شد.

اسکن هیچ `.env` یا Credential واقعی را نخواند و هیچ مقدار خصوصی واقعی وارد خروجی آزمون یا گزارش نشد.

## فایل‌های اصلی Phase 7-D

- `src/eitaa_bridge/application/process_runtime.py`
- `src/eitaa_bridge/infrastructure/worker_ipc/error_taxonomy.py`
- `tests/test_phase7d_process_isolation_adversarial.py`
- `docs/WORKER_IPC_PROTOCOL.md`
- `ARCHITECTURE_DECISIONS.md`
- `PHASE7D_PROCESS_ISOLATION_ACCEPTANCE_REPORT_2026-08-11.md`
- `PHASE7_PROCESS_ISOLATION_FINAL_REPORT_2026-08-11.md`

## نتیجهٔ آزمون و کنترل کیفیت

Dedicated Phase 7-D:

```text
7 passed
```

Focused Phase 4-D/7-A/7-B/7-C/7-D و Coordinator/Config/Runtime:

```text
76 passed
```

Full repository:

```text
439 collected
439 passed
```

کنترل‌های تکمیلی:

```text
compileall src + tests: passed
git diff --check: passed
actual fake-worker kill: passed
actual Eitaa Child kill/recovery: passed
authentication failure limit: passed
stale fence rejection: passed
real lock contention: passed
duplicate spawn race: passed
generated-secret byte scan: passed
TypeScript check: passed
UI production build: passed
remaining worker bootstrap files: 0
```

Vite فقط هشدار غیرمسدودکنندهٔ قدیمی دربارهٔ Chunk بزرگ‌تر از ۵۰۰ kB داد؛ Build با موفقیت کامل شد و Phase 7 هیچ تغییر UI جدیدی ایجاد نکرد.

## وضعیت نصب واقعی و Side effectها

- `bridge.json` واقعی تغییر نکرد و `worker_process.enabled` خاموش ماند.
- هیچ Login، Logout، OTP، Sync یا Send واقعی انجام نشد.
- هیچ دادهٔ واقعی Migration یا Reset نشد.
- هیچ Process واقعی برنامهٔ نصب‌شده Kill نشد؛ فقط Childهای ایجادشده توسط Test هدف بودند.
- هیچ Port، Firewall rule، Service، Router setting یا Dependency تغییر نکرد.
- هیچ Stage، Commit یا Push انجام نشد.

## محدودیت آگاهانه پس از Phase 7

Process isolation، Supervisor و پذیرش امنیتی کامل شده‌اند، اما مسیرهای Provider که هنوز RPC اختصاصی DTO/opaque-reference ندارند با Feature Flag روشن عمداً `eitaa_process_operation_ipc_required` می‌دهند. فعال‌سازی نصب واقعی یا حدس‌زدن API/Login flow برای Providerهای دیگر انجام نشده است.

Phase 7-D completed.

Phase 7 completed.

Phase 8-A NOT started.

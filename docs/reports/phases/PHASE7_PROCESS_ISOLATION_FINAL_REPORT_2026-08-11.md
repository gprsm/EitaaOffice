# گزارش نهایی Phase 7: Process isolation حساب‌های پیام‌رسان

تاریخ: ۲۰۲۶-۰۸-۱۱

وضعیت: Phase 7-A تا Phase 7-D تکمیل و آزموده شد

Feature واقعی: پیش‌فرض خاموش؛ Rollout انجام نشده است

## خروجی نهایی

Eitaa Bridge اکنون قرارداد نسخه‌دار و احرازشدهٔ IPC، یک Child اختصاصی برای هر MessengerAccount ایتا، مالکیت کامل Runtime در Child، Supervisor fenced، Crash recovery با Backoff/Quarantine و آزمون‌های خصمانهٔ Process isolation را دارد.

Parent فقط Coordinator، Authorization، Process control و DTOهای امن را نگه می‌دارد. Session object، Core، Access hash، Raw peer/message، Provider DB handle، Cache، Media handle، Job state، Account log، OTP، Password، Token و Cookie از مرز IPC عبور نمی‌کنند.

## وضعیت زیرفاز‌ها

### Phase 7-A — پروتکل IPC

- Envelope نسخهٔ ۱، HMAC-SHA256، correlation، deadline و nonce
- Secret کوتاه‌عمر یک‌بارمصرف با DACL کاربر جاری
- Payload validator، Error taxonomy و Fake provider worker مستقل
- منع Session/Access hash/Raw peer/Token/Password/OTP

### Phase 7-B — انتقال Runtime ایتا

- یک Child process برای هر MessengerAccount
- Core، Scheduler، Session/DB paths، Cache، Media، Job، Lease و Log فقط در Child
- Parent proxy و DTOهای کنترلی بدون Python callback
- Feature Flag نسخه‌دار پیش‌فرض خاموش و مسیر Legacy قابل Rollback
- Core deferred بدون Login/Network در Startup

### Phase 7-C — Supervisor و Recovery

- Heartbeat واقعی و deadline کران‌دار برای هر حساب
- Fence دقیق Worker ID + Generation + PID در Child و Coordinator
- Crash/Exit detection، Exit code، Reason code و Reconciliation اتمیک
- Backoff نمایی کران‌دار، Restart budget و Quarantine
- Duplicate worker rejection، Stale lease recovery و Shutdown/Restart تمیز
- استقلال Crash و Auth state حساب‌ها

### Phase 7-D — پذیرش خصمانه

- Kill واقعی Fake/Eitaa test workers
- Signature/Scope/Replay/response tampering
- Authentication failure limit و stream desynchronization shutdown
- Lock contention و duplicate-spawn race
- عدم اشتراک Session/Scheduler/DB/Cache/Log
- اسکن بایت‌به‌بایت Secretهای تولیدشده در تمام خروجی‌های آزمایشی

## روند آزمون‌های کامل

```text
پایان 7-A: 421 / 421 passed
پایان 7-B: 427 / 427 passed
پایان 7-C: 432 / 432 passed
پایان 7-D: 439 / 439 passed
```

هیچ Test حذف، deselect یا xfail جدیدی برای سبزکردن مجموعه اضافه نشد.

کنترل TypeScript و Build تولیدی UI نیز موفق شدند. هشدار غیرمسدودکنندهٔ موجود دربارهٔ اندازهٔ Chunk اصلی Vite باقی است و به تغییرات Process isolation مربوط نیست.

## Feature Flag نهایی

`features.worker_process` نسخهٔ ۱ شامل Startup/Request deadline، Heartbeat interval/deadline/failure threshold، Restart window/budget، Backoff bounds و Quarantine duration است. نبود بخش، Schema ناشناخته، مقدار خارج از کران، Multi-session غیرفعال یا Kill switch محیطی همگی قابلیت را Fail-closed خاموش می‌کنند.

نمونه‌های Config مستند شده‌اند، ولی هر سه نمونه و `bridge.json` واقعی همچنان `enabled: false` هستند.

## لاگ و Audit

چرخهٔ Process این رویدادهای امن را دارد:

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

Coordinator نیز Start/Ready/Heartbeat/Crash/Stop/Quarantine و Generation را با Reason و Metadata محدود ثبت می‌کند. هیچ Secret، Phone، Credential، Session، Payload خصوصی یا Traceback وارد Log/Audit نمی‌شود.

## گزارش‌های مرجع Phase 7

- `PHASE7A_WORKER_IPC_PROTOCOL_REPORT_2026-08-11.md`
- `PHASE7B_EITAA_PROCESS_RUNTIME_REPORT_2026-08-11.md`
- `PHASE7C_PROCESS_SUPERVISOR_RECOVERY_REPORT_2026-08-11.md`
- `PHASE7D_PROCESS_ISOLATION_ACCEPTANCE_REPORT_2026-08-11.md`
- `docs/WORKER_IPC_PROTOCOL.md`
- `ARCHITECTURE_DECISIONS.md`

## ممیزی Side effect نهایی

- مسیر جدید پروژه قابل نوشتن بود و مسیر مطلق قدیمی در فایل‌های فعال پیدا نشد.
- Branch برابر `main` و upstream برابر `origin/main` باقی ماند.
- Worktree موجود عمداً dirty بود و تغییرات قبلی حفظ شدند.
- `bridge.json`، Session، Coordinator، Contacts، Cache، Media و Log واقعی تغییر یا مهاجرت نکردند.
- هیچ Login، Logout، OTP، Sync، Send، Port، Firewall، Service یا Router action واقعی انجام نشد.
- هیچ Dependency نصب نشد.
- هیچ Stage، Commit یا Push انجام نشد.

## مرز ادامه

Phase 7 به‌طور کامل بسته شد. گام معماری بعدی Roadmap، Phase 8-A برای ممیزی Repository/Query/Cache حساب‌محور است و در این نوبت آغاز نشده است. Rollout Feature واقعی نیز نیازمند تصمیم و برنامهٔ جداگانه است.

Phase 7 completed.

Phase 8-A NOT started.

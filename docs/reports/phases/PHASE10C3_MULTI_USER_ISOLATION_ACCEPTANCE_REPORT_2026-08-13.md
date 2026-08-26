# گزارش Phase 10-C3 — پذیرش جداسازی چندکاربر/چندحساب — 2026-08-13

## نتیجه

**C3 در سطح Fake/Contract/adversarial کامل و پذیرفته شد.** مسیر زیر بدون نشت بین A و B اثبات شد:

```text
AppUser A -> MessengerAccount A -> Session/Data/Jobs/Audit A
AppUser B -> MessengerAccount B -> Session/Data/Jobs/Audit B
```

## پوشش پذیرش

- login، نشست‌های هم‌زمان، CSRF، idle/absolute expiry، logout و revoke؛
- membership و رد cross-account/cross-session/impersonation؛
- مسیرهای جداگانهٔ session/database/media/catalog/index/log/lock و runtime state؛
- Job owner/account scope، idempotency، lease fencing، restart، retry، crash recovery و cancel؛
- Audit کاربرمحور، correlation، pagination/export امن، chain validation و tamper detection؛
- Worker signature/scope/replay tampering، duplicate spawn و عدم نشت secret/path؛
- دو کاربر و چند Client هم‌زمان با مجموعه‌حساب‌های متفاوت.

## آزمون‌ها

مجموعهٔ دقیق Fake/Contract/adversarial در 9 فایل اجرا شد:

```text
48/48 passed
```

فایل‌های محوری شامل `test_phase6b_lan_http_auth_session_hardening.py`،
`test_account_runtime.py`، `test_phase7d_process_isolation_adversarial.py`،
`test_phase8b_persistent_jobs.py`، `test_phase8d_audit_stress_acceptance.py` و
`test_phase9d_multi_client_acceptance.py` بودند.

هیچ حساب یا نشست واقعی دوم ایجاد نشد و هیچ Provider واقعی فراخوانی نشد.

## Pilot واقعی

طبق تصمیم محیط‌مستقل، Pilot واقعی حساب دوم تا آماده‌شدن سیستم استقرار نهایی deferred است و blocker
پذیرش کد 10-C نیست. اگر ادعای production multi-user پیش از Release نهایی مطرح شود، Pilot واقعی یا
پذیرش معادل با حضور مالک حساب و ورود خصوصی UI لازم است.

## دروازهٔ خروج

C3 پذیرفته است و ادامه به C4 مجاز شد.

# گزارش G-04-D — پذیرش خصمانهٔ چهار کانال حریم خصوصی

تاریخ: 2026-08-26  
Run: `STAB-G04-R04`  
وضعیت: `ADVERSARIAL_GREEN / RELATED_REGRESSION_GREEN / G-04-E_AWAITING_USER`  
Finding: `F-044 OPEN_FINALIZATION_PENDING`

## هدف و مرز

این زیرمرحله اثبات کرد مجازبودن نمایش canonical در محصول به نشت آن در Runtime Log، Audit، Diagnostic یا Support Bundle منجر نمی‌شود. همهٔ ورودی‌ها، DBها، logها، diagnostics و ZIPها مصنوعی و زیر basetemp بودند. هیچ فایل عملیاتی یا Live خوانده نشد.

## RED پنج‌گانه

فایل `tests/test_g04d_privacy_channels.py` پنج کنترل مستقل ایجاد کرد. یک هویت canonical جهانی و یک Bearer کاملاً ساختگی زیر نام‌های شناخته‌شده، ناشناخته و ساختار تو‌در‌تو تزریق شدند؛ پیام شکست مقدار را echo نمی‌کرد.

| کانال/کنترل | RED |
|---|---|
| Runtime Log | generic/nested value حفظ می‌شد |
| Diagnostic JSONL | generic/nested value حفظ می‌شد |
| Audit persistence/query/export | metadata خصوصی ذخیره و صادر می‌شد |
| Support Bundle creator | canonical جهانی در چند ورودی باقی می‌ماند |
| Support Bundle scanner | canonical جهانی را full phone تشخیص نمی‌داد |

نتیجهٔ اولیه `5/5 failed` بود. failure محیطی یا retry وجود نداشت؛ creator فقط مسیر ZIP موقت را در stdout چاپ کرد.

## اصلاح

- redaction مشترک علاوه بر نام کلید، متن طبقه‌بندی‌نشده و تو‌در‌تو را برای E.164 جهانی، شکل تلفنی پشتیبانی‌شده، Bearer و provider-token shape بررسی و sanitize می‌کند.
- Coordinator Audit metadata را پیش از محاسبهٔ hash و persistence redacted می‌کند. Query/Export نیز برای تاریخچهٔ موجود دفاع ثانویهٔ key-aware و pattern-aware دارد.
- Support Bundle creator و scanner از دامنهٔ global phone همسو استفاده می‌کنند؛ شمارهٔ ایران همچنان پوشش داده می‌شود.
- RuntimeLogger و BridgeDiagnosticManager تغییر مستقیم نداشتند و hardening را از redaction مشترک دریافت کردند.

## نتایج

| دامنه | نتیجه |
|---|---|
| G-04-D اختصاصی | `5/5 passed` |
| privacy regression A | `53/53 passed` |
| privacy regression B | `2/2 passed` |
| privacy regression C | `50/50 passed` |
| full Backend | اجرا نشد؛ اجباری در G-04-E |

Regressionها Audit chain/query/export، diagnostics/observability، AppUser/AccountAuth، account management، onboarding/Registry و Support Bundle عمومی/حساب‌محور را پوشش دادند.

## هش‌های نهایی

- `redaction.py`: `10eb93c1a3ff08845764d55b39c04ba21ed45888e5b767f28c66dbb9ba37a9a4`
- `store.py`: `b7ceb3c5b41bd3071f93e9331623794939eb9ee293210317d068cc65844ef710`
- `audit.py`: `385f2621726584fe8bc5b6b3b1a8c69b942f8ae62763666464a3d5350b631f22`
- `create_diagnostics_bundle.py`: `480805802c27b27814f20f60a6fe8a2a9c33c3d58fd67f7b53a959cf81538202`
- `scan_diagnostics_bundle.py`: `b02e66e97a7fcce4661634bf34eeaa117a332f9e50d6f43cb30008b4a143a4cc`
- `test_g04d_privacy_channels.py`: `5096701603a670a3270ddc368ce88ef54c4de0e50acc3359d271eded6bc5244e`

`runtime_logger.py` و `manager.py` بدون تغییر مستقیم باقی ماندند و هش‌های ثابت آن‌ها در V-120 ثبت شده است.

## ادامه

G-04-D کامل است، اما F-044 هنوز بسته نمی‌شود. G-04-E باید معیارهای خروج A تا D را audit، full Backend و کنترل‌های UI لازم را اجرا و فقط در صورت سبزی کامل گزارش نهایی/closure را ثبت کند. این مرحله release readiness عمومی یا مجوز Live ایجاد نمی‌کند.

هیچ Provider network، Login/OTP/Send، migration/rollback عملیاتی، config/session/runtime/diagnostics واقعی، توسعهٔ Bale یا Git stage/commit/push انجام نشد.

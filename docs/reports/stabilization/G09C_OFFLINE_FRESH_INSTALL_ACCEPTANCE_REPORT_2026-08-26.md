# گزارش G-09-C — پذیرش fresh-install کاملاً آفلاین

تاریخ: 2026-08-26  
Run: `STAB-G09-R01`  
وضعیت: `EXTRACT_AND_FRESH_INSTALL_GREEN / AUTO_CONTINUE_G09_D`

## دامنه

archive پذیرفته‌شدهٔ G-09-B فقط زیر `artifacts/stabilization/G09C_extracted` استخراج و یک محیط Python تازه فقط زیر `artifacts/stabilization/G09C_fresh_venv` ساخته شد. نصب با `--no-index` و فقط از wheelهای داخل همان archive انجام شد؛ نصب کاربر/سیستم، دانلود، Provider، Login/OTP/Send، دادهٔ واقعی، Bale development و Git mutation وجود نداشت.

## نتیجهٔ استخراج و parity

- SHA-256 archive ورودی: `a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360`.
- extract شامل 283 فایل است: 282 فایل allowlisted و یک content manifest.
- 15 فایل ضروری canonical بررسی شد: missing=0.
- فایل قرنطینه‌شدهٔ `application/bale_client`: صفر.
- self dry-run از داخل extract: file_count=282، content-set=`cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a` و output write=0.
- compileall روی source/script/package داخل extract با exit code صفر پایان یافت.
- wheel/source parity در extract: source=90، missing=0، mismatched=0، extra=0 و wheel SHA=`9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70`.

## نتیجهٔ نصب تمیز

- نصب آفلاین `eitaa-core`، `eitaa-bridge` و شش dependency runtime موفق شد.
- runtime environment checker: `ok=true` و failure=0.
- `pip check`: `No broken requirements found`.
- module واقعاً زیر prefix محیط تازه بار شد؛ shadow شدن از source tree رخ نداد.
- importهای مرکزی سبز: product=`0.7.0-ui-mvp6.1.1-gmi4.2`، API=`v1` و Event Catalog count=103.
- چهار entrypoint نصب شد: bridge، API، provider worker و Windows LAN.

## رخداد checklist

چک 15فایلی نخست یک missing کاذب گزارش کرد، چون مسیر قدیمی `observability/event_catalog.py` در checklist دستی استفاده شده بود. فایل canonical در `infrastructure/diagnostics/event_catalog.py` حاضر بود؛ checklist اصلاح و بدون تغییر archive/source با `15/15` سبز شد. این رخداد invocation/checklist است و failure محصول یا package نیست.

RED تازه موضوعیت نداشت: این بخش rehearsal پذیرش artifact جاری است؛ REDهای packaging/dependency/parity در V-132/V-135/V-141 ثبت شده‌اند. هیچ کد یا test تغییر نکرد.

## نتیجه

G-09-C برابر `OFFLINE_FRESH_INSTALL_GREEN` پذیرفته شد. G-09-D همهٔ قراردادهای UI و build را اجرا و شواهد Backend جاری را با hash/no-drift تجمیع می‌کند.

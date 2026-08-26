# گزارش رفع خروج Backend هنگام راه‌اندازی — ۲۰۲۶-۰۸-۲۰

## نتیجه

خطای عمومی `The owned backend exited during startup` که در اجرای محلی گزارش شد، از مسیر مالکیت Worker حساب پیش‌فرض رفع شد. Backend دیگر صرفاً به‌دلیل زنده‌بودن یک PID قدیمی، آن PID را Worker معتبر تلقی نمی‌کند.

## علت واقعی

- در Coordinator یک Worker قدیمی با وضعیت فعال باقی مانده بود و فایل lease همان PID را نگه می‌داشت.
- بررسی فقط‌خواندنی سیستم نشان داد PID مذکور اکنون زنده است، اما executable آن `svchost.exe` است؛ بنابراین ویندوز PID بسته‌شدهٔ Worker قبلی را به یک فرایند نامرتبط داده بود.
- منطق قبلی فقط «زنده بودن PID» را می‌سنجید و این وضعیت را مالکیت معتبر Worker فرض می‌کرد. در نتیجه ساخت `BridgeApplicationApi` با کد امن `eitaa_worker_process_alive` متوقف و Launcher فقط پیام عمومی خروج Backend را نمایش می‌داد.

## اصلاح

- نام executable از مرجع سیستم‌عامل خوانده می‌شود: Toolhelp Process Snapshot در Windows و `/proc/<pid>/exe` در محیط‌های سازگار.
- مالکیت Worker سه‌حالته و fail-closed است:
  - PID مرده یا executable قطعاً نامرتبط: رکورد stale بازیابی می‌شود؛
  - executable مطابق runtime Python: مالک زنده حفظ و شروع تکراری رد می‌شود؛
  - هویت غیرقابل‌بررسی: هیچ lease یا رکوردی دست‌کاری نمی‌شود و خطای امن owner-unknown باقی می‌ماند.
- همین تشخیص هم در بازیابی رکورد Coordinator و هم در archive امن `worker.lock` قدیمی اعمال می‌شود؛ بنابراین دو لایهٔ مالکیت با یکدیگر سازگارند.
- بازیابی ناشی از استفادهٔ مجدد PID با reason code مستقل `worker_process_pid_reused` در Worker history و audit ثبت می‌شود و با مرگ واقعی PID اشتباه گزارش نمی‌شود.

## آزمون‌ها

- آزمون red اولیهٔ PID-reuse مطابق انتظار شکست خورد و خطای قبلی `eitaa_worker_process_alive` را بازتولید کرد.
- چهار قرارداد مستقل پذیرفته شدند: lease stale، رکورد Worker stale، تشخیص executable واقعی Python و reason code پایدار Coordinator.
- مجموعهٔ مالکیت/Process isolation برابر `25/25` موفق شد.
- regression کامل Backend پس از اصلاح `570/570` موفق شد.
- TypeScript check و قرارداد Observability UI/Electron نیز موفق‌اند.
- scanner فقط‌خواندنی لاگ‌های JSONL برابر ۹۱۰۸ رکورد، `invalid_json=0` و `finding=0` را تأیید کرد.

## مرز عملیاتی

- لاگ واقعی Launcher/Backend، metadata امن Worker و نام executable فقط‌خواندنی بررسی شدند؛ شناسهٔ حساب، شماره، پیام، Token، Cookie، OTP یا Credential گزارش نشد.
- `bridge.json`، `.env`، Session واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` بازنویسی، جابه‌جا یا پاک نشدند.
- برای جلوگیری از Login یا ارتباط ناخواسته با Provider، نرم‌افزار واقعی در این نوبت restart نشد. اجرای بعدی عادی برنامه مسیر بازیابی جدید را به‌کار می‌گیرد.
- هیچ فرایند، Port، Firewall، Proxy، Certificate یا وضعیت Git تغییر داده نشد.

## Trigger ابطال

تغییر در `account_runtime.py`، قرارداد Worker lease، Coordinator worker recovery، روش spawn کردن Provider Worker یا نام executable runtime نیازمند تکرار این پذیرش است.

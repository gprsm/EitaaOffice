# گزارش Phase 11-B1 — Multi-provider Core Generalization

تاریخ: 2026-08-13  
نتیجهٔ نهایی: `IMPLEMENTED / FAKE_VERIFIED`  
اثر بیرونی: `NONE`  
وضعیت Bale Personal: `RUNTIME_BLOCKED / UNCHANGED`

## ۱. هدف و دامنه

هدف این زیرمرحله حذف hard-codeهای زیرساختی باقی‌مانده پیش از Provider سوم بود، بدون پیاده‌سازی یا دورزدن اتصال بله. دامنه شامل Registry پایدار، migration سازگار، Audit عمومی، Contact binding عمومی، Capability service و Fake Provider سوم آفلاین بود.

خارج از دامنه: Provider network، ورود یا ارسال واقعی، Pilot حساب دوم، تغییر `bridge.json`، restart سرویس واقعی، migration پایگاه عملیاتی، Firewall/Proxy/Port و هرگونه عملیات Git تغییردهنده.

## ۲. پیاده‌سازی

### ۲.۱. Registry و schema

- Coordinator schema از v5 به v6 ارتقا یافت و جدول `provider_registrations` اضافه شد.
- `messenger_accounts`، `operation_jobs`، `audit_events` و `account_execution_limits` در schema جاری با FK به Registry بازسازی می‌شوند.
- triggerهای تازه مانع mismatch میان Provider یک Job/Execution Policy و MessengerAccount می‌شوند.
- migration با `foreign_keys=OFF` کنترل‌شده، transaction اتمیک، ثبت checksum نسخهٔ 6، `foreign_key_check` و `quick_check` آزموده شد.
- رکوردهای Eitaa/Bale برای سازگاری seed می‌شوند و سپس composition root metadata را افزایشی reconcile می‌کند.
- حذف خودکار registration غایب انجام نمی‌شود تا تاریخچه و FKهای قبلی از بین نروند.

### ۲.۲. Contact Store

- schema از v2 به v3 ارتقا یافت و `contact_provider_registrations` اضافه شد.
- `contact_account_bindings.provider` به Registry محلی FK دارد و allowlist ثابت حذف شد.
- migration پیش از تغییر schema backup هم‌مسیر می‌سازد و دادهٔ binding قبلی را حفظ می‌کند.
- ثبت Provider عمومی است؛ raw provider subject ذخیره نمی‌شود و فقط fingerprint حساب‌محور باقی می‌ماند.

### ۲.۳. Capability

- `ProviderCapabilityService` Manifest و observation حساب را merge می‌کند.
- Capability اعلام‌نشده حتی با observation جعلی `supported` فعال نمی‌شود.
- mismatch میان Manifest و Registry پایدار fail-closed است.
- Capability تازهٔ `contacts.write` از `contacts.read` جدا شد.
- endpoint امن `GET /api/v2/messenger-accounts/{id}/capabilities` پس از Membership check اضافه شد.
- مسیرهای Dialog، History، Send، Media و Contacts در حالت multi-session پیش از runtime guard می‌شوند.

### ۲.۴. Fake Provider سوم

- Adapter typed و deterministic برای dialogs/history/send/session validation ایجاد شد.
- هیچ socket، endpoint، credential، filesystem path یا دادهٔ واقعی ندارد.
- registration آن `test_only`، runtime-capable برای Contract و از catalog محصول پنهان است.
- persistence آن فقط با opt-in تست انجام می‌شود.

### ۲.۵. Observability

- `provider_registry_reconciled` و `provider_capability_check_rejected` به Event Catalog افزوده شدند.
- Event Catalog از 76 به 78 رخداد رسید.
- payload فقط metadata امن و شناسهٔ server-generated دارد.

## ۳. شواهد آزمون

- Targeted schema/provider/contact/audit: `48/48` موفق.
- Targeted API/AppUser/runtime/observability: `55/55` موفق.
- Full Backend regression: `540/540` موفق در `102.6s`.
- TypeScript check: موفق.
- UI assertionهای شماره‌دار: scroll `10/10`، grouped media `16/16`، Phase 9 workspace `11/11`، Phase 9 acceptance `10/10`، Phase 10 activation `7/7`، Phase 11 onboarding `7/7`؛ مجموع `61/61`.
- Electron/UI observability contract: موفق.
- Production build: موفق؛ warning شناخته‌شدهٔ chunk اصلی `894.38 kB` مطابق F-013 باز و غیرمسدودکننده است.
- Runtime log privacy scan: `9106` رکورد، invalid JSON=`0`، finding=`0`.
- metadata: Coordinator schema=`6`، Event Catalog=`78`، product provider catalog=`bale,eitaa`.

## ۴. آزمون‌های خصمانه و جداسازی

- Provider ناشناخته در FK، Audit filter و Contact binding رد شد.
- observation جعلی نتوانست Capability خارج از Manifest را بالا ببرد.
- تغییر Provider Job به Provider حساب دیگر با trigger رد شد.
- Fake worker/job/audit با Provider عمومی و بدون شرط Eitaa اجرا شد.
- دو binding برای دو MessengerAccount مستقل ماندند و raw subject در فایل DB مشاهده نشد.
- Fake از catalog محصول و persistence پیش‌فرض خارج ماند.

## ۵. Invocation/error ledger

1. چند جست‌وجوی اولیهٔ PowerShell به‌علت quoting پیچیده یا glob سبک Unix parse/resolve نشدند؛ همه فقط‌خواندنی بودند و با `rg` و مسیرهای Windows-safe تکرار شدند.
2. یک جست‌وجو exit code 1 داد چون بخش دوم match نداشت؛ mutation رخ نداد.
3. یک فرمان ترکیبی PowerShell به‌علت پرانتز بسته‌نشده اجرا نشد؛ با فرمان ساده‌تر تکرار شد.
4. دو lookup با مسیر فرضی `infrastructure/diagnostics.py` و نام تست فرضی B0 فایل را نیافتند؛ مسیر canonical با `rg --files` پیدا شد.
5. اجرای هدفمند نخست `38 passed / 1 failed` داشت؛ failure فقط assertion قدیمی `schema == 5` بود. انتظار به نسخهٔ جاری 6 ارتقا یافت و اجرای نهایی سبز شد.
6. `git status` نخست به‌علت Windows sandbox ownership با `dubious ownership` متوقف شد. فقط همان invocation با `git -c safe.directory=<workspace>` تکرار شد و هیچ Git config تغییر نکرد.
7. یک جست‌وجوی hard-code به‌علت escape نامعتبر PowerShell شکست؛ با الگوی single-quoted تکرار شد.
8. full regression نخست پس از 120 ثانیه در 66٪ timeout شد و تا آن نقطه failure نداشت؛ شاهد نهایی محسوب نشد. اجرای تازه با basetemp مستقل و سقف 300 ثانیه `540/540` موفق شد.
9. خروجی نخست collect-only با tail شمار کل را نمایش نداد؛ شمارش امن خروجی collection مقدار `540` را تأیید کرد.
10. patch تجمیعی نخستِ اسناد به‌علت تفاوت context انتهای Validation ledger اعمال نشد و هیچ فایل را تغییر نداد؛ patch به بخش‌های دقیق تقسیم و سپس کامل اعمال شد.

## ۶. حفظ داده و اثر بیرونی

- `bridge.json`، `.env`، Session، `data/` عملیاتی، `runtime/`، `catalog/` و `backups/` تغییر داده نشدند.
- migration فقط روی SQLiteهای موقت آزمون اجرا شد؛ DB واقعی در این نوبت باز یا migrate نشد.
- هیچ Provider endpoint، Login، OTP، Credential، Send، WordPress، Laragon، Firewall یا Proxy استفاده نشد.
- هیچ reset/checkout/clean/stage/commit/push و هیچ تغییر Git config انجام نشد.
- worktree عمداً dirty حفظ شد.

## ۷. نتیجه و مرز مرحلهٔ بعد

هستهٔ persistence/audit/contact/capability برای Provider سوم دیگر به بازنویسی دوتایی Eitaa/Bale نیاز ندارد. این پذیرش به معنی عمومی‌شدن کامل اجرای application نیست: برخی handlerهای v1 و EitaaRuntimeRegistry هنوز اختصاصی ایتا هستند.

مرحلهٔ بعدی `11-B2 Provider-neutral Application Orchestration` است. در آن serviceهای Dialog/History/Send/Media/Contacts باید Adapter عمومی را مصرف کنند و Fake سوم از همان مسیر عبور کند. Bale Personal تا API رسمی/مجوز کتبی غیرفعال می‌ماند و Pilot واقعی حساب دوم همچنان نیازمند اعلام آمادگی و ورود خصوصی کاربر است.

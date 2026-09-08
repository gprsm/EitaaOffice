# گزارش Setup مستقل Windows برای انتقال Eitaa Bridge

تاریخ: 2026-08-28  
Run: `INSTALLER-SELF-CONTAINED-R01`  
وضعیت: `IMPLEMENTED / OFFLINE_AUTOMATED_ACCEPTED / UNSIGNED_SHAREABLE_CANDIDATE / CLEAN_MACHINE_PENDING`

## نتیجه

یک Setup تک‌فایلی برای Windows 10/11 x64 ساخته شد که Python 3.13، بسته‌های Runtime نصب‌شده از wheelهای آفلاین و UI ازپیش‌ساخته را همراه دارد. رایانهٔ مقصد به نصب جداگانهٔ Python یا Node.js، دسترسی شبکه یا مجوز Administrator نیاز ندارد. نصب در سطح کاربر انجام می‌شود و ارتقا فقط فایل‌های managed برنامه را جایگزین می‌کند.

Setup از حمل state خصوصی build host جلوگیری می‌کند. `bridge.json`، `.env`، Session، database، media، runtime logs، diagnostics، backups و catalog وارد artifact نمی‌شوند. نصب تازه config نمونه و پوشه‌های خالی لازم را ایجاد می‌کند؛ نصب روی مسیر موجود state خصوصی مقصد را حفظ می‌کند. انتقال state واقعی فقط باید با مسیر Backup/Restore مستقل انجام شود.

## ممیزی پوشهٔ خام

ریشهٔ واقعی بستهٔ کاربر یک سطح داخل `Eitaa_Bridge/Eitaa_Bridge` بود. `VERSION.txt` وجود نداشت و `package_clean.py --dry-run` قبل از repair به‌درستی متوقف شد. wheel موجود نسبت به source جاری دو mismatch در `api.py` و `eitaa_provider_runtime_operations.py` داشت. فایل عملیاتی `bridge.json` در raw وجود داشت، اما محتوا خوانده و فایل جابه‌جا، بازنویسی یا حذف نشد.

builder جدید wheel را از source جاری بازسازی می‌کند و پیش از ساخت Setup، allowlist و wheel/source parity را fail-closed می‌سنجد. همگام‌سازی raw فقط فایل‌های managed را هدف می‌گیرد و state عملیاتی raw را کنار می‌گذارد.

در repair نهایی 30 فایل managed همگام و wheel raw با SHA-256=`4b08cf9e11c51ad7a3e2f8b3ea545b37bab0c33455f6f75a855f847e4eded208` بازسازی شد. dry-run raw سپس با 260 فایل، write صفر و content-set=`50d3bb8950c35bf5cfddf5ac4120c84c22eb17553150eff437d68a0095e3f9b8` PASS شد. nesting و فایل‌های عملیاتی موجود برای جلوگیری از mutation ناخواسته جابه‌جا نشدند.

## خطای اولین اجرا پس از کپی پوشه

نشانهٔ قبلی به دو نقص clean-install ثبت‌شده در F-041 متصل بود: نبود Coordinator در database خالی و نبود `challenge_id` امن در پاسخ Legacy login. این نقص‌ها در G-03 اصلاح شده‌اند. مجموعهٔ regression مرتبط در این checkpoint دوباره سبز شد. بااین‌حال کپی عینی پوشهٔ پروژه روش انتقال پشتیبانی‌شده نیست، چون source، wheel، runtime و state میزبان را بدون مرز نسخه/مالکیت مخلوط می‌کند؛ مسیر پشتیبانی‌شده Setup تازه و Backup/Restore جداگانه است.

## قرارداد Windows 7

Windows 7 برای این release هدف پشتیبانی‌شده نیست و preflight پیش از هر mutation آن را رد می‌کند. قرارداد جاری پروژه حداقل Python 3.11 دارد، Python رسمی 3.13 روی Windows 7 پشتیبانی نمی‌شود و مرورگر Edge پشتیبانی‌شده نیز برای آن باقی نمانده است. پایین‌آوردن Runtime به Python 3.8 و pin کردن dependencyها/مرورگرهای منقضی یک fork امنیتی پرهزینه و نه یک تنظیم بسته‌بندی ساده است؛ بنابراین به‌عنوان release امن انتخاب نشد.

راه‌های عملی امن عبارت‌اند از ارتقای سیستم مقصد به Windows 10/11 x64، یا اجرای Bridge روی یک رایانهٔ پشتیبانی‌شده و طراحی جداگانهٔ دسترسی LAN با authentication/authorization مناسب. گزینهٔ دوم تغییر معماری و نیازمند سناریوی مستقل است.

## شواهد ساخت و آزمون

- RED قرارداد Setup: `3/3 failed`.
- targeted نهایی: `4/4 passed`؛ مجموعهٔ مرتبط runtime/auth/package/UI: `88/88 passed`.
- Backend کامل: `674/674 passed` با failure/error/skip صفر؛ collection مستقل نیز 674 تست را تأیید کرد.
- TypeScript و UI/Electron Observability هر دو PASS.
- نصب Runtime در payload و شبیه‌سازی install-copy فقط با `--no-index` و wheelهای محلی PASS؛ runtime checker و importهای Bridge/Core/diagnostics سبز.
- dry-run نهایی بستهٔ canonical پس از refresh اسناد 286 فایل، write صفر و content-set برابر `6888b72a04a124aee773cb172c4ce3ccc4aa6415174ed7b962b9f061c7aa5640` داشت؛ wheel/source drift صفر بود.
- EXE با `--verify-only` بدون نصب resourceهای داخلی را تأیید کرد.
- بررسی مستقل ZIP داخلی 4397 فایل را دید؛ entry لازم مفقود نبود، extra صفر و finding حریم خصوصی صفر بود.

## Artifactها

- Setup: `EitaaBridge-0.8.0-rc1-SelfContained-Setup-x64.exe`
  - size: `38,436,864 bytes`
  - SHA-256: `B609DD9AA689451A694C78FBB0DCAA71943D396F8F548B11E11ECEF500930121`
  - signature: `NotSigned`
- Portable fallback: `EitaaBridge-0.8.0-rc1-SelfContained-Portable.zip`
  - size: `37,793,425 bytes`
  - SHA-256: `855E734098E5C1AF4C3637C5782631FFB376A830518CF580367383D417F660DA`

## محدودیت‌های باقی‌مانده

Setup روی همین میزبان نصب واقعی نشد تا state عملیاتی یا `%LOCALAPPDATA%` تغییر نکند. پذیرش clean-machine، مشاهدهٔ Windows/Edge واقعی، code-sign و SmartScreen reputation هنوز انجام نشده است. چون EXE امضا نشده، Windows ممکن است هشدار SmartScreen نشان دهد. این artifact نامزد قابل‌اشتراک برای آزمون کنترل‌شده است، نه انتشار Production عمومی.

worktree اصلی هم‌زمان تغییرهای سناریوهای دیگری را در خود داشت. برای جلوگیری از mixed commit هیچ stage/commit/push انجام نشد؛ انتشار source فقط پس از ساخت snapshot ایزوله و تکرار validation همان snapshot مجاز است. این محدودیت مانع تحویل artifact محلی آزموده‌شده نیست.

هیچ Provider، Login/OTP، ارسال پیام، WordPress، Firewall/Proxy/Registry سراسری یا دادهٔ عملیاتی در این Run لمس نشد. مرجع تصمیم ADR-48، Finding برابر F-062 و شاهد رسمی V-184 است.

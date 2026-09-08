# گزارش Setup گرافیکی و اصلاح تجربهٔ فعال‌سازی — 2026-08-28

## نتیجه

RC4 با Setup گرافیکی فارسی، فعال‌سازی قابل Copy/Paste مستقل از زبان صفحه‌کلید، آرشیو خودکار خروجی‌های قبلی و بستهٔ تحویل امضاشده ساخته شد. مسیر نصب همچنان `%LOCALAPPDATA%\Programs\EitaaBridge` و بدون نیاز به Python/Node.js نصب‌شده روی مقصد است.

## فعال‌سازی

- کادر request دیگر به حالت disabled غیرقابل‌تعامل متکی نیست و دکمهٔ کپی، انتخاب متن و منوی راست‌کلیک دارد.
- کادر activation دکمهٔ صریح «جای‌گذاری از کلیپ‌بورد»، منوی راست‌کلیک، `Shift+Insert` و handler کلید فیزیکی `V/C/A` دارد؛ بنابراین فارسی یا انگلیسی بودن layout مانع Paste/Copy/Select All نمی‌شود.
- فاصله، خط جدید و نویسه‌های نامرئی قالب‌بندی هنگام Paste حذف می‌شوند، ولی محتوای ASCII امضاشده تغییر معنایی نمی‌کند.
- UI با عنوان «نسخه اختصاصی Eitaa Bridge»، آیکون محصول و توضیح فعال‌سازی همان دستگاه نمایش داده می‌شود. Startup پس از فعال‌سازی معتبر همچنان بی‌صداست.

قالب رمزنگاری برای سازگاری تغییر نکرد. request نمونه 258 نویسه و activation نمونه با metadata استاندارد 563 نویسه است. کوتاه‌سازی متوسط با format binary نسخه‌دار ممکن است، اما signature Ed25519 به‌تنهایی حدود 86 نویسه Base64URL می‌گیرد؛ کد بسیار کوتاه بدون سرویس lookup آنلاین یا کاهش اطلاعات/امنیت ممکن نیست.

## Setup گرافیکی و ارتقا

bootstrap تک‌فایلی اکنون WinForms فارسی و RTL است. مسیر نصب، حفظ داده‌های قبلی، نیاز نداشتن Python/Node، ایجاد میان‌برها، progress و گزینهٔ اجرای پس از نصب را نشان می‌دهد. عملیات داخلی با `/quiet` بدون پنجرهٔ Console اجرا می‌شود. `--verify-only` برای کنترل resourceها بدون نصب حفظ شده است.

ارتقای عادی managed code/runtime را mirror می‌کند و `bridge.json`، `.env`، نشست، `data/`، `runtime/`، `diagnostics/`، `backups/` و `data/licensing/activation.dat` را حفظ می‌کند. برای آزمون فعال‌سازی، تغییر نام موقت `activation.dat` و برای نصب کاملاً تمیز، تغییر نام کل پوشه نصب به‌جای حذف توصیه و در بستهٔ تحویل مستند شد.

## آرشیو نسخه قبلی

`scripts/archive_previous_office_release.ps1` فقط Setup/Portable و sidecarهای نام‌دارِ مستقیم `release/office` را پیش از انتشار جفت جدید به `archive/<timestamp>` منتقل و نام، اندازه و SHA-256 را در Manifest ثبت می‌کند. در ساخت RC4، 12 artifact مربوط به RC1 تا RC3 محلی آرشیو شد. در شاخهٔ تحویل نیز 7 item قدیمی RC2/RC3 به آرشیو زمان‌دار منتقل شد؛ trust bundle عمومی مشترک حذف یا جابه‌جا نشد.

## خروجی و شواهد

- Setup RC4: `46,855,488 bytes`، SHA-256=`E964C93B7800CBEB64F638D62321F6267AF23166D7DE074E228DF32CD389BFA4`، `--verify-only=0`، signer Thumbprint مطابق، tamper detection=true، timestamp=false و وضعیت پیش از trust=`UnknownError`.
- Portable RC4: `45,941,170 bytes`، SHA-256=`8D9AE8ADF6EF67F16AF8C36DFCC456CE0ACE8D692D12123FC06A2D62FC9A66FC`.
- Delivery ZIP: `92,782,790 bytes`، SHA-256=`6DACA748F79508E2DCE4F3409F7A3E24B378F27A2327BFA2B0CEF4E201EEFD9E`، 13 entry و private-key-named entry صفر. هشت فایل متنی delivery همگی strict UTF-8 با BOM و بدون mojibake/replacement هستند.
- targeted activation/installer=`41/41`، full Backend سریالی=`690/690` در 76 فایل، TypeScript=`PASS` و UI/Electron observability=`PASS`. یک اجرای full هم‌زمان با سایر checkerها یک شکست scanner حریم خصوصی نشان داد که در 10 تکرار ایزوله و full سریالی بازتولید نشد.
- package dry-run پس از افزودن helper به allowlist=`301 files / PASS`؛ wheel/runtime/install-copy simulation در ساخت Setup سبز بود.

## محدودیت باقی‌مانده

نصب واقعی RC4 و مشاهدهٔ بصری پنجره/میان‌برها روی یک Windows 10/11 تمیز انجام نشد، چون نصب در حساب کاربر mutation محیط و نیازمند تأیید همان لحظه است. گواهی Self-signed همچنان reputation عمومی SmartScreen ندارد و مقصد باید CER را پس از تطبیق Thumbprint آگاهانه trust کند. Windows 7 پشتیبانی نمی‌شود.

worktree شاخهٔ `codex/stabilization-g09` از سناریوهای هم‌زمان قبلی عمداً dirty و دارای overlap در تست‌ها/اسناد canonical است. برای جلوگیری از mixed commit هیچ stage/commit/push انجام نشد؛ این مانع به artifact امضاشدهٔ RC4 و بستهٔ تحویل خارجی اثر نمی‌زند.

مرجع: F-066، ADR-48 تا ADR-50 و V-188.

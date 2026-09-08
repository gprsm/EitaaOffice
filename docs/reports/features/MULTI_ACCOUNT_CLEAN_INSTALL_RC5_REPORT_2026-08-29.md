# گزارش اصلاح نصب تازهٔ چندحسابی و RC5 — 2026-08-29

## نتیجه

علت نمایش مسیر تک‌حسابی در نصب تازه پیدا و اصلاح شد. بستهٔ RC4 از sample configای استفاده می‌کرد که AppUser Auth، Multi-session و Worker Process را خاموش داشت. RC5 هر سه قابلیت را روشن می‌کند و ترتیب صحیح را به‌صورت «فعال‌سازی دستگاه، ساخت مدیر نرم‌افزار، افزودن نخستین حساب Eitaa متعلق به مدیر و سپس Start/Auth صریح» حفظ می‌کند.

## اصلاح Backend و UI

- نصب خالیِ process-isolated دیگر برای شروع AppUser bootstrap به legacy runtime نیاز ندارد.
- تا پیش از ساخت/انتخاب حساب، routeهای نیازمند runtime با خطای امن `messenger_account_selection_required` بسته می‌مانند.
- request logging نبود account را می‌پذیرد و شناسهٔ ساختگی یا dereference نادرست ندارد.
- `AppUserGate` قبل از `MessengerAccountGate` قرار دارد. مدیر اولیه role=`admin` می‌گیرد و نخستین حساب پیام‌رسان membership=`owner/active` برای همان کاربر می‌سازد.
- ساخت حساب هیچ تماس Provider، دریافت کد، OTP یا Worker start خودکاری ندارد؛ این مراحل فقط پس از انتخاب و Start صریح حساب انجام می‌شوند.

## شواهد

- rehearsal نصب با copy واقعی `bridge.example.json`، root موقت و دادهٔ کاملاً ساختگی: setup-required، ساخت admin، فهرست حساب خالی و مالکیت `admin/owner/active` همگی PASS.
- Backend کامل: `691/691`، بدون failure/error؛ collection مستقل=`691`.
- UI onboarding=`8/8`، TypeScript=`PASS` و UI/Electron Observability=`PASS`.
- allowlist dry-run=`301 files / PASS`؛ wheel SHA-256=`F0C9BFD235108A6C6CB3891BDF163DDA163FEF3862F38587CD7CD49C8932924C`.
- payload scanner: operational state=0، private-key filename=0 و private-key PEM=0. nested payload=3555 entry و سه feature اصلی=true.
- Setup `--verify-only`، signer Thumbprint و tamper detection همگی PASS؛ status پیش از نصب CER عمومی `UnknownError` و timestamp=false مطابق قرارداد Self-signed است.

## خروجی

- Setup: `EitaaBridge-0.8.0-rc5-MultiAccount-Activated-InternalSigned-GuiSetup-x64.exe`
- اندازه Setup: `31,295,296 bytes`
- SHA-256 Setup: `2BC280463AF1B0975EA904DB8CF761BC57F0A1CC69C53DB8C8FC104E249F20CC`
- Portable: `EitaaBridge-0.8.0-rc5-MultiAccount-Activated-SelfContained-Portable.zip`
- اندازه Portable: `30,492,682 bytes`
- SHA-256 Portable: `175D80117706C0C49B391ABEE04F174E5F7952AAD327078998857CB96093E925`
- Delivery ZIP: `EitaaBridge-0.8.0-rc5-MultiAccount-InternalSigned-GuiSetup-Delivery.zip`
- اندازه Delivery ZIP: `61,883,250 bytes`
- SHA-256 Delivery ZIP: `66AF08945065BF17E503A257DFC36F8415F251E78583A8602B9A2BBA2E2C2D26`
- Delivery شامل 15 فایل است؛ Setup داخل آن hash-identical، همهٔ 10 متن strict UTF-8 BOM و finding نام/محتوای private key صفر است.
- نسخهٔ RC5 قبلی به `release/office/archive/20260829-060000` منتقل و با Manifest نگه‌داری شد.
- بستهٔ تحویل RC4 نیز به `delivery-activation-branch/archive/20260829-195620` منتقل شد.

## روش آزمون روی مقصد

برای ارتقای عادی چیزی حذف نشود؛ Setup تنظیمات و state قبلی را حفظ می‌کند. برای مشاهدهٔ مسیر نصب کاملاً تازه، برنامه بسته و پوشهٔ `%LOCALAPPDATA%\Programs\EitaaBridge` به نامی مانند `EitaaBridge.pre-rc5-test` تغییر نام داده شود، سپس Setup RC5 اجرا شود. این کار برگشت‌پذیر است و از حذف config، نشست، داده و مجوز قبلی جلوگیری می‌کند.

ورود واقعی Eitaa، OTP، Start حساب و جابه‌جایی میان دو حساب در این Run انجام نشد، چون عملیات واقعی Provider نیازمند اقدام و تأیید کاربر روی ماشین مقصد است. Windows 7 همچنان هدف پشتیبانی‌شدهٔ این Release نیست.

مرجع: F-067، ADR-52 و V-189.

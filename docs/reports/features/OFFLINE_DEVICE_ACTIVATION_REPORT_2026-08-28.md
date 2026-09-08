# گزارش فعال‌سازی آفلاین وابسته به دستگاه

تاریخ: 2026-08-28  
Run: `LICENSE-ACTIVATION-R01`  
وضعیت: `IMPLEMENTED / BRANCH_RC2_BUILT / OFFLINE_E2E_ACCEPTED / PRODUCTION_KEY_AND_CODE_SIGN_PENDING`

## نتیجه

نسخهٔ self-contained اکنون بدون مجوز معتبر دستگاه، مسیر عادی محصول را اجرا نمی‌کند. اولین Startup پنجره‌ای برای کپی request code و Paste activation code نشان می‌دهد. پس از فعال‌سازی، بررسی‌های بعدی بی‌صدا هستند. کپی پوشه یا Backup به دستگاه یا Windows user دیگر، مجوز قابل استفاده منتقل نمی‌کند.

راهکار «فرمول محرمانه داخل نرم‌افزار» کنار گذاشته شد، زیرا secret همراه برنامه قابل استخراج و تولید سریال قابل جعل می‌شد. مدل پیاده‌شده امضای نامتقارن Ed25519 است: برنامه فقط public key دارد؛ private key صدور مجوز و ابزار مالک خارج از Repository، source archive، Setup، Portable ZIP و پوشهٔ delivery نگه‌داری می‌شوند.

## شناسه و request code

برنامه Machine GUID و serial دیسک سیستم Windows را می‌خواند، هر component را جداگانه SHA-256 می‌کند و digestها را در payload canonical نسخه‌دار دوباره hash می‌کند. request code فقط Product ID، fingerprint version و digest نهایی را حمل می‌کند. هیچ component خام، نام رایانه، حساب، تلفن، پیام یا Session در کد، log یا گزارش قرار نمی‌گیرد.

کد درخواست checksum کوتاه برای تشخیص typo دارد، ولی مرجع امنیتی نیست. ابزار مالک request را parse می‌کند و activation payload شامل device digest، key/license ID، زمان صدور، expiry اختیاری، edition و featureها را با private key امضا می‌کند. برنامه signature، Product، version، زمان و device match را fail-closed تأیید می‌کند.

## ذخیره و Startup

activation code معتبر با Windows DPAPI در scope همان Windows user و write اتمیک داخل `data\licensing\activation.dat` ذخیره می‌شود. متن `EBLC1` در فایل محافظت‌شده دیده نشد. خرابی، کپی از user/device دیگر، signature نامعتبر، mismatch یا expiry مجوز را رد می‌کند.

Office launcher پیش از `ensure_backend` check می‌کند و فقط هنگام نیاز UI فعال‌سازی را باز می‌کند. `BridgeApplicationApi` و `EitaaBridge.open` نیز پیش از Config، Coordinator DB، Diagnostics یا Provider همان gate را enforce می‌کنند. Source development بدون installer marker/bundled runtime قفل نمی‌شود؛ payload customer marker صریح دارد و وجود Runtime محلی دفاع دوم است.

## RED و GREEN

- RED اولیه: `5 failed / 1 passed / 2 setup errors`. پنج failure نبود module/contract بودند؛ دو error فقط Temp پیش‌فرض غیرقابل‌دسترسی و از محصول جدا بودند.
- GREEN هدفمند/مرتبط: `60/60 passed` با basetemp کنترل‌شده.
- Backend کامل: `684/684 passed`، failure/error/skip صفر؛ collection مستقل 684 تست در 76 فایل.
- TypeScript و UI/Electron Observability: PASS.
- wheel نهایی SHA-256=`31fdfe2db2276f9682c797361a7d27800e6ce7d7ac1c269b9ac229b6e695bf0b` و source parity صفر.
- dry-run نهایی canonical پس از همسان‌سازی Release Manifest/اسناد 293 فایل، write صفر و content-set=`296a29a77d84d52abddaa17e52a460835923b09361a01faebaa02a15da698367` داشت.
- Runtime checker: cryptography=`46.0.7`، Bridge/Core/requests/tzdata و timezone PASS.
- RC2 packaged rehearsal: import cryptography/Tk/licensing، rejection پیش از activation، request→issue→activate→silent check و API پس از activation همگی PASS؛ store=890 bytes و plaintext finding=false.

## Artifact شاخه

- EXE: `EitaaBridge-0.8.0-rc2-Activated-SelfContained-Setup-x64.exe`
  - size=`46,415,360 bytes`
  - SHA-256=`84453D43A2E04F10FC2F453A81639AF6ED69C971FEE18AA8ED29EC1BC10EF02F`
  - `--verify-only=PASS`
  - signature=`NotSigned`
- ZIP: `EitaaBridge-0.8.0-rc2-Activated-SelfContained-Portable.zip`
  - size=`45,723,128 bytes`
  - SHA-256=`A78C5AAA5EF2D6BAC00BBA8F321FAF8B03419C89CFA8556C880E7A9BDE89D129`
- nested payload=`4664 files`; required license policy/documentation/cryptography/verifier/UI حاضر؛ private-key name/PEM=0 و operational entry=0.

## کلید و محدودیت Production

کلید فعلی برای آزمون شاخه ساخته شده، بدون رمز است و فقط بیرون Repository/delivery نگه‌داری می‌شود. این کلید نباید مبنای انتشار Production باشد. مالک باید پس از تأیید طرح، با ابزار `tools/license_admin.py` یک private key رمزدار تازه تولید کند؛ public key برنامه جایگزین، Setup دوباره ساخته و همهٔ شواهد تکرار شوند. private key نیازمند backup آفلاین، کنترل دسترسی و برنامهٔ rotation/revocation است.

طبق درخواست کاربر این تغییر فعلاً فقط در شاخهٔ جاری نگه داشته شد و به پروژهٔ اصلی کپی نشد. Git stage/commit/push نیز برای جلوگیری از انتشار پیش از review و مخلوط‌شدن با تغییرهای هم‌زمان انجام نشد.

این سازوکار جعل مجوز بدون private key، ویرایش و کپی معمول فایل را مهار می‌کند؛ ادعای DRM مطلق ندارد. مدیر محلی متخصص می‌تواند برای Patch کردن Python یا launcher تلاش کند. Code-sign، integrity hardening یا کامپایل verifier هزینهٔ دورزدن را بالا می‌برد، اما تضمین نظری ایجاد نمی‌کند.

نصب واقعی در `%LOCALAPPDATA%`، Login/OTP، Provider، Send، WordPress یا دادهٔ عملیاتی اجرا نشد. مرجع تصمیم ADR-49، Finding برابر F-063 و Validation برابر V-185 است.

# گزارش امضای داخلی و برندینگ Windows

## وضعیت

مسیر گواهی Self-signed، CER عمومی، pin کردن Thumbprint، امضای Authenticode SHA-256، hash پس از امضا، آزمون دستکاری و wiring آیکون Setup/Desktop/Start Menu پیاده و آزمایش شد. تصویر تأییدشدهٔ کاربر به ICO چنداندازه تبدیل و RC3 تک‌فایلی برندشده، امضاشده و قابل‌تحویل ساخته شد.

## تصمیم امنیتی

گواهی Authenticode از کلید Ed25519 فعال‌سازی مستقل است. گواهی با Subject برابر `CN=Eitaa Bridge Internal Publisher` و EKU کد امضا (`1.3.6.1.5.5.7.3.3`) در `Cert:\CurrentUser\My` ساخته شد. کلید RSA 3072-bit با سیاست `NonExportable` ایجاد شد؛ کنترل زندهٔ provider مقدار export policy را `None` نشان داد. هیچ PFX یا private key در Repository، Setup یا پوشهٔ تحویل تولید نشد.

Thumbprint عمومی گواهی این Run:

```text
441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02
```

CER صادرشده کلید خصوصی ندارد و تا 2031-08-28 معتبر است. trust bundle عمومی شامل CER، `certificate-metadata.json`، فایل Thumbprint، راهنمای فارسی و اسکریپت نصب اعتماد است. metadata، CER، guide و script همگی همان Thumbprint را گزارش می‌کنند و SHA-256 CER با metadata برابر است.

در بازبینی پس از تحویل، فایل راهنمای فارسی از نظر ساختار بایت UTF-8 بود اما Windows PowerShell 5.1 متن source بدون BOM را پیش از تولید به mojibake تبدیل کرده بود؛ backtickهای Markdown نیز مانع جای‌گذاری سه مقدار گواهی شده بودند. generator با BOM اجباری برای source، placeholderهای صریح و `UTF8Encoding(true)` اصلاح و trust bundle با همان گواهی بازتولید شد. ممیزی نهایی همهٔ هفت فایل متنی delivery: strict UTF-8 with BOM=`PASS`، replacement character=0، mojibake marker=0 و placeholder حل‌نشده=0. راهنما اکنون Thumbprint، SHA-256 CER و پایان اعتبار واقعی را دارد؛ JSON parse، syntax اسکریپت اعتماد، public-only CER و تطبیق hash/Thumbprint نیز PASS هستند.

Setup گواهی را به‌طور پنهان اعتماد نمی‌دهد. کاربر مقصد باید Thumbprint را از کانال مستقل کنترل و سپس اسکریپت عمومی را برای Current User اجرا کند؛ اعتماد LocalMachine نیازمند Administrator است. Self-signed اعتبار تجاری عمومی یا SmartScreen reputation ایجاد نمی‌کند.

## برندینگ

Builder اکنون `installer/assets/EitaaBridge.ico` معتبر را اجباری می‌کند و آن را با `/win32icon` در EXE می‌گذارد. همان ICO در payload زیر `assets/EitaaBridge.ico` نصب می‌شود و میانبرهای Desktop و Start Menu `IconLocation` همان فایل را دارند. fallback بدون آیکون IExpress دیگر به‌عنوان Setup نهایی منتشر نمی‌شود.

فایل کاربر PNG واقعی `520×520 / Format32bppArgb` با SHA-256=`6ED4762BFC43C9A022A0FF19BC617043F5441FB64617B2E23C7C31B0227EFA1C` بود. محتوای لوگو با ImageGen تغییر داده نشد؛ converter deterministic با alpha-preserving `SourceCopy` و `HighQualityBicubic` frameهای 16، 20، 24، 32، 40، 48، 64، 128 و 256 پیکسل را ساخت. ICO نهایی SHA-256=`8C35B98F9291F066D200E587208C50B48032DAEDDD495CB2EAB62C9EC8C1F5F7` دارد؛ frameهای 32/256 و آیکون 32 استخراج‌شده از خود EXE بصری پذیرفته شدند.

## امضا و آزمون

- RED قرارداد برندینگ/امضا با نبود asset و scriptها ثبت شد؛ پس از ورود asset، قرارداد ICO مفقود نیز RED و مجموعهٔ هدفمند نهایی سبز شد.
- parser هر سه PowerShell script بدون خطا بود.
- یک کپی 46,415,360 بایتی از RC2 برای probe امضا شد؛ signer Thumbprint دقیقاً برابر گواهی بالا و SHA-256 پس از امضا برابر `A1C2BAC4BB15062C4351AD4F303DF8464A0FDAE5C94D0950CB0508F454264E32` بود.
- تلاش نخست امضای Batch پس از ساخت EXE به نبود drive مجازی `Cert:` در PowerShell فرزند خورد؛ signer به `X509Store(CurrentUser/My)` مستقیم منتقل شد و همان EXE بدون rebuild payload امضا شد. این repair وابستگی به provider drive را حذف کرد.
- RC3 Setup=`46,842,176 bytes / SHA-256 9587728CD28E6EA6B7DD499EBE94B73361DF79757C74E4346A29BE5398986463`. signer Thumbprint دقیقاً مطابق گواهی است، `--verify-only=PASS` و tamper detection=true. چون CER عمداً در مخزن اعتماد حساب Build نصب نشد، status ویندوز=`UnknownError` و timestamp=false است؛ پس از trust آگاهانهٔ CER chain معتبر می‌شود.
- Portable RC3=`45,936,308 bytes / SHA-256 07931D6E3905FF4E1A1630F682AA073F4A9A192E7A90576FFAA59120EBF53566`.
- payload داخلی Setup=4665 entry؛ ICO نصب‌شونده byte-identical با source ICO، shortcut contract=true، operational entry=0 و private-key-named entry=0.
- delivery ZIP=`92,766,896 bytes / SHA-256 81C45B1449A386D1FA7E6809CF18FB197A3D1ADAB52F0DFB01E5EB20E48CF15E`؛ Setup داخل ZIP با manifest/hash/signer بیرونی یکسان و private-key-named entry=0 است.
- اجرای واقعی trust installer در sandbox به `E_ACCESSDENIED` خورد و درخواست تغییر پایدار Root/TrustedPublisher حساب اصلی نیز به‌دلیل نیاز به اجازهٔ مستقل امنیتی اجرا نشد. parser، pin، CER hash و public-only boundary سبزند؛ نصب اعتماد واقعی مقصد همچنان گام صریح کاربر است.
- full Backend نهایی=`688/688`، collection=`688 tests / 76 files`؛ TypeScript و UI/Electron Observability پیش از تغییر asset سبز و UI source در این Run بدون تغییر بود.

## گیت باقی‌مانده

نصب واقعی برنامه در `%LOCALAPPDATA%` و مشاهدهٔ میانبرها روی ماشین مقصد انجام نشد، زیرا طبق policy نیازمند تأیید همان لحظه و mutation محیط کاربر است. Self-signed همچنان public CA/SmartScreen reputation نمی‌سازد و trust مقصد باید صریح باشد. Production key فعال‌سازی و clean-machine real-user acceptance مستقل باقی‌اند.

Provider، Login/OTP، Send، WordPress، Firewall/Proxy و دادهٔ عملیاتی در این Run انجام نشد. Git stage/commit/push نیز به‌علت worktree هم‌زمان و overlap اسناد canonical انجام نشد تا mixed commit ساخته نشود.

مرجع: ADR-50، F-064 و V-186.

# P8 — آزمون آنلاین و گرم با اختیار محدود

وضعیت اولیه: PLANNED. پیش‌نیاز: بخش مربوط P7 و دروازه‌های offline PASS؛ برای بله B6 و برای AI P6. [قواعد مشترک](EXECUTION_RULES.md).

## ابزار را کامل کن، Live را جعل نکن

runner/selftest و runbook opt-in بساز. default اجرای آن بدون اثر خارجی باشد؛ CI و pytest عمومی هیچ حساب واقعی باز نکنند. حالت dry-plan فقط مشخص کند کدام عملیات با چه profile، capability و سقف اثر قرار است اجرا شوند؛ secret/شماره در output نباشد. endpoint و حساب باید allowlisted باشند؛ localhost به‌تنهایی اثبات fake بودن نیست.

«گرم»: نشست احراز‌شدهٔ مالک و اتصال سالم همان حساب با lifecycle صحیح reuse شود؛ runner startup هیچ OTP، import یا send خودکار ندارد. auth challenge تازه فقط با مجوز جدا. ابزار باید حالت سرد/گرم، generation اتصال و دفعات connect را با metadata امن تفکیک کند؛ زمان اجرای تنها شاهد warm بودن نیست.

## آماده‌سازی و تأیید همان لحظه

قبل از درخواست اجازه، تمام کارهای مستقل ابزار، fake tests، rate/error scenarios و doc gates را تمام کن. سپس برنامهٔ مشخص بده: Provider، برچسب امن حساب، نوع گیرندهٔ مورد رضایت، افزودن/تغییر مخاطب یا فقط موجود، تعداد محدود پیام، مقصد AI و هزینهٔ محدود، TTL، معیار abort. مالک همان برنامه را تأیید کند؛ درخواست کلی این سند اجازهٔ ارسال واقعی نیست.

ورودی‌ها از تنظیمات امن/UI یا secret store گرفته شوند، نه argv، log یا فایل tracked. شماره و متن خصوصی در گزارش، traceback، pytest/JUnit، HAR و screenshot نباشند. network capture و dump payload پیش‌فرض خاموش؛ report فقط revisionها، نوع عملیات، وضعیت، counts، latency و شاهد تأیید غیرخصوصی.

## ماتریس اجرا، مستقل برای هر قابلیت

- Eitaa: سلامت نشست گرم و حساب منتخب؛ یک ارسال محدود به مخاطب مورد تأیید؛ در صورت مجوز جدا یک شمارهٔ تازه با نام درست، receipt contact→send و تأیید OTP توسط backend وب. تکرار همان operation نباید ارسال Provider تازه ایجاد کند.
- Bale Personal: همین مسیر با حساب مستقل و peer بله؛ شاهد تاریخی V-194/V-195 به‌جای witness مخاطب‌نویسی تازه پذیرفته نشود. افزودن/حذف مخاطب دو effect جدا با اجازه‌اند؛ پاک‌سازی خودکار مخاطب کاربر ممنوع.
- AI: probe محتوای ساختگی و سپس مسیر مجاز P6 با payload حداقلی، model_id واقعی و is_test_response=false. بدون key/مجوز، PENDING_INPUT، نه PASS و نه توقف آزمون مستقل Eitaa.
- client: preflight پیش از مرحلهٔ OTP، reservation، status/poll، challenge expiry و verification واقعی وب. حدود rate/cooldown با fake آزموده شوند؛ برای تولید 429 واقعی spam نکن.
- mixed account: metadata نشان دهد sender همان profile است و داده/نشست حساب دیگر استفاده نشده. تعویض Provider نباید recipient mapping قدیمی را reuse کند.

تعداد RPC محلی، شمار تلاش ارسال و نتیجهٔ readback/تأیید گیرنده را جدا گزارش کن. نبود API delivery receipt را با accepted بیان کن؛ readback تاریخچهٔ فرستنده ثابت نمی‌کند دستگاه گیرنده پیام را دریافت کرده است.

## توقف امن

timeout، invalid session، retry_after، unexpected recipient/account، uncertain و privacy violation اجرای اثر بعدی را متوقف کنند. state/status عملیات جاری تعیین تکلیف شود؛ runner هنگام interrupt رزرو مصرف‌نشده را idempotent cancel کند، اما send_started را refund یا resend نکند. راهنمای recovery فقط استعلام status و اقدام دارای مجوز باشد، نه reset session یا حذف operational data.

نتیجهٔ هر بخش: PASS/FAIL/PENDING_INPUT/BLOCKED با شاهد و revision مستقل. تغییر کد/config مرتبط پس از witness، اعتبار آن بخش را دوباره ارزیابی می‌کند؛ بازآزمایی طبق Ledger علت لازم دارد.

شاهد معتبر B6 برای قابلیت بدون تغییر دوباره مصرف شود، نه اینکه فقط به دلیل نام فاز دوباره پیام/مخاطب واقعی بسازی. مسیر تازهٔ وب/رزرو/OTP اگر بعد از B6 تغییر کرده، شاهد جدا لازم دارد؛ علت بازآزمایی را قبل از اجرا در Ledger بنویس.

## پذیرش

P8-A01: runner، dry-plan، opt-in guard، warm ownership و privacy مستقل PASS.

P8-A02: ماتریس Eitaa با اجازه و شاهد مشخص تکمیل شده یا ورودی مفقود دقیق ثبت شده است.

P8-A03: ماتریس Bale و AI هرکدام مستقل با witness یا وضعیت ناتمام واقعی ثبت‌اند.

P8-A04: abort/recovery، counts و جلوگیری از replay effect تأیید شده‌اند.

P8-A05: گزارش، Ledger و دروازه‌های post-change کامل‌اند؛ هیچ fake به‌عنوان Live گزارش نشده.

خروجی: docs/reports/validation/WEB_CLIENT_LIVE_WARM_ACCEPTANCE_REPORT.md و handoff متناظر. P8 با ابزار کامل ولی Live انجام‌نشده، OFFLINE_READY/LIVE_PENDING است؛ پایان محصول کامل نیست.

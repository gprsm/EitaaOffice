# پرامپت انتقال به چت جدید — آغاز فاز ۶-A

کار روی پروژهٔ زیر را ادامه بده:

`C:\Users\Mohsen\Documents\eitaa\Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`

این پروژه از فاز صفر تا فاز ۵ برای معماری چندکاربره، چندحسابی و چندپیام‌رسانی توسعه یافته است. قبل از هر تغییر، فایل زیر را **کامل** بخوان و آن را مرجع اصلی وضعیت و نقشهٔ ادامه بدان:

`../reports/architecture/HTTP_LAN_MULTIUSER_CONTINUATION_REPORT_2026-08-02.md`

سپس حداقل این گزارش‌ها را کامل بخوان:

- `../reports/phases/PHASE5_SHARED_LOCAL_CONTACTS_AUDIT_REPORT.md`
- `../reports/phases/PHASE4D_MESSENGER_ACCOUNT_MANAGEMENT_REPORT.md`
- `../reports/phases/PHASE4C_EITAA_ACCOUNT_AUTH_LIFECYCLE_REPORT.md`
- `../reports/phases/PHASE4B_EITAA_ACCOUNT_RUNTIME_REPORT.md`
- `../reports/phases/PHASE4A_EITAA_SESSION_OWNERSHIP_REPORT.md`
- `../reports/phases/PHASE3_APP_USER_AUTH_REPORT.md`
- `../reports/phases/PHASE2_COORDINATOR_MIGRATION_REPORT.md`
- `../reports/phases/PHASE1_MULTI_PROVIDER_ARCHITECTURE_REPORT.md`
- `../reports/architecture/MULTI_SESSION_ARCHITECTURE_REPORT.md`
- `../reports/features/CONTACT_IMPORT_REMOTE_FIX_AND_LOGGING_REPORT_2026-07-30.md`

وضعیت Git، فایل‌های تغییرکرده و آزمون‌ها را بررسی کن. Worktree عمداً Dirty است و تغییرات فازهای صفر تا پنج هنوز Commit نشده‌اند؛ همهٔ تغییرات و فایل‌های کاربر را حفظ کن. پوشهٔ `catalog` فقط مرجع خواندنی است. هیچ Commit یا Push انجام نده مگر اینکه من صریحاً درخواست کنم.

## سناریوی قطعی جدید

- برنامه در آینده روی یک رایانه/سرور ویندوزی در شبکهٔ داخلی خصوصی اجرا می‌شود.
- رایانهٔ مرکزی به مودم‌روتر ADSL متصل است و موبایل کاربران از Wi-Fi همان مودم‌روتر استفاده می‌کند. هر دو باید در یک LAN خصوصی و قابل دسترسی متقابل باشند.
- چند AppUser، عمدتاً با مرورگر تلفن همراه، با IP ثابت/رزروشدهٔ رایانه و HTTP وارد می‌شوند.
- هر کاربر باید فقط PhoneAccountها و MessengerAccountهای مجاز خود را ببیند و استفاده کند.
- یک شماره یک PhoneAccount است و می‌تواند حساب مستقل ایتا و بله داشته باشد.
- دفترچه و دسته‌های محلی مشترک‌اند؛ Session، دادهٔ پیام‌رسان، Cache، Worker، Job، Media و Log حسابی جدا هستند.
- تنظیمات WordPress در سطح کل نصب میان همهٔ AppUserهای فعال مشترک است. همه می‌توانند از Site/Profileهای فعال استفاده کنند، اما فقط `admin` می‌تواند تنظیمات اتصال یا Credential را ایجاد/تغییر دهد. Credential فقط سمت سرور نگهداری می‌شود و Draft، انتخاب جاری، Upload موقت، Job و Audit آغازکننده همچنان کاربرمحور هستند.
- رابط موبایل باید کاملاً Touch-first و بهینه باشد، نه نسخهٔ کوچک‌شدهٔ Desktop. یک Codebase و API مشترک حفظ کن، اما در فازهای رابط از `MobileShell` و `DesktopShell` یا تفکیک Presentation مشابه استفاده کن؛ منطق دامنه مشترک بماند و Navigation، Card/List، Dialog و فرم موبایل بتوانند مستقل باشند.
- عملیات کانال فقط با MessengerAccount انتخاب‌شدهٔ همان کاربر و پس از کنترل Server-side مدیر بودن انجام می‌شود. انتشار در کانال با ارسال مستقیم انبوه به اعضا یکی نیست؛ ارسال مستقیم باید رضایت/Opt-out، Capability و Rate limit Provider را رعایت کند.
- بنا به تصمیم آگاهانهٔ من، استقرار LAN باید با **HTTP و بدون HTTPS و بدون گواهی داخلی** قابل انجام باشد.
- خطر شنود و دست‌کاری ترافیک HTTP پذیرفته شده است؛ آن را دقیق مستند کن، اما HTTPS را شرط ادامه یا فعال‌سازی نکن.
- در عین حال، معماری را طوری نگه دار که افزودن HTTPS در آینده نیازمند بازنویسی بنیادی نباشد.
- API بله در این نوبت خارج از Scope است و نباید حدس زده شود.

## فقط فاز ۶-A را اجرا کن

عنوان فاز:

**قرارداد استقرار و Config امن برای چندکاربرهٔ HTTP روی LAN خصوصی**

کارهای لازم:

1. وضعیت فعلی محدودیت Loopback در Config، HTTP adapter، Electron launcher، AppUser auth، Host/Origin validation و آزمون‌ها را ممیزی کن.
2. دو حالت صریح و نسخه‌دار طراحی و پیاده‌سازی کن:
   - `desktop_loopback` به‌عنوان پیش‌فرض سازگار فعلی
   - `trusted_lan_http` فقط با Config صریح
3. برای LAN mode قرارداد Config لازم را ایجاد کن، شامل مفهوم‌های زیر با نام‌گذاری مناسب و سازگار با ساختار پروژه:
   - Bind host و port
   - Allowed hosts
   - Allowed origins
   - Allowed private client CIDRs
   - Cleartext-risk acknowledgement
   - سیاست Remote messenger authentication
   - پیش‌شرط private LAN و منع Public/Guest network
4. حالت LAN باید Fail-closed باشد. حداقل در این حالت‌ها Startup رد شود:
   - AppUser authentication خاموش است.
   - تأیید صریح خطر HTTP وجود ندارد.
   - Host، Origin یا CIDR مجاز خالی/باز/نامعتبر است.
   - Config ناخواسته همه مبدأها یا شبکه عمومی را مجاز می‌کند.
5. حالت Legacy/Loopback با Config فعلی نباید تغییر رفتار دهد.
6. Bootstrap مدیر اولیه را به‌طور پیش‌فرض Loopback-only نگه دار.
7. Remote messenger Login/OTP/2FA را در LAN mode به‌طور پیش‌فرض خاموش نگه دار و برای فعال‌سازی احتمالی آینده یک سیاست صریح با تأیید خطر جداگانه در نظر بگیر. در این فاز آن را فعال نکن.
8. UI و API باید در طرح نهایی Same-origin باشند؛ CORS عمومی یا wildcard مجاز نیست.
9. `0.0.0.0` یا Non-loopback نباید بدون قیود فوق به‌صورت تصادفی قابل استفاده شود. Bind خودکار یا کشف/بازکردن پورت انجام نده.
10. Config نمونه و توضیح فارسی روشن برای مدیر سیستم اضافه کن. هیچ Secret، شمارهٔ کامل، Token، Cookie یا Session را در نمونه‌ها و گزارش وارد نکن.
    راهنما باید IP ثابت/DHCP reservation، احتمال Guest Wi-Fi یا AP/Client Isolation، Windows Firewall محدود به Subnet و منع Port Forwarding/DMZ/UPnP را توضیح دهد؛ در این فاز هیچ‌کدام را عملاً تغییر نده.
    تصمیم ثبت‌شدهٔ WordPress مشترک نصب و راهبرد یک Codebase با MobileShell/DesktopShell را در مستند معماری حفظ کن، اما پیاده‌سازی کامل آن‌ها را در فاز ۶-A آغاز نکن.
11. آزمون‌های متمرکز Loader/Startup/Host/Origin/CIDR و سازگاری Loopback را اضافه کن. در صورت تغییر رابط، TypeScript/Vite را نیز بررسی کن.
12. آزمون کامل مرتبط و سپس مجموعهٔ کامل را تا حد معقول اجرا کن. شکست تاریخی زیر را دوباره تشخیص بده، ولی فقط اگر واقعاً مستقل است آن را به‌عنوان Baseline ثبت کن؛ نتیجه را جعل نکن:

`tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`

13. لاگ و Audit باید Context امن داشته باشند و هیچ Secret، شمارهٔ کامل، رمز، OTP، Token نشست یا محتوای خصوصی را ثبت نکنند.

## مرزهای این نوبت

- فقط فاز ۶-A؛ وارد ۶-B یا فازهای بعد نشو.
- هیچ پورت واقعی شبکه یا Rule فایروال را باز/اعمال نکن.
- `bridge.json` واقعی و Feature Flagهای نصب واقعی را فعال نکن.
- دادهٔ واقعی Contacts/Coordinator/Session را مهاجرت یا بازنویسی نکن.
- هیچ Login، Logout، OTP، Status یا Send واقعی ایتا انجام نده.
- هیچ اتصال یا API فرضی بله ایجاد نکن.
- هیچ Dependency جدیدی بدون ضرورت و تأیید من نصب نکن.
- فایل‌های Legacy را حذف نکن و Rollback را حفظ کن.
- Commit و Push نکن.

## خروجی لازم

پس از پیاده‌سازی و آزمون:

1. فایل `../reports/phases/PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md` را ایجاد کن.
2. در آن تصمیم‌های Config، فایل‌های تغییرکرده، نتیجهٔ دقیق آزمون‌ها، وضعیت واقعی Feature Flagها، محدودیت HTTP و ریسک‌های باقی‌مانده را بنویس.
3. بررسی کن که نرم‌افزار با تنظیمات فعلی همچنان در حالت Loopback/Legacy کار می‌کند.
4. دستور دقیق و کوتاه آغاز فاز ۶-B را در انتهای گزارش ثبت کن.
5. سپس متوقف شو و منتظر دستور من برای فاز ۶-B بمان.

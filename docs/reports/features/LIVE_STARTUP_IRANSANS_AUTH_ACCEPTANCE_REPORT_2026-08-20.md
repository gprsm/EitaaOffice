# گزارش رفع راه‌اندازی، IRANSans و پذیرش زندهٔ ورود ایتا

تاریخ: ۲۰۲۶-۰۸-۲۰  
وضعیت: `IMPLEMENTED / FULL_AUTOMATED_VERIFIED / LIVE_EITAA_READ_ACCEPTED`

## دامنه

- جلوگیری از خروج owned Backend در شروع Electron؛
- بارگذاری واقعی دو وزن فونت IRANSans در تم مرکزی Material UI؛
- جداسازی نشست AppUser از نشست Provider در client؛
- مقاوم‌سازی ورود OTP برای رقم فارسی/عربی و خطاهای رایج Provider؛
- پذیرش زندهٔ ورود و خواندن/همگام‌سازی ایتا بدون ارسال پیام؛
- ثبت محدودهٔ مجوز WordPress و ارسال آزمایشی بدون ذخیرهٔ هویت خصوصی گیرنده.

## یافته‌ها و اصلاح‌ها

### ۱. Backend توسعه از artifact قدیمی شروع می‌شد

در اجرای source، Electron فایل entry-point ساخته‌شدهٔ قدیمی را به Python module جاری ترجیح می‌داد. آن artifact با exit code غیرصفر خارج می‌شد، در حالی که اجرای `python -m eitaa_bridge.interfaces.http_api` سالم بود. اجرای development اکنون Python module جاری را ترجیح می‌دهد؛ build بسته‌بندی‌شده همچنان executable انتشار را ترجیح می‌دهد.

### ۲. نسخهٔ مورد انتظار Electron از نسخهٔ canonical جدا شده بود

نسخهٔ hard-coded قدیمی باعث می‌شد Backend سالم با Health 200 نیز ناسازگار تشخیص داده و متوقف شود. نسخهٔ مورد انتظار اکنون از خط نخست `VERSION.txt` خوانده می‌شود و fallback بسته‌بندی‌شده محدود و معتبر دارد.

### ۳. نام IRANSans بدون `@font-face` فعال بود

Theme نام فونت را داشت، اما تعریف `@font-face` فقط در stylesheet تاریخی و خارج از graph فعال Material-only باقی مانده بود. دو فایل موجود Regular/Bold اکنون در `MuiCssBaseline.styleOverrides` با `font-display: swap` و مسیر نسبی سازگار با `file://` و HTTP ثبت شده‌اند. هیچ class یا stylesheet طراحی تازه‌ای اضافه نشد.

### ۴. invalid شدن نشست Provider، CSRF نشست AppUser را پاک می‌کرد

Client مقدار `session_invalid` مربوط به Eitaa را با invalid شدن AppUser اشتباه می‌گرفت و CSRF کاربر نرم‌افزار را پیش از reset خودکار حذف می‌کرد. پاک‌سازی CSRF اکنون فقط به logout یا invalid شدن صریح `/api/v2/app-auth/status` محدود است.

### ۵. OTP محلی‌سازی‌شده و خطای Provider

کد ورود در UI و Backend با NFKC نرمال می‌شود؛ رقم فارسی/عربی به ASCII تبدیل و فاصله و directional mark حذف می‌شوند. قالب نامعتبر پیش از Provider با error امن رد می‌شود. خطاهای allowlisted کد اشتباه، منقضی و محدودیت تلاش به error code و متن فارسی مشخص نگاشت می‌شوند و متن خام Provider یا خود OTP وارد log/audit نمی‌شود. UI دکمهٔ «دریافت کد تازه» دارد و کد منقضی را با چالش تازه جایگزین می‌کند.

## پذیرش زنده

- برنامهٔ بازسازی‌شده روی loopback با Health 200 بالا آمد و پس از آخرین restart رخداد health-timeout تازه نداشت.
- ورود AppUser، reset خودکار نشست نامعتبر و درخواست کد Provider موفق شدند.
- چند تلاش اولیهٔ OTP به‌صورت امن رد شدند؛ هیچ OTP در log/audit ثبت نشد. پس از اصلاح و دریافت چالش تازه، رخداد `eitaa.auth.login.completed` ثبت شد.
- پس از ورود، `dialogs/live-sync`، `messages/sync` و `messages/list` به‌صورت پیوسته پاسخ 200 دادند. این شاهد Live برای خواندن و near-real-time polling حساب موجود است.
- هیچ پیام، دعوت، contact mutation یا WordPress publish در این پذیرش انجام نشد.

## محدودهٔ مجوز عملیاتی مالک

- WordPress فقط روی محیط آزمایشی Laragon و پس از اعلام روشن‌بودن آن قابل پذیرش زنده است.
- ارسال آزمایشی Eitaa فقط به alias داخلی `owner_approved_test_recipient` مجاز است. نام و شمارهٔ واقعی این گیرنده در کد، log، audit، test artifact یا سند ذخیره نمی‌شود.
- این مجوزها عمومی، دائمی یا قابل تعمیم به گیرنده/سایت دیگر نیستند.

## آزمون‌ها

- Red/green اختصاصی برای انتخاب runtime توسعه، منبع نسخه، دو وزن فونت، استقلال CSRF، OTP محلی‌سازی‌شده و نگاشت خطای Provider ثبت شد.
- Backend کامل: `580/580`.
- Runtime ownership: `21/21` در مرحلهٔ هدفمند پیش از OTP.
- Auth/Material هدفمند نهایی: `38/38`.
- npm شماره‌دار: Scroll `10/10`، Grouped Media `16/16`، Phase 9=`22/22`، Phase 10=`7/7`، Phase 11=`13/13`؛ Observability و mobile-auth-live نیز موفق.
- TypeScript check و production build موفق؛ build شامل 1008 module و chunk اصلی `788.97 kB`، gzip=`241.76 kB` است. warning بالاتر از 500 kB همچنان F-013 و non-blocking است.
- اسکن لاگ زنده: application=`8827`، worker=`678`، invalid JSON=`0` و finding=`0`.

## Failure ledger

1. نخستین invocation هدفمند نام test ناموجود داشت؛ شاهد Python نساخت و با فایل canonical تکرار شد.
2. یک اجرای pytest به‌علت نبود parent مربوط به basetemp شروع نشد؛ parent محدود workspace ساخته و suite تکرار شد.
3. هر آزمون red جدید ابتدا دقیقاً روی رفتار قدیمی شکست خورد و سپس سبز شد.
4. assertion قدیمی Phase 10 هنوز payload خام `code` را مطالبه می‌کرد؛ قرارداد به normalization امن ارتقا یافت و `7/7` شد.
5. فرمان نخست privacy scanner آرگومان پشتیبانی‌نشده داشت؛ help خوانده و invocation canonical بدون echo دادهٔ خصوصی موفق شد.
6. Screenshot ابزار کنترل Windows با accessibility tree برنامه همخوان نبود؛ هیچ click مبتنی بر تصویر نامعتبر انجام نشد و شاهد دیداری تازه برای فونت ادعا نمی‌شود.

## Trigger ابطال

تغییر `ui/electron/main.cjs`، `VERSION.txt`، `ui/src/theme.ts`، `ui/src/lib/api.ts`، Login Gate، auth lifecycle/OTP mapping، فایل‌های فونت یا Provider polling نیازمند تکرار شاهد مرتبط است.

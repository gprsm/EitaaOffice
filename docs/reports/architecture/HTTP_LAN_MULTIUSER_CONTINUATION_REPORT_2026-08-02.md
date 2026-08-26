# گزارش انتقال کار: چندکاربرهٔ شبکهٔ داخلی با HTTP

- تاریخ: ۲۰۲۶-۰۸-۰۲
- پروژه: `Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- مسیر فعلی: `C:\Users\Mohsen\Documents\eitaa\Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`
- شاخهٔ مشاهده‌شده: `main`
- Commit مبنا پیش از فازهای جدید: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- وضعیت برنامه از دید کاربر: نسخهٔ فعلی در حالت Legacy درست کار می‌کند.
- وضعیت این سند: نقشهٔ لازم‌الاجرا برای ادامه؛ این سند خودش Feature جدیدی را فعال نمی‌کند.

## تصمیم جدید کاربر

سناریوی مقصد از این پس چنین است:

1. برنامه روی یک رایانه/سرور ویندوزی در شبکهٔ داخلی اجرا می‌شود.
2. چند کاربر، عمدتاً با مرورگر تلفن همراه، از طریق Wi-Fi/LAN خصوصی به برنامه متصل می‌شوند.
3. هر AppUser با هویت خود وارد نرم‌افزار می‌شود و فقط PhoneAccountها و MessengerAccountهای مجاز خود را می‌بیند.
4. یک شماره تلفن یک `PhoneAccount` است و می‌تواند برای ایتا و بله `MessengerAccount`های جدا داشته باشد.
5. دفترچهٔ محلی و دسته‌های محلی مشترک باقی می‌مانند؛ دادهٔ واقعی پیام‌رسان، Session، Cache، Job، Media و Log حسابی جدا است.
6. کاربر آگاهانه خواسته است استقرار شبکهٔ خصوصی با **HTTP و بدون HTTPS یا گواهی داخلی** قابل انجام باشد.
7. معماری نباید HTTPS را پیش‌شرط اجرا قرار دهد، اما امکان افزودن آن در آینده نیز نباید با بازنویسی بنیادی همراه شود.
8. بله فعلاً فقط در مدل عمومی Provider دیده می‌شود؛ دربارهٔ API آن بعداً و در گفت‌وگویی مستقل تصمیم گرفته می‌شود.

### توپولوژی واقعی شبکهٔ کاربر

- یک رایانهٔ مرکزی به مودم‌روتر ADSL متصل است و برنامه روی همان رایانه اجرا می‌شود.
- تلفن‌های همراه کاربران از طریق Wi-Fi همان مودم‌روتر متصل می‌شوند.
- رایانه و گوشی‌ها باید در یک LAN و محدودهٔ IP خصوصی قابل دسترسی متقابل باشند.
- کاربران با مرورگر موبایل به IP ثابت یا رزروشدهٔ رایانه و Port برنامه، برای مثال `http://192.168.1.20:<port>`، متصل می‌شوند.
- مودم‌روتر نقش Gateway/DHCP را دارد؛ برنامه نباید با Port Forwarding، DMZ یا UPnP روی اینترنت منتشر شود.
- Guest Wi-Fi، AP/Client Isolation یا جداسازی شبکهٔ بی‌سیم از LAN سیمی می‌تواند دسترسی گوشی به رایانه را مسدود کند و باید در پذیرش شبکه کنترل شود.
- بهتر است برای رایانه در DHCP مودم Address Reservation تعریف شود تا آدرس برنامه تغییر نکند.
- Windows Firewall فقط Port برنامه را برای Subnet خصوصی لازم باز می‌کند؛ اعمال Rule نیازمند تأیید صریح کاربر است.
- اتصال اینترنت مودم برای دسترسی خود سرور به ایتا، وردپرس یا Providerهای دیگر استفاده می‌شود؛ مرورگر موبایل مستقیماً Credential پیام‌رسان یا وردپرس را نگهداری نمی‌کند.

### عملیات مورد انتظار کاربران

هر AppUser پس از ورود باید بتواند، فقط در محدودهٔ مجوزهای خود، عملیات زیر را انجام دهد:

- انتخاب MessengerAccount متعلق یا واگذارشده به خودش؛
- مشاهده و استفاده از گفتگوها، کانال‌ها، گروه‌ها و مخاطبان همان حساب؛
- انجام عملیات مجاز روی کانالی که Provider تأیید می‌کند حساب انتخاب‌شده در آن مدیر است؛
- ارسال/انتشار فقط با همان حساب انتخاب‌شده و بدون استفاده از Session کاربر دیگر؛
- انتخاب WordPress site/integration مشترک نصب و انتقال مطالب به آن بدون دریافت Credential خام در مرورگر؛
- مشاهدهٔ Job، نتیجه، خطا و Audit فقط در Scope خودش.

عبارت «ارسال به همهٔ اعضای کانالی که کاربر مدیر آن است» در پیاده‌سازی باید به دو عملیات متفاوت تفکیک شود:

1. **انتشار یک پیام داخل خود کانال:** یک عملیات انتشار در کانال است.
2. **ارسال مستقیم جداگانه به اعضای کانال:** عملیات انبوه و حساس است و فقط در صورت پشتیبانی API، مجوز حساب، رضایت/Opt-out گیرندگان و رعایت Rate limit و سیاست Provider انجام می‌شود. Rate limit یک حساب هرگز با حساب دیگر دور زده نمی‌شود.

تشخیص مدیر بودن فقط در سمت سرور و از دادهٔ Provider انجام می‌شود؛ ادعای رابط یا شناسهٔ ارسالی کاربر قابل اعتماد نیست.

### جایگاه WordPress در معماری

WordPress یک `MessengerAccount` نیست و به شماره تلفن وابسته نمی‌شود؛ یک `AppIntegration` مشترک در سطح کل نصب است. بنا به تصمیم کاربر، تنظیمات WordPress باید برای همهٔ AppUserهای فعال مشترک باشد:

```text
Application Installation -> Shared WordPressSite/Profile
                         -> usable by every active AppUser
```

- همهٔ AppUserهای فعال می‌توانند Site/Profileهای فعال را ببینند و برای عملیات مجاز استفاده کنند.
- فقط نقش `admin` می‌تواند Site/Profile، URL، Username، Credential، Policy یا وضعیت فعال‌بودن اتصال را ایجاد یا تغییر دهد؛ نقش `user` فقط استفاده می‌کند.
- URL و نام نمایشی قابل نمایش‌اند، اما Username، Application Password، Token و Cookie فقط سمت سرور و ترجیحاً رمزگذاری‌شده نگهداری می‌شوند.
- Jobهای WordPress دارای `app_user_id`، `app_integration_id` و در صورت داشتن منبع پیام‌رسان، `messenger_account_id` منبع هستند.
- مشترک‌بودن Connection به معنی مشترک‌بودن Draft، انتخاب جاری، Upload موقت یا state رابط نیست؛ این موارد کاربرمحور می‌مانند.
- هر ایجاد/ویرایش/انتشار در WordPress با AppUser آغازکننده، زمان، منبع و نتیجه Audit می‌شود تا مسئول عملیات مشخص باشد.
- شناسهٔ Integration از رابط بدون کنترل Server-side معتبر نیست و فقط Integration فعال و مجاز در سطح نصب قابل استفاده است.

### تصمیم رابط دسکتاپ و موبایل

یک Codebase و یک API حفظ می‌شود، اما لایهٔ نمایش به دو Shell واکنش‌گرا تقسیم خواهد شد:

```text
Shared state, domain logic and API client
  ├── DesktopShell / Wide layouts
  └── MobileShell / Touch-first layouts
```

نسخهٔ موبایل نباید صرفاً Desktop کوچک‌شده باشد. تشخیص Layout بر اساس عرض/Container انجام می‌شود، نه User-Agent، و Build یا URL جدا لازم نیست. Componentهای دامنه، Validation و Data fetching مشترک می‌مانند تا دو نسخه از نظر رفتار و امنیت از هم دور نشوند؛ Navigation، ترتیب محتوا، Modalها و Interactionهای موبایل می‌توانند Componentهای اختصاصی داشته باشند.

الزامات MobileShell:

- طراحی Mobile-first برای عرض پایهٔ ۳۶۰ و ۳۹۰ پیکسل و کنترل عرض‌های نزدیک؛
- یک ستون اصلی، بدون Horizontal overflow و بدون وابستگی به Hover؛
- Navigation پایین صفحه یا Drawer مناسب Touch به‌جای فشرده‌کردن منوی دسکتاپ؛
- Modalهای مهم به‌صورت Full-screen dialog یا Bottom sheet؛
- Touch target حداقل حدود ۴۴ پیکسل، فاصلهٔ مناسب و پشتیبانی از Safe area؛
- سازگاری فرم‌ها با صفحه‌کلید موبایل، Focus، Scroll و Autofill؛
- فهرست‌ها و جدول‌های عریض به Card/List یا نمای جزئیات تبدیل شوند، نه جدول فشرده؛
- حفظ RTL، Dark theme، خوانایی، Contrast و اندازهٔ متن؛
- بازیابی صحیح پس از رفتن مرورگر به Background، قطع Wi-Fi و تغییر Orientation؛
- Polling و Media متناسب با موبایل و شبکهٔ Wi-Fi، بدون مصرف غیرضروری؛
- آزمون دیداری و تعاملی مستقل موبایل، علاوه بر Desktop.

## پذیرش آگاهانهٔ محدودیت HTTP

HTTP روی شبکهٔ داخلی از نظر فنی قابل استفاده است، اما محرمانگی و اصالت انتقال را تأمین نمی‌کند. در نتیجه، دستگاهی که بتواند ترافیک مسیر را ببیند یا تغییر دهد ممکن است نام کاربری، رمز ورود برنامه، Cookie نشست، OTP، رمز دوم یا محتوای عملیات را مشاهده یا دست‌کاری کند. هیچ CSRF Token، Hash پایگاه داده یا رمزگذاری سمت سرور این خطر مسیر شبکه را حذف نمی‌کند.

این ریسک بنا به تصمیم کاربر پذیرفته می‌شود، ولی باید در Config، راهنمای استقرار و Audit به‌صورت صریح ثبت شود. نرم‌افزار باید خطرهای قابل‌کنترل را کاهش دهد و نباید امنیتی معادل HTTPS ادعا کند.

حداقل قیود حالت `trusted_lan_http`:

- حالت پیش‌فرض برنامه همچنان Loopback باشد.
- فعال‌سازی LAN فقط با Config صریح و تأیید ریسک Cleartext انجام شود.
- AppUser authentication برای LAN اجباری باشد.
- Bind به IP شبکه، Hostهای مجاز، Originهای مجاز و CIDRهای خصوصی مجاز صریح باشند.
- LAN mode با Config ناقص Fail-closed شود.
- UI و API از یک Origin سرو شوند و CORS عمومی فعال نشود.
- Session فقط در Cookie با `HttpOnly` و `SameSite=Strict` نگهداری شود؛ `Secure` در HTTP قابل استفاده نیست.
- Token نشست یا Credential در URL، Query String، `localStorage` یا فایل رابط ذخیره نشود.
- Session پس از Login و تغییر سطح دسترسی Rotate و دارای Idle/Absolute timeout کوتاه باشد.
- CSRF، Host validation، Origin validation، محدودیت تلاش ورود، Lockout، محدودیت حجم Upload و Headerهای `no-store` حفظ یا تقویت شوند.
- به `X-Forwarded-For` اعتماد نشود مگر آنکه Proxy مورد اعتماد بعداً صریحاً پیکربندی شود.
- Bootstrap مدیر اولیه به‌طور پیش‌فرض فقط از خود سرور/Loopback انجام شود.
- ورود یا Re-auth پیام‌رسان از راه دور به‌طور پیش‌فرض خاموش باشد؛ اگر بعداً کاربر آن را لازم دانست، فقط با گزینه و تأیید خطر جداگانه فعال شود.
- فایروال فقط Subnetهای لازم را مجاز کند؛ هیچ Port Forwarding، UPnP یا انتشار اینترنتی انجام نشود.
- اعمال Rule فایروال یا تغییر سیستم‌عامل فقط با تأیید صریح کاربر انجام شود.

## وضعیت فازهای تکمیل‌شده

### فاز صفر — ممیزی معماری

تکمیل شد. تک‌سشن‌بودن Runtime، نقاط نشت Scope، Cacheها، Jobهای حافظه‌ای، Session مشترک و نیاز به مدل چهارلایه شناسایی شد.

### فاز ۱ — معماری چندکاربره، چندحسابی و چندProvider

تکمیل شد. مدل زیر تثبیت شد:

```text
AppUser -> PhoneAccount -> MessengerAccount -> Provider Runtime
```

قرارداد Provider، Context حساب، Capability، Scope داده، Feature Flag، Logging، Audit و Redaction طراحی شد. بله بدون حدس API در حالت `unknown/not configured` باقی ماند.

### فاز ۲ — Coordinator و مهاجرت Legacy

تکمیل شد. Coordinator نسخه‌دار، AppUser اولیه، PhoneAccount، MessengerAccount ایتا، Membership، Session metadata و Audit ایجاد شدند. مهاجرت Copy-and-Verify توسط کاربر اجرا و موفق گزارش شد. Backup زیر ایجاد شده است:

`eitaa-bridge-backup-20260731-063818-961222.zip`

Feature واقعی پس از مهاجرت خاموش باقی ماند و مسیر Legacy حذف نشد.

### فاز ۳ — احراز هویت AppUser

تکمیل شد. نقش‌های حداقلی `admin/user`، Credential Hash، نشست سمت سرور، CSRF، Idle/Absolute expiry، Logout، لغو نشست، Audit و UI ورود پیاده شد. محدودیت فعلی این است که هنگام فعال‌بودن AppUser auth، HTTP غیرLoopback عمداً رد می‌شود؛ این محدودیت باید فقط در حالت جدید و کنترل‌شدهٔ LAN بازطراحی شود.

### فاز ۴-A — مالکیت Session ایتا

تکمیل شد. مسیر، Metadata، مالکیت و Generation نشست حساب‌محور شد و سازگاری Legacy حفظ گردید.

### فاز ۴-B — Runtime و Storage حساب‌محور

تکمیل شد. Registry، Runtime، Scheduler، Core DB، Media، Cache، Diagnostics، Log و Lock حساب‌محور ساخته شد. مسیرهای حساب‌ها از هم جدا هستند.

### فاز ۴-C — چرخه Auth/Session حساب‌محور ایتا

تکمیل شد. Request code، Challenge، OTP، رمز دوم، Status، Reconciliation، Logout، Revocation و Generation حساب‌محور و Fail-closed شدند. آزمون‌ها Fake بودند و Codex اتصال واقعی ایجاد نکرد.

### فاز ۴-D — مدیریت MessengerAccount

تکمیل شد. Membership، Account Selector، کنترل Server-side مالکیت، Worker lifecycle منطقی، Recovery Lock، Media/Upload scope، Correlation، Rotation، Redaction، Support Bundle و UI حساب پیاده شد.

نکتهٔ مهم: Worker فعلی هنوز یک **Process مستقل واقعی برای هر حساب با IPC احراز‌شده** نیست؛ heartbeat آن Thread داخلی دارد. Process isolation کامل همچنان کار باقی‌مانده است.

### فاز ۵ — دفترچهٔ محلی مشترک و قابل ممیزی

تکمیل شد. Schema 2، Backup مهاجرت، Actor، Audit زنجیره‌ای، ادغام شمارهٔ تکراری، Binding مستقل هر MessengerAccount و endpoint عمومی افزودن به پیام‌رسان پیاده شد. نصب واقعی هنوز `contacts.sqlite3` با Schema 1، تعداد ۵۷۴ مخاطب و ۳ دسته دارد؛ مهاجرت در اولین Rollout کنترل‌شده و پس از Backup انجام می‌شود.

آخرین نتیجهٔ ثبت‌شده:

- آزمون متمرکز مخاطبان و فاز ۵: `20/20`
- کل مجموعه با کنارگذاشتن شکست تاریخی: `365/365`
- اجرای کامل: `365 passed, 1 failed`
- TypeScript و Vite build: موفق
- تنها شکست تاریخی: `tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`
- علت شکست: Fixture مسیر لاتین `Documents\Eitaa` می‌سازد ولی Assertion مسیر فارسی `Documents\ایتا` می‌خواهد؛ این مورد به فازهای چندکاربره مربوط نیست.

این آزمون‌ها در زمان تهیهٔ این گزارش دوباره اجرا نشدند؛ اعداد بالا آخرین نتایج ثبت‌شده در گزارش فاز ۵ هستند.

## وضعیت Git و دادهٔ واقعی

- هیچ Commit یا Push برای فازهای صفر تا پنج انجام نشده است.
- Worktree عمداً دارای تغییر است: ۲۶ فایل tracked تغییرکرده و ۲۸ entry جدید ثبت‌نشده مشاهده شد.
- تقریباً ۴۲۱۲ خط افزوده و ۳۱۵ خط از فایل‌های tracked حذف شده است.
- همهٔ این تغییرات و فایل‌های کاربر باید حفظ شوند.
- `bridge.json` واقعی Featureهای جدید را فعال نکرده است.
- AppUser auth و Multi-session مؤثر همچنان خاموش‌اند.
- Session، Coordinator، Contacts و Runtime واقعی نباید بدون Backup و تأیید کاربر بازنویسی شوند.
- هیچ Login/Logout/Send واقعی، API بله، Rule فایروال، Commit یا Push بدون تأیید صریح کاربر مجاز نیست.

## نقشهٔ اصلاح‌شدهٔ فازهای باقی‌مانده

هر زیرفاز باید در یک نوبت مستقل اجرا، آزموده، گزارش و سپس متوقف شود. اجرای یک‌جای تمام فاز توصیه نمی‌شود.

### فاز ۶ — زیرساخت چندکاربرهٔ HTTP روی LAN خصوصی

#### فاز ۶-A: قرارداد استقرار و Config امن HTTP/LAN

حجم: متوسط.

- تعریف صریح modeهای `desktop_loopback` و `trusted_lan_http`
- تعریف Bind host/port، Allowed Host، Allowed Origin، Allowed Client CIDR و Risk acknowledgement
- اجبار AppUser auth در LAN و Fail-closed برای Config ناقص
- نگه‌داشتن Bootstrap مدیر به‌صورت Loopback-only
- سیاست جدا برای Remote messenger authentication، پیش‌فرض خاموش
- جلوگیری از فعال‌شدن تصادفی با `0.0.0.0` یا Host/Origin باز
- نمونه Config، مستندات Threat model و آزمون Loader/Startup
- بدون بازکردن پورت، بدون روشن‌کردن Featureهای نصب واقعی و بدون Login واقعی

معیار پایان: حالت فعلی بدون تغییر کار کند و حالت LAN فقط با Config کاملاً صریح قابل انتخاب باشد.

#### فاز ۶-B: مقاوم‌سازی Auth و HTTP در حالت LAN

حجم: نسبتاً سنگین.

- بازطراحی Host/Origin validation برای فهرست مجاز LAN
- Session rotation، timeout، logout-all، lockout و rate limit ورود
- Cookie با `HttpOnly; SameSite=Strict` و پذیرش مستند نبود `Secure`
- CSRF اجباری برای تغییرات، پاسخ‌های `Cache-Control: no-store`
- عدم ذخیره Credential/Session در Local Storage، URL یا Log
- محدودیت Upload، Content-Type، اندازه Body و تعداد Request
- Headerهای CSP، frame protection، referrer و permissions مناسب HTTP
- آزمون جعل Host/Origin، CSRF، brute-force، Session fixation و دسترسی Cross-user

معیار پایان: دو Client شبیه‌سازی‌شده نتوانند نشست یا دادهٔ یکدیگر را بخوانند؛ ادعای حفاظت در برابر شنود شبکه مطرح نشود.

#### فاز ۶-C: سرویس‌دهی LAN و عملیات ویندوز

حجم: متوسط.

- سرو UI و API از یک Origin و یک Port
- Bind به IP ثابت/رزروشدهٔ LAN با رفتار Startup روشن
- Launcher و نمونه تنظیمات شبکه، Health/Readiness و Shutdown سالم
- طرح محدود Rule فایروال برای Subnet مشخص، بدون اعمال واقعی تا تأیید کاربر
- منع Port Forwarding/UPnP و راهنمای روتر/Wi-Fi خصوصی
- ثبت امن Client/Request بدون شماره، Token یا IP حساس غیرضروری
- Backup/Restore تنظیمات شبکه‌ای بدون کپی Secret به گزارش

معیار پایان: تست خودکار LAN mode و راهنمای دقیق نصب؛ هنوز پورت واقعی سیستم کاربر بدون اجازه باز نشود.

#### فاز ۶-D: پذیرش موبایل و هم‌زمانی HTTP

حجم: متوسط.

- ایجاد Skeleton و قواعد پایهٔ `MobileShell` و کنترل عرض‌های ۳۶۰ و ۳۹۰
- اثبات اینکه موبایل نسخهٔ صرفاً کوچک‌شدهٔ Desktop نیست: Navigation و فرم ورود Touch-first باشند
- ورود، خروج، انتخاب حساب، بازگشت از Background و قطع/وصل Wi-Fi
- چند نشست هم‌زمان برای دو AppUser و چند Tab
- جلوگیری از نشت state هنگام تعویض کاربر یا MessengerAccount
- نمایش هشدار غیرمزاحم «شبکهٔ خصوصی/HTTP» برای مدیر
- سناریوهای Restart سرور، Session expiry و Re-login
- گزارش پذیرش؛ تست دستی روی گوشی واقعی با همکاری کاربر، بدون ارسال واقعی

معیار پایان: UI موبایل و Auth شبکه‌ای پذیرفته شوند؛ Feature نصب واقعی هنوز خاموش بماند.

### فاز ۷ — Worker Process مستقل و IPC واقعی

این فاز برای جلوگیری از اثر Crash، Logout یا خرابی Core یک حساب بر حساب دیگر ضروری است.

#### فاز ۷-A: پروتکل و Worker entrypoint

حجم: متوسط.

- قرارداد IPC نسخه‌دار و محلی، Envelope، Correlation، deadline و error taxonomy
- احراز هویت IPC با Secret کوتاه‌عمر/فایل ACLدار
- Worker entrypoint مستقل و Fake Provider worker
- ممنوعیت انتقال Session object، Access Hash یا Raw Peer به Coordinator

#### فاز ۷-B: انتقال Runtime ایتا به Process اختصاصی

حجم: سنگین.

- یک Process برای هر MessengerAccount
- مالکیت Core، Scheduler، Session، DB، Cache، Media و Log فقط در Child
- DTO و opaque reference در مرز IPC
- سازگاری Legacy پشت Feature Flag

#### فاز ۷-C: Supervisor، Crash و Recovery

حجم: سنگین.

- Spawn/stop/heartbeat/fencing و duplicate-worker rejection
- Crash recovery، stale lease، quarantine و backoff
- خرابی A نباید B را متوقف یا Logout کند
- Shutdown و Restart کنترل‌شدهٔ سرور

#### فاز ۷-D: آزمون ایزولاسیون Process

حجم: متوسط.

- Kill واقعی Fake worker، Lock contention و IPC tampering
- عدم اشتراک Session/Scheduler/DB/Cache/Log
- اسکن خروجی‌ها برای Secret و گزارش فاز

### فاز ۸ — Scope کامل داده و Jobهای پایدار

#### فاز ۸-A: Repository، Query و Cache حساب‌محور

حجم: سنگین.

- ممیزی مجدد همه Repositoryها پس از تغییرات اخیر
- Dialog، Message، Sender، Content Index، Composition/WordPress source، Read receipt، Media و Cache
- مدل `AppIntegration` مشترک نصب برای WordPress؛ استفاده برای همهٔ کاربران فعال، مدیریت فقط توسط admin، Credential سمت سرور و مالکیت کاربرمحور Job/Audit
- Context فقط Server-side؛ رد شناسهٔ حساب جعلی از Body/Query
- کلیدهای Provider+MessengerAccount و آزمون Cross-account collision

#### فاز ۸-B: Job، Lease، Idempotency و Restart

حجم: سنگین.

- انتقال Jobهای حافظه‌ای لازم به Coordinator پایدار
- Owner، Account، Lease expiry، attempt و cancellation
- Idempotency key و جلوگیری از عملیات دوباره برای یک گیرنده/درخواست
- Recovery پس از Crash/Restart و وضعیت `uncertain`

#### فاز ۸-C: Rate limit و سیاست خطا

حجم: متوسط تا سنگین.

- Rate limit مستقل هر MessengerAccount
- احترام به `retry_after`، backoff محدود و circuit breaker
- عدم انتقال خودکار کار برای دورزدن محدودیت
- تفکیک transient/auth/privacy/permanent/uncertain/internal

#### فاز ۸-D: Audit عملیاتی و آزمون سراسری Fake

حجم: متوسط.

- Job/Lease/Attempt/Retry correlation کامل
- Query و Export امن Audit
- دو AppUser، حداقل سه Fake account و عملیات هم‌زمان پرتعداد
- Restart، Crash، cancellation و عدم نشت حساب

### فاز ۹ — رابط کامل مدیریت چندکاربره و موبایل

#### فاز ۹-A: مدیریت کاربران، PhoneAccount و Membership

حجم: متوسط تا سنگین.

- UI مدیر برای ساخت/تعلیق AppUser، نقش و لغو نشست
- اتصال امن PhoneAccount و Membershipهای owner/operator/viewer
- مدیریت WordPress integration مشترک نصب توسط admin و استفادهٔ آن توسط همهٔ AppUserهای فعال
- نمایش شماره فقط Masked و Audit تغییر دسترسی

#### فاز ۹-B: Workspace موبایل و عملیات حساب انتخاب‌شده

حجم: سنگین.

- تکمیل Account selector و پاک‌سازی کامل state هنگام تغییر حساب
- گفتگو، مخاطب، Quick Send، اعضا و پیشرفت Job فقط برای حساب انتخاب‌شده
- Polling سازگار با موبایل، reconnect و محدودیت مصرف
- تکمیل `MobileShell` با Navigation لمسی، Card/List، Full-screen dialog/Bottom sheet و فرم‌های سازگار با صفحه‌کلید
- حفظ `DesktopShell` بهینه برای Electron و صفحات بزرگ، با اشتراک منطق و API میان دو Shell

#### فاز ۹-C: مدیریت نشست‌های دستگاه‌ها

حجم: متوسط.

- فهرست امن نشست‌های خود کاربر بدون Token/IP کامل
- خروج از یک دستگاه یا همه دستگاه‌ها
- نمایش آخرین فعالیت و هشدار ورود/انقضا

#### فاز ۹-D: پذیرش دیداری، دسترس‌پذیری و هم‌زمانی

حجم: متوسط.

- عرض‌های ۳۶۰/۳۹۰/۱۲۸۰/۱۶۰۰
- RTL، Dark theme، Touch target حدود ۴۴ پیکسل، Safe area، صفحه‌کلید، Orientation و عدم overflow
- دو کاربر هم‌زمان روی دو موبایل و یک Desktop
- Visual regression و سناریوهای تعاملی جدا برای MobileShell و DesktopShell

### فاز ۱۰ — Rollout کنترل‌شده روی نصب واقعی

این فاز حتماً به تأیید و همراهی کاربر نیاز دارد.

#### فاز ۱۰-A: Preflight، Backup و Dry-run

حجم: متوسط.

- توقف کنترل‌شده برنامه
- Backup قابل بازیابی Coordinator/Contacts/Session/Data
- Verify Hash و تمرین Rollback روی کپی
- Preview مهاجرت Contacts Schema 1→2

#### فاز ۱۰-B: فعال‌سازی محلی اولیه

حجم: متوسط و دارای دروازهٔ تأیید.

- فعال‌سازی AppUser auth روی Loopback
- Bootstrap مدیر اولیه توسط خود کاربر
- مهاجرت Contacts و Verify تعداد ۵۷۴ مخاطب/۳ دسته
- فعال‌سازی Multi-session فقط پس از قبولی

#### فاز ۱۰-C: Pilot شبکهٔ داخلی HTTP

حجم: سنگین و نیازمند تست دستی.

- اعمال محدود Rule فایروال با اجازه کاربر
- کنترل هم‌شبکه‌بودن LAN سیمی و Wi-Fi، خاموش‌بودن Guest/AP isolation و ثابت‌بودن IP سرور
- دو AppUser و دو حساب واقعی ایتا با دادهٔ کم
- WordPress profile مشترک نصب: استفاده توسط دو کاربر، تغییر تنظیمات فقط توسط admin و بدون افشای Credential به موبایل
- بررسی Login/Expiry/Logout حساب A بدون اثر بر B
- بدون ارسال انبوه؛ هر ارسال واقعی فقط با تأیید جداگانه
- تست موبایل، قطع شبکه، Restart و Audit

#### فاز ۱۰-D: پذیرش، Rollback drill و تثبیت

حجم: متوسط.

- سنجش معیارهای پذیرش و رفع اشکالات Pilot
- تمرین Rollback و بازگشت Feature Flag
- راهنمای بهره‌برداری، Backup، بازیابی و Support bundle
- تصمیم جداگانه درباره کنارگذاشتن Legacy؛ حذف فوری مجاز نیست

### فاز ۱۱ — بله، مسیر مستقل و مبتنی بر API واقعی

زمان این فاز بعد از تثبیت هسته یا هر زمان است که کاربر مستندات/API واقعی بله را برای گفت‌وگوی مستقل مطرح کند.

1. **۱۱-A:** بررسی مستندات، نوع API، محدودیت‌ها، Auth، Session و Capabilityها؛ بدون حدس.
2. **۱۱-B:** Adapter و Contract test با Fake، بدون Login واقعی.
3. **۱۱-C:** چرخه Auth/Session واقعی بله با تأیید صریح کاربر.
4. **۱۱-D:** Capabilityهای تأییدشده، UI، جداسازی، Rate limit و Pilot محدود.

یک PhoneAccount مشترک می‌تواند MessengerAccount ایتا و بله داشته باشد، اما Session، Worker، IDها، Cache، Job و محدودیت هر Provider مستقل است.

### فاز ۱۲ — بهره‌برداری و Release نهایی

این فاز پس از Pilot ایتا و در صورت نیاز پس از بله اجرا می‌شود:

- نصب پایدار و Startup کنترل‌شده در ویندوز
- Health/Monitoring و Retention/Rotation نهایی
- آزمون Backup/Restore دوره‌ای و Support runbook
- اسکن Secret و Privacy نهایی
- بهینه‌سازی Bundle رابط و عملکرد موبایل
- نسخه‌گذاری، Release notes و در صورت درخواست کاربر Commit/Push

## ترتیب پیشنهادی و مدیریت مصرف Codex

ترتیب امن ادامه:

```text
6-A -> 6-B -> 6-C -> 6-D
-> 7-A -> 7-B -> 7-C -> 7-D
-> 8-A -> 8-B -> 8-C -> 8-D
-> 9-A -> 9-B -> 9-C -> 9-D
-> 10-A -> 10-B -> 10-C -> 10-D
-> 11 (گفت‌وگوی مستقل بله)
-> 12
```

هر زیرفاز باید گزارش مستقل `PHASE*.md` داشته باشد. در پایان هر نوبت باید آزمون‌های مرتبط، وضعیت Feature Flag، فایل‌های تغییرکرده، محدودیت‌ها و دستور دقیق نوبت بعد ثبت شود. فازهای سنگین ۷-B، ۷-C، ۸-A، ۸-B، ۹-B و ۱۰-C نباید با فاز دیگری در همان نوبت ترکیب شوند.

## دستور آغاز مناسب

اقدام بعدی فقط **فاز ۶-A** است. در این فاز نباید پورت شبکه واقعاً باز، Rule فایروال اعمال، Feature نصب واقعی فعال، دادهٔ واقعی مهاجرت، حساب واقعی Login/Logout یا پیام واقعی ارسال شود.

پس از تکمیل و آزمون فاز ۶-A، فایل `../phases/PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md` ایجاد و کار متوقف شود تا کاربر فاز ۶-B را جداگانه دستور دهد.

## به‌روزرسانی وضعیت اجرا — ۲۰۲۶-۰۸-۱۱

مراحل 6-A تا 8-D تکمیل و گزارش‌های مستقل آن‌ها ثبت شده‌اند. پذیرش یکپارچهٔ Phase 8 با ۴۶۹/۴۶۹ آزمون Python، TypeScript check، build تولیدی و ۲۶/۲۶ آزمون مدل UI موفق بسته شد. مرجع وضعیت جاری `../phases/PHASE8_FINAL_REPORT_2026-08-11.md` است؛ دستور قدیمی «اقدام بعدی فقط 6-A» در بخش تاریخی بالا دیگر وضعیت جاری محسوب نمی‌شود. مرحلهٔ بعد طبق Roadmap، 9-A است.

## به‌روزرسانی تصمیم استقرار — ۲۰۲۶-۰۸-۱۳

توپولوژی LAN توصیف‌شده در ابتدای این سند یک سناریوی استقرار است و نباید با
محیط توسعه یا شرط معماری محصول یکی گرفته شود. طبق تصمیم جدید کاربر:

- Public/DHCP/Firewall رایانهٔ توسعه blocker نیست؛
- تمام مقادیر شبکه در زمان استقرار و بیرون از کد تعیین می‌شوند؛
- محصول باید پروفایل Loopback، LAN اختیاری و استقرار وب 80/443 داشته باشد؛
- 443 فقط با TLS termination معتبر پذیرفته است؛ HTTP روی پورت 443 معادل HTTPS نیست؛
- WordPress فقط هنگام آزمون integration باید در دسترس باشد؛
- Pilot واقعی دوکاربر/دوحساب به محیط استقرار نهایی موکول می‌شود، درحالی‌که
  آزمون خودکار جداسازی همچنان الزامی است.

مرجع جاری ادامهٔ Phase 10 فایل
`../phases/PHASE10_DEPLOYMENT_PORTABILITY_DECISION_2026-08-13.md` است.

# تصمیم‌های canonical معماری Eitaa Bridge

وضعیت: لازم‌الاجرا برای توسعه‌های بعدی  
آخرین بازبینی: ۲۰۲۶-۰۸-۲۵، اصلاح عدم rollback قراردادهای متأخر؛ بازبینی کامل تناقض‌های Bale در G-01

این سند منبع نسخه‌پذیر تصمیم‌های کلان پروژه است. گزارش هر فاز باید با آن سازگار باشد و هر تغییر معماری ابتدا در همین سند ثبت شود. این سند به‌تنهایی هیچ Feature، اتصال شبکه، حساب یا Provider را فعال نمی‌کند.

## ۱. مدل کاربران، حساب‌ها و Providerها

- معماری پایه `multi-user + multi-account-per-provider + multi-provider` است.
- هر `AppUser` می‌تواند صفر، یک یا چند `MessengerAccount` از هر Provider داشته باشد.
- Providerهای هدف عبارت‌اند از Eitaa، Bale، Rubika و SoroushPlus؛ Providerهای آینده نیز از همان قرارداد عمومی استفاده می‌کنند.
- یک کاربر می‌تواند هم‌زمان چند حساب ایتا، چند حساب بله، چند حساب روبیکا و چند حساب سروش‌پلاس داشته باشد.
- رابطهٔ دسترسی کاربر به حساب از طریق Membership/Authorization سمت سرور کنترل می‌شود. شناسهٔ حساب ارسالی از رابط، به‌تنهایی مجوز ایجاد نمی‌کند.
- مدل منطقی اصلی چنین است:

```text
AppUser -> Membership/Authorization -> PhoneAccount -> MessengerAccount -> Provider Runtime
```

## ۲. استقلال کامل MessengerAccount

هر `MessengerAccount` مرز مستقل مالکیت و اجراست. موارد زیر نباید میان حساب‌ها ادغام یا به‌صورت ضمنی مشترک شوند:

- Session و چرخهٔ Authentication
- Worker/Process و Runtime
- Provider database و شناسه‌های Provider
- Cache، Media و Upload
- Job، Lease، Idempotency و Rate limit
- Log، Diagnostics و Audit scope

خرابی، Logout، محدودیت یا Re-auth یک حساب نباید حساب دیگر را مختل کند. Process isolation کامل برای هر MessengerAccount در فاز ۷ تکمیل می‌شود؛ Thread فعلی جایگزین آن تصمیم نیست.

## ۳. قرارداد Provider و Capability

- لایه‌های عمومی فقط با `ProviderId`، `MessengerAccount`، `ProviderRuntime` و `ProviderCapability` کار می‌کنند.
- هیچ API، Login flow، URL، Token، Session یا Capability برای Bale، Rubika یا SoroushPlus حدس زده نمی‌شود.
- قابلیت‌های هر Provider فقط پس از Discovery و آزمون قرارداد واقعی فعال می‌شوند.
- نبود یک Capability حالت معتبر سیستم است و UI باید آن عملیات را پنهان یا غیرفعال کند.
- Reply، Send، Upload و عملیات کانال همیشه به همان Provider و همان MessengerAccount مبدأ بازمی‌گردند.

## ۴. Unified Inbox یک Read/Query layer است

- Unified Inbox فقط aggregation/projection خواندنی روی حساب‌های مجاز همان AppUser است.
- Source of Truth هر پیام، گفتگو و Session در Provider و MessengerAccount خودش باقی می‌ماند.
- حداقل reference پایدار هر نتیجه شامل `provider_id`، `messenger_account_id`، `provider_conversation_id` و در صورت وجود `provider_message_id` است.
- Search و Pagination یکپارچه نیز فقط در Authorization scope همان AppUser اجرا می‌شوند.
- مخاطب محلی مشترک به معنی یکی‌بودن Identity یا Conversation آن شخص در Providerهای مختلف نیست.
- زیرساخت Unified Read Model در فاز ۸ و رابط Unified Inbox در فاز ۹ ساخته می‌شوند؛ فاز ۶-A آن‌ها را پیاده‌سازی نمی‌کند.

## ۵. WordPress یک AppIntegration مشترک نصب است

- WordPress یک `MessengerProvider` یا `MessengerAccount` نیست.
- Site/Profile و Credential آن `AppIntegration` مشترک در سطح Application Installation هستند.
- همهٔ AppUserهای فعال می‌توانند از Integrationهای فعال استفاده کنند، اما فقط `admin` می‌تواند تنظیمات اتصال و Credential را ایجاد یا تغییر دهد.
- Credential فقط سمت سرور نگهداری می‌شود.
- Draft، انتخاب جاری، Upload موقت، Job و Audit آغازکننده همچنان AppUser-scoped هستند و در صورت داشتن منبع پیام‌رسان، `messenger_account_id` منبع را نیز نگه می‌دارند.

## ۶. یک Codebase با دو Presentation shell

- Domain، API client، Validation و Data fetching مشترک می‌مانند.
- Presentation به `DesktopShell` برای صفحه‌های عریض/Electron و `MobileShell` لمسی و mobile-first تقسیم می‌شود.
- MobileShell نسخهٔ فشردهٔ Desktop نیست؛ Navigation، Card/List، Dialog و فرم می‌توانند مخصوص موبایل باشند.
- انتخاب Shell بر اساس عرض/Container انجام می‌شود، نه User-Agent، و Build یا URL جدا لازم نیست.
- فاز ۶-D Foundation مشترک، انتخاب Shell بر پایهٔ عرض، دسترسی لمسی و پذیرش Mobile/LAN را تکمیل می‌کند؛ MobileShell مستقل و کامل در فاز ۹ انجام می‌شود.

## ۷. قرارداد استقرار HTTP/LAN

- حالت نسخه‌دار پیش‌فرض `desktop_loopback` است و نبود بخش Deployment در Config دقیقاً به همین حالت امن برمی‌گردد.
- حالت `trusted_lan_http` فقط برای LAN خصوصی و فقط با Config کاملاً صریح و fail-closed مجاز است.
- Bind address/port، Allowed Host، Allowed Origin و Allowed private client CIDR باید محدود و صریح باشند؛ wildcard، شبکهٔ عمومی، `0.0.0.0` و CORS عمومی مجاز نیستند.
- UI و API باید از یک Origin سرو شوند.
- AppUser authentication در `trusted_lan_http` اجباری است.
- Bootstrap مدیر اولیه loopback-only باقی می‌ماند.
- Remote messenger authentication در LAN به‌طور پیش‌فرض خاموش است و تا فاز صریح بعدی قابل فعال‌سازی نیست.
- استفاده از HTTP به معنی نبود محرمانگی و اصالت انتقال است. پذیرش این خطر، HTTPS-equivalent ایجاد نمی‌کند.
- `trusted_lan_http` فقط برای شبکهٔ خصوصی مدیریت‌شده است؛ Guest Wi-Fi، AP/Client Isolation، Port Forwarding، DMZ و UPnP خارج از قرارداد امن هستند.
- هیچ Firewall rule یا Port واقعی در فاز ۶-A باز نمی‌شود. سرویس‌دهی و عملیات ویندوزی فاز ۶-C است.

## ۸. مرز فاز ۶-A

فاز ۶-A فقط قرارداد Config، اعتبارسنجی Startup/Request boundary، نمونه و مستندات را ایجاد می‌کند. این فاز Featureهای نصب واقعی را فعال نمی‌کند، دادهٔ واقعی را مهاجرت نمی‌دهد، اتصال واقعی Provider ایجاد نمی‌کند و API جدیدی برای Bale/Rubika/SoroushPlus نمی‌سازد.

## ۹. مدل عملیاتی Windows/LAN

- لانچر مستقل Windows/LAN فقط با `trusted_lan_http` معتبر اجرا می‌شود و Host/Port را منحصراً از Config نسخه‌دار می‌گیرد؛ هیچ Override یا Discovery شبکه‌ای مجاز نیست.
- `Health` فقط زنده‌بودن Application را با Payload حداقلی نشان می‌دهد. `Readiness` وضعیت پذیرش Request را جداگانه و با حالت Fail-closed گزارش می‌کند.
- هر Installation فقط یک نمونهٔ LAN فعال دارد. قفل سیستم‌عاملی در Crash آزاد می‌شود و Metadata باقی‌مانده به‌عنوان وضعیت stale قابل جایگزینی است.
- خروجی Firewall فقط Plan بدون اجراست و به IP محلی Config، Port دقیق، CIDRهای خصوصی Config، پروفایل `Private` و TCP inbound محدود می‌شود.
- نصب Service، اجرای Rule، بازکردن Port، تغییر Router و فعال‌سازی `bridge.json` واقعی فقط در Rollout صریح و با تأیید مدیر انجام می‌شود.

## ۱۰. قرارداد پذیرش Mobile/LAN و هم‌زمانی

- سرور HTTP از Worker thread مستقل برای هر Request استفاده می‌کند؛ یک Request طولانی نباید Health یا Request کلاینت دیگر را مسدود کند. محدودیت‌های Coordinator و Provider همچنان مرزهای تراکنشی و حساب‌محور خود را حفظ می‌کنند.
- نشست هر Browser با Cookie همان Origin و `SameSite=Strict` مستقل است. CSRF فقط در حافظهٔ همان صفحه نگهداری می‌شود و در `localStorage` یا `sessionStorage` نوشته نمی‌شود.
- کلاینت مرورگر فقط Request خواندنی `GET` را پس از خطای انتقال، یک‌بار و با تأخیر کوتاه تکرار می‌کند. Mutation، Upload و عملیات ارسال هرگز خودکار تکرار نمی‌شوند؛ Idempotency سمت سرور جایگزین این ممنوعیت نیست.
- قطع ارتباط با وضعیت سراسری و قابل مشاهده گزارش می‌شود و Readiness برای reconnect کنترل‌شده Probe می‌شود. این وضعیت نباید اطلاعات نشست، حساب، Provider، مسیر فایل یا Config خصوصی را نمایش دهد.
- انتخاب Presentation بر اساس عرض Viewport است، نه User-Agent. Foundation فاز ۶-D شامل Dynamic Viewport، Safe Area، هدف لمسی حداقل ۴۴ پیکسل، منوی قابل دسترس موبایل و Drawerهای عرض‌محور است.
- وضعیت محلی عملیاتی رابط، از جمله Draft، انتخاب گفتگو، تاریخچهٔ استفاده و موقعیت مطالعه، با Scope ترکیبی `AppUser + MessengerAccount` کلیدگذاری می‌شود. دادهٔ یک کاربر یا حساب نباید پس از تعویض کاربر/حساب در Scope دیگری خوانده شود.
- MobileShell کامل، Navigation/Information Architecture مستقل موبایل و Unified Inbox همچنان در فاز ۹ هستند. فاز ۶-D Provider جدید، API حدس‌زده‌شده، Remote messenger authentication یا Rollout شبکه‌ای ایجاد نمی‌کند.

## ۱۱. قرارداد IPC فرایند Worker

- مرز Worker یک پروتکل محلی و نسخه‌دار روی Pipeهای اختصاصی Parent/Child است؛ این مرز Socket شبکه، HTTP یا رابط عمومی نیست.
- هر Process فقط برای یک `MessengerAccount + Provider` احراز می‌شود. Envelope باید نسخه، نوع پیام، `correlation_id`، deadline، nonce، شناسهٔ حساب، Provider، method و payload محدود داشته باشد.
- احراز Envelope با HMAC-SHA256 و کلید تصادفی کوتاه‌عمر انجام می‌شود. کلید از Command line، Environment، Log یا Payload عبور نمی‌کند؛ Worker آن را از فایل یک‌بارمصرف با DACL کاربر جاری می‌خواند و فایل هنگام Bootstrap مصرف و حذف می‌شود.
- Replay nonce، نسخهٔ ناشناخته، deadline منقضی/بیش‌ازحد دور، Scope متفاوت، امضای نامعتبر و Payload خارج از قرارداد Fail-closed رد می‌شوند.
- Session object، Access Hash، Raw Peer/Message، Cookie، Token، Password و OTP اجازهٔ عبور از مرز Coordinator/Worker را ندارند. Coordinator فقط DTO امن و opaque reference را می‌بیند.
- Phase 7-A، Codec، Secret bootstrap، Error taxonomy، Worker entrypoint مستقل و Fake Provider را تثبیت کرد.
- Phase 7-B مالکیت Runtime هر حساب ایتا را پشت `features.worker_process` نسخهٔ ۱ و پیش‌فرض خاموش به یک Child اختصاصی منتقل می‌کند. با Flag روشن، Runtime قدیمی در Parent ساخته نمی‌شود و PID واقعی Child در Coordinator و Lease ثبت می‌شود.
- Core، Scheduler، Session/DB path contract، Cache، Media، Job state و Log حساب فقط در Child مالکیت می‌شوند. ساخت Core تا نخستین عملیات Provider در Child deferred است؛ Startup نباید Login، OTP، Sync یا Send واقعی اجرا کند.
- Parent فقط DTO امن، summary محدود و opaque reference را از IPC می‌بیند. Callback پایتون، raw provider object و دسترسی مستقیم به mutable account state از مرز عبور نمی‌کنند. مسیر عملیاتی بدون RPC اختصاصی Fail-closed است.
- خاموش‌بودن Flag مسیر Legacy را حفظ می‌کند. Schema نامعتبر، نبود Multi-session یا Kill switch قابلیت Process را Fail-closed خاموش می‌کنند.
- Phase 7-C برای هر Process runtime یک Supervisor اختصاصی دارد. Heartbeat هم در IPC و هم در Coordinator با `worker_instance_id + generation + process_id` Fence می‌شود؛ Generation قدیمی نمی‌تواند وضعیت Worker جدید را تغییر دهد.
- Crash، EOF یا عبور از سقف خطای Heartbeat، Worker را اتمیک `crashed` می‌کند، `exit_code` و Reason امن را ثبت می‌کند و Restart را با Backoff نمایی کران‌دار انجام می‌دهد. عبور از Restart budget حساب را Quarantine و Restart خودکار را متوقف می‌کند.
- Backoff و Duplicate rejection در تراکنش Coordinator اعمال می‌شوند. Shutdown کنترل‌شده Recovery ایجاد نمی‌کند و Restart سرور یک Generation تمیز می‌سازد. خرابی یک حساب نباید Auth، Session یا Process حساب دیگر را تغییر دهد.
- Phase 7-D با Kill واقعی Workerهای آزمایشی، Lock contention، duplicate-spawn race، جعل امضا/Scope، Replay، پاسخ unsolicited، Fence قدیمی و اسکن Secret، Process isolation را پذیرش کرد.
- Parent برای stdout/stderr Child اندازه و صف کران‌دار دارد. پاسخ نامعتبر یا correlation mismatch کانال را Fail-closed می‌بندد و Process را Terminate می‌کند؛ ادامه‌دادن روی stream desynchronized مجاز نیست.
- هیچ Session/Scheduler/DB/Cache/Log میان حساب‌ها مشترک نیست. Feature Flag نصب واقعی پس از پایان Phase 7 همچنان پیش‌فرض خاموش و Rollback Legacy محفوظ است.

## ۱۲. قرارداد دامنهٔ داده و AppIntegration

- کلید canonical هر دادهٔ مشتق از پیام‌رسان `Provider + MessengerAccount` است؛ شناسه‌های Peer، Message، Sender، Job یا Site به‌تنهایی کلید سراسری نیستند.
- `legacy` فقط یک دامنهٔ صریح سازگاری تک‌نشستی است. Runtime چندنشستی موظف است UUID canonical حساب را به همهٔ Repositoryها، Cacheها و صف‌های درون‌فرایند منتقل کند.
- Dialog، Sender، Content Index، Read receipt، Media token و Cache با دامنهٔ حساب کلیدگذاری می‌شوند. تطبیق دامنه در فایل/پایگاه داده Fail-closed است و برخورد عمدی شناسه‌ها نباید موجب overwrite یا read-through شود.
- Composition با دامنهٔ ترکیبی `Provider + MessengerAccount + AppUser` نگهداری می‌شود؛ منبع پیام‌رسانی، حساب مبدأ خود را از Context معتبر سمت سرور می‌گیرد.
- `messenger_account_id` و `account_id` ورودی Body/Query مسیرهای v1 نیستند. Context حساب فقط پس از احراز هویت، Membership و انتخاب سمت سرور تعیین می‌شود. Media URL فقط Token مبهم دارد و حساب از همان Token بازیابی می‌شود.
- WordPress یک AppIntegration مشترک نصب است. Metadata غیرمحرمانه در Coordinator ثبت می‌شود، Credential در Config/Environment سمت سرور باقی می‌ماند، همهٔ AppUserهای فعال حق استفاده دارند و مدیریت فقط برای `admin` مجاز است.

## ۱۳. قرارداد Job پایدار Coordinator

- هر عملیات پس‌زمینهٔ چندنشستی دارای رکورد پایدار Coordinator با Owner AppUser، PhoneAccount، MessengerAccount، Provider، Operation، Correlation و Idempotency است.
- Idempotency با کلید یکتای `MessengerAccount + Operation + IdempotencyKey` اعمال می‌شود. استفادهٔ مجدد توسط Owner دیگر یا Payload/Recipient set متفاوت Fail-closed رد می‌شود.
- Recipient فقط با SHA-256 opaque reference ثبت می‌شود؛ شماره، Peer خام، Access Hash و Payload محرمانه وارد Coordinator Job نمی‌شوند. برخورد گیرندهٔ تکراری در یک Request با PK پایگاه داده حذف می‌شود.
- Lease با `worker_id + generation + expiry` Fence می‌شود. Attempt فقط با Lease جاری آغاز/تکمیل می‌شود و Heartbeat اجاره برای عملیات طولانی الزامی است.
- Lease منقضی پیش از Start به `pending` بازمی‌گردد؛ Crash پس از Start به‌دلیل نامعلوم‌بودن اثر بیرونی به `uncertain` می‌رود و خودکار تکرار نمی‌شود.
- Cancellation پیش از Start فوری و پس از Start cooperative است. Worker قدیمی پس از Recovery یا Lease جدید حق ثبت نتیجه ندارد.
- مسیرهای background عمومی، Dialog sync، Content Index و Contact import در حالت چندنشستی از Job پایدار استفاده می‌کنند. مسیر Legacy با Feature خاموش سازگار می‌ماند.

## ۱۴. سیاست اجرای مستقل هر حساب

- Token bucket، `retry_not_before`، شمارندهٔ Failure و Circuit state با کلید `MessengerAccount + OperationScope` در Coordinator نگهداری می‌شود؛ State حساب یا Operation دیگر هرگز به‌عنوان fallback مصرف نمی‌شود.
- `retry_after` اعلام‌شدهٔ Provider حداقل زمان انتظار است. Backoff نمایی داخلی کران‌دار است، اما زمان بیشتر Provider کوتاه نمی‌شود.
- Circuit پس از Failureهای متوالی باز می‌شود و بعد از مهلت فقط یک Probe با Claim fenced در حالت `half_open` می‌پذیرد. موفقیت Probe Circuit را می‌بندد و Failure آن را دوباره باز می‌کند.
- taxonomy خطا دقیقاً شامل `transient`، `auth`، `privacy`، `permanent`، `uncertain` و `internal` است. فقط transient/internal قابلیت retry خودکار دارند.
- auth/privacy و uncertain نیازمند Reset/Reconciliation صریح هستند و Circuit بدون مهلت خودکار باز می‌ماند. `uncertain` هرگز به‌صورت خودکار تکرار نمی‌شود.
- طبقه‌بندی فقط از Error code امن، HTTP status و Flag صریح «اثر ممکن است رخ داده باشد» استفاده می‌کند؛ متن خام Provider در Coordinator ذخیره نمی‌شود.

## ۱۵. Correlation و Audit عملیاتی

- هر Job یک Root correlation دارد. هر Lease و Attempt نیز UUID correlation مستقل دارد و از طریق `job_id + lease_id` به Root متصل است؛ Retry همان Root را حفظ و Lease/Attempt تازه می‌سازد.
- `job_leases` Journal پایدار و append-by-row است. Active Lease برای هر Job یکتا، Renewal fenced و Release/Expiry صریح است.
- Audit query برای admin سراسری و برای user فقط رخدادهای خودش یا Jobهای متعلق به خودش است. فیلتر حساب user علاوه بر این نیازمند Membership فعال است.
- Cursor، Account، Correlation، Action، Result و Time range همگی اعتبارسنجی می‌شوند. خروجی PhoneAccount ID و دادهٔ محرمانه ندارد و Metadata هنگام خروج دوباره Redact می‌شود.
- Export فقط در پوشهٔ Server-owned، با نام تولیدشدهٔ سرور، نوشتن اتمیک، `fsync` و SHA-256 انجام می‌شود. مسیر دلخواه Client پذیرفته نمی‌شود.
- زنجیرهٔ Audit با بازسازی canonical event، `previous_event_hash` و `event_hash` کامل بررسی می‌شود. هر تغییر پس از حذف عمدی Trigger در تست به‌عنوان tamper شناسایی می‌شود.

## ۱۶. حافظهٔ مهندسی و منع یافتهٔ Chat-only

- پوشهٔ `docs/project-memory` مرجع اول وضعیت فعلی، یافته‌ها، اعتبارسنجی‌ها و نقشه‌راه است. پیش از بررسی دوبارهٔ کد یا اجرای Live/Test باید سند موضوعی و Validation ledger خوانده شوند.
- هیچ یافته، تصمیم، محدودیت، بدهی فنی، نتیجهٔ آزمون یا تغییر وضعیت مادی نباید فقط در Chat باقی بماند.
- بررسی یا آزمون معتبر فقط پس از تغییر فایل/Config اثرگذار، رخداد متعارض، انقضای اعتبار، نیاز پذیرش واقعی یا درخواست صریح تکرار می‌شود.
- هر تغییر مادی باید در همان نوبت Baseline، Finding، Validation و سند موضوعی را به‌روز کند. تصمیم کلان علاوه بر آن در همین سند ثبت می‌شود.
- گزارش‌ها باید سطح شاهد را از میان Decision، Static، Unit، Contract/Fake، Adversarial، Isolated Runtime و Live مشخص کنند.
- این سیاست جای آزمون را نمی‌گیرد؛ آزمون را به تغییر و ریسک مربوط متصل و از تکرار بی‌دلیل جلوگیری می‌کند.

## ۱۷. قرارداد لاگ‌گذاری و Observability

- همهٔ رخدادهای مادی، Errorها، Warningها و transitionهای امنیتی/عملیاتی باید Event ساختاریافته، Level، Result، Reason code، Correlation و Scope امن داشته باشند.
- «همهٔ رخدادهای مادی» شامل lifecycle، crash، auth/session/account/worker transition، عملیات بیرونی، retry/cancel/uncertain، rate/circuit، رد امنیتی، backup/restore و تغییر Config است؛ ثبت هر کلیک یا Payload خصوصی هدف نیست.
- متن پیام، Body/Payload خام، Query خام، Header، Credential، Cookie، Token، OTP، رمز، Session، Access Hash و شمارهٔ کامل در Log/Audit/Diagnostic ممنوع است.
- رخداد دارای اثر بیرونی یا تغییر مالکیت/امنیت علاوه بر Runtime log باید Audit پایدار داشته باشد.
- Application، Worker، Electron، Renderer و Provider adapter باید از Event schema و redaction مشترک استفاده کنند و Correlation را در مرزهای مجاز منتقل کنند.
- Error Boundary رابط، unhandled rejection، Electron structured logging، sanitization مسیر و Event Catalog مرکزی بدهی‌های باز ثبت‌شده‌اند و پیش از ادعای Production-ready چندProvider باید تکمیل شوند.
- Support Bundle فقط دادهٔ امن، محدود، نسخه‌دار و قابل اسکن را می‌پذیرد و inclusion هر منبع تازه نیازمند adversarial secret/PII test است.

## ۱۸. اولویت Eitaa/Bale و Onboarding چندحسابی

- اولویت Providerها Eitaa سپس Bale است. Provider سوم فقط پس از تثبیت قرارداد عمومی افزوده می‌شود.
- UI انتخاب حساب موجود را دارد، اما افزودن حساب جدید هنوز Feature کامل نیست. Multi-account Onboarding provider-neutral پیش‌نیاز ورود واقعی Bale است.
- Onboarding باید ساخت امن PhoneAccount/MessengerAccount، Membership، Auth state machine، Wizard خصوصی، Resume/Cancel/Recovery و جابه‌جایی حساب را بدون دریافت مسیر فایل یا Account identity قابل جعل از Client فراهم کند.
- Provider باید از Registry/Descriptor و Capability خوانده شود؛ Unionهای ثابت UI، `CHECK`های ثابت Eitaa/Bale و شرط‌های مستقیم `provider == eitaa` باید با Migration و قرارداد نسخه‌دار عمومی شوند.
- افزودن Provider آینده باید فقط به Manifest، Adapter، Auth flow، Capability، Error/rate mapping و Contract tests نیاز داشته باشد و نباید مالکیت AppUser، Account isolation، Coordinator job، UI shell یا Security boundary را بازنویسی کند.
- Discovery واقعی هر Provider پیش از Adapter الزامی است؛ Endpoint، Token، Session، Login flow یا Capability حدس زده نمی‌شود.

## ۱۹. قرارداد اجرایی Self-service Onboarding

- AppUser فعال می‌تواند حداکثر ۲۰ MessengerAccount غیرآرشیوی را به‌صورت self-service مالک شود. این سقف داخل همان تراکنش Coordinator بررسی می‌شود و تغییر آن نیازمند تصمیم و آزمون تازه است.
- Client فقط `provider`، هویت خصوصی canonical و label اختیاری را می‌فرستد. UUID، PhoneAccount، Membership، Session/Runtime/Storage path و revisionها منحصراً سمت سرور تولید می‌شوند.
- هویت خصوصی پیش از ورود به Coordinator با DPAPI و fingerprint نصب محافظت می‌شود؛ متن کامل هویت در DB، Log، Audit، گزارش یا storage مرورگر ثبت نمی‌شود.
- یکتایی `PhoneAccount identity + Provider` با تراکنش `BEGIN IMMEDIATE` و قید پایگاه داده اعمال می‌شود. retry/race همان مالک همان MessengerAccount را برمی‌گرداند؛ مالک دیگر پاسخ عمومی `identity_unavailable` می‌گیرد و وجود رکورد افشا نمی‌شود.
- عضویت `owner` نخستین AppUser همراه PhoneAccount در همان تراکنش ساخته می‌شود. حتی مدیر سراسری نمی‌تواند از مسیر self-service هویت متعلق به مالک دیگر را تصاحب کند.
- Provider و مراحل Auth فقط از descriptor سمت سرور خوانده می‌شوند. Eitaa در 11-0 onboardable است؛ Bale تا پایان Discovery/Adapter صریحاً غیرفعال و بدون جزئیات حدسی باقی می‌ماند.
- lifecycle حساب تازه `created/stopped` و auth state آن `absent` (نمای معماری `identity_required`) است. Start صریح Worker، Auth flow حساب‌محور موجود را فعال می‌کند؛ ساخت حساب به‌تنهایی اتصال شبکه یا ارسال ایجاد نمی‌کند.
- رخدادهای started/succeeded/reused/rejected در Runtime Event Catalog و تغییر مالکیت در Audit زنجیره‌دار ثبت می‌شوند؛ هیچ payload خصوصی وارد این رخدادها نمی‌شود.

## ۲۰. مرز رسمی/غیررسمی Provider و تفکیک Bale Bot از Bale Personal

- مجوز متن‌باز یک client به معنی مجوز استفاده از سرویس Provider نیست. Adapter عملیاتی فقط بر مبنای API رسمی، قرارداد سازمانی یا اجازهٔ کتبی قابل توسعه است.
- شرایط رسمی بله در بازبینی ۲۰۲۶-۰۸-۱۳ API غیررسمی و مهندسی معکوس را ممنوع کرده است؛ بنابراین کدهای personal client غیررسمی فقط ورودی Discovery هستند و Vendor/اجرا نمی‌شوند.
- `Bale Bot/Arm` و `Bale Personal` دو account kind با identity، auth، capability و محدودیت متفاوت‌اند و نباید پشت یک descriptor مبهم یا Wizard مشترکِ تلفنی پنهان شوند.
- مسیر رسمی Bot با Token محرمانه، scope محدود و API مستند قابل طراحی است؛ اما دسترسی به گفتگو/مخاطب/تاریخچهٔ شخصی را ادعا نمی‌کند.
- مسیر Personal تا انتشار API رسمی یا دریافت اجازهٔ کتبی `BLOCKED` است. در این وضعیت `configured/runtime/onboarding` آن false باقی می‌ماند و Phase 11-B شخصی آغاز نمی‌شود.

## ۲۱. قرارداد نسخه‌دار و دروازهٔ فعال‌سازی Provider

- قرارداد عمومی Provider در `src/eitaa_bridge/providers/contracts.py` و با `extension_api_version=1` تعریف می‌شود. Adapter، Worker، Manifest، Capability و DTOهای عمومی از این مرز عبور می‌کنند؛ raw RPC، raw response، Cookie، Token، Session object و مسیر فایل client-selected از مرز عمومی عبور نمی‌کنند.
- چرخهٔ implementation برابر `scaffold -> implemented -> contract_verified -> live_accepted` است. Manifest اجازه نمی‌دهد scaffold یا Provider بدون مبنای authorization configured شود، یا implementation آزمایش‌نشده runtime/onboarding را فعال کند.
- مبنای authorization یکی از API رسمی، اجازهٔ کتبی، integration پذیرفته‌شدهٔ موجود یا Fake صرفاً تستی است. API رسمی/اجازهٔ کتبی باید reference قابل ممیزی داشته باشد.
- Registry یک allowlist صریح در composition root است. نام Provider دریافتی client باعث import پویا، filesystem discovery، `eval/exec` یا انتخاب module نمی‌شود.
- هر Provider/account kind registration مستقل دارد. Bot و Personal حتی با نام تجاری یکسان نباید Manifest، auth flow یا Capability مبهم مشترک داشته باشند.
- Session و Worker با `provider + messenger_account_id + session_generation` scope می‌شوند. Fake store حافظه‌ای production نیست؛ storage واقعی باید sealed، حساب‌محور و قابل archive باشد.
- فعال‌سازی از رخدادهای canonical started/succeeded/rejected/failed استفاده می‌کند. Provider exception خام، secret، هویت کامل و payload شبکه در log/audit ثبت نمی‌شود.
- slot بله در Phase 11-B0 فقط scaffold غیرفعال است. آماده‌بودن این زیرساخت مجوز یا پذیرش اتصال عملیاتی Bale Personal محسوب نمی‌شود.

## ۲۲. Registry پایدار، Capability حساب‌محور و مهاجرت بدون بازنویسی Provider

- composition root تنها محل registration صریح Provider است. startup، metadata امن registrationهای محصول را در Coordinator و Contact Store به‌صورت افزایشی reconcile می‌کند و هیچ Provider تاریخی را صرفاً به‌علت غیبت از build حذف نمی‌کند.
- در 11-B1، Coordinator v6 و Contact v3 نام Provider را با FK به Registry بستند. schema جاری Coordinator پس از 11-B2 نسخهٔ 7 است و فقط receipt عمومی mutation را افزوده؛ CHECK ثابت Eitaa/Bale همچنان فقط در migrationهای تاریخی باقی می‌ماند و قرارداد schema جاری نیست.
- Manifest سقف Capability است. observation حساب فقط می‌تواند Capability اعلام‌شده را محدود، ناشناخته یا unsupported کند و حق فعال‌کردن Capability اعلام‌نشده را ندارد.
- mismatch میان Manifest درون build و registration پایدار fail-closed است تا startup/reconciliation ناقص باعث افزایش اختیار نشود.
- routeهای provider-backed پیش از انتخاب runtime به Capability عمومی نگاشت می‌شوند. Membership همچنان پیش از Capability کنترل می‌شود تا endpoint قابلیت به کانال کشف حساب تبدیل نشود.
- Fake Provider سوم `test_only`، آفلاین و خارج از catalog محصول است. persistence آن فقط با opt-in تست مجاز است؛ هیچ endpoint، credential یا دادهٔ واقعی ندارد.
- migration واقعی DB عملیاتی فقط در startup کنترل‌شده انجام می‌شود. اجرای test روی DBهای موقت مجوز restart سرویس واقعی یا تغییر Session/Config نیست.
- مرحلهٔ بعدی، انتقال orchestration handlerهای Eitaa-specific به serviceهای provider-neutral است؛ این تصمیم اجازهٔ حدس transport یا فعال‌سازی Bale را ایجاد نمی‌کند.

## ۲۳. Orchestration عمومی Provider و vertical slice اتمیک

- هر عملیات عمومی Provider در application با ترتیب ثابت `AppUser -> Membership/account scope -> capability -> deadline -> adapter resolution -> bounded operation -> safe result/log` اجرا می‌شود. adapter پیش از authorization/capability ساخته یا فراخوانی نمی‌شود.
- orchestrator نام Provider را مقایسه نمی‌کند. composition root از registration صریح به factory اختصاصی Provider می‌رسد و translation/transport فقط در package همان Provider می‌ماند.
- Manifest حتی پس از تصمیم capability service سقف نهایی است. observation، payload یا factory نمی‌تواند عملیات خارج از Manifest را فعال کند.
- replay کلید idempotency همواره پس از کنترل مجدد دسترسی، scope، capability و deadline انجام می‌شود. receipt درحال‌اجرا duplicate را رد می‌کند و receipt با وضعیت `uncertain` terminal است و retry خودکار ندارد.
- UI snapshot قابلیت را به MessengerAccount انتخابی bind می‌کند. loading، error، stale account، restricted، unsupported و unknown همگی fail-closed هستند؛ نام Provider معیار enablement نیست.
- مهاجرت بزرگ به vertical sliceهای کامل تقسیم می‌شود. slice 1 در 11-B2 فقط routeهای v2 Dialog/History/Text Send را با Eitaa compatibility و Fake مشترک فعال می‌کند؛ legacy غنی‌تر نیمه‌مهاجرت‌یافته جایگزین نمی‌شود.
- Media/Contacts در slice 1 قرارداد typed/bounded و guard دارند، اما فعال‌سازی transport یا capability زائد حدس زده نمی‌شود. Process Runtime فقط پس از RPC حساب‌محور، bounded و fenced عبور می‌کند؛ دسترسی مستقیم Parent به mutable child state ممنوع می‌ماند.

## ۲۴. تکمیل Process RPC و receipt پایدار mutation در 11-B2

- شش operation عمومی Dialog/History/Text Send/Media read/Contact list/upsert قرارداد کامل application هستند. مسیرهای legacy غنی‌تر می‌توانند باقی بمانند، اما Provider تازه نباید برای همین قابلیت‌ها handler عمومی موازی و نام‌محور بسازد.
- Process Worker فقط methodهای صریح `eitaa.provider.*` را با allowlist فیلد و fence حساب/generation می‌پذیرد. Parent نتیجه را دوباره به DTO عمومی نگاشت و scope/reference/limit را کنترل می‌کند؛ raw SDK object، session state، access hash و مسیر فایل مرز IPC را رد نمی‌کنند.
- media cache در مالکیت Child است. Parent فقط token account-bound و chunkهای Base64 محدود با offset پیوسته، MIME ثابت، byte count و EOF معتبر را broker می‌کند؛ caller حق انتخاب مسیر ندارد.
- mutationهای `messages.send_text` و `contacts.upsert` پیش از فراخوانی Provider در Coordinator schema v7 claim می‌شوند. کلید receipt به MessengerAccount، operation، AppUser و fingerprint درخواست bind است و request payload خام ذخیره نمی‌شود.
- replay terminal بعد از restart فقط پس از authorization/capability/deadline پاسخ می‌دهد و Provider را دوباره فراخوانی نمی‌کند. claim منقضی‌شده یا اثر بیرونیِ بدون receipt قطعی، محافظه‌کارانه terminal `uncertain` است و retry خودکار ندارد.
- Send و Contact Upsert در API عمومی علاوه بر idempotency key به `confirm=true` دقیق نیاز دارند. این تأیید مجوز Live کلی ایجاد نمی‌کند؛ اجرای واقعی همچنان تابع تأیید همان لحظه و وضعیت Provider/account است.
- رخدادهای replay/interruption هیچ idempotency key، fingerprint، متن، identity یا مسیر فایل ندارند. ارتقای v6→v7 فقط در startup کنترل‌شدهٔ DB هدف انجام می‌شود؛ موفقیت migration روی DB موقت مجوز تغییر DB عملیاتی یا restart نیست.

## ۲۵. Material UI تنها مرجع طراحی و mobile-first بودن رابط

- همهٔ سطح‌های فعال React باید از componentهای Material UI و سامانهٔ `theme/sx` استفاده کنند. افزودن class طراحی اختصاصی، primitive بصری موازی یا import stylesheet اختصاصی برای feature تازه مجاز نیست.
- RTL، رنگ، contrast، touch target و حالت‌های component در Theme مرکزی تعریف می‌شوند. CSS قدیمی می‌تواند برای تاریخچه باقی بماند، اما تا وقتی import نشده بخشی از runtime نیست.
- منطق محصول میان موبایل و دسکتاپ مشترک است، اما `MobileShell` و `DesktopShell` render targetهای صریح دارند. موبایل مبنای اولیه است: safe-area، ارتفاع `dvh/svh`، bottom navigation، Dialog تمام‌صفحه، فرم تک‌ستونه و حداقل touch target 44px باید حفظ شوند.
- صفحه‌ها و نوارهای اصلی در moduleهای مستقل مانند Navigation، Conversation List، Chat Header، Settings، Contacts، Auth و Toast نگه‌داری می‌شوند. `App.tsx` می‌تواند orchestration state را مالک باشد، اما نباید دوباره مالک همهٔ presentationها شود.

## ۲۶. ثبت‌نام خودخدمت خصوصی، رمز کوتاه و نشست یک‌ساله

- Self-registration فقط وقتی مجاز است که AppUser Auth و flag آن روشن باشند و deployment یکی از `desktop_loopback` یا `trusted_lan_http` باشد. در `web_reverse_proxy` عمومی fail-closed است.
- کاربر ثبت‌نامی همیشه نقش `user` می‌گیرد، وجود مدیر فعال لازم است و client حق تعیین role، account ownership یا مسیر storage ندارد. رخداد ثبت‌نام با metadata امن audit می‌شود.
- حداقل طول رمز AppUser چهار نویسه است و رمز چهاررقمی پذیرفته می‌شود. حداکثر طول/بایت و ممنوعیت control character حفظ می‌شوند؛ PBKDF2-HMAC-SHA-256 با 600000 iteration، salt مستقل، dummy hash، throttle پایدار و lockout حذف نمی‌شوند.
- سیاست جاری idle و absolute هر دو یک سال است و Cookie مرورگر `Max-Age=31536000` دارد. نشست همچنان با logout، revoke، غیرفعال‌شدن کاربر یا تغییر رمز قابل لغو است؛ طولانی‌بودن نشست به معنی دائمی یا غیرقابل‌ابطال بودن آن نیست.

## ۲۷. دریافت خودکار گفتگو و پیام بدون reload دستی

- گفتگوی باز با polling تطبیقی و کوتاه پیام‌های تازه را merge می‌کند؛ فهرست گفتگو نیز نخستین صفحهٔ محدود Provider را در پس‌زمینه تازه و unread/top-message را upsert می‌کند. کاربر برای دیدن پیام تازه نباید reload یا دکمهٔ بارگذاری بزند.
- این قرارداد در وضعیت فعلی near-real-time polling است، نه ادعای WebSocket/Push Provider. فاصلهٔ polling برای موبایل، صفحهٔ پنهان، save-data، offline و خطا کندتر و retry آن bounded است.
- live-sync فهرست فقط snapshot تازه را merge می‌کند و گفتگوی قدیمی خارج از صفحهٔ نخست را hidden نمی‌کند. همهٔ درخواست‌ها به MessengerAccount فعال bind هستند و پاسخ دیررس حساب قبلی پذیرفته نمی‌شود.
- retry خودکار این مسیر فقط برای read است؛ mutation، ارسال و دعوت از این loop عبور نمی‌کنند و همچنان به تأیید و idempotency مستقل وابسته‌اند.

## ۲۸. بازیابی خودکار نشست نامعتبر با حفظ مرز احراز هویت

- UI جزئیات فایل Session، نام backup و عملیات بایگانی را به کاربر عادی نمایش نمی‌دهد. پس از تشخیص نشست نامعتبر، بازیابی محلی و درخواست چالش ورود به‌صورت خودکار آغاز می‌شوند و صفحه فقط وضعیت آماده‌سازی یا ورودی لازم را نشان می‌دهد.
- حالت بدون تأیید `automatic_recovery=true` در Backend حساب‌محور فقط وقتی مجاز است که state پایدار حساب `invalid` باشد. حالت سالم، authenticated، challenge یا هر state دیگر رد می‌شود و فایل فعال دست‌نخورده می‌ماند؛ حالت absent بدون فایل فقط به‌شکل idempotent موفق است.
- فایل نامعتبر حذف نمی‌شود و همچنان با نام یکتای `.invalid.<timestamp>.bak` کنار Session نگه‌داری می‌شود، اما پاسخ automatic نام archive را افشا نمی‌کند. Audit فقط reason امن `automatic_invalid_session_recovery` و metadata غیرخصوصی دارد.
- UI پس از بازیابی، `request-code` را با هویت محافظت‌شدهٔ همان MessengerAccount اجرا می‌کند. این تصمیم OTP یا رمز دوم Provider را دور نمی‌زند؛ اگر Provider آن‌ها را لازم بداند، کاربر فقط همان ورودی ضروری را می‌بیند.
- خطای بازشدن Session یا مسیر مهاجرتی می‌تواند با انتخاب محصولی فعلی در UI به reset تأییدشدهٔ محلی هدایت شود، اما Backend همچنان برای مسیر عمومی `confirm=true` می‌خواهد. این مجوز به logout راه‌دور، تغییر Credential، Provider mutation یا بازیابی DPAPI تعمیم ندارد.
- هر تغییر در state machine احراز هویت، reset route، archive naming، challenge binding یا audit reason نیازمند تکرار آزمون‌های lifecycle، privacy و UI contract است.

## ۲۹. منبع واحد Desktop runtime، فونت و استقلال نشست‌ها

- اجرای Electron در محیط source باید Python module همین workspace را ترجیح دهد؛ executable تولیدشده ممکن است از source عقب بماند. نسخهٔ بسته‌بندی‌شده می‌تواند executable انتشار را ترجیح دهد، اما Health و version هر دو باید قبل از reuse پذیرفته شوند.
- `VERSION.txt` منبع canonical تطبیق Electron/Backend است. fallback فقط برای حالت بسته‌بندی‌شده یا نبود فایل و با قالب محدود نسخه مجاز است؛ constant جداگانهٔ قابل drift مجاز نیست.
- Typography فعال Material از Theme و `MuiCssBaseline` می‌آید. IRANSans Regular/Bold فایل‌های bundled هستند و URL نسبی باید هم در `file://` Electron و هم HTTP کار کند؛ stylesheet تاریخی منبع runtime نیست.
- نشست AppUser و نشست Messenger Provider دو lifecycle مستقل‌اند. invalid شدن Provider فقط context حساب پیام‌رسان را تغییر می‌دهد و نباید CSRF، cookie یا MessengerAccount selection کاربر نرم‌افزار را پاک کند. پاک‌سازی AppUser فقط در logout یا invalid شدن صریح endpoint AppAuth انجام می‌شود.
- OTP پیش از اعتبارسنجی با NFKC و نگاشت رقم فارسی/عربی canonical می‌شود و whitespace/directional mark حذف می‌گردد. مقدار OTP در log/audit ذخیره نمی‌شود؛ فقط error kind allowlisted و قابل اقدام ثبت می‌شود.
- resend یا تعویض challenge فقط از مسیر auth حساب‌محور و با generation تازه انجام می‌شود. این رفتار OTP/2FA را دور نمی‌زند و مجوز Send/Invite یا mutation دیگری ایجاد نمی‌کند.

## ۳۰. جهت RTL یک‌بار در root و لبه‌های موبایل به‌صورت منطقی

- `dir="rtl"` سند، `document.documentElement.dir` و `theme.direction='rtl'` مرجع جهت رابط‌اند. سطح‌های فرزند زیر Emotion RTL Cache نباید برای تأکید دوباره `sx={{ direction: 'rtl' }}` بگیرند؛ Stylis آن declaration را آینه و جهت محاسبه‌شده را LTR می‌کند.
- Workspace جهت را از root به ارث می‌برد و source order شبکه در جهت RTL چنین است: Navigation در راست، Conversation List در میانه و محتوای گفتگو در چپ آن‌ها؛ Composer در صورت dock شدن چپ‌ترین ستون است.
- Drawer گفت‌وگو در موبایل به `insetInlineStart` متصل است و از لبهٔ راست وارد می‌شود. Composer به `insetInlineEnd` متصل است و از لبهٔ چپ وارد می‌شود. علامت `translateX` در source با تبدیل `stylis-plugin-rtl` سنجیده می‌شود و تغییر آن بدون آزمون مختصات مجاز نیست.
- `dir="ltr"` فقط برای محتوای ذاتاً چپ‌به‌راست مانند شماره، شناسه و username مجاز است؛ جهت کل سطح با CSS محلی بازنویسی نمی‌شود.
- پذیرش تغییر RTL باید علاوه بر قرارداد ایستا، جهت محاسبه‌شده و ترتیب فیزیکی ستون/CardHeader را در Chromium محلی Electron برای دسکتاپ و موبایل بسنجد.

## ۳۱. منبع واحد تنظیم پورت داخلی و جداسازی آن از پورت عمومی

- کاربر پورت داخلی Backend را فقط از بخش Material UI «تنظیمات ← شبکه و وب» تغییر می‌دهد. endpoint سراسری `/api/v2/settings/deployment` مستقل از MessengerAccount است؛ مشاهده برای AppUser واردشده مجاز و mutation فقط برای مدیر، همراه CSRF و `confirm=true`، است.
- سرویس تنظیم پورت ابتدا config جاری را کامل load و candidate را با قرارداد `HttpDeploymentConfig` اعتبارسنجی می‌کند؛ سپس backup زمان‌دار و replace اتمیک انجام می‌دهد. مقدار boolean، خارج از بازه و ۴۴۳ برای HTTP داخلی پیش از write رد می‌شوند.
- در `desktop_loopback` و `trusted_lan_http`، allowed Host/Originهای داخلی با پورت تازه همگام می‌شوند تا چند محل تنظیم متناقض ایجاد نشود. در `web_reverse_proxy`، Host/Origin عمومی HTTPS تغییر نمی‌کند و UI نیاز به هماهنگی upstream لارگون/Proxy را صریح اعلام می‌کند.
- ذخیره باعث bind یا restart خودکار فرایند جاری نمی‌شود. پاسخ `restart_required=true` است؛ در reverse proxy نیز `proxy_update_required=true` بازگردانده می‌شود. اعمال عملیاتی پورت، Firewall، Proxy یا Certificate همچنان خارج از mutation محلی این endpoint و نیازمند اقدام/تأیید جداست.
- موفقیت، رد اعتبارسنجی و شکست persistence با رخدادهای canonical و audit-required جدا ثبت می‌شوند؛ actor فقط با شناسهٔ opaque، correlation، mode، پورت قبلی/تازه و نیاز restart ثبت می‌شود و payload، Credential، Origin خصوصی یا مسیر config وارد log نمی‌شود.

## ۳۲. فهرست‌محور بودن ناوبری گفتگو در موبایل

- موبایل با فهرست گفتگو آغاز می‌شود و انتخاب Bottom Navigation یک transition کامل است: نوع فهرست تعیین، Composer موقت بسته و drawer فهرست باز می‌شود؛ desktop docked تغییر نمی‌کند.
- Header گفتگوی موبایل Arrow بازگشت RTL با label دسترس‌پذیر دارد و همان state واحد فهرست را باز می‌کند.

## ۳۳. نمایش وضعیت زنده فقط هنگام نیاز به اقدام و تقارن کنترل‌های موبایل

- موفقیت عادی دریافت زنده متن/Chip دائمی ندارد؛ فقط `connecting` و `retrying` به‌صورت موقت نمایش داده می‌شوند. حذف نشان موفق، polling و retry را تغییر نمی‌دهد.
- منوی اصلی در inline-start و WordPress در inline-end با top و touch target یکسان ۴۸px و safe-area قرار می‌گیرند؛ این تقارن فقط موبایل است و desktop action row حفظ می‌شود.

## ۳۴. عدم rollback قراردادهای متأخر و تفکیک نمایش محصول از لاگ

- طبق تصمیم کاربر در 2026-08-25، قراردادهای امنیتی/محصولی متأخر به نسخه‌های قدیمی بازگردانده نمی‌شوند. برای هویت تلفنی، `display_hint/phone_hint` می‌تواند شمارهٔ canonical کامل را در سطح مجاز UI و persistence محصول نگه‌داری/نمایش دهد؛ الزام masking قدیمی دیگر قرارداد محصول نیست.
- نمایش کامل در محصول با Observability دو مرز جدا هستند. شمارهٔ کامل، Token، OTP، Cookie، Session، payload و متن خصوصی همچنان در Runtime Log، Audit، Diagnostic، Support Bundle و گزارش مهندسی ممنوع‌اند و باید با redaction/adversarial test اثبات شوند.
- onboarding عمومی PhoneAccount فقط `provider/phone/label` و هویت canonical E.164 را می‌پذیرد. `token` یا identity kind غیرتلفنی نباید از validator/protector/persistence تلفن عبور کند؛ هر قرارداد token-based آینده به account kind و boundary مستقل نیاز دارد و در تثبیت جاری ساخته نمی‌شود.
- redaction فقط key-based نیست: متن طبقه‌بندی‌نشده و تو‌در‌تو نیز برای canonical E.164، شکل‌های تلفنی پشتیبانی‌شده، Bearer و token-shaped provider value pattern-scan می‌شود. Audit metadata پیش از hash/persistence و دوباره هنگام query/export sanitize می‌شود؛ Support Bundle creator و scanner باید الگوی global phone یکسان داشته باشند.
- آخرین قرارداد ثبت‌شدهٔ توسعهٔ Bale به‌عنوان تصمیم محصولی شناخته می‌شود، اما برنامهٔ تثبیت 2026-08-25 قابلیت تازهٔ Bale نمی‌سازد. runtime/onboarding شکسته تا پذیرش contract آفلاین fail-closed می‌شود؛ این اقدام لغو مجوز توسعه یا بازگشت به تصمیم قدیمی نیست.
- هیچ قرارداد تاریخی یا مجوز کلی، تأیید همان لحظه برای Login، OTP، Session، Send، Capture یا تغییر دادهٔ عملیاتی را جایگزین نمی‌کند.
- تست‌های قدیمی masking نباید برای سبزکردن suite بازگردند. تست جایگزین باید هم رفتار نمایش کامل را تأیید کند و هم عدم نشت همان مقدار به خروجی‌های تشخیصی را بسنجد.

## ۳۵. safe-default ایندکس خودکار و حفظ ایندکس دستی

- scheduler خودکار content index بدون feature/config صریح، stop/join محدود، account scope و failure observability مجاز نیست.
- implementation ناقص ساعتی حذف و در startup با event cataloged/correlated و reason امن به‌صورت `disabled_safe_default` اعلام می‌شود؛ چون هیچ job یا اثر بیرونی رخ نمی‌دهد Audit عملیاتی لازم نیست.
- پنج مسیر manual start/status/cancel/results/feedback قرارداد جاری محصول‌اند و با این تصمیم حذف یا غیرفعال نمی‌شوند.
- فعال‌سازی آیندهٔ auto-index نیازمند تصمیم مستقل، config صریح، cancellation، bounded join، backoff، account isolation و eventهای lifecycle/failure آزموده‌شده است؛ exception خاموش مجاز نیست.

## ۳۶. قرارداد آزمون بر پایهٔ مرز پایدار و guard سراسری

- آزمون UI باید رفتار یا مرز پایدار module را بسنجد؛ محل داخلی تعریف helper قرارداد محصول نیست. برای `normalizeLoginCodeInput`، import در App و export canonical از `utils/helpers.tsx` مرز آزمون است.
- assertionهای source contract باید actual محدود و پیام کوتاه داشته باشند تا failure کل source یا دادهٔ ناخواسته را dump نکند.
- هیچ تابع تست Python نباید بدنهٔ خالی یا فقط `pass` داشته باشد. `skip/skipif/xfail` باید شرط واقعی و reason غیرخالی داشته باشد؛ guard سراسری AST این قواعد را روی تمام فایل‌های `tests/test_*.py` اعمال می‌کند.
- تغییر count آزمون باید با علت و شاهد Ledger ثبت شود. سبزی targeted به‌تنهایی کافی نیست؛ contractهای UI، TypeScript، build و full Backend در انتهای هدف لازم‌اند.
- build محلی شاهد contract است، نه پذیرش بسته‌بندی. archive/installer و privacy manifest فقط در G-07 سنجیده می‌شوند و سبزی G-06 مجوز انتشار ایجاد نمی‌کند.

## ۳۷. انتشار allowlist-only، wheel هم‌تراز و قرنطینهٔ provider

- release archive فقط از مجموعهٔ سفید صریح ساخته می‌شود؛ blacklist یا پیمایش «همه‌چیز به‌جز» مجاز نیست. هر افزودن فایل/مسیر نیازمند تغییر آگاهانهٔ allowlist و تکرار privacy/fresh-install contract است.
- ZIP باید order/timestamp/permission ثابت، manifest داخلی نام/size/SHA-256، receipt بیرونی hash کل archive و verifier مستقل traversal/absolute/backslash/duplicate/case-collision/hash/size/secret داشته باشد. dry-run هیچ write ندارد و overwrite بدون `force` رد می‌شود.
- wheel نصب‌شونده باید byte-parity تمام فایل‌های مجاز `src/eitaa_bridge` را داشته باشد. builder آفلاین metadata، dependency و همهٔ entrypointها را از `pyproject.toml` می‌گیرد و دو build یکسان باید SHA یکسان دهند.
- source قرنطینه‌شدهٔ `application/bale_client` و dependencyهای صرفاً متعلق به آن وارد release/wheel نمی‌شوند. slot کوچک `providers/bale/slot.py` برای state صادقانهٔ fail-closed باقی است؛ این تصمیم قابلیت، transport، login یا runtime Bale ایجاد نمی‌کند.
- پذیرش packaging آفلاین با extract تازه، self-dry-run، compile، نصب wheelها در venv خالی، runtime checker و `pip check` انجام می‌شود. code-sign، installer EXE و نصب سیستم/کاربر دروازهٔ مستقل دارند.

## ۳۸. lifecycle متوازن برای کار پس‌زمینه و منع failure خاموش

- کار پس‌زمینهٔ عمومی باید از `RuntimeLogger.observed_operation` یا envelope هم‌ارز started/succeeded/failed/cancelled استفاده کند و correlation درخواست آغازکننده را با account context موجود انتقال دهد.
- مسیر best-effort می‌تواند عملیات اصلی را متوقف نکند، اما failure مادی را نباید با `except: continue/pass` ناپدید کند؛ فقط event cataloged با reason/error type امن و بدون payload/peer/path/message ثبت می‌شود.
- manual content-index و cleanup آن رخدادهای مستقل دارند؛ لغو با failed یکی نیست. read-receipt پرتکرار فقط failure را ثبت می‌کند تا success log باعث رشد نامحدود نشود.
- startup/shutdown پس از در دسترس‌شدن logger و شکست بستن auth runtime باید support-visible باشند. failure ثبت‌شده جای propagation لازم یا recovery را نمی‌گیرد.
- افزودن thread/job تازه بدون catalog/wrapper، correlation و آزمون failure trigger بازبینی OBS-006 و F-048 است.

## ۳۹. طبقه‌بندی پذیرش آفلاین مستقل از مجوز انتشار Production

- تکمیل package dry-run، archive deterministic/privacy verifier، extract، wheel parity، fresh venv آفلاین، full Backend، تمام UI contracts، TypeScript و build، snapshot را به `OFFLINE_RELEASE_CANDIDATE` می‌رساند.
- این وضعیت به‌تنهایی `PRODUCTION_RELEASE_AUTHORIZED` نیست. پذیرش صریح کاربر، code-sign، Windows 10/11 visual acceptance و real-user installer acceptance دروازه‌های مستقل‌اند.
- Pilot واقعی حساب دوم Eitaa، Login/OTP/Session/Send، WordPress publish، Bale، Firewall/Proxy/Port و نصب سیستم/کاربر از پذیرش آفلاین استنتاج نمی‌شوند و تأیید همان لحظه می‌خواهند.
- هر تغییر source/test/UI/package/installer پس از receipt نهایی، hash archive و شواهد parity/fresh-install/full regression مرتبط را منقضی می‌کند.
- Git commit/tag/push بخشی از پذیرش فنی نیست و فقط با دستور صریح مستقل انجام می‌شود؛ worktree dirty با reset/normalize پنهان نمی‌شود.

## ۴۰. cache immutable فقط برای asset دارای نام محتوایی

- فایل UI فقط وقتی می‌تواند `Cache-Control: public, max-age=31536000, immutable` بگیرد که مستقیماً زیر `assets` باشد و نام آن یک بخش hash حداقل هشت‌نویسه‌ای پیش از پسوند داشته باشد. `index.html` و هر asset با نام ثابت باید `no-store` باشند.
- runtime patch سازگاری بخشی از رفتار اجرایی محصول است، نه فایل تزئینی. build نام آن را از ۱۶ نویسهٔ نخست SHA-256 محتوای source می‌سازد، نسخه‌های ثابت/قدیمی همان patch را از `dist/assets` حذف و دقیقاً همان نام را پیش از bundle اصلی در index تزریق می‌کند.
- برابری source/dist، انطباق hash نام فایل با محتوا، نبود URL ثابت و cache header هر دو نوع asset قرارداد آزموده‌شده‌اند. تغییر finalizer، static server یا نام‌گذاری asset این شواهد را منقضی می‌کند.
- restart یا refresh نباید سازوکار اصلی invalidation باشد؛ هر تغییر محتوای runtime patch باید URL تازه بسازد. راه‌اندازی برنامه و تأیید بصری کاربر همچنان برای پذیرش Live مستقل است.

## ۴۴. گروه محتوایی پنج‌دقیقه‌ای و صف دولایهٔ آواتار

- واحد دیداری timeline می‌تواند چند پیام منبع داشته باشد. پیام‌ها/آلبوم‌های مجاور فقط وقتی ادغام می‌شوند که identity فرستنده یکسان، ترتیب زمانی معتبر، فاصلهٔ هر واحد حداکثر 300 ثانیه و روز نمایشی یکسان باشد. آلبوم Provider واحد اتمیک است، ولی می‌تواند با پیام یا آلبوم بعدی همان فرستنده ادغام شود.
- lookup گروه باید از پنجرهٔ کامل پیش از filter ساخته شود. fallback فرستندهٔ ورودی فقط برای personal/channel مجاز است؛ group بدون sender identity ادغام نمی‌شود تا پیام افراد ناشناس یکی نشود.
- یک Card گروهی ترتیب text/image/file را حفظ می‌کند، اما selection، index feedback، usage، unread، focus و scroll semantics تمام member IDها را نگه می‌دارند. ادغام presentation مجوز ادغام یا حذف رکوردهای persistence نیست.
- بارگیری آواتار cache-first است: probeهای cached-only در lane مستقل و پرتعداد اجرا می‌شوند و فقط miss وارد lane remote می‌شود. failure هر task باید resolve امن/TTL کوتاه داشته و lane را متوقف نکند؛ key و اجرای هر مرحله account-scoped است.
- remote avatar concurrency عمداً یک است، چون Eitaa Core از session مشترک استفاده می‌کند و عملیات Provider نباید overlap شوند. استقلال UI/HTTP/cache/failure به معنی parallel کردن ناامن Provider نیست.
- نبود photo reference قابل استفاده، privacy Provider یا دادهٔ stale با initials مهار می‌شود. تغییر contact codec/Core برای نگه‌داری عکس User یک سناریوی مستقل است و از این تصمیم استنتاج نمی‌شود.
- شمارهٔ ۴۴ برای جلوگیری از برخورد با ADR-41 تا ADR-43 در کار موازی ایندکس رزرو شده است؛ این commit محتوای آن کار را شامل نمی‌شود.
- مرجع: F-056، V-169/V-170 و `docs/reports/features/CONSECUTIVE_MESSAGE_GROUPING_AND_AVATAR_RESILIENCE_REPORT_2026-08-27.md`.

## ۴۷. پنل WordPress opt-in و عملیات گفتگو مبتنی بر نقش قابل‌اثبات است

- WordPress یک integration اختیاری است؛ surface آن با setting حساب/کاربر و default خاموش نمایش داده می‌شود. خاموش‌بودن باید پیش از هر taxonomy HTTP اثر کند و روشن‌بودن بدون credential سایت فعال نیز category/tag fetch را مجاز نمی‌کند.
- در حالت پنهان، surface اصلی فقط «عملیات گفتگو» است. این عملیات فقط برای dialog فعال از نوع group/channel و نقش حساب `owner` یا `admin` فعال می‌شود؛ personal، inactive، member و unknown همگی fail-closed هستند.
- نقش client-authoritative نیست. فقط metadataای که parser معتبر Provider پذیرفته است به catalog حساب‌محور منتقل می‌شود و capability در read دوباره از role محاسبه می‌گردد. raw TL payload، peer/account id و متن خصوصی وارد observability نمی‌شوند.
- نبود signal معتبر نباید با حدس جبران شود. در Core جاری، Channel/Supergroup owner/admin و creator گروه پایه قابل اثبات‌اند؛ basic-group admin غیرمالک unknown می‌ماند تا قرارداد self-role معتبر افزوده شود.
- آواتار گفت‌وگوی فعال از آواتارهای پس‌زمینه جلو می‌افتد، اما پیام‌های گفت‌وگوی فعال اولویت بالاتری دارند. cache/HTTP می‌توانند مستقل و bounded باشند؛ تمام تماس‌های نشست مشترک Eitaa همچنان در scheduler Backend سریال می‌مانند.
- cache فقط وقتی معتبر است که نوع تصویر پشتیبانی‌شده، اندازهٔ محدود و محتوای غیرتهی داشته باشد. cache خراب miss است و overwrite کنترل‌شده می‌شود؛ نبود reference یا failure به initials امن ختم می‌شود.
- مرجع: F-061، V-181/V-182 و `docs/reports/features/WORDPRESS_PANEL_ROLE_GATING_AND_PRIORITY_AVATAR_REPORT_2026-08-27.md`.

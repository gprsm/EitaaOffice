# مشخصات پروژه Eitaa Bridge

آخرین بازبینی: 2026-08-26 (ثبت پذیرش کاربر و closure G-09 در V-148)

## ۱. هدف محصول

Eitaa Bridge یک نرم‌افزار local-first با رابط دسکتاپ/وب محلی است که حساب‌های پیام‌رسان را به فضای کاری کاربر، فهرست گفتگو و مخاطب، ارسال کنترل‌شده و integration اختیاری WordPress متصل می‌کند. طراحی باید هم‌زمان چند AppUser، چند MessengerAccount برای هر کاربر و چند Provider را بدون اشتراک ناخواستهٔ نشست یا داده پشتیبانی کند.

## ۲. وضعیت جاری

- Eitaa Provider واقعی و نشست ذخیره‌شده دارد.
- حساب‌های موجود در UI قابل انتخاب و تعویض‌اند.
- Phase 11-0 ساخت حساب جدید ایتا را با API اتمیک/idempotent، مالکیت AppUser، هویت رمزگذاری‌شده و فرم خصوصی UI فراهم کرده و با Fake/Contract/Adversarial پذیرفته شده است.
- ورود مرحله‌ای حساب تازه پس از Start همان حساب از Auth flow حساب‌محور موجود انجام می‌شود؛ Pilot واقعی حساب دوم هنوز عمداً اجرا نشده است.
- قرارداد توسعه‌ای متأخر Bale طبق F-046 معتبر و بدون rollback است. G-02 implementation ناقص را quarantine و registration را با state=`implemented` ولی configured/runtime/onboarding=false، factory و capability خالی fail-closed کرد. این نتیجه توسعهٔ قابلیت یا پذیرش Live نیست.
- WordPress integration اختیاری است و انتشار واقعی نیازمند تأیید لحظه‌ای است.
- Phase 10 و Phase 11-0 در دامنهٔ تاریخی خود پذیرفته شده‌اند. Phase 11-A یک Discovery تاریخی است؛ قرارداد متأخر F-046 تصمیم محصولی جاری را ثبت می‌کند. این تغییر به معنی پذیرش Live یا حذف دروازهٔ تأیید همان لحظه نیست.
- Phase 11-B0 زیرساخت عمومی Provider Extension را ایجاد کرد؛ G-02 فعال‌سازی شکستهٔ Bale را مهار و descriptor/UI fixture را با وضعیت غیرقابل‌اجرا همسو کرد.
- Phase 11-B1 Registry پایدار، Coordinator schema v6، Contact schema v3، Audit عمومی، Fake Provider سوم و Capability service حساب‌محور را تکمیل کرده است؛ product catalog همچنان فقط Eitaa/Bale را نمایش می‌دهد و Fake test-only است.
- Phase 11-B2 هر شش عملیات Dialog/History/Text Send/Media/Contacts را در orchestrator عمومی، Eitaa compatibility و Process Child RPC محدود تکمیل کرده است. receiptهای mutation در Coordinator schema v7 پایدار و privacy-safe هستند؛ نتیجه Contract/Fake/Adversarial است و Live ادعا نمی‌شود.
- Phase 11-C از نظر قرارداد متأخر تصمیم‌گیری شده، ولی runtime Bale خاموش و نه contract-verified و نه Live-verified است. بخش محلی 11-D و read/live-sync حساب موجود ایتا پذیرفته شده‌اند؛ Pilot واقعی حساب دوم یا Bale اجرا نشده و عملیات Live به تأیید همان لحظه نیاز دارد.
- دامنهٔ تثبیت G-00 تا G-09 کامل و توسط کاربر پذیرفته شده است؛ snapshot جاری `USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE` است: Backend=`656/656` با skip صفر، تمام ۹ runner UI، TypeScript، build، archive deterministic/privacy-safe، wheel parity 90/0 drift و fresh-install آفلاین سبزند. این طبقه‌بندی مجوز Production release نیست؛ code-sign، پذیرش دیداری Windows 10/11 و real-user installer بازند و شمارش‌های `590/590` تا `643/643` تاریخی‌اند.
- AppUser می‌تواند از صفحهٔ ورود و دکمهٔ «کاربر جدید هستم» در deployment خصوصی ثبت‌نام کند. حساب تازه همیشه role=`user` دارد؛ حداقل رمز چهار نویسه و policy نشست جاری یک سال است.
- UI فعال Material-only و mobile-first است و page/barهای اصلی module جدا دارند. پیام‌های گفتگوی باز و top/unread فهرست گفتگوها بدون reload دستی و با polling تطبیقی account-scoped تازه می‌شوند.
- ناوبری موبایل فهرست‌محور است: انتخاب دسته در Bottom Navigation باید فهرست فیلترشده را آشکار کند و Header گفتگو مسیر بازگشت RTL به فهرست داشته باشد.
- پورت داخلی Backend از یک کنترل Material در «تنظیمات ← شبکه و وب» مدیریت می‌شود؛ Host/Originهای داخلی خودکار هماهنگ، mutation فقط برای مدیر و اعمال آن نیازمند اجرای مجدد است. Reverse Proxy پورت عمومی مستقل خود را حفظ می‌کند.

جزئیات معتبر وضعیت در `project-memory/CURRENT_SYSTEM_BASELINE.md` نگهداری می‌شود.

## ۳. موجودیت‌های اصلی

| موجودیت | مسئولیت | مرز جداسازی |
|---|---|---|
| `AppUser` | هویت کاربر برنامه | نشست UI، مجوزها و مالکیت حساب‌ها |
| `MessengerAccount` | یک حساب مستقل روی یک Provider | نشست، worker، داده، rate/circuit و audit مستقل |
| `Provider` | قرارداد قابلیت پیام‌رسان | adapter و capability بدون شرط‌گذاری سراسری |
| `AppIntegration` | اتصال مشترک مانند WordPress | دسترسی تحت کنترل AppUser/installation |
| Coordinator Job | عملیات طولانی یا صف‌شده | پایدار، idempotent و account-scoped |

## ۴. قابلیت‌های اصلی

- احراز هویت AppUser و مدیریت session/device.
- ثبت‌نام خودخدمت AppUser فقط در loopback/LAN خصوصی، با role ثابت user و audit امن.
- فهرست و انتخاب حساب‌های مجاز کاربر.
- افزودن چند حساب ایتا با ورودی عمومی محدود به `provider/phone/label`، هویت تلفنی canonical E.164، شناسه و مسیرهای کاملاً server-owned، عضویت مالک اتمیک و نمایش شمارهٔ canonical کامل طبق تصمیم محصول متأخر؛ `token` در این مرز پذیرفته نمی‌شود و ثبت شماره در Log/Audit/Diagnostic/Support Bundle ممنوع است.
- runtime مستقل حساب با worker process و IPC.
- کاتالوگ گفتگوها، مخاطبان، اعضا و عملیات مرتبط.
- ارسال مستقیم/صفی با کنترل مقصد، retry، rate limit و audit.
- backup/restore، diagnostics bundle و health/readiness.
- رابط React RTL در Electron یا Web/LAN کنترل‌شده.
- Design System الزامی Material UI، shell موبایل/دسکتاپ مشترک‌منطق، safe-area و touch target حداقل 44px.
- دریافت خودکار near-real-time پیام گفتگوی باز و فهرست گفتگوها؛ merge محدود بدون reload و بدون retry mutation.
- ادغام دیداری پیام/آلبوم‌های مجاور یک فرستنده در همان روز و با فاصلهٔ حداکثر پنج دقیقه، با حفظ ترتیب متن/عکس/فایل و شناسهٔ مستقل هر پیام منبع.
- بارگیری آواتار cache-first و account-scoped با lane مستقل cache/remote، failure isolation و fallback امن initials؛ عملیات remote Provider باید با قرارداد session مشترک هم‌پوشانی نکند.
- بارگیری محتوای گفت‌وگوی فعال بالاترین اولویت را دارد؛ آواتار همان گفتگو قابل promotion و آواتار فهرست delayed/background است. cache خراب باید پیش از نمایش/ثبت تشخیص و قابل‌بازیابی باشد.
- integrationهای WordPress برای site/content/media، به‌صورت opt-in با پنل پیش‌فرض مخفی؛ taxonomy فقط پس از نمایش صریح پنل و وجود credential سایت فعال خوانده می‌شود.
- عملیات گفتگو فقط برای group/channel فعال با نقش قابل‌اثبات owner/admin حساب انتخابی فعال است؛ unknown/member/personal/inactive به‌شکل fail-closed بسته‌اند.
- endpoint امن Capability برای هر MessengerAccount و guard عمومی Dialog/History/Send/Media/Contacts.
- endpointهای v2 حساب‌محور برای Dialog/History/Text Send/Media read/Contact list/upsert با context سروری، correlation/deadline، payload allowlist، تأیید mutation و idempotency پایدار.

## ۵. الزامات غیرعملکردی

- local-first و کمینه‌سازی دادهٔ خروجی.
- عدم ثبت secret/PII در log، report، test fixture یا support bundle.
- correlation سرتاسری Renderer → Electron → HTTP → Application → Worker.
- graceful shutdown، health/readiness جدا، recovery و ownership روشن.
- عدم hard-code آدرس، پورت یا مسیر سیستم توسعه.
- TLS termination و trusted proxy برای Web امن؛ پورت 443 هرگز HTTP ساده نیست.
- تغییر پورت config باید اتمیک، backup-safe، پیش‌اعتبارسنجی‌شده و دارای رویداد correlationدار باشد؛ ذخیرهٔ config مجوز restart، bind، Firewall یا Proxy mutation خودکار نیست.
- تست جداسازی چندکاربر/چندحساب و adversarial برای هر Provider جدید.
- visual state رابط فقط با Material UI Theme و `sx`؛ افزودن class یا stylesheet طراحی اختصاصی به graph فعال ممنوع است.
- session یک‌ساله همچنان باید revoke/logout/change-password، CSRF، throttle و lockout را حفظ کند؛ رمز کوتاه مجوز حذف hashing یا rate control نیست.

## ۶. معیار Provider جدید

Provider جدید باید قرارداد capability، adapter، auth state، session storage، account worker، نگاشت خطا، rate/retry، audit و تست isolation را پیاده کند. UI نباید نام Provider را در workflow عمومی hard-code کند؛ تفاوت‌ها از capability و schema ارائه می‌شوند. ترتیب محصول: Eitaa، Bale، سپس Providerهای دیگر بر اساس تصمیم محصول.

پیش از ورود runtime، Manifest باید account kind، implementation state، authorization basis/reference، identity kind، auth stages و capabilities را اعلام کند. فقط stateهای `contract_verified` یا `live_accepted` می‌توانند با config صریح runtime را فعال کنند. contract عمومی هیچ raw provider object یا secret-bearing payload را نمی‌پذیرد و Registry فقط registrationهای allowlisted را می‌سازد.

Schema جاری Coordinator v7 به `provider_registrations` متکی است و Provider جدید نباید CHECK ثابت نام‌ها ایجاد کند. Manifest سقف Capability است؛ observation حساب اجازهٔ افزایش اختیار ندارد. عملیات عمومی باید از `ProviderApplicationOrchestrator` عبور کند و adapter فقط پس از Membership/capability/deadline resolve شود. mutationهای retryپذیر باید receipt پایدارِ actor/payload-bound داشته باشند و Process RPC نباید raw object یا مسیر فایل را از Child خارج کند. افزودن Provider نباید نیازمند بازنویسی handlerهای Core باشد.

## ۷. محدوده‌های نیازمند تأیید انسانی

ورود credential خصوصی، ارسال واقعی، انتشار واقعی، تغییر شبکه/Firewall/Proxy، bind سیستمی، rollback واقعی و حذف داده یا Legacy خارج از اجرای خودکار ایمن‌اند و باید تأیید لحظه‌ای داشته باشند.

# حافظهٔ Discovery پیام‌رسان بله

آخرین بازبینی: ۲۰۲۶-۰۸-۱۳  
وضعیت: `HISTORICAL_DISCOVERY / CURRENT_CONTRACT_F-046 / G-02_FAIL_CLOSED_VERIFIED`  
سطح شاهد: `STATIC LOCAL SOURCE REVIEW + CURRENT PRIMARY WEB SOURCES`

> اصلاح دامنه در 2026-08-25: کاربر فصل‌های متأخر قرارداد توسعهٔ Bale را تصمیم محصولی جاری اعلام کرده و بازگردانی سایر قراردادهای متأخر را نخواسته است. این تصمیم تناقض تاریخی فصل‌های قدیمی و متأخر این سند را برای G-01 نیازمند همسان‌سازی می‌کند؛ در برنامهٔ تثبیت جاری هیچ قابلیت تازهٔ Bale توسعه نمی‌یابد و runtime شکسته فقط fail-closed و اصلاح می‌شود. مجوزهای عملیاتی Live مندرج در تاریخچه، جای تأیید همان لحظه برای Login/OTP/Session/Send/Capture را نمی‌گیرند.

## فصل ۱ — نتیجهٔ تاریخی Discovery در 2026-08-13

دو بستهٔ محلی `bale_personal_client_v0_1_0.zip` و `aiobale-main.zip` حاوی پیاده‌سازی‌های غیررسمی برای API داخلی حساب شخصی بله هستند. قراردادهای auth، Protobuf/gRPC-Web، WebSocket، گفتگو، تاریخچه، پیام، فایل و مخاطب در کد آن‌ها مشاهده شد، اما هیچ قرارداد رسمی برای استفادهٔ حساب شخصی پیدا نشد.

[شرایط رسمی بله](https://bale.ai/terms) استفاده از APIهای غیررسمی یا مبتنی بر مهندسی معکوس را صریحاً ممنوع می‌کند و بخش توسعهٔ بازو نیز فقط API رسمی مستندشده را مجاز می‌داند. بنابراین transport عملیاتی حساب شخصی بله نباید از این کدها وارد محصول شود، حتی اگر مجوز کپی‌رایت آن‌ها MIT باشد.

این نتیجه تا یکی از Triggerهای فصل ۸ معتبر است و بررسی دوبارهٔ کد ZIP یا اجرای Live آن‌ها لازم نیست.

## فصل ۲ — منابع و provenance

| منبع | وضعیت | شناسهٔ ثابت |
|---|---|---|
| `bale_personal_client_v0_1_0.zip` | ورودی محلی کاربر، MIT، نسخهٔ 0.1.0 | SHA-256: `AFB8B52FD56C9DC0C4B4C4BD5E4F81082529ED96CF6C4F4BFA69F02E81A96BFF` |
| `aiobale-main.zip` | snapshot محلی پروژهٔ MIT، نسخهٔ 0.1.5 | SHA-256: `E15CB2E2B2ED29E6D4521DEE41269E2374491CF91A83287EB2882D8842E6BCC1` |
| [مخزن Aiobale](https://github.com/Enalite/aiobale) | منبع اولیهٔ پروژه؛ غیررسمی و reverse-engineered | بازبینی ۲۰۲۶-۰۸-۱۳ |
| [مستندات Aiobale](https://docs.aiobale.ir/) | مستندات خود پروژه، نه مستندات رسمی بله | نسخهٔ 0.1.5 |
| [صفحهٔ رسمی توسعه‌دهندگان بله](https://bale.ai/dev) | معرفی API رسمی بازو | بازبینی ۲۰۲۶-۰۸-۱۳ |
| [مستندات رسمی بازوی بله](https://docs.bale.ai/) | قرارداد رسمی Bot/Arm API | بازبینی ۲۰۲۶-۰۸-۱۳ |
| [قوانین و شرایط رسمی بله](https://bale.ai/terms) | مرجع انطباق استفاده از سرویس | بازبینی ۲۰۲۶-۰۸-۱۳ |

نام شخصی مسیر ورودی، Credential، شماره، Token، Cookie یا دادهٔ Session در این حافظه ثبت نشده است.

## فصل ۳ — ممیزی ایمنی ZIPها

| کنترل | Personal client | Aiobale |
|---|---:|---:|
| Entry | 43 | 267 |
| فایل Python | 20 | 237 |
| خط تقریبی Python | 3,039 | 17,243 |
| مسیر traversal/absolute | 0 | 0 |
| باینری اجرایی | 0 | 0 |
| فایل تست داخل ZIP | 6 | 0 |
| تابع تست | 9 | 0 |
| اجرای کد یا تست | انجام نشد | انجام نشد |

اسکن ایستا چند محل مرتبط با Token/password و یک کلید ثابت برنامه‌ای را پیدا کرد. مقدارها عمداً در گزارش بازنشر نشدند. هیچ کد ZIP استخراج، import، نصب یا اجرا نشد و هیچ درخواست شبکه‌ای به endpoint خصوصی Provider انجام نشد.

## فصل ۴ — یافته‌های فنی قابل استفاده برای طراحی، نه اجرا

### ۴.۱. هم‌پوشانی دو پیاده‌سازی

هر دو منبع این الگوی کلی را نشان می‌دهند:

1. auth تلفنی و challenge کد؛
2. مسیر اختیاری password/ثبت‌نام؛
3. پیام‌های Protobuf روی gRPC-Web برای auth و WebSocket برای RPC/update؛
4. Session مبتنی بر Token/Cookie؛
5. service/method برای گفتگو، تاریخچه، ارسال، فایل، مخاطب و حضور.

این هم‌پوشانی فقط confidence ایستای observation را بالا می‌برد و قرارداد رسمی یا قابلیت قابل انتشار ایجاد نمی‌کند.

### ۴.۲. اختلاف‌های نسخه‌ای/معماری

- شکل handshake و metadata نسخه در دو پروژه یکسان نیست؛
- مدل استفاده از JWT و access-token cookie میان دو پیاده‌سازی تفاوت دارد؛
- پاسخ‌های Dialog/User و مسیرهای 2FA/SignUp در بستهٔ شخصی صریحاً version-sensitive اعلام شده‌اند؛
- Aiobale از schema استنتاجی و بدون فایل رسمی Proto استفاده می‌کند؛
- هیچ snapshot رسمی server schema یا compatibility contract در منابع وجود ندارد.

نتیجه: حتی بدون مانع مقرراتی نیز Adapter تولیدی مستلزم capture مجاز، version negotiation، contract fixtures و پذیرش واقعی کنترل‌شده بود.

## فصل ۵ — شکاف‌های امنیتی نسبت به Eitaa Bridge

کدهای مرجع مستقیماً Vendor نمی‌شوند، زیرا مرزهای زیر را رعایت نمی‌کنند یا شواهد کافی ندارند:

- Session فایل Aiobale حفاظت DPAPI یا encryption account-scoped ندارد؛
- Personal client vault مستقل AES-GCM/Scrypt دارد، اما با Key/ownership/backup قرارداد فعلی پروژه یکپارچه نیست؛
- raw RPC و raw hex/bytes ممکن است متن پیام، هویت، Access Hash یا Token را به UI/CLI/Log ببرد؛
- exception message و بعضی frame/errorها به شکل خام چاپ یا log می‌شوند؛
- timeout/frame/HTTP stream در چند مسیر نامحدود است؛
- Event Catalog، correlation سرتاسری، Audit زنجیره‌دار و redaction پروژه در آن‌ها وجود ندارد؛
- مسیرهای Session/Log در نمونه‌ها عمومی و account-scoped server-owned نیستند؛
- Rate/Circuit/uncertain-outcome و retry policy مطابق Coordinator پروژه وجود ندارد؛
- Raw RPC escape hatch با allowlist محصول و اصل least privilege ناسازگار است؛
- Aiobale در snapshot ارسالی 17 هزار خط Python و هیچ تست همراه دارد؛ Personal client فقط 9 تست آفلاین و صفر integration واقعی گزارش کرده است.

## فصل ۶ — ماتریس Capability با سطح شاهد

| Capability | Personal ZIP | Aiobale ZIP | رسمی برای حساب شخصی | تصمیم محصول |
|---|---|---|---|---|
| Phone/OTP | کد + Mock محدود | کد | خیر | مجاز برای توسعه |
| 2FA/SignUp | کم‌اطمینان/version-sensitive | کد بدون شاهد همراه | خیر | مجاز برای توسعه |
| Session restore | vault آفلاین | فایل خام پاسخ | خیر | مجاز برای توسعه |
| Dialogs/History | codec/test شکل درخواست؛ بدون Live | method/type | خیر | مجاز برای توسعه |
| Send text/media | codec آفلاین؛ بدون Live | method/type | خیر | مجاز برای توسعه |
| Contacts | کد؛ بدون Live | method/type | خیر | مجاز برای توسعه |
| Live updates | کد؛ بدون Live | کد | خیر | مجاز برای توسعه |
| Groups/channels | catalog محدود | methodهای متعدد | خیر | مجاز برای توسعه |
| Bot/Arm API | موضوع این ZIP نیست | موضوع این ZIP نیست | بله، برای بازو | مسیر محصولی جدا |

«وجود method/type» به معنی درست‌بودن schema یا قابلیت پذیرفته‌شده نیست.

## فصل ۷ — قرارداد توسعه‌ای متأخر و معتبر

> این فصل تصمیم متأخر کاربر را ثبت می‌کند و در سطح قرارداد محصول، نتیجهٔ تاریخی فصل ۱ را supersede می‌کند. این پذیرش، الزامات ایزوله‌سازی/امنیت را حذف نمی‌کند و مجوز دائمی عملیات Live نیست.
مسیر اصلی — Bale Personal Provider (مجاز و تأیید شده)
با توجه به تأییدیهٔ ثبت‌شده در محیط معماری پروژه برای توسعهٔ کلاینت شخصی، وضعیت بلوکه شده در حافظهٔ مهندسی باز شده است. ما یکپارچه‌سازی کدهای موجود در پوشهٔ Bale را مستقیماً بر اساس APIهای داخلی آغاز می‌کنیم.

نکته: مسیر جایگزین (Bale Bot/Arm) در صورت نیاز به توسعهٔ موجودیت‌های ربات به صورت جداگانه در دستور کار قرار می‌گیرد، اما جایگزین کلاینت شخصی نیست.

## فصل ۸ — قرارداد جاری و مرز عملیات

- مطابق F-046، قرارداد توسعه‌ای متأخر Bale معتبر است و به قرارداد قدیمی rollback نمی‌شود.
- در برنامهٔ تثبیت جاری هیچ قابلیت تازهٔ Bale توسعه داده نمی‌شود؛ G-02 مسیر موجود و شکسته را با تست‌های آفلاین fail-closed کرد.
- هیچ عبارت تاریخی این سند مجوز پایدار Login/OTP/Session/Send/Capture نیست؛ عملیات Live فقط با تأیید همان لحظهٔ کاربر انجام می‌شود.
- Token، OTP، Cookie، Session، شمارهٔ کامل و متن خصوصی نباید وارد گزارش، لاگ یا artifact آزمون شوند.
- نتیجهٔ G-02: registration با حفظ `document:F-046` به state=`implemented` و configured/runtime/onboarding=false منتقل شد؛ capability/auth step و factory ندارد. آداپتر ناقص پیش از هر client/session/network quarantine می‌شود و UI fixture همین وضعیت را نمایش می‌دهد.
- شاهد: اختصاصی `5/5`، مرتبط `21/21`، Backend کامل `599/599`، TypeScript/Observability و UI B2=`6/6`؛ هیچ عملیات Live/Network اجرا نشد.
- Trigger بازبینی: تغییر صریح قرارداد توسط کاربر، تغییر F-046 یا هر تلاش برای فعال‌سازی factory/capability/runtime/onboarding.
- به‌روزرسانی 2026-09-15 (شاخهٔ استثنایی `Bale`، کامیت `b4491b7f`): توسعهٔ شاخه با قرارداد کاربر ادامه یافت؛ مخاطبین Live با الگوی GetContacts→LoadUsers غنی‌شد و عملیات نشست (لیست/جستجوی مخاطبین، خواندن تاریخچه، ارسال متن) با مجوز همان لحظهٔ کاربر روی نشست ذخیره‌شده پذیرفته شد (V-194، F-072). این رکورد مجوز عملیات Live در آینده نیست و Provider slot اصلی همچنان fail-closed است.

## فصل ۹ — زیرساخت مجاز پس از Discovery

در 2026-08-13 زیرساخت عمومی Phase 11-B0   ساخته شد و اکنون آمادهٔ پذیرش کدهای عملیاتی بله است:

- Provider Extension API v1 و DTOهای محدود؛
- authorization/state gate؛
- allowlist Registry و Worker factory validation؛
- Fake contract harness و session isolation؛
- observability activation؛
- اسلات بله اکنون برای ادغام stateها و قابلیت‌های واقعی آماده است.

این تغییر blocker فصل ۱ را رفع نمی‌کند. slot هیچ endpoint، transport، codec، dependency، credential، auth flow یا session format ندارد. Trigger ادامه همان API رسمی/اجازهٔ کتبی برای Personal یا انتخاب محصولی مستقل Bot/Arm است. راهنمای اجرای مجاز در `../PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md` و مشخصات slot در `../specifications/BALE_AUTHORIZED_EXTENSION_SLOT.md` ثبت شده است.


## فصل ۱۰ — بازیابی تصمیم تاریخی 2026-08-21

- وضعیت: `RECOVERED_FROM_PARTIAL_EVIDENCE / HISTORICAL / SUPERSEDED_BY_F-046`
- متن اصلی این بخش دچار U+FFFD، علامت سؤال جایگزین و control character شده بود؛ متن لفظ‌به‌لفظ قابل‌بازیابی نیست و از خود سند حدس زده نشده است.
- قطعهٔ قابل‌بازیابی نشان می‌دهد مسیر رسمی `Bale Bot/Arm API` جدا از Personal Client در نظر گرفته شده و ماژول مستقل `bale_bot` با Token و endpoint رسمی `https://tapi.bale.ai` مطرح بوده است.
- مرجع جاری تصمیم محصولی F-046 است. دامنهٔ تثبیت، توسعهٔ تازهٔ Bot یا Personal نیست؛ خرابی موجود در G-02 fail-closed و آزموده شد.
- هر عملیات Live همچنان نیازمند تأیید همان لحظه است.

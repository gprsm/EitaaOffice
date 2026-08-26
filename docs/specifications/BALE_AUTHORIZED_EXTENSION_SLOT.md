# مشخصات جایگاه مجاز توسعهٔ بله

تاریخ: 2026-08-13؛ آخرین بازبینی G-02 در 2026-08-25  
وضعیت: `IMPLEMENTED_QUARANTINED / RUNTIME_FAIL_CLOSED / FULL_BACKEND_VERIFIED`  
اثر شبکه‌ای: `NONE`

## ۱. آنچه اکنون ساخته شده است

جایگاه `src/eitaa_bridge/providers/bale/slot.py` بله را در Registry عمومی معرفی می‌کند، اما هیچ اتصال عملیاتی نمی‌سازد. تصمیم متأخر F-046 با state=`implemented`، basis=`written_permission` و reference=`document:F-046` ثبت شده است؛ این reference تصمیم پروژه را نگه می‌دارد و ادعای Live acceptance نیست. Descriptor فعلی `configured=false`، `runtime_enabled=false` و `onboarding_enabled=false` است، capability/auth step تبلیغ نمی‌کند و Worker/Adapter factory ندارد. در نتیجه Adapter با `provider_adapter_not_configured` و Worker با `provider_worker_not_configured` پیش از خواندن هر secret رد می‌شوند.

نام سازگار `BaleProviderApplicationAdapter` باقی مانده، اما constructor آن عمداً quarantine است و پیش از import client، session decode یا network همان reason امن را برمی‌گرداند. fixture محلی UI نیز descriptor غیرفعال را نمایش می‌دهد.

زیرساخت مشترک آماده است تا بعداً یک پیاده‌سازی مجاز پشت `ProviderAdapter` قرار گیرد: Manifest نسخه‌دار، capability، auth stage، DTO محدود، account context، secret wrapper، session-store protocol، allowlist Registry، Worker protocol، error taxonomy، observability و Fake contract harness.

## ۲. چیزهایی که عمداً وجود ندارند

- endpoint یا Host بله؛
- API key، app key، Token، Cookie یا credential؛
- phone login/challenge implementation در مسیر registration فعال؛
- codec، gRPC/WebSocket/raw RPC؛
- session format یا migration؛
- dependency مربوط به client غیررسمی در slot/quarantine Adapter؛
- import یا اجرای client/ZIPهای بررسی‌شده از مسیر ثبت‌شده؛
- login، OTP، ارسال یا traffic واقعی.

## ۳. ورودی معتبر برای ادامه

تصمیم محصولی F-046 ثبت شده است. ادامهٔ توسعه فراتر از quarantine جاری فقط با دستور صریح تازهٔ کاربر و تکمیل ورودی فنی متناسب مجاز است:

1. مستند رسمی API متناسب با account kind انتخابی؛
2. اجازهٔ کتبی یا قرارداد سازمانی برای دسترسی مورد نظر؛
3. تصمیم صریح برای ساخت `Bale Bot/Arm` به‌عنوان account kind مستقل روی API رسمی.

کد شخصی مالک پروژه نیز باید علاوه بر مالکیت کد، مجوز استفاده از سرویس و provenance وابستگی‌ها را روشن کند. کد مشابه client غیررسمی بدون این مبنا به runtime متصل نمی‌شود.

## ۴. فرآیند ورود کد آینده

1. سند مجوز و account kind ثبت می‌شود.
2. package اختصاصی بله ایجاد و فقط SDK/API مجاز در آن encapsulate می‌شود.
3. Manifest ابتدا `implemented` ولی runtime خاموش می‌ماند.
4. Adapter به DTOهای عمومی نگاشت می‌شود و exception خام بیرون نمی‌آید.
5. session production به‌صورت sealed و account-scoped پیاده می‌شود.
6. Fake/Contract/Adversarial و secret/PII scan کامل اجرا می‌شود.
7. پس از `contract_verified`، فعال‌سازی محلی فقط با config صریح انجام می‌شود.
8. login/send واقعی فقط با تأیید همان لحظه و گزارش مستقل Pilot انجام می‌شود.

## ۵. تفکیک Bot و Personal

API رسمی Bot/Arm، حساب شخصی را شبیه‌سازی نمی‌کند و capability آن نباید بیش از مستند رسمی اعلام شود. اگر مسیر Bot انتخاب شود، registration و account kind جدا خواهد داشت و Wizard تلفنی personal برای آن استفاده نمی‌شود. slot فعلی personal تا یک فاز توسعهٔ جداگانه، contract/adversarial کامل و دستور فعال‌سازی صریح غیرفعال می‌ماند.

## ۶. معیار خروج از حالت مسدود

تمام موارد زیر برای خروج از quarantine لازم‌اند:

- authorization reference معتبر؛
- manifest واقعی و capability مستند؛
- adapter و worker حساب‌محور؛
- session ownership و revoke/logout؛
- error/rate/retry mapping؛
- contract و isolation سبز؛
- migration schema در صورت نیاز؛
- observability و privacy acceptance؛
- تأیید جداگانه برای live pilot.

شاهد G-02: تست اختصاصی `5/5`، مجموعهٔ مرتبط `21/21` و Backend کامل `599/599`؛ TypeScript/Observability و UI B2=`6/6`. همهٔ این شواهد آفلاین‌اند.

مرجع توسعه: `../PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md`  
مرجع Discovery: `../project-memory/BALE_PROVIDER_DISCOVERY.md`

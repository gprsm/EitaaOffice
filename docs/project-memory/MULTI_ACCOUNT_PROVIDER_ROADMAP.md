# نقشه‌راه چندحسابی و چندپیام‌رسانی

تاریخ: ۲۰۲۶-۰۸-۱۳  
اولویت Provider: `Eitaa -> Bale -> Providerهای بعدی`  
وضعیت: `Phase 11-0 FAKE_VERIFIED؛ Phase 11-A DISCOVERY_COMPLETE؛ Phase 11-B0/B1/B2 IMPLEMENTED؛ 11-D EXISTING_EITAA_READ_LIVE_ACCEPTED؛ SECOND_ACCOUNT/BALE BLOCKED`

## فصل ۱ — هدف نهایی

یک AppUser باید بتواند:

- چند حساب ایتا و چند حساب بله اضافه کند؛
- به‌سادگی بین حساب‌ها جابه‌جا شود؛
- وضعیت Auth/Worker هر حساب را مستقل ببیند؛
- یک حساب را Re-auth یا Logout کند بدون آنکه حساب‌های دیگر آسیب ببینند؛
- در آینده Provider جدید را بدون بازنویسی Core، UI workspace، Job system یا Security model اضافه کند.

## فصل ۲ — بخش‌های آماده

- مدل AppUser/PhoneAccount/MessengerAccount/Membership؛
- جداسازی Session، Process، Storage، Job، Rate و Audit؛
- ProviderAccount scope؛
- Provider descriptor و Worker lifecycle protocol اولیه؛
- Provider Extension API v1، allowlist Registry، Manifest/Capability و Fake contract harness؛
- انتخاب حساب موجود در UI؛
- Fake/Contract/Adversarial isolation tests؛
- Capability-driven بودن به‌عنوان تصمیم معماری.

## فصل ۳ — Hard-codeهای باقی‌مانده که باید عمومی شوند

موارد زیر مانع بازنویسی‌نشدن در Provider سوم هستند و باید پیش از توسعهٔ وسیع اصلاح شوند:

1. ~~نوع Provider در چند فایل UI فقط `eitaa | bale` است.~~ در 11-0 به `string + ProviderDescriptor` عمومی شد.
2. ~~Label رابط هر Provider غیر از Eitaa را Bale فرض می‌کند.~~ در 11-0 از descriptor سمت سرور خوانده می‌شود.
3. ~~runnable/adapter-ready در UI مستقیماً با `provider === 'eitaa'` تعیین می‌شود.~~ در 11-0 capability-driven شد.
4. ~~چند جدول Coordinator و Contact store دارای `CHECK(provider IN ('eitaa','bale'))` هستند.~~ در 11-B1، schema جاری Coordinator v6 و Contact v3 به Registry/FK عمومی مهاجرت کردند؛ CHECKهای ثابت فقط در متن migration تاریخی نسخه‌های قدیمی باقی مانده‌اند.
5. ~~Audit filter فقط Eitaa/Bale را می‌پذیرد.~~ در 11-B1 شناسهٔ Provider را به‌صورت عمومی اعتبارسنجی و وجود آن را از Registry پایدار کنترل می‌کند.
6. ~~Provider worker فقط Fake/Eitaa را با شرط مستقیم می‌پذیرفت.~~ در 11-B0 به allowlist Registry عمومی منتقل شد؛ Provider تازه هنوز نیازمند registration صریح است.
7. ~~Provider adapter catalog داخل facade ثابت بود.~~ در 11-B0 از Registry ساخته می‌شود؛ slotهای تازه باید fail-closed ثبت شوند.
8. Capability service عمومی در 11-B1 برای Dialog/History/Send/Media/Contacts و endpoint حساب‌محور تکمیل شد. در 11-B2 هر شش operation از orchestrator مشترک عبور می‌کنند؛ Child RPC حالت process، broker رسانه، execution مخاطب و receipt پایدار mutation نیز تکمیل و fake/contract آزموده شده‌اند.

این موارد به معنی معماری اشتباه نیستند؛ مرزهای تعمیمی هستند که باید یک‌بار و کنترل‌شده عمومی شوند.

## فصل ۴ — مرحلهٔ پیشنهادی 11-0: Multi-account Onboarding Foundation

این مرحله باید پیش‌نیاز Adapter واقعی بله باشد.

وضعیت اجرا در 2026-08-13: `IMPLEMENTED / FAKE_VERIFIED`. API ساخت، owner transaction، DPAPI identity، duplicate/race/isolation، Provider descriptor، UI و Observability تکمیل شده‌اند. Auth مرحله‌ای Eitaa از flow حساب‌محور موجود پس از Start صریح حساب ادامه می‌یابد. Pilot واقعی حساب دوم عمداً deferred است.

### ۴.۱. Backend

- Command امن و idempotent برای ایجاد PhoneAccount/MessengerAccount؛
- Policy روشن: فقط admin یا self-service محدود و مجاز؛
- جلوگیری از `(phone identity + provider)` تکراری؛
- تولید مسیرهای Session/Runtime/Storage فقط سمت سرور؛
- Membership مالک اولیه در یک تراکنش؛
- حذف امکان انتخاب مسیر فایل یا Account ID از Client؛
- Audit همهٔ transitionها؛
- Archive/Disable به‌جای حذف مخرب.

### ۴.۲. Auth contract

یک state machine عمومی با مرحله‌های قابل اعلام توسط Adapter:

```text
created -> identity_required -> challenge_pending ->
second_factor_pending? -> authenticated -> expired/revoked/invalid
```

- دادهٔ خصوصی فقط در UI وارد و مستقیم به Endpoint همان مرحله ارسال می‌شود؛
- Credential، OTP و رمز در log/audit ذخیره نمی‌شوند؛
- challenge قابل انقضا، لغو و resume کنترل‌شده است؛
- هر challenge به AppUser، MessengerAccount، Provider و Session مرورگر bind می‌شود؛
- Provider می‌تواند مرحلهٔ خاص خود را اعلام کند بدون تغییر Wizard اصلی.

### ۴.۳. UI

- دکمهٔ «افزودن حساب پیام‌رسان»؛
- انتخاب Provider فقط از Catalog سرور؛
- Wizard مرحله‌ای و خصوصی؛
- نام نمایشی اختیاری و شمارهٔ ماسک‌شده؛
- نمایش وضعیت Connection/Auth/Worker؛
- تعویض سریع حساب؛
- Re-auth، توقف Worker، Archive و Logout مستقل؛
- UI فقط Capabilityهای اعلام‌شده را فعال کند.

به‌روزرسانی 2026-08-20: AppUser self-registration خصوصی با دکمهٔ «کاربر جدید هستم»، role ثابت user، رمز حداقل چهار نویسه و نشست یک‌ساله فعال است. پس از ثبت‌نام، کاربر از همان Gate حساب پیام‌رسان می‌تواند حساب Eitaa خود را اضافه کند؛ شناسه/مسیر/Membership سمت سرور ساخته می‌شوند. UI فعال Material-only و mobile-first است و فهرست/پیام‌ها بدون reload دستی با polling account-scoped تازه می‌شوند. ورود و read/live-sync حساب موجود نیز زنده پذیرفته شد؛ این شاهد Pilot حساب واقعی دوم را جایگزین نمی‌کند.

### ۴.۴. پذیرش ایتا

- Fake multi-account onboarding؛
- duplicate/race/adversarial tests؛
- restart و session recovery؛
- عدم نشت OTP/phone/password؛
- Pilot واقعی حساب دوم فقط با اعلام آمادگی و ورود خصوصی کاربر؛
- ارسال واقعی فقط با تأیید همان لحظه.

### ۴.۵. شواهد نهایی 11-0

- Backend full regression: 518/518 موفق؛
- UI model/contract: 61/61 assertion شماره‌دار به‌علاوه observability contract موفق؛
- production build موفق؛ Warning اندازهٔ chunk در F-013 ثبت شده است؛
- Desktop Fake و viewport موبایل 390×844 بدون سرریز افقی؛ مقدار خصوصی پس از cancel پاک شد؛
- Runtime log redaction: 9106 رکورد، invalid JSON=0 و finding=0؛
- گزارش: `../reports/phases/PHASE11_0_MULTI_ACCOUNT_ONBOARDING_FOUNDATION_REPORT_2026-08-13.md`.

## فصل ۵ — مرحلهٔ 11-A: Discovery بله

- شناسایی روش رسمی/واقعی اتصال و محدودیت‌های حقوقی/فنی؛
- مستندسازی Login flow، Session persistence، rate/error model؛
- Capability matrix برای dialogs/messages/send/media/contacts/groups/channels؛
- ثبت موارد نامعلوم؛
- ممنوعیت حدس Endpoint، Token، Session format یا Capability.

خروجی این مرحله فقط Discovery report و قرارداد پذیرفته‌شده است؛ ورود واقعی انجام نمی‌شود.

وضعیت ۲۰۲۶-۰۸-۱۳: `COMPLETE / BLOCKED FOR PERSONAL CLIENT`. دو ZIP محلی و Aiobale به‌صورت ایستا بررسی شدند. شرایط رسمی بله APIهای غیررسمی/مهندسی معکوس را ممنوع کرده است؛ بنابراین هیچ transport شخصی پیاده‌سازی نشد. به‌روزرسانی 2026-09-27: این blockage با قرارداد متأخر مالک (فصل ۷ Discovery) و سپس تصمیم صریح F-085/ADR-60 منتفی شد؛ مسیر شخصی بله مجاز و در محصول فعال (کلاینت در شاخهٔ Bale با پذیرش زندهٔ V-194) است و بات بله به‌عنوان مسیر رسمی جداگانه در کنار آن scaffold شده است. مرجع: `BALE_PROVIDER_DISCOVERY.md`، F-086 و ADR-60.

## فصل ۶ — مرحلهٔ 11-B: Bale Adapter و Fake Contract

وضعیت زیرمرحلهٔ عمومی 11-B0 در 2026-08-13: `IMPLEMENTED / FAKE_VERIFIED`. قرارداد نسخه‌دار، authorization/state gate، DTOهای bounded، Registry، Worker factory، session Fake، observability و slot غیرفعال بله ساخته شدند؛ full regression 525/525 و UI/build پذیرفته شد. این زیرمرحله هیچ Bale transport یا Adapter عملیاتی ندارد و شرط ورود پایین را تغییر نمی‌دهد.

وضعیت زیرمرحلهٔ عمومی 11-B1 در 2026-08-13: `IMPLEMENTED / FAKE_VERIFIED`. Provider Registry پایدار، مهاجرت Coordinator v6 و Contact v3، Audit عمومی، worker/onboarding gate رجیستری‌محور، Fake Adapter سوم، Capability service حساب‌محور و guard مسیرهای provider-backed تکمیل شدند. full regression برابر 540/540 است. هیچ Bale transport، login/send واقعی یا migration روی پایگاه عملیاتی در این نوبت اجرا نشد.

وضعیت زیرمرحلهٔ 11-B2 slice 1 در 2026-08-20: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED`. orchestrator عمومی، routeهای v2 برای Dialog/History/Text Send، Eitaa compatibility adapter، Fake مشترک، DTO/protocolهای bounded رسانه/مخاطب، lifecycle log و UI capability fail-closed تکمیل شدند. Backend full regression برابر 554/554 است. حالت process برای عملیاتی که Child RPC ندارند عمداً fail-closed باقی مانده و ادعای Live نشده است.

وضعیت تکمیل محلی 11-B2 در 2026-08-20: `IMPLEMENTED / CONTRACT_FAKE_VERIFIED / NOT_LIVE`. routeهای Media/Contact فعال، Process Child RPC typed/fenced، media chunk broker بدون خروج مسیر، Coordinator schema v7 و receiptهای restart-safe برای Send/Contact تکمیل شدند. suite مستقل B2=`20/20` و full Backend=`561/561` است. هیچ Provider network یا ارسال واقعی استفاده نشد.

- پیاده‌سازی Adapter پشت Provider interfaces؛
- Fake transport و fixtureهای مستقل؛
- اجرای Contract Suite مشترک Eitaa/Bale؛
- Auth state machine، error mapping و capability declaration؛
- storage/process/log/audit مستقل؛
- بدون Login واقعی.

قید ورود به این مرحله: برای `Bale Personal` قرارداد رسمی/مجوز کتبی؛ یا انتخاب صریح `Bale Bot/Arm` به‌عنوان Provider/account kind جدا. ZIPهای غیررسمی به‌تنهایی شرط ورود را تأمین نمی‌کنند.

## فصل ۷ — مرحلهٔ 11-C: احراز هویت واقعی بله

- فقط پس از پذیرش Discovery و با اجازهٔ لحظه‌ای؛
- Credential فقط در UI؛
- ثبت فقط Metadata امن؛
- آزمون session restore/restart/logout روی حساب آزمایشی؛
- بدون ارسال واقعی مگر با تأیید جداگانه.

## فصل ۸ — مرحلهٔ 11-D: UI، Capability و Pilot

- نمایش Eitaa/Bale در Account switcher؛
- محدودکردن عملیات براساس Capability؛
- اثبات جداسازی دو AppUser، چند حساب Eitaa و چند حساب Bale؛
- rate/circuit مستقل؛
- Pilot محدود و گزارش نهایی Phase 11.

وضعیت جزئی 2026-08-20: محدودسازی UI براساس capability حساب‌محور، جداسازی account/provider، مسیرهای عمومی و persistence محلی با Fake/Contract انجام شده است. ورود و خواندن/همگام‌سازی حساب موجود ایتا Live accepted است. نمایش/Pilot واقعی Bale، rate/circuit واقعی آن و Pilot حساب دوم به مانع F-016/F-021 و ورودی مالک وابسته است.

## فصل ۹ — آماده‌سازی برای Provider سوم و بعدی

برای جلوگیری از بازنویسی بعدی:

- Provider باید داده/Registry باشد، نه Union و شرط پراکنده؛
- Schema باید Provider registry یا FK نسخه‌دار داشته باشد، نه CHECK ثابت دوتایی؛
- UI باید icon/label/capability/auth steps را از descriptor بگیرد؛
- Auth، Send، Dialog، Media، Contact و Group operation قرارداد مستقل داشته باشند؛
- Provider-specific DTO نباید از Adapter به UI عمومی نشت کند؛
- Errorهای خام Provider به taxonomy امن نگاشت شوند؛
- Contract Suite مشترک برای هر Adapter اجباری باشد؛
- storage namespace همیشه `provider + messenger_account_id` باشد.

## فصل ۱۰ — معیار «بدون بازنویسی»

افزودن Provider جدید باید فقط به این موارد نیاز داشته باشد:

1. Provider manifest/descriptor؛
2. Adapter و transport؛
3. Auth flow implementation؛
4. Capability declaration؛
5. Error/rate mapping؛
6. fixture و Contract tests؛
7. asset/label ترجمه‌شده.

نباید نیازمند تغییر منطق مالکیت AppUser، Coordinator job، Account isolation، Support Bundle، UI shell یا Security boundary باشد.

## فصل ۱۱ — ملاحظات Telegram و Providerهای نامعلوم

Telegram نمونهٔ خوبی از اهمیت Discovery است: Bot API با حساب کاربری/MTProto یک Provider contract یکسان نیست. پیش از هر طراحی باید نوع حساب، روش مجاز اتصال، نگهداری Session و محدودیت‌های سرویس مشخص شود. همین اصل برای Rubika و SoroushPlus نیز لازم‌الاجراست.

## فصل ۱۲ — مرز مرحلهٔ بعد پس از تکمیل محلی 11-B2

کار ایمن و محلی B2 تمام و ورود/read-sync حساب موجود ایتا پذیرفته شده است. ادامهٔ بخش‌های باقی‌ماندهٔ Phase 11 سه ورودی بیرونی دارد:

- Pilot حساب دوم Eitaa فقط با تأیید همان لحظه و ورود خصوصی مالک؛
- Bale Personal فقط پس از API رسمی یا اجازهٔ کتبی قابل ممیزی؛
- Bale Bot/Arm فقط پس از انتخاب صریح account kind، capability و دامنهٔ محصول.

تا دریافت یکی از این ورودی‌ها، Bale غیرفعال می‌ماند، 11-C آغاز نمی‌شود و 11-D فقط برای حساب موجود در سطح read/live-sync پذیرفته است. اعمال migration روی DB عملیاتی و هر Login حساب تازه/Send/Pilot فعالیت کنترل‌شدهٔ جدا است و از موفقیت Contract/Fake یا read فعلی استنتاج نمی‌شود.

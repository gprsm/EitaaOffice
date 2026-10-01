# راهنمای توسعهٔ Provider Adapter مجاز

آخرین بازبینی: 2026-09-28

وضعیت قرارداد: `API v1 / additive Contact contract v2 / Bale CONTRACT_VERIFIED`
دامنه: افزودن پیام‌رسان یا نوع حساب تازه بدون بازنویسی مالکیت، UI shell، Coordinator و مرزهای امنیتی

## ۱. هدف و مرز

این راهنما مسیر رسمی قرار دادن کد یک Provider در Eitaa Bridge را تعریف می‌کند. زیرساخت حاضر عمداً transport، endpoint، codec، کلید برنامه، Token، Cookie یا الگوریتم ورود هیچ سرویس تازه‌ای را حدس نمی‌زند. کد عملیاتی تنها هنگامی وارد مسیر runtime می‌شود که یکی از مبانی زیر ثبت شده باشد:

1. API رسمی و مستند Provider؛
2. قرارداد سازمانی یا اجازهٔ کتبی قابل ارجاع؛
3. integration موجودی که قبلاً به‌طور مستقل پذیرفته شده است؛
4. `test_only` فقط برای Fake آفلاین و بدون شبکه.

مجوز متن‌باز یک client به‌تنهایی مجوز استفاده از سرویس Provider نیست. هر account kind نیز قرارداد جدا دارد؛ برای نمونه Bot API نباید به‌عنوان حساب شخصی معرفی شود.

## ۲. نقشهٔ فایل‌ها

| مسیر | مسئولیت |
|---|---|
| `src/eitaa_bridge/providers/contracts.py` | قرارداد نسخه‌دار، Manifest، Capability، DTOهای محدود، Adapter/Worker protocol و Registry |
| `src/eitaa_bridge/providers/registry.py` | composition root و allowlist صریح Providerهای built-in |
| `src/eitaa_bridge/providers/testing.py` | contract probe آفلاین و session store ساختگی حساب‌محور |
| `src/eitaa_bridge/providers/<provider>/` | پیاده‌سازی اختصاصی Provider؛ transport و mapping نباید از این مرز نشت کند |
| `src/eitaa_bridge/providers/bale/slot.py` | registration مجاز شخصی بله و factory آداپتور/worker؛ contract_verified |
| `src/eitaa_bridge/application/provider_adapter.py` | facade سازگاری برای مصرف‌کننده‌های فعلی catalog |
| `src/eitaa_bridge/application/provider_orchestration.py` | مسیر application عمومی، ترتیب guardها، deadline، idempotency و result/error mapping |
| `src/eitaa_bridge/providers/eitaa/application_adapter.py` | compatibility port ایتا؛ نمونهٔ قرارگیری translation در package Provider |
| `src/eitaa_bridge/interfaces/provider_worker.py` | entrypoint فرایند مستقل هر MessengerAccount بر مبنای Registry |
| `src/eitaa_bridge/infrastructure/worker_ipc/` | envelope، secret bootstrap و taxonomy امن خطا |
| `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py` | رخدادهای canonical و الزام audit |
| `tests/test_phase11b_provider_extension_foundation.py` | تست قرارداد، fail-closed، isolation و scan ایستا |
| `tests/test_phase11b2_provider_neutral_orchestration.py` | تست مشترک Eitaa/Fake، جداسازی، capability ceiling، race/idempotency و log safety |

## ۳. چرخهٔ عمر اجباری

```text
scaffold
  -> implemented
  -> contract_verified
  -> live_accepted
```

- `scaffold`: فقط نام، نوع حساب و دلیل غیرفعال‌بودن؛ `configured/runtime/onboarding=false`.
- `implemented`: کد موجود است، اما runtime هنوز مجاز نیست.
- `contract_verified`: مجوز ثبت شده و Fake/Contract/Adversarial سبز شده‌اند؛ runtime می‌تواند با پیکربندی صریح فعال شود.
- `live_accepted`: Pilot واقعی کنترل‌شده و گزارش مستقل پذیرفته شده است.

سه پرچم `configured`، `runtime_enabled` و `onboarding_enabled` مستقل ولی fail-closed هستند. Manifest اجازه نمی‌دهد scaffold یا Provider بدون مبنای مجوز configured شود، یا implementation آزمایش‌نشده runtime را فعال کند.

## ۴. قرارداد عمومی Adapter

`ProviderAdapter` فقط این دسته عملیات typed را می‌پذیرد:

- challenge و second-factor به‌صورت state محدود و محرمانه؛
- اعتبارسنجی session sealed؛
- فهرست گفتگو و history صفحه‌بندی‌شده؛
- ارسال متن با idempotency key؛
- خواندن رسانه با reference محدود، variant معین و byte limit؛
- فهرست/افزودن مخاطب با DTO محدود و identity محرمانه؛
- shutdown صریح.

مرز عمومی عمداً raw RPC، raw request/response، object داخلی SDK، مسیر فایل انتخاب‌شده توسط client، Cookie، access token و Session object ندارد. Provider-specific exception باید داخل adapter به `ProviderExtensionError` و reason code امن نگاشت شود.

هر عملیات `ProviderOperationContext` دارد که شامل account scope، correlation و deadline کران‌دار است. پاسخ‌ها نیز سقف اندازه دارند تا یک Provider نتواند حافظه یا IPC را با page نامحدود اشغال کند.

### ۴.۱. ترتیب application orchestration

Adapter تا پس از این ترتیب resolve نمی‌شود:

```text
authenticated AppUser
-> active Membership/account scope
-> server-owned ProviderAccountContext
-> account capability decision
-> live bounded deadline
-> allowlisted adapter factory
-> manifest capability ceiling
-> bounded operation/result
-> safe event/error mapping
```

- body/query نمی‌تواند `messenger_account_id`، Provider یا Capability مؤثر بسازد؛ account id از route معتبر و context از Coordinator می‌آید.
- cache نتیجهٔ idempotency قبل از authorization/capability قابل بازگشت نیست. duplicate درحال‌اجرا رد و `uncertain` بدون retry خودکار terminal است.
- اگر Provider در Child process است، عملیات باید RPC typed/bounded/fenced داشته باشد. دسترسی Parent به object یا mutable state داخل Child جایگزین RPC نمی‌شود.
- vertical slice نیمه‌کاره route قدیمی را جایگزین نمی‌کند. route عمومی جدید باید از ابتدا تا پایان Contract/Fake و fail-closed باشد.

## ۵. Session، Secret و جداسازی حساب

- کلید مالکیت runtime برابر `provider + messenger_account_id + session_generation` است.
- هر Worker فقط یک MessengerAccount را مالک می‌شود.
- secret فقط با `SensitiveProviderValue` از مرز داخلی عبور می‌کند؛ `repr` و `str` آن redacted است.
- `InMemoryProviderSessionStore` فقط Fake تستی است و برای production مجاز نیست.
- production store باید session را sealed/encrypted، حساب‌محور و قابل archive نگه دارد؛ نام فایل یا مسیر واقعی نباید از UI دریافت شود.
- شمارهٔ کامل، OTP، رمز، Token، Cookie، challenge payload، session bytes، raw provider response و مسیر خصوصی در log/audit/report ممنوع‌اند.
- context حساب همیشه سمت سرور و پس از Membership ساخته می‌شود؛ شناسهٔ ارسالی client به‌تنهایی اختیار ایجاد نمی‌کند.

## ۶. مراحل افزودن یک Provider یا account kind

### ۶.۱. ورودی‌های لازم

پیش از کدنویسی، یک بستهٔ provenance آماده شود:

- نام و نسخهٔ مستند رسمی یا شناسهٔ اجازهٔ کتبی؛
- account kind دقیق: `personal`، `bot` یا `service`؛
- auth stages واقعی و نوع هویت؛
- capabilityهای مستند، rate limit، timeout و retry semantics؛
- قالب session و سیاست revoke/logout؛
- محدودیت‌های نگهداری داده و شرایط سرویس؛
- روش sandbox/test رسمی، اگر وجود دارد.

هیچ credential واقعی داخل این بسته یا مستندات پروژه قرار نمی‌گیرد.

### ۶.۲. ایجاد package

در `src/eitaa_bridge/providers/<provider>/` ماژول‌های زیر ایجاد شوند:

```text
<provider>/
├── __init__.py       export registration
├── manifest.py       فقط metadata و capabilityهای مستند
├── adapter.py        ترجمهٔ SDK رسمی به ProviderAdapter
├── errors.py         نگاشت خطا به taxonomy امن
└── worker.py         مالک transport/session همان حساب
```

اگر SDK رسمی جداگانه وجود دارد، dependency باید pin و provenance آن ثبت شود. کد خارجی بدون بررسی license، dependency، secret handling و test evidence مستقیم در `vendor/` یا source کپی نمی‌شود.

### ۶.۳. Manifest

Manifest حداقل باید provider id، display name، account kind، implementation state، authorization basis/reference، identity kind، auth stages و capabilities را اعلام کند. reference فقط نشانی HTTPS سند رسمی یا شناسهٔ سند داخلی است و endpoint عملیاتی محسوب نمی‌شود.

### ۶.۴. Registry

registration به‌صورت صریح در `default_provider_registry()` افزوده می‌شود. import پویا، plugin discovery از filesystem، `eval/exec` یا بارگذاری module با نام دریافتی client ممنوع است. این تصمیم سطح حمله و supply-chain را محدود می‌کند.

در Phase 11-B1، `persistence_catalog()` metadata امن registration را برای Coordinator و Contact Store تولید می‌کند. Provider تستی فقط با `include_test=True` وارد پایگاه موقت تست می‌شود. startup محصول registrationهای قابل‌استفادهٔ build را افزایشی reconcile می‌کند و رکورد تاریخی را خودکار حذف نمی‌کند.

هیچ migration تازه‌ای نباید دوباره `CHECK(provider IN (...))` بسازد. جدول‌های وابسته باید به `provider_registrations(provider)` ارجاع دهند و trigger تطابق Provider با MessengerAccount را حفظ کنند.

### ۶.۵. Capability حساب‌محور

- Manifest فهرست حداکثر Capabilityهای Provider است.
- observation حساب می‌تواند وضعیت را محدود کند ولی Capability خارج از Manifest را فعال نمی‌کند.
- هر عملیات عمومی تازه باید در `provider_capability_for_route` یا service orchestration متناظر نگاشت شود.
- endpoint حساب‌محور Capability فقط metadata امن و revision را منتشر می‌کند؛ constraint خام، endpoint، token و session ممنوع‌اند.
- تغییر Capability نیازمند migration داده نیست، اما reconciliation، contract test، route guard و UI behavior باید هم‌زمان بازبینی شوند.

### ۶.۵. تست قبل از runtime

حداقل ماتریس پذیرش:

1. Manifest authorization/state gating؛
2. contract shape و نبود memberهای خام/حساس؛
3. Fake auth، dialogs، history، send و close؛
4. دو AppUser و حداقل دو MessengerAccount از همان Provider؛
5. منع cross-account session/data access؛
6. duplicate/race/idempotency/replay/deadline؛
7. timeout، retry-after، circuit و uncertain send؛
8. malformed/oversized provider response؛
9. secret/PII scan لاگ، audit و support bundle؛
10. restart/crash/shutdown و عدم orphan Worker؛
11. UI desktop/mobile از descriptor و capability؛
12. regression کامل Python و UI.

Contract/Fake هیچ endpoint واقعی را فراخوانی نمی‌کند. Live pilot مرحله‌ای جداست و به تأیید همان لحظه نیاز دارد.

## ۷. Observability اجباری

فعال‌سازی Provider از چهار رخداد canonical استفاده می‌کند:

- `provider_adapter_activation_started`
- `provider_adapter_activation_succeeded` با audit
- `provider_adapter_activation_rejected` با audit
- `provider_adapter_activation_failed`

فیلدهای مجاز شامل provider id، account id سرورساز، implementation state، safe reason code و correlation هستند. exception خام SDK یا payload Provider ثبت نمی‌شود. رخدادهای عملیاتی تازه باید ابتدا به Event Catalog افزوده و با تست redaction پوشش داده شوند.

Phase 11-B2 هشت رخداد application operation دارد: `provider_operation_started/succeeded/rejected/failed/uncertain/idempotency_replayed/idempotency_interrupted/adapter_close_failed`. این رخدادها فقط provider، messenger account id سرورساز، operation، capability، correlation، reason code، outcome/source امن، error type و duration را می‌پذیرند؛ متن پیام، هویت مخاطب، idempotency key، fingerprint و exception message ثبت نمی‌شوند.

Mutationهای `messages.send_text` و `contacts.upsert` باید پیش از اثر بیرونی یک claim پایدار account-scoped بسازند. کلید به actor و fingerprint payload bind است؛ payload خام در receipt ذخیره نمی‌شود. replay terminal پس از restart نباید Provider را دوباره فراخوانی کند و claim منقضی‌شده باید بدون retry به `uncertain` تبدیل شود. در Process Runtime فقط RPC typed/allowlisted مجاز است و media cache path باید در Child مالک باقی بماند.

## ۸. وضعیت جایگاه بله

حالت scaffold تاریخی این بخش با F-086/ADR-60 و اجرای محصولی 2026-09-28 superseded است. `bale` اکنون registration مجاز حساب شخصی است:

- account kind برابر `personal` و state برابر `contract_verified` است؛
- configured/runtime/onboarding همگی true و factoryهای adapter/worker متصل‌اند؛
- runtime هر حساب loop، vault، کلید و لاگ مستقل دارد؛ process و in-process هر دو آزموده‌اند؛
- auth، contacts، dialogs/history، text/media و polling در API/UI اصلی متصل‌اند؛
- حذف مخاطب در `ProviderContactRemovalAdapter` قرارداد افزایشی v2 است؛ ارسال رسانه protocol اختیاری مستقل دارد. extension API v1 سازگار باقی مانده و schema 10 receiptهای تازه را با حفظ migrationهای تاریخی می‌پذیرد؛
- درخواست رمز دومرحله‌ای در IPC با `credential`، و محتوای فایل با `content_handle` منتقل می‌شود؛ فیلتر عمومی secret/session خام ضعیف نشده است؛
- گروه/کانال در عملیات فقط‌خصوصی خطای صریح می‌گیرند؛ رسانه حداکثر 512 KiB، و receive با polling پنج‌ثانیه‌ای است؛
- contract verification معادل پذیرش Live یا مرورگر نیست؛ وضعیت باز در گزارش BALE-PRODUCT و V-230 ثبت شده است.

Bot/Arm مستقل و غیرثبت‌شده باقی است؛ capability حساب شخصی به آن منتقل نمی‌شود. مبنای اجازهٔ مسیر شخصی F-086 است.

## ۹. چک‌لیست تحویل کد دستی آینده

هنگامی که مالک پروژه کد خود یا مستند رسمی را ارائه کرد:

- [ ] provenance و حق استفاده ثبت شده است؛
- [ ] account kind با محصول رسمی تطبیق دارد؛
- [ ] هیچ secret یا دادهٔ واقعی داخل source/fixture نیست؛
- [ ] transport فقط داخل package Provider است؛
- [ ] public DTO و error taxonomy رعایت شده است؛
- [ ] registration صریح و بدون loader پویا است؛
- [ ] Fake/Contract/Adversarial کامل سبز است؛
- [ ] schema hard-codeهای باقی‌مانده با migration سازگار رفع شده‌اند؛
- [ ] لاگ، audit، support bundle و PII scan پذیرفته شده‌اند؛
- [ ] live login/send فقط با تأیید همان لحظه انجام می‌شود؛
- [ ] گزارش مستقل discovery، implementation، live pilot و rollback نوشته شده است.

## ۱۰. Trigger بازبینی

با تغییر هرکدام از `contracts.py`، `registry.py`، Worker IPC، session store، Event Catalog، account schema، onboarding UI یا شرایط رسمی Provider، این راهنما و آزمون‌های Phase 11-B باید بازبینی شوند. تا قبل از این triggerها، برای پرسش‌های معماری Provider ابتدا به همین سند و حافظهٔ پروژه رجوع شود و ممیزی کامل source بی‌دلیل تکرار نشود.

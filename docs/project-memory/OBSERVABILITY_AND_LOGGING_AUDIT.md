# ممیزی لاگ‌گذاری، Audit و Observability

تاریخ ممیزی اولیه: ۲۰۲۶-۰۸-۱۳  
آخرین همسان‌سازی: ۲۰۲۶-۰۸-۲۶ / G-09  
وضعیت کلی: `FOUNDATION_AND_LOCAL_OPERATIONS_AUTOMATED_ACCEPTED / WEB_METRICS_DEFERRED`  
دامنه: آزمون‌های آفلاین/مصنوعی و قراردادهای current program؛ بدون اسکن تازهٔ Live یا مشاهدهٔ مقادیر خصوصی

## فصل ۱ — پاسخ صریح

برای دامنهٔ فعلی برنامه، رخدادهای مادی Backend/Worker/Account/Audit/Renderer/Electron و background lifecycle با قرارداد ساختاریافته و آزمون خودکار پوشش دارند. این نتیجه تضمین «همهٔ رخدادهای آینده» یا Web production metrics نیست؛ OBS-008 آگاهانه deferred است و تغییر هر مرز Trigger بازبینی دارد.

همچنین «ثبت هر اتفاق» باید به معنی ثبت هر رخداد **مادی و قابل پشتیبانی** باشد. ثبت متن پیام، Payload، شمارهٔ کامل، Credential، هر کلیک UI یا هر retry کم‌اهمیت هم خطر نشت اطلاعات دارد و هم لاگ را غیرقابل استفاده می‌کند.

## فصل ۲ — امکانات موجود و پذیرفته‌شده

### ۲.۱. RuntimeLogger

- JSONL ساختاریافته با زمان UTC، Event، Level، Thread و Fields؛
- چرخش فایل با سقف ۵ MiB و پنج نسخهٔ پشتیبان؛
- Request/Correlation ID مبتنی بر Context؛
- Context ثابت Provider و MessengerAccount برای Worker log؛
- مسیر Application: `runtime/logs/application.jsonl`؛
- مسیر هر حساب: `runtime/accounts/<account-id>/logs/worker.jsonl`.

### ۲.۲. Redaction

- Secretها مانند Token، Cookie، Authorization، Password، OTP، CSRF و Session redact می‌شوند؛
- شماره‌ها mask می‌شوند؛
- متن پیام، Body، Caption، Content و Bytes ذخیره نمی‌شوند و فقط summary/hash امن می‌ماند؛
- Path فقط به‌صورت summary محدود ثبت می‌شود؛
- تست‌های عدم نشت برای AppUser، Auth، WordPress، حساب‌ها و LAN وجود دارند.

### ۲.۳. API request logging

Dispatcher برای هر درخواست API موارد زیر را ثبت می‌کند:

- method و path امن بدون Query؛
- status؛
- duration؛
- error code امن؛
- AppUser و MessengerAccount مجاز؛
- سطح `info/warning/error` بر پایهٔ status.

Exceptionهای عبوری از Dispatcher به پاسخ امن تبدیل و در سطح request ثبت می‌شوند.

### ۲.۴. Diagnostics

`BridgeDiagnosticManager` فایل‌های JSONL جزءبه‌جزء و Run-scoped تولید می‌کند، Manifest امنیتی دارد و Diagnosticهای قدیمی را محافظه‌کارانه پاک می‌کند.

### ۲.۵. Audit

- Audit Coordinator برای رخدادهای امنیتی/مالکیتی/عملیاتی؛
- Audit مستقل مخاطبان؛
- append-only و hash chain؛
- Query/Export مجوزدار؛
- Metadata امن و redaction ثانویه؛
- Correlation برای Job/Lease/Attempt/Retry؛
- آزمون tamper و stress پذیرفته شده است.

### ۲.۶. Desktop و Support

- Electron رخدادهای اصلی شروع/خروج API و recovery را در `desktop.log` ثبت می‌کند؛
- stdout/stderr Backend در `api.log` نگهداری می‌شود؛
- Support Bundle فقط فایل‌های مجاز و tailهای redactشده را جمع می‌کند؛
- Scanner محتوای Session، `.env`، SQLite، media، Secret، شمارهٔ کامل، IP و مسیر شخصی را fail-closed رد می‌کند؛
- اسکن Phase 10-D برای لاگ‌های زنده `invalid_json=0` و `finding_count=0` ثبت کرده است.

## فصل ۳ — شکاف‌های ثبت‌شده

### OBS-001 — نبود Error Boundary و ثبت سراسری خطاهای Renderer

- شدت: بالا
- وضعیت: `CLOSED / AUTOMATED_VERIFIED`
- شاهد: در UI handler سراسری `window.onerror`، `unhandledrejection` یا React Error Boundary ثبت‌کننده پیدا نشد.
- اثر: Crash یا Promise rejection رابط ممکن است فقط به کاربر نمایش داده شود یا کاملاً گم شود.
- اقدام: Error Boundary در Root، handler امن برای unhandled errors و Endpoint محدود ثبت Client diagnostic.

### OBS-002 — Electron log ساختاریافته و Correlated نیست

- شدت: بالا
- وضعیت: `CLOSED / AUTOMATED_VERIFIED`
- شاهد: `desktop.log` متن ساده است و schema/version/level/correlation/account ندارد.
- اثر: اتصال رخداد Desktop به API/Worker/Audit دشوار است.
- اقدام: استفاده از JSONL مشترک یا DesktopLogger سازگار با Event Contract.

### OBS-003 — ثبت raw targetPath در خطای Electron

- شدت: بالا از دید Privacy hardening
- وضعیت: `CLOSED / AUTOMATED_VERIFIED`
- شاهد: مسیر درخواست ناموفق مستقیماً در `desktop.log` نوشته می‌شود، در حالی که Backend Query را حذف می‌کند.
- اثر: اگر Route آینده Query حساس داشته باشد، احتمال ثبت ناخواسته وجود دارد.
- اقدام: ثبت فقط pathname allowlisted و حذف کامل Query/Fragment پیش از log و response safe_context.

### OBS-004 — نبود Event Catalog و تضمین پوشش

- شدت: بالا
- وضعیت: `CLOSED / CURRENT_PROGRAM_SCOPE_VERIFIED`
- شاهد: Eventها با فراخوانی‌های پراکندهٔ `emit` و `_append_audit` تعریف شده‌اند و Catalog نسخه‌دار مرکزی وجود ندارد.
- اثر: توسعهٔ جدید می‌تواند Error/Warning مهم را بدون Log یا با فیلد ناسازگار اضافه کند.
- اقدام: Event registry، schema و تست coverage برای مرزهای مهم.

### OBS-005 — تفاوت کانال‌های Application/Worker/Desktop/API stderr

- شدت: متوسط
- وضعیت: `CLOSED / STRUCTURED_CHANNELS_VERIFIED`
- اثر: Support و جست‌وجوی رخداد میان چهار قالب متفاوت سخت است.
- اقدام: قالب مشترک، فهرست Source ثابت و correlation propagation.

### OBS-006 — پوشش Background taskها تضمین مرکزی ندارد

- شدت: متوسط
- وضعیت: `CLOSED / CURRENT_PROGRAM_SCOPE_VERIFIED`
- شرح: بسیاری از Jobها و supervisorها log/audit دارند، اما wrapper اجباری برای همهٔ background taskهای فعلی و آینده وجود ندارد.
- اقدام: executor/wrapper مشترک با events استاندارد `started/succeeded/failed/cancelled/uncertain`.

### OBS-007 — سیاست Retention و Log health کامل نیست

- شدت: متوسط
- وضعیت: `CLOSED / LOCAL_SYNTHETIC_OPERATIONS_VERIFIED`
- شرح: Runtime rotation و Diagnostics pruning وجود دارد، ولی retention یکپارچه برای Desktop/API/Audit/Export و شاخص failure نوشتن لاگ تعریف نشده است.
- اقدام: قرارداد retention، disk budget، write-failure counter و health summary امن.

### OBS-008 — مشاهده‌پذیری عملیاتی Web هنوز Metrics/Alert ندارد

- شدت: متوسط و وابسته به استقرار
- وضعیت: `DEFERRED`
- شرح: برای Desktop محلی blocker نیست؛ برای Web production باید نرخ خطا، latency، queue depth، circuit و worker restart قابل پایش باشند.
- اقدام: metrics exporter اختیاری و بدون دادهٔ خصوصی در فاز Release/Web.

## فصل ۴ — قرارداد پیشنهادی Event

هر رخداد ساختاریافته باید حداقل این فیلدها را داشته باشد:

```text
schema_version
at
source
event
level
result
reason_code
correlation_id
app_user_id?              (opaque)
messenger_account_id?     (opaque)
provider?
operation?
duration_ms?
safe_fields
```

قواعد:

- `event` از Catalog انتخاب می‌شود؛
- Error و Warning مادی بدون `reason_code` ممنوع است؛
- Exception type امن است، Exception message خام به‌صورت پیش‌فرض ممنوع است؛
- Payload، Query خام، Header، Credential و متن خصوصی ممنوع است؛
- رخداد دارای اثر بیرونی باید Audit نیز داشته باشد؛
- رخداد عملکردی پرتکرار باید sampling یا aggregation داشته باشد؛
- هر Provider از همان envelope استفاده می‌کند.

## فصل ۵ — مسیر اجرای Observability

### O-1: Contract و Catalog

- ایجاد schema و Event Catalog؛
- Adapter برای RuntimeLogger، Audit و Diagnostics؛
- تعریف Level/Result/Reason taxonomy؛
- تست schema و redaction.

### O-2: Backend و Worker coverage

- wrapper مشترک request/background/provider operation؛
- پوشش startup/shutdown/crash/retry/circuit/rate/auth؛
- تست failure injection و correlation end-to-end.

### O-3: Electron و React

- Desktop JSONL؛
- sanitization مسیر؛
- Error Boundary و unhandled rejection؛
- Endpoint امن و rate-limited برای client diagnostics؛
- جلوگیری از ثبت state و DOM خصوصی.

### O-4: Operations

- retention و disk budget؛
- health summary؛
- Support Bundle نسخه‌دار؛
- metrics اختیاری Web؛
- runbook تشخیص خطا بر پایهٔ correlation.

## فصل ۶ — معیار پذیرش

- همهٔ Error/Warningهای تزریق‌شده در مرزهای تعریف‌شده Event استاندارد تولید کنند؛
- یک correlation از UI/Electron تا API/Worker/Audit قابل دنبال‌کردن باشد؛
- Secret/PII adversarial scan برابر صفر باشد؛
- خاموشی یا خرابی logger باعث افشای داده یا توقف عملیات اصلی نشود و health امن آن را گزارش کند؛
- تست ثابت کند حساب A نمی‌تواند log خصوصی حساب B را ببیند؛
- Support Bundle فقط دادهٔ امن و محدود داشته باشد.

## فصل ۷ — به‌روزرسانی اجرایی 2026-08-13

این فصل وضعیت‌های فصل ۳ را پس از پیاده‌سازی supersede می‌کند:

| شناسه | وضعیت جدید | شاهد |
|---|---|---|
| OBS-001 | `CLOSED / AUTOMATED_VERIFIED` | React Error Boundary، global error/rejection handlers و client diagnostic امن |
| OBS-002 | `CLOSED / AUTOMATED_VERIFIED` | Desktop JSONL با schema نسخهٔ 1 و correlation |
| OBS-003 | `CLOSED / AUTOMATED_VERIFIED` | حذف query/fragment و خلاصه‌سازی شناسه‌های route در Electron |
| OBS-004 | `CLOSED / FOUNDATION_VERIFIED` | Event Catalog مرکزی، endpoint contract و تست schema/redaction |
| OBS-005 | `PARTIAL` | Application/Worker/Desktop/Renderer envelope مشترک دارند؛ `api.log` خام process channel جدا باقی مانده است |
| OBS-006 | `PARTIAL` | `observed_operation` ایجاد و تست شد؛ migration همهٔ background pathهای legacy تدریجی است |
| OBS-007 | `OPEN` | rotation موجود است؛ retention/disk-health یکپارچه هنوز تکمیل نیست |

## فصل ۸ — افزودهٔ Observability در Phase 11-0

- Event Catalog از ۶۸ به ۷۲ رخداد افزایش یافت و lifecycle ساخت حساب شامل `started/succeeded/reused/rejected` شد.
- هر چهار رخداد account-onboarding دارای correlation و `audit_required=true` هستند.
- تغییر مالکیت created/reused و رد cross-owner در Audit زنجیره‌دار ثبت می‌شوند؛ رکورد ردشده شناسهٔ PhoneAccount/MessengerAccount ندارد.
- Payload ورودی، شمارهٔ کامل، fingerprint، ciphertext، Credential و مسیرها وارد Log/Audit نمی‌شوند.
- اسکن ۹۱۰۶ رکورد Runtime برابر finding=0 و invalid JSON=0 بود.
- پذیرش دیداری یک Warning MUI مستقل را کشف کرد؛ پس از اصلاح، تب تازهٔ Development صفر error/warning داشت.
- Trigger تکرار: تغییر eventهای onboarding، safe metadata، PhoneProtector، API payload یا Audit write.
| OBS-008 | `DEFERRED` | metrics/alert برای استقرار واقعی Web، بدون PII |

وضعیت کل: `OBSERVABILITY FOUNDATION IMPLEMENTED؛ OPERATIONS MATURITY PARTIAL`.

مرجع قرارداد جاری: `../LOGGING_AND_OBSERVABILITY.md`.  
گزارش پیاده‌سازی و آزمون: `../reports/features/OBSERVABILITY_FOUNDATION_REPORT_2026-08-13.md`.

## فصل ۹ — افزودهٔ Observability در Phase 11-B1

- Event Catalog از 76 به 78 رخداد رسید.
- `provider_registry_reconciled` فقط شمار registrationهای created/updated/unchanged و provider_count را ثبت می‌کند.
- `provider_capability_check_rejected` فقط account id سرورساز، Capability و reason code امن را ثبت می‌کند.
- Coordinator reconciliation علاوه بر Runtime event، Audit زنجیره‌دار `provider_registration.created/updated` دارد.
- Audit provider filter از allowlist دوتایی به syntax عمومی + وجود registration منتقل شد.
- اسکن 9106 رکورد Runtime همچنان finding=0 و invalid JSON=0 است.
- هیچ exception خام Adapter، constraint، endpoint، credential، session یا provider subject وارد رخدادهای B1 نمی‌شود.
- Trigger تکرار: تغییر Registry reconciliation، Capability service/route guard، Event Catalog، Audit filter یا safe fields.

وضعیت عملیات retention/disk health و Web metrics بدون تغییر `PARTIAL/DEFERRED` باقی است.

## فصل ۱۰ — پذیرش خصمانهٔ مرز حریم خصوصی در G-04-D

- پنج کانال/کنترل مستقل با یک هویت canonical و Bearer کاملاً ساختگی آزموده شدند: Runtime Log، Diagnostic، Audit persistence/query/export، Support Bundle creator و Support Bundle scanner.
- RED اولیه `5/5 failed` بود. علت مشترک، اتکای redaction به کلیدهای شناخته‌شده و محدودبودن الگوی bundle/scanner به شمارهٔ ایران بود؛ Audit نیز metadata ناشناخته را پیش از persistence pattern-scan نمی‌کرد.
- اصلاح مشترک، pattern-scan متن ناشناخته و تو‌در‌تو برای E.164 جهانی/Bearer/provider-token، redaction پیش از Audit hash/persistence و دفاع دوباره در query/export را اضافه کرد. creator و scanner اکنون یک دامنهٔ global phone همسو دارند.
- GREEN اختصاصی=`5/5`؛ regressionهای مرتبط=`53/53`، `2/2` و `50/50`. Audit chain، AppAuth/AccountAuth، Registry/onboarding، diagnostics/observability و هر دو Support Bundle پوشش داده شدند.
- هیچ diagnostics/runtime/config/session واقعی خوانده نشد؛ همهٔ ورودی‌ها و فایل‌ها زیر basetemp مصنوعی بودند. اسکن Live یا ادعای release readiness انجام نشد.
- Trigger تکرار: تغییر redaction pattern/key contract، RuntimeLogger، Diagnostic manager، Audit append/query/export، bundle creator/scanner یا افزودن identity kind تازه.

وضعیت privacy چهارکاناله: `ADVERSARIAL_GREEN / SYNTHETIC_OFFLINE`. وضعیت کلی operations به‌علت retention/disk health و Web metrics همچنان `PARTIAL/DEFERRED` است.

## فصل ۱۱ — closure نهایی G-04-E

- هش‌های مسیرهای identity/redaction/Audit/bundle و آزمون‌های A تا D با V-119/V-120 تطبیق کامل داشتند؛ drift مشاهده نشد.
- full Backend نخست `618/620` بود و دو timeout Process Worker داشت. همان دو node بدون patch در isolation=`2/2` و full rerun با basetemp تازه=`620/620` سبز شدند؛ رخداد نخست به ازدحام زمانی full-suite طبقه‌بندی و در V-121 حفظ شد.
- TypeScript و UI/Electron Observability exit code صفر و UI Phase 11 onboarding=`7/7` است.
- F-044 و G-04 در سطح `OFFLINE_AUTOMATED_ACCEPTED` بسته‌اند. این نتیجه اسکن Live، مجوز Provider/OTP/Send یا بلوغ retention/disk health/Web metrics ایجاد نمی‌کند.
- Trigger تکرار: تغییر قرارداد نمایش identity، validator/API onboarding، redaction، Audit persistence/query/export، Support Bundle creator/scanner یا هر identity kind تازه.

## فصل ۱۲ — safe-default و closure ایندکس خودکار در G-05

- RED اولیه سه نقص را مستقل ثابت کرد: thread پس از close زنده، نبود event و loop نامحدود با exception swallowing؛ manual index PASS بود.
- scheduler ناقص حذف و event `content_auto_index_scheduler_skipped` با result/reason/correlation و fields محدود catalog شد. هیچ account id، target، label، پیام یا payload در event نیست.
- سه start/close متوالی orphan thread=`0` و correlation یکتا=`3/3` داشتند. مرتبط=`76/76`، adversarial/observability=`11/11`، broad=`143/143` و full Backend=`625/625` سبزند.
- F-043 در سطح `OFFLINE_AUTOMATED_ACCEPTED` بسته است. فعال‌سازی آیندهٔ scheduler Trigger بازگشایی و نیازمند feature/config، stop/join، account isolation و failure events مستقل است.

## فصل ۱۳ — ممیزی عملیاتی و RED در G-08-A

- scanner Phase 10 یک account id ثابت و فقط دو log ثابت داشت؛ rotation و حساب‌های دیگر خارج می‌ماندند.
- RuntimeLogger فاقد write-failure counter/health بود و خطای handler مصنوعی را به عملیات اصلی منتشر کرد.
- retention موجود فقط diagnostic run directoryها را می‌پوشاند و policy محدود rotation/disk-health امن وجود ندارد.
- چهار قرارداد کاملاً مصنوعی در اجرای canonical برابر `4/4 failed` شدند؛ این RED به F-048 متصل است.
- Event Catalog جاری و coverage literal موجود در G-08-C برای background/bootstrap/lifecycle عمیق‌تر ممیزی می‌شود. OBS-008 Web metrics همچنان deployment-dependent و `DEFERRED` است.
- هیچ log/config/account/runtime واقعی خوانده یا تغییر داده نشد.

## فصل ۱۴ — اسکنر چندحسابی G-08-B

- account id و مسیرهای ثابت حذف و discovery به application و همهٔ account scopeهای مستقیم با rotation عددی محدود شد.
- report فقط scope ترتیبی، channel/rotation و شمار عددی دارد؛ path، account id، کلید ناشناخته و value یافته ثبت نمی‌شوند.
- JSON/UTF-8 خراب، current مفقود، read failure و symlink fail-closed هستند.
- targeted=`2/2` و regression مرتبط=`18/18` سبز است؛ هیچ log واقعی اسکن نشد.
- OBS-006/007 و F-048 تا تکمیل C/D/E بازند.

## فصل ۱۵ — lifecycle و background coverage در G-08-C

- generic background اکنون `operation_started/succeeded/failed` متوازن با correlation انتقال‌یافته دارد و failure اختصاصی آن حفظ است.
- content-index دستی started/succeeded/cancelled/failed/cleanup-failed و read-receipt best-effort failure صریح دارند.
- unexpected lease-renew، runtime startup پس از logger، shutdown موفق/ناموفق و auth-runtime close failure فقط type/reason امن ثبت می‌کنند.
- Catalog از 92 به 102 رسید؛ RED=`4/4`، GREEN=`4/4` و related=`98/98`.
- OBS-006 برای مسیرهای اصلاح‌شدهٔ این برنامه `CLOSED / PROGRAM_SCOPE_VERIFIED` است؛ legacy future paths همچنان باید از wrapper مشترک استفاده کنند. OBS-007 تا D باز است و OBS-008 deferred باقی می‌ماند.

## فصل ۱۶ — operations health و Support Bundle در G-08-D

- RuntimeLogger خطای مستقیم و internal `handleError` را بدون چاپ record مهار و شمارش می‌کند؛ endpoint health فقط status/count/type و disk/policy عددی دارد.
- retention فقط current/rotation عددی Application/Worker را می‌شناسد، symlink را رد و current را همیشه حفظ می‌کند؛ age/count/total budget محدود است.
- Support Bundle، JSONL ناقص را به marker aggregate امن تبدیل و scanner نام archive/member خصمانه را opaque می‌کند؛ symlinkهای ورودی رد می‌شوند.
- RED اصلی=`4/4` و endpoint RED=`1/1`؛ G08 all=`13/13` و related=`78/78`.
- OBS-007 در دامنهٔ runtime/diagnostic محلی `CLOSED / SYNTHETIC_OPERATIONS_VERIFIED` است؛ Desktop/API raw process channel تابع Electron policy باقی می‌ماند و OBS-008 Web metrics همچنان `DEFERRED` است.

## فصل ۱۷ — پذیرش تجمیعی G-09

- archive نهایی دو بار بایت‌یکسان ساخته شد؛ privacy scan، verifier، traversal/duplicate/collision/hash و forbidden scan سبز و finding صفر است.
- fresh extract/venv فقط از wheelهای archive با parity 90/0 drift، runtime checker و `pip check` سبز شد.
- full Backend جاری=`656/656` و skip صفر؛ همهٔ ۹ runner UI، TypeScript، UI/Electron Observability و build سبزند.
- F-005/F-006 برای current program scope بسته‌اند. OBS-008 همچنان deployment-dependent و `DEFERRED` است؛ Live scan و Production release ادعا نمی‌شود.
- Trigger: تغییر هر logger/redactor/catalog/background/scanner/retention/bundle/Electron/React boundary یا شروع استقرار Web واقعی.

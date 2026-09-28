# دستور اول — تکمیل بله به‌عنوان Provider درجه‌یک محصول

تاریخ: 2026-09-28

شناسهٔ مأموریت: BALE-PRODUCT

وضعیت: `PLANNED`

پیش‌نیاز اجرا: خواندن کامل [قواعد مشترک](EXECUTION_RULES.md)، اسناد AGENTS و این فایل.

## دستور مستقیم به عامل

اتصال Bale Personal به برنامهٔ اصلی AntiGravity2 را از کد موجود تا محصول قابل استفاده کامل کن. احراز هویت/ارسال/دریافت مستقل را بازنویسی نکن؛ façade `BaleApi` را در لایه‌های مالکیت حساب، runtime، adapter، API و UI عمومی درست متصل کن. checkpointها زیرمأموریت داخلی‌اند؛ در نبود مانع واقعی پس از هر checkpoint به بعدی برو.

مأموریت با ثبت نام بله در Registry، تغییر دو flag، نصب client یا بازکردن پنل مستقل تمام نمی‌شود. کاربر باید در همان برنامهٔ اصلی حساب بله بسازد/انتخاب کند، وارد شود، مخاطب و گفتگو ببیند، پیام ارسال/دریافت کند و آن حساب را برای سرویس وب مجاز کند.

## شواهد آغاز و بخش‌های نامعلوم

- F-086/ADR-60 توسعهٔ حساب شخصی بله را مجاز و درجه‌یک کرده‌اند. متن تاریخی G-02 یا قرنطینه، مبنای منع تازه نیست.
- V-194/F-072 در `b4491b7f`: list/search مخاطب، read-history و send-text با read-back روی نشست پذیرفته شدند.
- V-195/F-073: بهبود LoadDialogs و متن/رسانهٔ دیالوگ‌ها؛ گزارش و fixtureهای همان اصلاح را بخوان.
- `bale_client/api.py` دارای `add_contact_by_phone`، `add_contact` و `remove_contact` است. V-194 شاهد Live افزودن/حذف نیست؛ موفقیت آن‌ها را از وجود method فرض نکن.
- `bale_provider_adapter.py` فعلی `upsert_contact` را با `provider_contact_operation_not_implemented` رد می‌کند و `ProviderContactAdapter.list_contacts` در آن متصل نیست.
- `providers/bale/slot.py`: configured=true، runtime/onboarding=false، worker_factory=None.
- composition root اصلی adapter factory ایتا را وصل کرده؛ runtime registry و façade process ایتامحورند.
- M2M resolve/send فعلی با reference ایتا و lookup ایتا کار می‌کنند؛ reference بله `bale:peer:...` است. این شکاف در Core حل شود، نه با جعل `user:<id>` برای بله.

مرجع‌ها: [گزارش کلاینت مستقل](../../reports/BALE_BRANCH_PHASE1_REPORT.md)، [Discovery جاری](../../project-memory/BALE_PROVIDER_DISCOVERY.md)، [قرارداد Provider](../../PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md)، [قرارداد M2M](../../contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md). سابقهٔ report مستقل localStorage/token یا vault مشترک الگوی امنیت محصول اصلی نیست.

## B0 — inventory و قرارداد دقیق

فایل‌ها را بررسی کن: `application/bale_client/{api,client,auth,vault,codecs,codecs_ext,ws,models}.py`، `bale_provider_adapter.py`، `providers/{contracts,registry}.py`، `providers/bale/slot.py`، `account_runtime.py`، `process_runtime.py`، `interfaces/provider_worker.py`، `provider_orchestration.py`، `api.py`، `m2m_api.py`.

یک ماتریس روش backend → DTO → worker method → endpoint → UI → آزمون بساز. capabilityهای advertised همگی باید implementation و evidence مشخص داشته باشند. receive یعنی هم history و هم به‌روزرسانی گفتگوی باز؛ صرف façade تاریخچه، LIVE_UPDATES را اثبات نمی‌کند.

روی snapshot فعلی آزمون‌هایی برای شکاف contact protocol، factory/runtime، peer type و UI/API routing بنویس؛ RED درست و بدون شبکه ثبت کن.

## B1 — runtime، نشست و worker هر حساب

- account lifecycle را عمومی کن یا runtime اختصاصی بله پشت protocol عمومی بساز؛ موتور ایتا را برای حساب بله نساز.
- هر account یک مالک اتصال/async event loop و storage مستقل داشته باشد. WebSocket فعال را بین `asyncio.run`های کوتاه‌عمر درخواست‌ها جابه‌جا نکن.
- `BaleApi.create()` را با مسیر vault/log server-owned همان حساب و secret reference محافظت‌شده مقداردهی کن. استفادهٔ بی‌پارامتر و default vault مشترک برای چند حساب ممنوع است.
- challenge/code/password در state machine account-scoped، با expiry/cancel و بررسی identity همان حساب متصل شوند. passphrase vault از secret service داخل runtime تأمین شود؛ کاربر مجبور به واردکردن passphrase داخلی در فرم OTP نشود.
- sealed-session فعلی آداپتور عملاً passphrase می‌گیرد؛ آن را با قرارداد واقعی secret/session store تطبیق بده. انتقال رمز vault به‌عنوان public session DTO یا raw IPC راه‌حل نیست.
- factory worker، startup handshake، nonce/deadline/HMAC، generation fence، lease، shutdown و crash recovery را با زیرساخت عمومی موجود تکمیل کن.
- restore نشست فقط اتصال نشست مجاز است؛ ساخت حساب/startup نباید ارسال OTP ورود، import مخاطب یا send ایجاد کند. session invalid به وضعیت اقدام کاربر برگردد، نه حلقهٔ ورود خودکار.
- پروفایل worker_process=true و حالت پشتیبانی‌شدهٔ in-process را واقعاً بیازما. برای حل بله، خاموش‌کردن اجباری worker تمام محصول قابل قبول نیست.

## B2 — آداپتور، داده و مخاطبین کامل

`ProviderContactAdapter` را با list و upsert واقعی پیاده کن؛ نام درست، شمارهٔ canonical، paging محدود، deadline و mutation receipt داشته باشد. افزودن با phone روی `add_contact_by_phone` و id-only روی method موجود ترجمه شود. public DTO باید access_hash/phone/token خام façade را حذف و reference حساب‌محور بدهد.

جستجو روی contacts enriched، codec plain/wrapped و peer-only حفظ شود. تغییر نام موجود سیاست روشن داشته باشد؛ افزودن OTP کاربر جدید نباید contact موجود را تصاحب یا overwrite کند.

حذف contact در UI مدیریتی و endpoint حساب‌محور عمومی با scope/capability، confirm، idempotency و audit متصل شود؛ اگر protocol فعلی remove ندارد آن را نسخه‌دار توسعه بده. تماس import/search با یک Provider دیگر یا shared contact identity باعث اشتراک peer نشود.

reference نوع peer را حفظ کند: عدد user و group/channel یکسان، مقصد یکسان نیست. تابع فعلی `_user_id_from_reference` برای همهٔ نوع‌های گفتگو تعمیم بی‌شرط نشود. referenceهای قدیمی را با قرارداد سازگاری یا خطای صریح migration پشتیبانی کن.

dialog title/last_text/unread، message order/cursor، media references و فایل‌های قابل استفادهٔ backend را به DTO/UI وصل کن. media/send تنها با مسیر عمومی bounded و account-scoped؛ نه مسیر فایل از مرورگر و نه raw RPC.

LIVE_UPDATES یا polling واقعی با dedup/stale-account guard برقرار شود. امکانات groups/channels از قرارداد/رفتار واقعی backend و مجوز حساب تعیین شوند؛ feature ناموجود را با پاسخ خالی موفق جعل نکن. قابلیت محصولی هدف را فقط با blocker فنی مشخص باز بگذار، نه ممنوعیت تاریخی بله.

Send result فعلی façade random_id برمی‌گرداند؛ آن را message_id تحویل یا مشاهدهٔ گیرنده معرفی نکن. نگاشت success/uncertain و receipt طبق شاهد واقعی باشد. قطع اتصال بعد از شروع اثر بیرونی خودکار send دوباره نکند.

## B3 — API، M2M و همهٔ جایگاه‌های UI

| جایگاه محصول | نتیجهٔ لازم |
|---|---|
| افزودن حساب | انتخاب ایتا/بله شخصی از descriptor و Wizard صحیح هرکدام |
| انتخاب/تعویض حساب | چند بله و ترکیب ایتا/بله؛ label/شماره در نمای مجاز؛ دادهٔ قبلی نشت نکند |
| ورود و وضعیت نشست | challenge/2FA/resume/cancel/restore/logout حساب انتخابی |
| فهرست گفتگو | titles، unread، آخرین پیام و refresh واقعی بله |
| گفتگوی باز | history، متن/رسانهٔ پشتیبانی‌شده، send و receive بدون reload دستی |
| مخاطبین | list/search/add-by-phone/add-by-id/remove با نتیجه و خطای واقعی |
| مدیریت دسترسی | membership و انتخاب حساب‌های بله برای service credential |
| تنظیمات سرویس | نمایش account-level readiness؛ Provider registered معادل حساب ready نیست |
| انتخاب فرستندهٔ وب | حساب بله در selector قابل انتخاب؛ پایهٔ sender profile در P1 کامل می‌شود |
| M2M/OTP | resolve و ارسال روی peer بله؛ مخاطب جدید فقط با capability و permission import |
| diagnostics و release | summary امن حساب و دربرداشتن moduleهای بله در بسته |

API عمومی از Registry به adapter درست برسد. HTTP مستقل 8791 و `webui.html` موقت backend اصلی جدید یا shell موازی محصول نشوند. token آن در localStorage الگوی مصرف M2M نیست.

resolve عمومی account-scoped و فقط‌خواندنی بماند؛ از mapping واقعی همان حساب، peer قابل ارسال بله بدهد. `_DIALOG_REFERENCE` و parser مسیر ارسال را نسخه‌دار و Provider-neutral کن؛ شمارهٔ خام به peer تبدیل نشود. process-mode lookup هم با query bounded متصل شود، نه دسترسی Parent به object Child.

برای OTP بله: شمارهٔ مقصد + نام به contact prepare مجاز تبدیل شود، import نتیجهٔ matched واقعی بدهد، peer از همان نتیجه/lookup معتبر گرفته و سپس send شود. بدون matched یا با حالت نامعلوم، success یا peer ساختگی تولید نکن. pipeline پایدار رزرو/OTP در P3/P4 است؛ این مأموریت primitives لازم آن را قابل استفاده می‌کند.

بات بله جدا بماند؛ نقص phone lookup بات، مانع حساب شخصی مجاز نیست و capability شخصی به بات تسری پیدا نکند.

## B4 — مجموعهٔ آزمون لازم

tests موجود `test_bale_branch_api.py`، `test_bale_personal_authorization.py`، phase11 suites، m2m/service_auth و agent_gateway را حفظ و توسعه بده. fixture shapeهای V-194/V-195 را استفاده کن؛ fallback را با fixture تهیِ همیشه موفق نپوشان.

آزمون مستقل برای دو AppUser، دو حساب بله و یک ایتا؛ برخورد peer ID، vault، cache، contacts، reply و membership. تست restore/restart، قطع WS، cancellation، deadline، stale generation، concurrent request، import نام صحیح، mutation replay و uncertain send لازم است.

UI acceptance باید مرورگر/HTTP و API واقعی با backend ساختگی را شامل شود؛ regex source به‌تنهایی پایان B3 نیست. assert تعداد invocation، حساب مقصد و state persistence بده؛ payload خصوصی چاپ نشود.

startup ساخته‌شده در آزمون شبکه/OTP واقعی ایجاد نکند. نشان بده دیگر branch شرطِ Eitaa-only یا default vault مشترک باقی نمانده است.

## B5 — promotion و اسناد

runtime/onboarding را پس از تکمیل factory/worker و سبزی contractها فعال کن. promotion به `contract_verified` شاهد offline می‌خواهد؛ پذیرش Live از آن استنتاج نشود. خاموش‌ماندن دائمی با reason قدیمی pending پس از اتمام wiring، شکست معیار این مأموریت است.

تمام capabilityهای manifest باید به protocol درست و اجرای آزموده‌شده متصل باشند. implementation ناموجود با True advertised نشود. default مصنوعی disabled جدید نساز.

docs متناقض specification/structure/discovery/slot/test guards با ADR-60 و رفتار جدید هماهنگ شوند؛ گزارش تاریخی حفظ و صریحاً superseded شود. release allowlist و wheel باید همهٔ moduleهای لازم را داشته باشند.

## B6 — Pilot و handoff

ابزار Pilot خاموش در حالت پیش‌فرض بساز. فقط در دامنهٔ مجوز مالک، حساب و گیرندهٔ معلوم: restore گرم، list/search/history، دریافت به‌روزشده، یک contact import با نام مشخص و send/read-back. add/remove واقعی contact به‌صورت مستقل تأیید و شاهد شود؛ برای آزمون remove مخاطب عملیاتی نامرتبط پاک نشود.

قبل از نیاز به مجوز/credential، تمام کارهای B0-B5 و برنامهٔ دقیق Pilot را آماده کن. نبود credential فقط B6 را pending می‌کند. Full Live لازم را بدون اجرا `LIVE_ACCEPTED` اعلام نکن.

## معیارهای پایان

- BALE-A01: runtime و storage مستقل هر حساب، worker و restore آزموده‌شده.
- BALE-A02: auth/2FA/cancel/logout از برنامهٔ اصلی قابل استفاده.
- BALE-A03: contact list/search/add/remove واقعی در adapter/API/UI؛ Live هر mutation مشخص.
- BALE-A04: dialogs/history/send/receive و media موجود در backend، در برنامهٔ اصلی.
- BALE-A05: UI matrix B3 و mixed-account isolation دارای شاهد.
- BALE-A06: peer بله در resolve/send عمومی؛ آمادهٔ انتخاب برای sender/OTP.
- BALE-A07: همهٔ gateهای قواعد مشترک و wheel/source parity سبز.
- BALE-A08: گزارش جدید و handoff با وضعیت offline/Live جدا؛ V-194 به‌عنوان witness جدید generic runtime جا زده نشود.

پس از اتمام بخش مجاز، گزارش `docs/reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md` و handoff `docs/handoffs/BALE_FULL_PRODUCT_INTEGRATION_HANDOFF.md` را بساز. این فایل‌ها هنوز وجود ندارند. وضعیت را در [دفتر اجرا](EXECUTION_STATUS.md) به‌روز کن و برای برنامهٔ دوم آمادهٔ مصرف primitives بده.

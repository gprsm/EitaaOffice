# دستور اصلاحی پس از رد پذیرش کامل بله

> قید متأخر V-251 (2026-09-30): نتیجهٔ V-247/V-249 در دامنهٔ آزموده‌شده معتبر است، اما دو شکاف تازهٔ جستجوی فراگیر مخاطبین در IPC و تکمیل بدون توکنِ claim نسل دوم، پذیرش آفلاین کامل را باز کرده‌اند. دستور ادامه در [BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md](BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) است.

تاریخ: 2026-09-29 — مرجع F-099/V-234، V-236 و بازآزمایی V-246 پس از ادعای V-244. وضعیت: OFFLINE_REPAIRED_AND_VERIFIED_V249 / LIVE_PENDING_INPUT.

> **به‌روزرسانی وضعیت (پایان همان روز):** R1 (attempt fence با `attempt_token`/`attempt_generation`، شمای ۱۳) و R3 (صفحه‌بندی کران‌دار Child/IPC + `contacts.contains`) طبق این دستور پیاده و در V-247 و V-249 ثبت شد؛ پروب fence و پروب چهارگانه سبزند. آزمون کانونیکال پروسهٔ فرزند واقعی با Popen (`test_child_process_large_address_book_real_popen_paging_and_last_page`) با ۲۰۰۰ مخاطب مصنوعی، بررسی سقف فریم‌های IPC زیر ۳۵۰ کیلوبایت، رسیدن به مخاطب ۲۰۰۰ در صفحهٔ آخر، ایزولاسیون دو حساب و شبیه‌سازی UI اجرا و پاس شد (۲۰/۲۰ در فایل اصلی و ۱۲۳/۱۲۳ در کل فایل‌های بله). این هیچ پذیرش قطعی یا Live نیست: B6 نیازمند نشست/تأیید همان‌لحظهٔ مالک است و برچسب نهایی با ممیز مستقل است.

## ادامهٔ ضروری پس از V-246

پروب قبلی چهارگانه اکنون 4/4 سبز است؛ سناریوهای پایهٔ 501 مخاطب و تغییر payload پس از 429 را دوباره خراب نکن. این قبولی به معنی R5-A02/A03 نیست. [پروب تازهٔ attempt fence](BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py) در DB ایزوله RED است: تلاش A آزاد، B با همان owner/key/fingerprint claim شد، cleanup دیررس A ادعای B را آزاد کرد و C نیز claim گرفت. API فعلی release هیچ شناسهٔ تلاش نمی‌گیرد؛ `claim_released` به‌تنهایی fence نیست. generation/attempt token پایدار و match اتمیک هنگام release و complete اضافه کن؛ تست رقابت/cleanup دیررس برای text/media/remove، restart و نتیجهٔ terminal لازم است. پروب باید بدون تضعیف به GREEN برسد.

در R3 نیز Child هنوز `list_contacts()` را کامل می‌گیرد و تمام خروجی را در یک IPC frame می‌فرستد؛ runtime و adapter عملاً fetch-all می‌کنند و بعد از IPC صفحه‌بندی می‌کنند. 2000 مخاطب مصنوعی با نام 512حرفی، body حداقلی 1,134,907 بایت، از سقف frame برابر 1,048,576 بزرگ‌تر است. ورودی cursor/limit را در مسیر Child→backend اعمال و پاسخ bounded + next_cursor واقعی برگردان؛ اگر backend شخصی بله paging ندارد، راه‌حل کران‌دار یا اعلام صریح unsupported/truncated لازم است، نه fetch-all و پایان ظاهری. تست Child واقعی با دفترچهٔ بزرگ و بررسی frame، صفحهٔ آخر و UI لازم است. بعد از اصلاح، R5 و gateهای کامل روی snapshot ثابت اجرا شوند؛ Live همچنان نیازمند تأیید همان لحظه است.

## وضعیت ادامه پس از بازآزمایی مستقل V-236

R2 و نگاشت پایهٔ R4 در probe سبز شدند؛ R1 نیز برای retry یکسان پس از refill دیگر گیر نمی‌کند. آن مسیرهای رفع‌شده را بازنویسی نکن. اما R1 کامل نیست: release ردیف receipt را همراه fingerprint/مالکیت حذف می‌کند؛ درخواست ردشدهٔ 429 با همان id و متن متفاوت پس از refill به 201 و یک adapter call تازه می‌رسد، نه conflict. R3 همچنان با 501 مخاطب، 500 unique و next_cursor=null شکست می‌خورد. گزارش P3 خودش R3 را تحویل‌نداده اعلام کرده؛ تحویل P3 معادل پذیرش کامل BALE نیست.

عامل ادامه‌دهنده ابتدا دو RED باقی‌مانده را تثبیت کند: binding پایدارِ درخواست ردشده (R1) و paging بدون قطع خاموش (R3). binding با owner/account/service و fingerprint در محدودهٔ نگه‌داری قراردادی حفظ شود؛ تنها retry همان payload مجاز به claim تلاش تازه باشد. هویت تلاش با generation/attempt fence جدا از هویت درخواست باشد تا پاک‌سازی دیررس، تلاش تازهٔ همان owner/payload را حذف نکند. نداشتن اثر خارجی اجازهٔ حذف binding نیست. تست retry پس از restart، payload و owner/service متفاوت، و cleanup دیررس نیز لازم است. R2/R4 سبز و کنترل‌های R5 حفظ و روی snapshot نهایی تکرار شوند. هیچ Live یا ادعای بسته‌شدن F-099 پیش از این شواهد مجاز نیست.

## دستور مستقیم به عامل

در workspace AntiGravity2، AGENTS و ترتیب منابع آن، این فایل و [گزارش مستقل](../../reports/validation/BALE_PRODUCT_ACCEPTANCE_REVIEW_2026-09-29.md) را کامل بخوان. مأموریت اصلی [BALE-PRODUCT](BALE_FULL_PRODUCT_INTEGRATION.md) را حفظ کن. بدون reset/checkout/clean و بدون حذف کار P1/P2/P3، نقص‌های زیر را با regression مستقل RED→GREEN اصلاح کن. فقط سبز شدن suite موجود پایان کار نیست.

پایهٔ Git این بررسی 41dc87a2 است، ولی شاهد از working tree دارای اصلاحات V-230/V-233 و P1/P2 گرفته شده؛ HEAD تنها revision واقعی source را مشخص نمی‌کند. هنگام ممیزی، schema در حال تغییر 11→12 بود. پیش از پذیرش نهایی با عامل‌های نویسنده snapshot ثابت هماهنگ کن؛ فایل/شاخهٔ آن‌ها را جابه‌جا یا stage نکن.

این نقص‌ها در مسیر واقعی بله از UI/API اصلی بازتولید شده‌اند. دو نقص admission به لایهٔ مشترک P2 هم مربوط‌اند؛ مالک اصلاح واحد مشخص شود تا دو عامل یک فایل را هم‌زمان تغییر ندهند.

## شاهد آمادهٔ اجرا

[probe آفلاین](BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py) از API/orchestrator/DB/worker واقعی و backend مصنوعی موجود، ساعت fake و پوشهٔ موقت استفاده می‌کند. هیچ credential یا config عملیاتی نمی‌خواند و network Provider ندارد.

~~~powershell
.\.venv\Scripts\python.exe docs\implementation-plans\bridge-client-2026-09-28\BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py
~~~

در V-234 سه بررسی اولیه false بودند. در V-236 دو بررسی اولیه true و paging همچنان false است؛ بررسی چهارمِ binding، شرطی از R1 همین دستور، نیز false است. پس از رفع هر چهار باید true و exit=0 شوند؛ تابع probe را به‌جای محصول آسان نکن. probe مکمل است: سناریوها را به آزمون‌های مستقل canonical تبدیل کن، بدون fixture/shape خراب و بدون چاپ payload خصوصی.

## R1 — مالکیت claim در شکست admission

در provider_orchestration.send_text، durable claim و _send_in_progress پیش از _admit_execution ثبت شده‌اند، ولی acquire بیرون try/finally است. با ظرفیت یک، ارسال اول 201 می‌شود؛ دوم قبل از adapter رد می‌شود؛ بعد از refill همان id به provider_operation_duplicate_in_progress می‌رسد، entry حافظه و receipt durable هر دو in_progress باقی‌اند؛ id تازه ارسال می‌کند. در _extension_mutation نیز claim قبل از admission است؛ send-media و remove را جدا بیازما.

تمام خروجی‌های pre-dispatch از جمله acquire exception/circuit denial/cancellation باید مالکیت همان تلاش را تعیین تکلیف کنند. state پیش از شروع اثر خارجی را از started/uncertain جدا کن. fingerprint و مالکیت idempotency پس از رد نیز حفظ شوند؛ همان id با payload متفاوت conflict و retry یکسان پس از رفع مانع مجاز باشد.

صرف انتقال acquire قبل از replay/claim راه‌حل نیست: replay نباید token بگیرد و race یک id نباید دو permit/اثر ایجاد کند. پاک‌سازی فقط با owner/attempt fence انجام شود؛ claim رقیب یا نتیجهٔ کامل را حذف نکن. هیچ ادعای uncertain برای عملیاتی که قطعاً شروع نشده باقی نماند. پس از send_started یا نتیجهٔ واقعاً unknown، retry/fallback خودکار همچنان ممنوع است. خطای bookkeeping خطای اصلی را نپوشاند.

آزمون‌های مستقل: سطل خالی واقعی، refill fake، retry همان id، رقیب هم‌زمان، restart قبل از retry و expiry claim قطعاً بدون اثر؛ send_text/send_media/remove هرکدام؛ count adapter و state حافظه/DB دقیق. همچنین failure واقعی بعد از شروع send همچنان uncertain و بدون resend بماند. موفقیت replay بدون token حفظ شود.

## R2 — محدودیت واقعی contacts.upsert/import

مسیر upsert_contact هیچ admission/record_result ندارد؛ در probe سطل contacts.upsert خالی بود ولی API 201 داد و backend مخاطب را ایجاد کرد. این نقص فقط ضعف preflight نیست، bypass اجرای واقعی است.

همان policy موجود در composition root را روی هر fresh upsert/import اعمال کن، با مالک واحد هزینه، ثبت نتیجه و claim lifecycle R1. مسیر UI canonical، M2M prepare، حساب بله و ایتا و پروفایل‌های Process/in-process را بررسی کن. read-only resolve/list/search mutation نسازند و replay هزینهٔ عملیات نگیرد.

آزمون مستقل با bucket خالی و zero import/add، موفقیت پس از refill، replay، دو حساب/سرویس، نرخ observed Provider و failure/cancellation. preflight new_recipient و اجرای import باید دربارهٔ همان operation scope تصمیم بگیرند.

## R3 — صفحه‌بندی بدون حذف خاموش مخاطبین

Child در contacts.query فهرست را به items[:500] قطع می‌کند؛ adapter هم cursor را به offset<500 و next_cursor را به min(total,500) محدود کرده است. probe با 501 مخاطب واقعی در backend مصنوعی، پس از پنج صفحهٔ 100تایی فقط 500 مورد و next_cursor=null می‌بیند. پس موضوع «صرفاً paging ناکارآمد LOW» نیست؛ داده ناپدید می‌شود.

محدودیت هر page/IPC را حفظ کن، اما سقف page را سقف کل دفترچه فرض نکن. paging bounded در worker/backend و DTO درست با next_cursor/has_more پیاده شود؛ اگر Provider سقف واقعی دارد، truncated/unsupported صریح و مستند باشد، نه پایان جعلی فهرست. UI loadContacts باید ادامهٔ صفحات را قابل مشاهده/استفاده کند؛ fetch-all نامحدود برای دورزدن frame limit ممنوع.

آزمون بیش از 500 مورد، اندازهٔ pageهای مختلف، malformed cursor، دو حساب، پایان واقعی، duplicate/missing صفر، هر frame محدود، و بازکردن/جستجوی مخاطب صفحهٔ آخر از UI لازم است. lookup مورد نیاز OTP شمارهٔ جدید نباید با صفحهٔ اول اشتباه گرفته شود.

## R4 — قرارداد خطای محدودیت در API اصلی

API حساب‌محور محصول برای provider_operation_rate_limited فعلاً 400 و بدون Retry-After می‌دهد؛ مسیر M2M نگاشت 429 دارد. این دو مسیر نباید UX و retry متناقض بسازند.

نگاشت canonical همان code به 429 و Retry-After معتبر، circuit/dependency به کد قراردادی مناسب، duplicate/conflict به خطای مشخص و safe payload را تعریف کن. schema خطا و UI/client آن را مصرف کنند؛ متن raw exception یا اطلاعات حساب دیگر خارج نشود. آزمون انتقال واقعی HTTP روی loopback لازم است، نه فقط dispatch مستقیم. snapshot نرخ و حق تلاش بعدی تضمین تحویل نیست.

## R5 — شواهد و پایان مجاز

R5-A01: probe هر چهار بخش true/exit=0 و regressionهای مستقل RED→GREEN ثبت شده‌اند.

R5-A02: R1 برای text/media/remove و R2 برای import هر دو در حافظه، DB، retry/restart و رقابت PASS هستند.

R5-A03: بیش از 500 مخاطب بدون حذف خاموش در API/Child/UI دیده می‌شوند؛ bounds و مجوزها حفظ‌اند.

R5-A04: HTTP واقعی 429/Retry-After، UI انتظار و replay بدون token صحیح‌اند.

R5-A05: F-090/F-091، account isolation، auth/restore، generation fence، media و عدم ارسال دوبارهٔ uncertain حفظ شده‌اند.

R5-A06: روی snapshot ثابت full pytest، UI check/observability/build، wheel parity و تمام gateهای قواعد مشترک PASS؛ شکست‌ها و rerunها در Ledger.

R5-A07: baseline، گزارش بله، handoff، دفتر وضعیت، F-099 و قرارداد با رفتار واقعی هماهنگ؛ عبارت «تنها B6 باز است» پیش از این اصلاح‌ها استفاده نشود.

R5-A08: انتشار scoped فقط پس از اتمام و طبق AGENTS؛ درخت مشترک ناقص stage نشود. B6 Live همچنان نیازمند حساب/گیرنده و اجازهٔ همان لحظه است و با offline PASS بسته نمی‌شود.

بعد از رفع offline می‌توان برای Pilot محدود و مرحلهٔ بعد آماده شد؛ پذیرش کامل بله بدون B6 Live ادعا نشود. این دستور اجازهٔ اجرای زنده یا اصلاح خود سامانهٔ آزمون آنلاین نمی‌دهد.

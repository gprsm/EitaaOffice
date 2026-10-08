# بازبینی و اصلاح BALE-PRODUCT — 2026-09-28

قید جاری V-258/F-099 (2026-10-01): شرح V-244/V-247 در ادامهٔ این سند تاریخی است. جست‌وجوی فراگیر Child و حصار تکمیل نسل دوم اصلاح شده‌اند؛ پس از اصلاح اتصال بله در V-255/V-256، بازبینی مستقل کنونی ۱۰۵۱ آزمون جمع‌آوری کرد و full Backend با exit=0 و یک skip گذشت. پایلوت Live فقط در محدودهٔ خواندن، ارسال متن و تغییر مخاطب شاهد محدود مالک و رخدادهای امن V-257 دارد؛ پذیرش کامل B6 هنوز باز است. پاسخ خام WebSocket مخاطبین پیش از guard بایتی کامل دریافت می‌شود. [دستور اصلاحی دوم](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) و V-257/V-258 مرجع وضعیت جاری‌اند؛ پذیرش قطعی با ممیز/مالک است.

تکمیل اصلاحات و پذیرش آفلاین F-099 در 2026-09-29 با V-244: تمامی موارد دستور اصلاحی `BALE_ACCEPTANCE_REPAIR_2026-09-29.md` شامل R1 (پایبندی پایدار ادعا، بازگشت ۴۰۹ در صورت ارسال با محتوای متفاوت، موفقیت ارسال با محتوای یکسان)، R2 (کنترل نرخ مخاطب)، R3 (صفحه‌بندی ۵۰۱+ مخاطب بدون حذف خاموش)، R4 (نگاشت ۴۲۹ با Retry-After) و R5 (قبولی ۴/۴ پروب مستقل و قبولی ۱۰۰٪ کیفیت و آزمون‌ها) محقق و تأیید شدند. گزارش تفصیلی در [گزارش پذیرش بله](../validation/BALE_ACCEPTANCE_REPAIR_REPORT_2026-09-29.md) ثبت است.

وضعیت جاری: `OFFLINE_REPAIRED / VERIFIED_OFFLINE / B4_BROWSER_ACCEPTED_ON_FIXTURE / B6_LIVE_PENDING_INPUT`.
مرجع جاری: V-244، F-099، [گزارش پذیرش اصلاحات](../validation/BALE_ACCEPTANCE_REPAIR_REPORT_2026-09-29.md) و [handoff بله](../../handoffs/BALE_FULL_PRODUCT_INTEGRATION_HANDOFF.md).

## نتیجهٔ بررسی

مسیر بله از برنامهٔ اصلی به runtime، worker و آداپتور متصل است؛ خاموش‌کردن flag یا بازگشت به پنل مستقل راه‌حل نیست. نقص قطعی باقی‌مانده در حالت Child شناسایی و اصلاح شد: `/media/content` فیلد `token` را وارد IPC می‌کرد و فیلتر امن آن را رد می‌کرد. تست واقعی Child پیش از patch با status=400 شکست خورد؛ پس از استفاده از `content_handle` سبز شد. فیلتر عمومی secret/session خام تغییر نکرد.

اصلاح‌های تکمیلی:

- ورودی ناقص auth/code و auth/password به validation محدود worker می‌رسد؛ دسترسی مستقیم به کلید غایب دیگر KeyError نمی‌سازد. نگاشت رمز به `credential` که مدل دیگر انجام داده بود حفظ شد.
- دانلود رسانه هنگام خواندن stream کران‌دار شد، حتی اگر اندازهٔ اعلام‌شدهٔ Provider نادرست باشد؛ فایل جزئی تازه‌ساخته‌شده در خطا پاک می‌شود. حد فعلی 512 KiB است.
- پاسخ ارسال قدیمی، draft گفتگوی تازه‌انتخاب‌شده را پاک نمی‌کند؛ guard حساب و peer هر دو اعمال می‌شوند.
- آزمون نگاشت نام مخاطب موجود، deadline/cancellation روی loop ماندگار، challenge غلط/منقضی، session generation قدیمی و ارسال هم‌زمان اضافه شد.
- تست Child اکنون پس از restart کل برنامه replay را می‌سنجد؛ cache حافظه نمی‌تواند شاهد رسید پایدار باشد. migration واقعی schema 9 به 10 با receipt دارای مالک سرویس و نتیجهٔ موجود نیز آزموده شد.
- guard قدیمی UI onboarding که بله را الزاماً disabled می‌خواست اصلاح شد؛ مبنای مجوز، state قراردادی و factory همچنان assert می‌شوند.
- diagnostics عمومی برای ارسال uncertain، event موفقیت نمی‌سازد؛ text/media و replay همان نتیجهٔ نامعلوم را ثبت می‌کنند. regression پیش از patch هر دو رخداد متناقض را نشان داد.
- ابزار واقعی `scripts/bale_product_pilot.py` ساخته و به release allowlist افزوده شد؛ پیش‌نمایش Fake ابزار Pilot زنده محسوب نمی‌شود.

## وضعیت معیارها

| معیار | وضعیت جاری | شاهد و مرز |
|---|---|---|
| BALE-A01 | PASS آفلاین | loop/key/vault مستقل؛ in-process و Child؛ heartbeat/crash؛ restart کل برنامه و replay |
| BALE-A02 | PASS API آفلاین + مرورگری فیکسچر | auth/2FA/cancel/logout و challenge/session fence؛ wizard کامل مرورگری در V-233؛ هیچ ورود واقعی انجام نشده |
| BALE-A03 | PASS آفلاین + مرورگری فیکسچر؛ Live mutation باز | list/search/import/id/remove با confirm در مرورگر؛ add/remove واقعی هنوز تأیید نشده |
| BALE-A04 | PASS API آفلاین + مرورگری فیکسچر | title/preview/history/text/media و **دریافت بدون reload با polling/dedup در مرورگر (V-233)**؛ Live باز |
| BALE-A05 | PASS روی فیکسچر مرورگری | ماتریس UI با API واقعی و backend مصنوعی در مرورگر IAB: تعویض حساب بدون نشت، wizard، مخاطبین، تنظیمات، service selector (V-233)؛ Live ندارد |
| BALE-A06 | PASS آفلاین | resolve فقط‌خواندنی، prepare با contacts.import، matched واقعی، membership/account/credential fence |
| BALE-A07 | gateهای اجراشده سبز | full Backend 947 passed پس از اصلاح‌های F-098؛ wheel parity؛ کنترل اسناد |
| BALE-A08 | PASS | گزارش/ماتریس/handoff با تفکیک offline، browser-fixture و Live؛ V-194/V-195 مستقل و تاریخی‌اند |

## آزمون‌ها و بسته

فرمان‌های اصلی این بازبینی:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -o addopts='' --tb=short --show-capture=no
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
npm.cmd --prefix ui run build
.\.venv\Scripts\python.exe scripts/build_wheel_stdlib.py --force
.\.venv\Scripts\python.exe scripts/check_runtime_environment.py
.\.venv\Scripts\python.exe package_clean.py --dry-run
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py
.\.venv\Scripts\python.exe scripts/check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts/refresh_project_docs.py --check --check-links
git diff --check
```

آزمون محصولی/owner/Pilot: 24 تست مستقل؛ به‌علاوه آزمون migration. full Backend نهایی پس از آخرین source و rebuild wheel: `926 passed, 1 skipped, 1 warning` در 174.93s، exit=0. check، observability و build رابط کاربری exit=0؛ تمام runnerهای canonical مدل/قرارداد UI سبز شدند. runner phase11-onboarding ابتدا با الزام قدیمی disabled بودن بله exit=1 داشت و پس از اصلاح guard exit=0 شد. package dry-run با 345 فایل allowlisted و privacy scan exit=0؛ integrity/generator/link check سبز. هشدار شناخته‌شدهٔ websockets و اندازهٔ chunk اصلی Vite مانع build نبودند.

## بازبینی F-098/V-233 — شکاف‌های مغفول و پذیرش مرورگری (2026-09-29)

ممیزی مستقل کد علیه مأموریت سه نقص واقعی و یک نقص ابزار پیدا کرد؛ هر چهار با آزمون RED بازتولید و سپس سبز شدند:

1. **Latch ناعادلانهٔ restore:** هر شکست restore — حتی تایم‌اوت و قطع حمل — حساب را برای همیشه `auth_state=invalid` می‌کرد و restore بعدی را قفل می‌کرد، در حالی که worker ممکن بود سالم بماند و خطای واقعی پوشانده می‌شد. اکنون فقط `bale_vault_locked`/`bale_session_invalid` invalid می‌شود؛ خطاهای حمل با `bale_restore_unavailable`/`bale_vault_missing` گزارش و وضعیت حفظ می‌شود؛ مسیر auto-restore worker هم فقط روی vault-locked latch می‌شود و کد واقعی را برمی‌گرداند.
2. **دورزدن تأیید صریح M2M:** مسیر سازگاری `POST /api/v2/m2m/messenger-accounts/{id}/messages/send-text` به‌صورت خودکار `confirm:true` تزریق می‌کرد. تزریق حذف شد؛ بدون تأیید صریح `400 m2m_confirm_required` می‌دهد و قرارداد بخش 1b برای آن نوشته شد.
3. **LIVE_UPDATES بدون پشتوانه (نقض B5):** قابلیت در manifest advertised بود ولی هیچ protocol/observation متصل نداشت و وضعیت آن صرفاً از declaration «supported» گزارش می‌شد. اکنون نویسندهٔ `record_messenger_capability_observation` در coordinator store وجود دارد، ران‌تایم بله هنگام start مشاهدهٔ `bale_updates_polling_transport` با قیود transport/dedup/scope ثبت می‌کند، snapshot قابلیت مشاهدهٔ واقعی را گزارش می‌کند و حلقهٔ polling UI روی `hasCapability('updates.live')` گیت خورده است.
4. **نقص ابزار preview:** `bale_ui_preview.py` UPDATE برچسب‌ها را بدون commit می‌نوشت و labelهای fixture هرگز اعمال نمی‌شدند؛ commit اضافه شد.

### پذیرش مرورگری B4 روی فیکسچر (V-233)

`tests/bale_ui_preview.py` با API واقعی محصول، باندل build واقعی و backend مصنوعی (دو Bale/یک Eitaa، DB یک‌بارمصرف) در مرورگر IAB اجرا شد و همهٔ ردیف‌های ماتریس B3 را پوشش داد: بازکردن گفتگو و تاریخچه؛ **دریافت پیام `/__fixture__/receive` بدون reload در چرخهٔ polling با dedup**؛ ارسال با دیالوگ تأیید صریح و پیام صادقانهٔ «مشاهدهٔ گیرنده تأیید نشده»؛ تعویض حساب Alpha→Beta بدون هیچ نشت داده (وضعیت absent و wizard)؛ جریان کامل ورود start→code→رمز دومرحله‌ای→authenticated؛ هشدار صادقانهٔ گروه/کانال با ارسال غیرفعال؛ مخاطبین list/add-by-phone با نام/remove با تأیید؛ نمای تنظیمات با readiness حساب‌محور و دیالوگ credential سرویس با انتخاب bale به‌عنوان Provider و عضویت حساب‌های بله.

محدودیت ابزار: کلیک‌های Playwright روی ListItemButton حین re-render دوره‌ای polling تایم‌اوت می‌شدند؛ اجرای گام‌ها با کلیک برنامه‌ای/رخداد کامل مکان‌نما ممکن شد — این محدودیت اتوماسیون است نه محصول، و تعامل واقعی کاربر از مسیر رویداد بومی عبور می‌کند.

دروازه‌های نهایی این بازبینی: full Backend `947 passed, 1 skipped, 1 warning` در 211.15s، exit=0؛ focused بله/m2m `140 passed`؛ check/observability/phase11 (با چک جدید LIVE_UPDATES) exit=0؛ wheel بازسازی با SHA-256=`23285b0c…26002a0`؛ refresh/integrity/check/check-links/diff-check exit=0. شاهد مرورگر روی backend مصنوعی است و هرگز معادل Live نیست؛ دادهٔ عملیاتی دست نخورده باقی ماند.

## Pilot آماده و خاموش

اجرای پیش‌فرض زیر هیچ شبکه یا ورودی credential ندارد:

```powershell
.\.venv\Scripts\python.exe scripts/bale_product_pilot.py
```

فقط برای نصب اصلی loopback و با `--allow-live --origin http://127.0.0.1:PORT --action ACTION` فعال می‌شود؛ هیچ اجرای زنده در این بازبینی انجام نشد. session/CSRF و شناسه/نام/متن خصوصی با prompt امن، بدون ذخیره/چاپ دریافت می‌شوند؛ redirect رد می‌شود و خطا یا اثر نامعلوم خودکار retry نمی‌شود. actionها status، restore، contacts، search، history، receive، import، add-id، send/read-back، media و remove هستند. restore/import/add-id/send/remove در همان گام تأیید خصوصی می‌خواهند؛ remove فقط برای contact ایجادشدهٔ همین Pilot مجاز است.

ورودی‌های باقی‌مانده: نصب/revision هدف؛ حساب و گیرندهٔ آزمایشی مجاز؛ نام و متن مصوب؛ سقف عملیات؛ روش امن نشست اپلیکیشن و تأیید همان‌لحظهٔ هر عملیات واقعی. در نبود آن‌ها B6 Live باز می‌ماند. انتشار Git نیز به تصمیم مالک است: درخت کاری مشترک سه سناریوست (بازبینی V-230، کار موازی P1/P2 و این بازبینی) و جداسازی تمیز stage ممکن نیست؛ این مانع در F-095 و F-098 ثبت شده است. مادهٔ LOW باقی‌مانده از ممیزی (submission_reference تصادفی رسانه، صفحات‌بندی offset مخاطب، و شipping `bale_client/api_server.py` داخل wheel) در F-098 فهرست شده و معیار پذیرش را نقض نمی‌کند.
قید تکمیلی V-255/F-101 (2026-10-01): نخستین ورود واقعی OTP در نصب تست جداگانه نشست را ذخیره کرد، اما خواندن گفتگوها به‌علت فرض نادرست Worker دربارهٔ اتصال WebSocket با `bale_not_connected` شکست خورد. اصلاح OTP و عامل دوم با آزمون RED→GREEN انجام شد؛ پس از راه‌اندازی دوباره، خواندن زندهٔ گفتگوها موفق بود. این شاهد ارسال/تغییر مخاطب یا پذیرش کامل B6 نیست.

قید تکمیلی V-256/F-101 (2026-10-01): قطع دیرهنگام WebSocket دوباره همان خطا را پدید آورد. Worker اکنون با دریافت `bale_not_connected` اتصال را نامعتبر می‌کند تا درخواست بعدی از vault وصل شود؛ درخواست شکست‌خورده به‌طور خودکار replay نمی‌شود. بازیابی با آزمون آفلاین RED→GREEN ثابت شده؛ خواندن زنده پس از restart موفق بود، اما قطع و بازیابی زنده هنوز جداگانه مشاهده نشده است.

قید تکمیلی V-257 (2026-10-01): مالک موفقیت خواندن، ارسال متن و مخاطبین را در نصب تست گزارش کرد؛ لاگ امن همان نصب دو ارسال متن، دو upsert و یک remove موفق و خواندن‌های موفق را ثبت کرده است. این پایلوت Live محدود است؛ read-back دقیق، دریافت به‌روزشده، جست‌وجو و بازیابی زنده پس از قطع هنوز شاهد جداگانه ندارند. پذیرش کامل بله و انتشار ثبت نشده‌اند.

پیگیری F-102/V-260 (2026-10-01): پیام عمومی شکست پس از مدتی استفاده از نصب تست با `bale_rpc_error` در درخواست تکمیلی `GetContacts` هم‌بسته بود. کد قبلی در هر بازخوانی گفتگو مخاطبان را نیز می‌خواند؛ چند رد RPC با کد عددی ۸ دیده شد. درخواست اختیاری تکمیل نام اکنون cache و در خطای RPC غیرمسدودکننده است؛ UI خطای polling را پس از موفقیت پاک و در شکست‌های پی‌درپی کندتر تکرار می‌کند. پس از راه‌اندازی دوباره، بازخوانی‌های پیوستهٔ `dialogs.list` موفق بودند؛ هیچ عملیات mutation تازه‌ای برای این بررسی اجرا نشد. مرجع آزمون و مرز شاهد در V-260 است.

پیگیری V-261 (2026-10-01): مالک جست‌وجوی موفق یک مخاطب موجود و دیدن دوبارهٔ پیام ارسالی قبلی در تاریخچهٔ نصب تست را تأیید کرد. رخدادهای امن خواندن با آن سازگارند، اما تطبیق محتوا بر شاهد مستقیم مالک تکیه دارد. هیچ دادهٔ خصوصی یا عملیات اثرگذار تازه ثبت/اجرا نشد. بازیابی گرم نشست و مسیر عمومی M2M هنوز مستقل‌اند.

پیگیری V-262 (2026-10-01): در مشاهدهٔ دیرتر، خود `LoadDialogs` در چرخهٔ پنج‌ثانیه‌ای با کد ۸ به‌طور متناوب رد شد؛ بنابراین شاهد کوتاه پایداری V-260 برای پذیرش بلندمدت کافی نبود. UI فهرست گفتگوها را با cadence پایهٔ ۱۵ ثانیه و backoff ۳۰/۶۰ ثانیه از تاریخچهٔ گفتگوی باز با cadence پنج‌ثانیه‌ای جدا کرد؛ تب پنهان درخواست نمی‌فرستد و شکست گفتگو دیگر تاریخچه را متوقف نمی‌کند. UI check/observability/build سبزند. سرویس تست از وضعیت خاموش با همان Config و نشست قبلی بالا آمد؛ مالک بازگشت گفتگوها بدون کد ورود تازه را تأیید کرد و لاگ امن `dialogs.list` موفق با فاصلهٔ حدود ۱۵ ثانیه نشان داد. دوام بلندمدت نرخ تازه و بازیابی از قطع WebSocket در همان فرایند هنوز شاهد جدا می‌خواهند.

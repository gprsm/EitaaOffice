# ممیزی مستقل تحویل بله — پذیرش کامل رد شد

تاریخ: 2026-09-29؛ مرجع F-099/V-234 و بازآزمایی مستقل V-236. نتیجهٔ جاری: PARTIALLY_REPAIRED / OFFLINE_REPAIR_REQUIRED / LIVE_PENDING_INPUT.

## بازآزمایی پس از تحویل P3/V-235 — V-236

HEAD همچنان 41dc87a2 است؛ شاهد از working tree عمدی دارای کار بله و P1/P2/P3 گرفته شد، نه صرفاً کامیت یا شاخهٔ دوردست. آغاز بازآزمایی 42 فایل tracked modified و staged صفر داشت؛ untrackedهای کاربر و عوامل حفظ شدند. گزارش P3 صریحاً R3 را خارج از تحویل خود گذاشته است؛ این ممیزی پذیرش کامل وب/P3 نیست.

| موضوع | خروجی مستقل فعلی | پذیرش |
|---|---|---|
| رد rate و retry یکسان | 201، سپس 429 با Retry-After؛ retry پس از refill و id تازه هر دو 201؛ count هنگام رد 1، پایان 3؛ memory in_progress=0 و durable=succeeded | شرط گیرنکردن retry سبز شده |
| upsert با bucket خالی | 429، بدون backend mutation | شاهد پایهٔ R2 سبز شده |
| 501 مخاطب | page sizes=[100,100,100,100,100]، unique=500، next_cursor=null | R3 هنوز RED |
| متن متفاوت با همان id ردشده پس از refill | رد اولیه 429، متن متفاوت 201؛ count مستقل از 1 به 2 (در probe تجمیعی از 3 به 4) | R1 binding هنوز RED؛ انتظار 409 و count ثابت |
| suite هدفمند preflight، main product، agent gateway | 54 passed، 1 warning، 56.10s، exit=0 | پوشش موجود سبز، نه پذیرش شرایط RED |

ردیف receipt در `ProviderOperationReceiptStore.release` با DELETE حذف می‌شود؛ بررسی actor/fingerprint/service پیش از حذف، binding را پس از حذف حفظ نمی‌کند. در نتیجه همان id به payload دیگری قابل تخصیص می‌شود، خلاف شرط صریح R1 دستور قبلی. این نتیجه از API/orchestrator واقعی، bucket/refill واقعی و backend مصنوعی حاصل شد، نه فقط تحلیل source یا exception ساختگی. اثر خارجی واقعی رخ نداد. تست مستقل تک‌سناریو و probe تجمیعی هر دو همین شکست را نشان دادند؛ probe سه شرط قبلی را حفظ کرده و شرط چهارم از R1 را اضافه کرده است.

F-099 باز می‌ماند. فقط مسیرهای پایهٔ rate/upsert/HTTP تأیید شده‌اند؛ پوشش media/remove/restart/race و attempt fence نباید از این تست متن استنتاج شود. full suite و UI/build/wheel این نوبت دوباره اجرا نشدند: دو معیار پذیرش هنوز مستقلاً RED هستند؛ نتایج گزارش عامل در V-235 به‌عنوان شاهد او محفوظ، نه نتیجهٔ اجرای این ممیز. هیچ source محصول، دادهٔ عملیاتی، stage/commit/push یا Live تغییر نکرد. ادامه مطابق [دستور به‌روز](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) است. نتایج اولیهٔ زیر فقط سابقهٔ V-234 هستند و شرح source جاری نیستند.

## مبنا و مرز

checkout واقعی AntiGravity2 روی HEAD 41dc87a2 و شاخهٔ codex/bale-web-client-instructions بررسی شد. 40 فایل tracked در آغاز dirty بودند، staged صفر و untrackedهای کاربر/فازهای موازی محفوظ. تغییرهای محصولی V-230/V-233 و P1/P2 هنوز commit نشده‌اند؛ remote branch نمی‌تواند شاهد این تغییرهای محلی باشد. هیچ source محصول یا فایل عملیاتی توسط این ممیزی تغییر نکرد.

مأموریت، B0 matrix، گزارش و handoff جاری و حافظه/قرارداد خوانده شدند. V-233 شاهد مرورگری فیکسچر است، نه Live. B6 طبق خود گزارش هنوز ورودی/مجوز ندارد. بررسی حاضر ادعای فازهای وب را نمی‌پذیرد/نمی‌بندد؛ فقط اثر لایهٔ مشترک روی مسیر بله را نشان می‌دهد.

## نتایج مستقل

| موضوع | خروجی واقعی | نتیجه |
|---|---|---|
| suite هدفمند بله، Pilot، agent gateway و M2M | 91 passed، 1 warning، 44.89s، exit=0 | پوشش موجود سبز؛ کافی برای اتمام نیست |
| ارسال با bucket یک و retry پس از refill | اول 201؛ رد دوم 400 rate_limited بدون Retry-After؛ retry همان id برابر 400 duplicate_in_progress؛ id تازه 201 | claim حافظه/DB رهاشده پیش از اثر خارجی |
| count/state همان سناریو | count ارسال هنگام رد 1، پایان 2؛ حافظه in_progress=1؛ receipt ردشده in_progress | تلاش ردشده هرگز adapter را اجرا نکرد، اما retry گیر می‌کند |
| upsert با سطل contacts.upsert خالی | 201؛ contact واقعاً در backend مصنوعی ایجاد شد | admission این مسیر غایب است |
| صفحه‌بندی 501 مخاطب | پنج صفحهٔ 100تایی، unique=500، next_cursor=null | حذف خاموش یک مخاطب |
| UI check و observability | هر دو exit=0 | type/contract سبز؛ جایگزین آزمون رفتار نیست |

probe قابل اجرا در [فایل مستقل](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py) ثبت شده؛ آخرین اجرای تمیز سه passed=false و exit=1 فقط به علت شکست معیارهای معنایی داشت. API/orchestrator/DB/worker واقعی و backend موجود ساختگی‌اند؛ clock fake و config/DB یک‌بارمصرف، بدون شبکه/حساب واقعی.

## ریشه‌ها و حدود

provider_orchestration.send_text پس از ثبت claim، admission را بیرون try/finally اجرا می‌کند؛ _extension_mutation هم receipt را پیش از admission ثبت می‌کند. upsert_contact اساساً admission ندارد. قطع items[:500] در worker و min(total,500) در cursor آداپتور، cap هر page را به سقف کل تبدیل کرده‌اند. API اصلی نگاشت HTTP محدودیت M2M را ندارد. این موارد با fake exception تنها حدس زده نشده‌اند؛ bucket/refill و paging واقعی مسیر محصول بازتولید شده‌اند.

چهار مورد باید طبق [دستور اصلاحی](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) اصلاح شوند. طبقه‌بندی LOW تاریخی paging در F-098 برای loss of data فعلی کافی نیست. نقص admission اشتراک با P2 دارد و به یک مالک اصلاح نیاز دارد؛ دو عامل روی یک فایل کار نکنند.

## کنترل harness و درخت متغیر

اجرای ابتدایی probe خروجی نقص‌ها را داد، ولی teardown دستی fixture اشتباه بود: generator.close به‌جای ادامهٔ post-yield، روی Windows قفل DB/log موقت باقی گذاشت و exit=1 ساخت. این خطای harness شاهد RED محصول محسوب نمی‌شود. fixture teardown با resume و close اتصال موقت اصلاح شد؛ اجرای نهایی بدون traceback، شکست معنایی را مستقل نشان داد.

در فاصلهٔ بررسی، schema از 11 به 12 توسط کار موازی تغییر کرد؛ یک اجرای میانی قبل از تکمیل migration با schema checksum mismatch در setup متوقف شد و شاهد نقص بله شمرده نشد. پس از تکمیل DDL اولیه، probe تمیز سه نقص را دوباره نشان داد. full suite روی درخت در حال تغییر دوباره اجرا نشد؛ گزارش سبز پیشین را به snapshot جدید تعمیم نمی‌دهیم. gateهای نهایی محصول بر عهدهٔ اصلاح روی درخت ثابت است.

## تصمیم تحویل

بله برای «محصول کامل» پذیرفته نیست. کار مستقل وب می‌تواند جدا ادامه یابد، اما Pilot/انتشار/پذیرش نهایی مسیر بله باید پس از اصلاح و gateهای snapshot ثابت انجام شود. هیچ login/import/send واقعی، اتصال AI، تغییر config/نشست یا استقرار در این نوبت انجام نشد. commit/push محصول انجام نشد و هیچ تغییر دیگران stage نشد.

# گزارش نهایی G-03 — نصب تمیز و احراز هویت آغازین

تاریخ: 2026-08-26  
Runها: `STAB-G03-R01` تا `STAB-G03-R06`  
وضعیت: `COMPLETE / SYNTHETIC_OFFLINE_ACCEPTED / FULL_BACKEND_GREEN`  
Finding: `F-041 CLOSED`

## هدف و مرز

هدف G-03 این بود که نصب بدون Coordinator DB، config/session عملیاتی یا حساب ازپیش‌موجود بتواند به‌صورت ایمن بالا بیاید؛ Legacy challenge نیز باید opaque، وابسته به شناسه/stage/TTL و در برابر replay، mismatch و restart fail-closed باشد. تمام acceptanceها با Fake و ریشهٔ موقت اجرا شدند. نصب واقعی، Login/OTP، Provider network، Session واقعی و تغییر سیستمی خارج از دامنه بودند.

## RED و علت‌های ریشه‌ای

- RED اولیه `4/4 failed`: bootstrap مدیر روی Coordinator کاملاً خالی ممکن نبود، startup حالت AppAuth+multi-session بدون DB/default رد می‌شد، Legacy پاسخ `challenge_id` نداشت و expiry به submit bind نبود.
- نخستین retry پس از patch `3/4` بود؛ failure باقی‌مانده defect محصول نبود و test double مادهٔ credential کوتاه‌تر از CHECK schema تولید می‌کرد. فقط fixture آزمون اصلاح شد.
- adversarial/restart RED برابر `4/5` بود: پس از restart، Provider فراخوانی نمی‌شد اما رکورد چندحسابی در `challenge_pending` باقی می‌ماند.
- نخستین full Backend پس از G-03 برابر `607/608` بود: دو event جدید challenge emit می‌شدند اما Event Catalog آن‌ها را ثبت نکرده بود.
- در finalization روشن شد دو معیار برنامه—startup تکراری و installer config-copy rehearsal ایزوله—شاهد مستقل نداشتند. این شکاف traceability با دو acceptance تازه بسته شد؛ defect محصول جدیدی دیده نشد.

## اصلاح محصول

- `LegacyAuthChallenge` با UUID opaque سمت سرور، stage، زمان صدور/انقضا، provider challenge فقط در حافظه و summary محدود ایجاد شد.
- request-code Legacy شناسه را برمی‌گرداند و submit-code/password وجود شناسه، stage و expiry را پیش از Provider می‌سنجد.
- Coordinator کاملاً خالی می‌تواند نخستین مدیر را اتمیک bootstrap کند و setup status امن ارائه دهد.
- composition root در AppUser Auth، Coordinator را روی ریشهٔ خالی initialize می‌کند و runtime فقط در empty-bootstrap واقعی بدون default account بالا می‌آید.
- challenge گم‌شدهٔ چندحسابی پس از restart، همان generation پایدار را با reason امن و audit به `expired` منتقل می‌کند.
- `auth_challenge_denied` و `auth_challenge_expired` با category احراز هویت، result ردشده و الزام audit در Event Catalog ثبت شدند.

## پذیرش و regression

| مرحله | نتیجه |
|---|---|
| RED اولیه clean-install/Legacy | `4/4 failed` معتبر |
| G-03-A اختصاصی | `4/4 passed` |
| G-03-B AppAuth/API/AccountRuntime | `57/57 passed` |
| G-03-C adversarial/restart | RED=`4/5`، GREEN=`5/5` |
| G-03-C regression مرتبط | `81/81 passed` |
| G-03-D observability هدفمند | `6/6 passed` |
| G-03-D Backend پس از catalog | `608/608 passed` |
| G-03-E startup تکراری + installer rehearsal | `2/2 passed` |
| G-03-E Backend نهایی | `610/610 passed` |
| UI TypeScript | PASS |
| UI/Electron observability | PASS |
| diff هدفمند | PASS |
| generator + integrity/stale/link | PASS |

دو acceptance نهایی ثابت کردند empty multi-session startup روی همان DB خالی تکرارپذیر است و config نمونه مطابق قرارداد copy-if-missing نصب‌کننده در ریشهٔ موقت، بدون بازکردن Provider و بدون ساخت Session، دو بار startup می‌شود. اجرای Installer واقعی یا bind سیستمی انجام نشد.

Phase 10 local activation و Phase 11 onboarding دوباره اجرا نشدند، زیرا drift آن‌ها پیش‌تر در F-042/G-06 ثبت شده و هیچ کد مرتبطی در G-03 تغییر نکرد. این تصمیم مطابق قاعدهٔ جلوگیری از بررسی تکراری است و closure G-03 آن findingهای مستقل را نمی‌بندد.

## امنیت و اثر بیرونی

تست‌ها ثابت کردند شناسهٔ اشتباه/خصمانه، stage نادرست، challenge منقضی، replay، supersession و restart پیش از Provider رد می‌شوند و مقدار ورودی در پاسخ echo نمی‌شود. provider challenge خام و فیلد خارج از allowlist وارد response نیست. تست‌های observability نیز redaction و catalog را پوشش دادند.

هیچ Login، OTP، رمز دوم واقعی، Provider network، Send، WordPress، migration/rollback عملیاتی، نصب واقعی، Firewall/Proxy/Port، داده/config/session/runtime واقعی یا Git stage/commit/push انجام نشد. تمام DB/config/session/logهای ایجادشده مصنوعی و زیر basetemp بودند.

## هش‌های نهایی

- `api.py`: `1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4`
- `account_auth.py`: `6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da`
- `account_runtime.py`: `7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b`
- `coordinator/app_auth.py`: `637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c`
- `event_catalog.py`: `33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9`
- `test_clean_install_auth_stabilization.py`: `980d467153927d6f9b6d8b1ccacfb88ebb3db177dce94b8178524c9912b0830c`
- `test_account_auth_lifecycle.py`: `ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882`

## نتیجه و Trigger

معیار خروج G-03 محقق و F-041 بسته شد. هر تغییر آینده در bootstrap Coordinator، AppAuth startup، account runtime selection، Legacy/Account challenge binding، installer config copy یا Event Catalog احراز هویت، شاهد این گزارش را منقضی می‌کند و باید حداقل acceptanceهای G-03 و regression متناسب دوباره اجرا شوند.

این closure به‌معنای release readiness عمومی نیست؛ F-042، F-043، F-044 و مراحل G-04 تا G-09 همچنان بازند.

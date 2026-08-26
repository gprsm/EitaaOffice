# گزارش نهایی G-04 — هم‌ترازی هویت محصول و مرز مستقل حریم خصوصی

تاریخ: 2026-08-26  
Run نهایی: `STAB-G04-R05`  
Ledger: `V-117` تا `V-121`  
Finding: `F-044 CLOSED`  
وضعیت: `G-04 COMPLETE / OFFLINE_AUTOMATED_ACCEPTED / NOT_RELEASE_READY`

## هدف و تصمیم ثابت

نمایش هویت canonical تلفنی در سطح مجاز محصول مطابق تصمیم کاربر حفظ شد و تست‌های masking منقضی بازنگشتند. این تصمیم هیچ مجوزی برای ثبت شمارهٔ کامل، Token، OTP، Cookie، Session یا متن خصوصی در Runtime Log، Audit، Diagnostic، Support Bundle یا اسناد مهندسی ایجاد نمی‌کند.

## مسیر A تا E

| بخش | شاهد و نتیجه |
|---|---|
| G-04-A | تست test-first جدید: نمایش محصول سبز؛ placeholder آزمون و identity-hint redaction عمداً `2/3 failed` |
| G-04-B | جایگزینی تست‌های خالی و redaction کلیدهای hint؛ اختصاصی=`3/3`، مرتبط=`28/28` |
| G-04-C | حذف token از onboarding عمومی و الزام `phone_e164`؛ Backend=`2/2`، UI=`7/7`، مرتبط=`126/126` |
| G-04-D | چهار کانال privacy و scanner ابتدا `5/5 failed` و پس از hardening=`5/5 passed`؛ regressionها=`53/53`، `2/2` و `50/50` |
| G-04-E | ممیزی هش بدون drift؛ full Backend نهایی=`620/620`؛ TypeScript/Observability سبز؛ onboarding UI=`7/7` |

## رخداد full regression

full Backend نخست `620 collected / 618 passed / 2 failed` بود. هر دو failure، timeout ده‌ثانیه‌ای subprocess در Process Worker بودند و هیچ failure هویت/privacy رخ نداد. همان دو node بلافاصله و بدون patch در isolation=`2/2` سبز شدند. full rerun با basetemp تازه و بدون تغییر محصول=`620/620 passed` شد؛ failure نخست به ازدحام زمانی full-suite طبقه‌بندی و در V-121/Execution Log حفظ شد.

## معیارهای خروج

- assertion یا نام تست masking منقضی بازنگشت و replacementها assertion واقعی دارند.
- مقدار canonical در persistence/UI مجاز محصول حفظ می‌شود.
- public onboarding فقط `provider/phone/label` و identity kind تلفنی E.164 را می‌پذیرد؛ token/account kind تازه ساخته نشد.
- Runtime Log، Audit persistence/query/export، Diagnostic و Support Bundle با دادهٔ synthetic برای global E.164/Bearer و کلید ناشناخته/تو‌در‌تو fail-closed هستند.
- Backend کامل، TypeScript، UI/Electron Observability و قرارداد onboarding جاری سبزند.
- Baseline، Specification، Architecture، Findings، Observability Audit، Ledger و Handoff با قرارداد نهایی همسو شده‌اند.

## اثر تغییر و مرز پذیرش

در G-04-E هیچ source/test محصولی تغییر نکرد؛ فقط full regression و اسناد closure اجرا/ثبت شدند. تمام DB/log/diagnostic/bundleها مصنوعی و زیر basetemp بودند. هیچ config/session/runtime/diagnostics عملیاتی، Provider network، Login/OTP/Send، migration/rollback واقعی، توسعهٔ Bale یا Git stage/commit/push انجام نشد.

G-04 و F-044 بسته‌اند، اما پروژه هنوز `NOT_RELEASE_READY` است. G-05 تا G-09، F-042/F-043 و معیارهای مستقل packaging/lifecycle باقی‌اند. G-05 فقط با دستور صریح کاربر آغاز می‌شود.

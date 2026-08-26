# گزارش پاک‌سازی commit و انتشار GitHub

تاریخ: 2026-08-26  
Run: `STAB-GIT-R01`  
وضعیت: `COMPLETE / PUSH_VERIFIED / MAIN_UNCHANGED`

## مجوز و هدف

کاربر پاک‌سازی commit ایجادشده با PyCharm و push به GitHub را با شرط حفظ کامل لاگ‌ها و مراحل تأیید کرد. شاخهٔ `main` نباید تغییر کند و انتشار فقط روی شاخهٔ تازهٔ `codex/stabilization-g09` انجام می‌شود.

## ممیزی commit اولیه

- commit اولیه: `f4464ef8bc971462ffdc61c82d0b158a1d3f3660` روی شاخهٔ `stabilization`.
- پیام اولیه با دامنهٔ واقعی تغییر همسو نبود.
- 7213 فایل در commit بود؛ 6068 فایل cache/temp و 100 archive/binary، عمدتاً ZIPهای basetemp، شناسایی شد.
- root operational file، DB واقعی، `bridge.json` و `.env` واقعی در commit دیده نشد.
- یک high-confidence secret pattern فقط در `tests/test_g07_release_packaging.py` و متعلق به fixture مصنوعی adversarial بود.
- commit تازه روی GitHub نبود. مخزن جاری فقط remote محلی `legacy` داشت؛ GitHub `EitaaDesktop/main` هنوز روی `a4df3ec...` بود و branch `stabilization` نداشت.

## حفاظت بازیابی

پیش از هر پاک‌سازی، شاخهٔ `codex/backup-pycharm-f4464ef` روی hash کامل commit اولیه ساخته شد. هیچ فایل محلی حذف نمی‌شود؛ فایل‌های موقت فقط با `git rm --cached` از snapshot قابل انتشار خارج خواهند شد.

## سیاست پاک‌سازی

این scopeها از GitHub حذف ولی روی دیسک حفظ می‌شوند: top-level Pytest/Codex temp، `.tmp`، `.test-tmp`، کپی third-party تحقیقاتی `Bale`، `prompt_out.txt`، فایل‌های `*.backup` و اسکریپت‌های یک‌بارمصرف extract/find/fix/gen/read/test/update و screenshot. اسناد `docs/project-memory`، گزارش‌ها، handoff، source، tests، scripts canonical عملیاتی، UI، installer و wheelهای offline مجاز حفظ می‌شوند.

نتیجهٔ cleanup، تست، commit و push در ادامهٔ همین گزارش و Ledger ثبت خواهد شد.

## نتیجهٔ پاک‌سازی index

- candidate میانی نسبت به parent آخر 642 فایل داشت. پس از کشف چهار commit محلی روی مبنای GitHub و حذف cached-only اسکریپت‌های یک‌بارمصرف، candidate نهایی نسبت به `a4df3ec...` شامل 426 فایل است؛ temp/cache=0، operational root=0، DB=0، Bale top-level=0 و scratch/fix/backup=0.
- 177 فایل `docs/project-memory`، reports و handoff حفظ شدند.
- 14 فایل `application/bale_client` به‌عنوان source قرنطینه‌شدهٔ تاریخی در repository حفظ، ولی طبق قرارداد G-07 از release/wheel خارج می‌مانند. این cleanup توسعه یا فعال‌سازی Bale نیست.
- `.env.example` و `.env.multisite.example` template عمومی‌اند؛ `.env` واقعی وجود ندارد.
- تنها secret pattern همچنان fixture مصنوعی داخل تست adversarial بسته‌بندی است.
- پوشه‌های temp، کپی تحقیقاتی Bale و prompt روی دیسک وجود دارند ولی اکنون ignored و خارج از index هستند.

## رخدادهای ابزار ثبت‌شده

1. ساخت backup ref در sandbox فقط‌خواندنی `.git` با lock error رد شد؛ بدون side effect، همان فرمان با مجوز Git mutation تکرار و موفق شد.
2. script نخست طبقه‌بندی remote از نام رزروشدهٔ PowerShell `$Host` استفاده کرد و فقط خروجی تشخیصی را خراب کرد؛ هیچ Git state تغییر نکرد و نسخهٔ اصلاح‌شده remote محلی را تأیید کرد.
3. `ls-remote` نخست به‌علت محدودیت شبکهٔ sandbox رد شد؛ اجرای فقط‌خواندنی تأییدشده GitHub main و نبود commit/branch تازه را ثابت کرد.
4. الگوی cleanup نخست 171 فایل قدیمی `.phase*pytest*` را پوشش نداد؛ audit index آن‌ها را پیش از commit یافت و pass دوم فقط cached آن‌ها را خارج کرد.

هیچ‌یک از رخدادهای بالا فایل یا لاگ را حذف نکردند و همگی پیش از commit نهایی بسته شدند.

## reconciliation آرشیو پس از سیاست Git

`.gitignore` عضو allowlist انتشار است؛ dry-run پس از hardening content-set تازه داد. دو archive مستقل با file_count=282، SHA یکسان=`187ea793cc43db2cb4f427201ee845e6d997581aaf5d5094a9d5d227626ebf6b` و content-set=`6b9a37c1279923627b78b09935f6298c751302721322827d80a651406f0221ea` ساخته شدند. verifier/privacy هر دو سبز و finding صفر است. diff با archive G09E فقط `.gitignore` را changed و added/removed را صفر نشان داد؛ بنابراین wheel/source/fresh-install evidence منقضی نشد.

Artifactهای canonical تازه `artifacts/stabilization/GITPUBLISH_release_final_a.zip` و `GITPUBLISH_release_final_b.zip` با receiptهای متناظرند. این artifactها ignored و در GitHub commit نمی‌شوند؛ hash و receipt آن‌ها در اسناد ثبت است.

مرحلهٔ بالا snapshot میانیِ پیش از تکمیل فهرست اسکریپت‌های یک‌بارمصرف بود و برای حفظ ردپا تاریخی باقی می‌ماند. پس از policy نهایی، dry-run مقدار content-set=`43c67c2eba3c30c534c855119287793eeb2ae7fc8fc61ab7aed19ecfc6dc217a` داد. دو artifact نهایی `GITPUBLISH_release_final2_a/b.zip` با file_count=282 و SHA یکسان=`481ed1be889892dc2802fa2052c27ef9ef3078994e3cc377b1e1a1c59f3b3384` ساخته و بازگشایی شدند؛ privacy finding صفر است. مقایسهٔ manifest با archive میانی added=0، removed=0 و changed فقط `.gitignore` را نشان داد؛ بنابراین source/UI/wheel/dependency و شاهد fresh-install تغییری نکرده است. از این نقطه final2 canonical و final_a/b شاهد تاریخی‌اند.

## کنترل کیفیت پیش از commit

- full Backend با cache خاموش و basetemp کنترل‌شده: collect=`656` و `656/656 PASS`، exit code صفر.
- TypeScript check و UI/Electron observability هر دو PASS و exit code صفر.
- تست‌های بسته‌بندی در اجرای فرعی نخست به‌علت `PermissionError` پوشهٔ temp سراسری ویندوز پیش از اجرای testها متوقف شدند؛ این رخداد محصولی نبود. retry با basetemp داخل `artifacts/stabilization` برابر `15/15 PASS` شد و همین 15 تست در full suite نیز سبز بودند.
- refresh اسناد، memory integrity، stale check، link check، JSON parse و package dry-run همگی PASS؛ dry-run همچنان 282 فایل و content-set=`43c67c2e...` است.
- هیچ عملیات Live، Provider، Bale، ارسال پیام، دادهٔ عملیاتی یا تغییر `main` انجام نشد.

## commit تمیز و حفاظت تاریخچه

- snapshot پیش از reset نرم با tree=`5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d` ثبت شد.
- reset فقط `--soft` تا GitHub base=`a4df3ecf2bcd4ab658c5361afdc287444694fcd2` بود؛ tree پس از reset نیز دقیقاً `5a7f4067...` ماند و unstaged tracked file صفر بود.
- چهار commit محلی قبلی همچنان از `codex/backup-pycharm-f4464ef` با رأس `f4464ef8...` قابل بازیابی‌اند؛ هیچ ref پشتیبان، لاگ یا فایل محلی حذف نشد.
- commit تمیز=`fca3ea72c54c0b7226f4dbabc54b4684e1215513`، parent=`a4df3ec...`، message=`chore(stabilization): complete G00-G09 offline acceptance` و files=426 است.
- شاخهٔ مستقل `codex/stabilization-g09` روی commit تمیز ساخته و فعال شد؛ `main` دست‌نخورده و push هنوز انجام نشده است.
- lookup نخست tree با syntax دارای brace در PowerShell فقط با parser error شکست خورد؛ جایگزین فقط‌خواندنی `git show --format=%T` همان hash مورد انتظار را برگرداند و هیچ state تغییر نکرد.

## انتشار GitHub و راستی‌آزمایی

- remote تازهٔ `origin` به `https://github.com/gprsm/EitaaDesktop.git` افزوده شد؛ remote محلی `legacy` حفظ شد.
- pre-push live check: GitHub main=`a4df3ec...` و branch مقصد absent بود.
- فقط `codex/stabilization-g09` push و upstream همان شاخه تنظیم شد؛ push موفق بود و GitHub لینک ساخت Pull Request را برگرداند.
- post-push live check: remote branch=`66f7beaca6a2cd0a67c54ec5705dcf5c381a8e9f` و main همچنان `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` است.
- این بخش در commit مستندی پس از push ثبت می‌شود و سپس همان شاخه یک بار دیگر push/verify خواهد شد؛ hash نهایی remote به‌علت همین commit مستندی متأخر با مقدار بالا متفاوت خواهد بود و در خروجی closure گزارش می‌شود. هیچ force-push یا تغییر main انجام نمی‌شود.

## closure انتشار

- commit ثبت نتیجهٔ push=`1f0f546b7532c5d856f82552f1abd69f8e337a10` به‌صورت push عادی منتشر و live remote روی همان hash تأیید شد؛ main همچنان `a4df3ec...` بود.
- tracking محلی به‌طور مستقل از config تأیید شد: remote=`origin` و merge ref=`refs/heads/codex/stabilization-g09`؛ tracked worktree clean است.
- lookup اختیاری upstream با shorthand=`@{u}` به‌علت PowerShell hash-literal parser error بدون state change رد شد؛ retry از config و status موفق بود.
- نتیجهٔ Run: cleanup، backup، archive reconciliation، full validation، commit تمیز، push و verify کامل است. شاخهٔ backup محلی حفظ شده، artifactهای تاریخی حذف نشده‌اند، main تغییر نکرده و هیچ force-push انجام نشده است.
- commit همین closure پس از کنترل اسناد روی همان شاخه push می‌شود؛ hash نهایی آن در تحویل کاربر اعلام خواهد شد تا خودارجاعی hash داخل commit ایجاد نشود.

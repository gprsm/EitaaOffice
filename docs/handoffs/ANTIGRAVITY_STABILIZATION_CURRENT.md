# Handoff جاری تثبیت برای AntiGravity و Codex

## closure فنی G-10 — timeline قدیمی گروه منتخب

- گزارش کاربر دربارهٔ نمایش پیام‌های حدود یک ماه قبل بررسی شد. catalog و SQLite به‌صورت فقط‌خواندنی و بدون ثبت عنوان/شناسه/متن نشان دادند sync و persistence تا همان روز جاری‌اند؛ پس مشکل Provider یا «منتخب» نبود.
- علت F-049 در `ui/src/ui33-runtime-patch.js` بود: checkpoint موقعیت مطالعه، `before_id/limit` درخواست عادی صفحهٔ نخست را بازنویسی می‌کرد. این بازنویسی حذف شد و request اکنون با `originalFetch(input, init)` دست‌نخورده ارسال می‌شود؛ scroll restoration صرفاً concern نمایشی باقی ماند.
- RED=`1 failed / 5 passed`، contract GREEN=`1/1`، targeted=`11/11`، full Backend=`657/657` با skip صفر، تمام ۹ runner UI، TypeScript و build 1015-module سبزند. source/dist patch SHA یکسان=`6de1ad48...` است.
- archiveهای محلی نهایی G-10 بایت‌یکسان، 282فایلی و دارای SHA=`077d316d...`، content-set=`36012dbb...` و privacy finding صفرند.
- Computer Use پیش از انتخاب پنجره/input سه بار با خطای زیرساختی path-not-found شکست خورد؛ تأیید بصری کاربر باقی است. هیچ پیام آزمایشی، login/OTP، WordPress، Bale یا write دادهٔ عملیاتی انجام نشد.
- مرجع: `docs/reports/stabilization/G10_SELECTED_GROUP_STALE_TIMELINE_REPAIR_REPORT_2026-08-26.md`؛ Ledger=`V-158`؛ Run=`STAB-G10-R01`.

## دستور دائمی انتشار سناریوهای نهایی

- از 2026-08-26، پس از نهایی‌شدن و عبور تست‌های هر سناریو، Agent مجاز و موظف است snapshot همان سناریو را با commit دقیق روی شاخهٔ کاری اختصاصی GitHub push و local/remote hash را verify کند.
- این مجوز شامل push/merge مستقیم `main`، force-push یا انتشار snapshot ناقص/قرمز/دارای دادهٔ عملیاتی نیست؛ جزئیات الزام‌آور در `AGENTS.md` و `CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md` ثبت است.

## انتشار GitHub بسته‌شده — checkpointهای تاریخی

- closure نهایی Run=`STAB-GIT-R01` با remote hash=`89f3551f...` verify شد؛ GitHub main=`a4df3ec...` بدون تغییر و backup محلی محفوظ ماند. سطرهای زیر مسیر checkpointها را برای جلوگیری از حذف تاریخ نگه می‌دارند.

- Run=`STAB-GIT-R01`: commit اولیه PyCharm با hash=`f4464ef8...` شامل 7213 فایل و بیش از 6000 temp/cache بود و هنوز روی GitHub نبود.
- backup بازیابی‌پذیر `codex/backup-pycharm-f4464ef` ساخته شد؛ هیچ لاگ یا فایل محلی حذف نمی‌شود.
- cleanup فقط از index و روی شاخهٔ انتشار تازه انجام می‌شود؛ `main` دست‌نخورده می‌ماند.
- گزارش جاری: `docs/reports/stabilization/GIT_PUBLISH_CLEANUP_AND_PUSH_REPORT_2026-08-26.md`؛ Ledger=`V-149`.
- candidate میانی پس از دو pass cached-only برابر 642 فایل بود؛ pass نهایی اسکریپت‌های یک‌بارمصرف را نیز فقط از index خارج کرد و نامزد نسبت به مبنای GitHub اکنون 426 فایل است. temp/cache، operational root، DB، Bale top-level و scratch صفر و engineering logs حفظ شده‌اند؛ Ledger=`V-150/V-152`.
- `.gitignore` عضو release بود؛ archive میانی SHA=`187ea793...` تاریخی و دو archive canonical نهایی با SHA=`481ed1be...` و content-set=`43c67c2e...` ساخته شدند. privacy/determinism سبز و diff محتوایی فقط gitignore است؛ Ledger=`V-151/V-152`.
- کنترل پیش از commit سبز است: full Backend=`656/656`، TypeScript و Observability PASS، package retry کنترل‌شده=`15/15` و تمام کنترل‌های اسناد PASS؛ Ledger=`V-153`. commit و push هنوز pending‌اند.
- commit تمیز `fca3ea72...` با parent مستقیم GitHub main و tree آزموده‌شده=`5a7f4067...` ساخته شد؛ backup کامل `f4464ef8...` باقی است و شاخهٔ فعال=`codex/stabilization-g09`. فقط push pending است؛ Ledger=`V-154`.
- push اولیهٔ `codex/stabilization-g09` موفق و remote hash=`66f7beac...` شد؛ GitHub main همچنان `a4df3ec...` است. commit مستندی final و verify دوم باقی است؛ Ledger=`V-155`.
- commit مستندی دوم=`1f0f546b...` push و live verify شد؛ tracking با origin برقرار، worktree tracked clean، main=`a4df3ec...` ثابت و Run انتشار Git بسته است. فقط commit همین closure با push عادی و اعلام hash در گفت‌وگو باقی می‌ماند؛ Ledger=`V-156`.

## closure فنی G-09-E — مرجع جاری

- G-00 تا G-09 کامل و توسط کاربر پذیرفته شده‌اند؛ snapshot=`USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED`.
- archive نهایی E با SHA=`6ff12e2b...` و content-set=`d60b10ea...` دو بار بایت‌یکسان ساخته شد؛ privacy finding صفر، extract/fresh-install no-index و wheel parity 90/0 drift سبزند. archiveهای B پس از تغییر Architecture تاریخی‌اند.
- full Backend جاری=`656/656` و skip صفر؛ تمام ۹ runner UI، TypeScript و build 1015-module سبزند.
- F-005/F-006/F-045 بسته‌اند؛ F-039 commit pending، F-013 nonblocking و OBS-008 deferred باقی‌اند.
- هیچ عملیات Live، Provider، Bale، دادهٔ عملیاتی، نصب سیستم/کاربر یا Git mutation انجام نشد. code-sign، Windows visual و real-user installer دروازه‌های مستقل‌اند.
- گزارش نهایی: `docs/reports/stabilization/G09_FINAL_ACCEPTANCE_AND_HANDOFF_REPORT_2026-08-26.md`؛ Ledger=`V-146`؛ Run=`STAB-G09-R01`.
- artifact canonical: `artifacts/stabilization/G09E_release_final_a.zip` و `G09E_release_final_b.zip` با receiptهای متناظر؛ Ledger نهایی=`V-147`.

## سابقهٔ closure G-08-E (با G-09 جایگزین شده)

- G-08 و F-048 در سطح `OFFLINE_AUTOMATED_ACCEPTED` بسته‌اند؛ full Backend نهایی=`656/656` و skip صفر، TypeScript و UI/Electron Observability سبزند.
- full نخست فقط wheel پایان G-07 را با mismatched=6 رد کرد؛ pre-image حفظ و دو build آفلاین تازه با SHA=`9408596d...`، 90 source و zero drift یکسان شدند. package+G08=`28/28`.
- archive نهایی G-07 پس از تغییرهای G-08 تاریخی است؛ G-09 باید archive/dry-run/verifier/fresh-install تجمیعی و پذیرش نهایی اسناد را تکرار کند.
- این وضعیت تاریخی پایان G-08 بود؛ G-09 اکنون دامنهٔ خودکار را کامل کرده است. محدودیت Live/Provider/Bale/data/Git همچنان برقرار است.

## وضعیت G-09-A

- بازهٔ پنج‌دقیقه‌ای بدون پیام توقف پایان یافت و G-09 شروع شد.
- hash audit بدون drift و package dry-run برابر 282 فایل، content-set=`cf055cd4...` و write صفر است.
- B دو archive تازهٔ artifacts را با verifier/privacy/reproducibility می‌سازد؛ هیچ نصب/انتشار واقعی مجاز نیست.

## نتیجهٔ G-09-B

- دو archive تازه هرکدام 282 فایل مجاز دارند و با SHA=`a637250e...` و content-set=`cf055cd4...` بایت‌یکسان‌اند.
- verifier داخلی و بازبینی مستقل: hash/order/manifest سبز، duplicate/case-collision/forbidden/private-key/JWT finding همگی صفر.
- attempt نخست package tests فقط به Temp پیش‌فرض غیرقابل‌دسترسی `3 passed / 12 setup errors` شد؛ retry ایزوله بدون تغییر کد `15/15 passed` است.
- G-09-C باید archive A را زیر artifacts استخراج و fresh-install آفلاین را انجام دهد؛ هیچ نصب سیستمی یا عملیات Live مجاز نیست.

## نتیجهٔ G-09-C

- archive A به‌صورت ایزوله استخراج شد: 283 فایل، required=`15/15`، Bale client=0 و self dry-run=282/بدون write.
- wheel parity=`90 source / zero drift / SHA 9408596d...` و compileall سبز است.
- fresh venv فقط از wheelهای archive و با no-index نصب شد؛ runtime checker، pip check، import ایزوله، Catalog=103 و چهار entrypoint سبزند.
- یک missing اولیه فقط مسیر قدیمی Event Catalog در checklist دستی بود و با مسیر canonical، بدون تغییر محصول، بسته شد.
- G-09-D اکنون همهٔ قراردادهای UI، build و تجمیع شواهد Backend را ادامه می‌دهد.

## نتیجهٔ G-09-D

- full Backend در اجرای نخست `656/656` و skip صفر؛ collect-only مستقل=656.
- هر ۹ runner UI، TypeScript و build 1015-module سبزند؛ warning chunk حدود 795kB غیرمسدودکننده و تاریخی است.
- G08 scanner/privacy contracts در full جاری و archive privacy scan صفر یافته است؛ هیچ log واقعی اسکن نشد.
- status فقط read-only بود؛ worktree dirty عمدی normalize نشد و root operational scope row=0 است.
- G-09-E فقط closure و همسوسازی نهایی اسناد/وضعیت انتشار را ادامه می‌دهد.

## روند ثبت‌شدهٔ G-08-A

- G-07/F-042 بسته و G-08 پس از بازهٔ توقف خودکار آغاز شد.
- ممیزی، scanner تک‌حساب hard-coded، نبود health برای failure نوشتن RuntimeLogger و نبود retention/disk-health محدود را به F-048 متصل کرد.
- تست تازهٔ `test_g08_observability_completion.py` روی دادهٔ کاملاً مصنوعی `4/4 failed` و RED معتبر است؛ test SHA=`1644076e...`.
- G-08-B باید ابتدا scanner چندحسابی/rotation را با report opaque و malformed fail-closed سبز کند. C lifecycle/catalog و D write-health/retention/Support Bundle را ادامه می‌دهند؛ E full regression/closure است.
- هیچ runtime/diagnostics/config/account واقعی، Provider، Bale، شبکه یا Git mutation لمس نشده است.

## نتیجهٔ G-08-B

- scanner چندحسابی/rotation با scope ترتیبی و گزارش path/id/value-free پیاده‌سازی شد؛ malformed/UTF-8/missing/read/symlink fail-closed است.
- targeted=`2/2` و related=`18/18`؛ scanner SHA=`a0c28c12...` و test SHA=`39228757...`.
- هیچ اسکن Live انجام نشد. G-08-C برای catalog/background/lifecycle خودکار ادامه دارد.

## نتیجهٔ G-08-C

- چهار RED catalog/background/manual failure با چهار GREEN بسته شد؛ related=`98/98` و Catalog=`102`.
- generic background متوازن/correlated و content-index/read-receipt/startup/shutdown/auth-close قابل مشاهده‌اند؛ پیام خام exception ثبت نمی‌شود.
- دو failure در related attempt نخست فقط REDهای برنامه‌ریزی‌شدهٔ D بودند؛ دامنهٔ صحیح C بدون retry محصولی `98/98` است.
- G-08-D اکنون write-health، retention/disk-health و Support Bundle adversarial را ادامه می‌دهد.

## نتیجهٔ G-08-D

- write failure مستقیم و swallowed logging هر دو در health counter امن دیده می‌شوند؛ endpoint health path-free است.
- retention current log را حفظ و فقط rotation عددی را با age/count/budget محدود می‌کند؛ disk summary فقط عددی است.
- Support Bundle JSONL ناقص/نام خصمانه را بدون نشت عادی/opaque می‌کند؛ G08=`13/13` و related=`78/78`.
- هیچ runtime واقعی prune یا scan نشد. G-08-E full regression/closure را خودکار ادامه می‌دهد.

وضعیت: `G-09 COMPLETE / USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE`  
آخرین ازسرگیری: 2026-08-26T18:03:00+03:30  
آخرین checkpoint: 2026-08-26T21:54:16.9907168+03:30  
Agent نویسنده: `Codex`  
آخرین Run بسته: `STAB-G09-R01`  
Run جاری: `NONE`  
آخرین زیرمرحلهٔ بسته: `G-09 / USER_ACCEPTED / FINAL_CLOSURE`  
Goal فعال: `NONE / EXTERNAL_RELEASE_GATES_ONLY`

## دستور کاربر

تمام مشکلات شناخته‌شده باید فازبه‌فاز و یکی‌یکی با لاگ دقیق، تست هدفمند، regression و نتیجهٔ کامل اصلاح شوند. AntiGravity ممکن است پس از توقف Codex ادامه دهد؛ هم‌زمانی نوشتن وجود ندارد.

## وضعیت واقعی

- G-00 تا G-09 کامل و پذیرفته شده‌اند. F-041/F-042/F-043/F-044/F-048 و F-005/F-006/F-045 بسته‌اند؛ فقط دروازه‌های بیرونی انتشار باقی‌اند.

## نتیجهٔ G-05-A

- thread ساعتی API با target کنترل‌شده واقعاً start شد و پس از `close()` زنده بود؛ خود تست آن را release/join کرد تا artifact یتیم باقی نماند.
- event مورد انتظار scheduler-disabled وجود نداشت و source هنوز `_run_auto_indexer`/`bridge-auto-indexer` را داشت.
- هر پنج route و method ایندکس دستی در source باقی و قرارداد manual PASS شد.
- نتیجه=`1/4 passed`, `3/4 failed`؛ basetemp=`artifacts/stabilization/pytest-g05a-r01-red-a`؛ بدون failure محیطی یا retry.
- گزارش: `docs/reports/stabilization/G05A_AUTO_INDEX_LIFECYCLE_RED_REPORT_2026-08-26.md`؛ Ledger=`V-122`؛ Run=`STAB-G05-R01`.
- ادامهٔ خودکار: G-05-B scheduler ناقص را fail-closed حذف، event امن اضافه و manual index را حفظ می‌کند.

## نتیجهٔ G-05-B

- startup thread و loop `_run_auto_indexer` حذف شدند؛ بنابراین `close()` دیگر thread یک‌ساعته‌ای برای توقف ندارد و orphan مربوط به F-043 ساخته نمی‌شود.
- event cataloged `content_auto_index_scheduler_skipped` با result=`rejected`، reason امن، correlation و دو field allowlisted ثبت می‌شود.
- APIهای manual content index بدون تغییر باقی ماندند.
- اختصاصی=`4/4`؛ regression مرتبط content-index/account-runtime/observability/Application/AppUser/clean-install=`76/76`؛ هر دو با basetemp تازه و بدون retry.
- گزارش: `docs/reports/stabilization/G05B_AUTO_INDEX_SAFE_DEFAULT_GREEN_REPORT_2026-08-26.md`؛ Ledger=`V-123`.
- ادامهٔ خودکار: C تکرار startup/close و نبود انباشت thread/correlation drift را adversarial می‌سنجد.

## نتیجهٔ G-05-C

- سه چرخهٔ متوالی API start/close تعداد threadهای `bridge-auto-indexer` را تغییر نداد.
- دقیقاً سه event scheduler-skipped با correlation یکتا ثبت شد؛ fields فقط mode، availability ایندکس دستی و request_id بودند و هیچ account/private scope نداشتند.
- G-05 و کل observability contract در یک اجرای تازه=`11/11 passed`؛ بدون retry/failure محیطی.
- فایل محصول از B تغییر نکرد؛ فقط یک guard آزمون تازه افزوده شد.
- گزارش: `docs/reports/stabilization/G05C_AUTO_INDEX_LIFECYCLE_ADVERSARIAL_REPORT_2026-08-26.md`؛ Ledger=`V-124`.
- ادامهٔ خودکار: D regression گسترده lifecycle/API را بدون تکرار بی‌دلیل suiteهای نامرتبط اجرا می‌کند.

## نتیجهٔ G-05-D

- ۱۴ suite مرتبط شامل G-05، content index، account/application lifecycle، clean-install، diagnostics/observability، Phase 10-B/D، Phase 11 onboarding/B1/B2 اجرا شدند.
- نتیجه=`143/143 passed` با basetemp تازه؛ collect-only نیز 143 و exit code صفر.
- هیچ retry، failure محیطی یا تغییر source/test در D وجود نداشت.
- گزارش: `docs/reports/stabilization/G05D_AUTO_INDEX_BROAD_REGRESSION_REPORT_2026-08-26.md`؛ Ledger=`V-125`.
- ادامهٔ خودکار: E full Backend، TypeScript/Observability، ممیزی معیار خروج و closure مشروط F-043 را انجام می‌دهد.

## نتیجهٔ فنی G-05-E

- full Backend در اجرای نخست=`625/625 passed`؛ collect-only نیز 625.
- TypeScript و UI/Electron Observability هر دو exit code صفر.
- هیچ failure، retry یا patch ثانویه در E وجود نداشت؛ هش source/test با checkpointهای B/C ثابت است.
- معیار فنی G-05 کامل و F-043 بسته است؛ کنترل اسناد/discoverability پیش از اعلام توقف یا ورود G-06 باقی است.
- گزارش نهایی: `docs/reports/stabilization/G05_AUTO_INDEX_LIFECYCLE_STABILIZATION_FINAL_REPORT_2026-08-26.md`؛ Ledger=`V-126`.

## closure نهایی G-05

- generator، memory integrity، stale check، link check و targeted diff check همگی exit code صفر.
- گزارش نهایی در REPORTS_INDEX discoverable و hash آن در V-126/S06 ثبت است.
- G-05 کامل و F-043 در سطح `OFFLINE_AUTOMATED_ACCEPTED` بسته است؛ پروژه همچنان `NOT_RELEASE_READY` است.
- طبق دستور کاربر، پس از checkpoint کامل پنج دقیقه فرصت توقف وجود دارد؛ در نبود پیام، G-06 خودکار با audit وضعیت جاری F-042 شروع می‌شود.

## نتیجهٔ G-06-A

- بازهٔ پنج‌دقیقه‌ای بدون پیام توقف پایان یافت و G-06 طبق مجوز کاربر آغاز شد.
- Phase 10 local activation پنج assertion اول را PASS و assertion ششم را به‌علت جست‌وجوی تعریف `normalizeLoginCodeInput` در `App.tsx` FAIL کرد؛ helper اکنون از `utils/helpers.tsx` import می‌شود. runner روی failure source کامل App را dump کرد؛ source فاقد credential/PII عملیاتی است، اما verbosity ثبت شد.
- guard تازه پس از اصلاح دو خطای fixture/audit برابر `2/3 passed`, `1/3 failed` شد؛ empty test و marker نامعتبر هر دو PASS و فقط import contract RED است.
- هشت runner دیگر scroll/grouped-media/Phase9/observability/Phase11/mobile-auth همگی exit code صفر دارند.
- رخدادهای غیرمحصولی ثبت‌شده: quoting PowerShell، wildcard ویندوز، BOM reader و حدس پسوند helper؛ هیچ‌کدام failure محصول نبودند.
- گزارش: `docs/reports/stabilization/G06A_TEST_CONTRACT_RED_REPORT_2026-08-26.md`؛ Ledger=`V-127`؛ ادامهٔ خودکار B.

## نتیجهٔ G-06-B

- runner اکنون `src/utils/helpers.tsx` را مستقیم می‌خواند و import/export canonical را می‌سنجد؛ assertion محل قدیمی حذف شد.
- assertionهای import/export با boolean+message محدود هستند و در شکست بعدی source کامل App/helper را چاپ نمی‌کنند.
- guard Python=`3/3`، Phase 10=`7/7`، Backend مرتبط auth/application=`66/66` و mobile-auth static سبزند.
- فقط runner و guard test تغییر کردند؛ `App.tsx` و `helpers.tsx` بدون تغییر باقی ماندند.
- گزارش: `docs/reports/stabilization/G06B_PHASE10_TEST_CONTRACT_GREEN_REPORT_2026-08-26.md`؛ Ledger=`V-128`؛ ادامهٔ خودکار C.

## نتیجهٔ G-06-C

- هر ۹ runner رابط کاربری در اجرای نخست exit code صفر داشت: scroll=`10/10`، grouped-media=`16/16`، Phase9 workspace=`12/12` و `15/15`، Phase9 acceptance=`13/13`، Phase10=`7/7`، observability=PASS، Phase11 onboarding=`7/7`، Phase11-B2=`6/6` و mobile-auth=PASS.
- TypeScript check و build محلی هر دو سبزند؛ build تعداد 1015 module را تبدیل کرد و package/installer اجرا نشد.
- Vite هشدار غیرمسدودکنندهٔ chunk اصلی `794.74 kB` داد؛ این هشدار failure قرارداد G-06 نیست و برای پیگیری عملکردی حفظ شد.
- تلاش نخست خواندن Git status به‌علت dubious ownership sandbox رد شد؛ retry فقط با `safe.directory` فرمانی و بدون تغییر config انجام شد. dirty بودن عمدی پروژه تأیید و هیچ Git mutation انجام نشد.
- گزارش: `docs/reports/stabilization/G06C_UI_CONTRACTS_TYPESCRIPT_BUILD_REPORT_2026-08-26.md`؛ Ledger=`V-129`؛ ادامهٔ خودکار D.

## نتیجهٔ G-06-D

- ۳۵ suite آفلاین مرتبط با G-04/G-05/G-06، clean install، account/application/auth، diagnostics/observability، content index و Phaseهای UI اجرا شد.
- نتیجه=`307/307 passed`، failure/error/skip صفر؛ collect-only مستقل نیز دقیقاً 307 تست را ثبت کرد.
- تنها warning، ناتوانی pytest cache در نوشتن nodeids به‌علت مجوز sandbox بود؛ basetemp آزمون سالم و exit code صفر است.
- collect-only quiet جمع کل را در سه سطر آخر نشان نداد؛ همان collection بدون quiet تکرار و عدد 307 قطعی شد. هیچ تست محصولی تکرار نشد.
- گزارش: `docs/reports/stabilization/G06D_BROAD_BACKEND_REGRESSION_REPORT_2026-08-26.md`؛ Ledger=`V-130`؛ ادامهٔ خودکار E.

## نتیجه و closure G-06-E

- full Backend در اجرای نخست با cacheprovider خاموش و basetemp تازه به ۱۰۰٪ رسید: `628/628 passed`، failure/error/skip صفر؛ collect-only مستقل نیز `628 tests collected` است.
- از C به بعد هیچ source/test/UI تغییر نکرد؛ بنابراین همهٔ ۹ runner UI، TypeScript و build محلی شاهد جاری همین snapshot هستند.
- guard نهایی: تست خالی صفر و skip/xfail بدون reason صفر. runner Phase 10 از helper واقعی import/export می‌خواند و source کامل را در assertion تازه dump نمی‌کند.
- حوزهٔ test contract در F-042 بسته است، ولی F-042 برای package allowlist/privacy scan تا G-07 باز می‌ماند؛ وضعیت پروژه `NOT_RELEASE_READY` است.
- گزارش نهایی: `docs/reports/stabilization/G06_TEST_CONTRACT_AND_REGRESSION_STABILIZATION_FINAL_REPORT_2026-08-26.md`؛ Ledger=`V-131`.
- پس از کنترل کامل اسناد، بازهٔ پنج‌دقیقه‌ای توقف آغاز می‌شود؛ در نبود پیام کاربر G-07-A خودکار شروع خواهد شد.

## نتیجهٔ G-07-A

- بازهٔ پنج‌دقیقه‌ای بدون پیام توقف پایان یافت و G-07 با پنج زیرمرحلهٔ A تا E آغاز شد.
- تلاش نخست test collection با SyntaxError متوقف شد: فایل موجود `package_clean.py` در واقع UTF-16LE و دارای 1826 NUL است، هرچند ابزار خواندن متن آن را ظاهراً عادی نشان می‌دهد.
- loader فقط برای audit به UTF-16 fallback داده شد؛ RED رفتاری سپس همهٔ هشت contract را شکست داد. در fixture مصنوعی، packager blacklist واقعاً `prompt_out.txt` و `probe.json` را داخل ZIP گذاشت.
- contractهای مفقود: allowlist canonical، dry-run بدون write، archive deterministic+receipt، privacy scan کم‌افشا و رد سه نام traversal/noncanonical.
- تلاش دوم source bytes را در assertion encoding چاپ کرد؛ assertion محدود شد. تلاش سوم canonical=`0/8 failed` با basetemp تازه و بدون دادهٔ واقعی است.
- گزارش: `docs/reports/stabilization/G07A_RELEASE_PACKAGING_RED_REPORT_2026-08-26.md`؛ Ledger=`V-132`؛ ادامهٔ خودکار B.

## نتیجهٔ G-07-B

- apply_patch نتوانست pre-image نامعتبر UTF-16 را بخواند؛ مسیرهای دقیق در workspace کنترل و فایل شکسته به `artifacts/stabilization/G07A_package_clean_utf16_preimage_be8a9cf2.bin` منتقل شد. هش آن با pre-image A برابر است و بازیابی ممکن است.
- `package_clean.py` تازه UTF-8 با NUL صفر است و فقط root/files/scopes صریح را انتخاب می‌کند؛ scratch/fix/probe، Bale، test، project-memory و تمام داده/config/session/runtime خارج‌اند.
- manifest داخلی شامل نام/hash/size و receipt بیرونی شامل hash archive است؛ ZIP timestamp/order ثابت، duplicate/case collision/traversal/backslash/absolute/size و secretهای high-confidence رد می‌شوند.
- compile=PASS، targeted=`8/8`، مرتبط release/baseline/clean-install/docs=`21/21`؛ همه در اجرای نخست پس از patch سبز.
- dry-run واقعی=`296` فایل، content-set SHA ثبت‌شده و هر دو output/receipt برابر absent؛ archive واقعی در B ساخته نشد.
- یک wildcard rg ویندوزی هنگام کشف dependency اسکریپت exit code 2 داشت؛ retry با `-g` موفق و هیچ تغییر ایجاد نکرد.
- گزارش: `docs/reports/stabilization/G07B_RELEASE_ALLOWLIST_GREEN_REPORT_2026-08-26.md`؛ Ledger=`V-133`؛ ادامهٔ خودکار C.

## نتیجهٔ G-07-C

- سه guard تازهٔ case-insensitive collision، entry hash tamper و حفظ خروجی موجود بدون `force` افزوده شد؛ کل adversarial package suite=`11/11 passed`.
- دو archive واقعی فقط زیر artifacts و بدون overwrite ساخته شدند: هرکدام 296 فایل+manifest، 2,031,927 بایت و SHA-256 یکسان `3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903`.
- هر receipt با hash archive خود منطبق و content-set هر دو `bf8483fea77af8b29fbc922daf475916bfc05ed83c02eb4d931792b274f52a72` است؛ verifier مستقل هر دو را 296 تأیید کرد.
- اسکن نام نخست 13 false-positive داد، چون regex هر قطعهٔ میانی diagnostics/Bale/runtime را گرفت؛ بررسی نام‌ها نشان داد همگی source fail-closed/diagnostics یا wheelهای vendor بودند. rule فقط top-level شد و forbidden=0، collision=0 و manifest-last=true برای هر دو archive ثبت شد.
- یک invocation Python به‌علت quoting ناقص SyntaxError گرفت؛ retry ساده موفق شد و archiveها تغییر نکردند.
- گزارش: `docs/reports/stabilization/G07C_RELEASE_ADVERSARIAL_REPRODUCIBILITY_REPORT_2026-08-26.md`؛ Ledger=`V-134`؛ ادامهٔ خودکار D.

## نتیجهٔ G-07-D

- parity فقط‌خواندنی wheel جاری نشان داد `api.py` متفاوت و moduleهای جاری غایب‌اند. invocation نخست Python quoting error داشت؛ PowerShell ZIP audit موفق شد.
- تست parity ابتدا API guard مفقود را RED کرد؛ پس از افزودن guard، RED canonical=`12/13 passed`, یک failure واقعی با missing=57/mismatched=20 باقی ماند.
- wheel قدیمی با SHA واقعی `668a30c2...` در artifacts حفظ شد. نام backup نخست از hash تاریخی/منقضی Release Manifest گرفته و فوراً به prefix هش واقعی اصلاح شد.
- build استاندارد آفلاین به‌علت نبود `setuptools.build_meta` شکست خورد. builder stdlib موجود پارامتردار/deterministic شد و metadata/dependencies/چهار entrypoint را از `pyproject.toml` خواند؛ `build_wheel.bat` دیگر cache/egg-info را حذف نمی‌کند.
- نخستین wheel تازه 104 فایل و parity صفر drift داشت، اما fresh venv `pip check` سه dependency مفقود cryptography/httpx/websockets را نشان داد. هر سه فقط در `application/bale_client` شکسته و قرنطینه‌شده استفاده می‌شدند.
- release source و wheel آن subtree را حذف کردند، dependencyهای صرفاً آن از pyproject/metadata حذف و fail-closed Bale slot حفظ شد. دو wheel نهایی بایت‌یکسان با SHA=`de9dd96f...`، 90 فایل و zero drift ساخته شد.
- archive نهایی 282 فایل، SHA=`8b769488...` و content-set=`3c777df5...` دارد. extract: 15/15 فایل ضروری، Bale client=0، self-dry-run همان 282 و compile سبز.
- fresh venv تازه: نصب آفلاین dependency/core/bridge، runtime checker، `pip check` و import API/Event Catalog همگی exit code صفر. تست builder/package+Bale=`20/20` و regression مرتبط=`102/102`.
- گزارش: `docs/reports/stabilization/G07D_FRESH_INSTALL_REHEARSAL_REPORT_2026-08-26.md`؛ Ledger=`V-135`؛ ادامهٔ خودکار E.

## نتیجه و closure G-07-E

- full Backend در اجرای نخست=`643/643 passed`، failure/error/skip صفر؛ collect-only=643.
- TypeScript و UI/Electron Observability exit code صفر. build UI تکرار نشد، چون پس از G-06-C هیچ UI change/trigger وجود نداشت و `ui/dist` خارج از clean archive است.
- اسناد release، تصمیم معماری، Baseline، Specification، Structure، Security و Release Manifest با قرارداد allowlist/wheel/fresh-install هم‌سو شدند.
- دو archive نهایی پس از همین هم‌سویی هرکدام 282 فایل و SHA-256 یکسان `729a3d613f8e941c7b973af2e6433fb387b1f97fee2b4e07e72d196b79e2cb57` دارند؛ verifier=282، forbidden/collision=0 و receipt match سبز است.
- در checkpoint پایان G-07، پروژه به‌دلیل G-08/G-09 و code-sign/real installer acceptance هنوز `NOT_RELEASE_READY` بود؛ G-08 اکنون بسته و G-09 باقی است.
- گزارش نهایی: `docs/reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md`؛ Ledger=`V-136`.
- پس از کنترل نهایی اسناد، پنج دقیقه فرصت توقف است؛ در نبود پیام کاربر G-08-A خودکار آغاز می‌شود.
- ممیزی V-103: Backend `587 collected / 585 passed / 2 failed`؛ دو شکست BOM در Bale slot.
- UI: TypeScript/observability سبز و Phase 11 onboarding=`7/7` است؛ Phase 10 helper drift مستقل باز می‌ماند.
- ریشهٔ `AntiGravity2` repository شاخهٔ `stabilization` است و به `legacy/main` متصل شده؛ index/stage/commit عمداً دست‌نخورده/باز است و status مبنای دامنهٔ تغییر نیست.
- داده‌ها، config، session، runtime، diagnostics و backups دست‌نخورده‌اند.
- Bale با حفظ F-046 به‌طور آفلاین fail-closed شده است؛ هیچ factory/capability/onboarding/runtime فعال ندارد.
- قرارداد متأخر نمایش کامل شماره rollback نمی‌شود؛ عدم نشت آن در log مستقل آزموده خواهد شد.

## وضعیت دقیق G-04-A

- اجرای G-04 به پنج بخش A تا E شکسته شد تا پس از هر بخش توقف و handoff مستقل ممکن باشد.
- فایل `tests/test_g04_identity_privacy_stabilization.py` سه قرارداد مستقل و دادهٔ کاملاً ساختگی دارد؛ مقدار کامل در پیام شکست یا اسناد ثبت نمی‌شود.
- نتیجهٔ هدفمند: `3 collected / 1 passed / 2 failed` با exit code 1. قرارداد نمایش canonical در مرز مجاز محصول PASS است.
- RED اول: دو تست تاریخی نام‌برده در `tests/test_coordinator_schema.py` هنوز فقط `pass` هستند.
- RED دوم: redaction فعلی نام‌های `phone_hint` و `display_hint` را در مجموعهٔ کلیدهای تلفن پوشش نمی‌دهد؛ این یک شکاف privacy مستقل از مجازبودن نمایش محصول است.
- در G-04-A هیچ فایل محصولی اصلاح نشد. `identity.py` و `redaction.py` بدون تغییر ماندند و full Backend تکرار نشد، زیرا این زیرمرحله عمداً test-first و قرمز است.
- گزارش: `docs/reports/stabilization/G04A_IDENTITY_PRIVACY_RED_REPORT_2026-08-26.md`؛ Ledger=`V-117`؛ Run=`STAB-G04-R01`.
- این فهرست هنگام پایان A شامل B تا E بود؛ اکنون B/C/D/E همگی بسته‌اند و F-044 closure دارد.
- هیچ migration/rollback واقعی، Provider/Login/OTP/Send، دادهٔ عملیاتی، توسعهٔ Bale یا Git mutation انجام نشد.

## نتیجهٔ G-04-B

- دو تست placeholder با دو قرارداد دارای assertion و نام صحیح جایگزین شدند؛ نام‌های قدیمی masking اکنون توسط guard ممنوع‌اند.
- تست persistence پذیرش display hint canonical کامل و تست مرز محصول حفظ مقدار canonical را ثابت می‌کنند.
- redaction مشترک اکنون `phone_hint` و `display_hint` را همانند دیگر نام‌های تلفن mask می‌کند.
- GREEN اختصاصی=`3/3`؛ regression مرتبط coordinator schema، diagnostics، observability و G-04 برابر `28/28`.
- فایل‌های محصول/تست تغییرکرده: `redaction.py`، `test_coordinator_schema.py` و `test_g04_identity_privacy_stabilization.py`؛ هش‌ها در V-118 ثبت شده‌اند.
- در پایان B، full Backend هنوز اجرا نشده و به E موکول بود. اکنون شاهد نهایی E برابر `620/620` است.
- گزارش مستقل: `docs/reports/stabilization/G04B_IDENTITY_REDACTION_GREEN_REPORT_2026-08-26.md`؛ Run=`STAB-G04-R02`؛ Ledger=`V-118`.

## نتیجهٔ G-04-C

- RED Backend=`2/2 failed`: validator با نام E.164 token-shaped identity را قبول می‌کرد و endpoint عمومی فیلد token را تا PhoneProtector می‌فرستاد.
- RED UI: Phase 11 onboarding پس از PASS assertion اول روی allowlist Backend شکست خورد و source کامل را dump کرد؛ این همان drift ثبت‌شدهٔ F-042 بود.
- اصلاح: validator تلفن فقط E.164 است؛ `masked_phone` branch token ندارد؛ endpoint فقط `provider/phone/label` را می‌پذیرد و descriptor غیر `phone_e164` را پیش از PhoneAccount رد می‌کند.
- GREEN هدفمند Backend=`2/2`؛ UI Phase 11 onboarding=`7/7`.
- regression مرتبط دو اجرا داشت: هفت suite identity/API/onboarding/runtime/provider=`90/90` و AccountAuth/Provider orchestration=`36/36`؛ مجموع=`126/126`.
- F-042 برای Phase 11 onboarding بسته شد، ولی برای Phase 10 helper drift و packaging باز است. F-044 نیز بعداً با full regression/finalization در E بسته شد.
- Bale همچنان configured/runtime/onboarding=false است؛ هیچ account kind، token auth، factory، capability یا کد Bale تازه ساخته نشد.
- گزارش مستقل: `docs/reports/stabilization/G04C_PUBLIC_ONBOARDING_IDENTITY_BOUNDARY_REPORT_2026-08-26.md`؛ Run=`STAB-G04-R03`؛ Ledger=`V-119`.
- در پایان C، full Backend اجرا نشده و `610/610` فقط snapshot پایان G-03 بود؛ شاهد جاری پس از E=`620/620` است.

## نتیجهٔ G-04-D

- پنج آزمون خصمانهٔ تازه در `tests/test_g04d_privacy_channels.py` چهار کانال Runtime Log، Audit، Diagnostic و Support Bundle به‌علاوه scanner را مستقل سنجیدند.
- RED معتبر=`5/5 failed`: identity/Bearer زیر کلید ناشناخته یا nested در Runtime/Diagnostic/Audit/Bundle باقی می‌ماند و scanner فقط تلفن ایران را تشخیص می‌داد.
- اصلاح: redaction عمومی pattern-scan E.164 جهانی/Bearer/provider-token دارد؛ Audit metadata پیش از hash/persistence و هنگام query/export sanitize می‌شود؛ bundle creator/scanner الگوی تلفن جهانی همسو دارند.
- GREEN اختصاصی=`5/5` با basetemp تازه.
- regression مرتبط سه اجرای مستقل و سبز داشت: `53/53`، `2/2` و `50/50`. هیچ retry یا failure محیطی رخ نداد.
- RuntimeLogger و Diagnostic manager مستقیماً تغییر نکردند؛ با استفاده از redaction مشترک hardening را دریافت کردند. فایل‌های تغییرکرده و هش‌ها در V-120 ثبت شده‌اند.
- هیچ ورودی عملیاتی یا Live خوانده نشد. bundle، Audit DB، log و diagnostics همگی مصنوعی و زیر basetemp بودند.
- گزارش مستقل: `docs/reports/stabilization/G04D_PRIVACY_CHANNELS_ADVERSARIAL_REPORT_2026-08-26.md`؛ Run=`STAB-G04-R04`؛ Ledger=`V-120`.
- در پایان D، full Backend/finalization باقی بود؛ G-04-E اکنون آن دروازه را با `620/620` و closure F-044 بسته است.

## نتیجهٔ G-04-E و closure نهایی

- معیارهای خروج و هش‌های A تا D با snapshot جاری تطبیق و drift_count=`0` ثبت شد. تلاش نخست hash audit دو مسیر حدسی ناموجود داشت؛ تکرار با مسیرهای کشف‌شده سبز و به‌عنوان خطای ابزار، نه محصول، ثبت شد.
- full Backend نخست=`618/620`: دو Process Worker به timeout ده‌ثانیه‌ای خوردند. همان دو node بلافاصله در isolation=`2/2` سبز شدند.
- full Backend دوم با basetemp تازه و بدون patch محصول=`620/620 passed` شد؛ دو failure نخست ازدحام زمانی full-suite طبقه‌بندی شدند و از تاریخچه حذف نشدند.
- TypeScript exit code صفر، UI/Electron Observability exit code صفر و Phase 11 onboarding=`7/7` است.
- G-04 کامل و F-044 در سطح `OFFLINE_AUTOMATED_ACCEPTED` بسته شد. هیچ فایل محصولی در E تغییر نکرد؛ فقط test execution و اسناد closure به‌روزرسانی شدند.
- گزارش مستقل: `docs/reports/stabilization/G04_IDENTITY_PRIVACY_STABILIZATION_FINAL_REPORT_2026-08-26.md`؛ Run=`STAB-G04-R05`؛ Ledger=`V-121`.
- پروژه `NOT_RELEASE_READY` است؛ G-05 تا G-09 و یافته‌های مستقل باقی‌اند.

## نتیجهٔ G-01

- checker دائمی UTF-8/control/duplicate-ID/Markdown اضافه شد و full pytest آن را اجرا می‌کند.
- RED repository=`143` نشانه؛ GREEN نهایی=`issue_count 0`.
- duplicateهای تاریخی به `LEGACY-...` منتقل و متن‌های غیرقابل‌بازیابی با provenance صریح ثبت شدند؛ هیچ متن ازدست‌رفته حدس زده نشد.
- suite هدفمند G-01=`5/5`؛ generator و link check سبز؛ گزارش‌های G-00/G-01 در `REPORTS_INDEX.md` قابل‌کشف‌اند.
- Baseline/Specification/finalization وضعیت جاری را `NOT_RELEASE_READY` و شواهد `590/590` را تاریخی اعلام می‌کنند.

## نتیجهٔ G-02

- RED معتبر اختصاصی=`4/4 failed`؛ GREEN اختصاصی=`5/5` و مرتبط=`21/21`.
- Backend کامل=`599/599`؛ دو شکست BOM قبلی بسته شدند.
- TypeScript/Observability و UI B2=`6/6` سبز.
- Bale descriptor: state=`implemented`، reference=`document:F-046`، اما configured/runtime/onboarding=false، capability/factory خالی و reason امن.
- Phase 11 onboarding هنوز روی allowlist assertion قدیمی شکست می‌خورد؛ به F-042/G-06 متصل است، نه G-02.

## وضعیت دقیق G-03 در توقف جدید

- تست تازه: `tests/test_clean_install_auth_stabilization.py` با چهار سناریوی کاملاً مصنوعی و بدون شبکه/OTP/ورود واقعی.
- RED معتبر پیش از patch: `4 collected / 4 failed`؛ علت‌ها دقیقاً bootstrap مدیر روی DB خالی، `app_auth_coordinator_missing`، نبود `challenge_id` در Legacy و نبود expiry binding بودند.
- دو رخداد غیرمحصولی نیز ثبت شدند: Temp پیش‌فرض pytest مجوز نداشت؛ یک test double اولیه فیلد اشتباه `PasswordMaterial` داشت. هر دو از RED محصول جدا و اصلاح شدند.
- patch اولیه اعمال شده: `LegacyAuthChallenge`، allowlist summary، bootstrap مدیر روی DB واقعاً خالی، initialize خودکار Coordinator، حالت محدود empty-bootstrap و الزام challenge id/stage/expiry در Legacy.
- هش‌های چهار فایل محصول پیش از ازسرگیری با V-111 تطبیق کامل داشتند؛ هیچ drift پنهان در patch محصول دیده نشد.
- اجرای نخست پس از patch `4 collected / 3 passed / 1 failed` بود. failure تنها به طول نامعتبر دادهٔ مصنوعی `PasswordMaterial` در test double مربوط شد؛ یک سطر fixture آزمون اصلاح شد و retry با basetemp تازه `4/4 passed` شد.
- هش نهایی تست `1e5be6e0bbb998b2de8fd6aca442a48df5f4ec224286c4b9bf2a8d8b1c565344` است؛ هش چهار فایل محصول بدون تغییر و در V-112 ثبت شده است.
- اسناد تولیدشونده refresh شدند و memory integrity، stale check و link check همگی exit code صفر دارند.
- G-03-B: چهار suite مرتبط AppAuth/API/AccountRuntime در یک اجرای ایزوله `57/57 passed` شدند؛ هیچ فایل source/test تغییر نکرد و هش‌های پیش/پس یکسان‌اند.
- پس از ثبت G-03-B، generator، memory integrity، stale check و link check همگی exit code صفر داشتند.
- G-03-C: پنج قرارداد adversarial/restart ابتدا `4/5` بودند؛ رکورد چندحسابی پس از گم‌شدن challenge در restart در `challenge_pending` می‌ماند. guard API اکنون آن را audit‌شده به `expired` می‌برد. GREEN اختصاصی=`5/5` و regression مرتبط=`81/81` است.
- تست‌های restart Legacy، password expiry/replay، supersession، wrong-stage/hostile-id و account reconciliation بدون Provider/Live اجرا شدند. فقط `api.py` و دو فایل آزمون تغییر کردند؛ هش‌ها در V-114 ثبت شده‌اند.
- پس از ثبت G-03-C، generator، memory integrity، stale check و link check همگی exit code صفر داشتند.
- G-03-D: full Backend ابتدا `607/608` بود؛ دو event جدید challenge خارج از catalog بودند. پس از ثبت امن آن‌ها، observability هدفمند=`6/6` و full Backend=`608/608` شد.
- TypeScript و UI/Electron observability هر دو exit code صفر دارند. Phase 10/11 drift مستقل F-042 بدون trigger تکرار نشد.
- پس از ثبت G-03-D، generator، memory integrity، stale check و link check همگی exit code صفر داشتند.
- G-03-E در audit معیار خروج دو شاهد جاافتادهٔ startup تکراری و installer rehearsal را یافت؛ acceptance تکمیلی `2/2` و Backend نهایی `610/610` سبز شدند.
- F-041 بسته و گزارش نهایی `docs/reports/stabilization/G03_CLEAN_INSTALL_AUTH_STABILIZATION_REPORT_2026-08-26.md` ثبت شد.
- گزارش در REPORTS_INDEX discoverable است و generator، memory integrity، stale check و link check همگی exit code صفر دارند.
- **هشدار مهم:** تکمیل G-03 و G-04 به‌معنای release readiness عمومی نیست؛ F-042/F-043 و G-05 تا G-09 بازند.
- هیچ فایل عملیاتی، config واقعی، DB/session واقعی، Provider، Git index/stage/commit/push یا عملیات Bale لمس نشد.

## رخداد ازسرگیری

- توقف قبلی به درخواست فوری کاربر انجام شد.
- Handoff توقف و V-106 نوشته شدند، اما generator فرصت اجرا نیافت.
- RED ازسرگیری: هر دو فرمان docs check با exit code 1، علت یگانه `STALE: docs/REPORTS_INDEX.md`.
- نتیجه: قرارداد همکاری و log توقف/ازسرگیری ثبت شد؛ `REPORTS_INDEX.md` refresh و هر دو docs check با exit code صفر سبز شدند.

## نتیجهٔ G-00

- `tests/test_stabilization_baseline.py`: `2/2` سبز پس از RED نبود module.
- snapshot امن: 613 فایل، archive SHA-256=`70908224926eb45791bdc504558478756328743f0a9f7b8355f19b30d73ca8ab`، forbidden top-level=`0`.
- Git: شاخهٔ `stabilization` و `legacy/main` به commit تاریخی یکسان متصل‌اند؛ مالک metadata اصلاح شد.
- global safe.directory تغییر نکرد. stage/commit/index normalization انجام نشد.
- گزارش: `docs/reports/stabilization/G00_TRACEABILITY_BASELINE_REPORT_2026-08-25.md`.

## ترتیب اصلاح

`G-00 → G-01 → G-02 → G-03 → G-04 → G-05 → G-06 → G-07 → G-08 → G-09`

## مشکلات اصلی

- F-039: Git traceability/baseline.
- F-040: Bale runtime و factory شکسته.
- F-041: clean-install و legacy challenge.
- F-042: test/package drift.
- F-043: auto-index lifecycle/observability؛ `CLOSED` در G-05-E.
- F-044: تست/اسناد قرارداد نمایش کامل؛ `CLOSED` در G-04-E.
- F-046: عدم rollback قراردادهای متأخر.

## مرز Git

ساخت baseline/hash و آماده‌سازی read-only مجاز است. `stage/commit/push` تا دستور صریح کاربر انجام نمی‌شود؛ Agent نباید این مرز را با reset/read-tree یا روش معادل دور بزند.

## اولین اقدام خودکار پس از بازهٔ توقف

1. G-06-A ابتدا F-042 و قراردادهای جاری را audit کند؛ موارد Bale BOM و Phase 11 onboarding که در G-02/G-04 بسته شده‌اند دوباره اصلاح نشوند.
2. Phase 10 helper drift، empty-test guard، skip count و دامنهٔ packaging مستقل را با REDهای جاری تفکیک کند.
3. G-06 نیز به زیرمرحله‌های checkpointدار شکسته و پس از هر بخش test/log/docs کامل ثبت شود.
4. هیچ build انتشار، package واقعی، Provider network، Login/OTP/Send، دادهٔ عملیاتی، توسعهٔ Bale یا Git mutation انجام نشود.

مرجع کامل: `docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md`.

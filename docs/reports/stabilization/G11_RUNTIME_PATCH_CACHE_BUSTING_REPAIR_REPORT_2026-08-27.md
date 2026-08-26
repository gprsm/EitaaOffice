# گزارش G-11 — اصلاح تحویل patch رابط و حذف cache قدیمی

تاریخ: 2026-08-27  
Run: `STAB-G11-R01`  
وضعیت: `COMPLETE / FULLY_TESTED / OFFLINE_ARTIFACT_GREEN / PUBLISHED_TO_WORKING_BRANCH / USER_VISUAL_RECHECK_PENDING`

## گزارش کاربر و مرز محرمانگی

کاربر پس از G-10 اعلام کرد گروه نمونهٔ منتخب همچنان آخرین پیام ۶ مرداد را نشان می‌دهد، در حالی که آخرین پیام واقعی ۴ شهریور است. عنوان واقعی گروه فقط برای تطبیق خواندنی storage استفاده شد و در این گزارش، Ledger، execution log یا خروجی آزمون ثبت نشده است. شناسهٔ حساب/peer، متن پیام، شماره، Token و مسیر حساس نیز ثبت نشدند. هیچ پیام آزمایشی، Login، OTP، WordPress، Bale یا write دادهٔ عملیاتی انجام نشد.

## تشخیص ماسک‌شده

- چهار peer file متناظر در دو scope تاریخی/جاری یافت شد.
- storage تاریخی 420 پیام داشت و بیشینهٔ تاریخ آن همان ۶ مرداد گزارش‌شده بود.
- storage حساب جاری برای همان peer دارای 674 پیام و بیشینهٔ تاریخ ۴ شهریور بود؛ 254 پیام پس از checkpoint تاریخی وجود داشت و catalog top با بیشینهٔ SQLite برابر بود.
- unread صفر و read boundary برابر top جاری بود؛ در نتیجه stale بودن دادهٔ جاری، sync عقب‌مانده یا نگاشت catalog علت نبود.
- probe نخست به‌اشتباه فیلد عمومی `id` را با catalog مقایسه کرد، در حالی که peer file canonical از `peer_id` استفاده می‌کند؛ نتیجهٔ mismatch کاذب بلافاصله کنار گذاشته شد. retry با loader رسمی، title/id/type/access hash را منطبق نشان داد. این خطای ابزار تشخیص بود و هیچ state را تغییر نداد.

## علت ریشه‌ای

G-10 بازنویسی `before_id/limit` را واقعاً از source حذف کرده بود، اما build سازگاری patch را همیشه با URL ثابت `/assets/ui33-runtime-patch.js` منتشر می‌کرد. هم‌زمان HTTP server هر asset غیر-index را با `public, max-age=31536000, immutable` پاسخ می‌داد. بنابراین Edge مجاز بود pre-image قدیمی patch را یک سال بدون revalidation اجرا کند. همان pre-image checkpoint ذخیره‌شده را دوباره روی `messages/list` اعمال و دقیقاً پنجرهٔ منتهی به ۶ مرداد را نمایش می‌داد.

این علت توضیح می‌دهد چرا restart قبلی Backend یا وجود فایل درست در `ui/dist` اثر نداشت: URL مرورگر تغییر نکرده بود.

## RED و اصلاح

RED تازه سه مرز را پوشش داد:

1. index باید نام `ui33-runtime-patch-<content-hash>.js` داشته باشد و hash با محتوای source برابر باشد؛
2. finalizer باید SHA-256 را در نام asset وارد و URL ثابت را حذف کند؛
3. static server فقط نام hashدار را immutable و asset ثابت را `no-store` بفرستد.

pre-image برابر `3 failed / 6 passed` بود. اصلاح‌ها:

- finalizer محتوای patch را می‌خواند، ۱۶ نویسهٔ نخست SHA-256 را می‌سازد، patchهای ثابت/قدیمی را پاک و asset hashدار تازه را پیش از bundle اصلی inject می‌کند؛
- cache policy سرور فقط برای فایل مستقیم زیر `assets` با بخش hash حداقل هشت‌نویسه‌ای یک‌ساله و immutable است؛ index و فایل ثابت `no-store` هستند؛
- آزمون source/dist، نام/content hash، نبود URL ثابت و headerهای HTTP را کنترل می‌کند.

نخستین GREEN برابر `8/9` بود؛ regex اولیه بیش از حد باز بود و `runtime-patch.js` را به‌اشتباه hashدار می‌دانست. regex محدود و retry برابر `9/9 PASS` شد. این failure بخشی از TDD بود و به runtime عملیاتی نرسید.

## اعتبارسنجی کامل

- هدفمند cache/build/HTTP=`9/9 PASS`.
- regression مرتبط runtime patch، HTTP media، Phase 6 و Material UI=`54/54 PASS`.
- همهٔ runnerهای UI سبز: scroll=`10/10`، grouped=`16/16`، Phase9 workspace=`12/12 + 15/15`، Phase9 acceptance=`13/13`، Phase10=`7/7`، observability=PASS، Phase11 onboarding=`7/7`، Phase11-B2=`6/6` و mobile-auth/live=PASS.
- TypeScript=PASS و Vite build=PASS با 1015 module. asset نهایی `ui33-runtime-patch-6de1ad483e2c97af.js` و SHA کامل محتوا=`6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893` است.
- full Backend نخست=`657/658`؛ تنها failure، wheel/source parity مورد انتظار پس از تغییر `http_api.py` بود.
- wheel آفلاین دوبار با SHA یکسان=`ba05c810792fe695a96b90ce4b313ef3b5e15e7b9ef70032518c96923e295e7a` ساخته شد؛ parity شامل 90 source file و missing/mismatched/extra همگی صفر بود.
- full Backend retry=`658/658 PASS`، failure/error/skip=0؛ collect-only مستقل 74 فایل و 658 تست را تأیید کرد.
- دو archive canonical پس از ثبت ADR-40 با 282 فایل، SHA بایت‌یکسان=`08c5d5dd132f2c4d7a41c27f0cd26d084630d747a542a8c7383296e906a2c61c` و content-set=`4ec774ed765b932bb93fece08596108524608c18dc926be0d13b63a09e6c731e` ساخته شدند؛ بازگشایی، path/hash/manifest/privacy داخلی PASS بود. checkpoint پیش از تغییر سند معماری با همان نام artifact و `--force` جایگزین شد.
- wheel نهایی در fresh venv فقط با wheelهای local و `--no-index` نصب شد؛ runtime checker=`ok=true/failures=0`، `pip check` سبز، import زیر prefix تازه و Event Catalog برابر 103 بود.

## اعتبارسنجی زنده و رخدادهای ابزار

- Computer Use پس از reset و دو initialize، پیش از انتخاب پنجره/click/input با `kernel assets path not found` شکست خورد؛ input و ارسال پیام صفر بود.
- برنامه هنگام بررسی نهایی loopback اجرا نبود و اتصال HTTP با `connection refused` رد شد. برنامه بدون اجازه راه‌اندازی نشد؛ بنابراین شاهد این گزارش تا تأیید کاربر `AUTOMATED + ISOLATED RUNTIME` است، نه Live UI.
- یک اسکن خواندنی گسترده بیش از 60 ثانیه طول کشید و متوقف شد؛ یک parser شبکه، یک probe مسیر، یک LevelDB reader و یک identity header invocation نیز خطای ابزاری داشتند و با retry محدود/روش canonical اصلاح شدند. هیچ‌کدام داده‌ای ننوشتند.
- probe شمارش privacy receipt ابتدا فیلد ناموجود را به‌اشتباه مانند finding شمرد؛ receipt schema با پیام verification canonical خوانده شد و بازگشایی archive/privacy موفق بود.

## نتیجه و اقدام کاربر

F-050 در سطح کد، build، HTTP contract، full regression، wheel، archive و fresh install بسته است. برخلاف G-10، URL patch اکنون با هر تغییر محتوا عوض می‌شود و cache قدیمی نمی‌تواند نسخهٔ تازه را پنهان کند.

برای پذیرش Live، کاربر فقط برنامه را کاملاً ببندد و دوباره اجرا کند، سپس گروه نمونه را باز کند. انتظار این است که پیام‌های منتهی به ۴ شهریور دیده شوند. پاک‌کردن دستی cache یا حذف داده لازم نیست. اگر پس از restart هنوز ۶ مرداد نمایش داده شد، F-050 با Trigger زنده باز می‌شود و قبل از هر تغییر تازه، پاسخ index/asset و timeline همان اجرای زنده به‌صورت ماسک‌شده بررسی خواهد شد.

## انتشار Git

commit اصلی G-11 با hash=`8fe8d90d507fccb9bec586feb81c1f28d71d64fc` و پیام `fix(ui): invalidate cached runtime patches` به‌صورت عادی روی `codex/stabilization-g09` push شد. remote branch دقیقاً همان hash و GitHub main همچنان `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` است. push/merge مستقیم main، force-push، حذف ref و انتشار دادهٔ عملیاتی انجام نشد. commit مستندی closure همین verify را با push عادی دوم ثبت می‌کند.

# گزارش G-10 — اصلاح نمایش قدیمی گروه منتخب با وجود sync موفق

تاریخ: 2026-08-26  
Run: `STAB-G10-R01`  
وضعیت: `COMPLETE / TESTED / PUBLISHED_TO_WORKING_BRANCH`

## گزارش کاربر و مجوز

کاربر اعلام کرد محتوای یک گروه که قبلاً «منتخب» شده بود حدود یک ماه عقب است. کاربر مشاهدهٔ زندهٔ محیط پیام‌رسان و در صورت نیاز ارسال فقط به فضای ذخیره‌سازی شخصی را مجاز کرد. هیچ پیام آزمایشی ارسال نشد، چون مشکل در مسیر خواندن/نمایش بازتولید و اصلاح شد. عنوان گروه، شناسهٔ حساب، متن پیام، شماره و مسیر حساس در شاهد یا گزارش ثبت نشده‌اند.

## تشخیص امن وضعیت زنده

- ابزار کنترل پنجرهٔ ویندوز پیش از هر مشاهده یا input سه بار با خطای زیرساختی `failed to write kernel assets: path not found` متوقف شد؛ یک reset طبق راهنمای ابزار نیز مشکل را رفع نکرد و UI automation ادامه نیافت.
- ممیزی فقط‌خواندنی catalog و SQLite نشان داد تنها گروه منتخب جاری `active=true` است، peer file موجود است و `top_message_id` catalog دقیقاً با جدیدترین پیام SQLite برابر است.
- پایگاه محلی برای peer ماسک‌شده 674 پیام داشت و جدیدترین تاریخ ذخیره‌شده متعلق به همان روز بود؛ بنابراین Provider sync و persistence یک ماه عقب نبودند.
- اسکن aggregate لاگ‌های جدید 91 فایل و 5613 رکورد مرتبط را دید؛ event typeهای `dialogs_received`، `messages_upserted`، `sync_completed` و `message_search_completed` حاضر و failure record صفر بود. هیچ متن یا شناسهٔ خام لاگ نشد.

## علت ریشه‌ای

`ui/src/ui33-runtime-patch.js` یک لایهٔ سازگاری قدیمی است. این patch علاوه بر نگهداری موقعیت مطالعه، درخواست عادی `POST /api/v1/messages/list` را برای گفتگوی بدون unread تغییر می‌داد:

- `before_id` را به `lastVisibleId + 1` از checkpoint قدیمی تبدیل می‌کرد؛
- `limit` را به حداقل 120 می‌رساند؛
- همان request تغییرکرده پس از sync نیز دوباره اجرا می‌شد.

در نتیجه دادهٔ تازه در SQLite وجود داشت، اما UI عمداً پنجرهٔ یک checkpoint قدیمی را می‌خواند و ظاهراً «به‌روز نمی‌شد». منتخب‌بودن علت sync نبود؛ فقط سناریوی گزارش‌شده را قابل مشاهده کرده بود.

## RED و اصلاح

- قرارداد تازه `test_saved_reading_position_never_rewrites_the_latest_message_request` ابتدا روی pre-image با `1 failed / 5 passed` RED شد.
- fetch wrapper دیگر body، `before_id` یا `limit` را تغییر نمی‌دهد و دقیقاً `originalFetch(input, init)` را فراخوانی می‌کند.
- نگهداری موقعیت مطالعه و metadata استفادهٔ WordPress حفظ شد؛ checkpoint فقط concern نمایشی است و در صورت حاضر بودن row در پنجرهٔ تازه می‌تواند scroll را بازیابی کند.
- source و dist patch با SHA-256 یکسان=`6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893` ساخته شدند.

## اعتبارسنجی

- source contract پس از patch=`1/1 PASS`.
- regression هدفمند runtime patch + mobile concurrency=`11/11 PASS`.
- full Backend=`657/657 PASS`، failure/error/skip=0؛ collect-only مستقل=657 در 74 فایل.
- هر 9 runner UI سبز: scroll=`10/10`، grouped=`16/16`، Phase9 workspace=`12/12 + 15/15`، Phase9 acceptance=`13/13`، Phase10=`7/7`، observability=PASS، Phase11 onboarding=`7/7`، Phase11-B2=`6/6` و mobile-auth/live=PASS.
- TypeScript و Vite build=PASS؛ 1015 module و runtime patch source/dist برابر.
- دو archive نهایی G-10 با file_count=282، SHA یکسان=`077d316d5a546fa20eff39a9e77205e57756050ed293884bd34d09cba52a7f3e` و content-set=`36012dbba19eb2b464bfa5df2de37006157e7515a774784738bc9d57fadcc1ff` ساخته شدند؛ privacy finding صفر است.
- manifest diff نسبت به archive پیشین: changed فقط `ui/src/ui33-runtime-patch.js`، added=0 و removed=0.
- refresh اسناد، memory integrity، stale check، link check و parse شدن Release Manifest همگی PASS هستند؛ package dry-run نهایی همان 282 فایل/content-set آزموده‌شده و write صفر را تأیید کرد.

## رخدادهای ابزار و اثر عملیاتی

1. Computer Use در initialize/retry/reset-retry شکست زیرساختی داشت؛ window selection/input/message send=0.
2. دو تلاش orchestration برای probe ماسک‌شده به‌علت نبود `TextEncoder` و `btoa` در V8 رد شدند؛ retry با Python read-only موفق شد؛ DB write=0.
3. اسکن نخست log روی دو رکورد JSON null هشدار index داد؛ retry با null guard بدون خطا و failure record صفر پایان یافت.

هیچ login، OTP، ارسال پیام، WordPress، Bale، حذف/بازنویسی دادهٔ عملیاتی یا تغییر Firewall/Proxy انجام نشد. فایل‌های runtime فقط خوانده شدند.

## نتیجه

F-049 بسته است. مسیر آخرین پیام‌ها دیگر به checkpoint قدیمی منحرف نمی‌شود و بازکردن گروه، پنجرهٔ تازه‌ترین پیام‌های محلیِ همگام‌شده را می‌گیرد. تأیید بصری مستقیم به‌علت خرابی زیرساخت Computer Use اجرا نشد، اما علت در pre-image با RED قطعی، دادهٔ جاری با SQLite اثبات و قرارداد source/dist/full regression سبز شد.

## انتشار Git

commit اصلی G-10 با hash=`407cd418c2249fb6d9b51827e0601d9ca883d0d0` و پیام `fix(ui): show latest messages for selected groups` روی `codex/stabilization-g09` push شد. remote branch دقیقاً با commit محلی برابر و GitHub `main` همچنان `a4df3ecf2bcd4ab658c5361afdc287444694fcd2` است؛ force/merge/main push انجام نشد.

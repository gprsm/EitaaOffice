# گزارش ادغام پیام‌های متوالی و تاب‌آوری بارگیری آواتار

تاریخ: 2026-08-27
Run: `UX-MESSAGE-AVATAR-R01`
وضعیت: `IMPLEMENTED / FULL_AUTOMATED_ACCEPTANCE / GITHUB_DEDICATED_BRANCH_PUBLISHED`

## نتیجه

پیام‌ها و پست‌های متوالی یک فرستنده اکنون، فارغ از نوع محتوا، در یک Card نمایش داده می‌شوند؛ شرط ادغام آن است که ترتیب timeline قطع نشده باشد، فاصلهٔ هر واحد با واحد بعدی حداکثر پنج دقیقه باشد و روز نمایشی تغییر نکند. این قرارداد متن→عکس، عکس→متن، چند عکس، چند آلبوم رسمی پشت‌سرهم، فایل و محتوای ترکیبی را پوشش می‌دهد. انتخاب، ایندکس، وضعیت WordPress، unread، تمرکز جست‌وجو و پیمایش مجازی نیز تمام اعضای گروه را یک واحد دیداری ولی چند پیام منبع در نظر می‌گیرند.

بارگیری آواتار cache-first و failure-isolated شد. probeهای cached-only در صف سریع مستقل اجرا می‌شوند و فقط miss وارد صف remote می‌شود. صف remote عمداً concurrency یک دارد، چون Eitaa Core یک نشست مشترک دارد و عملیات Provider نباید هم‌پوشانی کنند؛ استقلال مورد نیاز در سطح HTTP/UI، حساب، failure و cache فراهم شده است. تعویض حساب، کار ماندهٔ scope قبلی را پیش از شروع هر مرحله خنثی می‌کند و شکست یک آواتار دیگر Promiseها را reject یا صف را متوقف نمی‌کند.

## علت‌های ریشه‌ای

1. گروه‌بندی قبلی فقط تغییر شکل ظاهری Cardهای جدا بود، حد زمانی محاسبه اما اعمال نمی‌شد و آلبوم‌ها عمداً از ادغام با پیام مجاور کنار گذاشته می‌شدند. بنابراین متن و عکس یا دو آلبوم پشت‌سرهم یک محتوای واحد نبودند.
2. سه slot مشترک آواتار هم cache probe و هم remote download را اجرا می‌کرد. درخواست remote کند می‌توانست probe آواتارهای حاضر در cache را پشت صف نگه دارد؛ reject نیز به component می‌رسید و guard کافی برای unmount/account switch وجود نداشت.
3. پاک‌سازی cache برای یک site با prefix واقعی account-scoped تطبیق نداشت.
4. همهٔ عکس‌های فرستنده از نظر داده‌ای قابل بازیابی نیستند. مدل contact جاری Core، `UserProfilePhoto` مخاطب را نگه نمی‌دارد؛ در نتیجه عکس فرستنده فقط وقتی قابل دریافت است که همان User یک photo reference قابل استفاده در dialog catalog داشته باشد. گروه/کانال و گفت‌وگوی شخصی معمولاً reference دارند؛ رکورد فاقد reference، عکس پنهان Provider یا دادهٔ stale باید امن به حروف نام برگردد. این محدودیت با افزایش موازی‌سازی قابل رفع نیست و تغییر schema/Core جداگانه می‌خواهد.

## قرارداد پیاده‌سازی

- `buildMessageGroupLookup` ابتدا آلبوم رسمی/استنباطی را واحد اتمیک می‌گیرد و سپس واحدهای مجاور با sender identity پایدار را تا 300 ثانیه ادغام می‌کند.
- lookup از پنجرهٔ کامل و پیش از filter ساخته می‌شود تا حذف موقت یک فرستنده باعث ادغام کاذب دو پیام غیرمجاور نشود.
- در گروه‌های ناشناس، fallback هویت فقط برای personal/channel مجاز است؛ در group، نبود sender identity باعث عدم ادغام می‌شود تا پیام دو فرد ناشناس یکی نشود.
- renderer بلوک‌های متن، gallery و فایل را به ترتیب زمانی می‌سازد. run عکس‌های متوالی یک gallery است و captionهای همان run پس از gallery و به ترتیب نمایش داده می‌شوند.
- cached-only با concurrency شش و remote با concurrency یک اجرا می‌شود. نتیجهٔ مثبت یک ساعت، نبود عکس دو دقیقه و failure فقط پانزده ثانیه cache می‌شود.
- cache/request key شامل AppUser/MessengerAccount storage scope، site و peer است. scope پیش از cache probe و remote fetch دوباره بررسی می‌شود.
- آواتار شخصی با sender key ناقص از peer خود گفت‌وگو استفاده می‌کند؛ آواتار image خراب نیز به initials برمی‌گردد.

## شاهد RED و GREEN

- RED گروه‌بندی: `buildMessageGroupLookup is not a function` در runner رسانه.
- RED آواتار: module صف مستقل وجود نداشت و contract Python نبود cached-only/two-lane را رد کرد.
- GREEN هدفمند: grouped-media=`29/29`، Phase 9 workspace/queue=`18/18` و regression Material/UI=`42/42`.
- TypeScript=`PASS`؛ build تولیدی Vite=`PASS` با 1016 module. warning تاریخی chunk بزرگ غیرمسدودکننده باقی است.
- تمام ۹ runner UI سبزند: scroll=`10/10`، grouped-media=`29/29`، Phase 9 workspace=`18/18`، Phase 9 acceptance=`13/13`، Phase 10=`7/7`، Observability=`PASS`، Phase 11 onboarding=`7/7`، Phase 11-B2=`6/6` و mobile/auth/live=`PASS`.
- full Backend پس از افزودن یک guard آزمون=`659/659` و skip/failure/error صفر است.
- package tests=`15/15`؛ دو archive نهاییِ ایزوله از work موازی ایندکس، 282فایلی و با SHA بایت‌یکسان=`1c52502d...cfb6900` و content-set=`35f58c15...c6c34c2` ساخته و privacy/hash/path/manifest آن‌ها verify شد.
- fresh venv فقط از wheelهای داخل archive و با `--no-index` نصب شد؛ runtime checker، `pip check`، import ایزوله و Event Catalog=103 سبز هستند.

## حریم خصوصی و اثر عملیاتی

هیچ برنامهٔ واقعی اجرا نشد، هیچ حساب/OTP/Session باز نشد، هیچ پیام یا WordPress/Provider mutation انجام نشد و `bridge.json`، `.env`، `data/`، `runtime/`، `diagnostics/` و `backups/` تغییر نکردند. آزمون‌ها فقط دادهٔ مصنوعی و artifact کنترل‌شده ساختند. هیچ عنوان گفتگو، peer/account id، متن خصوصی پیام، شماره یا credential در این گزارش ثبت نشده است.

## فایل‌های اصلی

- `ui/src/lib/groupedMedia.ts`
- `ui/src/MessageContentCard.tsx`
- `ui/src/App.tsx`
- `ui/src/lib/avatarQueue.mjs`
- `ui/src/lib/avatarLoader.ts`
- `ui/scripts/run-grouped-media-tests.mjs`
- `ui/scripts/run-phase9-workspace-tests.mjs`
- `tests/test_ui_repair.py`
- `tests/test_ui2_scroll_repair.py`

## دروازه‌های باقی‌مانده

پذیرش فعلی خودکار و آفلاین است. مشاهدهٔ بصری روی دادهٔ واقعی بدون mutation می‌تواند توسط کاربر انجام شود، اما برای صحت contract لازم نیست. رفع عکس کاربران گروهی که photo reference در Core ندارند، تغییر جداگانهٔ مدل/codec و migration احتمالی است و در این Run حدس زده یا فعال نشده است. تصمیم canonical این Run در ADR-44 و شواهد آن در V-169/V-170/V-180 ثبت شده است.

انتشار Git به‌صورت ایزوله روی `codex/message-avatar-grouping` انجام شد. commit اصلی `97022f36...85fef` با remote برابر verify و `main` روی `a4df3ecf...fcd2` ثابت ماند. فایل‌های work موازی ایندکس، workbook و artifactها در candidate نبودند.

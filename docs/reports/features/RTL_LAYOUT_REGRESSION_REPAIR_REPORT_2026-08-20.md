# گزارش اصلاح بازگشت چیدمان RTL

تاریخ: ۲۰۲۶-۰۸-۲۰  
وضعیت: `COMPLETE / AUTOMATED_AND_LOCAL_VISUAL_ACCEPTED`

## نتیجه

چیدمان فعال دوباره در همهٔ سطح‌های Workspace راست‌به‌چپ است. در دسکتاپ Navigation راست‌ترین ستون، Conversation List در سمت چپ آن و Chat در ادامه قرار دارد. Header کارت پیام Avatar نویسنده را در راست، نام را در میانه و action را در چپ می‌چیند. در موبایل Navigation پایین صفحه است، فهرست گفتگوها از لبهٔ راست و Composer از لبهٔ چپ وارد می‌شوند.

## علت ریشه‌ای

سند و Theme از قبل RTL بودند، اما `App.tsx` روی `main` دوباره `direction: 'rtl'` می‌گذاشت. چون این style زیر `stylis-plugin-rtl` تولید می‌شد، declaration یک‌بار دیگر آینه و `main` در Chromium عملاً LTR محاسبه می‌شد. همین موضوع ترتیب grid و `CardHeader` را برعکس کرده بود. transform و لبهٔ کشوهای موبایل نیز بدون درنظرگرفتن تبدیل Stylis تعریف شده بودند.

## تغییرها

- declaration تکراری جهت از Workspace حذف شد و جهت root به ارث رسید.
- Conversation drawer به `insetInlineStart` متصل و علامت transform آن با RTL Cache هماهنگ شد تا از راست وارد شود.
- Composer drawer به `insetInlineEnd` متصل و transform آن طوری تنظیم شد که از چپ وارد شود.
- دو قرارداد ضدبازگشت به Phase 9 acceptance افزوده شد: ممنوعیت direction تکراری و قرارداد لبه/transform کشوهای موبایل.
- harness محلی Electron برای ثبت screenshot و اندازه‌گیری computed direction/مختصات دسکتاپ و موبایل اضافه شد.

## Test-first و شکست‌های ثبت‌شده

1. قرارداد نخست پیش از اصلاح روی `direction: 'rtl'` سطح Workspace شکست خورد و double flip را بازتولید کرد.
2. قرارداد دوم پیش از اصلاح روی لبه و transform قدیمی هر دو drawer شکست خورد.
3. Browser درون برنامه localhost را با `ERR_BLOCKED_BY_CLIENT` رد کرد؛ Chrome نیز در دسترس نبود. به‌جای bypass، fixture در Chromium خود Electron اجرا شد.
4. نخستین Vite invocation از cwd نادرست root را 404 داد؛ invocation بعدی داخل `ui` در sandbox هنگام dependency scan با محدودیت دسترسی والد روبه‌رو شد. سرور محلی با cwd صحیح و مجوز محدود اجرا و پس از پذیرش با Ctrl-C متوقف شد.
5. نخستین full pytest به temp سراسری کاربر دسترسی نداشت و با `WinError 5` شاهد محصول نساخت. همان suite با basetemp تازه داخل workspace تکرار و موفق شد.
6. تلاش خودکار برای کلیک روی drawer در پنجرهٔ پنهان Electron state را تغییر نداد؛ این probe به‌عنوان شاهد کنار گذاشته شد. قرارداد edge/transform ایستا و مختصات حالت بسته معیار شدند.

## شواهد نهایی

- Phase 9 acceptance: `13/13`.
- همهٔ assertionهای شماره‌دار UI: `70/70`؛ mobile-auth-live و observability نیز موفق.
- TypeScript check: موفق.
- Production build: موفق، 1008 module؛ chunk اصلی `788.97 kB` و gzip `241.76 kB`. warning شناخته‌شدهٔ F-013 همچنان باز است.
- Full Python: `580/580` با basetemp ایزولهٔ workspace.
- Electron desktop 1280×800: `htmlDirection=rtl`، `mainDirection=rtl`؛ Navigation در بازهٔ x=1192..1264، Conversation List در x=788..1192 و Chat در x=0..788.
- Electron mobile 390×844: viewport محتوایی 374×779؛ Navigation در پایین x=0..374 و drawer بسته در x=408..752، یعنی خارج لبهٔ راست.
- CardHeader: در هر دو viewport مختصات Avatar از Title و Title از Action راست‌تر بود.

## دامنه و ایمنی

این پذیرش فقط fixture محلی UI را استفاده کرد. هیچ Provider network، Login/OTP/Credential، Send/Invite، WordPress، Session/Config عملیاتی، migration/rollback، تغییر Firewall/Proxy/Port/Certificate، حذف داده یا Git mutation انجام نشد. worktree dirty موجود حفظ شد و دادهٔ خصوصی وارد screenshot، log آزمون یا سند نشد.

## Trigger ابطال

تغییر `rtlCache`، Theme direction، root dir، Workspace grid/source order، `ConversationListPage` edge/transform، Composer drawer، `MessageContentCard` header یا Electron visual fixture نیازمند تکرار این پذیرش است.

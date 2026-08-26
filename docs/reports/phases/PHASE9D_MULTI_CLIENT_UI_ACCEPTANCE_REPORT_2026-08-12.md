# گزارش مستقل Phase 9-D — پذیرش دیداری، دسترس‌پذیری و هم‌زمانی

تاریخ: ۲۰۲۶-۰۸-۱۲  
زمان پایان QA دیداری: حدود ۰۴:۵۹ به وقت ایران  
وضعیت: **تکمیل‌شده، آزموده‌شده و پذیرفته‌شده**

## نتیجهٔ نهایی

پذیرش واقعی رابط با Browser Use و میزبان موقت Loopback، روی fixture کاملاً ساختگی و بدون هیچ Provider call اجرا شد. پوسته‌ها، RTL، تم تیره، عدم overflow، drawerها، bottom sheet، Dialog تمام‌صفحه، صفحه‌کلید کم‌ارتفاع و جداسازی دو کاربر از DOM و تصویر کنترل شدند.

## ماتریس پذیرش واقعی

| حالت | نتیجهٔ اندازه‌گیری DOM | نتیجه |
|---|---|---|
| ۳۶۰×۸۰۰، مدیر | `MobileShell`؛ bottom sheet در `[0,110,360,624]`؛ حالت بسته خارج از viewport و `visibility:hidden/pointer-events:none` | موفق |
| ۳۹۰×۸۴۴، اپراتور | `MobileShell`؛ Dialog تنظیمات دقیقاً `[0,0,390,844]`؛ margin و border-radius صفر؛ مقدار تمام password inputها خالی | موفق |
| ۸۴۴×۳۹۰ افقی، اپراتور | `MobileShell`؛ rail برابر ۵۸ پیکسل؛ drawer گفتگو هنگام بازشدن `[454,0,390,332]` و در حالت بسته کاملاً خارج صفحه | موفق |
| ۱۲۸۰×۸۰۰، مدیر | `DesktopShell`؛ composer drawer برابر `[760,0,520,800]` | موفق |
| ۱۶۰۰×۹۰۰، مدیر | `DesktopShell`؛ grid برابر `72px 352px 760px 416px`؛ composer چهارمین ستون static | موفق |

در همهٔ موارد `document.scrollWidth <= innerWidth` بود و overflow افقی مشاهده نشد. دور پاک نهایی روی یک tab تازه در هر پنج حالت اجرا شد و Console نتیجهٔ **صفر warning و صفر error** داشت.

## سناریوهای تعاملی

- منوی «بیشتر» روی موبایل باز شد و هویت/حساب masked را نمایش داد.
- drawer گفتگو در موبایل عمودی و افقی باز و بسته شد.
- bottom sheet وردپرس در ۳۶۰ و ۳۹۰ باز و بسته شد و تمام کنترل‌های بسته خارج از چرخهٔ تعامل باقی ماندند.
- Dialog تنظیمات با Portal واقعی Material باز شد و تمام viewport را پوشاند.
- composer در ۱۲۸۰ drawer و در ۱۶۰۰ ستون docked بود.
- با viewport شبیه صفحه‌کلید `360×500`، textarea فعال در بازهٔ `369.5..415.5` باقی ماند، `scroll-margin-block:96px` داشت و overflow ایجاد نشد.
- حرکت Tab، `:focus-visible` با outline سه‌پیکسلی و offset دوپیکسلی را فعال کرد.

## جداسازی دو کاربر

دو tab هم‌زمان با fixtureهای مدیر و اپراتور اجرا شدند:

- مدیر فقط «مدیر آزمایشی» و scope زیر را داشت:
  `user-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.account-11111111-1111-4111-8111-111111111111`
- اپراتور فقط «اپراتور آزمایشی» و scope زیر را داشت:
  `user-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb.account-22222222-2222-4222-8222-222222222222`
- هر tab صریحاً فاقد هویت tab دیگر بود و scopeها متفاوت بودند.
- آزمون Python هم‌زمانی سه Client نیز ۳۰ چرخه برای هر Client، جمعاً ۹۰ چرخه، را بدون نشت حساب/نشست گذراند.

## اشکالات کشف و اصلاح‌شده در پذیرش

1. بخش کوچکی از composer بسته در پایین موبایل قابل مشاهده/کلیک بود؛ حالت بسته اکنون کاملاً hidden و بدون pointer event است.
2. تلفن افقی ۸۴۴×۳۹۰ به‌علت شرط صرفاً عرضی `DesktopShell` می‌گرفت؛ انتخاب Shell و قواعد Phone اکنون viewport افقی کم‌ارتفاع را نیز پوشش می‌دهند.
3. `min-width:821px` حالت static گفتگو را بر drawer افقی غالب می‌کرد؛ selector پوستهٔ موبایل و transform قطعی اصلاح شد.
4. fixture مسیر امن `/api/v1/settings/sites` را نداشت و Settings را خالی می‌کرد؛ پاسخ بدون Credential اضافه شد.
5. Dialog به‌علت Portal خارج از `.mobile-shell` شش پیکسل margin داشت؛ selector در media query به کلاس Portal متصل شد و اندازهٔ دقیق viewport تأیید گردید.

برای همهٔ موارد assertion جلوگیری از بازگشت در `ui/scripts/run-phase9-acceptance-tests.mjs` یا تست Phase 6-D به‌روزرسانی شد.

## آزمون‌های نهایی

- مجموعهٔ کامل Python: **۴۷۵/۴۷۵ موفق**.
- regression اختصاصی Shell: **۱/۱ موفق**.
- Phase 9 acceptance: **۱۰/۱۰ موفق**.
- Phase 9 Workspace: **۱۰/۱۰ موفق**.
- Scroll model: **۱۰/۱۰ موفق**.
- Grouped-media model: **۱۶/۱۶ موفق**.
- TypeScript و build تولیدی: موفق؛ ۹۸۱ module.
- Compile کل `src`، `pip check` و `git diff --check`: موفق.
- build نهایی تولیدی: CSS برابر 125.39 kB و JavaScript برابر 885.50 kB (gzip برابر 263.36 kB).
- هشدار غیرمسدودکنندهٔ chunk بزرگ‌تر از 500 kB همچنان بدهی performance است.

## ایمنی و پاک‌سازی

- fixture فقط در build صریح آزمایشی فعال شد؛ سپس build تولیدی عادی جایگزین گردید.
- markerهای fixture و «مدیر آزمایشی» در `ui/dist` تولیدی وجود ندارند.
- میزبان Loopback و تمام tabهای آزمون بسته و viewport reset شدند.
- هیچ Login/Logout/OTP/Sync/Send واقعی، WordPress call واقعی، Migration، Firewall/LAN/Router/Service یا Rollout اجرا نشد.
- `bridge.json` واقعی نوشته نشد؛ اندازهٔ آن ۹۳۴ بایت و SHA-256 آن همچنان زیر است:

```text
D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89
```

- هیچ reset، checkout، stage، commit یا push انجام نشد و worktree کثیف قبلی حفظ شد.

## نتیجهٔ پذیرش

همهٔ معیارهای صریح 9-D شامل عرض‌های هدف، حالت افقی، RTL/Dark، عدم overflow، Keyboard، focus، Mobile/Desktop shell، دو کاربر و سه Client پوشش داده شدند. **Phase 9-D کامل و پذیرفته‌شده است.**


# گزارش فاز ۶-D: پذیرش Mobile/LAN و هم‌زمانی

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: تکمیل‌شده و پذیرفته‌شده  
مرز گزارش: پایان Phase 6-D و پایان کل Phase 6

## نتیجهٔ اجرایی

Foundation لازم برای استفادهٔ چند Browser/Mobile client روی استقرار کنترل‌شدهٔ LAN تکمیل شد. سرور HTTP تحت آزمون واقعی، Requestهای هم‌زمان را روی Worker threadهای مستقل پذیرفت و یک Request نگه‌داشته‌شده نتوانست Health را مسدود کند. نشست‌های هم‌زمان دو AppUser نیز زیر بار موازی به Principal یا Session یکدیگر نشت نکردند.

رابط تولیدی اکنون Presentation shell را بر پایهٔ عرض انتخاب می‌کند، Dynamic Viewport و Safe Area را رعایت می‌کند، منوی اصلی را در موبایل قابل دسترس نگه می‌دارد، وضعیت قطع/reconnect را نمایش می‌دهد و Mutation یا Upload را پس از خطای انتقال به‌صورت خودکار تکرار نمی‌کند. وضعیت محلی عملیاتی رابط نیز با Scope ترکیبی AppUser و MessengerAccount کلیدگذاری می‌شود.

MobileShell کامل و مستقل، Unified Inbox و Information Architecture نهایی موبایل همچنان طبق معماری canonical در Phase 9 باقی می‌مانند.

## ورودی‌ها و قیود حفظ‌شده

- `ARCHITECTURE_DECISIONS.md`
- `PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md`
- `PHASE6B_LAN_HTTP_AUTH_SESSION_HARDENING_REPORT.md`
- `PHASE6C_WINDOWS_LAN_SERVING_OPERATIONS_REPORT.md`
- Worktree موجود و تمام تغییرات قبلی کاربر
- ممنوعیت حدس‌زدن API یا Login flow برای Bale، Rubika و SoroushPlus
- ممنوعیت اجرای Firewall rule، نصب Windows Service، تغییر Router، Port forwarding یا فعال‌سازی Config واقعی LAN
- ممنوعیت Login/OTP/Send واقعی Provider در آزمون‌ها

## تصمیم‌های معماری تثبیت‌شده

### ۱. هم‌زمانی HTTP

- `BridgeApiHttpServer` همان `ThreadingHTTPServer` باقی ماند و هر Request را در Worker thread مستقل می‌پذیرد.
- Readiness و Health از هم جدا هستند و Request کند نباید Health را متوقف کند.
- Coordinator همچنان مرز تراکنشی SQLite و Authorization سمت سرور است؛ Thread مستقل به معنی حذف قفل یا دورزدن تراکنش نیست.
- Session، CSRF، AppUser و MessengerAccount از Header/Cookie همان Request استخراج و سمت سرور دوباره مجازسنجی می‌شوند.

### ۲. قرارداد انتقال Browser

- `fetch` با `credentials: 'same-origin'` اجرا می‌شود.
- فقط `GET` پس از خطای انتقال، یک بار و بعد از ۳۵۰ میلی‌ثانیه تکرار می‌شود.
- `POST`، Upload، Send و سایر Mutationها هرگز به‌صورت خودکار تکرار نمی‌شوند.
- Timeout عمومی ۶۰ ثانیه است و فقط مسیرهای طولانی Media Preview یا Message Sync تا ۱۲۰ ثانیه فرصت دارند.
- CSRF در حافظهٔ Module نگهداری می‌شود و در `localStorage` یا `sessionStorage` نوشته نمی‌شود.

### ۳. reconnect و مشاهده‌پذیری

- وضعیت `online | offline | reconnecting` به‌صورت سراسری منتشر می‌شود.
- هنگام قطع ارتباط، Alert قابل مشاهده و دکمهٔ تلاش دوباره نمایش داده می‌شود.
- در حالت قطع، Readiness هر چهار ثانیه Probe می‌شود و پس از بازیابی Alert حذف می‌شود.
- Payload وضعیت اتصال Token، Cookie، Phone، Provider session، مسیر فایل یا Config خصوصی نمایش نمی‌دهد.

### ۴. Responsive/Touch foundation

- Shell با `useMediaQuery('(max-width:599px)')` و بدون User-Agent انتخاب می‌شود.
- `100dvh`، `100svh`، Safe Area و جلوگیری از Overscroll/Horizontal overflow اضافه شد.
- برای Pointer لمسی، هدف‌های تعاملی حداقل ۴۴ پیکسل و ورودی‌ها حداقل فونت ۱۶ پیکسل دارند.
- منوی «بیشتر» در Navigation پایین موبایل قابل دسترس است و تنظیمات، افزودن گفتگو، همگام‌سازی، عملیات گروهی و خروج را در Popover محدود به Viewport نمایش می‌دهد.
- نوار پایین دقیقاً پنج خانه دارد؛ Theme ثابت و WordPress rail در موبایل پنهان هستند تا ردیف دوم یا Scrollbar ناخواسته ساخته نشود.
- مرز Drawer گفتگو با CSS روی ۹۰۰ پیکسل و در React نیز دقیقاً روی همان مقدار یکسان شد.
- کلید Escape پنل‌های موقت، Drawerها و منوی باز را می‌بندد.

### ۵. Scope دادهٔ محلی رابط

- کلیدهای Local UI state با Prefix زیر ساخته می‌شوند:

```text
user-{app_user_id}.account-{messenger_account_id|default}
```

- Draft ارسال سریع، Site/Peer selection، Tab، Media mode، Sync time، Taxonomy cache، تاریخچهٔ استفاده و Reading position از این Scope پیروی می‌کنند.
- تغییر AppUser، MessengerAccount را پاک و Scope را دوباره منتشر می‌کند.
- تغییر MessengerAccount علاوه بر Header انتخاب حساب، Scope محلی را نیز عوض می‌کند.
- Runtime patch قدیمی UI3.3 هم از همان Scope استفاده می‌کند و هنگام تغییر Scope، Cacheهای حافظه‌ای و Restore generation را پاک می‌کند.
- حالت Feature-off سازگاری قبلی را با کلیدهای Legacy بدون Prefix حفظ می‌کند.

## فایل‌های تغییرکرده یا جدید در Phase 6-D

- `ARCHITECTURE_DECISIONS.md`
- `ui/src/App.tsx`
- `ui/src/AppUserGate.tsx`
- `ui/src/ConnectionStatus.tsx` (جدید)
- `ui/src/QuickSendBar.tsx`
- `ui/src/lib/api.ts`
- `ui/src/main.tsx`
- `ui/src/styles.css`
- `ui/src/ui33-runtime-patch.js`
- `tests/test_phase6d_mobile_lan_concurrency_acceptance.py` (جدید)
- `PHASE6D_MOBILE_LAN_CONCURRENCY_ACCEPTANCE_REPORT.md` (جدید)

Build تولیدی `ui/dist` نیز با Script رسمی پروژه بازتولید شد؛ این مسیر طبق قرارداد Release یک خروجی Build است.

## آزمون‌های اختصاصی Phase 6-D

فایل اختصاصی شامل پنج Acceptance test است:

1. دو Request واقعی HTTP با Barrier هم‌زمان وارد دو Worker thread مستقل می‌شوند.
2. Request کند نگه داشته می‌شود و Health پیش از آزادشدن آن پاسخ موفق می‌دهد.
3. ۲۴ Authorization موازی روی دو AppUser، Principal و Session درست خود را حفظ می‌کنند و CSRF نشست‌ها مستقل می‌ماند.
4. قرارداد Browser transport، GET-only retry، عدم retry برای Upload و نگهداری CSRF در حافظه بررسی می‌شود.
5. Width-driven shell، Touch foundation، منوی موبایل و AppUser+MessengerAccount storage scope بررسی می‌شوند.

نتیجه:

```text
5 passed
```

## بازبینی تولیدی رابط

### TypeScript و Build

```text
npm.cmd run check
PASS

npm.cmd run build
977 modules transformed
PASS
```

Vite هشدار غیرمسدودکنندهٔ قبلی دربارهٔ Chunk بزرگ‌تر از ۵۰۰ KiB را گزارش می‌کند. Bundle اصلی نهایی حدود 873.56 KiB و gzip آن حدود 260.32 KiB است. این هشدار خطای Phase 6-D نیست، اما Code splitting برای فاز بهینه‌سازی بعدی باقی می‌ماند.

### بررسی JavaScript مستقل

```text
node --check ui/src/ui33-runtime-patch.js
PASS
```

### بازبینی تصویری در مرورگر محلی ایزوله

هیچ Backend، Provider یا دادهٔ واقعی استفاده نشد. ابتدا Build تولیدی با API ناموجود برای وضعیت قطع ارتباط و سپس با یک Fixture محلی فقط‌خواندنی و دادهٔ خالی برای Workspace بررسی شد. Fixture و Process موقت پس از آزمون حذف شدند.

- Mobile login surface در `390x844`: `presentation-shell=mobile` و بدون Horizontal overflow.
- Desktop login surface در `1366x768`: `presentation-shell=desktop` و بدون Horizontal overflow.
- Mobile workspace در `390x844`: Navigation پایین fixed، بدون Horizontal overflow.
- هدف لمس «بیشتر»: `78x56` پیکسل.
- Rail: `scrollHeight=clientHeight=66` و بدون Scrollbar پنهان.
- Popover منو: `374x334` پیکسل، از `x=8..382` و `y=440..774`، کاملاً داخل Viewport.

بازبینی تصویری دو نقص پیش از پذیرش را پیدا و اصلاح کرد:

1. `.rail-top` در Phone پنهان بود و منوی تنظیمات/خروج دسترس‌پذیر نبود.
2. Theme rail ششمین آیتم پنج ستون بود و ردیف پنهان/Scrollbar عمودی ایجاد می‌کرد.

## نتایج Regression

### کل Phase 6

```text
Phase 6-A + 6-B + 6-C + 6-D focused:
46 passed
```

### کل Repository

```text
412 tests collected
411 passed
1 historical failure
```

تنها Failure همان مورد شناخته‌شدهٔ قبل از ۶-C/۶-D است:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

Fixture آن رشتهٔ لاتین `Documents\Eitaa` تولید می‌کند اما روی Workspace فارسی انتظار `Documents\ایتا` دارد. فایل آزمون و فایل Runtime مربوطه در Phase 6-C و Phase 6-D تغییر نکردند.

اجرای کل Suite با حذف فقط همین مورد:

```text
411 passed
1 deselected
```

## وضعیت Config واقعی و Side effectها

`bridge.json` واقعی تغییر نکرد و Loader منبع فعلی این وضعیت امن را تأیید کرد:

```json
{
  "deployment_mode": "desktop_loopback",
  "bind": ["127.0.0.1", 8765],
  "app_user_auth": false,
  "multi_session": false,
  "remote_messenger_auth": false
}
```

در Phase 6-D موارد زیر انجام نشدند:

- Bind واقعی LAN یا بازکردن Port
- اجرای Firewall rule یا نصب Windows Service
- تغییر Router، UPnP، DMZ یا Port forwarding
- فعال‌سازی AppUser auth یا Multi-session در Config واقعی
- Login، OTP، Logout، Sync یا Send واقعی Eitaa
- اتصال واقعی Bale، Rubika یا SoroushPlus
- Migration یا تغییر دادهٔ واقعی
- Commit، Push یا Stage کردن فایل‌ها

Socketهای Acceptance فقط روی `127.0.0.1` و Port موقت/آزمونی بودند و همهٔ Processهای محلی پس از بازبینی متوقف شدند.

## موارد صریحاً Deferred

- Process isolation کامل هر MessengerAccount: Phase 7
- Unified Read Model: Phase 8
- MobileShell کامل و Unified Inbox: Phase 9
- Discovery و Contract واقعی Providerهای Bale/Rubika/SoroushPlus: فقط پس از مستندات و آزمون واقعی هر Provider
- HTTPS یا استقرار عمومی: خارج از قرارداد `trusted_lan_http`
- Code splitting رابط: بهینه‌سازی بعدی، خارج از Acceptance امنیتی/عملیاتی Phase 6

## جمع‌بندی پذیرش

Phase 6-D completed and accepted.  
Phase 6-A through Phase 6-D completed.  
Phase 6 closed without enabling real LAN rollout or real provider operations.

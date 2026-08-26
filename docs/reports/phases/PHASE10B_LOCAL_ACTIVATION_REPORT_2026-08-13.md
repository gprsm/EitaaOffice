# Phase 10-B Local Activation Report — 2026-08-13

## نتیجه

**Phase 10-B کامل و پذیرفته شد.** سرویس واقعی از سورس جاری روی Loopback اجرا
شد، AppUser توسط خود کاربر در UI وارد شد، نشست واقعی ایتا و مرز دادهٔ حساب با
metadata امن تأیید شدند و پذیرش دیداری Desktop/Mobile و تمام تست‌های مرتبط
موفق بودند.

هیچ نام کاربری، رمز، OTP، Cookie، Token، challenge id، شمارهٔ کامل یا Secret
در این گزارش خوانده یا ثبت نشده است.

## مبنای ادامه و حفاظت Worktree

- شاخه: `main`
- Commit مبنا: `a4df3ecf2bcd4ab658c5361afdc287444694fcd2`
- Worktree عمداً dirty حفظ شد.
- Snapshot آغاز نوبت: ۴۰ فایل tracked تغییرکرده و ۲۲۸۳ ورودی untracked
- Snapshot پایان 10-B: ۴۰ فایل tracked تغییرکرده و ۲۳۳۸ ورودی untracked؛
  افزایش فقط شامل artifactهای وریفای/تست و گزارش‌های همین نوبت است.
- `git diff --check`: موفق
- هیچ reset، checkout، clean، stage، commit یا push انجام نشد.
- `bridge.json` واقعی حفظ شد:
  - bytes: 2383
  - SHA-256 پیش و پس از فعال‌سازی نهایی:
    `5EA3850DDEB14D1776E6DA2A01D303C2EA1AA7C463D6CB72F5E46B5BEE6B4BBC`

## راه‌اندازی واقعی از Source

- پیش از اجرا، Port 8765 Listener نداشت.
- Backend با Python محیط پروژه و ماژول موجود در `src` اجرا شد؛ نسخهٔ نصب‌شدهٔ
  قدیمی مبنای import نبود.
- Bind فقط روی `127.0.0.1:8765` باقی ماند.
- UI از build واقعی `ui/dist` سرو شد.
- سرویس دسترسی خروجی شبکهٔ لازم برای Provider داشت.
- هیچ Windows Service، Firewall، Router، Network Profile، bind روی 80/443 یا
  تنظیم بیرونی تغییر نکرد.

نتیجهٔ زنده:

```text
listener=127.0.0.1:8765
health.ok=true
health.status=alive
readiness.ok=true
readiness.status=ready
deployment_mode=desktop_loopback
ui_http_status=200
```

## ورود خصوصی AppUser

- UI روی دروازهٔ «ورود کاربر محلی» به کاربر تحویل شد.
- خود کاربر Credential خصوصی را فقط در UI وارد کرد.
- Codex فیلدهای Credential را پر نکرد و Cookie، Token یا Storage مرورگر را
  بازرسی نکرد.
- موفقیت ورود از تغییر دیداری به Workspace واقعی و metadata سمت سرور تأیید شد.
- پس از ورود، شمار نشست‌های فعال AppUser در metadata برابر ۲ بود؛ هیچ شناسه یا
  Token نشست خوانده نشد.
- Reload پس از build تولیدی، نشست AppUser و Workspace را حفظ کرد.

Artifact وریفای امن:

`backups/phase10-rollout/phase10b-local-activation-verification-20260813-final.json`

- نتیجه: `verified=true`
- کنترل‌ها: ۱۹/۱۹ موفق

## داده، Audit و نشست ایتا

- Contacts schema: 2
- Contacts/Category: ۵۷۴/۳
- Contacts quick check: `ok`
- Contacts foreign-key violations: صفر
- Coordinator schema: 5
- Coordinator quick check: `ok`
- Coordinator foreign-key violations: صفر
- زنجیرهٔ Audit هماهنگ‌کننده: معتبر
- زنجیرهٔ Audit Contacts: معتبر
- AppUser auth: فعال
- Multi-session: فعال
- Worker process feature: طبق ترتیب rollout خاموش
- Provider: Eitaa
- Provider auth state: `authenticated`
- `session_generation=4`
- safe reason: `remote_session_validated`

این وریفای فقط metadata امن را خواند و به Session payload، OTP، رمز دوم، Token
یا شمارهٔ کامل دسترسی نداشت.

## مرز حساب و peer file

اسکن فقط‌خواندنی کاتالوگ واقعی پس از ورود و پس از build:

```text
catalog_rows=427
inside_selected_account=427
outside_selected_account=0
missing_peer_files=0
invalid_peer_paths=0
```

- یک گفتگوی واقعی و پیام‌های ذخیره‌شده در Workspace باز شدند.
- عبارت خطای `peer_file is outside the selected MessengerAccount.` در UI ظاهر
  نشد.
- Console مرورگر برای `peer_file` دارای صفر رخداد error بود.
- هیچ مسیر خارج حساب برای رفع خطا پذیرفته یا whitelist نشد؛ کنترل fail-closed
  موجود حفظ شد.

## پذیرش دیداری واقعی

### اندازهٔ جاری — 1256 × 912

- Rail: `72 × 912`، ردیف ۱
- Conversation list: `401.91 × 912`، ردیف ۱
- Content: `782.09 × 912`، ردیف ۱
- Scroll width دقیقاً برابر viewport بود؛ overflow افقی وجود نداشت.

### Desktop — 1280 × 720

- Grid: `72px 409.59px 798.41px`
- Grid row: یک ردیف `720px`
- Rail، conversation list و content همگی از `y=0` و با ارتفاع کامل 720 بودند.
- WordPress زیر breakpoint 1500 یک Drawer با `position=fixed` بود.
- Drawer باز در `x=760` با عرض 520 و ارتفاع 720 قرار گرفت و Track جدیدی به
  Grid تحمیل نکرد.
- overflow افقی: صفر

### Desktop — 1600 × 900

- Grid: `72px 352px 760px 416px`
- Rail، conversation list، content و WordPress همگی در یک ردیف 900px بودند.
- WordPress در این عرض ستون چهارم عادی و نه Drawer شناور بود.
- overflow افقی: صفر

### Mobile — 390 × 844

- Content تک‌ستونه با عرض کامل 390 و ارتفاع 778 بود.
- Navigation لمسی پایین صفحه با عرض 390 و ارتفاع 66 قرار گرفت.
- Conversation list خارج Canvas و قابل فراخوانی به‌صورت Drawer بود.
- WordPress به‌صورت sheet پنهان/قابل فراخوانی و نه Grid column بود.
- document scroll width: 390؛ overflow افقی صفر

### Mobile — 360 × 800

- Content تک‌ستونه با عرض کامل 360 و ارتفاع 734 بود.
- Navigation پایین صفحه با عرض 360 و ارتفاع 66 قرار گرفت.
- document scroll width: 360؛ overflow افقی صفر
- خطای account/peer boundary: صفر

پس از آزمون breakpointها، viewport override حذف و مرورگر به اندازهٔ واقعی
`1256 × 912` بازگردانده شد.

## تست‌های نهایی

### Python

بستهٔ دقیق regression مربوط به Account/API/Catalog/Runtime:

```text
65/65 passed
```

فایل‌های آزموده‌شده:

- `tests/test_account_runtime.py`
- `tests/test_application_api.py`
- `tests/test_dialog_catalog.py`
- `tests/test_runtime_ownership.py`

### UI و build

```text
TypeScript check: passed
Phase 9 workspace: 11/11 passed
Phase 9 responsive/visual acceptance: 10/10 passed
Phase 10 local activation: 7/7 passed
Scroll model: 10/10 passed
Grouped-media model: 16/16 passed
Production build: passed (981 modules transformed)
```

Build فقط هشدار غیرمسدودکنندهٔ اندازهٔ chunk اصلی را گزارش کرد؛ خطای build یا
TypeScript وجود نداشت. UI build جدید از همان سرویس Reload و Workspace واردشده،
چهار pane اصلی و نبود خطای peer boundary دوباره تأیید شد.

## عملیات انجام‌نشده

- هیچ ارسال واقعی ایتا انجام نشد.
- هیچ Login/Logout ارائه‌دهنده اجرا نشد.
- هیچ mutation یا انتشار واقعی WordPress انجام نشد.
- Laragon لازم نشد.
- هیچ rollback واقعی، حذف Legacy یا تغییر Firewall/Router/Service انجام نشد.
- Phase 11 شروع نشد.

## دروازهٔ خروج 10-B

تمام معیارهای فعال‌سازی محلی برآورده‌اند. ادامهٔ مجاز، Phase 10-C با تعریف
محیط‌مستقل و ترتیب C1 تا C4 است. Pilot واقعی حساب دوم، WordPress واقعی و bind
واقعی 80/443 طبق تصمیم استقرار deferred می‌مانند مگر کاربر در همان لحظه مجوز
و آمادگی صریح بدهد.

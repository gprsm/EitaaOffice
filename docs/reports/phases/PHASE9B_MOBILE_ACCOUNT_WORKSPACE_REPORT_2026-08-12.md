# گزارش مستقل Phase 9-B — Workspace موبایل و حساب انتخاب‌شده

تاریخ: ۲۰۲۶-۰۸-۱۲  
وضعیت: **تکمیل‌شده و آزموده‌شده**  
مرز گزارش: پایان 9-B؛ مدیریت نشست دستگاه مربوط به 9-C نیست.

## نتیجهٔ اجرایی

- `MobileShell` و `DesktopShell` به‌صورت صریح ساخته شدند، ولی یک درخت AppUser/Account/API مشترک دارند.
- Account selector موجود حفظ و lifecycle تغییر حساب با remount کامل Workspace تثبیت شد.
- هر درخواست UI اکنون Account scope را در لحظهٔ آغاز snapshot می‌کند، همان شناسه را به Backend می‌فرستد و اگر پیش از دریافت پاسخ حساب عوض شده باشد، نتیجه را با `ApiAccountScopeChangedError` کنار می‌گذارد.
- این fencing مانع می‌شود Poll یا Job قدیمی حساب A پس از انتخاب حساب B، شناسهٔ Job/Peer/Contact قبلی را روی حساب جدید استفاده کند.
- Stateهای React مربوط به گفتگو، پیام، مخاطب، Quick Send، اعضا، Composer و Job با کلید حساب remount می‌شوند.
- LocalStorage از قبل با `AppUser + MessengerAccount` scope می‌شد؛ آزمون مستقل برخورد User/Account را تثبیت کرد.
- Cache درون‌حافظه‌ای Avatar نیز Account scope گرفت تا Peer/Site یکسان میان دو حساب برخورد نکند.
- Polling عملیات طولانی از فاصلهٔ ثابت خارج شد:
  - Desktop فعال: پایهٔ ۷۵۰ms؛
  - Mobile فعال: پایهٔ ۱۲۵۰ms؛
  - Save-Data: حداقل ۲۵۰۰ms؛
  - Tab پس‌زمینه: حداقل ۸ ثانیه؛
  - Reconnect: backoff کران‌دار ۴ تا ۳۰ ثانیه.
- Poll ثابت Contact import با loop قابل لغو و تطبیقی جایگزین شد؛ loop پس از unmount/تعویض حساب ادامه نمی‌یابد.
- Navigation موبایل، Drawer گفتگو، Full-screen Material dialog، bottom navigation، Safe area و Touch targetهای ۴۴px موجود حفظ و توسط قرارداد 9-B تثبیت شدند.

## آزمون مستقل Workspace

فایل: `ui/scripts/run-phase9-workspace-tests.mjs`

نتیجه: **۱۰/۱۰ موفق**:

- Fencing حساب و تشخیص پاسخ دیررس؛
- جداسازی کلیدهای AppUser/Account؛
- Polling موبایل، پس‌زمینه، Save-Data و reconnect؛
- Scope آواتار و remount Workspace؛
- استفادهٔ همهٔ loopهای طولانی از Poll تطبیقی؛
- وجود Shell مستقل موبایل/دسکتاپ با منطق مشترک؛
- قرارداد CSS موبایل، Safe area و Touch target.

## QA مرحله

- Backend مرتبط با Scope/Job/Policy/Media/Auth: **۳۲/۳۲ موفق**.
- TypeScript check: موفق.
- Production build: موفق؛ ۹۸۰ module.
- کل مجموعهٔ Python پس از 9-B: **۴۷۱/۴۷۱ موفق**.

Build یک هشدار غیرمسدودکننده برای chunk اصلی ۸۸۱٫۵۹ kB (gzip برابر ۲۶۲٫۵۵ kB) دارد. این مورد صحت/جداسازی را نقض نمی‌کند و برای بهینه‌سازی bundle در پذیرش نهایی ثبت شده است.

## فایل‌های اصلی تغییرکرده

- `ui/src/App.tsx`
- `ui/src/ConnectionStatus.tsx`
- `ui/src/lib/api.ts`
- `ui/src/lib/avatarLoader.ts`
- `ui/src/lib/accountScope.mjs`
- `ui/src/lib/accountScope.d.mts`
- `ui/src/lib/polling.mjs`
- `ui/src/lib/polling.d.mts`
- `ui/scripts/run-phase9-workspace-tests.mjs`
- `ui/package.json`

## Feature Flag و ایمنی

- `multi_session` در تنظیم واقعی فعال نشد؛ پذیرش با Fake/contract انجام شد.
- هیچ Provider/WordPress واقعی، Login/OTP/Sync/Send، مهاجرت یا تغییر شبکه اجرا نشد.
- `bridge.json` واقعی نوشته نشد.
- هیچ reset/checkout/stage/commit/push انجام نشد.

## ورودی مرحلهٔ بعد

9-C باید نشست‌های AppUser را با metadata امن دستگاه، last activity/expiry و هشدارها فهرست کند و خروج از یک نشست یا همهٔ نشست‌ها را بدون نمایش Token یا IP کامل ارائه دهد.

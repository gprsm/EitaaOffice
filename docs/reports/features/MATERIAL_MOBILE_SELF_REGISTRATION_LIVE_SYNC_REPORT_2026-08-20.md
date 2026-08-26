# گزارش Material/mobile، ثبت‌نام خودخدمت و دریافت خودکار پیام

تاریخ: 2026-08-20  
نتیجه: `IMPLEMENTED / AUTOMATED_VERIFIED / NOT_LIVE_PROVIDER`  
دامنه: AppUser Auth، session policy، UI Material/mobile، dialog/message refresh و مستندسازی  
اثر Provider واقعی: `NONE`

## ۱. نتیجهٔ محصول

1. صفحهٔ ورود دکمهٔ «کاربر جدید هستم» دارد. کاربر شبکهٔ خصوصی می‌تواند خود را ثبت کند و سپس از Gate حساب پیام‌رسان، حساب Eitaa خود را اضافه کند.
2. حداقل رمز AppUser چهار نویسه است؛ رمز چهاررقمی پذیرفته می‌شود. حداکثر طول/بایت، منع control character، PBKDF2-600000، salt مستقل، dummy hash، throttle، lockout، CSRF و revoke حفظ شده‌اند.
3. idle timeout و absolute timeout هر دو یک سال‌اند و Cookie مرورگر `Max-Age=31536000` دارد. نشست با logout، revoke، غیرفعال‌شدن کاربر یا تغییر رمز همچنان باطل می‌شود.
4. همهٔ visual surfaceهای فعال با Material UI و `theme/sx` ساخته شده‌اند. source فعال TSX فاقد `className` و import stylesheet اختصاصی است.
5. رابط mobile-first است: safe-area، shell صریح mobile/desktop، bottom navigation، `100dvh/100svh`، Dialog تمام‌صفحه، فرم تک‌ستونه و touch target حداقل 44px دارد.
6. پیام گفتگوی باز و top/unread فهرست گفتگوها خودکار تازه می‌شوند. کاربر برای دیدن پیام تازه reload یا دکمهٔ بارگذاری لازم ندارد.

## ۲. مرز امنیت ثبت‌نام

- route عمومی کنترل‌شده: `POST /api/v2/app-auth/register`؛
- فقط در صورت روشن‌بودن AppUser Auth و self-registration؛
- فقط در profileهای `desktop_loopback` و `trusted_lan_http`؛
- در `web_reverse_proxy` عمومی fail-closed؛
- role ثبت‌نامی همیشه `user` و وجود مدیر فعال الزامی؛
- پیام duplicate عمومی است و client امکان تعیین role، account id، Membership یا مسیر ندارد؛
- Audit فقط actor/result/reason و metadata امن دارد؛ username/password/token/CSRF ثبت نمی‌شوند.

Config اجرایی `bridge.json` فقط در چهار فیلد مجازشدهٔ مالک تغییر کرد: self-registration روشن، idle=525600 دقیقه و absolute=8760 ساعت؛ AppUser Auth/multi-session از قبل در مسیر جاری فعال بودند. هیچ Session، Provider credential، `data/`، `runtime/`، `diagnostics/` یا backup بازنویسی نشد.

## ۳. دریافت خودکار و account scope

### گفتگوی باز

- polling تطبیقی foreground: حدود 0.75 ثانیه desktop و 1.25 ثانیه mobile؛
- offline، hidden tab، save-data و خطا باعث کاهش آهنگ و backoff محدود می‌شوند؛
- merge با شناسهٔ پیام انجام می‌شود و scroll memory/anchor گفتگو حفظ می‌شود؛
- پاسخ دیررس فقط اگر MessengerAccount و peer فعال هنوز یکسان باشند commit می‌شود.

### فهرست گفتگوها

- route تازه: `POST /api/v1/dialogs/live-sync`؛
- foreground: حدود 2.5 ثانیه desktop و 4 ثانیه mobile؛
- فقط صفحهٔ نخست محدود 100 گفتگو از Provider خوانده و top/unread upsert می‌شود؛
- `finalize_snapshot=False` است، بنابراین گفتگوهای قدیمی خارج از صفحهٔ نخست پنهان نمی‌شوند؛
- loop فقط read است و هیچ Send/Invite/mutation را retry نمی‌کند.

این قرارداد near-real-time polling است، نه WebSocket/Push. به‌علت انجام‌نشدن Provider pilot در این نوبت، سطح شاهد آن Automated/Contract است.

## ۴. ماژول‌بندی و Material UI

- `ui/src/AppUserGate.tsx` و `AuthBrand.tsx`: setup/login/register؛
- `ui/src/MessengerAccountGate.tsx`: انتخاب و افزودن حساب؛
- `ui/src/WorkspaceNavigation.tsx`: navigation دسکتاپ/موبایل؛
- `ui/src/ConversationListPage.tsx`: list/search/unread؛
- `ui/src/ChatHeader.tsx`: header/search/live state؛
- `ui/src/SettingsPage.tsx`: تنظیمات مستقل؛
- `ui/src/ContactDirectoryModal.tsx`: دفترچهٔ Material؛
- `ui/src/MaterialIndexWorkbench.tsx` و `MessageIndexEditor.tsx`: ابزارهای ایندکس lazy؛
- `ui/src/MaterialToast.tsx`: Snackbar/Alert با صف محدود و buffer رخداد پیش از mount؛
- `ui/src/App.tsx`: orchestration state، timeline مجازی و composerهای stateful مشترک.

CSSهای تاریخی حذف نشدند تا تغییر کاربر یا سابقه از بین نرود، اما هیچ‌کدام در runtime import نمی‌شوند. `react-toastify` و CSS آن از dependency graph حذف و Toast به Material منتقل شد.

## ۵. شواهد نهایی آزمون

| دامنه | نتیجه |
|---|---:|
| Full Backend | `566/566` |
| Migration suite خارج از محدودیت sandbox | `7/7` |
| UI/Python contractهای مرتبط | `65/65` |
| Scroll model | `10/10` |
| Grouped media | `16/16` |
| Phase 9 workspace | `11/11` |
| Phase 9 acceptance contract | `11/11` |
| Phase 10 local activation | `7/7` |
| Phase 11 onboarding | `7/7` |
| Phase 11-B2 capability | `6/6` |
| Mobile auth/live contract | موفق |
| UI/Electron observability | موفق |
| TypeScript check | موفق |
| Production build | موفق؛ 1006 module |
| Main bundle | `785.60 kB`، gzip `240.96 kB` |

هشدار bundle بزرگ‌تر از 500 kB همچنان غیرمسدودکننده و در F-013 باز است. نسبت به 894.38 kB مبنای 11-0 کاهش یافته، اما استخراج composer/controllerهای سنگین هنوز بدهی performance است.

## ۶. Failure و تحلیل اصلاحی

1. اجرای full pytest داخل sandbox 20 شکست داشت: 18 assertion قدیمی هنوز class/CSS اختصاصی را الزام می‌کردند و با تصمیم Material-only متناقض بودند؛ قراردادها به component، `sx`، aria و module جاری منتقل شدند. دو شکست دیگر `os.replace` پوشهٔ موقت Windows بود؛ suite مهاجرت خارج از sandbox `7/7` و full suite نهایی `566/566` شد.
2. یک rerun هدفمند تنها label تاریخی `Access Hash` را انتظار داشت؛ قرارداد به label امن فعلی «شناسه فنی» اصلاح و `65/65` شد.
3. یک خطای TypeScript میانی پس از حذف Icon سفارشی، type قدیمی `IconName` را نشان داد؛ reference باقیمانده حذف و check/build نهایی سبز شد.
4. چند patch تجمیعی به‌علت context خطوط بلند اعمال نشدند؛ هیچ mutation ناقص نداشتند و patchهای کوچک فایل‌محور جایگزین شدند.
5. Browser درون برنامه localhost را با `ERR_BLOCKED_BY_CLIENT` رد کرد؛ Chrome در دسترس نبود و file URL نیز طبق مرز امنیتی ابزار رد شد. bypass انجام نشد و پذیرش دیداری تازه در F-025 باز ماند.
6. Pytest فقط هشدار عدم امکان نوشتن `.pytest_cache` داد؛ basetempهای workspace استفاده شدند و نتیجهٔ آزمون معتبر بود.
7. Vite dev serverِ تلاش دیداری در dependency scan به HTMLهای runtime/Edge profile رسید و access/resolve/EPERM گزارش کرد؛ این invocation شاهد build نبود. production build مستقل موفق شد، server با Ctrl-C متوقف و Port 5173 بدون listener تأیید شد.

## ۷. فایل‌های اصلی تغییرکرده

Backend/config:

- `src/eitaa_bridge/config.py`
- `src/eitaa_bridge/infrastructure/config/loader.py`
- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `src/eitaa_bridge/application/api.py`
- `bridge.json`
- `bridge.example.json`

UI:

- `ui/src/App.tsx`
- `ui/src/AppUserGate.tsx`
- `ui/src/AppUserManagementPanel.tsx`
- `ui/src/AuthBrand.tsx`
- `ui/src/MessengerAccountGate.tsx`
- `ui/src/WorkspaceNavigation.tsx`
- `ui/src/ConversationListPage.tsx`
- `ui/src/ChatHeader.tsx`
- `ui/src/SettingsPage.tsx`
- `ui/src/MaterialToast.tsx`
- `ui/src/ClientErrorBoundary.tsx`
- `ui/src/ConnectionStatus.tsx`
- `ui/src/QuickSendBar.tsx`
- `ui/src/main.tsx`
- `ui/src/theme.ts`
- `ui/package.json` و `ui/package-lock.json`

Tests:

- `tests/test_app_user_auth.py`
- `tests/test_app_user_api.py`
- `tests/test_application_api.py`
- `tests/test_config.py`
- contractهای UI Python مرتبط با Material/mobile/scroll/composer
- `ui/scripts/run-mobile-auth-live-tests.mjs`
- scriptهای Phase 9 workspace/acceptance

## ۸. اثر بیرونی و مرز ادامه

- هیچ Login، OTP، Provider network، Send، Invite یا WordPress publish واقعی انجام نشد.
- هیچ Firewall، Proxy، Certificate، Port 80/443، service restart، rollback یا migration DB عملیاتی انجام نشد.
- Git reset/checkout/clean/stage/commit/push انجام نشد و worktree dirty حفظ شد.
- Phase 11-C و Live 11-D همچنان مطابق گزارش blocker به Pilot حساب دوم Eitaa یا تصمیم/مجوز Bale وابسته‌اند.

گزارش blocker: `../blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md`.

# گزارش نهایی Phase 11-0 — Multi-account Onboarding Foundation

تاریخ: 2026-08-13  
سطح پذیرش: `IMPLEMENTED / FAKE_VERIFIED`  
وضعیت Pilot واقعی حساب دوم: `DEFERRED — نیازمند اعلام آمادگی و ورود خصوصی کاربر`  
وضعیت Bale: `NOT CONFIGURED — مرحلهٔ بعد Discovery مستند`  

## ۱. نتیجهٔ اجرایی

Phase 11-0 برای افزودن چند حساب Eitaa به یک AppUser بدون بازنویسی معماری موجود پیاده‌سازی و با Unit/Contract/Fake/Adversarial، رگرسیون کامل و پذیرش دیداری Desktop/Mobile تأیید شد.

اکنون کاربر در UI دکمهٔ «افزودن حساب پیام‌رسان» دارد. Provider از catalog سمت سرور می‌آید، هویت خصوصی فقط در فرم کوتاه‌عمر وارد می‌شود، حساب و Membership در یک تراکنش ساخته می‌شوند، UUID و مسیرها کاملاً server-owned هستند و حساب تازه هیچ Worker یا اتصال شبکه‌ای را خودکار آغاز نمی‌کند.

هیچ حساب واقعی دوم ساخته نشد، هیچ OTP/رمز/Cookie/Token/شمارهٔ واقعی مشاهده یا ثبت نشد، هیچ ارسال واقعی ایتا و هیچ عملیات WordPress انجام نشد.

## ۲. محدودهٔ پیاده‌سازی‌شده

### ۲.۱. Backend و Coordinator

- Command ساخت یا reuse امن `PhoneAccount + owner Membership + MessengerAccount + session metadata`؛
- تراکنش `BEGIN IMMEDIATE` برای سریال‌کردن درخواست‌های هم‌زمان؛
- idempotency طبیعی با fingerprint نصب و قید یکتایی `phone identity + provider`؛
- بازگرداندن همان MessengerAccount برای retry یا race همان مالک؛
- رد عمومی و non-enumerating برای تلاش مالک دیگر؛
- سقف self-service برابر ۲۰ MessengerAccount غیرآرشیوی برای هر owner؛
- تولید همهٔ UUIDها سمت سرور؛
- lifecycle اولیه `created/stopped` و auth state اولیه `absent`؛
- حفظ Schema نسخهٔ ۵ و اجتناب از Migration غیرضروری روی Coordinator واقعی.

### ۲.۲. حریم خصوصی هویت

- ورودی canonical E.164 فقط به `PhoneProtector` داده می‌شود؛
- production از DPAPI machine-scope و install fingerprint استفاده می‌کند؛
- DB متن کامل شماره را نگهداری نمی‌کند؛
- UI فقط hint پوشیده را دریافت می‌کند؛
- فرم پس از submit موفق/ناموفق یا cancel مقدار هویت را پاک می‌کند؛
- `autoComplete=off` است و هیچ local/session storage برای هویت استفاده نشده است.

### ۲.۳. API

Route تازه:

```text
POST /api/v2/messenger-accounts
```

قرارداد:

- AppUser session و CSRF معتبر الزامی؛
- `multi_session.enabled` الزامی؛
- allowlist Body فقط `provider`, `phone`, `label`؛
- هر Account ID، PhoneAccount ID، Session/Storage path یا فیلد اضافه رد می‌شود؛
- `201` برای حساب تازه و `200` برای reuse idempotent؛
- Provider غیرفعال پیش از پردازش هویت رد می‌شود؛
- پاسخ فقط account card و metadata امن دارد.

### ۲.۴. Provider descriptor

Descriptor اکنون این metadata امن را دارد:

- `provider` و `display_name`؛
- `configured` و `runtime_enabled`؛
- `onboarding_enabled`؛
- `account_identity_kind`؛
- `auth_steps`؛
- `reason_code` امن.

Eitaa برای onboarding/runtime فعال است. Bale فقط با نام نمایشی و reason غیرفعال وجود دارد؛ هیچ Endpoint، Login flow، Token، Session format یا Capability برای آن حدس زده نشد.

### ۲.۵. UI و تعویض حساب

- Provider دیگر union ثابت `eitaa | bale` نیست؛
- label، runnable و onboarding از descriptor سمت سرور خوانده می‌شوند؛
- Dialog افزودن حساب دارای Provider، هویت E.164 و label اختیاری است؛
- پیام حریم خصوصی قبل از ورود داده نمایش داده می‌شود؛
- حساب تازه card مستقل با Auth/Worker state دارد؛
- Start/Stop و انتخاب حساب از کنترل‌های موجود و account-scoped استفاده می‌کنند؛
- پس از Start صریح، Auth flow مرحله‌ای Eitaa موجود در scope همان حساب ادامه می‌یابد؛
- ساخت حساب به‌تنهایی هیچ Network یا Login واقعی اجرا نمی‌کند.

## ۳. Observability و Audit

چهار Event نسخه‌دار به catalog افزوده شد:

- `messenger_account_onboarding_started`؛
- `messenger_account_onboarding_succeeded`؛
- `messenger_account_onboarding_reused`؛
- `messenger_account_onboarding_rejected`.

Eventها correlation، Provider، شناسهٔ opaque، نتیجه و reason امن دارند و Body/هویت خصوصی را ثبت نمی‌کنند. Event Catalog پس از تغییر ۷۲ رخداد دارد.

Auditهای پایدار:

- `messenger_account.onboarding.created`؛
- `messenger_account.onboarding.reused`؛
- `messenger_account.onboarding.rejected`.

Audit رد هویت متعلق به مالک دیگر عمداً `phone_account_id` و `messenger_account_id` ندارد تا وجود رکورد را افشا نکند. تغییر مالکیت created/reused علاوه بر Runtime log در زنجیرهٔ Audit ثبت می‌شود.

## ۴. آزمون امنیت و جداسازی

فایل اختصاصی `tests/test_phase11_0_multi_account_onboarding.py` این حالت‌ها را پوشش می‌دهد:

1. ساخت چند حساب Eitaa برای یک AppUser؛
2. retry پس از ساخت مجدد service و restart منطقی؛
3. race دو درخواست هم‌زمان و تولید دقیقاً یک حساب؛
4. جداسازی AppUser دوم و جلوگیری از claim هویت؛
5. عدم افشای شناسه در Audit ردشده؛
6. رد Account ID و path جعلی Client؛
7. رد Bale قبل از فراخوانی PhoneProtector؛
8. پاسخ فقط با شمارهٔ پوشیده؛
9. نبود شمارهٔ کامل و ciphertext در Runtime log؛
10. نبود شمارهٔ کامل در فایل SQLite.

## ۵. نتایج اعتبارسنجی

| اعتبارسنجی | نتیجه |
|---|---:|
| Python full regression | `518/518 passed` در 91.5s |
| Python onboarding/observability/account targeted | `16/16 passed` |
| UI Phase 11 assertions | `7/7 passed` |
| UI assertionهای شماره‌دار همهٔ suiteها | `61/61 passed` |
| UI/Electron observability contract | passed |
| TypeScript check | passed |
| Vite production build | passed؛ 982 module |
| Runtime log PII/redaction | 9106 record، invalid JSON=0، finding=0 |
| Markdown/project map checks | refresh موفق؛ stale=0 و broken link=0 |
| UTF-8 و شمارهٔ کامل در ۵ سند نهایی | encoding finding=0؛ full-phone finding=0 |

## ۶. پذیرش دیداری Fake

برای جلوگیری از ورود Credential واقعی، نمونهٔ Development/Fake فقط روی Loopback اجرا و پس از آزمون متوقف شد.

Desktop:

- پنل تنظیمات، card حساب، Provider label، Auth/Worker state و دکمهٔ افزودن قابل‌مشاهده بودند؛
- فرم فقط Eitaa فعال را عرضه کرد؛
- دکمهٔ ساخت برای هویت synthetic معتبر فعال شد؛
- cancel و بازکردن دوباره مقدار ورودی را خالی نشان داد.

Mobile:

- viewport دقیق `390×844`؛
- عرض Dialog برابر 378px و داخل مرز 6px تا 384px بود؛
- `documentWidth=390` و horizontal overflow برابر false؛
- دکمه‌های cancel/create و همهٔ فیلدها قابل‌دسترسی بودند.

سرویس واقعی `127.0.0.1:8765` پس از reload صفحهٔ ورود AppUser را نشان داد. هیچ Credential وارد نشد و پذیرش حساب واقعی دوم عمداً ادامه نیافت.

## ۷. Warningها و خطاهای کشف‌شده

### ۷.۱. Warning رفع‌شده

MUI هشدار داد یک Button غیرفعال مستقیماً child Tooltip است. دکمهٔ Template در `QuickSendBar.tsx` داخل `span` قرار گرفت. تب Development تازه پس از اصلاح صفر console error/warning داشت.

### ۷.۲. Warning باز و غیرمسدودکننده

Vite chunk اصلی را `894.38 kB` minified گزارش کرد که از آستانهٔ 500 kB بزرگ‌تر است. این مورد در F-013 باز است و نیازمند bundle analysis/code splitting مستقل است؛ blocker عملکرد یا امنیت 11-0 نیست.

### ۷.۳. خطاهای invocation بدون اثر محصولی

- Python پیش‌فرض سیستم pytest نداشت؛ همهٔ آزمون‌های معتبر با `.venv` اجرا شدند.
- pytest ابتدا به Temp سراسری Windows دسترسی نداشت؛ basetemp دقیق داخل workspace استفاده شد.
- PowerShell اجرای `npm.ps1` را رد کرد؛ روش canonical `npm.cmd` موفق بود.
- `Start-Process` به‌دلیل duplicate PATH محیط sandbox آغاز نشد؛ Vite مستقیماً اجرا و سپس صریح terminate شد.
- Git نخست به‌دلیل dubious ownership فقط‌خواندنی متوقف شد؛ بررسی با `git -c safe.directory=<workspace>` انجام شد و Config تغییر نکرد.
- یک expectation قدیمی descriptor و fixtureهای اولیهٔ تست تازه در چرخهٔ توسعه شکست خوردند؛ قرارداد/fixture اصلاح و سپس targeted و full suite سبز شدند.
- یک validation block هنگام patch ابتدا در handler مجاور قرار گرفت؛ بازبینی موضعی آن را پیش از پذیرش حذف و در handler صحیح قرار داد.
- دو مسیر مستند هنگام lookup اشتباه نام‌گذاری شده بودند؛ مسیر canonical پیدا شد و هیچ فایل یا داده‌ای تغییر نکرد.
- نخستین فرمان تجمیعی کنترل نهایی از عملگر سه‌تایی ناسازگار با PowerShell این محیط استفاده کرد و parse نشد؛ فرمان فقط‌خواندنی بود، اثری نداشت و با `if/else` سازگار تکرار و موفق شد.

## ۸. فایل‌های اصلی تغییرکرده

- `src/eitaa_bridge/application/provider_adapter.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/infrastructure/coordinator/identity.py`
- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py`
- `src/eitaa_bridge/errors.py`
- `ui/src/MessengerAccountGate.tsx`
- `ui/src/AccessManagementPanel.tsx`
- `ui/src/main.tsx`
- `ui/src/QuickSendBar.tsx`
- `ui/scripts/run-phase11-onboarding-tests.mjs`
- `tests/test_phase11_0_multi_account_onboarding.py`

## ۹. محدودیت‌های آگاهانه

- DB `CHECK(provider IN ('eitaa','bale'))` و چند Audit/Worker contract ثابت هنوز برای Provider سوم عمومی نشده‌اند؛ F-004 باز و partial است.
- Bale Adapter/Discovery وجود ندارد و onboarding آن غیرفعال است.
- Pilot واقعی حساب دوم Eitaa انجام نشده است.
- Archive/Disable به‌جای delete اصل معماری است؛ این مرحله هیچ delete API اضافه نکرد.
- عملیات retention/disk health/Web metrics Observability همچنان partial است.

## ۱۰. مرحلهٔ بعد

مرحلهٔ بعدی `Phase 11-A — Bale Discovery` است:

- فقط بررسی روش رسمی/مجاز اتصال، Login/Session، Rate/Error و Capabilityها؛
- تولید Discovery report و contract پذیرفته‌شده؛
- بدون حدس Endpoint یا Session format؛
- بدون Login واقعی، Credential یا ارسال؛
- هر منبع اینترنتی باید از منبع رسمی/اولیه و با citation مستند شود.

Pilot واقعی حساب دوم Eitaa یک مسیر جداگانه و اختیاری است و فقط پس از اعلام آمادگی صریح کاربر اجرا می‌شود.

## ۱۱. اعلام پذیرش

`Phase 11-0` از نظر کد، Fake/Contract/Adversarial، رگرسیون، UI Desktop/Mobile و Observability پذیرفته است. سطح پذیرش `FAKE_VERIFIED` است، نه `LIVE_ACCEPTED` برای حساب دوم.

## ۱۲. پاک‌سازی کنترل‌شده

پس از ثبت نتایج، پنج basetemp دقیق متعلق به همین مرحله با پیشوند `.pytest-phase11-0-*` و پس از تطبیق Parent با ریشهٔ پروژه حذف شدند. این cacheها صرفاً خروجی بازتولیدپذیر آزمون بودند و بازیابی لازم ندارند. cacheهای قدیمی سایر مراحل و همهٔ config/session/data/runtime/catalog/backups دست‌نخورده ماندند؛ `git clean` یا حذف الگویی اجرا نشد.

کنترل نهایی فقط‌خواندنی ۲۴۲ ورودی در worktree عمداً dirty گزارش کرد (`63 deleted`، `44 modified` و `135 untracked`) که شامل سازمان‌دهی و توسعهٔ انباشتهٔ مراحل قبلی است. این وضعیت پاک، stage یا بازنویسی نشد. `git diff --check` بدون خطا بود و حضور `bridge.json`، Session، data، runtime، catalog و backups فقط با metadata تأیید شد.

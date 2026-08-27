# ساختار و مالکیت پروژه

آخرین بازبینی: 2026-08-26

## ۱. نمای ریشه

| مسیر | نقش | سیاست تغییر |
|---|---|---|
| `src/eitaa_bridge/` | Backend و دامنهٔ اصلی Python | کد canonical |
| `ui/` | React، Electron و build رابط | کد canonical |
| `tests/` | تست‌های Python و contract | همراه هر تغییر به‌روز شود |
| `scripts/` | ابزار migration، release، diagnostics و نگهداری | عملیات حساس با preview/approval |
| `docs/` | مشخصات، راهنما، گزارش و حافظه | یافتهٔ مهم همان روز ثبت شود |
| `installer/` | تعریف installer ویندوز | پس از build/acceptance تغییر کند |
| `vendor/` | وابستگی‌های vendored | فقط با منشأ و نسخهٔ روشن |
| `package_clean.py` | allowlist، manifest/receipt، privacy scan و verifier archive | هر تغییر نیازمند G-07 contract و fresh rehearsal |
| `scripts/build_wheel_stdlib.py` | wheel آفلاین deterministic از source/pyproject | خروجی باید با source parity و build دوگانه سنجیده شود |
| `dist/*.whl` | wheel نصب‌شوندهٔ کنترل‌شده | build artifact؛ pre-image و SHA ثبت و با source تطبیق شود |
| `data/` | دادهٔ عملیاتی محلی | محرمانه؛ جابه‌جا/پاک نشود |
| `runtime/` | state و log اجرای واقعی | محرمانه و غیرمنبع |
| `diagnostics/` | bundleهای پشتیبانی | خروجی عملیاتی؛ پیش از اشتراک scan شود |
| `backups/` | backupهای محلی | عملیات restore فقط با تأیید |
| `catalog/` | دادهٔ کاتالوگ محلی | مالکیت و account scope حفظ شود |
| `bridge*.json` و `.env*` | config واقعی/نمونه | `bridge.json` و `.env` محرمانه‌اند |
| `*.bat` در ریشه | launcherهای عمومی ویندوز | عمداً برای استفادهٔ دستی در ریشه‌اند |

## ۲. لایه‌های Backend

```text
src/eitaa_bridge/
├── domain/          قواعد، entityها و قراردادهای مستقل از I/O
├── application/     orchestration، API، auth، jobs و account runtime
├── infrastructure/  persistence، provider adapter، diagnostics و OS/network
└── interfaces/      CLI، HTTP server، Windows LAN و worker entrypoint
```

جهت وابستگی مطلوب: `interfaces → application → domain` و `infrastructure` از طریق قراردادها تزریق می‌شود. منطق Provider خاص نباید به UI یا endpoint عمومی نشت کند.

### مسیرهای مرجع چندحسابی و Provider

| مسیر | مسئولیت |
|---|---|
| `src/eitaa_bridge/application/provider_adapter.py` | کاتالوگ قابلیت Provider، وضعیت اجرا و قرارداد مراحل ورود |
| `src/eitaa_bridge/providers/contracts.py` | Provider Extension API v1، Manifest، DTO، Adapter/Worker protocol و validation |
| `src/eitaa_bridge/providers/registry.py` | allowlist و composition root صریح Fake/Eitaa/slotهای آینده |
| `src/eitaa_bridge/providers/testing.py` | contract probe آفلاین و Fake session store حساب‌محور |
| `src/eitaa_bridge/providers/fake/` | Adapter و registration آفلاین Provider سوم؛ test-only و پنهان از catalog محصول |
| `src/eitaa_bridge/providers/bale/slot.py` | scaffold غیرفعال بله بدون transport، endpoint یا factory |
| `src/eitaa_bridge/application/provider_capabilities.py` | تصمیم Capability حساب‌محور و نگاشت routeهای provider-backed |
| `src/eitaa_bridge/application/provider_orchestration.py` | ترتیب امن عمومی، deadline/idempotency، فراخوانی Adapter و result/error/log محدود |
| `src/eitaa_bridge/application/eitaa_provider_runtime_operations.py` | اجرای typed عملیات عمومی داخل Child هر حساب ایتا و مالکیت media cache همان Child |
| `src/eitaa_bridge/application/eitaa_provider_worker.py` | allowlist و fence درخواست‌های Provider RPC در Process Worker |
| `src/eitaa_bridge/application/process_runtime.py` | Parent-side allowlist برای درخواست‌های عمومی Process Runtime |
| `src/eitaa_bridge/application/api.py` | مرز HTTP، از جمله onboarding حساب پیام‌رسان با AppUser session و CSRF |
| `src/eitaa_bridge/infrastructure/dialog_catalog.py` | کاتالوگ account-scoped گفتگو، role معتبر حساب و capability محاسبه‌شدهٔ مدیریت گروه/کانال |
| `src/eitaa_bridge/infrastructure/eitaa/dialog_permissions.py` | استخراج fail-closed نقش owner/admin از metadata معتبر Eitaa بدون نگه‌داری raw payload |
| `src/eitaa_bridge/application/scheduler.py` | سریال‌سازی نشست مشترک Eitaa با اولویت پیام فعال، آواتار فعال و کار پس‌زمینه |
| `src/eitaa_bridge/providers/eitaa/application_adapter.py` | ترجمهٔ سازگاری Eitaa پشت قرارداد عمومی؛ runtime lifetime همچنان مال EitaaRuntimeRegistry است |
| `src/eitaa_bridge/infrastructure/coordinator/store.py` | تراکنش، مالکیت، idempotency، سقف حساب و audit چندحسابی |
| `src/eitaa_bridge/infrastructure/coordinator/receipts.py` | claim/complete پایدار، account-scoped و privacy-safe برای mutationهای Provider |
| `src/eitaa_bridge/infrastructure/coordinator/app_auth.py` | سرویس AppUser و حفاظت DPAPI هویت حساب پیش از persistence |
| `src/eitaa_bridge/infrastructure/coordinator/identity.py` | قرارداد حفاظت از شماره/هویت خصوصی |
| `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py` | واژگان canonical رخدادها و الزام audit |
| `src/eitaa_bridge/infrastructure/config/deployment_settings.py` | تنظیم اتمیک و اعتبارسنجی‌شدهٔ پورت داخلی و همگام‌سازی Host/Origin |

افزودن Provider تازه باید ابتدا از descriptor و adapter آغاز شود؛ قرار دادن شرط‌های پراکندهٔ نام Provider در UI یا API مجاز نیست. schema جاری Coordinator v7 و Contact v3 است؛ migrationهای تاریخی ثابت برای ارتقای نصب‌های قدیمی نگهداری می‌شوند.

راهنمای canonical ورود کد Provider در `PROVIDER_ADAPTER_DEVELOPMENT_GUIDE.md` است. package هر Provider فقط translation/transport اختصاصی خود را مالک می‌شود؛ context، account ownership، DTO، Registry، Worker IPC و observability مشترک بازنویسی نمی‌شوند.

## ۳. رابط کاربری

```text
ui/
├── src/             React/TypeScript، viewها و client API
├── electron/        shell، process ownership، IPC و desktop diagnostics
├── scripts/         تست‌های contract/source و finalization build
├── dist/            خروجی build؛ تولیدشونده
└── package.json     نسخه‌ها و فرمان‌های canonical UI
```

`ui/src/lib/api.ts` مرز client API و correlation است. `ui/electron/preload.cjs` تنها bridge مجاز renderer است و `ui/electron/main.cjs` مالک process/API محلی است.

Design System فعال فقط Material UI است. componentهای بصری از `theme.ts` و `sx` استفاده می‌کنند؛ `styles.css` و `login-experience.css` artifact تاریخیِ بدون import runtime هستند و نباید مبنای feature تازه قرار گیرند. `App.tsx` controller/orchestrator مشترک workspace است و presentationهای اصلی در moduleهای زیر جدا شده‌اند:

- `ui/src/AppUserGate.tsx` و `ui/src/AuthBrand.tsx`: setup/login/self-registration و هویت بصری Material؛
- `ui/src/MessengerAccountGate.tsx`: انتخاب/افزودن حساب Provider؛
- `ui/src/WorkspaceNavigation.tsx`: rail دسکتاپ، bottom navigation موبایل و منوی Material؛
- `ui/src/ConversationListPage.tsx`: فهرست، جست‌وجو، unread و عملیات گفتگو؛
- `ui/src/ChatHeader.tsx`: عنوان، وضعیت دریافت خودکار، فیلتر و جست‌وجوی پیام؛
- `ui/src/MessageContentCard.tsx`: Card Material هر پیام یا گروه متوالی، Header نویسنده، بلوک‌های مرتب متن/رسانه/فایل، Collapse و Actionهای انتخاب/ایندکس/استفاده؛
- `ui/src/lib/groupedMedia.ts`: مدل آلبوم رسمی/استنباطی و گروه محتوایی پنج‌دقیقه‌ای پیش از filter؛
- `ui/src/lib/avatarLoader.ts` و `avatarQueue.mjs`: cache حساب‌محور، lane مستقل cached-only/remote، promotion گفت‌وگوی فعال و صف task delayed/background با failure isolation؛
- `ui/src/LoginExperience.tsx`: Surface مرکزی و mobile-first ورود بدون panel معماری؛ lifecycle و بازیابی نشست در controller احراز هویت `App.tsx` می‌ماند؛
- `ui/src/SettingsPage.tsx`: تنظیمات جدا از workspace، شامل کنترل پورت داخلی شبکه/وب و opt-in پیش‌فرض‌خاموش نمایش پنل WordPress؛
- `ui/src/ContactDirectoryModal.tsx`: دفترچهٔ Material و virtualized؛
- `ui/src/MaterialToast.tsx`: صف Snackbar/Alert با buffer رخدادهای پیش از mount.

`POST /api/v1/dialogs/live-sync` صفحهٔ نخست محدود را برای refresh خودکار فهرست merge می‌کند؛ پیام گفتگوی باز از مسیر sync موجود polling می‌شود. هر دو loop باید MessengerAccount scope و stale-result guard را حفظ کنند. قرارداد source/build این بخش در `ui/scripts/run-mobile-auth-live-tests.mjs` است.

در release تمیز، `src/eitaa_bridge/application/bale_client/` قرنطینه و خارج از source/wheel است؛ فقط `providers/bale/slot.py` fail-closed برای descriptor صادقانه باقی می‌ماند. این مرز توسعهٔ Bale نیست و تغییر آن Trigger بازگشایی G-02/G-07 است.

مسیرهای مهم Phase 11-0:

- `ui/src/MessengerAccountGate.tsx`: فهرست، تعویض و dialog افزودن حساب بر مبنای descriptor؛ مقدار شماره در state موقت UI می‌ماند و پس از لغو/پایان پاک می‌شود.
- `ui/src/AccessManagementPanel.tsx`: نمایش و مدیریت دسترسی حساب‌های پیام‌رسان بدون فرض Eitaa-only در type.
- `ui/scripts/run-phase11-onboarding-tests.mjs`: contractهای source/UI برای onboarding چندحسابی.
- `tests/test_phase11_0_multi_account_onboarding.py`: آزمون‌های تراکنش، هم‌زمانی، مالکیت، privacy و API.

مسیرهای مهم Phase 11-B2:

- `ui/src/MessengerAccountGate.tsx`: snapshot قابلیت حساب‌محور و helper عمومی `hasCapability` با fail-closed هنگام loading/error/account switch.
- `ui/src/App.tsx` و `ui/src/QuickSendBar.tsx`: guard مستقل Dialog/History/Media/Text Send/Media Send پیش از request.
- `ui/src/ContactDirectoryModal.tsx`: guard مستقل Contact read/write برای حساب انتخابی.
- `ui/scripts/run-phase11b2-orchestration-tests.mjs`: contract ایستای UI برای snapshot/gate/fake fixture.
- `tests/test_phase11b2_provider_neutral_orchestration.py`: Contract/Fake/Adversarial شش عملیات، Process RPC، chunk broker، receipt persistence/restart، جداسازی، log و API.

## ۴. مستندات و گزارش‌ها

اسناد ریشه به پوشه‌های `docs/reports/`، `docs/handoffs/`، `docs/checklists/` و `docs/specifications/` منتقل شده‌اند. فقط `README.md`، `ARCHITECTURE_DECISIONS.md` و `AGENTS.md` به‌عنوان ورودی‌های canonical در ریشه‌اند. فهرست ماشینی در `REPORTS_INDEX.md` است.

## ۵. فایل‌های تولیدشونده و عملیاتی

- قابل بازتولید: `ui/dist/`، cacheهای تست، project map و reports index.
- تاریخچه/شاهد: گزارش‌های `docs/reports/` و artifactهای GMI.
- عملیاتی و غیرقابل‌جایگزینی: config واقعی، session، data، catalog، runtime و backup.
- cacheهای قدیمی `.pytest-*` متعلق به اجراهای پیشین دست‌نخورده می‌مانند. پوشه‌های موقت با پیشوند دقیق `.pytest-phase11-0-*` که فقط در همین مرحله ساخته شده‌اند، پس از ثبت نتیجه با حذف صریح همان مسیرها پاک می‌شوند؛ هیچ `git clean` یا الگوی عمومی استفاده نمی‌شود.

## ۶. نقشهٔ دقیق

`project-map/PROJECT_FILE_MAP.md` و `project-map/SYMBOL_INDEX.json` با `scripts/refresh_project_docs.py` ساخته می‌شوند. این نقشه فقط source/config/test/docs-safe را می‌خواند و مسیرهای runtime یا فایل‌های محرمانه را وارد نمی‌کند.

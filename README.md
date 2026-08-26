# Eitaa Bridge v0.7 — MVP 6.1.1 GMI 4

> راهنمای جاری پروژه از اینجا شروع می‌شود: [`AGENTS.md`](AGENTS.md) برای توسعه‌دهنده/Agent و [`docs/README.md`](docs/README.md) برای مشخصات، ساختار، لاگ، نقشهٔ فایل‌ها و گزارش‌ها. بخش‌های قدیمی‌تر این README برای حفظ تاریخچه باقی مانده‌اند و در صورت تعارض، `docs/project-memory/CURRENT_SYSTEM_BASELINE.md` مرجع وضعیت فعلی است.

نسخه نهایی و بهینه‌شده MVP برای اجرای روزمره روی رایانه شخصی و سیستم اداری.

- Product: `0.7.0-ui-mvp6.1.1-gmi4.2`
- Bridge package: `0.7.0.dev31`
- UI package: `0.7.29`
- Core: `0.6.0-core7.4.5-gmi1` / `eitaa-core==0.6.0.dev19`
- SQLite schema: `9`
- Local content-index schema: `2`
- Status: `contact sources and safe audience handoff`

## GMI 4 — منابع مخاطب و انتقال امن مخاطبان هدف

- از پنجرهٔ «مدیریت اعضای گفتگو» می‌توان اعضای منتخب یا کل Snapshot محلی را به دفترچه افزود. Backend شناسه‌ها را دوباره از SQLite معتبر می‌خواند؛ Access Hash هرگز به UI فرستاده نمی‌شود.
- تب «منابع ایتا» در دفترچه، فهرست‌های شماره‌ای را که قبلاً Resolve شده‌اند نشان می‌دهد و نتیجه‌های موجود را بدون Resolve تازه به دفترچه منتقل می‌کند.
- هر دو نوع ورود محلی دارای Progress و Cancel هستند و Scheduler عملیات ایتا را اشغال نمی‌کنند.
- تکراری‌ها هم با شمارهٔ نرمال‌شده و هم با شناسهٔ ایتا تشخیص داده می‌شوند. تعارض میان دو هویت مستقل با خطا متوقف می‌شود.
- دسته‌های انتخاب‌شده به دسته‌های قبلی افزوده می‌شوند و وضعیت‌های Opt-out و غیرقابل‌ارسال تعیین‌شده توسط اپراتور بازنویسی نمی‌شوند.
- خروجی «مخاطبان هدف» می‌تواند فرم ارسال به شماره‌ها را پُر کند؛ این انتقال هیچ ارسال خودکاری انجام نمی‌دهد و Resolve، Preview و تأیید صریح Core همچنان الزامی است.
- Schema دفترچه همان نسخهٔ ۱ باقی مانده است؛ GMI4 به Migration جدید نیاز ندارد.


## UI 1 repair

UI 1 is built on the accepted Runtime 3.1 baseline. WordPress and manual-dialog tabs are real visible buttons with one active-state contract, the Composer title and tabs share one intrinsic sticky wrapper without a fixed `66px` offset, and select, checkbox, radio and keyboard-focus states are complete. The WordPress settings form now uses the same warm high-contrast palette as the rest of the application. The unsupported Excel label is replaced by the accurate `CSV or TXT` label.

Normal installation continues to use the prebuilt lightweight UI. When the two separately licensed IRANSans files exist in `ui/fonts`, `install_app.bat` copies them into `ui/dist/fonts` without Node.js and records the result in `runtime/font-status.json`; otherwise Tahoma and Segoe UI remain active.

UI 1 intentionally left message virtualization unchanged. UI 2 below is the isolated Scroll Repair stage built on that frozen baseline.

## UI 1.1 field hotfix

UI 1.1 keeps the accepted UI 1 visuals and fixes the issues found in the first real-account test. WordPress composition and message-usage Core work now runs on the single Eitaa scheduler thread, preventing thread-affine SQLite `ProgrammingError` failures. Dialog avatars are read from the local cache only and no longer trigger long automatic remote downloads. Completed dialog synchronization no longer labels skipped deleted/incomplete peers as an incomplete sync. WordPress categories preserve `parent_id` and render as an indented parent/child tree. When no configured site has credentials, WordPress taxonomy calls and publishing controls stay quiet and disabled until site settings are completed.



## UI 2 Scroll Repair

UI 2 changes only the message-list virtualization and scroll path. Message rows now use stable peer/message keys, content-aware initial estimates and measured heights. Prepending older messages restores the same visible message and pixel offset rather than applying a total `scrollHeight` delta. Incoming messages follow the viewport only when the user is near the bottom; an outgoing appended message may explicitly follow. One top-pagination request can be active per threshold crossing, and each dialog keeps an independent loaded-message window and scroll anchor. Image cards reserve a fixed 4:3 area before the thumbnail arrives, while date and loading indicators are overlays outside document flow.

The Runtime, Installer, Core wheel, SQLite schema 8, scheduler, WordPress composition/taxonomy behavior, cached-only avatar policy and dialog-sync classification remain unchanged from UI 1.1.

## UI 3, UI 3.1 and UI 3.2

UI 3 connects dialog-member operations, phone-list sending, invitations, job progress and failure reporting. UI 3.1 refines the WordPress and bulk-operation lifecycle: a successful create or update clears the WordPress form and selected Eitaa messages, existing multi-message WordPress posts may safely receive additional selected Eitaa messages, and recorded sources cannot be removed or replaced. UI 3.2 makes the Composition store an authoritative fallback for message usage, marks every committed source as used immediately after a successful WordPress write, prevents a newly appended message from being reused in another Composition, unifies the duplicate bulk-operation entry points, and places recipient/message fieldsets side by side on desktop while stacking them on small screens.

## Runtime 3.1 dialog synchronization repair

Runtime 3.1 keeps the accepted Runtime 3 ownership and installer repairs, and fixes the first real-account regression found after login. Eitaa dialog discovery no longer depends on configured WordPress credentials, an empty fresh catalog starts its complete background synchronization automatically, and unusable deleted peers cannot abort the remaining account. Visual styling, fonts, message scrolling, Core package and SQLite schema remain unchanged.

## بهینه‌سازی‌های نهایی MVP 6.1

- پیام‌های موجود ابتدا و فوراً از Core SQLite خوانده می‌شوند؛ فراخوانی سرور فقط در نبود داده، وجود پیام جدید یا پایان TTL انجام می‌شود.
- تغییر سایت WordPress، بازکردن Composer و پایان انتشار دیگر پیام‌های ایتا را از ابتدا Sync نمی‌کند.
- پس از انتشار، همان نمای فعلی (حتی فهرست بازشده یا بازه تاریخی) فقط از SQLite تازه می‌شود و به صفحه اول برنمی‌گردد.
- پیام‌های قدیمی ابتدا از SQLite صفحه‌بندی می‌شوند و فقط هنگام پایان Cache از سرور دریافت می‌شوند.
- پیش‌نمایش تصاویر به‌صورت Thumbnail دریافت و روی دیسک Cache می‌شود؛ تصویر اصلی فقط با کلیک کاربر یا هنگام انتشار WordPress دریافت می‌شود.
- فایل اصلی رسانه برای انتشار WordPress یک بار در Cache کامل ذخیره و در انتشارهای بعدی بازاستفاده می‌شود.
- نمایش رسانه از Endpoint محلی Stream می‌شود و دیگر فایل بزرگ به Base64 داخل JSON تبدیل نمی‌شود.
- Core در طول اجرای API به‌صورت کنترل‌شده Pool می‌شود و هزینه باز و بسته‌شدن مکرر دیتابیس و Session کاهش یافته است.
- DaisyUI سنگین از Build حذف و با Componentهای CSS محلی جایگزین شده است.
- لاگ Runtime چرخشی، زمان پاسخ API، خطاهای امن و Hit/Miss رسانه را ثبت می‌کند؛ Diagnosticهای بسیار قدیمی نیز محافظه‌کارانه پاک‌سازی می‌شوند.
- Builder اداره شامل `tzdata` و اصلاح دائمی خطای حذف بازگشتی Packageهای `diagnostics` است.


### 1. موتور درخواست و Read State

- همه RPCهای ایتا همچنان از یک Scheduler و یک Worker عبور می‌کنند.
- پیام‌های گفت‌وگوی فعال و درخواست تاریخ، اولویت بالاتر از همگام‌سازی پس‌زمینه دارند.
- همگام‌سازی Dialogها صفحه‌به‌صفحه است و میان صفحات فرصت اجرای درخواست مهم‌تر ایجاد می‌شود.
- Read Receipt پایین‌ترین اولویت را دارد، تأخیر و Coalesce می‌شود و فقط پس از پذیرش سرور Core DB و UI را تغییر می‌دهد.
- هنگام تعویض سریع گفت‌وگو، نتیجه درخواست‌های قدیمی در UI بی‌اثر می‌شود.
- نمایش داده محلی قبل از درخواست Remote انجام می‌شود.

### 2. DatePicker شمسی

- ورودی متنی تاریخ حذف شده و تنها دکمه تقویم در Header پیام‌ها باقی مانده است.
- DatePicker شمسی امکان انتخاب «همان روز» یا «از این تاریخ به بعد» دارد.
- پاک‌کردن فیلتر، کاربر را به جریان آخرین پیام‌ها برمی‌گرداند.
- جداکننده روز و برچسب شناور تاریخ شمسی حفظ شده‌اند.
- نمای تاریخ و جست‌وجو هیچ Read Receipt تولید نمی‌کنند.

### 3. عملیات اعضا و شماره‌ها

از پنجره عملیات دسته‌ای می‌توان:

- به اعضای گفت‌وگوی فعال متن، تصویر یا فایل ارسال کرد؛
- شماره‌ها را از TXT/CSV یا متن وارد، Resolve و به موارد قابل‌شناسایی پیام ارسال کرد؛
- شماره‌های Resolve‌شده را با Preview و تأیید صریح به گروه یا کانال دعوت کرد؛
- سقف تست و فاصله میان گیرندگان را تنظیم کرد؛
- Jobهای پایدار Core را اجرا و وضعیت آن‌ها را مشاهده کرد.

Core 7.4.4 از قبل API عمومی لازم برای این مسیرها را داشت؛ بنابراین کد پروتکل، SQL مستقیم یا Core جدیدی به Bridge افزوده نشده است.

### 4. مدیریت سایت‌های WordPress

Settings اکنون امکان افزودن، ویرایش، حذف، تعیین سایت پیش‌فرض و Test اتصال را دارد. URL، وضعیت نوشته، دسته پیش‌فرض، TLS، Timeout، Retry، نام کاربری و Application Password قابل تنظیم‌اند.

- Secretها فقط در `.env` نگهداری می‌شوند و API مقدار ذخیره‌شده را برنمی‌گرداند.
- پیش از هر تغییر، Backup خودکار در `backups/settings` ساخته می‌شود.
- حذف سایت نیازمند تأیید صریح است.
- HTTP فقط با فعال‌سازی صریح و فقط برای localhost، IP خصوصی شبکه یا دامنه توسعه محلی پذیرفته می‌شود؛ HTTP عمومی همچنان مسدود است.
- دکمه «ذخیره و آزمون اتصال» ابتدا فرم را ذخیره و سپس همان سایت را آزمایش می‌کند.
- فرم اتصال جدید کنتراست بالا، ورودی سفید، Border تیره و Focus طلایی دارد.

### 5. آماده‌سازی استفاده اداری

- Launcher واحد: `EitaaBridge.bat`
- اجرای پیش‌فرض سبک با Python و Microsoft Edge در حالت App؛ بدون بارگذاری Electron و بدون نیاز روزمره به Node.js
- اجرای Electron فقط به‌صورت اختیاری از `EitaaBridgeElectron.bat`
- اگر سرویس محلی از قبل فعال باشد، Launcher همان سرویس را بازاستفاده می‌کند و نمونه Backend دیگری ایجاد نمی‌کند
- Single Instance در نسخه Electron
- نصب آفلاین کتابخانه‌های Python از Wheelهای داخل بسته
- Backup دارای Manifest و SHA-256: `backup_now.bat`
- Restore امن با Backup اجباری پیش از بازیابی: `restore_backup.bat`
- Diagnostics امن و Redacted: `create_diagnostics.bat`
- پوشه لاگ استاندارد: `runtime/logs` شامل `application.jsonl` چرخشی و `server-console.log` برای خطاهای راه‌اندازی
- میانبر Desktop و Start Menu
- Migration اختصاصی از MVP 5.6 با Backup پیش از کپی
- تعریف کامل Windows RC/Installer مبتنی بر Electron Packager و Inno Setup

## ارتقا از UI MVP 6.0

بسته نهایی را در یک پوشه جدید استخراج کنید و مسیر پوشه قدیمی MVP 6.0 را به Migration بدهید:

```bat
upgrade_from_ui_mvp6_0.bat "FULL_PATH_TO_OLD_eitaa_bridge_v0_7_ui_mvp6_0"
install_app.bat
run_doctor.bat
EitaaBridge.bat
```

این مسیر Session، SQLite، پیام‌ها، رسانه و Cache، تنظیمات و Compositionها را منتقل می‌کند. Diagnosticها و Logهای تاریخیِ حجیم عمداً در پوشه قدیمی و Backup آن باقی می‌مانند تا سیستم اداره کند نشود.

## ارتقا از UI MVP 5.6

تمام فرایندهای قدیمی Bridge/API را ببندید، بسته MVP 6.1 را در پوشه جدید استخراج و اجرا کنید:

```bat
upgrade_from_ui_mvp5_6.bat "FULL_PATH_TO_eitaa_bridge_v0_7_ui_mvp5_6"
install_app.bat
run_doctor.bat
EitaaBridge.bat
```

Migration، Session، دیتابیس، رسانه، Compositionها، تنظیمات، UI metadata و فونت‌ها را منتقل می‌کند؛ `.venv`، `node_modules`، Wheelهای قدیمی و Build قبلی منتقل نمی‌شوند.

## نصب تازه

```bat
install_app.bat
run_doctor.bat
EitaaBridge.bat
```

این بسته Source کامل رابط Material UI را دارد، اما `ui\dist` موجود فقط برای آزمون‌های رگرسیون تاریخی نگه‌داری شده و Installer آن را به‌عنوان Build جدید نمی‌پذیرد. در نخستین نصب، Node.js 24 LTS و دسترسی به Registry عمومی npm لازم است تا `setup_ui.bat` وابستگی‌های قفل‌شده پروژه را داخل پوشه `ui` نصب و Build واقعی RTL/Material UI را ایجاد کند. پس از Build موفق، اجرای روزمره برنامه به اینترنت npm نیاز ندارد.

فونت تجاری IRANSans عمداً داخل بسته توزیع نشده است. اگر فایل‌های مجاز `IRANSansWeb-Regular.woff2` و `IRANSansWeb-Bold.woff2` در `ui\fonts` قرار داده شوند، اجرای `setup_ui.bat` آن‌ها را داخل Build قرار می‌دهد؛ در غیر این صورت رابط از Tahoma و Segoe UI ویندوز استفاده می‌کند.

## ساخت RC و Installer

روی Windows Build Workstation اجرا کنید:

```bat
build_windows_installer.bat
```

خروجی هدف:

```text
release\installer\EitaaBridge-0.8.0-rc1-Setup-x64.exe
```

فایل Installer نهایی باید پس از ساخت روی Windows، Code-sign و روی Windows 10/11 پاک آزمایش شود. محیط ممیزی فعلی Source، Wheel، آزمون‌های Backend و مدل‌های UI را اعتبارسنجی کرد؛ Build کامل MUI و Electron/Installer باید در محیط Windows دارای وابستگی‌های npm اجرا شود.

## Acceptance اجباری روی حساب واقعی

1. هنگام Refresh کامل Dialogها، پیام‌های گفت‌وگوی فعال باید بین صفحات سریع بارگذاری شوند.
2. بازکردن گفت‌وگو به‌تنهایی نباید Unread را صفر کند؛ پیمایش واقعی و مکث باید Read Receipt را فعال کند.
3. DatePicker شمسی باید همان بازه موردنظر را نشان دهد و Unread را تغییر ندهد.
4. ارسال دسته‌ای ابتدا با `test_limit` کوچک و یک پیام غیرحساس آزمایش شود؛ Pause/Resume/Cancel و گزارش نهایی بررسی شوند.
5. مسیر شماره‌ها با یک فهرست آزمایشی کوچک Resolve شود و موارد `not_found` یا محدودشده به‌درستی گزارش شوند.
6. دعوت اعضا فقط روی گروه آزمایشی و با دسترسی مدیریتی بررسی و Rollback آزمایش شود.
7. هر سایت WordPress با Test اتصال، Draft، Update نوشته قبلی و Upload رسانه پذیرش شود.
8. Backup، Restore و Diagnostics روی یک کپی آزمایشی بررسی شوند.
9. اجرای هم‌زمان دوم برنامه باید فقط پنجره موجود را Focus کند.
10. Installer RC باید روی Windows پاک، ارتقا از MVP 5.6 و Uninstall بدون حذف داده کاربر آزمایش شود.

## مستندات

- `docs/project-memory/README.md` — حافظهٔ مهندسی، یافته‌ها، اعتبارسنجی‌ها و نقشه‌راه؛ مرجع اول پیش از بررسی دوباره
- `docs/OFFICE_DEPLOYMENT.md`
- `docs/BACKUP_RESTORE.md`
- `docs/BULK_OPERATIONS.md`
- `docs/WORDPRESS_SITE_SETTINGS.md`
- `docs/INSTALLER.md`
- `docs/PRIORITY_SCHEDULER.md`
- `docs/CORE_7_4_5_GMI1_CONTRACT.md`
- `docs/GMI1_ARCHITECTURE_AND_SCOPE.md`
- `docs/LOCAL_CONTENT_INDEX_LAB_PLAN.md`

## مرز امنیتی

فایل‌های زیر را هرگز ارسال نکنید:

```text
.eitaa_session.json
.env
bridge.json
data\eitaa_messages.sqlite3
```

برای پشتیبانی فقط از ZIP ساخته‌شده توسط `create_diagnostics.bat` استفاده کنید.

## UI 3.3 additions

- WordPress publish/update success is accepted only after all source messages are read back against the same post ID.
- Confirmed source messages remain visibly used and cannot be selected again.
- Dialogs open from the unread boundary when available.
- Approximate per-dialog reading positions are saved locally at low priority, at most once per 2.5 seconds, with a 120-dialog cap.
- The frozen UI 3.2 scroll implementation and its production bundles remain byte-identical.

## GMI 1 — Grouped Media Gallery

- Core decodes the server-provided `grouped_id` from layer-134 messages and persists it in SQLite schema 9.
- The schema-8 database is backed up before migration; the schema change is transactional and leaves message content hashes unchanged.
- Message-list pages are completed with locally available members of any album crossing a page boundary.
- The UI shows all media sharing one `grouped_id` in one gallery card with one combined caption.
- Selecting or clearing a gallery operates on every locally available album member as one unit.
- Text search returns the complete album whenever any member caption or message ID matches.
- No heuristic based only on neighboring messages is used.

## GMI 2 — Local Index, Content Filters and Suggested Galleries

- Server galleries still use the authoritative `grouped_id` contract.
- Separately uploaded photos may additionally appear as a visibly labelled
  `گالری پیشنهادی` only when they are adjacent image messages with consecutive
  IDs, the same reliable sender, the same reply context and at most 120 seconds
  between adjacent uploads.
- A collapsible content-filter panel can hide messages already used in
  WordPress and filter the loaded conversation by a locally suggested category.
- Explicit indexing builds a small dependency-free Persian TF-IDF centroid
  model from confirmed local WordPress composition history and current
  category names. The filter panel also lets the user save optional local
  guide words/phrases for each category. The model can suggest up to three
  categories and evidence tokens, but never changes a WordPress post or
  category automatically.
- Indexing runs on a dedicated local worker and reads only the local public Core
  message store. It does not occupy the Eitaa operation scheduler and never
  sends message text to an AI or other online service.
- The separate `data/content_index.sqlite3` stores hashes, suggestions and
  feedback—not raw message text. Schema 1 is backed up before the transactional
  schema-2 migration.
- New run output is staged. Completion or controlled cancellation promotes the
  result atomically; an unexpected failure discards staging and preserves the
  previous visible result set.
- The 20,000-message normal cap, 50,000 hard cap, progress display and safe
  cancellation keep the UI responsive. A zero-progress cancellation preserves
  the previous results.
- Accuracy remains limited by the quantity and quality of the user's confirmed
  examples. Lab scores are synthetic evidence of algorithm behavior, not a
  promise of real-data accuracy.

## GMI 4.2 — RTL، مخاطبان ایتا و ارسال مستقیم

رابط بر پایه Material UI و Emotion RTL باقی مانده است. پوسته برنامه، پنجره‌های مدیریت مخاطبان، فرم‌های ایندکس، ورود و بازیابی نشست، و کادر ارسال از مؤلفه‌های استاندارد MUI و Breakpointهای `xs/sm/md/lg/xl` استفاده می‌کنند. فهرست مجازی پیام‌ها عمداً سبک و اختصاصی باقی مانده است تا رندر هزاران پیام به درخت سنگین MUI تبدیل نشود.

منوی مشکی سمت راست اکنون ورودی مستقیم «مخاطبان ایتا» دارد. پنجره مدیریت مخاطبان پنج تب روشن دارد: مخاطبان واقعی سرور ایتا، دفترچه دائمی محلی، دسته‌ها، ورود و انتقال، و مخاطبان هدف. افزودن انفرادی یا Excel/CSV/TXT می‌تواند با انتخاب کاربر هم‌زمان در دفترچه واقعی ایتا ذخیره شود. شماره تکراری رکورد جدید نمی‌سازد و دسته‌ها Merge می‌شوند. حذف از ایتا، نسخه محلی را خودکار حذف نمی‌کند.

فیلتر مخاطبان هدف در Query پایگاه داده اعمال می‌شود. اگر هیچ دسته‌ای انتخاب نشده باشد هیچ مخاطبی نمایش داده نمی‌شود؛ با برداشتن تیک یک دسته نیز مخاطبان خارج از دسته‌های باقی‌مانده از نتیجه حذف می‌شوند. Preview یکتا، Opt-out و سقف ایمنی پیش از انتقال به فرم ارسال حفظ شده است.

کادر ارسال مستقیم زیر محتوای گفت‌وگو، متن، عکس و فایل را از مسیر Scheduler موجود ارسال می‌کند. فایل انتخابی ابتدا به پوشه امن `runtime\uploads` کپی و پس از عملیات پاک می‌شود. پیش‌نویس هر گفت‌وگو محلی است و دکمه غیرفعال تمپلیت، نقطه اتصال نسخه آینده محسوب می‌شود.

مخاطبان، گفتگوها و رسانه‌ها از Cache، صفحه‌بندی، Lazy loading و جلوگیری از درخواست هم‌زمان تکراری استفاده می‌کنند. عکس اشخاص فقط وقتی قابل بازیابی است که Core برای آن شخص مرجع عکس معتبر در کاتالوگ گفتگو داشته باشد؛ در غیر این صورت حروف اول نام نمایش داده می‌شود.

برای جلوگیری از اجرای تصادفی خروجی قدیمی، `install_app.bat` فقط Build دارای نشانگر `ui\dist\.material-ui-v1` را می‌پذیرد. نخستین Build به Node.js 24 LTS و دسترسی به `https://registry.npmjs.org` نیاز دارد.

# گزارش پنل اختیاری WordPress، دروازهٔ نقش گفتگو و اولویت آواتار

تاریخ: 2026-08-27
Run: `UX-WP-AVATAR-R02`
وضعیت: `IMPLEMENTED / FULL_AUTOMATED_ACCEPTANCE / GIT_PUBLICATION_PENDING`

## نتیجه

پنل WordPress اکنون یک قابلیت opt-in در تنظیمات است و برای هر کاربر/حساب به‌صورت محلی نگه‌داری می‌شود. مقدار پیش‌فرض `false` است. وقتی پنل پنهان است، UI فقط «عملیات گفتگو» را نشان می‌دهد و هیچ درخواست category/tag اجرا نمی‌کند. حتی با روشن‌بودن پنل، بارگیری taxonomy فقط برای سایت فعال دارای `credentials_configured=true` مجاز است.

عملیات گفتگو فقط برای گفت‌وگوی فعالِ گروه یا کانال فعال می‌شود که نقش حساب انتخابی به‌طور قابل‌اعتماد `owner` یا `admin` باشد. نقش از metadata معتبر Eitaa Discovery گرفته، در catalog حساب‌محور ذخیره و در UI به‌شکل fail-closed مصرف می‌شود. مقدار نامعلوم، عضو عادی، گفت‌وگوی شخصی و گفت‌وگوی غیرفعال اجازه نمی‌گیرند. در Channel/Supergroup، بیت‌های creator/admin قابل تشخیص‌اند؛ در basic group قدیمی، Core جاری فقط creator را به‌طور قابل‌اعتماد نشان می‌دهد، بنابراین مدیر غیرمالک تا رسیدن شاهد معتبر عمداً `unknown` و بسته می‌ماند.

بارگیری آواتار گروه/کانال نیز اولویت‌دار شد. پیام‌های گفت‌وگوی در حال مشاهده همچنان بالاترین اولویت Provider را دارند؛ آواتار همان گفت‌وگو بعد از آن و آواتارهای فهرست در زمان خلوت اجرا می‌شوند. صف مرورگر cache probe را با concurrency هشت و انتظارهای HTTP را با concurrency سه مستقل پیش می‌برد، اما scheduler Backend تمام عملیات Eitaa را روی نشست مشترک سریال نگه می‌دارد؛ در نتیجه parallelism رابط باعث overlap ناامن Provider نمی‌شود. درخواست موجود در صف هنگام بازشدن گفتگو promote می‌شود.

فایل cache آواتار پیش از استفاده از نظر وجود، اندازهٔ محدود و magic واقعی JPEG/PNG/GIF/WebP سنجیده می‌شود. فایل صفر/خراب miss محسوب و با overwrite کنترل‌شده دوباره دریافت می‌شود؛ نتیجهٔ خراب در catalog ثبت نمی‌شود و UI به initials امن برمی‌گردد.

## قرارداد پیاده‌سازی

- تنظیم `showWordPressPanel` با default خاموش، در storage scope جاری کاربر/حساب ذخیره می‌شود.
- `loadTerms` بدون نمایش پنل یا بدون credential سایت فعال، پیش از HTTP بازمی‌گردد؛ فیلتر WordPress نیز در همین حالت پنهان و بی‌اثر است.
- نقش‌های dialog فقط پس از parse موفق metadata و تطبیق peer key ثبت می‌شوند؛ raw payload، شناسهٔ حساب و متن خصوصی نگه‌داری نمی‌شود.
- `can_manage_community` در زمان خواندن catalog از `account_role` دوباره محاسبه می‌شود و boolean ذخیره‌شدهٔ client یا رکورد قدیمی مورد اعتماد نیست.
- ترتیب Eitaa برابر `ACTIVE_MESSAGES=10`، `ACTIVE_AVATAR=40`، `AVATAR=50`، `BACKGROUND=70` و `AVATAR_BACKGROUND=80` است؛ عدد کمتر زودتر اجرا می‌شود.
- آواتار background در UI حداقل 350ms فرصت idle می‌گیرد؛ ورود به viewport آن را visible و بازشدن گفتگو آن را active/promoted می‌کند.
- endpointهای mutation موجود تغییر مجوز گسترده نداده‌اند؛ این سناریو دروازهٔ نمایش/فعال‌سازی پنل را سخت‌گیرانه می‌کند و Provider همچنان مجوز واقعی عملیات را enforce می‌کند.

## شاهد RED و GREEN

- RED نقش: `tests/test_dialog_permissions.py` به‌علت نبود module شکست خورد.
- RED صف: Phase 9 workspace به‌علت نبود `queue.promote` شکست خورد.
- RED تنظیمات: قرارداد UI به‌علت نبود `showWordPressPanel` شکست خورد.
- GREEN هدفمند Backend/role/avatar=`56 passed` و سناریوی مستقیم role/catalog/API=`7 passed`.
- full Backend دقیقاً 664 تست بود و برای جلوگیری از timeout ابزار در شش partition کامل اجرا شد: `207 + 97 + 105 + 61 + 42 + 152 = 664`؛ failure/error/skip صفر.
- تمام runnerهای UI سبز بودند: grouped-media=`29/29`، scroll=`10/10`، Phase 9 workspace=`19/19`، Phase 9 acceptance=`13/13`، Phase 10=`7/7`، Observability=`PASS`، Phase 11 onboarding=`7/7`، Phase 11-B2=`6/6` و mobile/auth/live contracts=`PASS`.
- TypeScript=`PASS` و Vite build=`PASS` با 1016 module؛ warning تاریخی chunk بزرگ غیرمسدودکننده باقی است.
- wheel worktree دوبار بایت‌یکسان و برابر `f2c3872d4985c26e77877262991739cd65a7ebcfd35c9b642612ee158cea5be9` بود. پس از جداسازی و نرمال‌سازی LF توسط Git، wheel نهایی candidate دوباره ساخته شد و SHA-256 آن `23cd95cfbb9ac47e9ca057406e2008eba16854d03adfa159e9ce628fdf534b51` است؛ این تفاوت فقط artifact byte-level است. `dist/` طبق policy Git ignore است و wheel فقط artifact بستهٔ release است، نه فایل commit.
- بستهٔ نهایی candidate با 283 فایل، content-set=`702bd412fca521092c5927e2cec4257ea5f23edf62525df4debd52a28a8c155d` و دو archive بایت‌یکسان SHA-256=`307d00b82fb1ff0ec30d5c05b2c55a18b23726901b35e2301ce5c0cda520cc00` تولید شد؛ verifier داخلی privacy/path/hash/manifest را پذیرفت و work ایندکس در آن نیست.
- نصب تازهٔ نخست worktree به‌دلیل جاافتادن `vendor/runtime` از `find-links` شکست خورد. نخستین archive clone نیز چون wheelهای runtime طبق policy در Git ignore هستند فقط 277 فایل داشت و dependency resolve نشد. سپس wheelhouse canonical صرفاً در staging بسته قرار گرفت؛ archive 283فایلی نهایی با سه `find-links` و `--no-index` نصب شد و runtime checker، `pip check` و import ایزولهٔ module تازه همگی PASS شدند. هیچ‌یک از wheelهای ignored وارد commit نمی‌شوند.
- خود candidate نیز با basetemp صریح `101/101` تست مرتبط/بسته‌بندی، Phase 9=`19/19` و grouped-media=`29/29` را گذراند. تلاش‌های قبلی فقط به Temp غیرقابل‌دسترسی میزبان و cwd فاقد npm/node_modules خوردند و بدون تغییر محصول تکرار شدند.

## حریم خصوصی و اثر عملیاتی

هیچ حساب واقعی، OTP، Session، پیام، WordPress، Provider mutation یا سرویس زنده باز یا فراخوانی نشد. فایل‌های `bridge.json`، `.env`، `data/`، `runtime/`، `diagnostics/` و `backups/` دست‌نخورده ماندند. آزمون‌ها فقط fixture مصنوعی، wheel، archive و venv موقت ساختند. raw metadata، peer/account id، عنوان گفتگو، متن پیام، شماره و credential در log یا گزارش ثبت نشده است.

## فایل‌های اصلی

- `src/eitaa_bridge/infrastructure/eitaa/dialog_permissions.py`
- `src/eitaa_bridge/infrastructure/dialog_catalog.py`
- `src/eitaa_bridge/application/scheduler.py`
- `src/eitaa_bridge/application/api.py`
- `ui/src/lib/avatarQueue.mjs`
- `ui/src/lib/avatarLoader.ts`
- `ui/src/App.tsx`
- `ui/src/SettingsPage.tsx`
- `ui/src/WorkspaceNavigation.tsx`
- `ui/src/ChatHeader.tsx`

## دروازه‌های باقی‌مانده

رکوردهای catalog موجود برای دریافت نقش تازه به یک live-sync معمول بعدی نیاز دارند. در basic group قدیمی، مدیر غیرمالک تا زمانی که Core نقش self را به‌طور معتبر ارائه نکند عمداً بسته است. گفت‌وگوی فاقد photo reference معتبر نیز نمی‌تواند از Provider عکس بسازد و به initials برمی‌گردد. پذیرش فعلی خودکار و آفلاین است؛ login، مشاهدهٔ واقعی، ارسال، مدیریت عضو و WordPress publish به‌دلیل نیاز به تأیید لحظه‌ای اجرا نشدند. تصمیم canonical در ADR-47 و شاهدها در V-181/V-182 ثبت شده‌اند.

# گزارش G-01 — سلامت اسناد و حاکمیت لاگ

تاریخ: 2026-08-25  
Run: `STAB-G01-R01`  
وضعیت: `COMPLETE / VERIFIED`  
دامنه: فقط source ابزار کنترل، تست، حافظهٔ مهندسی و اسناد؛ بدون config/data/session/runtime و بدون عملیات Provider/Live.

## هدف

حافظهٔ پروژه باید برای Codex و AntiGravity یک مرجع ماشینی و انسانی قابل‌اعتماد باشد: UTF-8 سالم، بدون نویسهٔ جایگزین/کنترلی، بدون شناسهٔ رسمی تکراری، بدون سطر فرمان شکسته و بدون استفاده از ادعاهای منقضی به‌عنوان وضعیت جاری.

## علت ریشه‌ای

- چند append تاریخی با encoding یا escaping ناسازگار وارد `FINDINGS_REGISTER.md`، `VALIDATION_LEDGER.md` و `BALE_PROVIDER_DISCOVERY.md` شده بود.
- Ledger رکوردهای تاریخی را با شناسه‌های رسمی موجود `V-015` و `V-078` دوباره تعریف کرده بود.
- چند جدول Markdown فرمان‌های npm را روی چند سطر شکسته نگه داشته بود.
- Baseline و گزارش finalization هنوز نتیجهٔ تاریخی `590/590 / PRODUCTION_READY` را مانند شاهد snapshot جاری بیان می‌کردند، در حالی که V-103 Trigger ابطال را ثبت کرده بود.
- کنترل خودکاری که این drift را در full suite متوقف کند وجود نداشت.

## RED و شکست‌های قابل‌ردیابی

1. پیش از وجود implementation، `tests/test_project_memory_integrity.py` با `ModuleNotFoundError: scripts.check_project_memory_integrity` در collection شکست خورد.
2. checker اولیه روی repository واقعی `143` نشانه گزارش کرد: replacement=`2`، question-run=`129`، control=`4`، duplicate validation ID=`2` و malformed command row=`6`. این عدد شمار نشانه‌هاست، نه ۱۴۳ defect مستقل؛ بیشتر question-runها از چند سطر واحدِ شدیداً آسیب‌دیده بودند.
3. دو اجرای نخست unit test پس از ساخت ابزار به‌علت Permission Temp ویندوز و سپس نبود parent مربوط به `--basetemp` خطای محیطی دادند. با ساخت `.test-tmp` داخل workspace و basetemp یکتا، همان تست‌ها سبز شدند؛ هیچ تغییر محصولی برای این خطای محیطی انجام نشد.
4. اجرای Git بدون `safe.directory` محدود به invocation، به‌علت تفاوت کاربر sandbox با مالک Windows رد شد. retry فقط‌خواندنی با `git -c safe.directory=<project-root>` انجام و `diff --check` سبز شد؛ config سراسری تغییر نکرد.

## اصلاح‌ها

- `scripts/check_project_memory_integrity.py` اضافه شد: decode سخت‌گیرانهٔ UTF-8، منع U+FFFD و C0 controlها، کشف question-run، سطر npm یتیم و تعریف تکراری F/V؛ خروجی متنی و JSON و exit code غیرصفر دارد.
- `tests/test_project_memory_integrity.py` چهار شاهد دارد: پذیرش سند سالم، کشف corruption/duplicate، تحمل invalid UTF-8 و کنترل repository واقعی. بنابراین full pytest نیز از این پس خرابی حافظه را می‌گیرد.
- F-035 و فصل ۱۰ Discovery فقط از قطعه‌های قابل‌بازیابی بازنویسی و صریحاً `RECOVERED_FROM_PARTIAL_EVIDENCE` شدند؛ متن لفظ‌به‌لفظ حدس زده نشد.
- control pathهای F-036/V-101 به لینک محلی واقعی `implementation_plan.md` تبدیل شدند.
- duplicateهای تاریخی V-015/V-078 به `LEGACY-...` تبدیل شدند؛ شناسه‌های canonical قبلی حفظ شدند.
- سه جدول اجرای UI به یک سطر معتبر با فرمان canonical `npm.cmd --prefix ui ...` تبدیل شدند.
- `CURRENT_SYSTEM_BASELINE.md`، `PROJECT_SPECIFICATION.md` و گزارش finalization با V-103/F-046 همسو شدند: قرارداد متأخر Bale rollback نشد، runtime شکسته جاری پذیرفته اعلام نشد و `590/590` فقط شاهد تاریخی ماند.
- checker در `AGENTS.md` و پروتکل مستندسازی به حداقل کنترل کیفیت افزوده شد.

## روش امن ترمیم فایل دارای control byte

`apply_patch` نتوانست hunk حاوی U+0008 را match کند. برای هر فایل آسیب‌دیده، محتوای دقیق UTF-8 خوانده شد، فقط محدودهٔ مشخص جایگزین شد، نسخهٔ بازسازی‌شده ابتدا با `apply_patch` در artifact موقت و قابل‌بازیابی ساخته شد، سپس original با `apply_patch` حذف/افزوده و artifact موقت نیز با `apply_patch` حذف شد. baseline رمزنگاری‌شدهٔ G-00 و pre-hashها پیش از این عملیات موجود بودند. هیچ shell writer یا دستکاری دادهٔ عملیاتی استفاده نشد.

## نتایج فعلی

- unit/contract ابزار و report-index generator: `5/5 PASS`.
- integration checker روی تمام Markdownهای root/docs: `issue_count=0`.
- `git diff --check`: PASS با safe-directory صرفاً همان invocation.
- `refresh_project_docs.py --check` و `--check --check-links`: هر دو exit code صفر.
- فهرست تولیدشونده اکنون بخش «گزارش‌های تثبیت» دارد و G-00/G-01 را لینک می‌کند؛ RED این شکاف پیش از اصلاح با `KeyError` ثبت شد.

## فایل‌های کلیدی و hash

- pre F-035 register: `0936b7a83db9fa651af203b99260486d78658662ba362a9680fa50a00d8daddd`
- post F-035 register (پیش از ثبت نهایی Run): `68711be9e22be434c7402d16f38f9d2fac4c9c32df8b6e355816d85400480967`
- pre Ledger: `bb96de2e82e0c3ef2f54854731fbd60e49a65a8ef2dff95b8a8796a198f2c1d9`
- post Ledger (پیش از V-109): `fba51b0c8d0bce120cebf977edfefa541465c18e7c22994ae22fa875810fab1a`
- pre Bale Discovery: `105885e250e309f7c19ecb07b6e951cbca7cdff9b7cd1cce2666510296d01f39`
- post Bale Discovery: `f3c59a941a757411690abfa045650b805ac5c4cdd3bad6b9839f4bf992eb9101`
- checker: `0ebbf7be58b654a9126e9ae1f1af50b7320f0fac3d303b24a40abd2c7e4236ac`
- checker tests: `dff0614e63b742c9759e02459dd6f37966ed69009017c62fb7eb881d8e451736`

## اثر بیرونی و حریم خصوصی

اثر بیرونی `none` است. هیچ Login/OTP/Session/Send/Capture/WordPress، network mutation، Git stage/commit/push یا تغییر config/data/runtime انجام نشد. هیچ شماره، Token، Cookie، OTP، متن خصوصی یا مسیر حساس به گزارش افزوده نشد.

## شرط بسته‌شدن و handoff

V-109 و Execution Log ثبت شدند، artifactهای تولیدشونده refresh و دروازه‌های نهایی سبز شدند. G-01 بسته و handoff روی G-02 قرار گرفت. G-02 فقط مهار آفلاین Bale موجود است و توسعهٔ قابلیت تازه نیست.

# قواعد مشترک اجرا، پذیرش و ادامهٔ کار

تاریخ: 2026-09-28

دامنه: تمام دستورهای این پوشه. این سند قرارداد اجرای مأموریت است؛ مجوز عملیات Live صادر نمی‌کند.

## شروع الزامی

1. ترتیب مطالعهٔ [AGENTS.md](../../../AGENTS.md) را اجرا کن؛ اسناد معتبر جاری و اصلاحات متأخر را بر گزارش تاریخی ترجیح بده.
2. این فایل، فایل مأموریت/فاز، [دفتر وضعیت](EXECUTION_STATUS.md)، گزارش نهایی پیش‌نیاز و آخرین handoff آن را بخوان. اگر گزارش هنوز ساخته نشده، تکمیل پیش‌نیاز را فرض نکن.
3. HEAD، branch، tracked diff، staged diff و untrackedها را فقط با metadata امن ثبت کن. وضعیت اولیهٔ تهیهٔ دستورها: branch اختصاصی F-091، HEAD=`c513cdf3`، tracked change صفر و untrackedهای موجود کاربر حفظ‌شده.
4. پرونده‌های source/test را از project map و `rg --files` پیدا کن. مسیرهای احتمالی این دستورها راهنمای بررسی‌اند؛ نام یا API ناموجود را موجود اعلام نکن.
5. عملیات فعلی این فایل‌ها از نوع توسعه است؛ هر endpoint تازه‌ای که ذکر شده «هدف قرارداد» است و تا source/test واقعی ساخته نشود، API موجود نیست.

## مرزهای اجرای فنی

- Eitaa و Bale Personal مسیرهای محصول‌اند. F-086/ADR-60 مجوز توسعهٔ بله را ثبت کرده‌اند؛ ممنوعیت تاریخی دائمی نساز. سقف capability، مالکیت، محافظت نشست و رفتار واقعی Provider حفظ شوند.
- Core عمومی به نام Provider شرط‌گذاری نکند؛ translation در adapter و registration صریح در composition root باشد. API/worker عمومی از DTO محدود استفاده کند.
- مسیر `service → credential fence → membership → account → capability → admission → orchestrator → adapter/worker` را حفظ کن. cache/replay پیش از مجوز برگشت داده نشود.
- secret، OTP، شمارهٔ کامل، access hash، متن خصوصی، raw exception و مسیر خصوصی وارد log/audit/report/test output نشوند. fixtureهای آزمون ساختگی باشند؛ چاپ payload در assertion شکست ممنوع است.
- به داده‌های عملیاتی، `bridge.json`، `.env` و نشست موجود دست نزن. نمونه و migration روی محیط مصنوعی مجازند. اعمال تنظیمات واقعی از UI توسط مالک یا در دامنهٔ تأیید صریح انجام شود.
- reset/checkout/clean، force-push، merge/push مستقیم main و bulk stage ممنوع‌اند. تغییرات فقط متعلق به سناریوی جاری stage شوند.
- مدل آنلاین chat-only است؛ نباید OTP تولید/اعتبارسنجی کند، حساب فرستنده انتخاب کند یا پیام‌رسانی را از طریق tool غیرمجاز اجرا کند.
- F-090/F-091 و V-225 را حفظ کن: claim تا پایان ذخیره، rollback زیر همان قفل، آزادی منتظران، replay کامل، تعارض متن، TTL و پرچم پاسخ. ضمانت چت درون فرایند و تا restart است.
- برای پیام‌رسان، unknown external effect=`uncertain`؛ retry/fallback خودکار مجاز نیست. پذیرش Provider معادل دیده‌شدن پیام توسط انسان نیست.

## تعریف اتمام هر فاز

هر فاز باید کد واقعی، UI/API قابل استفاده، آزمون مستقل مربوط به رفتار تازه و سند قرارداد هماهنگ داشته باشد. اگر acceptance ID باز است، وضعیت `COMPLETE` ننویس.

برای bugfix قبل از patch regression دارای علت درست RED ثبت کن. برای قابلیت تازه، آزمون قراردادی با fixture معتبر و رفتار هدف بنویس؛ RED ناشی از import/fixture خراب را شاهد نقص محصول اعلام نکن.

گزارش همان فاز در `docs/reports/features/` و handoff در `docs/handoffs/` ساخته شود؛ برای P8 پوشهٔ `docs/reports/validation/` مطابق فایل آن فاز است. نام گزارش مطابق فایل فاز و نام پیشنهادی handoff برای P1، `WEB_CLIENT_PHASE_01_HANDOFF.md` است. این نام‌ها فعلاً هدف ایجاد هستند. در هر گزارش بنویس:

- HEAD آغاز/پایان و فایل‌های تغییرکرده؛
- وضعیت تک‌تک acceptance IDها: PASS، FAIL، یا BLOCKED_WITH_REASON؛
- فرمان، exit code، تعداد تست و زمان شاهد؛ شکست و rerun هر دو محفوظ؛
- APIها و migrationهای واقعاً تحویل‌شده؛
- حد ضمانت، Live انجام‌شده/انجام‌نشده و دقیقاً چه چیزی برای ادامه لازم است؛
- اولین اقدام handoff و وضعیت پیش‌نیاز فاز بعد.

در [دفتر وضعیت](EXECUTION_STATUS.md) وضعیت و لینک گزارش ساخته‌شده را بنویس. نام گزارش ناموجود را با لینک شکسته ثبت نکن. Findings/Validation Ledger طبق پروتکل به‌روز شوند؛ ID تازه را از وضعیت واقعی استخراج کن، از این دستور کپی نکن.

## آزمون و اسناد

در پایان تغییر قرارداد مرکزی full Backend و کنترل‌های UI الزامی است. پس از افزودن module محصول، wheel parity را بررسی و در صورت drift از builder رسمی بازسازی کن؛ artifactهای قدیمی را بی‌دلیل حذف نکن.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix ui run check
npm.cmd --prefix ui run test:observability
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py
.\.venv\Scripts\python.exe scripts\check_project_memory_integrity.py
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
git diff --check
```

برای UI/build و بستهٔ نهایی، فرمان canonical در `ui/package.json` و rehearsal رسمی release را نیز اجرا کن. پس از تغییر Markdown، integrity دوباره اجرا شود. generator outputs را دستی ویرایش نکن.

آزمون Live هرگز داخل اجرای عادی pytest/CI فعال نشود. برای docs-only، کنترل integrity/generator/link/diff کافی است؛ full-suite قدیمی را شاهد رفتار پیاده‌نشده اعلام نکن.

## استمرار و موانع

- «بررسی کردم»، «پیشنهاد دادم»، scaffold، دکمهٔ بی‌عمل یا پاسخ Fake محصول نهایی نیست.
- تا وقتی کار مستقل و مجاز باقی است ادامه بده؛ برای انتخاب معمول نام فایل/ساختار داخلی از کاربر اجازهٔ تازه نگیر.
- اگر دامنه فقط یک فاز است، همان فاز را کامل کن و handoff بده؛ اگر مأموریت کل برنامه است، پس از gate به فاز بعد برو.
- نیازمند input واقعی: account/recipient مجاز، credential اتصال AI، محل مخزن وب یا دامنهٔ مشخص Live. ابتدا همهٔ کارهای مستقل و برنامهٔ دقیق آزمون را آماده کن؛ سپس فقط ورودی مفقود را درخواست کن.
- مجوزهای قبلی همان دامنه را حفظ کن. طبق AGENTS.md، ورود/ارسال واقعی، mutation مخاطب آزمایشی و تغییر استقرار باید در دامنهٔ تأیید مالک باشند. این دستور به‌تنهایی اجرای Live را مجاز نمی‌کند.
- با نبود ورودی Live، وضعیت درست `OFFLINE_COMPLETE / LIVE_PENDING_INPUT` است، نه `LIVE_ACCEPTED` یا «کل محصول تمام شد».
- انتشار Git فقط پس از اتمام دامنهٔ سناریو و gateهای متناسب طبق مجوز دائمی AGENTS.md؛ مانع انتشار ثبت شود. Git push پذیرش production نیست.

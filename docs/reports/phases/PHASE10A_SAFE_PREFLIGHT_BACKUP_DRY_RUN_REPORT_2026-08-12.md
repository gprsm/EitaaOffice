# گزارش Phase 10-A — پیش‌پرواز امن، Backup/Restore rehearsal و Contacts preview

تاریخ: ۲۰۲۶-۰۸-۱۲  
وضعیت: **بخش امن و غیرعملیاتی تکمیل و آزموده شد؛ بخش واقعی 10-A آغاز نشده است**

## مرز اجرا

در این نوبت هیچ‌یک از موارد زیر انجام نشد:

- توقف یا راه‌اندازی برنامهٔ واقعی؛
- ساخت backup دائمی از نصب واقعی؛
- restore یا rollback روی نصب واقعی؛
- مهاجرت Contacts یا Coordinator واقعی؛
- فعال‌سازی Feature Flag؛
- عملیات Provider/Eitaa/WordPress؛
- تغییر Port، Firewall، Service یا Router.

همهٔ عملیات نوشتنی فقط روی درخت موقت ساخته‌شده از کپی‌ها انجام شدند و در پایان پاک شدند.

## پیش‌پرواز واقعی فقط‌خواندنی

- Multi-session خاموش است.
- runtime فعال تشخیص داده نشد و `runtime/backend-state.json` وجود نداشت.
- در پورت‌های کاندید 8765، 8787، 8000، 8080، 3000 و 5173 listener وجود نداشت.
- مسیرهای legacy داخل نصب، Session container و Core SQLite خوانا هستند.
- فضای آزاد گزارش‌شده: ۲۳٬۸۳۲٬۵۷۶٬۰۰۰ بایت؛ نیاز پیش‌پرواز legacy: ۱۸۶٬۸۵۰٬۰۹۲ بایت.
- Coordinator از قبل وجود دارد؛ بنابراین preflight مهاجرت اولیه با کد `coordinator_already_exists` به‌درستی Fail-closed شد و apply اجرا نشد.
- خلاصهٔ فقط‌خواندنی Coordinator: schema 5، یک AppUser، یک PhoneAccount، یک Membership، یک MessengerAccount و دو Audit event؛ آخرین migration در وضعیت `activated` و Feature Flag همچنان خاموش است.
- Contacts واقعی: schema 1، `quick_check=ok`، دقیقاً ۵۷۴ مخاطب و ۳ دسته.
- چهار فایل حساسِ تحت نظر هنگام preflight (`bridge.json`، Session، Core DB و Contacts DB) تغییر نکردند.

## یافته و اصلاح مهم

فرمان قدیمی `migrate_legacy_account.py status` از `CoordinatorDatabase.safe_summary()` استفاده می‌کرد. آن متد پیش از خواندن، `initialize()` را اجرا و Coordinator را نوشتنی باز می‌کرد. در نخستین اجرای status، هش فیزیکی `coordinator.sqlite3` تغییر کرد؛ هیچ تغییر منطقی در تعداد رکوردها یا وضعیت migration مشاهده نشد، اما همین تغییر فیزیکی برای یک فرمان status قابل قبول نبود.

اصلاح انجام‌شده:

- متد `read_only_safe_summary()` اضافه شد؛
- اتصال با SQLite URI در `mode=ro&immutable=1` و `query_only=ON` انجام می‌شود؛
- وجود WAL/Journal غیرخالی باعث توقف Fail-closed می‌شود؛
- schema موجود فقط verify می‌شود و upgrade انجام نمی‌گیرد؛
- CLI status اکنون از مسیر فقط‌خواندنی استفاده می‌کند؛
- تست با Coordinator قدیمی schema 1 ثابت می‌کند status نه upgrade می‌کند و نه hash را تغییر می‌دهد؛
- اجرای مجدد روی Coordinator واقعی نیز hash ثابت را تأیید کرد.

هش فعلی Coordinator پس از اصلاح و اجرای کنترل ثابت ماند:

```text
C5A5306813EEA71FA53EF072AA43DB7A240EB41BBE0C512B67EE7B1916B4D5DA
```

هیچ بازگردانی حدسی روی این فایل انجام نشد تا دادهٔ واقعی دستکاری ثانویه نشود.

## سخت‌سازی Backup/Restore

- `backup_runtime.create_backup()` اکنون root صریح برای rehearsal روی کپی می‌پذیرد؛ رفتار پیش‌فرض نصب تغییر نکرده است.
- `restore_runtime.py --dry-run` همهٔ عضوها را بدون extraction یا write verify و فقط metadata امن را چاپ می‌کند.
- verifier اکنون Manifest، اندازه، SHA-256، path traversal، عضو تکراری و membership غیر canonical را رد می‌کند.
- restore به یک root صریح، ابتدا همهٔ اعضا را staging و verify می‌کند؛ جایگزینی‌ها اتمیک هستند و در خطای میانی، فایل‌های قبلی برمی‌گردند.
- تست fault-injection خرابی عمدی روی فایل دوم ایجاد کرد و بازگشت فایل اول به محتوای پیشین موفق بود.

## rehearsal جامع روی کپی

نتیجهٔ نهایی `scripts/phase10_copy_rehearsal.py`:

```text
ok=true
source_file_count=4114
backup_file_count=4114
backup_total_bytes=182295740
backup_verified=true
restore_hashes_match=true
source_unchanged=true
contact_schema_before=1
contact_schema_after_on_copy=2
contact_count_before=574
contact_count_after_on_copy=574
category_count_before=3
category_count_after_on_copy=3
contact_recovery_backup_verified=true
```

پاک‌سازی ۴٬۱۲۸ فایل موقت در Windows ابتدا با قفل/رفتار حذف Python مشکل داشت. کار سنگین به child process منتقل شد تا handleها پیش از cleanup آزاد شوند و fallback بومی فقط برای مسیر دقیق `eitaa-phase10-copy-*` زیر Temp، پس از اعتبارسنجی مسیر، اضافه شد. اجرای نهایی موفق بود و هیچ پوشهٔ rehearsal باقی نماند.

## آزمون‌ها

- هدفمند Backup/Coordinator/Contacts: **۳۲/۳۲ موفق**.
- Python کامل: **۴۷۹/۴۷۹ موفق**.
- TypeScript check: موفق.
- Production build: موفق، ۹۸۱ module؛ هشدار غیرمسدودکنندهٔ chunk بزرگ‌تر از ۵۰۰ kB باقی است.
- Phase 9 acceptance: **۱۰/۱۰**.
- Phase 9 workspace: **۱۰/۱۰**.
- Scroll model: **۱۰/۱۰**.
- Grouped-media model: **۱۶/۱۶**.
- `pip check`، compileall و `git diff --check`: موفق.

## وضعیت نهایی ایمنی

`bridge.json` واقعی همچنان ۹۳۴ بایت و بدون تغییر است:

```text
D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89
```

10-A واقعی تنها پس از توقف کنترل‌شدهٔ برنامه و تأیید جداگانه برای backup دائمی قابل ادامه است.

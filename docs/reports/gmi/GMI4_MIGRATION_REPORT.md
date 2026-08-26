# GMI4 — گزارش Migration

## نتیجه

Migration جدید لازم نیست.

- Core SQLite schema: `9`، بدون تغییر.
- Content Index schema: `2`، بدون تغییر.
- Contact schema: `1`، بدون تغییر.

Schema 1 از GMI3 ستون‌های `eitaa_user_id`، `access_hash`، `source`، `sendable`، `opt_out` و `last_resolved_at` و Unique Index شناسهٔ ایتا را از قبل دارد. GMI4 فقط قاعدهٔ تراکنشی تطبیق هویت و مسیرهای Import را تکمیل کرده است.

## Recovery

چون DDL یا تغییر `PRAGMA user_version` وجود ندارد، دادهٔ موجود هنگام ارتقا بازنویسی نمی‌شود. سازوکار Backup و Recovery ایجاد اولیهٔ Schema 1 دست‌نخورده باقی مانده است. پایگاه جدیدتر از نسخهٔ پشتیبانی‌شده همچنان Fail-closed می‌شود.

## سازگاری

- مخاطبان و دسته‌های GMI3 مستقیماً قابل استفاده‌اند.
- Unique شماره و Unique شناسهٔ ایتا حفظ شده است.
- اگر شماره و شناسهٔ ایتا به دو مخاطب متفاوت اشاره کنند، ادغام انجام نمی‌شود و رکورد خطا می‌گیرد.
- Import منبع، دسته‌ها را Merge می‌کند و Opt-out/وضعیت ارسال تعیین‌شده توسط اپراتور را حفظ می‌کند.

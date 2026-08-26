# گزارش Migration نسخه GMI3

## تغییر Schema

- Core message schema: بدون تغییر، نسخه ۹.
- Content-index schema: بدون تغییر، نسخه ۲.
- Contact directory schema: پایگاه مستقل جدید، نسخه ۱.

## قرارداد ایمنی

در اولین `initialize`، اگر فایل SQLite موجود و `user_version=0` باشد، پیش از هر DDL یک Backup با الگوی
`contacts.schema0.YYYYMMDDTHHMMSSZ.bak.sqlite3` ساخته می‌شود. ساخت جدول‌ها داخل `BEGIN IMMEDIATE` انجام می‌شود؛ شکست DDL باعث rollback می‌شود و Backup دست‌نخورده می‌ماند.

اگر `user_version` از نسخه پشتیبانی‌شده جدیدتر باشد، برنامه بدون تغییر پایگاه متوقف می‌شود. Migration هیچ Session، پیام، رسانه یا داده Core را لمس نمی‌کند.

## Recovery

1. برنامه را ببندید.
2. فایل ناموفق `data/contacts.sqlite3` را کنار بگذارید.
3. جدیدترین `contacts.schema0.*.bak.sqlite3` را با نام `contacts.sqlite3` بازگردانید.
4. Diagnostics را بررسی و سپس نسخه سازگار را اجرا کنید.

## آزمون‌ها

- Backup خودکار schema 0: موفق.
- ساخت schema 1 و foreign keys: موفق.
- رد schema جدیدتر بدون تغییر: موفق.
- حذف دسته بدون حذف مخاطب: موفق.
- بایگانی نرم مخاطب: موفق.

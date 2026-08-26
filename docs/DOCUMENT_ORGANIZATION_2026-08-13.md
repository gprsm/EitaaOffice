# گزارش سازمان‌دهی فایل‌ها و مستندات

تاریخ: 2026-08-13

## ۱. هدف

ریشهٔ پروژه شامل بیش از صد گزارش تاریخی در کنار launcher، config و دادهٔ واقعی بود. هدف این بازآرایی، ساختن مسیر روشن برای توسعهٔ دستی یا Agent دیگر، بدون حذف داده، clean کردن worktree یا شکستن launcherهای عمومی است.

## ۲. انتقال انجام‌شده

| مقصد | تعداد اولیه | محتوا |
|---|---:|---|
| `docs/reports/phases/` | 44 | گزارش‌های Phase 1 تا 10-D |
| `docs/reports/gmi/` | 28 | معماری، migration، validation و privacy مربوط به GMI |
| `docs/reports/features/` | 17 | UI، contact، session، theme و feature reportها |
| `docs/reports/architecture/` | 2 | گزارش‌های معماری گستردهٔ multi-session/LAN |
| `docs/reports/validation/` | 1 | validation عمومی Core |
| `docs/handoffs/` | 3 | continuation log و promptهای ادامه |
| `docs/checklists/` | 7 Markdown + 1 TXT | پذیرش Windows/UI و راهنمای نصب Material UI |
| `docs/specifications/` | 1 | معماری message template |
| `docs/reports/gmi/artifacts/` | 7 | diff و changed-files تاریخی GMI |

در مجموع 103 فایل Markdown و 8 artifact/یادداشت متنی از ریشه دسته‌بندی شد. فهرست دقیق و قابل‌کلیک همهٔ موارد در `REPORTS_INDEX.md` تولید می‌شود.

## ۳. مواردی که عمداً در ریشه ماندند

- `README.md`، `ARCHITECTURE_DECISIONS.md` و `AGENTS.md`: ورودی، تصمیم‌های canonical و دستور توسعه‌دهنده/Agent.
- launcherهای `*.bat`/`*.vbs`: ورودی مستقیم کاربر ویندوز و وابسته به موقعیت ریشه.
- `bridge*.json`، `.env*` و sessionها: config/runtime واقعی؛ انتقال آن‌ها پرریسک است.
- `pyproject.toml`، requirements، version، manifest و checksum: قرارداد build/release.
- `data/`, `runtime/`, `catalog/`, `backups/`, `diagnostics/`: دادهٔ عملیاتی.
- cacheهای `.pytest-*`: قابل حذف‌اند اما هیچ حذف یا clean در این کار مجاز/انجام نشده است.

## ۴. سازگاری و ارجاع‌ها

- ارجاع‌های متنی اسناد به مسیرهای جدید بازنویسی شدند.
- `scripts/build_gmi4_release.py` برای محل جدید report/artifact به‌روز شد تا اجرای بعدی دوباره فایل GMI را در ریشه تولید نکند.
- `CHECKSUMS.sha256` یک manifest تاریخی release است، نه checksum وضعیت dirty فعلی؛ عمداً بازتولید نشد.
- لینک‌های Markdown محلی با validator بررسی می‌شوند و project map/reports index با `scripts/refresh_project_docs.py` قابل‌بازتولید است.
- کنترل نهایی وجود `bridge.json`، session، `data/`، `runtime/`، `catalog/` و `backups/` را تأیید کرد؛ هیچ Git stage/commit/push یا clean انجام نشد.

## ۵. سیاست آینده

- گزارش جدید فاز: `docs/reports/phases/`.
- گزارش قابلیت مستقل: `docs/reports/features/`.
- handoff: `docs/handoffs/`.
- checklist: `docs/checklists/`.
- یافتهٔ جاری: `docs/project-memory/`، نه گزارش تاریخی جدید.
- فایل build/runtime فقط در صورتی منتقل شود که تمام consumerها و migration سازگار هم‌زمان اصلاح و تست شوند.

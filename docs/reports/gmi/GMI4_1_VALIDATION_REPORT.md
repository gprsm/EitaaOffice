# گزارش اعتبارسنجی GMI 4.1 — Material UI / Responsive / Performance Repair

تاریخ: 2026-07-24

## نسخه‌ها

- Product: `0.7.0-ui-mvp6.1.1-gmi4.1`
- Bridge package: `0.7.0.dev30`
- UI package: `0.7.27`
- Core package: `0.6.0.dev19`
- SQLite schema: `9`
- Content-index schema: `2`
- Contact schema: `1`

## آزمون‌های موفق

- Pytest کامل: `254/254`
- GMI4 deterministic smoke: `31/31`
- Python compileall: موفق
- Scroll model: `10/10` با 5,000 پیام ترکیبی
- Grouped-media model: `16/16`
- TypeScript/TSX syntax transpile: `11` فایل، `0` خطای نحوی
- Node syntax برای اسکریپت‌های مدل: موفق
- Wheel نصب‌شده: Bridge `0.7.0.dev30`، Core `0.6.0.dev19`، Product `gmi4.1`
- Target Builder در Wheel نصب‌شده: سقف و `truncated` موفق
- Privacy scan: موفق

## مواردی که به‌طور خاص بازبینی شدند

- RTL واقعی MUI با Emotion Cache
- Dialogهای Full-screen در موبایل
- Gridهای 12 ستونه و تک‌ستونه‌شدن در Breakpointهای کوچک
- عدم بسته‌شدن Dialog ایندکس در اثر Event bubbling از Workspace
- حذف Side-effect تو در تو از State Updater ایندکس
- حذف Query تکراری اولیه دفترچه مخاطبان
- محدودسازی نمایش مخاطبان، اعضا و گفت‌وگوها
- محدودسازی نتایج و Job ایندکس
- قفل درخواست‌های هم‌زمان Thumbnail و Full media
- محدودسازی Target Builder به 10,000 گیرنده
- ردکردن Build قدیمی UI توسط Installer

## محدودیت صریح اعتبارسنجی

محیط ممیزی به `registry.npmjs.org` دسترسی DNS نداشت. در نتیجه نصب واقعی پکیج‌های MUI و Production Build با Vite در این محیط اجرا نشد. بررسی نحوی TypeScript، مدل‌های Node و تست‌های منبع موفق‌اند، اما Type-check کامل با Declarationهای واقعی MUI و پذیرش بصری نهایی باید در Windows انجام شود.

`ui/dist` موجود فقط برای حفظ تست‌های Frozen قبلی نگهداری شده و نشانگر `.material-ui-v1` ندارد. `install_app.bat` آن را رد می‌کند و در Windows یک Build تازه Material UI ایجاد می‌کند.

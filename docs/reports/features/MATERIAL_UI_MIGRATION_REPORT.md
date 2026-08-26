# گزارش مهاجرت Material UI — GMI 4.1

تاریخ: 2026-07-24

## به‌روزرسانی وضعیت جاری — 2026-08-20

بخش‌های بعدی این گزارش سابقهٔ مهاجرت نخست GMI 4.1 هستند. وضعیت runtime جاری کامل‌تر است:

- همهٔ sourceهای فعال TSX، شامل فهرست مجازی پیام و عملیات گروهی، فقط از Material UI و `theme/sx` استفاده می‌کنند؛ `className` و import stylesheet اختصاصی در graph فعال وجود ندارد.
- `styles.css` و `login-experience.css` برای تاریخچه باقی مانده‌اند ولی import نمی‌شوند.
- Navigation، Conversation List، Chat Header، Settings، Contacts، Auth و Toast به moduleهای مستقل تفکیک شده‌اند و موبایل مبنای اولیهٔ layout است.
- TypeScript و build تولیدی موفق‌اند؛ 1006 module پردازش شد و chunk اصلی 785.60 kB است. Warning آستانهٔ 500 kB همچنان در F-013 باز است.
- پذیرش automated روی 360/390/mobile landscape/desktop، touch target، safe-area و نبود class موفق است؛ پذیرش دیداری تازه به‌علت مسدودبودن localhost در Browser این نوبت اجرا نشد و F-025 آن را ثبت می‌کند.

گزارش تکمیلی: `MATERIAL_MOBILE_SELF_REGISTRATION_LIVE_SYNC_REPORT_2026-08-20.md`.

## تصمیم معماری

رابط قبلی بر CSS اختصاصی و کنترل‌های HTML پراکنده متکی بود. در این شاخه، Material UI به‌عنوان Design System رسمی رابط تعیین شد و Theme واحد، Emotion Cache راست‌به‌چپ و Breakpointهای استاندارد MUI اضافه شدند.

## محدوده مهاجرت

- پوسته اصلی برنامه با `Box` و `Paper`
- Splash، خطای Startup، ورود و بازیابی Session
- پنجره ایندکس و فیلتر با `Dialog`, `Tabs`, `Grid`, `Stack`
- پنجره اصلاح چندایندکسی با جست‌وجو و فهرست محدود
- دفترچه مخاطبان، دسته‌ها، ورود فایل، منابع ایتا و ساخت مخاطبان هدف
- پوسته تمام پنجره‌های عملیاتی قدیمی در `Dialog` واکنش‌گرای MUI
- Theme سراسری برای تضاد رنگ، اندازه فیلد، Border، Radius و Typography
- RTL واقعی با `@emotion/cache` و `stylis-plugin-rtl`

## استثنای آگاهانه

فهرست مجازی پیام‌ها و برخی عناصر بسیار پرتکرار هر ردیف، به‌صورت Custom DOM باقی مانده‌اند. تبدیل هر ردیف مجازی به درخت سنگین MUI می‌توانست مصرف حافظه و هزینه Reconciliation را افزایش دهد. این عناصر از Tokenهای Theme و CSS Bridge تبعیت می‌کنند، ولی موتور Virtualization قبلی حفظ شده است.

## Responsive

- زیر 600px: Dialogها Full-screen، فرم‌ها تک‌ستونه، Actionها تمام‌عرض و Tabها Scrollable می‌شوند.
- 600 تا 899px: Gridها دو ستونه یا تک‌ستونه متناسب با محتوا هستند.
- 900px به بالا: چیدمان چندستونه دسکتاپ فعال است.
- همه Containerها `min-width: 0` و `max-width: 100%` دارند تا Overflow افقی کنترل شود.

## محدودیت Build در محیط ممیزی

محیط ممیزی به Registry عمومی npm دسترسی DNS نداشت؛ بنابراین Production Bundle جدید در همان محیط ساخته نشد. خروجی قدیمی `ui/dist` حذف شد و Installer فقط Build دارای نشانگر `.material-ui-v1` را می‌پذیرد. در Windows، نخستین اجرای `install_app.bat` وابستگی‌ها را نصب و Build جدید را ایجاد می‌کند.

# گزارش Privacy Scan — GMI 2

نتیجه: موفق

- در Working tree و بسته نهایی هیچ `.env` واقعی، Session، دیتابیس واقعی،
  Log، رسانه، فایل تشخیصی یا credential کاربر وجود ندارد.
- پوشه‌های `data`، `backups`، `diagnostics`، `runtime/logs` و
  `runtime/uploads` فقط `.gitkeep` دارند.
- Wheel جدید فقط کد/metadata را دارد و هیچ فایل خصوصی، SQLite یا Session
  در آن نیست.
- دیتابیس runtime ایندکس متن خام پیام را دریافت نمی‌کند؛ فقط SHA-256 متن
  نرمال‌شده، شناسه پیام، پیشنهادها، امتیازها و شواهد کوتاه ویژگی ذخیره می‌شود.
- فایل‌های Lab مصنوعی و بی‌هویت‌اند.
- شماره‌ها، access hashها و رمزهای موجود در tests/exampleها ساختگی‌اند.
- `node_modules`، cacheهای pytest/Python، محیط Wheel-test و build tree از
  Working ZIP حذف شدند.

مواردی که هنگام اجرای واقعی روی رایانه کاربر ساخته می‌شوند—از جمله
`data/content_index.sqlite3` و Backupهای Migration—جزء بسته انتشار نیستند.

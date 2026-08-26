# گزارش Privacy Scan نسخه GMI3

دامنه اسکن: Source، Wheel، UI build، Working ZIP و Review Bundle.

موارد ممنوع:

- `.env` واقعی
- Session یا Token
- SQLite/DB واقعی
- Log و Diagnostics واقعی
- رسانه و فایل Import کاربر
- cache، venv و `node_modules`

تنها `.env.example` و `.env.multisite.example` مجازند. `data/`, `diagnostics/`, `runtime/logs/` و `runtime/uploads/` فقط `.gitkeep` دارند.

اسکن محتوایی برای الگوهای Session، Bearer، Application Password واقعی، شماره ایرانی طولانی و کلید خصوصی در بسته نهایی اجرا می‌شود. مثال‌ها و fixtureهای مصنوعی آزمون خصوصی محسوب نمی‌شوند، اما در گزارش تفکیک می‌شوند.

نتیجه Release scan:

- فایل ممنوع: `0`
- Private-key hit: `0`
- فایل Working ZIP: `279`
- شماره‌های شناسایی‌شده در fixtureهای مصنوعی آزمون: `37` (هیچ‌کدام داده کاربر نیست)

Working ZIP دوباره از داخل بررسی شد و venv، `node_modules`، Session، DB، Log و رسانه در آن وجود ندارد.

# GMI4 — گزارش Privacy Scan

خروجی Working ZIP و Review Bundle با قواعد زیر بررسی شد:

- `.env` واقعی: صفر.
- Session/Token file: صفر.
- SQLite/DB واقعی: صفر.
- Log و Diagnostics واقعی: صفر.
- Media واقعی: صفر.
- Private key: صفر.
- `.venv`، `.wheel-test` و `node_modules`: صفر.

شماره‌های موجود در `tests/` و `scripts/gmi4_smoke.py` دادهٔ مصنوعی و مخصوص آزمون‌اند. `Access Hash`های آزمون نیز مصنوعی‌اند و بررسی شده که در پاسخ API ظاهر نشوند.

فایل‌های `.env.example` و تنظیمات نمونه صرفاً Placeholder هستند و Secret واقعی ندارند.

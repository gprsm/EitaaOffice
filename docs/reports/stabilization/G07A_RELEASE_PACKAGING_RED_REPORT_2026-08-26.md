# گزارش G-07-A — RED سخت‌سازی بسته‌بندی

تاریخ: 2026-08-26  
Run: `STAB-G07-R01`  
Ledger: `V-132`  
وضعیت: `RED_VERIFIED / AUTO_CONTINUE_G-07-B`

فایل `package_clean.py` فقط blacklist نداشت؛ در سطح encoding نیز UTF-16LE با 1826 بایت NUL بود و Python آن را import نمی‌کرد. برای ادامهٔ ممیزی، test loader فقط در این مرحله source را با UTF-16 خواند؛ این fallback بخشی از محصول نیست.

در درخت کاملاً مصنوعی، تابع فعلی `prompt_out.txt` و `probe.json` را واقعاً داخل ZIP گذاشت. قراردادهای تازه همچنین allowlist canonical، dry-run بدون write، determinism+receipt، privacy scan کم‌افشا و رد traversal/backslash/absolute path را مطالبه می‌کنند.

تلاش نخست collection error داشت. تلاش دوم هر هشت contract را RED کرد ولی assertion encoding source bytes امن را verbose چاپ کرد؛ assertion محدود و تلاش سوم با basetemp تازه canonical شد: `0/8 passed`, `8/8 failed`.

هیچ archive واقعی پروژه ساخته نشد و داده، session، config، Provider، Bale یا Git لمس نشد. B فایل را به UTF-8 و packager allowlist/manifest تبدیل می‌کند.

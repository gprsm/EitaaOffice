# GMI4 — گزارش Invariants

مبنای مقایسه: ZIP پاک و امضاشدهٔ GMI3.

نتیجهٔ `scripts/check_gmi4_invariants.py`:

- Frozen files: `16`
- Mismatches: `0`
- Missing: `0`

موارد فریز‌شده شامل Core wheel، Scheduler، Facade، Doctor، Runtime، Installer، WordPress، Composition storage/manifest و Scroll math/tests است.

نتیجه:

- Core source/wheel تغییر نکرد.
- Scheduler logic تغییر نکرد.
- Runtime و فایل‌های داخلی Installer تغییر نکردند.
- WordPress logic تغییر نکرد.
- Scroll math و rendering پیام تغییر نکردند.
- Content Index و Gallery logic تغییر نکردند.

تنها خواندن metadata فهرست شماره در Bridge API از قفل RPC مستقل شد؛ این تغییر local-only است و Scheduler را تغییر نمی‌دهد.

دو Entry Point ریشه‌ای `setup_venv.bat` و `BUILD_OFFICE_SETUP_EXE.bat` به‌علت ضرورت نسخه‌ای، فقط از Wheel قدیمی `dev27` به Wheel بسته‌شدهٔ `dev29` اصلاح شدند. نصب واقعی و کنترل خودکار هر دو مسیر موفق بود.

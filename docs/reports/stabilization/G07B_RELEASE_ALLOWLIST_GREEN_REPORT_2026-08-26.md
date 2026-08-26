# گزارش G-07-B — allowlist و manifest انتشار

تاریخ: 2026-08-26  
Run: `STAB-G07-R01`  
Ledger: `V-133`  
وضعیت: `ALLOWLIST_TARGETED_GREEN / AUTO_CONTINUE_G-07-C`

فایل UTF-16/NUL به‌دلیل محدودیت decoder ابزار patch مستقیماً قابل جایگزینی نبود؛ پس از کنترل containment، pre-image امن با همان SHA-256 در artifacts حفظ و نسخهٔ UTF-8 با NUL صفر ایجاد شد.

packager تازه فقط فایل‌ها و scopeهای محصولی صریح را می‌پذیرد. manifest داخلی نام/hash/size، receipt بیرونی hash archive، dry-run بدون write و ZIP deterministic دارد. verifier نام‌های traversal/absolute/backslash، duplicate/case collision، محدودیت size، hash/manifest mismatch و private-key/JWT high-confidence را رد می‌کند.

compile موفق، targeted=`8/8` و regression مرتبط=`21/21` است. dry-run واقعی 296 فایل با content-set hash ثبت‌شده انتخاب کرد و ثابت شد هیچ ZIP یا receipt ایجاد نشده است. archive واقعی و reproducibility به C موکول است؛ نصب/انتشار واقعی انجام نشد.

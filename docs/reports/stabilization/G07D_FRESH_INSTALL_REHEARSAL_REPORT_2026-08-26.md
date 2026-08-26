# گزارش G-07-D — wheel parity و fresh-install rehearsal

تاریخ: 2026-08-26  
Run: `STAB-G07-R01`  
Ledger: `V-135`  
وضعیت: `FRESH_INSTALL_REHEARSAL_GREEN / AUTO_CONTINUE_G-07-E`

## REDهای کشف‌شده

wheel نصب‌شونده با source جاری همسو نبود: guard نهایی A تا D را `12/13` کرد و missing=57/mismatched=20 ثبت شد. build استاندارد آفلاین به‌علت نبود setuptools backend شکست خورد. builder stdlib wheel تازه‌ای با parity کامل ساخت، اما نخستین fresh venv در `pip check` سه dependency مفقود cryptography/httpx/websockets داشت.

## علت و اصلاح

هر سه dependency فقط در `application/bale_client` شکسته و قرنطینه‌شده استفاده می‌شدند. مطابق G-02، این subtree از release source/wheel حذف و dependencyهای صرفاً آن از metadata برداشته شدند؛ `providers/bale/slot.py` fail-closed برای catalog صادقانه حفظ شد. builder اکنون پارامتردار، deterministic، بدون شبکه و متصل به pyproject است و چهار entrypoint را می‌سازد. launcher دیگر build cache یا egg-info را حذف نمی‌کند.

## پذیرش ایزوله

دو wheel نهایی بایت‌یکسان، 90 source file و SHA-256=`de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf` دارند. archive نهایی 282 فایل و SHA=`8b76948818111db7856278f8787ed8c1a277d1b2dd5d0680c0c24733fe3f3437` دارد.

در extract تازه، 15/15 فایل ضروری حاضر، Bale client صفر، self-dry-run همان 282 و compile سبز بود. venv تازه فقط از wheelهای archive نصب شد؛ runtime checker، `pip check` و import API/Event Catalog سبزند. تست package/Bale=`20/20` و regression مرتبط=`102/102` است.

تمام build/install/extractها فقط زیر artifacts بودند؛ هیچ نصب کاربر/سیستم، publish، Provider، دادهٔ عملیاتی یا توسعهٔ Bale انجام نشد.

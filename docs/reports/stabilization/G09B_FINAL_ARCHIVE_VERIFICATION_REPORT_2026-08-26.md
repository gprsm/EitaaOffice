# گزارش G-09-B — ساخت و راستی‌آزمایی archive نهایی

تاریخ: 2026-08-26  
Run: `STAB-G09-R01`  
وضعیت: `ARCHIVES_REPRODUCIBLE / PRIVACY_GREEN / AUTO_CONTINUE_G09_C`

## هدف و مرز

دو archive تازه از allowlist جاری G-09 ساخته شد تا reproducibility، manifest، hash هر عضو، نام‌های امن و privacy scan مستقل از archive تاریخی G-07 سنجیده شود. خروجی‌ها فقط در `artifacts/stabilization` قرار دارند؛ هیچ فایل عملیاتی، Provider، Bale، شبکه، نصب سیستمی یا Git state تغییر نکرد.

## خروجی قطعی

- هر archive شامل 282 فایل مجاز به‌علاوهٔ `_release/CONTENT_MANIFEST.json` است؛ تعداد entry برابر 283 است.
- SHA-256 هر دو archive بایت‌یکسان است: `a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360`.
- content-set هر دو: `cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a`.
- verifier داخلی برای هر دو archive schema/count/order/size/hash و privacy scan را پذیرفت؛ private-key/JWT high-confidence finding برابر صفر است.
- بازبینی مستقل ZIP برای هر دو: manifest در آخر، duplicate=0، case-collision=0 و forbidden-entry=0.
- receiptهای جداگانه archive hash، content-set و file_count را با archive متناظر یکسان ثبت می‌کنند.

## آزمون و رخداد محیطی

اجرای نخست `tests/test_g07_release_packaging.py` به علت `PermissionError` پوشهٔ موقت پیش‌فرض Pytest به `3 passed / 12 setup errors` رسید؛ هیچ test body محصولی در آن 12 مورد اجرا نشد و failure محصول نبود. اجرای مجدد با basetemp تازه و کنترل‌شده و cache غیرفعال، بدون تغییر source/test، برابر `15/15 passed` شد. این تفکیک برای جلوگیری از پنهان‌شدن شکست محیطی ثبت شده است.

RED تازه اجرا نشد، چون G-09-B artifact acceptance است و قراردادهای adversarial بسته‌بندی در V-132 و آزمون wheel drift در V-141 پیش‌تر RED معتبر دارند. کد packager و test در این بخش تغییر نکرد.

## Artifactهای قابل بازیابی

- `artifacts/stabilization/G09B_final_a.zip`
- `artifacts/stabilization/G09B_final_a.receipt.json`
- `artifacts/stabilization/G09B_final_b.zip`
- `artifacts/stabilization/G09B_final_b.receipt.json`

## نتیجه و ادامه

پذیرش G-09-B برابر `FINAL_ARCHIVE_GREEN` است. G-09-C باید یکی از archiveهای پذیرفته‌شده را در ریشهٔ ایزوله استخراج و نصب تمیز کاملاً آفلاین را بدون تغییر سیستم یا دادهٔ واقعی تکرار کند.

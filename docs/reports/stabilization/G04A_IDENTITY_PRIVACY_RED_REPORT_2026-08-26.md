# گزارش G-04-A — ممیزی قرارداد هویت و RED مستقل حریم خصوصی

تاریخ: 2026-08-26  
Run: `STAB-G04-R01`  
وضعیت: `STAGE_COMPLETE / RED_VERIFIED / G-04-B_AWAITING_USER`  
Finding: `F-044 OPEN`

## هدف و مرز

G-04-A فقط نقطهٔ شکست واقعی قرارداد متأخر هویت را تعیین کرد. نمایش مقدار canonical کامل در UI و پاسخ مجاز محصول rollback نمی‌شود، ولی همان مقدار در Runtime Log، Audit، Diagnostic، Support Bundle یا گزارش مهندسی ممنوع است. در این بخش هیچ اصلاح محصول، migration، عملیات Live یا توسعهٔ Bale انجام نشد.

## بخش‌بندی G-04

| بخش | دامنه | وضعیت |
|---|---|---|
| G-04-A | ممیزی قرارداد، تشخیص placeholder و RED مستقل redaction | `RED_VERIFIED` |
| G-04-B | اصلاح دو تست خالی و identity-hint redaction | `AWAITING_USER` |
| G-04-C | جداسازی `phone_e164` از token در onboarding عمومی | `NOT_STARTED` |
| G-04-D | اسکن خصمانهٔ Log/Audit/Diagnostic/Support Bundle و regression مرتبط | `NOT_STARTED` |
| G-04-E | full regression، اسناد نهایی و closure F-044 | `NOT_STARTED` |

## ممیزی قرارداد

- `masked_phone()` برای هویت E.164 مقدار canonical را در مرز محصول حفظ می‌کند؛ این رفتار با تصمیم کاربر همسو و آزمون تازهٔ آن سبز است.
- دو تست تاریخی در `tests/test_coordinator_schema.py` همچنان بدنهٔ خالی دارند و هیچ قراردادی را محافظت نمی‌کنند.
- redaction عمومی کلیدهای تلفن شناخته‌شده را حذف می‌کند، اما نام‌های `phone_hint` و `display_hint` در مجموعهٔ آن نیستند. در نتیجه داده‌ای که با این نام‌ها به observability برسد، مستقل از مجازبودن نمایش UI، محافظت کافی ندارد.
- Baseline، Specification و Architecture اکنون مرز نمایش/observability را درست تفکیک می‌کنند؛ شکاف جاری رفتاری و آزمونی است، نه مجوزی برای تغییر قرارداد محصول.

## RED هدفمند

فایل تازهٔ `tests/test_g04_identity_privacy_stabilization.py` از دادهٔ کاملاً ساختگی و پیام شکست بدون echo مقدار استفاده می‌کند.

| قرارداد | نتیجه |
|---|---|
| دو تست تاریخی placeholder نباشند | FAIL معتبر |
| نمایش canonical در مرز مجاز محصول حفظ شود | PASS |
| identity hint در redaction مقدار کامل نگه ندارد | FAIL معتبر |

نتیجهٔ کل: `3 collected / 1 passed / 2 failed`، exit code 1، بدون failure محیطی و بدون retry. دو شکست به‌ترتیب `test_drift` و `privacy_contract` طبقه‌بندی شدند.

Full Backend در این بخش اجرا نشد: فایل تازه عمداً RED است و کد محصول هنوز تغییر نکرده است. نتیجهٔ `610/610` فقط شاهد سبز snapshot پایان G-03 باقی می‌ماند و وضعیت فعلی G-04 را سبز اعلام نمی‌کند.

## تغییرها و هش‌ها

تنها فایل آزمون G-04-A افزوده شد؛ سه فایل موجود ممیزی‌شده تغییر نکردند:

- `identity.py`: `14de42290d97bb0ddc543ffa28dc41402b1619c9a3f91a85faaabaddefb32ac0`
- `redaction.py`: `3d688ab266d6856f49b412cfbcb4f82b05ad921139a0e409bdb1e48c9c186cbb`
- `test_coordinator_schema.py`: `cfb6c6ebc41e04a6cc644c4bd1e6605fbc46ef610f929e2e40ef348658d0b04e`
- `test_g04_identity_privacy_stabilization.py`: `d78bf0fb9c6c94b417d8420fbbcd613dba53271efb4f5a5834f4079ecad70280`

## نقطهٔ ادامهٔ G-04-B

پس از دستور کاربر، فقط این دو RED اصلاح می‌شوند: بدنهٔ دو تست تاریخی با assertionهای قرارداد تازه جایگزین می‌شود و redaction نام‌های identity hint را پوشش می‌دهد. سپس suite اختصاصی با basetemp تازه و regression مرتبط اجرا خواهد شد. ورود به جداسازی token، Support Bundle scan یا full regression در G-04-B مجاز نیست.

هیچ Provider network، Login/OTP/Send، migration/rollback دادهٔ واقعی، فایل config/session/runtime/diagnostics عملیاتی، توسعهٔ Bale یا Git stage/commit/push لمس نشد.

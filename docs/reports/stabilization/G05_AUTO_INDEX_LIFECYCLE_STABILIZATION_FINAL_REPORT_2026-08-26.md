# گزارش نهایی G-05 — lifecycle و Observability ایندکس خودکار

تاریخ: 2026-08-26  
Run: `STAB-G05-R01`  
Ledger: `V-122` تا `V-126`  
Finding: `F-043 CLOSED`  
وضعیت: `G-05 COMPLETE / OFFLINE_AUTOMATED_ACCEPTED / NOT_RELEASE_READY`

## مشکل و تصمیم

API در هر startup یک thread ساعتی daemon می‌ساخت؛ `close()` stop/join نداشت، خطاها با `except Exception: pass` ناپدید می‌شدند و فقط runtime پیش‌فرض scope می‌شد. مطابق مسیر امن برنامه، scheduler ناقص حذف و تا وجود feature/config و قرارداد lifecycle/account scope مستقل، fail-closed شد. ایندکس دستی حفظ شده است.

## مسیر پذیرش

| بخش | نتیجه |
|---|---|
| A — RED | `1/4 passed`, `3/4 failed`؛ thread/orphan، event missing و loop broken ثابت شد؛ manual PASS |
| B — اصلاح | اختصاصی=`4/4`، مرتبط=`76/76` |
| C — adversarial | سه start/close، orphan=`0`، correlation یکتا=`3/3`؛ G-05+Observability=`11/11` |
| D — broad regression | `143/143 passed` |
| E — finalization | full Backend=`625/625`؛ TypeScript/Observability سبز |

## رفتار نهایی

- هیچ `bridge-auto-indexer` یا loop نامحدود در API ساخته نمی‌شود.
- startup یک event cataloged/correlated با reason امن و metadata محدود برای safe-default ثبت می‌کند.
- پنج مسیر manual content index شامل start/status/cancel/results/feedback باقی‌اند.
- فعال‌سازی آینده بدون config صریح، stop/join محدود، cancellation، backoff، account isolation و failure visibility ممنوع است.

در G-05 فقط `api.py`، Event Catalog و آزمون/اسناد مرتبط تغییر کردند. تمام DB/config/logها مصنوعی بودند و هیچ Provider، Login/OTP/Send، دادهٔ عملیاتی، توسعهٔ Bale یا Git mutation انجام نشد.

G-05 و F-043 بسته‌اند، اما پروژه هنوز `NOT_RELEASE_READY` است؛ G-06 تا G-09 و F-042/packaging باقی‌اند.

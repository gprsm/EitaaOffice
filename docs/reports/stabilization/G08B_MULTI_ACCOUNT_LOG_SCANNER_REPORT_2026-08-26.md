# گزارش G-08-B — اسکنر امن چندحسابی Runtime Log

تاریخ: 2026-08-26  
Run: `STAB-G08-R01`  
وضعیت: `TARGETED_AND_RELATED_GREEN / AUTO_CONTINUE_G08_C`

## نتیجه

`phase10_log_redaction_verify.py` دیگر account id ثابت یا فهرست دو‌مسیره ندارد. اسکن از ریشهٔ مشخص، application log و rotationهای عددی آن و هر پوشهٔ مستقیم حساب به‌همراه worker log/rotation را کشف می‌کند. symlinkها پذیرفته نمی‌شوند و گزارش فقط scope ترتیبی `account-NNNN`، channel، rotation و شمارهای عددی را نگه می‌دارد؛ مسیر، نام پوشهٔ حساب و مقدار یافته چاپ نمی‌شود.

JSONL خراب، UTF-8 نامعتبر، فایل فعلی مفقود، شکست خواندن، symlink و کلید/الگوی حساس همگی fail-closed هستند. format گزارش به نسخهٔ `eitaa-bridge-log-redaction-verification-v2` ارتقا یافت. CLI گزینهٔ `--root` دارد تا contract روی نصب مصنوعی قابل‌آزمون باشد؛ report فقط مستقیماً زیر `backups/phase10-rollout` همان root قابل‌نوشتن است.

## آزمون

- compile اسکنر: PASS؛
- scanner targeted: `2/2 passed`؛
- privacy/observability/diagnostics/Phase10-D related: `18/18 passed`؛
- failure/error/skip: صفر.

fixture آزمون malformed پس از RED یک application log سالم مصنوعی دریافت کرد تا finding فایل ضروری مفقود با دو finding هدف مخلوط نشود؛ این اصلاح harness است و رفتار محصول را پنهان نمی‌کند.

## Hash و مرز

- scanner pre=`99c34024...`، post=`a0c28c122d54896082318545d56c884f12c65292871323a0bfeb4df22eb893d5`
- test post=`3922875718d92d72a652a598c9bd68a3d8bef0c8bd9f33259cdb63064b16b043`
- هیچ اسکن Live یا خواندن runtime/config/account واقعی انجام نشد؛ فقط basetemp مصنوعی، source، test و docs تغییر کردند.
- F-048 هنوز برای lifecycle/catalog و health/retention باز است؛ G-08-C خودکار ادامه دارد.


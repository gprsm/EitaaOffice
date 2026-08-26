# گزارش G-08-A — ممیزی و شاهد RED مشاهده‌پذیری

تاریخ: 2026-08-26  
Run: `STAB-G08-R01`  
وضعیت: `RED_VERIFIED / AUTO_CONTINUE_G08_B`  
سطح شاهد: `STATIC + SYNTHETIC CONTRACT`

## هدف و مرز

هدف این بخش تبدیل شکاف‌های باقی‌ماندهٔ Observability به قراردادهای شکست‌خورده و قابل‌تکرار بود. همهٔ فایل‌ها و شناسه‌ها ساختگی و زیر basetemp آزمون ساخته شدند. هیچ `runtime/`، `diagnostics/`، config، حساب، Session یا Provider واقعی خوانده یا تغییر داده نشد.

## ممیزی

- اسکنر `phase10_log_redaction_verify.py` یک `ACCOUNT_ID` ثابت و فقط دو مسیر ثابت داشت؛ بنابراین حساب‌های دیگر و rotationها خارج از دامنه می‌ماندند و API قابل‌آزمون برای ریشهٔ مصنوعی نداشت.
- `RuntimeLogger.emit()` خطای handler را به عملیات اصلی منتشر می‌کرد و write-failure counter یا health summary امن نداشت.
- cleanup موجود فقط diagnostic run directoryها را prune می‌کرد؛ retention محدود برای rotationهای Application/Worker و disk-health عددی/path-free وجود نداشت.
- Event Catalog جاری 92 رخداد دارد و آزمون AST برای همهٔ literal `RuntimeLogger.emit()`ها موجود است؛ ممیزی lifecycle/background عمیق‌تر به G-08-C تعلق دارد.
- OBS-008 یعنی Web metrics/alert وابسته به deployment و خارج از closure محلی G-08 باقی می‌ماند.

## RED canonical

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_g08_observability_completion.py --basetemp artifacts/stabilization/G08A-red
```

نتیجه: `4 collected / 0 passed / 4 failed`، exit code 1.

تفکیک شکست‌ها:

1. API اسکن همهٔ account logها وجود ندارد؛
2. همان API برای fail-closed شدن روی JSONL خراب/unsafe وجود ندارد؛
3. خطای مصنوعی handler از `emit()` بیرون می‌آید و `health_summary()` وجود ندارد؛
4. قرارداد retention و disk-health صادر نشده است.

این شکست‌ها `contract` هستند؛ warning ناتوانی pytest در نوشتن cache سراسری، محیطی و نامرتبط با نتیجه است.

## دامنهٔ پیاده‌سازی بعدی

- G-08-B: scanner چندحسابی/rotation، گزارش opaque و malformed JSONL fail-closed؛
- G-08-C: catalog/lifecycle/background و correlation؛
- G-08-D: logger write health، retention/disk health و Support Bundle adversarial؛
- G-08-E: regression کامل و closure اسناد.

## Hash و اثر بیرونی

- pre-image scanner: `99c34024b9b24477dc5fde05f88045dcdb87e6f9058773192a3c15e457b8958d`
- pre-image RuntimeLogger: `2dc04203775c829ebafd34f4ebc960232b7e34f8507465aecef87d65cc554fc1`
- pre-image manager: `fba43190216467231baffeca8838fe24a057812e74c586d9ef3c8521532face9`
- test RED: `1644076e371754207add4ed52e64d3f63ed29ca3f21a34ef927526ec90a09071`
- اثر بیرونی: فقط test temp و مستندات؛ بدون شبکه، عملیات Live، Bale، دادهٔ عملیاتی یا Git mutation.


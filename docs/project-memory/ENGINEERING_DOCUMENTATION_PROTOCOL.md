# پروتکل مستندسازی توسعه و یافته‌ها

وضعیت: لازم‌الاجرا از ۲۰۲۶-۰۸-۱۳

## فصل ۱ — پیش از شروع هر کار

1. `docs/project-memory/README.md` خوانده شود.
2. Baseline، Findings register و سند موضوعی خوانده شوند.
3. Validation ledger بررسی شود تا آزمون معتبر تکرار نشود.
4. فقط اگر Trigger ابطال برقرار بود، بررسی کد/Live/Test تازه انجام شود.
5. Dirty worktree و فایل‌های کاربر حفظ شوند.

## فصل ۲ — هنگام توسعه

- تصمیم تازه همان زمان در Finding یا Architecture Decisions ثبت شود.
- کد Provider-specific خارج از Adapter ممنوع یا به‌عنوان Debt صریح ثبت شود.
- هر Error/Warning مادی Event code امن داشته باشد.
- هر اثر بیرونی Audit و Correlation داشته باشد.
- Secret/PII وارد کد نمونه، log، test artifact یا سند نشود.
- هر فرض ناپایدار با سطح شاهد مشخص شود.

## فصل ۳ — پس از تغییر

حداقل خروجی لازم:

1. به‌روزرسانی `CURRENT_SYSTEM_BASELINE.md` اگر رفتار موجود تغییر کرد؛
2. به‌روزرسانی سند موضوعی؛
3. ثبت وضعیت Finding؛
4. ثبت Validation و Trigger تکرار؛
5. به‌روزرسانی Architecture Decisions برای تصمیم کلان؛
6. گزارش مستقل فاز برای تغییرهای بزرگ؛
7. خلاصهٔ نهایی Chat فقط از روی اسناد ثبت‌شده تهیه شود.
8. `scripts/check_project_memory_integrity.py` اجرا و با exit code صفر ثبت شود؛ متن ازدست‌رفته حدس زده نشود و provenance بازیابی صریح باشد.

## فصل ۴ — سطح شاهد

ترتیب قدرت شاهد:

```text
DECISION < STATIC < UNIT < CONTRACT/FAKE < ADVERSARIAL < ISOLATED RUNTIME < LIVE
```

سطح بالاتر جای سطح پایین‌تر را برای ادعای خودش می‌گیرد، اما پس از تغییر فایل/Config مؤثر، شاهد باید دوباره ارزیابی شود.

## فصل ۵ — قاعدهٔ گزارش خطا و Warning

برای هر رخداد مادی:

- Event name پایدار؛
- Level؛
- Result و reason code؛
- Correlation؛
- Scope حساب/Provider به‌صورت opaque؛
- Metadata امن؛
- اقدام یا Recovery؛
- تست redaction و coverage.

متن خام Exception، Payload، Query، Credential، شمارهٔ کامل و محتوای پیام به‌صورت پیش‌فرض ممنوع است.

## فصل ۶ — پایان هر نوبت

پیش از اعلام تکمیل به کاربر باید بررسی شود:

- آیا همهٔ یافته‌های مادی در پروژه ثبت شدند؟
- آیا سند قبلی به‌جای ایجاد نسخهٔ متناقض به‌روزرسانی شد؟
- آیا Validation ledger دلیل اجرای آزمون یا اجرا نشدن آن را دارد؟
- آیا نقشه‌راه و وضعیت Finding با کد جدید سازگارند؟
- آیا هیچ دادهٔ خصوصی در سند وارد نشده است؟
- آیا UTF-8، نویسه‌های کنترلی، شناسه‌های یکتا و سطرهای فرمان با checker حافظه سبز هستند؟

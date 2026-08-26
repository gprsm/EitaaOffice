# گزارش نهایی G-06 — ترمیم قرارداد آزمون و regression

تاریخ: 2026-08-26  
Run: `STAB-G06-R01`  
Ledger: `V-127` تا `V-131`  
وضعیت: `G-06 COMPLETE / TEST_CONTRACT_DOMAIN_CLOSED / F-042 PACKAGING OPEN`

## مسئله و اصلاح

ممیزی A نشان داد شکست‌های Bale BOM و Phase 11 قبلاً بسته شده‌اند و تنها RED جاری، runner Phase 10 است: helper به `utils/helpers.tsx` منتقل شده بود، ولی تست هنوز تعریف محلی در `App.tsx` را می‌خواست. B runner را به import/export واقعی متصل و پیام assertion را محدود کرد. guard سراسری تازه نیز هر تابع تست خالی و marker بدون شرط/reason را رد می‌کند.

## شواهد مرحله‌ای

- A: RED canonical guard=`2/3` و Phase 10 پس از پنج PASS روی assertion ششم FAIL؛ تست خالی و skip/xfail نامعتبر صفر.
- B: guard=`3/3`، Phase10=`7/7`، Backend مرتبط=`66/66` و mobile-auth سبز.
- C: هر ۹ runner UI، TypeScript و build محلی سبز؛ package/installer اجرا نشد. هشدار غیرمسدودکنندهٔ chunk اصلی `794.74 kB` ثبت شد.
- D: ۳۵ suite گسترده=`307/307 passed`، skip صفر؛ collect-only=307.
- E: full Backend در اجرای نخست=`628/628 passed`، failure/error/skip صفر؛ collect-only=628.

## نتیجه و مرز

حوزهٔ test contract در F-042 بسته است و count نسبت به G-05 دقیقاً سه تست guard افزایش یافته است. خود F-042 به‌علت package allowlist/privacy scan تا G-07 باز می‌ماند. این نتیجه release readiness یا پذیرش Live نیست؛ Provider network، Login/OTP/Send، دادهٔ عملیاتی و Bale لمس نشدند و هیچ Git mutation انجام نشد.

پس از کنترل نهایی generator، حافظه و پیوندها، پنج دقیقه فرصت توقف وجود دارد؛ در نبود پیام کاربر G-07-A خودکار آغاز می‌شود.

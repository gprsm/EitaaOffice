# Handoff فاز ۲ — نرخ واقعی و API پیش‌بررسی

تاریخ: 2026-09-28؛ وضعیت P2: `OFFLINE_COMPLETE` (نمایش UI countdown به P7 واگذار شد)
مرجع: [گزارش P2](../reports/features/WEB_CLIENT_PHASE_02_REPORT.md)، قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` نسخهٔ 1.6.0، V-232.

## چه چیزی تحویل شد

- admission اتمیک در orchestrator برای هر تلاش تازهٔ mutation با همان نمونهٔ `AccountExecutionPolicyService` composition root؛ ثبت نتیجه (موفق/ناموفق/circuit)؛ replay هرگز token مصرف نمی‌کند.
- `POST /api/v2/m2m/delivery/preflight` فقط‌خواندنی با decision/can_attempt/retry_after_seconds/sender_profile_revision/observed_at/valid_until/steps/constraints و `capacity_guaranteed=false` همیشه.
- `AccountExecutionPolicyService.read_only_snapshot` — refill تا زمان جاری بدون هیچ write.
- سه محدودیت جدا در قرارداد: `credential_quota` / `local_policy` / `provider_observed`؛ نبود مشاهده هرگز معنی سهمیهٔ نامحدود ندارد.
- نگاشت 429/503 با `Retry-After` سقف و گرد رو به بالا؛ رد قبل از تماس با Provider.

## شواهد کلیدی

- `tests/test_delivery_preflight.py` = 10/10 با ساعت fake و شمار اثر جانبی صفر.
- full-stack: ارسال ششم `429 + Retry-After` قبل از آداپتور؛ replay با سطل خالی 200 (مصرف‌نکردن token).
- رگرسیون 109 آزمونی (P1/F-090/F-091/orchestration/بله) سبز؛ full Backend و wheel در V-232.

## اقدام اول ادامه‌دهنده

1. شروع P3 (`PHASE_03_CAPACITY_RESERVATIONS.md`): رزرو اتمیک پایدار با انقضا/مصرف/لغو قابل حسابرسی. نقطهٔ اتصال: همین admission و preflight؛ رزرو جایگزین preflight نیست و «ready» هرگز تضمین ظرفیت نیست.
2. نام‌ها و کدهای خطای P1/P2 را تغییر نده؛ قرارداد را پیش از هر تغییر مسیر جدید به‌روز کن.
3. نمایش UI دلیل/countdown در کلاینت وب (P7) با همین response پیاده شود؛ polling وضعیت با نرخ مناسب محدود شود.
4. انتشار Git انجام نشده (درخت مشترک با V-230)؛ تصمیم با مالک است.

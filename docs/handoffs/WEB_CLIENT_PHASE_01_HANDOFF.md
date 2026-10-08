# Handoff فاز ۱ — پروفایل فرستنده و قرارداد پایه

تاریخ: 2026-09-28؛ وضعیت P1: `OFFLINE_COMPLETE` (بدون مؤلفهٔ Live)
مرجع: [گزارش P1](../reports/features/WEB_CLIENT_PHASE_01_REPORT.md)، قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` نسخهٔ 1.5.0، F-094/V-231.

## چه چیزی تحویل شد

- جدول `service_sender_profiles` (schema v11، ارتقای آزموده‌شده 10→11) با revision افزایشی، write اتمیک و `UNIQUE(credential, intent)`.
- enforce کامل سمت سرور در `application/m2m_api.py::handle_send_text`: درخواست بیرونی با `sender_profile_id`/`intent` (یا مسیر قدیمی حساب)؛ پروفایل هرگز حصارهای credential را جایگزین نمی‌کند؛ دورزدن با `sender_profile_mismatch` بسته است؛ هیچ پیش‌فرض پنهانی وجود ندارد (`sender_not_configured`).
- lifecycle صادقانه: `account_unavailable` برای حساب غایب/آرشیو/غیرفعال/قرنطینه؛ عدم جایگزینی بی‌صدای حساب؛ ابطال credential پروفایل‌هایش را بی‌اثر می‌کند.
- مسیرهای admin `GET/PUT/DELETE /api/v2/service-sender-profiles` با حصار زمان‌نوشتن، revision control و دو رخداد audit ثبت‌شده در Event Catalog.
- UI Provider-neutral در `ServiceAccountSettingsPanel` (انتخاب حساب با برچسب امن/ماسک/وضعیت، مدیریت stale_revision، حذف صریح).
- سیاست مهاجرت مستند در قرارداد: دادهٔ قدیمی بدون پروفایل بدون رفتار خودکار، بدون ارسال startup و بدون تغییر `bridge.json` کار می‌کند.
- آزمون مستقل: `tests/test_sender_profiles.py` (۷ آزمون شامل انتقال واقعی HTTP روی loopback) + به‌روزرسانی دو نگهبان نسخهٔ schema به ۱۱.

## زمینهٔ همکاری

این تحویل روی کار نیمه‌تمام یک عامل دیگر ادامه یافت و چهار نقص آن بسته شد: دو رخداد audit ثبت‌نشده در Event Catalog (RED نگهبان AST)، سه خطای TypeScript پنل، drift ویل، و تکمیل/تأیید بخش admin قرارداد. هیچ فایل V-230 (بازبینی بلهٔ کامیت‌نشده) تغییر داده نشد.

## شواهد کلیدی (جزئیات و اعداد در گزارش و V-231)

- full Backend پس از rebuild ویل سبز؛ سنجم رگرسیون F-090/F-091/M2M/service-auth/schema سبز.
- `npm run check`، `test:observability`، `build` سبز؛ integrity/link-check/diff-check exit=0.
- wheel `0.7.0.dev31` با SHA-256=`abcb0462…0887a9e` و parity 15/15.

## اقدام اول ادامه‌دهنده

1. شروع P2 (`PHASE_02_LIMITS_PREFLIGHT.md`) از دفتر وضعیت. نقطهٔ اتصال: اجرای واقعی سیاست نرخ در مسیر ارسال (کلاس `AccountExecutionPolicyService` در `rate_policy.py` اکنون فقط مسیر persistent-job را می‌بندد) و preflight بدون اثر جانبی.
2. قرارداد را پیش از هر تغییر مسیر جدید به‌روز نگه دار؛ نام‌ها و کدهای خطای P1 را تغییر نده.
3. انتشار Git: هیچ commit/push انجام نشد (درخت شامل تغییرات عمدی V-230 است و فایل‌های مشترک مخلوط‌اند). تصمیم با مالک/هماهنگ‌کننده است.

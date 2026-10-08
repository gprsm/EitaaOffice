# P3 — رزرو ظرفیت و پذیرش اتمیک

وضعیت اولیه: PLANNED. پیش‌نیاز P1 و P2؛ [قواعد مشترک](EXECUTION_RULES.md).

## هدف و حدود تضمین

preflight تضمین ندارد. رزرو کوتاه‌عمر، سهم عملیات محلی و فرستندهٔ مشخص را به جریان OTP اختصاص دهد تا دو درخواست آخرین ظرفیت را هم‌زمان نگیرند. رزرو سهمیهٔ مخفی Provider یا تحویل پیام را تضمین نمی‌کند. تضمین اتمیک چندفرایندی فقط برای دادهٔ durable واقعاً تراکنشی و آزموده‌شده ادعا شود؛ این ادعا نباید به agent.chat حافظه‌ای منتقل شود.

## مدل و قرارداد

در Coordinator و سازوکار migration فعلی پیاده کن، نه dict حافظه‌ای. از transaction اتمیک موجود یا BEGIN IMMEDIATE متناسب SQLite استفاده کن؛ هیچ await شبکه یا worker در transaction باز نباشد.

record حداقل: id تصادفی غیرقابل حدس، service_id، sender_profile_id/revision، pinned account_id/provider، intent، recipient binding، fingerprint درخواست، operation costs، expires_at و state. شمارهٔ کامل/OTP در این جدول ذخیره نشود. binding با HMAC کلید سرور روی شمارهٔ نرمال‌شده، هدف و سرویس باشد؛ hash سادهٔ شماره قابل جستجوی معکوس است.

state machine مشخص: reserved→consumed یا cancelled/expired؛ consumption به operation_id durable یکتا متصل شود. رزرو لغوشده/منقضی دوباره زنده نشود. تغییر membership/revocation/account lifecycle هنگام consume دوباره بررسی شود. سیاست revision تغییرکرده صریح باشد: پیش‌فرض رد و رزرو تازه، نه تغییر بی‌صدای حساب.

مسیرهای پیشنهادی create/cancel/status برای delivery reservations با scopeهای دقیق در قرارداد؛ cancel فقط مالک و idempotent. تعداد outstanding، TTL، هزینه و rate ایجاد رزرو محدود شوند تا یک سرویس ظرفیت حساب را برای همیشه حبس نکند.

## حسابداری و retry

- تصمیم capacity + ایجاد رزرو + debit باید یک تراکنش باشد؛ fingerprint همان idempotency key با payload متفاوت conflict.
- consume تکراری همان operation را برگرداند، نه acquire دوباره.
- token reserved و هزینهٔ started/completed را جدا ثبت کن. فقط هزینهٔ قطعاً شروع‌نشده refund شود؛ refund دو بار و افزایش فراتر از ظرفیت ممنوع.
- expiry janitor و lazy expiry هر دو به transition یکسان اتمیک متکی باشند؛ restart رکوردهای قدیمی را حفظ و بازیابی کند.
- بعد از شروع RPC و فقدان نتیجه، uncertain تعیین کن؛ timeout به معنای refund send نیست. صف انتظار بیشتر از expires_at به شروع ارسال منجر نشود.
- خارج از این سازوکار مسیر legacy نباید ظرفیت رزروشده را تصاحب کند؛ سیاست تعامل legacy/rate bucket مستند و تست شود.
- secret و context تحویل در P4 از این record عمومی جداست. retention محدود و metadata پاک‌سازی‌شونده بدون حذف operational data واقعی تعریف شود.

## آزمون الزامی

ظرفیت یک: دو request هم‌زمان فقط یک پذیرش؛ آزمون دو connection و دو process روی DB موقت مستقل، نه فقط lock داخل یک event loop. fake clock برای expiry/refill و race cancel/consume/expire. restart قبل و بعد از consume، consume دوباره، crash پس از debit، fingerprint متفاوت، credential سرویس دیگر، account revocation و refresh UI. شمار token، refund، عملیات و worker صریح assert شوند؛ در این فاز worker واقعی صفر.

## پذیرش

P3-A01: رقابت ظرفیت، ownership و pinned sender اتمیک و durable هستند.

P3-A02: expiry/cancel/consume/restart و refund بدون نشتی یا double-credit PASS.

P3-A03: API و خطاهای stale/expired/conflict در قرارداد دقیق‌اند.

P3-A04: محدودیت سوءاستفاده و تعامل ارسال legacy بررسی شده؛ گزارش، handoff و دروازه‌ها کامل‌اند.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_03_REPORT.md و handoff متناظر.

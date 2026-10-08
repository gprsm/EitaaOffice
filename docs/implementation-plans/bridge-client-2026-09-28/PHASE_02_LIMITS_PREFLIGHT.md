# P2 — نرخ واقعی و API پیش‌بررسی

وضعیت اولیه: PLANNED. پیش‌نیاز P1؛ [قواعد مشترک](EXECUTION_RULES.md) و [برنامه](WEB_CLIENT_PROGRAM.md).

## هدف

backend وب پیش از بردن کاربر به مرحلهٔ OTP بتواند بپرسد آیا Bridge اکنون برای ایجاد ارتباط جدید آمادگی دارد. پاسخ باید توضیح محدودیت و زمان مجاز بعدی را بدهد؛ هیچ مخاطب یا پیام/رزروی در preflight ایجاد نشود.

## پیاده‌سازی

- مسیر actual M2M→orchestration→worker→Provider را دنبال کن. سیاست AccountExecutionPolicyService را در admission و اجرای واقعی عملیات لازم وصل کن؛ صرف فراخوانی state یا ساخت endpoint کافی نیست. سیاست موجود را با مالک واحد token و refund حفظ کن.
- سه محدودیت را جدا نگه دار: request quota credential/service، ظرفیت محلی account+operation، و cooldown/flood مشاهده‌شدهٔ Provider. 60 درخواست در دقیقهٔ M2M معادل سقف ارسال Provider نیست؛ status polling نیز نباید با تعداد پیام اشتباه شود.
- snapshot خواندنی نرخ باید refill تا زمان جاری را محاسبه کند، بدون acquire/token mutation، worker RPC، resolve شبکه‌ای یا تغییر circuit. clock قابل تزریق؛ persisted monotonic در restart قابل اتکا نیست، زمان و بازیابی را صریح تعریف کن.
- حداقل هزینهٔ مسیر موجود recipient و new_recipient را جدا مدل کن: resolve/read، import/upsert و send. ناشناخته‌بودن قابلیت یا وضعیت Provider را با unknown برگردان؛ absence of cooldown فقط نبود محدودیت مشاهده‌شده است، نه تأیید سهمیهٔ پنهان.
- هنگام ارسال واقعی، acquire اتمیک را دوباره انجام بده. replay موفق نباید token عملیات Provider مصرف کند؛ quota هر HTTP request می‌تواند مستقل اعمال شود.

## قرارداد پیشنهادی

POST /api/v1/delivery/preflight با sender_profile_id، intent و recipient_kind=existing|new؛ ورودی شماره برای snapshot عمومی لازم نیست. نام endpoint پس از تطبیق با API جاری نهایی شود.

response حداقل decision=ready|wait|unavailable|unsupported|unknown، can_attempt، retry_after_seconds، sender_profile_revision، observed_at، valid_until و مراحل لازم را داشته باشد. هر constraint دارای scope، operation، source=local_policy|provider_observed|credential_quota، certainty و updated_at است. حساب/سرویس غیرمجاز هیچ جزئیاتی دریافت نکند.

ready به معنی امکان تلاش طبق سیاست معلوم است؛ capacity_guaranteed=false صریح باشد. unknown بسته به سیاست محافظه‌کارانه may deny یا require reservation، اما never quota-unlimited نمایش داده شود.

inspection معتبر با decision=wait می‌تواند 200 باشد؛ رد خود درخواست به علت quota با 429 و Retry-After؛ وابستگی واقعاً unavailable با 503؛ مجوز نامعتبر مطابق قرارداد 401/403. تصمیم نهایی error mapping در قرارداد ثبت شود. Retry-After بر حسب ثانیه، گردکردن رو به بالا و بیشینهٔ موانع مربوط به همان مسیر است، نه کمینهٔ خوش‌بینانه.

## آزمون

ساعت fake: bucket خالی/نیمه/refill، cooldown Provider بلندتر از backoff محلی، circuit باز و expiry؛ شمار acquire/worker/contact/send در preflight صفر. خواندن متوالی state را تغییر ندهد. حساب A باعث توقف B نشود مگر محدودیت واقعاً service-global باشد. رقابت preflight ready سپس ارسال ردشده مجاز و قابل توضیح باشد. replay فقط rate درخواست را ببیند. provider retry_after معتبر/نامعتبر و skew زمان بررسی شوند. UI دلیل و countdown امن را نمایش دهد؛ quota status poll با نرخ مناسب کنترل شود.

## پذیرش

P2-A01: read-only preflight با زمان و منبع محدودیت صحیح.

P2-A02: همان سیاست در اجرای ارسال enforce می‌شود؛ bypass مستقیم تست شده است.

P2-A03: ready/unknown/429/503 و Retry-After در قرارداد و UI سازگارند.

P2-A04: آزمون fake clock و شمار اثر جانبی مستقل PASS؛ گزارش و دروازه‌ها کامل‌اند.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_02_REPORT.md و handoff متناظر. سقف عمومی ادعایی برای ایتا/بله از روی تجربه یا حدس اضافه نکن.

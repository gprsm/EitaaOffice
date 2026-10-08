# P9 — پذیرش نهایی و تحویل محصول

وضعیت اولیه: PLANNED. پیش‌نیاز: شواهد تمام فازهای ادعاشده؛ [قواعد مشترک](EXECUTION_RULES.md).

## مأموریت

خروجی‌ها را با checkout واقعی تطبیق بده و محصول یکپارچه تحویل بده، نه مجموعهٔ فایل‌های disconnected. جدول requirements→code/API/UI→test→witness→status بساز؛ هیچ معیار قبلی با جملهٔ «در گزارش فاز قبل بود» بسته نشود مگر witness به revision جاری قابل اعمال باشد.

حداقل دامنه: بله در onboarding/runtime اصلی، account isolation، مخاطب/گفتگو/پیام و capabilities واقعی؛ تنظیم فرستندهٔ سرویس؛ preflight/rate enforcement؛ reservation durable؛ OTP contact→send و receipt/retry؛ AI settings/secret و data policy؛ client E2E؛ ابزار و پذیرش Live/گرم. بخش مورد نیاز کاربر غایب، disabled دائمی یا صرفاً mock، مانع پذیرش همان دامنه است.

## کنترل یکپارچه و انتشار

1. همهٔ acceptance IDها را با مدارک مستقل مرور کن. cold startup نباید login/send/import انجام دهد؛ warm runtime نباید session حساب‌ها یا event loop را مخلوط کند.
2. تنظیمات ذخیره‌شده از UI، M2M واقعی و worker به همان مدل policy وصل باشند. duplicate configuration و endpoint bypass باقی نماند. بلهٔ آماده هنوز پشت provider_not_implemented یا onboarding=false تاریخی مخفی نماند؛ unsupported واقعی با دلیل capability نمایش داده شود.
3. F-090/F-091 regressionهای TTL/ظرفیت، atomic save، waiter release، retry، cancellation، متن ذخیره‌شده و is_test_response اجرا شوند. ادعای exactly-once چندفرایند/restart برای agent.chat ممنوع؛ تضمین رزرو DB با تضمین اثر خارجی یکی نشود.
4. migration از fixtures واقعی ساختاریِ بدون دادهٔ خصوصی، backup/recovery dry-run و compatibility نسخهٔ قبلی آزموده شوند. operational config/database واقعی را برای اثبات migration بازنویسی نکن.
5. full pytest، UI check، observability، build/parity و آزمون packaging/wheel متناسب کد تغییرکرده اجرا شوند. bundle release باید Bale module/worker/assets و client resources لازم را واقعاً شامل شود؛ وجود source در checkout کافی نیست.
6. generator، integrity، freshness، links و diff check را اجرا کن. هر شکست و علت و اجرای مجدد در Ledger باشد. generated docs دستی تغییر نکنند.
7. privacy scan scoped تغییرات و artifactها: key/OTP/شمارهٔ کامل/متن خصوصی/نشست/trace payload صفر. فایل‌های کاربر خارج از سناریو stage نشوند.
8. baseline، Findings و قرارداد central با قابلیت نهایی و خطا/retry/policy جدید هماهنگ؛ PLANNED فقط با evidence به IMPLEMENTED/OFFLINE_VERIFIED/LIVE_ACCEPTED ارتقا یابد.
9. مطابق مجوز AGENTS روی شاخهٔ کاری اختصاصی codex/ و فقط فایل‌های سناریوی کامل commit/push؛ نه main، force-push یا secret/config عملیاتی. مانع انتشار ثبت و اعلام شود. نصب/rollout واقعی محصول اجازهٔ جدا می‌خواهد.

## راهنمای کاربر نهایی

راهنمای غیرمبهم و قابل اجرا بده: افزودن حساب و مشاهدهٔ وضعیت؛ انتخاب فرستندهٔ OTP/notification؛ تعیین endpoint/key/model و level داده؛ اتصال backend وب و scopes؛ نمایش محدودیت و retry؛ اجرای dry-plan و Live با اجازه؛ استعلام uncertain و بازیابی بدون duplicate؛ مدیریت/لغو کلیدها و حساب‌ها. نمونه‌ها ساختگی و بدون credential باشند. فرمان اجرا با محیط/پیش‌نیاز دقیق باشد، نه آدرس endpoint فرضی.

## معیار نهایی و گزارش

P9-A01: matrix یکپارچه برای تمام requirements PASS یا blocker صریح دارد.

P9-A02: gates مرکزی و build/package مناسب PASS؛ شکست‌ها و rerun ثبت‌اند.

P9-A03: قرارداد/UI/راهنما/baseline و اجرای واقعی تطبیق دارند.

P9-A04: status Live هر Provider/AI مستقل و صادقانه است.

P9-A05: انتشار scoped با SHA نهایی و وضعیت remote تأیید شده، یا مانع دقیق ثبت شده است.

اگر Live یا ادغام وب‌سایت واقعی ناتمام است، «نسخهٔ آمادهٔ آزمون / OFFLINE_READY_WITH_LIVE_BLOCKERS» تحویل بده؛ «محصول کامل و Live تأییدشده» نگو. release snapshot دارای دامنهٔ صریح تنها مطابق مجوز انتشارِ سناریوی واقعاً تکمیل‌شده مجاز است؛ blockers را مخفی نکن.

گزارش پیشنهادی: docs/reports/features/WEB_CLIENT_FINAL_PRODUCT_REPORT.md و handoff نهایی در docs/handoffs. گزارش نهایی شامل SHA، فایل‌ها، RED→GREENهای واقعی، خروجی/count دروازه‌ها، حدود تضمین درون‌فرایندی/DB/Provider، Live انجام‌شده/نشده و ورودی لازم باشد. EXECUTION_STATUS همهٔ لینک‌های شاهد را داشته باشد؛ هیچ TODO بحرانی به «کار آینده» منتقل نشود.

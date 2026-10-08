# دفتر وضعیت اجرای بله و کلاینت وب

تاریخ ایجاد: 2026-09-28

پیش از هر اجرا این دفتر و گزارش واقعی مرحلهٔ قبلی خوانده شود. به‌روزرسانی آن جای Validation Ledger را نمی‌گیرد.

| مرحله | وضعیت | گزارش/شاهد | مانع یا اقدام بعد |
|---|---|---|---|
| BALE | OFFLINE_REPAIR_VERIFIED_V252 / B6_LIVE_PILOT_EXPANDED_V262 / OWNER_ACCEPTANCE_PENDING | [گزارش بله](../../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md)، F-099/V-257/V-259/V-261/V-262 | مالک در نصب تست خواندن، ارسال متن، تغییر مخاطب، دریافت تازه، جست‌وجو، read-back و restore گرم را تأیید کرد؛ شواهد محدود و تفکیک‌شده در Ledger‌اند. UI پس از رد متناوب `LoadDialogs code=8` cadence گفتگو را از تاریخچه جدا کرد؛ دوام بلندمدت و مسیر عمومی M2M مستقل‌اند. پذیرش/انتشار نهایی باز است. |
| P1 | OFFLINE_COMPLETE (بدون مؤلفهٔ Live) | [گزارش فاز ۱](../../reports/features/WEB_CLIENT_PHASE_01_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_01_HANDOFF.md)، F-094/V-231 | sender profile نسخه‌دار + enforce سرور + UI + قرارداد 1.5.0 سبز؛ بدون commit (درخت مشترک با V-230)؛ P2 آمادهٔ شروع |
| P2 | OFFLINE_COMPLETE (نمایش UI countdown به P7) | [گزارش فاز ۲](../../reports/features/WEB_CLIENT_PHASE_02_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_02_HANDOFF.md)، F-095/V-232 | admission اتمیک در orchestrator + preflight فقط‌خواندنی + قرارداد 1.6.0 سبز؛ بدون commit؛ P3 آمادهٔ شروع |
| P3 | OFFLINE_COMPLETE (بدون مؤلفهٔ Live) | [گزارش فاز ۳](../../reports/features/WEB_CLIENT_PHASE_03_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_03_HANDOFF.md)، V-237 | رزرو durable/اتمیک با HMAC binding، آزمون دو فرایندی، رفع نقص‌های R1/R3 در ممیزی F-099 و قبولی پروب ۴/۴، قرارداد 1.7.0؛ P4 آماده و اجرا شده |
| P4 | OFFLINE_COMPLETE (بدون مؤلفهٔ Live) | [گزارش فاز ۴](../../reports/features/WEB_CLIENT_PHASE_04_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_04_HANDOFF.md)، V-238 | پایپ‌لاین ترکیبی تحویل OTP و شناسایی/افزودن مخاطب، جدول service_otp_deliveries، اندپوینت‌های M2M با کلید یکتایی، عدم نشت داده خام، قرارداد 1.8.0؛ P5 آماده شروع |
| P5 | OFFLINE_COMPLETE (بدون مؤلفهٔ Live) | [گزارش فاز ۵](../../reports/features/WEB_CLIENT_PHASE_05_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_05_HANDOFF.md)، V-239 | فروشگاه امن تنظیمات AI و کلید محرمانه با رمزنگاری AES-256-GCM، اعتبارسنجی سرسختانه URL و ضد SSRF، پروب ترکیبی آزمایشی؛ اندپوینت‌های Admin؛ بدون نشت کلید |
| P6 | OFFLINE_COMPLETE (بدون مؤلفهٔ Live) | [گزارش فاز ۶](../../reports/features/WEB_CLIENT_PHASE_06_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_06_HANDOFF.md)، V-240 | سیاست ۴ سطحی داده در سطح سرور، دروازه خروجی مدل، پالایش سخت‌گیرانه شماره، OTP و کلید، مستعارسازی تک‌طرفه شناسه‌های کاربران، کنترل دسترسی به مدل؛ آمادهٔ P7 |
| P7 | OFFLINE_COMPLETE / EXTERNAL_REPO_LOCATED / INTEGRATION_PENDING | [گزارش فاز ۷](../../reports/features/WEB_CLIENT_PHASE_07_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_07_HANDOFF.md)، V-241/V-245/V-263 | کلاینت مرجع Backend وب با ۱۱ آزمون Loopback واقعی آماده است. مخزن واقعی سایت در `D:/projects/OnlineExam-Copy` شناسایی شد و handoff پیام‌رسان آن وجود دارد؛ انطباق قرارداد و ادغام دو مخزن هنوز انجام نشده است. |
| P8 | OFFLINE_READY / LIVE_PENDING_INPUT (runner منطبق با قواعد فاز؛ V-248/V-250) | [گزارش فاز ۸](../../reports/validation/WEB_CLIENT_LIVE_WARM_ACCEPTANCE_REPORT.md)، [handoff](../../handoffs/WEB_CLIENT_PHASE_08_HANDOFF.md)، V-242/V-245/V-248/V-250 | ورودی‌های حساس (توکن/شماره/متن) از argv حذف و به env/پرامپت امن منتقل شد؛ تأیید همان عملیات برای عملیات اثرگذار الزامی (حتی تعاملی، bare confirm پرامپت نام‌دار دارد)؛ خروجی بدون پاسخ خام AI/exception؛ `warm_verified` فقط با شاهد نشست/اتصال و شمار connect واقعی؛ ai-probe با نشست admin واقعی + CSRF (رد Bearer M2M و fail-closed بدون CSRF)؛ ۲۰ آزمون runner سبز؛ ماتریس زنده همچنان نیازمند ورودی مالک |
| P9 | OFFLINE_GATE_GREEN_V263 / OWNER_ACCEPTANCE_PENDING / LIVE_PARTIAL | [گزارش جامع فاز ۹](../../reports/features/WEB_CLIENT_FINAL_PRODUCT_REPORT.md)، [handoff نهایی](../../handoffs/WEB_CLIENT_FINAL_PRODUCT_HANDOFF.md)، F-099/V-262/V-263 | full Backend روی بستهٔ جاری ۱۰۵۱ پاس/۱ skip، UI و wheel سبزند. پایلوت بله محدود است؛ Live ایتا/AI و ادغام وب‌سایت واقعی معیارهای مستقل باقی‌مانده‌اند. |

## ثبت هر checkpoint

اجرای هر مرحله باید تاریخ، revision، acceptance ID، نتیجهٔ gate و لینک گزارش واقعی را داشته باشد. هر partial یا نیازمند input صریح بنویسد چه عملیات مجازی انجام نشده است. متن OTP، هویت واقعی و credential اینجا ذخیره نشود.

## ورودی‌های Live در زمان اجرای آینده

- نصب هدف و revision واقعی آن؛
- حساب مبدأ و گیرندهٔ مورد تأیید، بدون درج هویت خصوصی در این دفتر؛
- کانال ورود امن credential و محدودیت تعداد عملیات/هزینه؛
- دامنهٔ مجوز همان Pilot؛
- محل backend سرویس وب در صورت اجرای ادغام واقعی.

این موارد در زمان تهیهٔ دستورها بررسی یا تأمین نشده‌اند.

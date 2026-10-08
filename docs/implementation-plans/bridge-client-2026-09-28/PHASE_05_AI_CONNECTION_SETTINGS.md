# P5 — تنظیمات امن اتصال و مدل AI

وضعیت اولیه: PLANNED. پیش‌نیاز P1؛ مستقل از تکمیل ارسال OTP. [قواعد مشترک](EXECUTION_RULES.md).

## هدف و UI

در تنظیمات اصلی، بخش «اتصال هوش مصنوعی» برای مدیر مجاز ایجاد کن: enabled، provider/API dialect پشتیبانی‌شده، endpoint، model_id واقعی، display_name جدا، timeout، سقف ورودی/خروجی و هم‌زمانی، کلید و وضعیت اتصال. endpoint/مدل از ورودی مدیر است؛ مدل دلخواه را به Provider نامرتبط نگاشت نکن. نام نمایشی با شناسه‌ای که در API فرستاده می‌شود یکی فرض نشود.

پیکربندی AI از حساب ارسال پیام مستقل است. پیش‌فرض test adapter باید صریح «آزمایشی» باقی بماند. enabled، configured، reachable و live_verified چهار وضعیت متفاوت‌اند؛ روشن‌کردن سوییچ برابر پذیرش اتصال واقعی نیست.

## کار فنی

- adapter موجود، API schema و storage را بررسی و تکمیل کن؛ اتصال مبتنی بر env فعلی سازگار بماند. routeهای admin برای save/read/probe از M2M عمومی جدا و role-protected باشند.
- پاسخ خواندن فقط key_configured و metadata امن بدهد، نه مقدار/بخشی از کلید. replace/clear/unchanged semantics صریح؛ placeholder ماسک‌شده هرگز به عنوان کلید جدید ذخیره نشود. config و secret rotation اتمیک و revision-aware باشند.
- کلید outbound نیاز به بازیابی دارد؛ hash یک‌طرفه کافی نیست. از secret store و protector موجود استفاده کن، یا حفاظت مناسب Windows/Linux با مدیریت کلید جدا و permission محدود طراحی کن. secret جدید را در bridge.json واقعی، repo، browser storage، URL query یا log قرار نده.
- URL سمت سرور validate شود: HTTPS پیش‌فرض، loopback فقط opt-in توسعه؛ credentials در URL ممنوع، redirect محدود/ممنوع و DNS/SSRF/egress policy متناسب. کلاینت M2M حق انتخاب arbitrary endpoint ندارد. صرف بررسی رشتهٔ hostname در برابر rebinding کافی نیست؛ سیاست شبکهٔ قابل اجرا و حدودش مستند شوند.
- timeout، response size، streaming/cancellation، error mapping، malformed JSON و max retries محدود. پس از نتیجهٔ نامعلوم درخواست مولد مدل، retry خودکار نباید هزینه/پاسخ تکراری تولید کند.
- client گرم را در lifespan/event loop مالک نگه دار. http client یا websocket یک loop را در asyncio.run تازه reuse نکن. تعویض config generationهای فعال را سالم تمام کند و resource قدیمی را پس از خروج آخرین استفاده ببندد.
- probe آنلاین فقط با درخواست مدیر و payload ساختگی حداقلی؛ بدون تاریخچه، شناسهٔ کاربر، شماره یا OTP. /health فرضی نساز؛ probe واقعی مطابق dialect مستند آن Provider باشد.
- P6 شرط فعال‌شدن egress محتوای واقعی کاربر است. در P5 می‌توان اتصال را با fake transport و probe مجاز آزمود؛ نبود سیاست داده به معنای full_history پیش‌فرض نباشد.
- تغییر adapter/setting نباید F-090/F-091 را بشکند: replay پاسخ موفق متن و is_test_response ذخیره‌شده را نگه دارد؛ config جدید باعث فراخوانی پنهانی دوباره نشود. request جاری snapshot config ثابت داشته باشد.

اگر Provider انتخابی OpenAI است، هنگام پیاده‌سازی دستور skill مربوط و منابع رسمی جاری را بخوان؛ این سند نسخه/نام مدل یا SDK متغیر را تجویز نمی‌کند.

## آزمون

read/write/clear/rotation، editor با revision قدیمی، permission و CSRF؛ fake outbound transport مقدار model_id و headers را capture کند ولی خروجی چاپ نکند. secret در UI/response/log/artifact صفر. URL ممنوع، redirect، TLS، timeout/cancel، oversized response، provider error و malformed body. رقابت save و درخواست جاری؛ connection گرم reused، close دقیق و loop ownership. test adapter و live adapter با flag واقعی متمایز؛ probe با تأیید مدیر و بدون دادهٔ خصوصی.

## پذیرش

P5-A01: مدیر endpoint، key و مدل واقعی را از UI امن تنظیم و نتیجه را مشاهده می‌کند.

P5-A02: secrets، egress/URL و lifecycle اتصال با آزمون مستقل پوشش دارند.

P5-A03: config revisions، compatibility و F-090/F-091 حفظ شده‌اند.

P5-A04: probe fake PASS؛ شاهد آنلاین در صورت ورودی/مجوز مجزا ثبت و نبودش صریح است. قرارداد و دروازه‌ها کامل‌اند.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_05_REPORT.md و handoff متناظر. بدون key واقعی ساخت امن این فاز ممکن است؛ live_verified نباید جعل شود.

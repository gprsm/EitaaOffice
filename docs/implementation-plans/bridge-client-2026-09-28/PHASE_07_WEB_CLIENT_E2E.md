# P7 — کلاینت backend وب و آزمون انتهابه‌انتها

وضعیت اولیه: PLANNED. پیش‌نیاز P4؛ برای چت آنلاین P6. [قواعد مشترک](EXECUTION_RULES.md).

## محدودهٔ محصول

کلاینت وب یک سرویس backend معتبر است، نه JavaScript مرورگر با کلید Bridge. مخزن وب‌سایت واقعی را از کاربر/مدارک شناسایی کن؛ پروژهٔ مشابه یا پوشهٔ همسایه را حدس نزن. اگر در دسترس نیست، کلاینت مرجع قابل اجرا و نمونهٔ ادغام امن در همین پروژه بساز و پذیرش ادغام وب‌سایت واقعی را جدا BLOCKED اعلام کن. هیچ قابلیت مرجع نباید به‌عنوان استقرار واقعی گزارش شود.

SDK یا client module با timeout، status mapping، Retry-After، request id امن و parser نسخه‌دار بساز. تمام Bridge credentials و کلید AI در backend بمانند؛ browser storage/URL/HTML bundle حاوی secret نباشد. server credential به کاربر یک سرویس دیگر یا account دلخواه تبدیل نشود.

## جریان لازم

1. backend قبل از هدایت کاربر به صفحهٔ OTP preflight عمومی برای sender/intent و recipient_kind می‌گیرد. اگر هنوز شماره معلوم نیست، نتیجه صرفاً آمادگی عمومی است.
2. UI wait/unavailable/unknown را با دلیل امن و زمان بعدی نمایش می‌دهد. ready تضمین ارسال نیست؛ صفحه نباید خلاف این بنویسد.
3. نام و شمارهٔ کاربر با رضایت و validation گرفته، binding واقعی ساخته و reservation با TTL مناسب گرفته می‌شود. محدودیت هر کاربر/شماره و ضدسوءاستفاده قبل از effect enforce شوند؛ Bridge general status برای account enumeration عمومی نشود.
4. backend challenge و verifier امن تولید می‌کند؛ OTP expire و attempt limit سمت وب‌سایت‌اند. عملیات P4 با idempotency key پایدار dispatch می‌شود. دادهٔ OTP هرگز برای AI ارسال نمی‌شود.
5. status را با interval محدود، jitter/backoff و Retry-After دنبال می‌کند؛ reload/قطع اتصال همان operation را بازیابی کند. poll نباید quota 60/min را کور پر کند یا چند tab هرکدام loop مستقل نامحدود بسازند.
6. نتیجهٔ accepted، uncertain، rejected و expired با UX متفاوت نمایش داده شود. در timeout HTTP، POST جدید با شناسهٔ جدید نزن؛ status همان تلاش را بخوان. fallback بعد از uncertain ممنوع. challenge تازه فقط با سیاست صریح و محدودیت مستقل.
7. تأیید OTP در backend وب با verifier، comparison امن، TTL، شمار تلاش و مصرف یک‌باره انجام شود؛ receipt ارسال برابر احراز کاربر نیست.
8. چت AI فقط با policy P6 و هویت معتبر، is_test_response واقعی و قرارداد replay/conflict/pending فعال شود؛ پاسخ آزمایشی با برچسب آنلاین نمایش داده نشود.

## قرارداد کلاینت و آزمون

endpoint/error قدیمی و جدید را با parser مرکزی و نسخهٔ قرارداد به کار ببر؛ خطای کسب‌وکار را صرفاً «network error» نکن. status 503 pending مربوط به agent.chat با cooldown ارسال مخلوط نشود. admin config routes از client user-facing قابل فراخوانی نباشند. CSRF/session/authorization و remote origin لازم enforce شوند.

آزمون E2E با backend Bridge واقعی روی loopback/پورت موقت و Provider/AI fake انجام شود: مرورگر یا runner واقعی UI→backend وب→HTTP Bridge→worker/backend fake. mock کردن کل client و assert متن ثابت E2E نیست. DB/clock/secret store موقت، بدون بازکردن operational session.

سناریوها: ready→رزرو→contact→send→status→OTP verify، wait پیش از نمایش OTP، quota race پس از preflight، contact failure، send uncertain، expiry، duplicate submit/reload، polling bounded، دو service، credential revoked، AI disabled/live fake/replay و هیچ secret در bundle/network مرورگر به Bridge. count import/send/AI و stage status صریح assert شوند. CSRF و OTP brute-force نیز آزمون شوند.

## پذیرش

P7-A01: جریان UI و backend کامل و قابل اجراست؛ مرورگر کلید Bridge/AI ندارد.

P7-A02: محدودیت، race و شکست‌ها UX صادقانه و retry امن دارند.

P7-A03: E2E واقعی HTTP/UI با counters و isolation PASS است.

P7-A04: راهنمای ادغام، نمونهٔ اجرا بدون secrets، report/handoff و دروازه‌ها کامل‌اند. ادغام مخزن واقعی در صورت غیبت جدا BLOCKED است.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_07_REPORT.md و handoff متناظر. ایجاد سرویس روی 80/443، تغییر Firewall، نصب Proxy یا انتشار واقعی از اختیار این فاز خارج است.

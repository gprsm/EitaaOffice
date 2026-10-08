# P6 — سطح دسترسی و سیاست دادهٔ مدل آنلاین

وضعیت اولیه: PLANNED. پیش‌نیاز P5؛ [قواعد مشترک](EXECUTION_RULES.md).

## هدف و سطح‌ها

کاربر مدیر در تنظیمات هر سرویس انتخاب کند چه دستهٔ اطلاعاتی می‌تواند به مدل برسد. enforcement باید پیش از egress در سرور باشد؛ جملهٔ «این داده را نخوان» در prompt یک کنترل دسترسی نیست.

حداقل سطح‌های روشن، با allowlist جدا برای منابع:

1. disabled: هیچ درخواست مدل آنلاین.
2. current_message: فقط ورودی جاریِ مجاز و سیاست system امن؛ بدون تاریخچه یا شناسهٔ خام.
3. limited_history: تعداد/حجم/بازهٔ زمانی محدود فقط همان مکالمهٔ مجاز.
4. approved_context: علاوه بر موارد مجاز، فقط منابع مشخص و allowlisted با سقف حجم/تعداد و مجوز واقعی.

full_database یا unrestricted پیش‌فرض/نام مبهم ممنوع. «سطح بالاتر» مجوز شماره، OTP، credential، cookie، session، passphrase یا متن سایر کاربران ایجاد نمی‌کند. مدل در این برنامه ابزار contact/send/admin ندارد.

## پیاده‌سازی

- policy revision و connection revision در snapshot درخواست ثبت شوند. عضو/مالک سرویس و مکالمه قبل از retrieval و قبل از خروج بررسی شوند. web_user_id دریافتی به‌تنهایی اثبات هویت نیست؛ binding معتبر از backend وب احراز‌شده لازم است، نه پارامتر آزاد مرورگر.
- retrieval در مرز service/user/session/account مجاز محدود شود؛ شناسهٔ مستند انتخابی کاربر یا prompt injection حق دسترسی ایجاد نکند. این پروژه محل ساخت query آزاد AI روی Coordinator نیست.
- egress builder واحد برای adapter آنلاین: allowlist field، truncation قطعی، history bounds، metadata حداقلی؛ web_user_id/session_id خام فعلی حذف/با pseudonym سرویس‌محور جایگزین شوند، مگر نیاز واقعی با سیاست صریح و حداقل‌سازی پذیرفته شده باشد.
- شماره، OTP و credential ساخت‌یافته اصلاً وارد context builder نشوند. تشخیص secret در متن آزاد دفاع مکمل است؛ regex نمی‌تواند «نبود هرگونه secret» را تضمین کند. UI به کاربر هشدار و preview دسته‌ها/سقف‌ها بدهد، نه dump دادهٔ خصوصی به log.
- policy غیرفعال/فاقد مجوز/نامعتبر fail-closed پیش از transport. failure آماده‌سازی context باید claim را طبق F-091 تعیین تکلیف کند. هیچ پاسخ نیمه‌ثبت‌شده یا inflight رهاشده باقی نماند.
- تغییر مجوز/policy برای درخواست تازه فوری enforce شود؛ دادهٔ قبلاً ارسال‌شده را قابل بازپس‌گیری ادعا نکن. درخواست جاری و لغو هنگام revocation سیاست صریح داشته باشد.
- replay ذخیره‌شده دوباره به مدل نرود. مجوز خواندن نتیجهٔ ذخیره‌شده هنگام replay بررسی شود؛ policy/config تغییرکرده به معنی rerun پنهانی با همان message_id نیست. conflict/replay/reject را با F-090 و fingerprint اصلی سازگار مستند کن.
- retention تاریخچه/پاسخ/cache، حذف مجاز، metadata حسابرسی امن و حافظهٔ چندفرایندی صریح؛ trace فقط policy revision، تعداد/حجم و دستهٔ source، نه payload یا شناسهٔ حساس. ادعای retention Provider فقط از قرارداد واقعی آن باشد.

## آزمون واقعی مرز خروج

transport fake پایین‌تر از serializer درخواست را capture کند. برای هر سطح دقیقاً فیلدهای مجاز/ممنوع و bounds assert شوند؛ fixture شامل secret/شماره/OTP ساختگی و دو سرویس/کاربر با مشابهت شناسه. retrieval از حساب دیگر، malicious prompt، منبع نامجاز و client-supplied policy رد شوند. transport call count برای disabled/unauthorized صفر.

race policy change، cancellation، TTL، failed egress build، replay بعد از revocation و cleanup inflight آزمون مستقل داشته باشند. snapshot test بدون assert معنایی کافی نیست؛ لاگ و artifact تست نباید fixture حساس‌نما را بی‌دلیل چاپ کنند.

## پذیرش

P6-A01: سطح‌ها در UI و enforcement خروجی واقعی واحد و دقیق‌اند.

P6-A02: سرویس/کاربر/حساب دیگر و prompt injection به context دسترسی ندارند.

P6-A03: revocation، replay، retention و cleanup قرارداد قطعی و آزمون دارند.

P6-A04: evidence از body خروجی captureشده، نه ادعای prompt؛ گزارش/دروازه‌ها کامل‌اند.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_06_REPORT.md و handoff متناظر. تا این فاز پاس نشده، تست مدل آنلاین با محتوای کاربر واقعی مجاز نیست.

# P4 — مخاطب واقعی و تحویل مرحله‌ای OTP

وضعیت اولیه: PLANNED. پیش‌نیاز P3؛ بله فقط پس از B1 تا B5 [دستور اول](BALE_FULL_PRODUCT_INTEGRATION.md). [قواعد مشترک](EXECUTION_RULES.md) الزامی است.

## مسئولیت و جریان

وب‌سایت challenge و OTP را ایجاد، verifier را امن ذخیره، expiry و سقف تلاش احراز را enforce می‌کند. Bridge transport احراز‌شده است و مسئول بررسی اعتبار خود OTP نیست. محتوا به AI داده نشود. OTP ورود به حساب Provider با OTP وب‌سایت مخلوط نشود.

یک عملیات ترکیبی durable برای recipient جدید بساز: validate/admit→resolve→import یا upsert با نام درست→ثبت peer واقعی→send→receipt. contacts.resolve موجود خواندنی بماند. شماره را مستقیماً به dialog_id یا eitaa_user_id تبدیل نکن؛ Bale peer باید Provider و نوع واقعی خود را حفظ کند.

## API پیشنهادی و دسترسی

POST /api/v1/otp/deliveries با reservation_id، idempotency_key/message_id، recipient phone/name، challenge_ref غیرحساس، expires_at و محتوای OTP محدود. schema و نام نهایی پس از بررسی قرارداد موجود ثبت شوند. account/provider از reservation گرفته شود، نه از override درخواست.

GET status مالک‌محور بدون متن/OTP/شمارهٔ کامل؛ scope مشاهده مستقل باشد. scope مرکب OTP باید صریح اختیار contact mutation و ارسال را محدود به همین جریان بدهد، یا دو scope دقیق لازم شوند؛ messages.send به‌تنهایی مجوز مخاطب‌نویسی عمومی ایجاد نکند. قابلیت admin مخاطبین مجوز جدا دارد.

payload fingerprint حساس با HMAC و canonicalization پایدار: replay یکسان همان receipt؛ message_id متفاوت برای challenge تازه؛ همان id با payload متفاوت conflict. lookup replay قبل از نیاز به رزرو تازه انجام شود، ولی scope و مالکیت جاری دوباره enforce شوند.

## سازگاری و failure windows

- قبل از هر RPC مرحلهٔ started durable ثبت شود؛ بعد از آن نتیجهٔ امن ثبت شود. concurrency claim همان operation فقط یک worker داشته باشد، با fencing/generation موجود. آزادشدن claim نباید RPC موازی جدید راه بیندازد.
- contact موجود را بدون سیاست صریح overwrite نکن. نام برای مخاطب تازه از ورودی validateشده و به طول محدود؛ شماره نرمال‌شدهٔ مورد تأیید کاربر. fake نتیجهٔ import نباید جای matched peer واقعی را بگیرد.
- اگر مخاطب اضافه شد و send شکست خورد، اثر خارجی را با حذف خودکار مخاطب rollback نکن. receipt contact_created/send_rejected را حفظ و retry مجاز را دقیق تعیین کن.
- crash/timeout بعد از send_started ولی قبل از ثبت پاسخ uncertain است، مگر Provider استعلام قابل اعتماد داشته باشد. random_id یا ACK شبکه به‌تنهایی شاهد دریافت نیست. uncertain هرگز ارسال/Provider fallback خودکار نشود.
- retry فقط مرحله‌ای را اجرا کند که قطعاً شروع نشده یا نتیجهٔ قطعی اجازه می‌دهد؛ از retry عمومی که import/send را کور تکرار می‌کند استفاده نکن.
- OTP منقضی قبل از dispatch یا پس از انتظار صف ارسال نشود. پس از expiry، resend همان challenge ممنوع؛ challenge تازه با مجوز و شناسهٔ تازه ایجاد شود.
- OTP و شمارهٔ کامل وارد log، audit، receipt، DB عمومی Coordinator یا argv نشوند. اگر صف durable به payload نیاز دارد، envelope رمز‌شدهٔ کوتاه‌عمر با کلید حفاظت‌شده و دسترسی worker محدود لازم است؛ انتقال IPC امن موجود حفظ شود. metadata لازم برای retry و status از secret جدا باشد.

status مرحله و نتیجه را جدا کند: pending/running/accepted/rejected/uncertain/expired همراه stage و retryable دقیق. accepted فقط پذیرش ارسال است؛ verified_delivery فقط با شاهد معتبر و اختیاری Provider. HTTP 202 برای صف، 409 conflict، 429 محدودیت، خطاهای dependency و permission مطابق قرارداد؛ Retry-After به کلاینت برسد.

## آزمون

دو سرویس/دو حساب؛ import+send واقعی از دید fake backend در HTTP pipeline، نه mock سطح endpoint. count resolve/import/send برای replay، retry، race و uncertain assert شود. failure پیش از import، پس از import، پیش/پس از send_started و پیش از receipt؛ restart همان DB؛ expiry در صف؛ reservation دیگری/شمارهٔ mismatched؛ عدم overwrite contact موجود؛ peer Bale و Eitaa درست. دادهٔ حساس در exception/log/DB عمومی صفر. status سرویس دیگر هیچ اطلاعاتی ندهد.

## پذیرش

P4-A01: شمارهٔ تازه با نام درست به peer همان حساب نگاشت و ارسال stage-aware می‌شود.

P4-A02: idempotency، crash، uncertain، expiry و عدم ارسال دوباره مستقلاً PASS.

P4-A03: اثر نیمه‌تمام خارجی در receipt صادقانه ثبت می‌شود؛ ادعای rollback یا exactly-once خارجی وجود ندارد.

P4-A04: policy، scopes، status، privacy و گزارش/دروازه‌ها تکمیل‌اند.

خروجی: docs/reports/features/WEB_CLIENT_PHASE_04_REPORT.md و handoff متناظر. آزمون fake تماس واقعی ایجاد نمی‌کند؛ آزمون Live mutation مجوز همان لحظه لازم دارد.

# گزارش مستقل Phase 8-A: Account-scoped Data Repositories

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: تکمیل‌شده و آزموده‌شده  
مرز گزارش: پایان 8-A؛ مرحلهٔ 8-B در این گزارش لحاظ نشده است.

## نتیجهٔ اجرایی

دامنهٔ canonical داده با زوج `Provider + MessengerAccount` ایجاد و به Runtime، Facade و Repositoryهای Bridge منتقل شد. مسیر Legacy به‌صورت صریح و سازگار حفظ شد، اما Runtime چندنشستی دیگر برای داده‌های مشتق از Provider به کلیدهای عمومی Peer/Message/Sender/Job تکیه نمی‌کند.

موارد تکمیل‌شده:

- Dialog catalog: دامنهٔ حساب در قالب نسخهٔ ۳ ثبت می‌شود، فایل متعلق به حساب دیگر Fail-closed رد می‌شود و قالب Legacy نسخهٔ ۲ بدون شکست حفظ شده است.
- Sender directory: کلید اصلی SQLite به `(provider, messenger_account_id, user_id)` ارتقا یافت؛ مهاجرت نسخهٔ قدیمی دارای Backup است.
- Content Index: Site، Source و Job داخلی با دامنهٔ حساب کلیدگذاری و schema از ۲ به ۳ با Backup، ثبت Scope و `foreign_key_check` مهاجرت شد.
- Composition: کلید ذخیره‌سازی شامل `Provider + MessengerAccount + AppUser + Site + Composition` است و مهاجرت خواندنی schema 1 حفظ شد.
- Runtime/Fascade: دامنهٔ صریح حساب و AppUser آغازکننده به Repositoryهای مرتبط منتقل می‌شود.
- Read receipt، avatar/contact cache و Content-index active-job: کلیدهای درون‌فرایند دامنه‌دار شدند.
- Media cache: URL دیگر شناسهٔ حساب ندارد؛ Token مبهم به Context حساب سمت سرور متصل و هنگام resolve دوباره با Scope تطبیق داده می‌شود.
- API v1: وجود `messenger_account_id` یا `account_id` در Body/Query، حتی به‌صورت تو‌در‌تو، پیش از عملیات رد می‌شود. انتخاب حساب فقط از Context احرازشدهٔ سمت سرور می‌آید.
- WordPress: Metadata غیرمحرمانهٔ Site در `AppIntegration` مشترک Coordinator reconcile می‌شود؛ همهٔ AppUserهای فعال حق استفاده و فقط admin حق مدیریت دارد. URL و Credential وارد مدل/جدول AppIntegration یا audit metadata نمی‌شوند.

## ممیزی Repositoryها

| بخش | دامنهٔ مؤثر | نتیجه |
|---|---|---|
| Dialog/Message reference | Provider + MessengerAccount + Peer/Message | ایزوله |
| Sender | Provider + MessengerAccount + User ID | ایزوله |
| Content Index | Provider + MessengerAccount + Site/Source/Job | ایزوله |
| Composition/WordPress source | Provider + MessengerAccount + AppUser | ایزوله |
| Read receipt | Provider + MessengerAccount + Peer | ایزوله |
| Media | Token مبهم + Account scope سمت سرور | ایزوله |
| Runtime cache | Provider + MessengerAccount + Namespace | ایزوله |
| WordPress installation | AppIntegration مشترک، مدیریت admin | مطابق قرارداد |

## آزمون‌های مستقل 8-A

فایل آزمون جدید: `tests/test_phase8a_account_scoped_data.py`

سناریوهای افزوده‌شده:

- اعتبار UUID canonical و رد key متعلق به Scope دیگر؛
- برخورد عمدی Peer ID و Sender User ID یکسان در دو حساب؛
- برخورد Site/Peer/Message/Job یکسان در یک SQLite مشترک Content Index؛
- برخورد Composition key یکسان میان دو حساب و دو AppUser؛
- استفادهٔ مشترک WordPress توسط admin و user فعال، رد مدیریت user و رد کاربر disabled؛
- اثبات نبود URL/Password در Metadata ذخیره‌شدهٔ AppIntegration؛
- کشف بازگشتی شناسهٔ حساب جعلی در Body/Query؛
- به‌روزرسانی آزمون Media قدیمی برای قرارداد جدید Token-only و رد Query حساب.

نتایج:

- آزمون هدف اولیه یک اشکال مهاجرت Dialog را پیدا کرد: lookup رکورد قبلی پیش از اعمال storage key انجام می‌شد. اصلاح و آزمون تکرار شد.
- آزمون هدف دوم محدودیت provider جدول audit را آشکار کرد؛ رخداد AppIntegration با `provider=NULL` و نوع هدف صریح ثبت شد.
- مجموعهٔ هدف نهایی: ۵۱ آزمون موفق.
- کل مجموعه: ۴۴۵ آزمون موفق، بدون failure.
- Compile کل `src`: موفق.

فرمان QA نهایی:

```text
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-phase8a-full2
```

## کنترل ایمنی و دادهٔ واقعی

- هیچ Login، Logout، OTP، Sync، Send یا اتصال واقعی WordPress/Eitaa اجرا نشد.
- هیچ Port، Firewall، Service یا Router تغییر نکرد.
- `bridge.json` واقعی نوشته نشد؛ SHA-256 پس از پایان 8-A همچنان `D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89` و اندازه ۹۳۴ بایت است.
- هیچ reset، checkout، stage، commit یا push انجام نشد و تغییرات قبلی Worktree حفظ شدند.

## مرز مرحلهٔ بعد

8-B باید Jobهای پایدار Coordinator، Owner/Account، Lease/Attempt/Cancellation، idempotency، جلوگیری از عملیات تکراری گیرنده/درخواست و recovery پس از crash/restart با حالت `uncertain` را پیاده و مستقلاً گزارش کند.

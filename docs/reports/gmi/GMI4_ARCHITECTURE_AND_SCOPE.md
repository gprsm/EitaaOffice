# GMI4 — معماری و دامنه

نسخه: `Eitaa Bridge MVP 6.1.1 GMI4 – Contact Sources & Safe Audience Handoff`

## دامنهٔ اجراشده

1. ورود اعضای منتخب یا کل Snapshot یک گروه/کانال به دفترچهٔ محلی.
2. ورود رکوردهای Resolve‌شدهٔ فهرست‌های شماره از Core SQLite به دفترچه.
3. تشخیص تکراری بر پایهٔ شمارهٔ نرمال‌شده و `Eitaa User ID`.
4. ادغام افزایشی دسته‌ها همراه با حفظ `Opt-out` و وضعیت غیرقابل‌ارسال اپراتور.
5. Progress، Cancel و گزارش شمارشی برای هر دو Import محلی.
6. انتقال نتیجهٔ پالایش‌شدهٔ Target Builder به فرم موجود ارسال شماره‌ای.

## مرز اعتماد

UI فقط شناسهٔ اعضای انتخاب‌شده یا شناسهٔ فهرست شماره را ارسال می‌کند. Backend دادهٔ عضو/Resolve را دوباره از API عمومی و محلی Core می‌خواند. شمارهٔ کامل فقط در پایگاه محلی مقصد نوشته می‌شود و `Access Hash` نه در پاسخ API و نه در UI نمایش داده نمی‌شود.

## مسیر اجرا

`UI selection → validated local API → Core SQLite read → transactional contact upsert`

این مسیر Scheduler ایتا را فراخوانی نمی‌کند. هیچ Resolve، دریافت عضو یا RPC دیگری در Import محلی انجام نمی‌شود.

`Target Builder → unique/allowed phones → prefilled bulk form → Core resolve → preview → explicit confirmation`

مرحلهٔ انتقال به‌تنهایی Job ارسال ایجاد نمی‌کند.

## خارج از دامنه

- Worker چندحسابی واقعی، اشتراک Session/Token یا توزیع بین DCها.
- هر سازوکار دورزدن Rate Limit یا محدودیت حساب.
- تغییر Core، Scheduler، Runtime، WordPress یا Scroll. در Installer فقط ارجاع ضروری Wheel از `dev27` به `dev29` اصلاح شده است.
- بازطراحی ارسال انبوه موجود.

آزمایش چندحسابی GMI3 همچنان فقط یک Lab آفلاین است و به Runtime متصل نشده است.

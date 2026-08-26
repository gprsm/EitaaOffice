# گزارش کارت Material پیام و بازیابی خودکار نشست — ۲۰۲۶-۰۸-۲۰

نتیجه: `IMPLEMENTED / AUTOMATED_VERIFIED / NOT_LIVE_PROVIDER`  
دامنه: محتوای گفتگو، نام نویسنده/Contact، صفحهٔ ورود و lifecycle نشست نامعتبر  
اثر Provider واقعی: `NONE`

## نتیجهٔ محصول

1. هر پیام کانال، گروه و چت شخصی اکنون یک Card مستقل Material با Header نویسنده، Avatar، رسانه، محتوا و Actionهاست.
2. نام Contact برای نویسنده اولویت دارد؛ اگر نام ذخیره‌شده فقط `Eitaa` یا `ایتا` باشد، نام واقعی عضو/تاریخچه جای آن نمایش داده می‌شود.
3. متن‌های بلند با `Collapse` باز و بسته می‌شوند. گالری، فایل، انتخاب پیام، اصلاح ایندکس، شناسه و وضعیت استفاده در WordPress حفظ شده‌اند.
4. component پیام از `App.tsx` خارج و به `ui/src/MessageContentCard.tsx` منتقل شد؛ implementation قدیمی حذف شد.
5. panel معرفی و متن معماری از Login Surface حذف و فرم Material با عرض محدود در مرکز صفحه قرار گرفت؛ breakpoint موبایل عرض کامل امن دارد.
6. نشست قطعی نامعتبر بدون نمایش جزئیات فایل/backup بازیابی می‌شود و درخواست کد ورود خودکار آغاز می‌گردد. کاربر فقط OTP یا رمز دوم الزامی Provider را وارد می‌کند.

## مرز ایمنی بازیابی

- Backend حالت `automatic_recovery=true` را فقط برای state پایدار `invalid` می‌پذیرد.
- یک آزمون adversarial تأیید می‌کند نشست `authenticated` با درخواست automatic archive نمی‌شود، فایل فعال باقی می‌ماند و پاسخ امن 400 دارد.
- Session نامعتبر حذف نمی‌شود؛ backup یکتا با پسوند `.bak` باقی می‌ماند، اما نام آن در پاسخ automatic افشا نمی‌شود.
- Audit reason موفق `automatic_invalid_session_recovery` و reason رد `automatic_recovery_state_mismatch` است؛ شماره، OTP، Cookie، Token، متن پیام یا نام فایل خصوصی ثبت نمی‌شود.
- reset محلی logout راه‌دور نیست و OTP/2FA را دور نمی‌زند. بازیابی DPAPI، migration عملیاتی و Credential همچنان خارج از این خودکارسازی‌اند.

## نام نویسنده

Enrichment بدون RPC اضافه و از دادهٔ محلی انجام می‌شود:

1. نمایهٔ تاریخچه یا snapshot عضو گفتگو؛
2. Contact محلی/ایتا به‌عنوان نام ترجیحی؛
3. استثنای عنوان عمومی `Eitaa/ایتا` که نام واقعی مرحلهٔ اول را حفظ می‌کند؛
4. username و fallback امن UI در صورت نبود نام.

فیلدهای `sender_display_name`، `sender_username`، `sender_is_eitaa_contact` و `sender_resolution` قرارداد موجود API را حفظ می‌کنند.

## شواهد آزمون

| دامنه | نتیجه |
|---|---:|
| Red contracts اولیه | `5/5` شکست مورد انتظار؛ نام عمومی Contact، تأیید دستی، panel ورود و component مفقود آشکار شدند |
| Targeted Python | `24/24` |
| Scroll contract اصلاح‌شده برای module جدید | `1/1` |
| Full Backend/Python | `573/573` |
| Scroll model | `10/10` |
| Grouped media | `16/16` |
| Phase 9 workspace + acceptance | `22/22` |
| Phase 10 local activation | `7/7` |
| Phase 11 onboarding + B2 | `13/13` |
| مجموع assertionهای شماره‌دار UI | `68/68` |
| Mobile auth/live و Observability | موفق |
| TypeScript check | موفق |
| Production build | موفق؛ `1008` module |
| Main bundle | `787.69 kB`، gzip `241.44 kB` |
| Runtime log privacy scan | ۹۱۲۹ رکورد، `invalid_json=0`، `finding=0` |

هشدار bundle بالاتر از 500 kB همچنان در F-013 باز و غیرمسدودکننده است. استخراج کارت پیام مرز ماژولی را بهتر کرد، ولی chunk اصلی هنوز composer/controllerهای سنگین دارد.

## Failure و تحلیل اصلاحی

1. اجرای red مطابق انتظار پنج شکست داشت و script موبایل نبودن `MessageContentCard.tsx` را گزارش کرد؛ سپس implementation نوشته شد.
2. نخستین اجرای هدفمند نام یک test را اشتباه صدا زد و شاهد نساخت. اجرای بعدی بدون basetemp به temp سراسری Windows دسترسی نداشت و هم‌زمان assertion نام helper را پیدا نکرد؛ basetemp به workspace منتقل و نام helper با قرارداد هماهنگ شد.
3. patch تجمیعی اولیهٔ Backend/UI به‌علت context متفاوت اتمیک رد شد؛ patchهای کوچک‌تر فایل‌محور اعمال شدند. patch تجمیعی نخست مستندات نیز به‌علت context Baseline رد و بدون mutation با patchهای جدا جایگزین شد.
4. full suite پس از ماژول‌بندی یک شکست ایستای واقعی داشت: آزمون scroll هنوز media layout را در `App.tsx` جست‌وجو می‌کرد. assertion به `MessageContentCard.tsx` منتقل و full نهایی سبز شد؛ رفتار layout تغییر نکرد.
5. production build موفق شد ولی warning اندازهٔ chunk اصلی را تکرار کرد. این warning خطای build نیست و به F-013 متصل ماند.
6. Git read-only نخست به‌علت safe-directory sandbox رد شد؛ هیچ Git config یا mutation انجام نشد و بررسی نهایی با گزینهٔ موقت read-only انجام می‌شود.

## محدودیت پذیرش دیداری

F-025 همچنان باز است. اجرای UI زنده می‌توانست status نشست و Provider probe را فعال کند؛ برای رعایت ممنوعیت Login/OTP/Provider network بدون تأیید همان لحظه، در این نوبت Browser live اجرا نشد. شواهد جاری `STATIC / UNIT / CONTRACT / ADVERSARIAL / BUILD` هستند.

## اثر بیرونی

- هیچ Login، OTP، Provider network، Send/Invite یا WordPress واقعی انجام نشد.
- Session واقعی، `data/`، `runtime/`، `diagnostics/` و `backups/` نوشته، جابه‌جا یا حذف نشدند؛ scanner لاگ فقط‌خواندنی بود.
- هیچ migration/rollback عملیاتی، restart، process termination یا تغییر Firewall/Proxy/Port/Certificate انجام نشد.
- worktree عمداً dirty حفظ شد و reset/checkout/clean/stage/commit/push انجام نشد.

## Trigger ابطال

تغییر در `MessageContentCard.tsx`، sender enrichment، Contact source priority، Auth state machine، reset route، challenge binding، Login surface یا Material/mobile contract نیازمند تکرار این پذیرش است.

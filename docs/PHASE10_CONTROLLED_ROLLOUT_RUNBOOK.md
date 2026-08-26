# راهنمای Rollout کنترل‌شدهٔ Phase 10

این راهنما برای اجرای حضوری و مرحله‌ای روی نصب واقعی است. عبور خودکار از هیچ دروازه‌ای مجاز نیست.

## اصل ایمنی

- در هر مرحله ابتدا hash و شمارش مبنا ثبت شود.
- هر عملیات نوشتنی فقط با برنامهٔ متوقف و backup تأییدشده انجام شود.
- Feature Flag بعد از پذیرش مرحلهٔ قبل فعال شود، نه پیش از آن.
- فایل legacy حذف نشود؛ خروج اضطراری باید بازگشت‌پذیر باشد.
- OTP، رمز، Session، Application Password و شمارهٔ کامل در گزارش یا Support bundle ثبت نشوند.
- هر ارسال واقعی—even تک‌پیام—تأیید مستقل می‌خواهد.

## Gate 10-A — Backup واقعی

شرایط ورود:

1. کاربر حضور دارد و توقف کنترل‌شدهٔ برنامه را تأیید می‌کند.
2. Backend، Electron و workerهای متعلق به نصب متوقف و Portها آزاد هستند.
3. `bridge.json` و پایگاه‌های اصلی hash و شمارش مبنا دارند.
4. فضای آزاد کافی است.

ترتیب:

1. backup دائمی Coordinator/Contacts/Session/Data ساخته شود.
2. آرشیو با `restore_runtime.py <backup.zip> --dry-run` verify شود.
3. Manifest hash و محل backup ثبت شود؛ محتوا یا secret چاپ نشود.
4. restore کامل ابتدا روی کپی جداگانه تمرین و hash اعضا مقایسه شود.
5. Contacts schema 1→2 روی کپی اجرا و ۵۷۴ مخاطب/۳ دسته و recovery backup کنترل شود.

شرط خروج: Backup واقعی verified و برنامه هنوز متوقف است. در غیر این صورت rollout متوقف می‌شود.

## Gate 10-B — فعال‌سازی محلی Loopback

1. AppUser auth فقط روی Loopback فعال شود.
2. خود کاربر مدیر اولیه و رمز را از UI محلی ایجاد کند؛ رمز در ترمینال/گزارش وارد نشود.
3. Contacts واقعی با backup verified مهاجرت و `quick_check`، ۵۷۴/۳ و Audit بررسی شود.
4. Multi-session فقط پس از پذیرش ورود، انقضا، logout و جداسازی حساب روشن شود.
5. در هر خطا Feature Flag خاموش و legacy دست‌نخورده نگه داشته شود.

## Gate 10-C — Pilot محدود LAN

این مرحله سنگین و دستی است:

1. IP ثابت سرور، هم‌شبکه‌بودن Ethernet/Wi-Fi و خاموش‌بودن Guest/AP isolation توسط کاربر کنترل شود.
2. Rule فایروال فقط برای Port مشخص، profile و subnet مورد تأیید کاربر ساخته شود.
3. دو AppUser و دو حساب واقعی با دادهٔ کم آزموده شوند.
4. WordPress مشترک بدون افشای credential به Client، با write فقط برای admin کنترل شود.
5. Login/expiry/logout حساب A نباید بر B اثر بگذارد.
6. موبایل، قطع شبکه، restart، Audit و عدم cross-account leak پذیرش شوند.
7. ارسال واقعی فقط با تأیید مستقل؛ ارسال انبوه ممنوع است.

### تصمیم جاری: محیط‌مستقل‌کردن Gate 10-C

سناریوی LAN بالا یک **پروفایل استقرار اختیاری** است و وضعیت شبکه، DHCP یا
Firewall رایانهٔ توسعه نباید اجرای کد، تست یا تکمیل بخش قابل‌حمل 10-C را متوقف
کند. پذیرش جاری 10-C به سه لایه تفکیک می‌شود:

1. `desktop_loopback`: توسعه و اجرای تک‌رایانه‌ای، بدون وابستگی به شبکهٔ میزبان.
2. `trusted_lan_http`: استقرار اختیاری شبکهٔ خصوصی با تنظیمات صریح همان محیط؛
   IP، Host، Origin، CIDR و Firewall در زمان استقرار تعیین می‌شوند، نه در کد.
3. `web_reverse_proxy`: backend فقط روی Loopback و HTTPS خارجی با TLS termination معتبر.
   HTTP روی 80 پیکربندی‌پذیر است، اما HTTP server داخلی اجرای ساده روی 443 را رد می‌کند.
   قرارداد Host/Origin، trusted proxy، forwarded proto/for پاک‌سازی‌شده، Secure cookie، CSRF،
   limits، health/readiness و shutdown در `docs/PHASE10_WEB_REVERSE_PROXY_DEPLOYMENT.md` است.

در نتیجه، اعمال Rule واقعی Firewall، تغییر Network Profile و رزرو DHCP از
معیارهای تکمیل توسعه حذف و به checklist استقرار هر میزبان منتقل می‌شوند.
WordPress نیز integration اختیاری است و فقط هنگام پذیرش واقعی آن باید Laragon
یا مقصد معادل در دسترس باشد.

Pilot دوکاربره برای اثبات عدم نشت بین دو AppUser و دو MessengerAccount است؛
برنامه برای استفادهٔ معمول به دو کاربر یا دو حساب نیاز ندارد. آزمون Fake و
خودکار بخشی از پذیرش کد است و Pilot واقعی می‌تواند تا محیط استقرار نهایی به
تعویق بیفتد.

### وضعیت پذیرش محیط‌مستقل در 2026-08-13

- C1: جداسازی سه پروفایل، Config-driven شدن Launcherها و حذف endpoint ثابت renderer پذیرفته شد؛
- C2: قرارداد `web_reverse_proxy` با fixture محلی Proxy و تست‌های adversarial پذیرفته شد؛
- C3: جداسازی دو کاربر/دو حساب با Fake/Contract/adversarial پذیرفته شد؛ Pilot واقعی deferred است؛
- C4: WordPress Fake/Contract پذیرفته شد؛ Laragon و هر write واقعی deferred هستند؛
- bind واقعی 80/443، نصب Proxy/certificate و Firewall همچنان عملیات deployment با مجوز جداگانه‌اند.

## Gate 10-D — پذیرش و Rollback

1. معیارهای Pilot و رخدادهای Audit مرور شوند.
2. Feature Flag rollback و restore روی کپی تکرار شود.
3. rollback واقعی فقط با حضور کاربر، توقف برنامه و backup جاری انجام شود.
4. Support bundle از نظر secret/PII scan شود.
5. Legacy فقط پس از دورهٔ تثبیت و یک تصمیم مستقل کنار گذاشته شود؛ حذف فوری مجاز نیست.

### وضعیت پذیرش 10-D در 2026-08-13

- backup واقعی Phase 10-A دوباره verify و روی کپی جدا restore شد؛ 4114 عضو با hash manifest تطبیق داشت؛
- feature toggle و rollback فقط روی همان کپی تمرین و hash اولیه بازیابی شد؛ کپی موقت حذف شد؛
- support bundle واقعی ساخته و با اسکنر fail-closed بررسی شد؛ finding برابر صفر بود؛
- health/readiness/drain/restart روی server fixture ایزوله و پورت تصادفی Loopback پذیرفته شد؛
- سرویس واقعی restart یا rollback نشد و پس از پذیرش همچنان alive/ready بود؛
- هیچ Legacy حذف و هیچ تنظیم بیرونی تغییر نکرد.

گزارش مستقل: `reports/phases/PHASE10D_OPERATIONAL_ACCEPTANCE_REPORT_2026-08-13.md`.

## توقف فوری

در موارد زیر هیچ مرحلهٔ بعدی آغاز نشود:

- hash یا شمارش غیرمنتظره؛
- WAL/Journal فعال در زمان خواندن immutable؛
- Backup verify ناموفق یا عضو تکراری/ناامن؛
- کمبود فضا؛
- runtime/worker ناشناخته یا فعال؛
- نیاز به OTP/رمز/تنظیم Firewall بدون حضور کاربر؛
- اختلاف ۵۷۴ مخاطب یا ۳ دسته؛
- نشت scope، Session یا credential؛
- quota، approval یا محدودیت اجرایی.

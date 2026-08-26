# Prompt for the next Codex task — Phase 10 continuation

بسم الله الرحمن الرحیم

مسیر پروژه:

`C:\Users\Mohsen\Documents\eitaa\Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send`

توسعه را از وضعیت واقعی موجود ادامه بده. ابتدا هیچ چیز را از نو نساز و هیچ
فرضی دربارهٔ کامل‌بودن Phase 10 نکن. پیش از تغییر کد این فایل‌ها را کامل بخوان:

1. `../reports/phases/PHASE10_DEPLOYMENT_PORTABILITY_DECISION_2026-08-13.md`
2. `../reports/phases/PHASE10B_ACCOUNT_BOUNDARY_AND_LAYOUT_RECOVERY_REPORT_2026-08-13.md`
3. `../reports/phases/PHASE10B_CHALLENGE_ID_RECOVERY_REPORT_2026-08-13.md`
4. `../reports/phases/PHASE10B_PROVIDER_NETWORK_RECOVERY_REPORT_2026-08-13.md`
5. `../reports/phases/PHASE10A_REAL_BACKUP_PREFLIGHT_REPORT_2026-08-13.md`
6. `../reports/phases/PHASE10_RESUMPTION_STATUS_2026-08-13.md`
7. `docs/PHASE10_CONTROLLED_ROLLOUT_RUNBOOK.md`
8. `../reports/architecture/HTTP_LAN_MULTIUSER_CONTINUATION_REPORT_2026-08-02.md`، با توجه به اینکه
   الحاقیهٔ ۲۰۲۶-۰۸-۱۳ بر فرض قدیمیِ وابستگی به LAN همین رایانه اولویت دارد.

## وضعیت قطعی فعلی

- Phase 10-A کامل و پذیرفته شده است.
- Backup واقعی معتبر:
  `backups/phase10-rollout/eitaa-bridge-backup-20260813-161104-845868.zip`
- SHA-256:
  `9688ECE0F77B348D2DA0D245AADE70198727B6D08955D0F1D1159226FD31D124`
- ورود واقعی ایتا موفق بوده و Coordinator وضعیت `authenticated` با
  `session_generation=4` دارد؛ OTP/رمز/Token را نخوان و چاپ نکن.
- DPAPI identity، درخواست شبکه، challenge_id کد/رمز دوم، مسیرهای مهاجرتی
  peer_file و چیدمان Grid اصلاح شده‌اند.
- کاتالوگ زنده پس از ترمیم: 427 مسیر داخل حساب، 0 مسیر خارج حساب.
- آخرین تست مرتبط: 65 تست Python، 11/11 workspace UI، 10/10 acceptance UI و
  7/7 Phase 10 activation موفق؛ TypeScript و build تولیدی نیز موفق بوده‌اند.
- آخرین بررسی نشان داد سرویس 127.0.0.1:8765 در حال اجرا نیست، اما داده و Session
  ایتا محفوظ است.
- Worktree عمداً بسیار dirty و دارای تغییرات کاربر/فازهای قبل است. هیچ reset،
  checkout، clean، stage، commit یا push انجام نده.

## کار نخست: بستن دقیق 10-B

1. دسترسی نوشتن، Git status فقط‌خواندنی، listener پورت 8765 و فایل‌های واقعی را
   بررسی کن؛ تغییرات موجود را حفظ کن.
2. سرویس را از `src` و نه نسخهٔ نصب‌شدهٔ قدیمی اجرا کن. برای دسترسی Provider در
   صورت نیاز اجرای شبکهٔ مجاز بگیر. فرمان قبلی مؤثر از این الگو استفاده می‌کرد:
   `.venv\Scripts\python.exe -c "import sys;sys.path.insert(0,r'src'); ..."`
3. Health و readiness را وریفای کن.
4. از کاربر بخواه فقط با Credential خصوصی AppUser در UI وارد شود. هیچ رمز، OTP،
   Cookie یا Token را درخواست، مشاهده یا ثبت نکن.
5. رابط واقعی را در اندازهٔ فعلی و مرزهای 1280/1600 و در صورت امکان موبایل
   بررسی کن: rail، conversation list و content باید یک ردیف کامل داشته باشند؛
   WordPress زیر 1500 drawer باشد؛ خطای peer boundary نباید برگردد.
6. نشست AppUser را فقط از metadata امن و بدون Cookie/Token وریفای کن.
7. مجموعه تست متناسب را دوباره اجرا و گزارش مستقل
   `../reports/phases/PHASE10B_LOCAL_ACTIVATION_REPORT_2026-08-13.md` را تکمیل کن. اگر نقصی دیدی،
   اصلاح، تست و گزارش کن.

## کار دوم: اجرای Phase 10-C با تعریف محیط‌مستقل

Public/DHCP/Firewall رایانهٔ توسعه blocker نیستند. شرایط این ماشین را در کد
hard-code نکن و هیچ تغییر واقعی Firewall/Router/Network Profile انجام نده.

10-C را به‌ترتیب و با گزارش مستقل انجام بده:

### 10-C1 — Deployment abstraction audit

- Config، launcher، HTTP server، Host/Origin/CIDR، cookie و docs را ممیزی کن.
- ثابت کن Loopback و LAN اختیاری از محیط جدا هستند.
- هر hard-code مربوط به IP/port/path/host را که مانع انتقال به سیستم دیگر است
  اصلاح کن.

### 10-C2 — Web 80/443 contract

- Port 80 باید از Config قابل استفاده باشد؛ نیاز مجوز سیستم را فقط مستند کن.
- Port 443 را HTTP ساده تلقی نکن. نسخهٔ فعلی TLS داخلی ندارد.
- یک قرارداد امن reverse proxy/TLS termination یا پروفایل HTTPS روشن طراحی و
  پیاده/مستند/تست کن: trusted proxy allowlist، Host/Origin، forwarded proto،
  Secure cookie، CSRF، body/time limits، health/readiness و shutdown.
- تا حد امکان با تست خودکار و reverse-proxy fixture محلی روی پورت‌های غیرحساس
  و copy config وریفای کن؛ bind واقعی 80/443 یا نصب proxy نیازمند مجوز جداست.

### 10-C3 — Multi-user isolation acceptance

- «دوکاربر/دوحساب» شرط استفادهٔ عادی نیست؛ آزمون اثبات جداسازی است.
- تست‌های Fake/Contract برای دو AppUser و دو MessengerAccount را کامل و
  adversarial اجرا کن: login/expiry/logout/job/data/audit A روی B اثر نگذارد.
- Pilot واقعی حساب دوم را تا محیط استقرار نهایی defer کن، مگر کاربر صریحاً
  آمادگی مالک حساب دوم را اعلام کند. Credential خصوصی فقط در UI وارد شود.

### 10-C4 — WordPress optional integration

- WordPress/Laragon blocker هسته نیست.
- تست Fake/Contract و عدم افشای credential را کامل کن.
- فقط هنگامی که برای پذیرش واقعی REST/draft/upload لازم شد، دقیقاً از کاربر
  بخواه Laragon را اجرا کند؛ بدون تأیید لحظه‌ای publish یا mutation واقعی نکن.

برای هر C1 تا C4 تست و گزارش مستقل `PHASE10C*.md` بنویس و در پایان گزارش نهایی
Phase 10-C را ایجاد کن.

## کار سوم: Phase 10-D

فقط پس از قبولی کامل بخش قابل‌حمل 10-C:

- rollback/restore را ابتدا روی کپی اجرا کن؛
- support bundle و logها را از نظر secret/PII اسکن کن؛
- health/readiness/restart/backup runbook را وریفای کن؛
- محدودیت‌های deferred واقعی (Pilot دوحساب، WordPress واقعی، bind واقعی 80/443)
  را صریح و جدا از کیفیت کد ثبت کن؛
- هیچ rollback واقعی، توقف گسترده، حذف Legacy یا mutation بیرونی بدون تأیید
  لحظه‌ای انجام نده؛
- گزارش مستقل 10-D و گزارش نهایی Phase 10 را بنویس.

## قواعد ایمنی و کیفیت

- تمام تغییرات با تست متناسب، تست بازگشتی، build و گزارش مستقل همراه باشد.
- فایل `bridge.json` واقعی و worktree dirty حفظ شوند.
- Secret، OTP، رمز، Session، Cookie، Application Password، Token و شمارهٔ کامل
  در خروجی یا گزارش نیاید.
- ارسال واقعی ایتا و انتشار واقعی WordPress ممنوع است مگر با تأیید همان لحظه.
- اگر blocker واقعی، quota، approval یا نیاز اجتناب‌ناپذیر به همکاری کاربر رخ داد،
  گزارش جامع محلی بنویس و دقیقاً متوقف شو.
- Phase 11 را پیش از گزارش نهایی و پذیرش کامل Phase 10 شروع نکن.

ابتدا یک گزارش کوتاه از وضعیت کشف‌شده بده، سپس کار را از بستن 10-B ادامه بده.

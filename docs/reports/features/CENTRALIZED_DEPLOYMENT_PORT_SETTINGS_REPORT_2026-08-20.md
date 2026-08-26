# گزارش فاز ۱ — تنظیم متمرکز پورت داخلی

تاریخ: ۲۰۲۶-۰۸-۲۰  
وضعیت: `COMPLETED / FULL_AUTOMATED_VERIFIED / LIVE_CONFIG_UNCHANGED`

## نتیجه

صفحهٔ تنظیمات اکنون بخش Material UI «شبکه و وب» دارد و پورت داخلی Backend فقط از همان محل مدیریت می‌شود. تغییر، Host/Originهای داخلی را خودکار همگام و config را پس از اعتبارسنجی کامل، backup و replace اتمیک ذخیره می‌کند. اعمال پورت به اجرای مجدد نیاز دارد و هیچ restart یا bind عملیاتی در این فاز انجام نشد.

## قرارداد ایمنی

- GET سراسری: `/api/v2/settings/deployment`؛ مستقل از MessengerAccount و قابل مشاهده برای AppUser واردشده؛
- mutation: `/api/v2/settings/deployment/port`؛ فقط مدیر، CSRF معتبر و `confirm=true`؛
- رد fail-closed مقدار غیرinteger، خارج از ۱..۶۵۵۳۵ و پورت ۴۴۳ برای HTTP ساده؛
- همگام‌سازی پورت در allowed Host/Origin برای desktop/LAN؛
- حفظ کامل Host/Origin عمومی HTTPS برای Reverse Proxy و اعلام `proxy_update_required`؛
- بازگرداندن `restart_required=true` بدون راه‌اندازی مجدد خودکار؛
- رخدادهای `deployment_port_update_succeeded`، `deployment_port_update_rejected` و `deployment_port_update_failed` با audit، correlation و metadata امن.

## Test-first و شکست‌ها

1. اجرای RED با ImportError مورد انتظار شکست خورد، چون `DeploymentPortSettings` هنوز وجود نداشت.
2. اجرای پس از افزودن سرویس به‌علت `WinError 5` در Temp سراسری ویندوز به setup نرسید؛ basetemp تازه و دقیقاً محدود به workspace انتخاب شد و `6/6` سبز شد. این تغییر workaround محصول نبود.
3. تست کاربر عادی ابتدا نشان داد مسیر v1 تنظیم سراسری به gate فضای کاری MessengerAccount برخورد می‌کند. مسیر به v2 سراسری منتقل شد؛ مشاهده برای user و mutation فقط admin پذیرفته شد.
4. assertion نخست correlation نام پارامتر داخلی `request_id` را به public dispatch می‌داد؛ public contract واقعی `correlation_id` است و تست به قرارداد canonical اصلاح شد.
5. بازبینی نهایی نشان داد PermissionError ساخت backup می‌تواند خام بالا بیاید. آزمون RED آن را بازتولید کرد؛ اکنون خطای امن `deployment_settings_backup_failed`، رخداد failure اختصاصی و تضمین عدم تغییر فایل اصلی پذیرفته شده‌اند.

## Validation

| دامنه | نتیجه |
|---|---|
| سرویس پورت + API admin/user + Material contract | `9/9` |
| Python کامل | `588/588` |
| UI Scroll | `10/10` |
| UI Grouped media | `16/16` |
| Phase 9 workspace + acceptance | `24/24` |
| Phase 10 | `7/7` |
| Phase 11 onboarding + B2 | `13/13` |
| مجموع assertionهای شماره‌دار UI | `70/70` |
| TypeScript | موفق |
| Observability | موفق |
| Mobile auth/live | موفق |
| Production build | موفق؛ 1009 module، Settings chunk=`30.62 kB`، main=`788.97 kB` و gzip=`241.76 kB` |

warning chunk بالاتر از 500 kB همان F-013 باز و مستقل از این فاز است؛ build exit code صفر داشت.

## دامنهٔ بیرونی

- `bridge.json` و `.env` واقعی، Session، `data/`، `runtime/` عملیاتی، diagnostics و backups واقعی تغییر نکردند.
- Backend واقعی restart نشد و هیچ پورت، Firewall، Laragon/Proxy یا Certificate تغییر نکرد.
- Provider network، Login/OTP/Credential، ارسال/دعوت و WordPress اجرا نشد.
- migration/rollback، حذف داده و Git mutation انجام نشد؛ worktree dirty موجود حفظ شد.

## ادامه

فاز ۲ نقشه‌راه به ناوبری موبایل محدود است: نمایش فهرست نوع گفت‌وگو با bottom navigation، بازگشت از گفت‌وگو به فهرست، حذف متن «همگام‌سازی زنده»، جانمایی دو سوی Header و برجسته‌کردن منتخب میانی. جست‌وجو/وردپرس، فیلتر/ایندکس/تاریخ و گروه‌بندی پیام در فازهای بعدی جدا باقی می‌مانند.

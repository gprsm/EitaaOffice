# گزارش ریزفاز ۲.۱ — ناوبری فهرست‌محور موبایل

تاریخ: ۲۰۲۶-۰۸-۲۰  
وضعیت: `COMPLETED / FULL_AUTOMATED_VERIFIED`

Bottom Navigation اکنون فهرست همان نوع گفتگو را باز می‌کند؛ انتخاب گفتگو آن را می‌بندد و Arrow بازگشت RTL در Header دوباره فهرست را نمایش می‌دهد. فهرست در ورود اولیهٔ موبایل نیز باز است و همهٔ کنترل‌ها Material UI هستند.

## Validation

- RED نبود `showDialogSection` ثبت شد؛ targeted و TypeScript سبز؛
- UI شماره‌دار=`70/70` و mobile-auth-live/observability موفق؛
- Python کامل=`589/589`؛
- build موفق: 1010 module، main=`789.37 kB`، gzip=`241.91 kB`؛ warning شناخته‌شدهٔ F-013 باقی است.

هیچ Provider/Login/OTP/Send/WordPress یا Config/Session/Port عملیاتی استفاده یا تغییر نکرد. ریزفازهای ۲.۲ و ۲.۳ عمداً pending ماندند.

# گزارش استقرار Production شاخه Bale

تاریخ: 2026-09-26  
وضعیت: `DEPLOYED / LIVE_VALIDATED / ADMIN_LOGIN_VERIFIED`

## نتیجه

نسخه شاخه `Bale` (کامیت `5ed7fa75` به‌علاوه برچسب نسخهٔ این گزارش) با خط مشترک
`publish-site` روی `eitaa.farhangimaz.ir` منتشر شد. سرویس `eitaa-bridge.service`
فعال است، readiness و دروازهٔ پاسخ وضعیت AppUser از gateway هم‌میزبان سبز است و
UI عمومی با باندل تازه سرو می‌شود.

## فرایند انتشار

1. بیلد UI (tsc + Vite) روی ماشین توسعه؛ باندل `index-DL8KbFBD.js`.
2. ساخت آرتیفکت فقط از فایل‌های ردیابی‌شده گیت به‌علاوه `ui/dist`؛ ۷۰۶ فایل،
   ۳٫۲MB. اسکن حریم خصوصی: بدون `bridge.json`، `.env`، نشست، پایگاه داده یا لاگ.
3. آپلود به `/srv/deploy-inbox/eitaa-bridge`، تأیید SHA-256 و اجرای
   `sudo publish-site deploy eitaa-bridge`.
4. gate انتشار: نصب venv، تغییر اتمیک symlink، restart و بررسی readiness و
   پاسخ بدون credential وضعیت AppUser؛ مسیر rollback فعال ولی استفاده‌نشده.

## شواهد

- `publish-site status`: release `20260926T095752Z-831592d7dfb5` فعال و ready؛
- سرویس active؛ journal بدون error/traceback؛
- عمومی: HTTP ‏301 به HTTPS، صفحهٔ اصلی 200، هش باندل سرو‌شده برابر بیلد محلی؛
- ورود ادمین: `POST /api/v2/app-auth/login` با کاربر `akhoondian` پاسخ
  `200 authenticated=true` با نقش `admin` و دسترسی `manage_users` داد؛
- `GET /api/v2/app-auth/status`: ‏`ok=true, enabled=true, authenticated=false` —
  مرز بدون نشست حفظ شده است.

## کاربران ادمین

دو کاربر admin فعال در coordinator موجود است؛ کاربر `akhoondian` با رمز منتخب
مدیر سامانه تأیید شد و حساب دومی (`آخوندیان`، ساختهٔ 2026-09-24) بدون تغییر
ماند. هیچ رمزی در این گزارش، مخزن یا خروجی ابزار ثبت نشد.

## یادداشت

- هیچ OTP، ارسال پیام‌رسان یا تماس Provider در این پذیرش انجام نشد.
- `VERSION.txt` و `RELEASE_MANIFEST.json` در همین کامیت به مرحلهٔ `bale1`
  به‌روزرسانی شدند؛ شماره بسته `0.7.0.dev31` و wheel هسته تغییر نکرد.

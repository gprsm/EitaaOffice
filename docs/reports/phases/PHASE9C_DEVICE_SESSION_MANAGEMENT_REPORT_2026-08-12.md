# گزارش مستقل Phase 9-C — مدیریت نشست‌های دستگاه‌ها

تاریخ: ۲۰۲۶-۰۸-۱۲  
وضعیت: **تکمیل‌شده و آزموده‌شده**  
مرز گزارش: پایان 9-C؛ پذیرش دیداری و هم‌زمانی نهایی مربوط به 9-D است.

## نتیجهٔ اجرایی

- هر AppUser می‌تواند حداکثر ۵۰ نشست اخیر خودش را ببیند.
- DTO نشست فقط شامل شناسهٔ غیرتوکنی Session، نوع/برچسب Client، زمان ایجاد، آخرین فعالیت، انقضای idle/absolute، وضعیت و دلیل امن است.
- Token، Token hash، CSRF، IP، IP fingerprint، نام کاربری و Credential در خروجی وجود ندارند.
- نشست جاری به‌صورت صریح مشخص می‌شود.
- وضعیت مؤثر `expired` حتی پیش از پاک‌سازی دوره‌ای محاسبه می‌شود؛ نشست منقضی «فعال» نمایش داده نمی‌شود.
- هشدار `recent_login` برای نشست فعال دیگری در پانزده دقیقهٔ اخیر و `expires_soon` برای کمتر از ده دقیقه تا انقضا افزوده شد.
- خروج از یک نشست فقط با تطبیق `session_id + app_user_id` انجام می‌شود؛ شناسهٔ نشست کاربر دیگر عمداً همان پاسخ «در دسترس نیست» را می‌گیرد.
- لغو نشست جاری Cookie را منقضی، CSRF سمت UI را پاک و Gate ورود را تازه می‌کند.
- خروج از همهٔ دستگاه‌ها با endpoint موجود `logout-all` در UI ارائه شد.
- Admin همچنان می‌تواند از پنل 9-A همهٔ نشست‌های یک کاربر را لغو کند، بدون دیدن metadata محرمانه.
- لغو تک‌نشست در Audit با Client kind و Session ID غیرتوکنی ثبت می‌شود.

## API

```text
GET  /api/v2/app-auth/sessions
POST /api/v2/app-auth/sessions/{session_id}/revoke
POST /api/v2/app-auth/logout-all
```

## آزمون مستقل

فایل: `tests/test_phase9c_device_sessions.py`

سه سناریو:

1. دو Device برای یک AppUser، تشخیص نشست جاری/recent login، اثبات نبود Token/IP، لغو Device دیگر و رد cross-user؛
2. پیشروی Clock و نمایش مؤثر Expired بدون افشای Secret؛
3. مسیر API لغو نشست جاری، `session_invalid` و Cookie با `Max-Age=0`.

نتایج:

- آزمون مستقل 9-C: **۳/۳ موفق**.
- مجموعهٔ مرتبط AppUser Auth/API/9-A/9-C: **۱۶/۱۶ موفق**.
- TypeScript check: موفق.
- کل مجموعهٔ Python پس از 9-C: **۴۷۴/۴۷۴ موفق**.

## فایل‌های اصلی تغییرکرده

- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `ui/src/SessionManagementPanel.tsx`
- `ui/src/AppUserManagementPanel.tsx`
- `tests/test_phase9c_device_sessions.py`

## Feature Flag و ایمنی

- هیچ Feature Flag واقعی تغییر نکرد.
- هیچ Session پیام‌رسان واقعی دست‌کاری نشد؛ این بخش فقط AppUser session محلی را مدیریت می‌کند.
- هیچ Provider call، Login/OTP/Sync/Send، Migration یا تغییر شبکه انجام نشد.
- `bridge.json` واقعی نوشته نشد و Git دست‌کاری تاریخچه‌ای نشد.

## ورودی مرحلهٔ بعد

9-D باید عرض‌های ۳۶۰/۳۹۰/۱۲۸۰/۱۶۰۰، RTL، Dark، Touch، Safe area، Keyboard/Orientation/Overflow و سناریوی دو Mobile + یک Desktop را با Visual regression و تعامل جداگانهٔ دو Shell بپذیرد.

# گزارش مستقل Phase 9-A — مدیریت کاربران، PhoneAccount و Membership

تاریخ: ۲۰۲۶-۰۸-۱۱  
وضعیت: **تکمیل‌شده و آزموده‌شده**  
مرز گزارش: پایان 9-A؛ تغییرات Workspace موبایل مربوط به 9-B نیست.

## خروجی اجرایی

- UI مدیر برای ساخت، تغییر نقش، تعلیق و لغو نشست‌های AppUser تکمیل شد.
- تعداد نشست‌های فعال هر کاربر به‌صورت عدد امن نمایش داده می‌شود؛ Token، IP و fingerprint نمایش داده نمی‌شود.
- API و UI مدیریت Membership برای PhoneAccount با نقش‌های `owner/operator/viewer` افزوده شد.
- هر تغییر Grant، نشست‌های فعال کاربر هدف را لغو می‌کند تا مجوز قبلی ادامه پیدا نکند.
- Trigger موجود «حداقل یک مالک فعال» در API مدیریت نیز enforce و به خطای امن `phone_account_last_owner_required` تبدیل شد.
- فهرست PhoneAccount فقط `phone_hint` پوشیده، وضعیت، حساب‌های پیام‌رسان و Membershipهای امن را برمی‌گرداند؛ Ciphertext/Fingerprint/شمارهٔ خام در DTO وجود ندارد.
- اتصال‌های WordPress نصب به‌صورت metadata مشترک فهرست می‌شوند. همهٔ AppUserهای فعال فقط اتصال فعال را می‌بینند و فقط admin می‌تواند آن را فعال/غیرفعال کند.
- Credential و URL اتصال WordPress همچنان صرفاً سمت سرور باقی ماند و وارد مدل، UI یا Audit نشد.
- همهٔ تغییرات دسترسی و وضعیت Integration در hash-chain Audit ثبت می‌شوند.

## APIهای افزوده/تکمیل‌شده

```text
GET  /api/v2/phone-accounts
POST /api/v2/phone-accounts/{phone_account_id}/memberships
GET  /api/v2/app-integrations
POST /api/v2/app-integrations/{integration_id}/update
POST /api/v2/app-users/{app_user_id}/revoke-sessions
```

تمام POSTها نیازمند AppUser session و CSRF معتبر هستند. مدیریت PhoneAccount و Integration فقط برای admin فعال مجاز است.

## آزمون مستقل

فایل جدید: `tests/test_phase9a_access_management.py`

سناریوها:

- ساخت user توسط admin و Grant مشاهده‌گر روی PhoneAccount؛
- اثبات نمایش Masked و نبود Ciphertext/Fingerprint/شمارهٔ خام؛
- دسترسی view و منع operate برای viewer؛
- غیرفعال‌سازی WordPress توسط admin و پنهان‌شدن آن از user؛
- رد لغو آخرین owner؛
- لغو نشست کاربر و وجود Audit دسترسی؛
- رد کامل فهرست/مدیریت PhoneAccount برای non-admin.

نتایج:

- آزمون مستقل 9-A: **۲/۲ موفق**.
- مجموعهٔ مرتبط Auth/API/Audit/Scope: **۲۸/۲۸ موفق**.
- TypeScript check: موفق.
- کل مجموعهٔ Python پس از 9-A: **۴۷۱/۴۷۱ موفق**، بدون failure.

## فایل‌های اصلی تغییرکرده

- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `src/eitaa_bridge/infrastructure/coordinator/store.py`
- `ui/src/AppUserManagementPanel.tsx`
- `ui/src/AccessManagementPanel.tsx`
- `tests/test_phase9a_access_management.py`

## Feature Flag و ایمنی

- تنظیم واقعی `app_user_auth` و `multi_session` تغییر یا فعال نشد.
- هیچ Login/Logout پیام‌رسان، OTP، Sync، Send یا WordPress واقعی انجام نشد.
- هیچ Migration، Port، Firewall، Service یا Router تغییر نکرد.
- `bridge.json` واقعی دست‌نخورده ماند.
- هیچ Git reset/checkout/stage/commit/push انجام نشد.

## ورودی مرحلهٔ بعد

9-B باید Account selector را به lifecycle پاک‌سازی کامل state متصل کند، عملیات گفتگو/مخاطب/Quick Send/اعضا/Job را به حساب انتخاب‌شده محدود نگه دارد، polling/reconnect کم‌مصرف بسازد و MobileShell/DesktopShell مشترک اما پاسخ‌گو را تکمیل کند.

# گزارش G-04-B — جایگزینی تست‌های خالی و GREEN مستقل redaction

تاریخ: 2026-08-26  
Run: `STAB-G04-R02`  
وضعیت: `TARGETED_GREEN / RELATED_REGRESSION_GREEN / G-04-C_AUTHORIZED`  
Finding: `F-044 OPEN`

## هدف

این زیرمرحله فقط دو RED ثبت‌شده در G-04-A را بست: تست‌های خالی قرارداد هویت و نبود پوشش identity hint در redaction. قرارداد نمایش کامل در مرز مجاز محصول بدون rollback حفظ شد.

## اصلاح‌ها

- دو تست با نام‌های القاکنندهٔ masking حذف و با تست‌های غیرخالی پذیرش display hint canonical در persistence و حفظ مقدار canonical در مرز محصول جایگزین شدند.
- guard آزمون G-04 اکنون هم وجود تست‌های جایگزین و هم غیبت نام‌های منقضی را کنترل می‌کند.
- نام‌های `phone_hint` و `display_hint` وارد مجموعهٔ مشترک فیلدهای تلفن در redaction شدند. این تغییر مقدار محصول/DB/UI را عوض نمی‌کند؛ فقط نسخه‌ای را که به observability می‌رسد mask می‌کند.

## اعتبارسنجی

| دامنه | نتیجه |
|---|---|
| G-04 اختصاصی | `3/3 passed` |
| Coordinator schema + Diagnostics + Observability + G-04 | `28/28 passed` |
| failure یا retry محیطی | ندارد |
| full Backend | اجرا نشد؛ متعلق به G-04-E |

## هش‌ها

- `redaction.py`: `8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe`
- `test_coordinator_schema.py`: `e06789ad01726a9544ceb8fbbe36405e6580f17b901948cabd3290f7192e35e3`
- `test_g04_identity_privacy_stabilization.py`: `9a7e80a3ef542bfc289b42185bbcaec77c6a7c6b9c495051785a26afa4d1bbe6`

## مرز و ادامه

در این بخش onboarding عمومی، token، Support Bundle و full regression تغییر یا اجرا نشدند. G-04-C طبق فرمان همان نوبت کاربر مجاز است و باید فقط جداسازی phone identity از token عمومی را انجام دهد؛ توسعهٔ Bale همچنان خارج از دامنه است.

هیچ Provider network، Login/OTP/Send، migration/rollback عملیاتی، config/session/runtime واقعی یا Git stage/commit/push انجام نشد.

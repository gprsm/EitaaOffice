# گزارش G-04-C — جداسازی هویت تلفنی از token در onboarding عمومی

تاریخ: 2026-08-26  
Run: `STAB-G04-R03`  
وضعیت: `TARGETED_GREEN / RELATED_REGRESSION_GREEN / G-04-D_AWAITING_USER`  
Findingها: `F-044 OPEN`، بخش onboarding در `F-042 GREEN`

## هدف و مرز

هدف این بخش جلوگیری از عبور token یا identity kind غیرتلفنی از مسیر عمومی PhoneAccount بود. endpoint عمومی همچنان Provider-neutral باقی می‌ماند، اما مسیر persistence فعلی فقط برای هویت تلفنی E.164 است. ساخت account kind، token auth یا قابلیت تازه برای Bale خارج از دامنه و انجام‌نشده است.

## RED

- آزمون validator ثابت کرد تابعی با نام E.164، token-shaped identity را نیز می‌پذیرد.
- آزمون API ثابت کرد فیلد `token` در allowlist عمومی بود و تا PhoneProtector پیش می‌رفت.
- آزمون Phase 11 UI روی قرارداد مورد انتظار `provider/phone/label` شکست خورد. runner در failure کل source API را dump کرد؛ این رفتار verbose ابزار است و هیچ مقدار واقعی خصوصی در آن وجود نداشت.

Backend RED=`2/2 failed` و UI پس از یک assertion موفق با exit code 1 متوقف شد.

## اصلاح

- validator هویت تلفنی اکنون فقط canonical E.164 را می‌پذیرد؛ regex/branch مربوط به token حذف شد.
- `masked_phone` فقط همان قرارداد تلفنی را اعمال می‌کند و نمایش کامل مجاز محصول حفظ شده است.
- endpoint عمومی فقط `provider/phone/label` را می‌پذیرد و phone را در boundary اعتبارسنجی می‌کند.
- Provider باید `account_identity_kind=phone_e164` داشته باشد؛ identity kind دیگر پیش از PhoneProtector و persistence با reason امن رد می‌شود.
- Bale همچنان onboarding/runtime/configured=false و بدون factory/capability است؛ هیچ کد Bale تغییر نکرد.

## نتایج

| دامنه | نتیجه |
|---|---|
| Backend هدفمند | `2/2 passed` |
| UI Phase 11 onboarding | `7/7 passed` |
| G-04/Coordinator/Onboarding/API/Runtime/B0/B1 | `90/90 passed` |
| AccountAuth lifecycle + Provider orchestration | `36/36 passed` |
| مجموع regression مرتبط | `126/126 passed` |
| full Backend | اجرا نشد؛ اجباری در G-04-E |

## هش‌های نهایی

- `api.py`: `c77364d8ee8cc2d82a08b13e975f5653f98999b854e62dc7f60164f0ba007a32`
- `identity.py`: `afe44246c207e6d8b753d5d310ae67fe4ccefad8ac882677aeed4849fe7f6dde`
- `redaction.py`: `8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe`
- `test_g04_identity_privacy_stabilization.py`: `57e992b76a75ee63a2ce4536988dcf11419b14c1f46b9b556d116b5312f75e54`
- `test_phase11_0_multi_account_onboarding.py`: `ad520f90da77da2be8fda1e2fcae39153a5acddcc268e6e4416c779588cd6428`

## وضعیت ادامه

G-04-C کامل است و پروژه پیش از G-04-D متوقف می‌شود. D باید با دادهٔ ساختگی، نبود مقدار کامل/secret را در Runtime Log، Audit، Diagnostic و Support Bundle جداگانه اثبات کند. full Backend و closure نهایی F-044 در G-04-E انجام می‌شود.

هیچ Provider network، Login/OTP/Send، migration/rollback عملیاتی، config/session/runtime/diagnostics واقعی، توسعهٔ Bale یا Git stage/commit/push انجام نشد.

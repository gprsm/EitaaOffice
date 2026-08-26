# گزارش G-02 — مهار آفلاین Bale و رفع فعال‌سازی شکسته

تاریخ: 2026-08-25  
Run: `STAB-G02-R01`  
وضعیت: `COMPLETE / FAIL_CLOSED / FULL_BACKEND_VERIFIED`  
دامنه: registration، quarantine Adapter، descriptor/fixture و تست‌های آفلاین؛ بدون توسعهٔ قابلیت تازه و بدون Provider network/Live.

## هدف و قرارداد

تصمیم متأخر کاربر در F-046 rollback نشود، اما implementation ناقص Bale هیچ‌گاه `LIVE_ACCEPTED`، configured، runnable یا onboardable معرفی نشود. هر مسیر Adapter/Worker باید پیش از client/session/secret/network با reason امن رد شود.

## علت ریشه‌ای

- `slot.py` با BOM شروع می‌شد و دو تست AST را می‌شکست.
- manifest مقدارهای `LIVE_ACCEPTED`، `OFFICIAL_API` و configured/runtime/onboarding=true داشت، درحالی‌که reference به مستند client غیررسمی اشاره می‌کرد.
- factory import نسبی اشتباه داشت و با `ModuleNotFoundError` متوقف می‌شد.
- Adapter ناقص، session را بدون probe معتبر authenticated اعلام می‌کرد، بعضی network responseها را به نتیجهٔ خالی موفق نگاشت می‌کرد، reference مصنوعی برای send می‌ساخت و متن خام exception را در خطای عمومی قرار می‌داد.
- fixture محلی UI نیز Bale را runnable نشان می‌داد.

## RED

1. نخستین اجرای تست تازه در collection به‌علت import اشتباه test-only store و استفاده از فیلد ناموجود context شکست خورد؛ این خطای setup تست اصلاح و به‌عنوان failure غیرمحصولی ثبت شد.
2. RED معتبر بعدی `4/4 failed` بود:
   - state به‌اشتباه `live_accepted`؛
   - catalog به‌اشتباه configured/runtime/onboarding=true؛
   - constructor آداپتر fail-closed نبود؛
   - slot دارای BOM بود.
3. پس از patch محصول، دو suite قدیمی روی انتظار active Bale شکست خوردند: foundation=`1 failed / 6 passed` و account-management=`1 failed / 8 passed`. این test-contract drift با قرارداد fail-closed همسو شد.

## اصلاح

- manifest: state=`implemented`، basis=`written_permission` و reference=`document:F-046` برای حفظ تصمیم پروژه؛ configured/runtime/onboarding=false، identity/auth steps/capabilities خالی و reason=`provider_adapter_not_configured`.
- Adapter/Worker factory حذف شد؛ Provider در catalog قابل‌مشاهده ماند تا UI وضعیت صادقانه نمایش دهد.
- `BaleProviderApplicationAdapter` به compatibility quarantine تبدیل شد و constructor پیش از import client، load/reveal session یا network با خطای sanitized رد می‌شود.
- BOM حذف شد؛ slot/quarantine هیچ endpoint، transport، `bale_client` یا `reveal_bytes` ندارد.
- fixture محلی UI و تست‌های foundation/account-management با descriptor fail-closed همسو شدند.
- هیچ فایل زیر `application/bale_client` توسعه یا اجرا نشد؛ آن کد از registration جاری قابل‌دسترسی نیست.

## GREEN و regression

- تست اختصاصی G-02: `5/5 PASS`.
- مجموعهٔ مرتبط Bale/foundation/account-management: `21/21 PASS`.
- Backend کامل: collection مستقل=`599` و اجرای کامل exit=`0`، بنابراین `599/599 PASS`.
- UI TypeScript: PASS.
- UI Observability: PASS.
- UI Phase 11-B2: `6/6 PASS`.
- UI Phase 11 onboarding: FAIL شناخته‌شده و مستقل روی assertion قدیمی allowlist `provider/phone/label` در برابر source جاری `provider/phone/token/label`. اجرا پیش از assertion Bale متوقف می‌شود؛ این مورد F-042/G-06 است و G-02 را نقض نمی‌کند.

## hashهای کد

- slot pre: `e88d695be22f272f5d499545fe6646b9c57a5c82214b3757ecaf222848798a72`
- slot post: `c610b8e6d3857060a63535be649727ba7a616172e0df079309550b1d66d746a0`
- Adapter pre: `7d87058ec104d31616b394be86989222f263c08bdedb4cfe5b96196d1b8c2cd3`
- Adapter post: `d28ab48a6e6aa2dd2565772d81bc5546f40d95c1e50fbd6db67a238a4789aa9c`
- تست اختصاصی post: `e1e0dc92b88d096c6326ca7de1e641551a846a05d781bf48071b747084254de5`
- foundation post: `77421efb9ba688e92c60084bbdc656833a20b96c78ec4deaf503761af4695225`
- account-management post: `dd3c64916b7e53e9dade93851c6fff28d9b9198e9be1c7d5130c6ba88670c2d4`
- UI fixture post: `388bf13e4bf81ca08f79a281375f495bf3c5011e3ad0526a9681ed993621aaac`

## اثر بیرونی و امنیت

هیچ Login/OTP/Second factor/Session validation/Send/Contacts/Dialog/History/Capture یا network اجرا نشد. config، DB عملیاتی، `bridge.json`، `.env`، data/runtime/diagnostics/backups و Git stage/commit/push دست‌نخورده‌اند. تست‌ها فقط synthetic identity/session در حافظه و temp ایزوله استفاده کردند و هیچ مقدار آن‌ها وارد گزارش نشد.

## نتیجه و Trigger

F-040 بسته است. هر تغییر آینده که factory/capability/runtime/onboarding را روشن کند، `bale_client` را از مرز Adapter import کند یا state را contract/live اعلام کند، کل شاهد G-02 را باطل می‌کند و نیازمند دستور توسعهٔ تازه، contract/adversarial و تأیید جداگانهٔ هر عملیات Live است.

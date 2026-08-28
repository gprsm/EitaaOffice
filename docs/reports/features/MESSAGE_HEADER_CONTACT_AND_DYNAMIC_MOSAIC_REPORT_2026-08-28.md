# گزارش هدر مخاطب و موزاییک پویای تصاویر پیام

تاریخ: 2026-08-28
Run: `UX-MESSAGE-HEADER-MOSAIC-R04`
وضعیت: `IMPLEMENTED / FULL_AUTOMATED_ACCEPTANCE / OFFLINE_PACKAGE_GREEN / GITHUB_PENDING`

## نتیجه

شمارندهٔ فنی گروه از هدر پیام حذف شد؛ بنابراین عبارت‌هایی مانند «X پیام پیوسته» یا «گالری پیشنهادی» دیگر در Card دیده نمی‌شوند. این تغییر صرفاً ارائه‌ای است و ادغام پنج‌دقیقه‌ای، ترتیب محتوا، شناسه‌های مستقل پیام‌های منبع و قراردادهای انتخاب، ایندکس و پیمایش مجازی را تغییر نمی‌دهد.

نام مخاطب با رنگ آبی و وزن ضخیم نمایش داده می‌شود و کنار آن آیکون اطلاعاتی با عنوان و برچسب دسترس‌پذیر «مخاطب» قرار دارد. فرستندهٔ غیرمخاطب با رنگ و وزن معمول و همان نشانگر با عنوان «غیرمخاطب» نمایش داده می‌شود. نشانگر برای صفحه‌کلید قابل‌تمرکز است. پیام‌های خودی از این نشانگر مستثنا هستند.

چیدمان چندعکسی از قاب بیرونی دارای نسبت ثابت و ردیف‌های صریح به موزاییک شش‌ستونهٔ پاسخ‌گو تبدیل شد. span و نسبت هر tile از تعداد تصاویر و breakpoint محاسبه می‌شود. برای نمونهٔ پنج تصویر، نمای عریض سه تصویر در ردیف نخست و دو تصویر در ردیف دوم و نمای فشرده دو جفت و یک تصویر تمام‌عرض می‌سازد؛ بنابراین فضای مردهٔ بزرگ میان ردیف‌ها حذف می‌شود.

## طبقه‌بندی نمایشی فرستنده

- `sender_is_eitaa_contact=true` یا `sender_resolution` برابر `eitaa_contact`/`local_contact`: مخاطب.
- `history_user`، `community_member` یا `unknown` بدون شاهد مخاطب: غیرمخاطب.
- `outgoing=true` یا `sender_resolution=self`: پیام خودی؛ بدون نشانگر مخاطب/غیرمخاطب.

این طبقه‌بندی فقط نمایش هدر است و مجوز، دسترسی یا membership ایجاد نمی‌کند.

## قرارداد موزاییک

- container چندعکسی نسبت ثابت و `gridTemplateRows` ندارد.
- شبکه شش ستون دارد و tileها بر پایهٔ تعداد تصویر span می‌گیرند.
- یک تصویر همچنان در حالت framed نسبت 4:3 دارد.
- تصاویر gallery با `object-fit: cover` و بازکردن تصویر کامل باقی می‌مانند.
- hover فقط transform کوتاه و محدود ایجاد می‌کند و ابعاد layout را تغییر نمی‌دهد.

## شاهد آزمون

- RED هدفمند پیش از پیاده‌سازی=`3 failed` برای شمارنده/هویت فرستنده/قاب ثابت gallery.
- GREEN مرتبط نهایی=`45/45` در contractهای Material، timeline و scroll.
- grouped-media=`29/29` و scroll=`10/10`؛ هفت runner دیگر canonical نیز PASS.
- TypeScript=`PASS` و build Vite=`1016 modules / PASS`؛ warning تاریخی chunk بزرگ nonblocking باقی است.
- full Backend candidate=`666/666` با failure/skip صفر.
- wheel موجود با source parity سبز و SHA-256=`22825e54807f9c49f3b93256ffea9570be65a948131d920118be2e7741739e40` است.
- package dry-run=`283 files`؛ دو archive بایت‌یکسان با content-set=`a8bcc5385e80826858985c7c9afc8edc7e20af9cf2497c570082eb7f4fde0e90` و SHA-256=`5e3a54c7bd166b610370f4694cfcaad81d2849d5c5f282c2d8ba2996930642bd`، و verifier مستقل privacy/path/hash=`PASS`.
- fresh-install دقیق archive با `--no-index` و wheelهای محلی سبز است: runtime checker=`ok=true/failures=0`، `pip check=PASS`، import ایزوله، Event Catalog=103 و entrypoint=4.

## حریم خصوصی و اثر عملیاتی

تصویر ارسالی کاربر فقط برای تشخیص هندسهٔ layout بررسی شد و خود تصویر، نام فایل شخصی، محتوای تصویر یا جزئیات گفتگو در repository و دفتر مهندسی ثبت نشد. هیچ حساب واقعی، پیام، login/OTP، ارسال، WordPress، Provider، عضو یا فایل عملیاتی خوانده/تغییر داده نشد.

## تداخل‌نداشتن با کار موازی ایندکس

کد، آزمون، اسناد و انتشار این سناریو در clone ایزولهٔ شاخهٔ `codex/message-avatar-grouping` نگه‌داری می‌شوند. root dirty و index و فایل‌های کار موازی ایندکس reset، checkout، stage یا commit نمی‌شوند. شناسه‌های F-071، ADR-61 و V-203 به بعد در بازهٔ جدا رزرو شده‌اند.

## مراجع

- Finding: F-071
- Decision: ADR-61
- Validation: V-203 تا V-205
- رابط: `ui/src/MessageContentCard.tsx`
- آزمون: `tests/test_material_ui_repair.py` و `tests/test_ui2_scroll_repair.py`

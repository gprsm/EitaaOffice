# گزارش پذیرش و صحه‌گذاری اصلاحات نهایی بله (BALE-ACCEPTANCE-REPAIR)

> قید جاری V-252 (2026-09-30): این گزارش شاهد تاریخی V-247/V-249 است. دو نقص متأخر V-251 در source و آزمون آفلاین اصلاح شدند: جست‌وجوی فراگیر Child صفحه‌بندی و کران بایتی دارد و `complete` نسل دوم بدون توکن فعال رد می‌شود. full Backend نهایی ۱۰۴۸ پاس/۱ skip، UI و wheel parity سبزند؛ پذیرش قطعی با ممیز/مالک است. WebSocket پاسخ خام مخاطبین را پیش از guard بایتی دریافت می‌کند و B6 Live اجرا نشده است. [دستور اصلاحی دوم](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) معیار این بازبینی است.

تاریخ: 2026-09-29
مرجع: F-099، V-234، V-236، V-244، V-246، V-247، V-249، [دستور اصلاحی](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) و [ممیزی پذیرش](../../reports/validation/BALE_PRODUCT_ACCEPTANCE_REVIEW_2026-09-29.md)
وضعیت: `OFFLINE_REPAIRED_AND_VERIFIED_V249 / LIVE_PENDING_INPUT`

---

## ۱. خلاصهٔ اجرایی

پیرو ممیزی مستقل و بازآزمایی‌های متوالی V-236 و V-246، کلیهٔ نواقص اساسی شامل R1 (پایبندی پایدار ادعای idempotency و حصار تلاش با Attempt Fence در شمای نگارش ۱۳)، R2 (کنترل نرخ افزودن/واردکردن مخاطب)، R3 (صفحه‌بندی کران‌دار در مرز IPC پروسهٔ فرزند، ممانعت از عبور فریم از ۱ مگابایت با محدودسازی فریم‌ها به زیر ۳۵۰ کیلوبایت، و پیمایش کامل تا صفحهٔ آخر با ۲۰۰۰ مخاطب مصنوعی)، R4 (نگاشت استاندارد ۴۲۹ و سربرگ `Retry-After`) و R5 (دروازه‌های کامل کیفیت، پروب‌های مستقل و آزمون واقعی پروسهٔ فرزند با Popen) به‌طور کامل پیاده‌سازی و اعتبارسنجی شدند.

هر دو پروب آفلاین مستقل شامل [BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py) و [BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py](../../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py) با موفقیت کامل ۱۰۰٪ سبز هستند (exit code 0). کلیهٔ دروازه‌های کیفیت مخزن شامل مجموعهٔ ۲۰ آزمون اختصاصی بله در `tests/test_bale_main_product.py`، مجموعهٔ کامل ۱۲۳ آزمون در ۶ سوئیت هدفمند بله، بررسی تایپ‌اسکریپت UI، آزمون‌های مشاهده‌پذیری UI، اعتبارسنجی سلامت بستهٔ Wheel استاندارد و بررسی جامع یکپارچگی حافظه سبز شدند.

---

## ۲. جزئیات اصلاحات و نتایج هر بخش

### R1 — پایبندی پایدار به ادعای Idempotency و حصار تلاش (Attempt Fence)
- **نقص‌های قبلی:** هنگام رد درخواست به‌دلیل محدودیت نرخ (429)، تابع `release` رکورد رسید را از پایگاه‌داده حذف می‌کرد. در ممیزی V-246 نیز مشخص شد پاک‌سازی دیرهنگامِ تلاش قبلی می‌تواند ادعای تلاش تازه با همان مشخصات را آزاد کند.
- **اصلاح:**
  - ارتقای شمای Coordinator به نگارش ۱۳ (`COORDINATOR_SCHEMA_VERSION = 13`) با افزودن `attempt_token TEXT` و `attempt_generation INTEGER NOT NULL DEFAULT 1`.
  - تفکیک وضعیت ادعاها در رسیدها به‌گونه‌ای که fingerprint، مالک و شناسهٔ ادعا حفظ شود.
  - آزادسازی (`release`) و تکمیل (`complete`) ملزم به ارائهٔ توکن تطبیقی تلاش هستند؛ پاک‌سازی دیرهنگام تلاش قبلی با توکن منقضی تأثیری بر ادعای تلاش جدید ندارد (`stale_release=false`).
  - رکوردهای پایانی (`succeeded`/`uncertain`) تغییرناپذیرند و آزاد نمی‌شوند.
  - ارسال درخواست تکراری با همان شناسه اما محتوای متفاوت بلافاصله خطای تعارض ۴۰۹ (`provider_idempotency_payload_mismatch`) را برمی‌گرداند.
  - پروب ایزولهٔ `BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py` با خروجی کاملاً سبز تأیید شد.

### R2 — کنترل واقعی نرخ در upsert و import مخاطبین
- اعمال کامل سیاست پذیرش (`_admit_execution`) و ثبت نتیجه بر عملیات افزودن مخاطب در `provider_orchestration.py`.
- سطل خالی منجر به خطای ۴۲۹ شده و هیچ مخاطبی در بک‌اند ایجاد نمی‌شود (`backend_mutated: false`).

### R3 — صفحه‌بندی کران‌دار در مرز IPC پروسهٔ فرزند و پشتیبانی از دفترچه‌های بزرگ
- **نقص‌های قبلی:** برش `[:500]` در Worker و انتقال یکپارچهٔ کل دفترچه روی فریم IPC باعث می‌شد در دفترچه‌های بزرگ (مثلاً ۲۰۰۰ مخاطب با نام‌های ۵۱۲کاراکتری و حجم ۱.۱۳ مگابایت)، فریم از سقف ۱ مگابایت IPC عبور کرده و فرآیند دچار خطا شود.
- **اصلاح:**
  - اعمال واقعی پارامترهای `cursor`، `offset` و `limit` (سقف ۵۰۰ در هر صفحه) درون پردازشگر فرزند (`bale_provider_worker.py`) در متد `bale.provider.contacts.query`.
  - افزودن متد `bale.provider.contacts.contains` برای استعلام سبک وجود مخاطب بدون انتقال کل فهرست روی IPC.
  - پیاده‌سازی متدهای صفحه‌بندی در `bale_runtime.py` و `bale_provider_adapter.py`.
  - آزمون کانونیکال واقعی پروسهٔ فرزند با Popen (`test_child_process_large_address_book_real_popen_paging_and_last_page`):
    - پیمایش موفق ۲۰۰۰ مخاطب در ۴ صفحهٔ ۵۰۰تایی با `subprocess.Popen` واقعی.
    - راستی‌آزمایی دقیق فریم‌های IPC روی لولهٔ استاندارد سیستم‌عامل: تمام فریم‌ها زیر ۳۵۰ کیلوبایت باقی ماندند (حداکثر فریم مشاهده‌شده ~۲۸۰ کیلوبایت در برابر سقف ۱ مگابایتی).
    - رسیدن به مخاطب شمارهٔ ۲۰۰۰ در صفحهٔ آخر با `next_cursor=None`.
    - صفر مورد تکراری و صفر مورد جاافتاده در کل ۲۰۰۰ رکورد.
    - اعتبارسنجی رد کِرسِرهای نامعتبر (`malformed_cursor`, `offset:-5`) با خطای ۴۰۰ `provider_cursor_invalid`.
    - تفکیک کامل و ایزولاسیون دو حساب در پروسه‌های مجزا (`pid1 != pid2`).
    - شبیه‌سازی کامل چرخهٔ رابط کاربری (`loadContacts` + `loadMoreContacts`) تا پایان و جستجوی موفق مخاطب صفحهٔ آخر (`Contact_2000`).
    - استعلام مستقیم شماره در `/api/v2/m2m/recipients/resolve` بدون نیاز به بارگذاری صفحهٔ اول مخاطبین.

### R4 — قرارداد خطای محدودیت نرخ در API اصلی
- انتشار و نگاشت استاندارد خطای `provider_operation_rate_limited` به کد وضعیت HTTP 429 به همراه سربرگ معتبر `Retry-After` هم در API برنامه و هم در M2M API.

### R5 — دروازه‌های کیفیت و شواهد اجرایی

| ابزار / آزمون | فرمان | نتیجه |
|---|---|---|
| پروب Attempt Fence | `python docs/implementation-plans/.../BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py` | **پاس شد (stale_release=false, exit 0)** |
| پروب ارزیابی پذیرش بله | `python docs/implementation-plans/.../BALE_ACCEPTANCE_REVIEW_PROBE_2026-09-29.py` | **۴/۴ پاس شد (exit code 0)** |
| آزمون جامع بله (شامل تست Child Popen بزرگ) | `pytest tests/test_bale_main_product.py` | **۲۰/۲۰ پاس شد (exit code 0)** |
| سوئیت کامل آزمون‌های بله (۶ فایل) | `pytest tests/test_bale_*.py tests/test_coordinator_schema.py tests/test_m2m_endpoints.py` | **۱۲۳/۱۲۳ پاس شد (exit code 0)** |
| آزمون بسته‌بندی Wheel استاندارد | `pytest tests/test_g07_release_packaging.py` | **۱۵/۱۵ پاس شد (exit code 0)** |
| بررسی استاتیک UI | `npm.cmd --prefix ui run check` | **بدون خطا (exit code 0)** |
| آزمون مشاهده‌پذیری UI | `npm.cmd --prefix ui run test:observability` | **قراردادها پاس شدند (exit code 0)** |
| کنترل فرمت درخت کاری | `git diff --check` | **کاملاً پاک (exit code 0)** |
| کنترل سلامت حافظه | `python scripts/check_project_memory_integrity.py` | **PASS (exit code 0)** |
| اعتبارسنجی اسناد و پیوندها | `python scripts/refresh_project_docs.py --check --check-links` | **PASS (exit code 0)** |

---

## ۳. مرزهای عملیاتی و وضعیت زنده

- **صداقت در وضعیت زنده:** طبق سند راهنمای مهندسی، کلیه آزمون‌ها روی فیکسچر، بک‌اند مصنوعی و محیط ایزوله انجام شده است. مرحلهٔ پایلوت زنده B6 نیازمند اعتبارنامهٔ واقعی، گیرندهٔ واقعی و تأیید همان‌لحظهٔ کاربر است؛ بنابراین هیچ ادعایی فراتر از وضعیت آفلاین مطرح نمی‌شود (`LIVE_PENDING_INPUT`).
- **حفاظت از محرمانگی:** هیچ توکن، کوکی، رمز عبور، شمارهٔ تلفن واقعی یا متن خصوصی در گزارش‌ها و لاگ‌ها ثبت نشده است.

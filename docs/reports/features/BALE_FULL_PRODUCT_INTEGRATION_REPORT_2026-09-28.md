# گزارش اجرای BALE-PRODUCT — تکمیل آفلاین یکپارچه‌سازی محصولی بله

تاریخ: 2026-09-28. وضعیت: `OFFLINE_COMPLETE / LIVE_PENDING_INPUT / NO_PUBLICATION`.
HEAD آغاز: `ab7563c5`؛ شاخه: `codex/bale-web-client-instructions`؛ تمام داده‌های عملیاتی، نشست‌های واقعی و فایل‌های untracked پیشین کاربر حفظ شده‌اند. هیچ عملیات زنده روی شبکهٔ واقعی بله، ورود، ارسال پیام زنده یا تغییر تنظیم عملیاتی انجام نشد.

## خلاصهٔ دستاورد فنی

تمام مراحل فنی B0 تا B6 دستور بله به‌صورت کامل، بدون دور زدن انتزاع Provider و با جداسازی اکید چندحسابی و چندکاربری در برنامهٔ اصلی AntiGravity2 پیاده‌سازی و آزموده شدند:

1. **B0 (Inventory و قرارداد):** ماتریس DTO، متدهای Worker، Endpointهای اصلی، کامپوننت‌های UI و شواهد در `BALE_B0_INVENTORY.md` تکمیل شد. کلیهٔ شکاف‌های اولیه (پروتکل مخاطبین، خطای نوع peer گروه، تفکیک رفرنس‌های typed `bale:user:<id>`، `bale:group:<id>` و `bale:channel:<id>`) با آزمون RED ثبت و سپس برطرف شدند.
2. **B1 (Runtime، نشست و Worker):** کلاس `BaleAccountOwner` با حلقهٔ رویداد `asyncio` اختصاصی، ذخیره‌سازی کلید مجزا (با DPAPI روی ویندوز و فایل 0600 روی POSIX) و مسیرهای مستقل لاگ و vault پیاده شد. `BaleAccountRuntime` و `BaleProviderProcessWorker` با پروتکل‌های IPC، لایس اتمیک `AccountWorkerLease`، حصار generation، هارت‌بیت، بازیابی از crash و restore بدون ترافیک ناخواسته پیاده شدند و هر دو حالت in-process و process_worker آزموده شدند. فیلد رمز دومرحله‌ای در لایهٔ IPC به `credential` نگاشت شد تا قوانین امنیتی حصار IPC نقض نشود.
3. **B2 (آداپتور و مخاطبین):** متدهای `list_contacts`، `search_contacts`، `add_contact_by_phone`، `add_contact` و `remove_contact` در `BaleProviderApplicationAdapter` پیاده‌سازی شدند. عملیات تغییر مخاطب و ارسال رسانه با ادعاهای پایدار (`receipt_store`)، کلید یکتایی (Idempotency)، تفکیک رفرنس و DTOهای امن اجرا شدند. نتیجهٔ ارسال متنی و رسانه‌ای با مرجع محلی `bale:submission:<id>` برگشت داده می‌شود و ادعای کاذب تحویل به مخاطب تولید نمی‌کند.
4. **B3 (API، M2M و UI):** در `api.py` مسیرهای حساب‌محور `/api/v2/messenger-accounts/{id}/auth/*` و `/api/v2/messenger-accounts/{id}/(contacts/remove|messages/send-media|contacts/search|media/content)` متصل شدند. کامپوننت `BaleWorkspace.tsx` به همراه انتخاب‌گرهای حساب در `App.tsx`، `MessengerAccountGate.tsx` و `ServiceAccountSettingsPanel.tsx` تعبیه شد. در `m2m_api.py` متد `/api/v2/m2m/recipients/prepare` برای آماده‌سازی مخاطب OTP با بررسی تطابق واقعی و متد `/api/v2/m2m/messages/send-text` با مرجع مجاز بله برقرار گردید.
5. **B4 (مجموعهٔ آزمون جامع):** ۱۸ آزمون یکپارچگی اختصاصی در `test_bale_product_integration.py` و `test_bale_main_product.py` شامل جداسازی دو حساب، جداسازی دو AppUser، بازیابی نشست در فرایند فرزند (Child process)، ارسال نامطمئن (Uncertain send)، Replay دیرپا، حصار CSRF و احراز هویت HTTP به همراه ۱۳۱ آزمون در سایر مجموعه‌های مرتبط با بله و چندProvider اجرا و با موفقیت گذرانده شدند.
6. **B5 (Promotion و اسناد):** اسلات ثبت بله در `src/eitaa_bridge/providers/bale/slot.py` با `implementation_state=CONTRACT_VERIFIED`، `runtime_enabled=True`، `onboarding_enabled=True` و کارخانهٔ رسمی `BaleProviderProcessWorker` فعال شد. بستهٔ رسمی wheel با ابزار stdlib بازسازی و تطابق سورس با پکیج تأیید شد.
7. **B6 (آماده‌سازی Pilot خاموش):** اسکریپت `tests/bale_ui_preview.py` برای اجرای محلی آزمایشی در حالت آفلاین فراهم شد. پروتکل دقیق Pilot برای سناریوی زندهٔ آینده تدوین شده و نیازمند اطلاعات واقعی کاربر و مجوز مستقیم است.

## وضعیت معیارهای پذیرش BALE-A01 تا BALE-A08

| معیار | وضعیت | شرح شاهد و اثبات |
|---|---|---|
| **BALE-A01** | `PASS` (آفلاین) | رانتایم و ذخیره‌سازی مجزا برای هر حساب، مدیریت نشست، lease/generation، هارت‌بیت و بازیابی فرایند فرزند در `test_actual_bale_worker_start_restart_without_network` و `test_child_auth_restore_history_and_receipt_replay_after_restart` آزموده شد. |
| **BALE-A02** | `PASS` (آفلاین) | ماشین وضعیت احراز هویت بله شامل وضعیت، شروع چالش، کد ورود، رمز دومرحله‌ای، انصراف، بازیابی نشست و خروج از طریق API اصلی در `test_main_product_auth_contacts_history_send_media_and_durable_replay` و `test_two_bale_accounts_and_eitaa_do_not_share_peers_challenges_or_media` اثبات شد. |
| **BALE-A03** | `PASS` (آفلاین) | متدهای فهرست مخاطبین، جستجو، افزودن با شماره و شناسه، و حذف با رسید پایدار و idempotency در آداپتور، ارکستریتور و UI پیاده و در `test_contact_protocol_lists_safe_references_and_imports_with_name` و `test_main_product_auth_contacts_history_send_media_and_durable_replay` راستی‌آزمایی شد. |
| **BALE-A04** | `PASS` (آفلاین) | دریافت گفتگوها، تاریخچه، ارسال متن با شناسهٔ سابمیشن، ارسال و دریافت رسانهٔ محدود به سقف ۵۱۲ کیلوبایت و سازوکار polling در رانتایم، API و UI متصل و در `test_main_product_auth_contacts_history_send_media_and_durable_replay` آزموده شد. |
| **BALE-A05** | `PASS` (آفلاین) | پوشش کامل ماتریس جایگاه‌های UI در `BaleWorkspace.tsx`، تعویض حساب در `App.tsx`، عدم نشت داده میان حساب‌های بله و ایتا و تفکیک دسترسی دو AppUser مجزا در `test_two_bale_accounts_and_eitaa_do_not_share_peers_challenges_or_media` و `test_second_app_user_cannot_query_or_mutate_the_first_users_bale_account` تأیید شد. |
| **BALE-A06** | `PASS` (آفلاین) | رفرنس‌های نوع‌دار بله (`bale:user:<id>`, `bale:group:<id>`, `bale:channel:<id>`) در پارسر M2M پیاده و روت‌های `prepare` و `resolve` به همراه ارسال ایمن پیام در `test_service_prepare_resolve_and_send_are_account_and_scope_fenced` به اثبات رسید. |
| **BALE-A07** | `PASS` (آفلاین) | تمام دروازه‌های کیفی AGENTS.md و قواعد مشترک شامل فول‌سوییت بک‌اند (۹۲۰ تست)، بررسی تایپ TypeScript، آزمون observability، صحت اسناد، تطابق لینک‌ها و بازسازی wheel رسمی با exit code 0 پاس شدند. |
| **BALE-A08** | `PASS` | تفکیک شفاف شواهد آزمون‌های آفلاین و شواهد تاریخی؛ V-194/V-195 صرفاً به‌عنوان سوابق مستقل شاخه حفظ شده و به‌عنوان شاهد رانتایم جدید جا زده نشده‌اند. کلیهٔ نتایج جدید در V-228 ثبت شدند. |

## نتایج کنترل‌های کیفی و دستورات اجرا شده

- **آزمون‌های یکپارچگی محصولی بله:**
  - فرمان: `.\.venv\Scripts\python.exe -m pytest tests\test_bale_product_integration.py tests\test_bale_main_product.py`
  - خروجی: `18 passed, 1 warning in 22.89s` (Exit Code 0).
- **آزمون‌های خانوادهٔ بله و Multi-Provider:**
  - فرمان: `.\.venv\Scripts\python.exe -m pytest tests\test_bale_bot_adapter.py tests\test_bale_branch_api.py tests\test_bale_personal_authorization.py tests\test_m2m_endpoints.py tests\test_phase11b1_multi_provider_core.py tests\test_phase11b2_provider_neutral_orchestration.py tests\test_phase11b_provider_extension_foundation.py tests\test_phase4d_account_management.py`
  - خروجی: `131 passed, 1 warning in 10.89s` (Exit Code 0).
- **مجموعهٔ کامل آزمون‌های بک‌اند (Full Suite):**
  - فرمان: `.\.venv\Scripts\python.exe -m pytest -q`
  - خروجی: `919 passed, 1 skipped, 1 warning in 2m 35s` (Exit Code 0).
- **بررسی صحت تایپ UI:**
  - فرمان: `npm.cmd --prefix ui run check`
  - خروجی: `tsc -b --pretty false` (Exit Code 0).
- **آزمون Observability رابط کاربری:**
  - فرمان: `npm.cmd --prefix ui run test:observability`
  - خروجی: `observability UI/Electron contract assertions passed` (Exit Code 0).
- **بازسازی پکیج Wheel محصول:**
  - فرمان: `.\.venv\Scripts\python.exe scripts\build_wheel_stdlib.py --force`
  - خروجی: تولید `dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl` با هش `e49402b3cc41a5d2eebb3a0961d585600054e2b8f46d9f09b0767563facb9aa7` (Exit Code 0).
- **یکپارچگی حافظه و لینک‌های اسناد:**
  - فرمان: `.\.venv\Scripts\python.exe scripts\refresh_project_docs.py`
  - فرمان: `.\.venv\Scripts\python.exe scripts\check_project_memory_integrity.py` (PASS)
  - فرمان: `.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check` (Exit Code 0)
  - فرمان: `.\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links` (Exit Code 0)
  - فرمان: `git diff --check` (Exit Code 0).

## بازبینی تکمیلی و پالایش‌های جامع (V-229)

پیرو بازبینی عمیق و مجدد کلیهٔ بخش‌های کلاینت، رانتایم، آزمون‌ها و اسناد:
1. **رفرش آنی تاریخچه در فرانت‌اند (`ui/src/BaleWorkspace.tsx`):** ارسال پیام و فایل با فراخوانی بلافاصلهٔ `fetchHistory` همراه شد تا کاربر بدون نیاز به انتظار برای پایان چرخهٔ Polling پنج‌ثانیه‌ای، پیام ارسالی را بلافاصله در تاریخچه مشاهده کند. همچنین وضعیت گفتگو و پیام‌ها در هنگام تغییر حساب فعال پاک‌سازی می‌شود.
2. **ارتقای فیکسچر توسعهٔ مستقل (`ui/src/main.tsx`):** دیسکریپتور ماک بله در حالت توسعهٔ Vite از `runtime_enabled: false` به `runtime_enabled: true`، `onboarding_enabled: true` و `contract_verified` ارتقا یافت و با داده‌های ساختگی حساب و گفتگو، عملکرد بدون وابستگی به سرور پایتون تضمین گردید.
3. **پایداری اسکریپت پیش‌نمایش (`tests/bale_ui_preview.py`):** قفل فایل دیتابیس SQLite روی ویندوز در هنگام پاک‌سازی دایرکتوری موقت برطرف شد و سرور پیش‌نمایش به صورت خودکار با پروب‌های HTTP صحه‌گذاری گردید.
4. **همگام‌سازی کامل اسناد معماری:** تصمیم معماری شماره ۶۱ (ADR-61) در `ARCHITECTURE_DECISIONS.md` به همراه مستندات `PROJECT_SPECIFICATION.md`، `PROJECT_STRUCTURE.md`، `EDUCATION_SYSTEM_API_CONTRACT_v1.md`، `BALE_PROVIDER_DISCOVERY.md` و `CURRENT_SYSTEM_BASELINE.md` کاملاً منطبق شدند.

## برنامهٔ Pilot زنده و ورودی‌های مورد نیاز

بخش توسعهٔ نرم‌افزاری و آفلاین کامل شده است. انجام Pilot زنده در حالت عملیاتی نیازمند فراهم شدن شرایط و تأیید صریح مالک در زمان اجرا است:
1. **حساب مبدأ بله:** شماره تلفن و دسترسی برای دریافت کد تایید و رمز عبور دومرحله‌ای (بدون ثبت در اسناد و لاگ‌ها).
2. **مخاطب آزمایشی مجاز:** شماره تلفن و نام مخاطب آزمایشی مورد تأیید مالک برای تست `add_contact_by_phone` و متعاقباً `remove_contact`.
3. **تأییدیهٔ ارسال پیام آزمایشی:** تعیین دقیق متن و گیرندهٔ پیام آزمایشی برای بررسی `send_text` و بازخوانی (read-back).
4. **محیط اجرایی:** در نبود این ورودی‌ها وضعیت در سطح `OFFLINE_COMPLETE / LIVE_PENDING_INPUT` باقی می‌ماند.

## وضعیت پیش‌نیاز فاز بعدی (کلاینت وب — فاز P1)

با تکمیل کلیهٔ بخش‌های B0 تا B6 و پایداری قراردادهای بله، نیازمندی‌های پایه برای مأموریت‌های برنامهٔ کلاینت وب (`WEB_CLIENT_PROGRAM.md`) فراهم گردیده است:
- مدل مرجع‌های نوع‌دار بله (`bale:user:...`) و ایتا آمادهٔ ادغام در پروفایل‌های فرستندهٔ P1 هستند.
- سرویس M2M دارای endpoint رسمی `prepare` و `resolve` جهت استفاده در خط لولهٔ OTP است.
- نخستین اقدام پس از این مرحله: شروع فاز P1 کلاینت وب طبق `WEB_CLIENT_PHASE_01_CONTRACT_SENDER_PROFILE.md`.

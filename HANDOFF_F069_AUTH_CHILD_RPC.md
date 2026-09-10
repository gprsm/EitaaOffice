# HANDOFF — F-069: مهاجرت چرخهٔ Auth به Child RPC (rc6)
**تاریخ:** 2026-09-09 · **وضعیت:** اصلاح کامل، تست‌شده، بستهٔ تحویل ساخته‌شده، **کامیت‌شده** — **منتظر تأیید روی رایانهٔ هدف**

## ثبت نسخه (Commits)
| مخزن | کامیت | محتوا |
|---|---|---|
| `D:\eitaa Project\AntiGravity2` (درخت ساخت، شاخه main) | `0c0d1257` | fix(auth): مهاجرت کامل چرخهٔ auth به Child RPC — ۹ فایل، +1565/-14 |
| `D:\eitaa Project\Eitaa_Bridge\Eitaa_Bridge` (درخت توسعه، مخزن جدید main) | `86dcad7` | baseline کامل درخت + اصلاح F-069 — ۴۶۹ فایل |
| `D:\eitaa Project\Eitaa_Bridge\delivery-activation-branch` (مخزن جدید main) | `b443cfa` | شناسنامهٔ تحویل rc6: manifest، چک‌سام‌ها، README، گواهی (بدون باینری‌ها) |


---

## ۱. مشکل اولیه (گزارش کاربر)
بعد از نصب rc5 روی رایانهٔ هدف: فعال‌سازی ✅ → ثبت مدیر اول ✅ → افزودن حساب ایتا ✅ → دکمهٔ «شروع Worker» ✅ → **صفحهٔ ورود شمارهٔ موبایل با خطا شکست می‌خورد:**
```
This API route has not been migrated to a DTO-based Child RPC.
```

## ۲. ریشهٔ مشکل
- بستهٔ rc5 با `worker_process.enabled=true` توزیع شده بود ( RC5_DELIVERY_MANIFEST.json → packaged_features).
- با این flag فعال، runtime حساب از نوع `EitaaProcessRuntime` است و gate در `api.py` (تابع `dispatch`) **همهٔ مسیرهای v1 به‌جز `GET /api/v1/scheduler/status`** را fail-closed می‌کرد، چون هنوز به Child RPC مهاجرت داده نشده بودند.
- فرانت‌اند (`App.tsx`) بلافاصله بعد از Start از مسیرهای `/api/v1/auth/*` استفاده می‌کند (request-code, submit-code, submit-password, status, ...) → همه بلاک می‌شدند.

## ۳. راه‌حل پیاده‌شده
کل چرخهٔ ورود به‌صورت DTO-based RPC به فرایند Child منتقل شد:

| لایه | فایل | تغییر |
|---|---|---|
| Child (اجرا) | `application/eitaa_auth_child_operations.py` | **ماژول جدید** — کل ماشین حالت چالش ورود: status, request_code, submit_code, submit_password, reset_local_session, logout (منطق عیناً از `_auth_*_account` در api.py) |
| Child (dispatch) | `application/eitaa_provider_worker.py` | ۶ متد `eitaa.auth.*` + `_require_auth_operations` + ساخت `EitaaAuthChildOperations` در `eitaa.runtime.start` |
| والد (پروکسی) | `application/process_runtime.py` | `auth_operation_request()` + `_AUTH_OPERATION_METHODS` allowlist |
| دروازه v1 | `application/api.py` | gate اصلاح شد (`_is_migrated_process_auth_route`)، ۶ تابع `_auth_*` به Child فوروارد می‌کنند (`_process_auth_request`)، recover-phone-identity سمت والد ماند (DPAPI key swap) |
| زیرساخت Child | `application/account_runtime.py` در `account_process()` | اتصال `CoordinatorDatabase` + `WindowsDpapiPhoneProtector` به runtime در Child (SQLite مشترک با busy_timeout=30s — safe) |
| تست | `tests/test_auth_child_rpc_regression.py` | ۷ تست جدید: spawn واقعی Child + تمام مسیرهای auth |
| تست (به‌روز) | `tests/test_phase7b_eitaa_process_runtime.py` | انتظار `auth/status == 200` (قبلاً 400 بود) |

### نکات امنیتی مهم (در صورت بازبینی)
- کلید IPC payload `password` و `session` ممنوع است (`_FORBIDDEN_PAYLOAD_KEYS` در `worker_ipc/protocol.py`) → در RPC از `credential` و `session_snapshot` استفاده شد و در api.py دوباره به نام اصلی نگاشت می‌شود.
- تمام متدهای `eitaa.auth.*` فقط با fence (worker_instance_id + generation) قابل فراخوانی‌اند (`_require_runtime_fields`).
- `eitaa_auth_child_operations.py` برای `_is_invalid_session_error` و `_normalize_login_code` از `BridgeApplicationApi` ایمپورت می‌کند — import chain تست‌شده و بدون حلقه است (factory در `providers/registry.py` lazy است).

## ۴. اعتبارسنجی انجام‌شده
- **درخت `D:\eitaa Project\Eitaa_Bridge\Eitaa_Bridge`** (توسعه): ۶۷۲ passed / 0 failed — به‌جز ۲۱ مورد pre-existing مربوط به UI theme/docs که قبل از این کار هم fail بودند (فایل theme.ts از 20 آگوست دست‌نخورده؛ تست‌ها رنگ قدیمی `#0a0f15` می‌خواهند ولی فایل `#0b1016` دارد).
- **درخت `D:\eitaa Project\AntiGravity2`** (ساخت واقعی rc5 — شامل licensing + F-068): **۷۶۸ passed / 0 failed** کامل. wheel rebuild شد.
- تست E2E با Child واقعی: auth/status=200، reset-local-session=200، logout=200، challenge state درست، مسیرهای مهاجرت‌نشده هنوز gated.
- تست درون‌روندی: `request_code` تا **سرور واقعی ایتا** رفت (خطای `PHONE_NUMBER_BANNED` برای شمارهٔ ساختگی = زنجیرهٔ DPAPI→phone→EitaaAuth→شبکه کاملاً سالم).
- wheel داخل بستهٔ پورتابل باز و تأیید شد: ماژول جدید + هر ۴ تغییر داخل آن موجود است.

## ۵. بستهٔ تحویل rc6 — آماده
مسیر: `D:\eitaa Project\Eitaa_Bridge\delivery-activation-branch\rc6-authchildrpc-internal-signed\`

| فایل | SHA-256 (پیشوند) |
|---|---|
| `EitaaBridge-0.8.0-rc6-AuthChildRpc-InternalSigned-GuiSetup-x64.exe` (۳۱.۴MB) | `217a128c…` |
| `EitaaBridge-0.8.0-rc6-AuthChildRpc-SelfContained-Portable.zip` (۳۰.۶MB) | `145bd6a3…` |
| `EitaaBridge-0.8.0-rc6-AuthChildRpc-Delivery.zip` (بستهٔ کامل ۶۱.۵MB شامل همه + manifest + trust) | — |
| `RC6_DELIVERY_MANIFEST.json` · `README_FIRST_FA.md` · `SHA256SUMS.txt` | — |

- امضای داخلی با همان گواهی rc5: thumbprint `441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`، tamper detection پاس.
- بیلد با `BUILD_OFFICE_SETUP_EXE.bat` (نام خروجی‌ها در آن از rc5 به rc6 تغییر کرد)؛ rc5 قبلی به `release\office\archive\20260909-122111` آرشیو شد.

## ۶. قدم‌های بعدی (به ترتیب)
1. **نصب rc6 روی رایانهٔ هدف (نصب تمیز):** اجرای GuiSetup → فعال‌سازی → مدیر اول → افزودن حساب → Start Worker → **این‌بار صفحهٔ ورود شمارهٔ موبایل باید باز شود و کد ایتا ارسال شود.** اگر خطای شبکه دیدید اتصال اینترنت رایانهٔ هدف را چک کنید (خطای سرور ایتا فارسی است: «ارتباط سرویس محلی با سرور ایتا برقرار نشد...»).
2. ✅ انجام شد (۱۴۰۵/۰۶/۱۸): `RELEASE_MANIFEST.json` هر دو درخت به rc6 به‌روز شد (branch_candidate، چک‌سام نصاب/پورتابل/wheel واقعی بیلد، شرح F-069، نتیجهٔ تست ۷۶۸/۰).
3. بعد از تأیید رایانهٔ هدف: آرشیو رسمی rc6 به سبک `rc5-multiaccount-internal-signed-rev2` در delivery-activation-branch، ثبت نتیجهٔ تست در `user_acceptance_recorded_at`، و (پیشنهاد بلندمدت) git کردن رسمی/اتحاد دو درخت برای جلوگیری از واگرایی دستی.

## ۷. نقشهٔ فایل‌های تغییر‌یافته (هر دو درخت)
- `src/eitaa_bridge/application/eitaa_auth_child_operations.py` **(جدید)**
- `src/eitaa_bridge/application/eitaa_provider_worker.py`
- `src/eitaa_bridge/application/process_runtime.py`
- `src/eitaa_bridge/application/account_runtime.py`
- `src/eitaa_bridge/application/api.py`
- `tests/test_auth_child_rpc_regression.py` **(جدید)**
- `tests/test_phase7b_eitaa_process_runtime.py`
- (فقط AG2) `BUILD_OFFICE_SETUP_EXE.bat` — نام rc6
- (فقط Eitaa_Bridge) `dist/eitaa_bridge-0.7.0.dev31-py3-none-any.whl` — rebuild
- (فقط AG2) `dist/…dev31…whl` — rebuild

## ۸. نکتهٔ محیط برای جلسهٔ بعد
- venv ساخت: `D:\eitaa Project\AntiGravity2\.venv\Scripts\python.exe` (Python 3.13.14) — برای تست/بیلد AG2 حتماً همین استفاده شود.
- درخت توسعه: پایتون سراسری 3.14 + `eitaa_core` wheel نصب‌شده در user site (از `vendor/`).
- گواهی امضا در `Cert:\CurrentUser\My` موجود است؛ env var لازم برای بیلد: `EITAA_CODE_SIGNING_THUMBPRINT=441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`.

---

# پیوست — اصلاح rc6a: خطای «The Eitaa Child rejected the request» در مرحلهٔ تأیید کد
**تاریخ:** 2026-09-09 (پس از تست واقعی RC6 روی ماشین مجازی) · **وضعیت:** اصلاح‌شده و تست‌شده در هر دو درخت — **منتظر rebuild بستهٔ تحویل و تست مجدد روی ماشین هدف**

## ۱. علامت در تست واقعی
نصب ✅ → فعال‌سازی ✅ → مدیر اول ✅ → Start Worker ✅ → request-code (یک خطای گذرا، سپس موفق و ارسال OTP) → **submit-code همیشه با 400 و `ipc_worker_internal_error` رد شد** (۱۱ بار، هر بار ~30ms — بدون تماس شبکه). در UI به‌صورت «The Eitaa Child rejected the request.» دیده شد.

## ۲. ریشهٔ مشکل
در `application/eitaa_auth_child_operations.py` (کد Child):
- خط ۴۹۶: `BridgeApplicationApi._normalize_login_code(code)`
- خط ۵۱۶: `BridgeApplicationApi._provider_login_code_failure(exc)`

اما این دو تابع در `api.py` **در سطح ماژول** تعریف شده‌اند (خط ۱۶۲ و ۱۹۱)، نه staticmethod روی کلاس `BridgeApplicationApi` (فقط `_is_invalid_session_error` staticmethod است). نتیجه: `AttributeError` که BridgeError نیست → در حلقهٔ `provider_worker.py` به `except Exception` خام می‌افتد → `ipc_worker_internal_error`. چون این خطا در **خط اولِ** submit_code رخ می‌دهد، هرگز به سرور ایتا نمی‌رسد (توضیح‌دهندهٔ 30ms).

تست رگرسیون قبلی فقط «خطای gate قدیمی نباشد و status در {200,400} باشد» را چک می‌کرد، پس 400 بودنِ همین کرش از زیر آن رد شد.

## ۳. اصلاح (هر دو درخت)
- `src/eitaa_bridge/application/eitaa_auth_child_operations.py`: دو ارجاع به توابع ماژول-سطح تبدیل شد (`_normalize_login_code` / `_provider_login_code_failure`) و import به‌روز شد.
- `tests/test_auth_child_rpc_regression.py::test_submit_code_routes_to_child_challenge_flow`: حالا صریحاً `error_code not in {ipc_worker_internal_error, eitaa_process_request_failed}` را assert می‌کند.
- wheel هر دو درخت rebuild شد (parity test پاس).

## ۴. اعتبارسنجی
- بازتولید مستقیم روی **بستهٔ پورتابل rc6 واقعیِ تحویل‌شده** (پایتون 3.13 خود بسته): AttributeError تأیید شد؛ پس از کپی فایل اصلاح‌شده، ماژول سالم import و نرمال‌سازی ارقام فارسی (`۱۲۳۴۵` → `12345`) کار کرد.
- شبیه‌سازی کامل سناریوی VM با Child واقعی: submit-code بدون challenge فعال → `400 api_auth_challenge_missing` (خطای تایپ‌شدهٔ صحیح، نه کرش IPC).
- مجموعهٔ تست AG2: همهٔ تست‌های مربوطه پاس (auth child RPC، phase7b، lifecycle، clean-install، packaging parity). دو تست ناموفوق در `test_runtime_ownership.py` و `test_ui33_usage_reading_position.py` **از قبل** روی کامیت be822771 بدون این تغییرات هم fail بودند (با git stash بررسی شد) — نامرتبط با این اصلاح.

## ۵. قدم‌های بعدی (به ترتیب)
1. rebuild بستهٔ تحویل با `BUILD_OFFICE_SETUP_EXE.bat` در AG2 (env var امضا لازم است) — خروجی به‌عنوان **rc6a** یا rev2 برچسب بخورد.
2. نصب تمیز rc6a روی ماشین هدف و تکرار همان سناریو: فعال‌سازی → مدیر → حساب → Start Worker → ورود شماره → **تأیید کد OTP**.
3. اگر تأیید شد: آرشیو رسمی در delivery-activation-branch، به‌روزرسانی manifest/checksum، ثبت `user_acceptance_recorded_at`.

## پیوست rc6a — بیلد ۲ (۲۰۲۶-۰۹-۱۰)
- تست کامل درخت ساخت قبل از بیلد: ۷۶۶ passed / 0 failed (۲ تست pre-existing نامرتبط — `test_runtime_ownership` و `test_ui33_usage_reading_position` — که روی کد be822771 بدون این اصلاح هم fail بودند).
- بیلد با `BUILD_OFFICE_SETUP_EXE.bat /quiet` + `EITAA_CODE_SIGNING_THUMBPRINT=441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02` انجام شد؛ نام خروجی‌ها در اسکریپت به **rc6a** تغییر کرد.
- خروجی‌ها در `D:\eitaa Project\AntiGravity2\release\office\`:
  - `EitaaBridge-0.8.0-rc6a-AuthChildRpc-InternalSigned-GuiSetup-x64.exe` — SHA-256 `05145214E31E285AE059D8BE13DAD6C52C78747DFEC92DA3BAEB52ED30E89F56`
  - `EitaaBridge-0.8.0-rc6a-AuthChildRpc-SelfContained-Portable.zip` — SHA-256 `a41d23fd1d504afcfd0d7197d7a181e896d5b7c595fd3c31ee38044e1ffee7e7`
- امضا: گواهی `CN=Eitaa Bridge Internal Publisher`، thumbprint `441692B49B8EF9C6FAC070CC18FB8B5A6C13BD02`، tamper-detection پاس. SignatureStatus `UnknownError` همان وضعیت عادی rc6 قبلی است (گواهی internal self-signed، غیر member-store).
- صحت‌سنجی محتوای بسته: پورتابل استخراج شد؛ ماژول `eitaa_auth_child_operations.py` نسخهٔ اصلاح‌شده را دارد (ارجاع‌های خراب حذف‌شده، نرمال‌سازی ارقام فارسی با پایتون 3.13 خود بنده سالم: `۱۲۳۴۵` → `12345`).
- release قبلی rc6 به `release\office\archive\20260910-062707` آرشیو شد.
- باگِ rc6 داخل این بسته دیگر وجود ندارد — آمادهٔ نصب تمیز روی ماشین مجازی و تکرار سناریو تا مرحلهٔ تأیید کد OTP.

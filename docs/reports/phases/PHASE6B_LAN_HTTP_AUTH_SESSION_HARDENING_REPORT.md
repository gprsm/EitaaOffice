# گزارش فاز ۶-B: مقاوم‌سازی Auth، Session و HTTP در LAN

تاریخ تکمیل: ۲۰۲۶-۰۸-۱۰  
وضعیت: پیاده‌سازی و آزمون تکمیل شد؛ فعال‌سازی واقعی انجام نشد  
مرز توقف: پایان Phase 6-B؛ Phase 6-C آغاز نشده است

## نتیجهٔ اجرایی

Hardening محدود به `trusted_lan_http` برای Session، CSRF، Host/Origin، Login throttling، Header/Cache، Request/Upload abuse و Logging تکمیل شد. Session موفق Login همیشه با Token و CSRF جدید صادر می‌شود و Cookie ورودی به نشست کاربر دیگری ارتقا پیدا نمی‌کند. تغییر واقعی Role یا Status تمام نشست‌های فعال کاربر را باطل می‌کند و Logout-all کاربر و Revoke همهٔ نشست‌های یک کاربر توسط مدیر نیز بدون ساخت UI مدیریت Device/Session اضافه شد.

Idle timeout و Absolute timeout سمت سرور و Fail-closed باقی ماندند. JSON و Media خصوصی `no-store` شدند، Headerهای امنیتی تکمیل شدند، Origin برای همهٔ درخواست‌های تغییردهنده در LAN الزامی شد، Brute-force علاوه بر AppUser و کل نصب با Bucket پایدار Client LAN محدود شد، و Request/Upload rate/size/content-type در مرز LAN کنترل شد.

هیچ LAN Port یا Firewall rule واقعی باز یا اعمال نشد. هیچ Windows launcher، LAN service یا Health/Readiness عملیاتی فاز ۶-C ساخته نشد. هیچ Login/Logout/OTP/Status/Send واقعی Eitaa انجام نشد و هیچ API یا Capability برای Bale، Rubika یا SoroushPlus حدس زده نشد.

## اسناد لازم‌الاجرا و baseline پیش از تغییر

پیش از هر تغییر این دو سند کامل خوانده شدند:

- `ARCHITECTURE_DECISIONS.md`
- `PHASE6A_TRUSTED_LAN_HTTP_CONFIGURATION_REPORT.md`

Worktree عمداً dirty بود و همهٔ تغییرات و فایل‌های قبلی حفظ شدند. هیچ `reset`، `checkout`، `commit` یا `push` انجام نشد.

Baseline متمرکز پیش از تغییر:

```text
57 passed
```

فایل‌های baseline:

```text
tests/test_config.py
tests/test_app_user_auth.py
tests/test_app_user_api.py
tests/test_http_api_media.py
tests/test_phase6a_trusted_lan_http.py
```

هیچ تصمیم کلان جدیدی خارج از قرارداد canonical لازم نشد؛ بنابراین `ARCHITECTURE_DECISIONS.md` در Phase 6-B تغییر نکرد. Logout-all، Revoke، invalidation پس از تغییر دسترسی و کنترل‌های abuse تکمیل همان قرارداد امنیتی ثبت‌شده بودند، نه گسترش مدل معماری.

## تصمیم‌های امنیتی Phase 6-B

### Session rotation و fixation

- Token هر Session با منبع تصادفی رمزنگاری‌شدهٔ مستقل ساخته می‌شود و فقط SHA-256 آن در Coordinator ذخیره می‌ماند.
- Login موفق بدون توجه به Cookie ورودی Session جدید صادر می‌کند؛ Token قبلی reuse یا elevate نمی‌شود.
- CSRF به همان Session bind است و CSRF یک Session یا AppUser برای Session دیگر پذیرفته نمی‌شود.
- تغییر واقعی `global_role` یا `status` همهٔ Sessionهای فعال Target را با reason امن `app_user_access_changed` باطل می‌کند. کاربر برای دریافت Principal جدید باید دوباره Login کند؛ این invalidation از نگه‌داشتن Session قدیمی با privilege تازه ایمن‌تر است.
- تغییر Password همچنان همهٔ Sessionهای دیگر همان کاربر را باطل می‌کند و Session جاری را طبق قرارداد قبلی نگه می‌دارد؛ Password change در این فاز Access-level change محسوب نشد.

### Timeout، Logout-all و Revoke

- Idle و Absolute expiry فقط از Timestampهای سمت سرور محاسبه می‌شوند؛ Idle هرگز از Absolute عبور نمی‌کند.
- Timestamp خراب یا بدون timezone Fail-closed رد می‌شود.
- `POST /api/v2/app-auth/logout-all` همهٔ Sessionهای فعال AppUser جاری، شامل Session جاری، را باطل و Cookie را پاک می‌کند.
- `POST /api/v2/app-users/{app_user_id}/revoke-sessions` فقط برای Admin فعال است و بدون افشای Device metadata همهٔ Sessionهای Target را باطل می‌کند.
- Logout تک‌نشستی موجود حفظ و دوباره آزموده شد.
- فهرست Sessionها، Device metadata و UI مدیریت آن‌ها عمداً برای Phase 9-C باقی ماند.

### Cookie و محل نگهداری Auth material

- Cookie نشست همچنان فقط با این قرارداد صادر می‌شود:

```text
Path=/; HttpOnly; SameSite=Strict
```

- `Domain` تنظیم نمی‌شود و Session token داخل JSON response قرار نمی‌گیرد.
- در HTTP cleartext امکان استفادهٔ مؤثر از `Secure` وجود ندارد؛ نبود `Secure` صریحاً در راهنمای LAN ثبت شد و هیچ ادعای HTTPS-equivalent مطرح نمی‌شود.
- Session/Credential از URL یا Query String خوانده نمی‌شود. تست کرد که قرار دادن Cookie token در Query موجب Authentication نمی‌شود.
- ممیزی Source رابط نشان داد Auth token، CSRF، Password یا Credential در `localStorage`/`sessionStorage` نوشته نمی‌شود. CSRF فقط در حافظهٔ Runtime رابط نگه داشته می‌شود.

### CSRF و روش‌های HTTP

- پس از Login، همهٔ Routeهای state-changing که از Dispatcher یا Upload boundary عبور می‌کنند CSRF همان Session را لازم دارند.
- Setup و Login Session قبلی ندارند؛ در LAN به Origin دقیق نیاز دارند و Setup علاوه بر آن Loopback-only است.
- Missing/invalid/cross-user/cross-session CSRF و Replay پس از Logout/Revoke/Timeout رد می‌شوند.
- CSRF فعلی یک synchronizer token نشست‌محور است، نه nonce یک‌بارمصرف. بنابراین reuse در طول همان Session معتبر قرارداد فعلی است؛ مهاجم قادر به شنود HTTP می‌تواند تا زمان اعتبار Session آن را Replay کند. این ریسک با HTTP cleartext حذف‌شدنی نیست.
- `HEAD` بدون اجرای Application code با `405` رد می‌شود. `GET` روی Routeهای Logout/Mutation عملیات را اجرا نمی‌کند. تمدید server-side Idle در درخواست authenticated، Activity bookkeeping است و تغییر Business/Auth lifecycle محسوب نمی‌شود.

### Host، Origin، CIDR و CORS

- Host فقط پس از parse و normalization دقیق Authority پذیرفته می‌شود.
- wildcard، userinfo، path، slash/backslash، comma، semicolon، whitespace/control character، Header تکراری، Host جعلی و Port نامعتبر رد می‌شوند.
- IPv4 و IPv6 bracket/compression/port normalization adversarial آزموده شد.
- Origin موجود در GET نیز باید معتبر باشد و Cross-origin رد می‌شود.
- تمام `POST/PUT/PATCH/DELETE` در `trusted_lan_http`، حتی از Client loopback، Origin دقیق same-origin می‌خواهند.
- `OPTIONS` بدون انتشار `Access-Control-Allow-Origin` پاسخ می‌گیرد؛ CORS عمومی یا wildcard اضافه نشد.
- Client IP فقط از Socket خوانده می‌شود و `X-Forwarded-For` مبنای CIDR یا Rate-limit نیست.
- رفتار `desktop_loopback` برای Missing Origin در Client loopback و Limitهای عملیاتی قبلی حفظ شد. تنها Origin حاضر باید واقعاً با Host همان Request same-origin باشد.

### Login brute-force و lockout

- Bucket پایدار AppUser/Subject قبلی حفظ شد؛ تغییر Client، Account یا Provider آن را دور نمی‌زند.
- Bucket سراسری نصب قبلی حفظ شد.
- برای HTTP LAN، Bucket پایدار Client IP نیز اضافه شد. IP ابتدا canonical و سپس با secret نصب HMAC می‌شود؛ IP خام در Coordinator یا Audit ذخیره نمی‌شود.
- Client با جابه‌جایی میان Usernameها نمی‌تواند از سقف `max_failed_attempts` عبور کند؛ AppUser نیز با جابه‌جایی Client از Bucket خودش عبور نمی‌کند.
- Provider messaging rate limit وارد این فاز نشد و برای Phase 8-C باقی ماند.

### Header، Cache و حفاظت Browser

پاسخ‌های JSON، Auth/Session، Runtime JSON و Media خصوصی این کنترل‌ها را دریافت می‌کنند:

- `Cache-Control: no-store, max-age=0`
- `Pragma: no-cache`
- `Content-Security-Policy` محدود برای JSON/Media
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy`
- `X-Content-Type-Options: nosniff`
- `Cross-Origin-Resource-Policy: same-origin`
- `X-Permitted-Cross-Domain-Policies: none`
- `X-XSS-Protection: 0`

UI موجود CSP جدا با `default-src 'self'`، منع Frame/Object/Base و Script فقط از `self` دارد. `style-src 'unsafe-inline'` برای Styleهای Runtime فعلی حفظ شد تا Electron/Loopback شکسته نشود؛ Inline script مجاز نشده است. فایل‌های static versioned می‌توانند cache عمومی immutable داشته باشند، اما `index.html`، API و Media خصوصی `no-store` هستند.

### Request و Upload abuse controls

- JSON body: سقف موجود ۲ MiB و الزام `application/json` برای body غیرخالی حفظ شد.
- `Transfer-Encoding` برای JSON و Upload رد می‌شود؛ Adapter فقط `Content-Length` صریح را پشتیبانی می‌کند.
- Upload در `trusted_lan_http`: حداکثر ۱۲۸ MiB و فقط `application/octet-stream`.
- سقف عمومی LAN: ۲۴۰ Request در ۶۰ ثانیه برای هر Socket IP.
- سقف Upload LAN: ۱۲ Upload در ۶۰ ثانیه برای هر Socket IP.
- Limiter حافظهٔ محدود دارد و فقط در `trusted_lan_http` فعال است؛ Limit قبلی Loopback تغییر نکرد.
- Rate limiter عمومی با Restart پاک می‌شود و تنظیمات ثابت آن هنوز UI/Config عملیاتی ندارد. Login throttle امنیتی در SQLite پایدار است. تنظیم عملیاتی و Service lifecycle در مرز ۶-C بررسی می‌شود.

### Cross-user isolation و Logging

- دو AppUser، دو Client address، دو Cookie و دو CSRF مستقل در دادهٔ Fake/Local ساخته شدند.
- `/me` حتی با `app_user_id` جعلی در Query فقط Principal صاحب Cookie را برگرداند.
- AppUser بدون Membership نتوانست MessengerAccount متعلق به AppUser مجاز را ببیند یا Status آن را بخواند.
- CSRF یک Client با Cookie Client دیگر رد شد و Session قربانی معتبر باقی ماند.
- Login با Cookie AppUser دیگر آن Cookie را elevate نکرد.
- مسیرهای Log به Route shape امن تبدیل شدند و identifier/segment ناشناخته یا high-entropy ثبت نمی‌شود.
- Console HTTP دیگر Request line، URL یا Query را روی خطا ثبت نمی‌کند و فقط Status امن می‌نویسد.
- Redaction برای `session_token`، `csrf_token`، OTP، Set-Cookie، API key/client secret، فهرست Phone و private message تقویت شد.
- Password، OTP، Token، Cookie/Session ID کامل، Secret، IP خام Client، Full phone و Private message content در Audit/Runtime log ثبت نشدند.

## فایل‌های تغییرکرده در Phase 6-B

کد:

- `src/eitaa_bridge/infrastructure/coordinator/app_auth.py`
- `src/eitaa_bridge/application/api.py`
- `src/eitaa_bridge/interfaces/http_api.py`
- `src/eitaa_bridge/infrastructure/diagnostics/redaction.py`

نکتهٔ baseline در زمان پیاده‌سازی: الگوی `diagnostics/` در خط ۱۳ `.gitignore` کل مسیر `src/eitaa_bridge/infrastructure/diagnostics/` را نیز Ignore می‌کرد؛ بنابراین تغییر `redaction.py` با وجود حضور و استفادهٔ واقعی در پروژه، در `git status` دیده نمی‌شد. این مورد در Closeout محدود Repository Hygiene همین گزارش تعیین تکلیف و بسته شد.

تست:

- `tests/test_phase6a_trusted_lan_http.py` — قرارداد Origin برای Bootstrap loopback در LAN به شرط سخت‌تر ۶-B به‌روزرسانی شد.
- `tests/test_phase6b_lan_http_auth_session_hardening.py` — فایل جدید با ۱۲ تست adversarial.

مستندات:

- `docs/TRUSTED_LAN_HTTP_CONFIGURATION.md`
- `PHASE6B_LAN_HTTP_AUTH_SESSION_HARDENING_REPORT.md`

`ARCHITECTURE_DECISIONS.md`، Config واقعی `bridge.json`، Feature Flagهای نصب، Coordinator/Contacts/Session/Runtime واقعی و فایل‌های UI در این فاز تغییر نکردند.

## آزمون‌های اختصاصی Phase 6-B

فایل `tests/test_phase6b_lan_http_auth_session_hardening.py` شامل این تست‌هاست:

1. `test_login_replaces_supplied_cookie_and_csrf_is_session_bound`
2. `test_idle_and_absolute_timeouts_fail_closed_server_side`
3. `test_logout_all_admin_revoke_and_access_change_invalidate_sessions`
4. `test_lan_client_and_subject_login_throttles_cannot_be_bypassed`
5. `test_trusted_lan_host_origin_adversarial_ipv4_normalization`
6. `test_trusted_lan_ipv6_host_origin_normalization`
7. `test_trusted_lan_rate_limiter_is_client_and_bucket_scoped`
8. `test_http_lan_headers_cookie_head_upload_controls_and_safe_logging`
9. `test_two_clients_cannot_cross_session_private_scope_or_impersonate`
10. `test_auth_audit_excludes_credentials_tokens_client_ip_and_private_content`
11. `test_runtime_redaction_covers_auth_material_phone_lists_and_private_messages`
12. `test_auth_material_is_not_persisted_in_browser_storage`

همهٔ تست‌ها با دادهٔ موقت و Fake/Local اجرا شدند. Socketهای Integration test فقط روی `127.0.0.1` و Port موقت بودند؛ هیچ Socket روی LAN باز نشد و هیچ Provider RPC واقعی فراخوانی نشد.

## نتایج آزمون و کنترل کیفیت

### Phase 6-B اختصاصی

```text
12 passed
```

### Focused نهایی

```text
69 passed
```

شامل Config، AppUser auth/API، HTTP media/upload، Phase 6-A و ۱۲ تست Phase 6-B.

### کل مجموعه بدون فیلتر

```text
400 collected
399 passed
1 failed
```

تنها شکست:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

### کل مجموعه با کنارگذاشتن فقط baseline تاریخی

```text
399 passed
1 deselected
```

### اجرای منفرد baseline تاریخی

```text
1 failed
```

Fixture همچنان مقدار لاتین زیر را می‌سازد:

```text
C:\Users\ExampleUser\Documents\Eitaa\runtime\edge-profile
```

اما Assertion انتظار suffix فارسی `Documents\ایتا\runtime\edge-profile` دارد. Diff این دو فایل خالی بود:

```text
tests/test_runtime_ownership.py
scripts/office_runtime.py
```

پس شکست مستقل، از قبل موجود و همان baseline ثبت‌شدهٔ Phase 6-A است.

کنترل‌های دیگر:

- `compileall` روی `src`، `tests` و `scripts`: موفق
- `git diff --check`: موفق
- Parse نمونه‌های `bridge.example.json`، `bridge.multisite.example.json` و `bridge.trusted-lan-http.example.json`: موفق
- Import و رفتار Redaction جدید: موفق
- Vite/TypeScript build: عمداً اجرا نشد، چون هیچ فایل UI در Phase 6-B تغییر نکرد و Suite پروژه نیز آن را الزام نکرد.

## وضعیت واقعی Feature Flag و نصب در پایان

Loader روی `bridge.json` واقعی:

```json
{
  "deployment_mode": "desktop_loopback",
  "bind_host": "127.0.0.1",
  "bind_port": 8765,
  "app_user_auth_enabled": false,
  "multi_session_enabled": false,
  "remote_messenger_auth_enabled": false
}
```

- `bridge.json` واقعی تغییر نکرد؛ اندازهٔ آن ۹۳۴ بایت و Timestamp آن همان `2026-07-25 03:45:49` باقی ماند.
- هیچ Feature واقعی فعال نشد.
- هیچ Migration یا تغییر دادهٔ Coordinator/Contacts/Session/Runtime واقعی انجام نشد.
- هیچ Login، Logout، OTP، Status یا Send واقعی Eitaa انجام نشد.
- هیچ Dependency جدیدی اضافه یا نصب نشد.
- هیچ Port LAN، Firewall rule، Port Forwarding، DMZ یا UPnP ایجاد یا تغییر نکرد.
- هیچ Commit یا Push انجام نشد.

## محدودیت HTTP و ریسک‌های باقی‌مانده

`trusted_lan_http` هنوز cleartext است. دستگاه یا تجهیزی که مسیر شبکه را ببیند یا تغییر دهد می‌تواند Username، Password، Cookie، CSRF، محتوای خصوصی و عملیات را مشاهده، سرقت یا Replay کند. Host/Origin/CIDR، Cookie flags، Lockout، CSP و CSRF این ریسک انتقال را حذف نمی‌کنند و امنیتی معادل HTTPS ایجاد نمی‌کنند.

ریسک‌ها و موارد عمداً باقی‌مانده:

- Cookie در HTTP نمی‌تواند `Secure` باشد.
- CSRF نشست‌محور در همان Session فعال یک‌بارمصرف نیست.
- Limiter عمومی Request/Upload با Restart پاک می‌شود و مقدارهای آن فعلاً ثابت‌اند.
- چند Client پشت یک IP، Bucket عمومی و Upload را مشترک دارند.
- UI فهرست Device/Session، نام‌گذاری Device، Last-used metadata و Revoke انتخابی Session برای Phase 9-C باقی ماند.
- TLS/HTTPS یا حفاظت مسیر شبکه در این فاز ساخته نشد.

## Closeout / Repository Hygiene

در Closeout محدود Phase 6-B، وضعیت Git مسیر `src/eitaa_bridge/infrastructure/diagnostics/redaction.py` بدون staging یا تغییر تاریخچه بررسی شد:

- پیش از اصلاح، `git ls-files --stage -- src/eitaa_bridge/infrastructure/diagnostics/redaction.py` خروجی نداشت؛ پس فایل tracked نبود.
- پیش از اصلاح، `git check-ignore -v` دقیقاً قاعدهٔ `.gitignore:13:diagnostics/` را برای خود فایل و پوشهٔ Source گزارش کرد.
- چون فایل هم untracked و هم ignored بود، تغییرات امنیتی Redaction در `git status` و diff معمول Git دیده نمی‌شدند و ریسک حذف از Commit/Release آینده واقعی بود.
- تنها اصلاح انجام‌شده در `.gitignore` تغییر `diagnostics/` به `/diagnostics/` بود. Slash ابتدایی قاعده را به پوشهٔ runtime/output ریشه محدود می‌کند؛ بنابراین `diagnostics/` و محتوای آن همچنان ignored هستند، اما هیچ پوشهٔ Source هم‌نام در زیر `src/` ناخواسته ignore نمی‌شود.
- پس از اصلاح، `git check-ignore -v -n` برای `diagnostics/` قاعدهٔ `.gitignore:13:/diagnostics/` را گزارش کرد و برای `src/eitaa_bridge/infrastructure/diagnostics/` و `redaction.py` خروجی non-matching (`::`) داد.
- پس از اصلاح، `redaction.py` و دیگر فایل‌های Source همان پوشه با `??` در `git status --untracked-files=all` دیده می‌شوند. `git ls-files` هنوز برای آن‌ها خالی است، زیرا طبق Scope هیچ `git add` یا Commit انجام نشد؛ وضعیت دقیق `redaction.py` اکنون **untracked but not ignored** و در نتیجه قابل نسخه‌گذاری است.
- Worktree dirty و همهٔ تغییرات قبلی کاربر حفظ شدند. هیچ `reset`، `checkout`، `git add`، `commit` یا `push` انجام نشد.

اعتبارسنجی Closeout:

```text
Import مستقیم redaction.py از src و probe رفتاری: موفق
Diagnostics/Redaction + Phase 6-B dedicated: 16 passed
Focused نهایی شامل Config/Auth/API/Media/Phase 6-A/Phase 6-B/Diagnostics: 73 passed
Full suite: 400 collected; 399 passed; 1 failed
Full suite excluding only historical baseline: 399 passed; 1 deselected
git diff --check: موفق
```

تنها شکست Full suite همان baseline تاریخی زیر باقی ماند:

```text
tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8
```

علت همچنان Fixture لاتین `Documents\Eitaa\runtime\edge-profile` در برابر انتظار suffix فارسی `Documents\ایتا\runtime\edge-profile` است. `git diff` برای `tests/test_runtime_ownership.py` و `scripts/office_runtime.py` خالی بود؛ بنابراین این شکست مستقل از Closeout و تغییر `.gitignore` است.

`ARCHITECTURE_DECISIONS.md` تغییر نکرد، چون این اصلاح صرفاً Repository hygiene بود و تصمیم معماری جدیدی ایجاد نکرد. `bridge.json` واقعی، Feature flagها، داده‌های واقعی، Network/Firewall، Provider login/send و مرزهای Phase 6-C نیز تغییر نکردند. با بسته‌شدن ریسک نسخه‌پذیری Source Diagnostics/Redaction و موفقیت کنترل‌های بالا، **Phase 6-B اکنون fully closed/accepted است**. Phase 6-C آغاز نشده است.

## مرز فازهای بعدی

### Phase 6-C

- سرویس‌دهی واقعی LAN و Windows launcher/service
- Health/Readiness و lifecycle عملیاتی
- طراحی و تأیید Firewall محدود به Subnet؛ هیچ Rule بدون تأیید صریح اعمال نشود
- تنظیمات عملیاتی Rate/Upload فقط در صورت نیاز روشن و بدون تضعیف fail-closed

### Phase 6-D

- Presentation shell موبایل و رفتار responsive/mobile-first طبق سند canonical
- بدون تغییر Source of Truth یا قرارداد Provider

### Phase 9-C

- فهرست Device/Session metadata امن
- UI مدیریت Session، Revoke انتخابی و Logout-all قابل مشاهده
- بدون نمایش Token، Cookie یا Session ID کامل

## دستور دقیق و کوتاه آغاز Phase 6-C

```text
فاز ۶-C پروژه Eitaa Bridge را اجرا کن. ابتدا ARCHITECTURE_DECISIONS.md و PHASE6B_LAN_HTTP_AUTH_SESSION_HARDENING_REPORT.md را کامل بخوان، Worktree dirty و bridge.json واقعی را حفظ کن، و فقط سرویس‌دهی عملیاتی trusted_lan_http، Windows launcher/service، Health/Readiness و طرح Firewall محدود به Subnet را تکمیل و تست کن؛ هیچ Firewall rule یا Port واقعی را بدون تأیید صریح اعمال نکن، هیچ Provider/Login/OTP/Send واقعی یا MobileShell/Unified Inbox نساز، commit/push نکن، در پایان گزارش مستقل ۶-C بساز و متوقف شو.
```

Phase 6-B در این نقطه پایان یافته است.

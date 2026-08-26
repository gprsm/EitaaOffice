# Application API v1

## Purpose

The API is the stable local boundary used by the Electron UI. It exposes only public Core and Bridge facades and returns JSON. Electron communicates through its isolated preload process, so the renderer does not require permissive CORS or Node integration.

## UI flow

1. `auth/status` selects the login gate or workspace.
2. staged auth endpoints perform phone, code, and optional 2FA login.
3. `dialogs/list` discovers dialogs and creates reusable peer files.
4. `messages/sync` and `messages/list` provide scroll-based local history;
   grouped media include nullable `grouped_id` and local `album_size` metadata.
5. `messages/media-preview` provides bounded cached image previews.
6. category and tag endpoints populate WordPress controls.
7. composition endpoints Preview or create one WordPress post from ordered messages.
8. compositions and message usage endpoints provide used/stale UI state.
9. explicit local-index endpoints build and expose advisory category
   suggestions without making a WordPress write or using the Eitaa scheduler.

## Routes

```text
GET  /api/v1/health
GET  /api/v1/schema
GET  /api/v1/auth/status
POST /api/v1/auth/request-code
POST /api/v1/auth/submit-code
POST /api/v1/auth/submit-password
POST /api/v1/auth/logout
GET  /api/v1/sites
GET  /api/v1/capabilities
GET  /api/v1/compositions
GET  /api/v1/wordpress/categories
GET  /api/v1/wordpress/tags
POST /api/v1/dialogs/list
POST /api/v1/messages/list
POST /api/v1/messages/media-preview
POST /api/v1/messages/sync
POST /api/v1/messages/usage
POST /api/v1/messages/index/start
GET  /api/v1/messages/index/status
POST /api/v1/messages/index/cancel
POST /api/v1/messages/index/results
POST /api/v1/messages/index/feedback
POST /api/v1/compositions/preview
POST /api/v1/compositions/status
POST /api/v1/compositions/publish
```

مسیرهای AppUser و چندحسابی در namespace نسخهٔ ۲ قرار دارند. مسیر افزوده‌شده در Phase 11-0:

```text
POST /api/v2/messenger-accounts
```

مسیرهای application عمومی Phase 11-B2:

```text
POST /api/v2/messenger-accounts/{messenger_account_id}/dialogs/query
POST /api/v2/messenger-accounts/{messenger_account_id}/history/query
POST /api/v2/messenger-accounts/{messenger_account_id}/messages/send-text
POST /api/v2/messenger-accounts/{messenger_account_id}/media/read
POST /api/v2/messenger-accounts/{messenger_account_id}/contacts/query
POST /api/v2/messenger-accounts/{messenger_account_id}/contacts/upsert
```

## Write safety

- Draft is the default.
- Publish requires `post_status=publish` and `confirm_publish=true`.
- WordPress `publish_posts` is checked before upload.
- already-used Eitaa sources block a new composition.
- media previews are limited and cached locally.
- login challenges stay in memory and secret challenge values never appear in JSON.
- local indexing has a 50,000-message hard cap, explicit progress/cancellation
  and staging-table promotion; its database contains hashes and suggestions,
  not raw message text.

## HTTP security

The backward-compatible default is `desktop_loopback`, but the effective bind is always read from
`deployment.bind`. Electron and the Office launcher derive their endpoint from the same Config and
do not pass a separate Host/Port override. The renderer uses Electron IPC, and desktop media uses a
private Electron protocol rather than a hard-coded HTTP endpoint.

`trusted_lan_http` is an explicit cleartext private-LAN profile. `web_reverse_proxy` keeps the
application backend on Loopback and requires exact HTTPS Host/Origin, a same-host trusted TLS
terminator, sanitized forwarded headers, Secure cookies, CSRF, HSTS and bounded lifecycle/resource
limits. Direct plain HTTP on port 443 is rejected. See
`docs/PHASE10_WEB_REVERSE_PROXY_DEPLOYMENT.md`.
# Multi-account onboarding (Phase 11-0)

`POST /api/v2/messenger-accounts` فقط با AppUser session و CSRF معتبر و در حالت `multi_session.enabled` پذیرفته می‌شود.

Body مجاز فقط شامل `provider`، `phone` canonical در قالب E.164 و `label` اختیاری است. هر فیلد دیگر، به‌ویژه شناسهٔ حساب یا مسیر Session/Storage، رد می‌شود. پاسخ `201` برای ساخت تازه و `200` برای retry idempotent همان مالک است و فقط card امن با شمارهٔ پوشیده برمی‌گرداند. Provider غیرفعال از catalog، پیش از پردازش هویت خصوصی رد می‌شود.

هیچ درخواست ساختی Worker را خودکار Start نمی‌کند و هیچ Credential، OTP یا رمز از این endpoint عبور نمی‌کند؛ مراحل Provider auth از endpointهای حساب‌محور موجود و فقط پس از انتخاب/Start صریح حساب اجرا می‌شوند.

## Provider descriptor (Phase 11-B0)

`GET /api/v2/messenger-accounts` در `provider_adapters` برای هر registration قابل نمایش، metadata امن زیر را برمی‌گرداند:

- `provider` و `display_name`؛
- `account_kind`؛
- `implementation_state`؛
- `configured`، `runtime_enabled` و `onboarding_enabled`؛
- `account_identity_kind` و `auth_steps`؛
- `capabilities`؛
- `reason_code` امن در وضعیت غیرفعال.

authorization reference، endpoint، credential، session material و جزئیات transport در API عمومی منتشر نمی‌شوند. UI فقط با پرچم‌ها و capabilityها تصمیم می‌گیرد؛ وجود نام Provider به معنی runnable/onboardable بودن آن نیست.

## Account capabilities (Phase 11-B1)

```text
GET /api/v2/messenger-accounts/{messenger_account_id}/capabilities
```

این مسیر فقط پس از AppUser authentication و کنترل دسترسی `view` همان MessengerAccount پاسخ می‌دهد. خروجی شامل provider، implementation state، runtime flag و فهرست تصمیم‌های امن زیر است:

- `capability`؛
- `status`: یکی از `supported/unsupported/unknown/restricted`؛
- `reason_code` امن؛
- وجود constraint بدون انتشار محتوای آن؛
- revision مشاهدهٔ حساب.

Manifest سقف اختیار است؛ رکورد account observation نمی‌تواند Capability اعلام‌نشده را supported کند. در حالت multi-session مسیرهای Dialog، History، Send، Media و Eitaa Contacts/افزودن مخاطب پیش از runtime به Capability متناظر نگاشت و fail-closed می‌شوند.

این endpoint هیچ Credential، Session material، endpoint Provider، raw constraint یا دادهٔ گفتگو/مخاطب برنمی‌گرداند.

## Provider-neutral operations (Phase 11-B2)

هر شش مسیر B2 فقط با AppUser session/CSRF معتبر اجرا می‌شوند. `messenger_account_id` مؤثر از route می‌آید، اما authorization با Membership سمت سرور انجام می‌شود. body نمی‌تواند account/provider/capability را override کند و فیلد زائد با `provider_operation_fields_rejected` رد می‌شود.

### Dialog query

Body مجاز: `site_key` اختیاری، `cursor` محدود و `limit` بین 1 تا 200. پاسخ فقط `peer_reference` opaque، `peer_kind`، عنوان محدود، unread count و cursor بعدی را دارد.

### History query

Body مجاز: `site_key`، `peer_reference`، `peer_kind`، `cursor` و `limit` بین 1 تا 500. پاسخ شامل referenceهای opaque، timestamp و متن bounded است؛ raw SDK/RPC object، access hash یا مسیر فایل منتشر نمی‌شود.

### Text send

Body مجاز: `site_key`، `peer_reference`، `peer_kind`، `text` محدود، `idempotency_key` صریح و `confirm=true`. نبود کلید با `provider_idempotency_key_required` و نبود تأیید دقیق با `provider_message_send_confirmation_required` رد می‌شود؛ سرور از correlation جدید کلید جایگزین نمی‌سازد. replay همواره authorization/capability/deadline را دوباره می‌سنجد. پاسخ وضعیت `succeeded/uncertain` و reason code امن دارد؛ `uncertain` خودکار تکرار نمی‌شود.

Receipt ارسال به AppUser، حساب، operation، idempotency key و fingerprint درخواست bind می‌شود. fingerprint متن را hash می‌کند و متن خام یا payload در جدول receipt ذخیره نمی‌شود. پس از restart، replay موفق Provider را دوباره فراخوانی نمی‌کند؛ claim منقضی‌شده به‌صورت terminal `uncertain` بسته می‌شود.

### Media read

Body مجاز: `site_key`، peer/message/media referenceهای opaque، `variant` و `max_bytes` محدود. پاسخ فقط content reference سرورساز، MIME و byte count دارد. در Process Runtime مسیر cache از Child خارج نمی‌شود؛ دانلود HTTP با chunkهای Base64 حداکثر 192 KiB، offset پیوسته و کنترل طول/MIME broker می‌شود.

### Contact query

Body مجاز: `site_key`، cursor و limit بین 1 تا 500. پاسخ فقط contact reference، display name محدود و identity hint پوشیده دارد؛ شمارهٔ کامل در hint معتبر نیست.

### Contact upsert

Body مجاز: `site_key`، identity خصوصی، display name، `idempotency_key` صریح و `confirm=true`. identity فقط داخل `SensitiveProviderValue` حمل و برای fingerprint hash می‌شود؛ در log/receipt خام ذخیره نمی‌شود. replay موفق پس از restart از receipt پایدار پاسخ می‌دهد و attempt ناقص بدون retry خودکار با reason امن رد می‌شود.

### مرز اجرا

این routeها قرارداد جدید و کامل‌اند و routeهای richer legacy v1 را نیمه‌کاره جایگزین نمی‌کنند. Eitaa in-process از compatibility adapter عبور می‌کند و `EitaaProcessRuntime` فقط RPCهای typed/allowlisted/fenced همان شش operation را می‌پذیرد. raw SDK object، access hash، session state و مسیر فایل از IPC عمومی عبور نمی‌کنند. هیچ‌کدام از این قراردادها Bale Personal runtime را فعال یا مجاز نمی‌کند.

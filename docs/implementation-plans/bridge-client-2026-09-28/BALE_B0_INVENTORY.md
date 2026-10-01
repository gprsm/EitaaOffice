# B0 — ماتریس اتصال کلاینت شخصی بله

تاریخ بررسی: 2026-09-28؛ revision آغاز: `ab7563c5`. این جدول وضعیت کد در آغاز مأموریت و نتیجهٔ بررسی آفلاین است؛ وجود متد façade شاهد پذیرش Live در برنامهٔ اصلی نیست. شاهد V-194 فقط سطح مستقل شاخهٔ Bale را پوشش می‌دهد.

| Backend façade | DTO عمومی | Worker method | Endpoint اصلی | UI اصلی | آزمون/شاهد آغاز | شکاف |
|---|---|---|---|---|---|---|
| `auth_start/auth_code/auth_password/connect` | `ProviderAuthOutcome` | ندارد | `/api/v1/auth/*` ایتامحور | Wizard ایتامحور | V-194 مستقل، V-216 Fake | vault مشترک پیش‌فرض، passphrase عمومی، نبود loop ماندگار/restore/account fence |
| `list_contacts/search_contacts` | `ProviderContactPage` | ندارد | `contacts/query` عمومی | دفترچهٔ ایتا | V-194 list/search مستقل | adapter بدون `list_contacts`، جستجوی account scoped عمومی ندارد |
| `add_contact_by_phone/add_contact/remove_contact` | `ProviderContactMutationReceipt`؛ remove ندارد | ندارد | `contacts/upsert`؛ remove ندارد | add/remove ایتامحور | V-194 شاهد mutation نیست | نتیجهٔ matched و replay و policy نام موجود باید آزموده شوند |
| `list_dialogs` | `ProviderDialogPage` | ندارد | `dialogs/query` عمومی | گفتگوهای v1 ایتامحور | V-195 مستقل | title/last_text و cursor عمومی ناقص |
| `read_history` | `ProviderMessagePage` | ندارد | `history/query` عمومی | گفتگوی v1 ایتامحور | V-194 read-back مستقل | نوع peer و media/cursor و polling |
| `send_text` | `ProviderSendReceipt` | ندارد | `messages/send-text` عمومی، M2M parser ایتا | quick send ایتامحور | V-194 مستقل | `random_id` message_id نیست؛ مرجع typed و runtime مستقل ندارد |
| `read_message_media/send_file_bytes` | media read DTO؛ media send عمومی ندارد | ندارد | media read عمومی، send media v1 ایتا | رسانهٔ v1 | V-194 رسانه را نپذیرفته | bounded transfer/storage/IPC لازم است |
| `BaleWebSocket.next_update` | ندارد | ندارد | polling/update عمومی ندارد | refresh خودکار ایتا | بدون شاهد برنامهٔ اصلی | LIVE_UPDATES advertised ولی وصل نیست |

قرارداد مرجع `bale:user:<id>`، `bale:group:<id>` و `bale:channel:<id>` است؛ `bale:peer:<id>` فقط به‌عنوان ورودی legacy خصوصی قابل تفسیر است. شناسهٔ عددی بدون نوع و account scope قابل ارسال نیست. بات بله با namespace/manifest مستقل می‌ماند. آزمون `tests/test_bale_product_integration.py` روی snapshot آغاز برای contact protocol، برخورد نوع peer و parser سرویس سه شکست معنادار داشت؛ نبود factory/runtime و مسیر UI/API در همین ماتریس با شاهد ایستا ثبت است. فعال‌سازی runtime/onboarding تا آزمون مستقل worker و vault ممنوع می‌ماند.

پیشرفت V-227 بالا snapshot آغاز است و با wiring در V-228/V-229 superseded شد. ماتریس جاری پس از بازبینی V-230:

در جدول زیر `A` برابر `/api/v2/messenger-accounts/{account_id}` است. حساب و generation سمت سرور bind می‌شوند؛ raw RPC/مسیر فایل/secret DTO عمومی نیستند.

| Backend | DTO/worker جاری | Endpoint | UI اصلی | شاهد آفلاین و مرز |
|---|---|---|---|---|
| auth_start/code/password/connect/logout | challenge opaque؛ `bale.auth.*` و generation fence | `A/auth/{status,start,code,password,cancel,restore,logout}` | wizard BaleWorkspace | main_product + product_integration؛ Child auth/restart سبز، browser/Live باز |
| list/search_contacts | ContactPage؛ `bale.provider.contacts.{query,search}` | `A/contacts/{query,search}` | مخاطبین | main_product؛ DTO بدون access_hash |
| add_by_phone/add_contact/remove | contact contract v2؛ `contacts.{add_phone,add_id,remove}` | `A/contacts/{upsert,remove}` | confirm + idempotency | replay، named match و حفظ نام موجود؛ Live mutation باز |
| list_dialogs | DialogPage title/last_text/unread؛ `dialogs.query` | `A/dialogs/query` | فهرست گفتگو | fixture معتبر نوع peer؛ group/channel در عملیات خصوصی پشتیبانی نمی‌شود |
| read_history | MessagePage، media ref، date cursor؛ `history.query` | `A/history/query` | history/older + polling | ترتیب و typed scope در API؛ polling مرورگری باز |
| send_text | SendReceipt؛ `messages.send_text` | `A/messages/send-text` و M2M send-text | ارسال با confirm | concurrent/replay/uncertain؛ submission تحویل انسانی نیست |
| send_file_bytes/read_message_media | optional media send + media read؛ `messages.send_media`, `media.{read,content}` | `A/messages/send-media`, `A/media/{read,content}` | فایل/دریافت پیوست | Child content regression سبز؛ stream و IPC حداکثر 512 KiB |
| read_history polling | LIVE_UPDATES با snapshot/dedup/peer+account guards | تاریخچهٔ گفتگوی باز هر ۵ ثانیه؛ فهرست گفتگوها هر ۱۵ ثانیه با backoff مستقل (V-262) | گفتگوی باز بدون reload | دریافت بدون reload با dedup در مرورگر فیکسچر (V-233) و گزارش Live مالک (V-259)؛ دوام cadence تازه در انتظار مشاهده |
| exact contact lookup/import | bounded `recipients.resolve` و ContactMutationReceipt | M2M `recipients/{resolve,prepare}` | انتخاب account سرویس/readiness | scope contacts.resolve/import جدا؛ peer ساختگی از phone ممنوع |

capabilityهای AUTH_PHONE، CONTACTS_READ/WRITE، DIALOGS_READ، HISTORY_READ، MESSAGES_SEND، MEDIA_READ/SEND به ردیف‌های متناظر متصل‌اند. LIVE_UPDATES از F-098 با مشاهدهٔ ثبت‌شدهٔ `bale_updates_polling_transport` (نویسندهٔ `record_messenger_capability_observation` در store، ثبت در start ران‌تایم بله، گیت `hasCapability('updates.live')` در UI) به پیاده‌سازی polling متصل است؛ صرف history شاهد مرورگر آن نیست. آداپتور logout به store account-owned متصل و بات بله مستقل باقی است. gateها، browser (V-233 روی فیکسچر) و Live جدا در [گزارش](../../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md) ثبت می‌شوند.

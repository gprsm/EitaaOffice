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

پیشرفت همین نوبت: سه RED نام‌برده GREEN شدند و `BaleAccountOwner` با دو حساب و restart آفلاین آزموده شد؛ هنوز در registry/worker/API/UI مصرف نمی‌شود. factory/runtime و routing UI/API هنوز آزمون RED مستقل ندارند. وضعیت معیارهای BALE-A01 تا A07 در [گزارش](../../reports/features/BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md) باز ثبت شده است.

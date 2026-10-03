# هستهٔ تراکنشی و دسترسی — فاز دو (P2-DESIGN-2026-10-03)

| ویژگی | مقدار |
| :--- | :--- |
| **شناسه** | P2-DESIGN-2026-10-03 |
| **تاریخ** | ۲۰۲۶-۱۰-۰۳ |
| **سند حاکم** | [UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md](UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md) بخش ۸-۹ فاز دو + بخش ۴ (ضدتکرار) |
| **سند طراحی فاز یک** | [DOMAIN-MODEL-V5-2026-10-03](REPORTING_DOMAIN_MODEL_MIGRATION_2026-10-03.md) |
| **وضعیت** | `PHASE2_DESIGN_DRAFT` |
| **پیشنیاز** | اسکیمای v5 (کامیت `4ae0c922`) |

---

## ۱. اصل نویسندهٔ واحد و مالکیت تکپروسه‌ای (رفع F-104)
- `ReportingStore` تنها writer دادهٔ گزارش است؛ هیچ مسیر دیگری حق `INSERT`/`UPDATE` جداول reporting را ندارد.
- **سازوکار مالکیت**: فایل قفل `runtime/reporting_store_owner.lock` شامل pid + host + زمان گرفتن + heartbeat؛ اجاره با TTL (پیش‌فرض ۳۰ ثانیه، heartbeat هر ۱۰ ثانیه)؛ گیرندهٔ دوم با خطای روشن `ReportingStoreOwnershipError` رد می‌شود؛ اجارهٔ کهنه (heartbeat بیشتر از TTL) قابل تصاحب با ثبت ممیزی؛ release تمیز هنگام خروج نرمال؛ بازیابی پس از crash = تصاحب اجارهٔ کهنه بدون دستکاری داده.
- هماهنگ با الگوی موجود network modes (`desktop_loopback`/`trusted_lan_http`/`web_reverse_proxy`) در `config.py`.

## ۲. مهاجرت v6 (در ادامهٔ زنجیرهٔ reporting_schema)
- جدول `reporting_user_roles`: `user_id` (app_user_id موجود)، `roles_json` (آرایه: editor/approver/admin)، `updated_by`، `updated_at`؛ `UNIQUE(user_id)`.
- جدول `reporting_audit_log`: `audit_id` TEXT PK، `actor` TEXT NOT NULL، `action` TEXT NOT NULL، `entity_type` TEXT NOT NULL، `entity_id` TEXT NOT NULL، `diff_json` TEXT (بدون PII — فقط شناسه‌ها و تغییر فیلدهای ساختاری)، `etag_before`/`etag_after`، `created_at` TEXT؛ ایندکس‌های (`entity_type`, `entity_id`, `created_at`) و (`actor`, `created_at`).
- نسخهٔ ثابت `REPORTING_SCHEMA_VERSION = 6` با الگوی گام شرطی idempotent فاز یک.

## ۳. مدل همزمانی و etag
- هر پروندهٔ رویداد یک etag دارد: ستون `version INTEGER` جدید روی `reported_events` در v6 (شروع ۱؛ +۱ در هر mutation) و `etag = sha256(f"{event_id}:{version}")`؛ پاسخ‌ها هدر/فیلد etag می‌دهند؛ PUT با `If-Match`؛ ناسازگاری → 409 با etag فعلی؛ آخرین ذخیره هیچ‌وقت بی‌صدا بازنویسی نمی‌کند (بخش ۶ سند حاکم).
- همهٔ mutationها در تراکنش SQLite واحد (`BEGIN IMMEDIATE`) با retry محدود روی `SQLITE_BUSY` (backlog کوتاه؛ حداکثر ۳ بار)؛ هیچ نوشتن چندمرحله‌ای بیرون تراکنش انجام نمی‌شود.

## ۴. قرارداد ضدتکرار تراکنشی (بخش ۴ سند حاکم)
- ثبت شاهد + پیوند + وضعیت در یک تراکنش: `INSERT OR IGNORE` شاهد (کلید `uq_witness_identity`) → خواندن `witness_id` → INSERT پیوند با نقش درخواستی.
- اگر همان پیام قبلاً primary فعال دارد: پاسخ 409 با جزئیات رویداد/رویدادهای مرتبط؛ پیوند supporting فقط با `reason` و مجوز editor+ و ثبت صف بازبینی `item_type='supporting_link_review'`.
- «اولین کلیک UI» هیچ اعتباری ندارد؛ قیود پایگاه داده ملاک قطعی هستند.

## ۵. نقش‌ها و مجوزهای سمت سرور
- سه نقش: `editor` (ثبت/ویرایش پیش‌نویس، ثبت شاهد، resolve صف)، `approver` (همهٔ اختیارات editor + approve/conflict)، `admin` (همهٔ اختیارات approver + مدیریت نقش‌ها و config).
- **اصل**: تشخیص نقش فقط سمت سرور از `reporting_user_roles` + `app_user_auth` موجود (actor از ContextVar به نام `_request_actor_app_user_id` می‌آید)؛ وضعیت «شبکهٔ داخلی» هرگز جای مجوز را نمی‌گیرد (بخش ۸ سند حاکم).
- عملیات approve فقط برای approver+ مجاز است؛ تغییر نقش فقط توسط admin انجام می‌شود؛ هر رد مجوز با کد وضعیت 403 و بدون افشای جزئیات داده بازمی‌گردد.
- **seed پیش‌فرض**: اگر جدول خالی است، هیچ‌کس نقش ندارد تا admin صریحاً تخصیص دهد (بدون حدس).

## ۶. قرارداد API (زیر /api/v3/reporting/*؛ v2 موجود دست‌نخورده می‌ماند)

| متد | مسیر | حداقل نقش | شرح | پاسخ‌ها |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v3/reporting/events` | `editor` | ساخت پیش‌نویس (`review_status='draft'`) | `201 {event_id, etag}` |
| `GET` | `/api/v3/reporting/events/{event_id}` | هر کاربر احرازشده | خواندن پرونده با etag و witnesses و documents | `200` / `404` |
| `PUT` | `/api/v3/reporting/events/{event_id}` | `editor` | ویرایش فیلدهای مجاز (`If-Match`) | `200 {etag}` / `409` / `412` |
| `POST` | `/api/v3/reporting/events/{event_id}/submit-review` | `editor` | `draft` → `needs_review` | `200` / `409` |
| `POST` | `/api/v3/reporting/events/{event_id}/approve` | `approver` | `needs_review` → `approved` یا `conflict` → `needs_review` پس از رفع | `200` / `409` / `403` |
| `POST` | `/api/v3/reporting/events/{event_id}/mark-conflict` | `approver` | `→ conflict` با دلیل | `200` / `403` |
| `POST` | `/api/v3/reporting/events/{event_id}/witnesses` | `editor` | ثبت شاهد + پیوند تراکنشی (بند ۴) | `201` / `409` / `403` |
| `POST` | `/api/v3/reporting/witness-links/{link_id}/detach` | `editor` | detach با دلیل (بدون حذف) | `200` |
| `GET` | `/api/v3/reporting/review-queue` | هر نقش | فهرست صف بازبینی با فیلتر status/item_type | `200` |
| `POST` | `/api/v3/reporting/review-queue/{queue_id}/resolve` | `editor` | resolve/dismiss با یادداشت | `200` / `404` |
| `PUT` | `/api/v3/reporting/users/roles` | `admin` | تخصیص نقش کاربر | `200` / `403` |
| `GET` | `/api/v3/reporting/events/{event_id}/audit` | `approver` + `admin` | تاریخچهٔ ممیزی پرونده | `200` |
| `PUT` | `/api/v3/reporting/events/{event_id}/documents` | `editor` | ثبت مدرک (`media_id` opaque، `sha256` الزامی، `kind`، `display_order`، `is_cover`) | `201` / `400` |
| `GET` | `/api/v3/reporting/events/{event_id}/documents/{document_id}/content` | هر کاربر احرازشدهٔ مجاز | جریان فایل با Content-Type؛ هرگز مسیر مطلق؛ 404 اگر نبود؛ 403 بدون مجوز | `200` / `403` / `404` |

*نکته: هر mutation مستلزم ثبت رکورد ممیزی در همان تراکنش است (بند ۲).*

## ۷. دسترسی رسانه
- `storage_ref` فقط کلید داخلی است؛ مسیر مطلق کلاینت یا دارای شناسهٔ حساس در هیچ پاسخی قرار نمی‌گیرد (بخش ۵ سند حاکم)؛ `sha256` هنگام ثبت سنجیده شده و در `event_documents` باقی می‌ماند؛ دانلود رسانه فقط با مجوز دسترسی به پرونده و از طریق endpoint محافظت‌شدهٔ بند ۶ میسر است.

## ۸. ممیزی و حریم خصوصی
- `diff_json` فقط شناسه‌ها و تغییر فیلدهای ساختاری را ثبت می‌کند؛ متن خصوصی پیام، شمارهٔ کامل، توکن و session هرگز در audit یا لاگ‌ها درج نمی‌شوند (بخش ۸ سند حاکم + F-102: هیچ رمز یا توکنی در `.env` جدید ذخیره نمی‌شود).
- ممیزی غیرقابل‌حذف (append-only) است؛ قابلیت حذف رویداد توسط این APIها ارائه نمی‌شود (حذف رویداد صرفاً از طریق فرایندهای مدیریتی جداگانه در آینده با تصمیم مالک انجام‌پذیر است).

## ۹. نقشهٔ اجرا به زیرمأموریت‌ها
- **P2-B**: مالکیت تکپروسه‌ای (قفل/اجاره/heartbeat/تصاحب) + تست‌های اعتبارسنجی آن.
- **P2-C**: مهاجرت v6 + متدهای تراکنشی store (`create_draft`/`update_with_etag`/`set_status`/`link_witness`/`detach_link`/`resolve_queue`/`roles`/`audit append`) + تست‌های تراکنش.
- **P2-D**: مسیرهای `/api/v3/reporting/*` + لایهٔ مجوزها + پاسخ‌های 401/403/409/412 + تست‌های API.
- **P2-E**: دروازه — آزمون دو کاربر همزمان، شناسهٔ پیام مشابه از دو حساب/گفت‌وگو، retry درخواست، شبیه‌سازی crash میان ثبت و پیوند (rollback کامل)، مجوزهای ممنوع، بازیابی DB/رسانه (رزمایش فاز صفر)، و مجموعهٔ کامل سبز.

## ۱۰. نقشهٔ پذیرش دروازهٔ فاز دو (بخش ۹ سند حاکم)
- هیچ گزارشی با ثبت ناقص یا شمارش دوباره تأیید نشود (تراکنش کامل یا هیچ)؛
- دو کاربر همزمان یکی از دو نتیجهٔ روشن را ببینند؛
- تعارض etag بدون گم‌شدن یا رونویسی ناخواستهٔ ذخیرهٔ قبلی مدیریت شود؛
- کاربر با نقش editor نتواند عملیات approve را اجرا کند (خطای 403)؛
- وقوع crash میان ثبت شاهد و ثبت پیوند منجر به rollback کامل شده و ردیف یتیم به جا نگذارد؛
- پیام مشابه در دو حساب مختلف، دو شاهد مستقل تلقی شود (دامنهٔ کلید یکتا شامل شناسهٔ حساب است)؛
- بازیابی پایگاه داده و رسانه از snapshot با رزمایش سبز اثبات شود؛
- مجموعهٔ کامل آزمون‌های `pytest` + `tsc` + `observability` و بررسی‌کننده‌های یکپارچگی اسناد سبز باشند.

---
**پاورقی:** این سند فقط دستور تغییر در مخزن EitaaBridge است؛ پروژهٔ اصلی AntiGravity2 خارج از دامنه است. الگوی مهاجرت و تست از فاز یک (V-245/V-246) تبعیت می‌کند.

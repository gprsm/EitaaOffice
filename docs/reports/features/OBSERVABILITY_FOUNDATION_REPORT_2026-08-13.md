# گزارش پیاده‌سازی Observability Foundation

تاریخ: 2026-08-13  
وضعیت: `IMPLEMENTED / AUTOMATED_VERIFIED`  
دامنه: Backend، account worker، Electron، React، قرارداد محرمانگی و مستندات  
اثر بیرونی: هیچ؛ بدون اتصال Provider، ارسال، ورود، انتشار یا تغییر شبکه

## ۱. نتیجهٔ مدیریتی

شکاف‌های پرخطر ممیزی قبلی بسته شدند: Event Catalog نسخه‌دار ایجاد شد، JSONL مشترک Backend/Worker/Desktop برقرار شد، correlation از Renderer تا HTTP/Application عبور می‌کند، Error Boundary و خطاهای global رابط پوشش داده شدند، مسیر request در Electron sanitize شد و endpoint گزارش client با allowlist و rate limit ساخته شد.

ادعای «ثبت هر اتفاق» در این پروژه به معنای ثبت رخداد مادی و قابل‌پشتیبانی است؛ payload خصوصی، متن پیام، credential، stack خام و نویز کم‌ارزش عمداً ثبت نمی‌شوند.

## ۲. تغییرات Backend

- Event Catalog و taxonomy در `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py`.
- envelope نسخهٔ 1 در `runtime_logger.py` شامل source/category/result/reason/correlation/operation.
- wrapper عمومی `observed_operation` برای started/succeeded/failed بدون exception message.
- source مستقل `application` و `provider_worker`.
- lifecycle رخدادهای شروع/توقف برنامه.
- دریافت correlation امن از HTTP header و ادامهٔ آن در Dispatcher.
- `GET /api/v2/observability/events` برای contract خواندنی.
- `POST /api/v2/client-diagnostics` با سه event مجاز، payload محدود و سقف 20 گزارش در دقیقه.

## ۳. تغییرات Electron و React

- `ui/electron/observability.cjs`: Desktop logger ساختاریافته، redaction و sanitization مسیر.
- ثبت process error/exit، renderer gone/unresponsive/load failure، API lifecycle/recovery/request/retry.
- IPC امن `diagnostics:report` با allowlist و rate limit محلی.
- `ClientErrorBoundary.tsx`: fallback دیداری امن برای render error.
- handlerهای `window.error` و `unhandledrejection` با dedupe؛ فقط نوع خطا و booleanهای امن ارسال می‌شوند.
- correlation تصادفی 32-hex برای requestهای UI و forward در preload/Electron/HTTP.

## ۴. قرارداد محرمانگی

موارد زیر در client diagnostic رد یا حذف می‌شوند:

- message و stack خام؛
- URL، query و fragment؛
- DOM، React state و payload دلخواه؛
- Token، Cookie، OTP، password و Authorization؛
- شمارهٔ کامل، متن پیام و فایل خصوصی.

آزمون adversarial ثابت می‌کند مقدارهای ممنوع به JSONL وارد نمی‌شوند و route فقط شکل امن را نگه می‌دارد.

## ۵. اعتبارسنجی

| سطح | نتیجه |
|---|---|
| تست اختصاصی Python Observability | 6/6 موفق |
| suite کامل Python | 513/513 موفق |
| UI/Electron observability contract | موفق |
| UI scroll model | 10/10 موفق |
| Grouped media | 16/16 موفق |
| Phase 9 workspace | 11/11 موفق |
| Phase 9 acceptance | 10/10 موفق |
| Phase 10 local activation | 7/7 موفق |
| TypeScript/Vite production build | موفق؛ warning اندازهٔ chunk ثبت شد |
| project docs freshness/local links | موفق؛ لینک شکسته صفر |

اجرای نخست تست هدفمند از پوشهٔ `ui` به‌دلیل مسیر نسبی اشتباه venv و policy اجرای `npm.ps1` شروع نشد. هیچ تستی در آن invocation اجرا نشد؛ اجرای اصلاح‌شده با مسیر ریشه و `npm.cmd` موفق بود و این نکته برای جلوگیری از تکرار در Validation Ledger ثبت شد.

تست پوشش کاتالوگ در نخستین اجرای intentional-red تعداد 43 رخداد literal قدیمی خارج از catalog را کشف کرد. همهٔ آن رخدادها با category/result/audit metadata ثبت شدند؛ اجرای بعدی 6/6 و suite نهایی 513/513 موفق شد. این تست از بازگشت همان نقص جلوگیری می‌کند.

## ۶. موارد باقیمانده

- migration تدریجی عملیات legacy به `observed_operation`؛ زیرساخت فراهم است اما همهٔ مسیرهای قدیمی تبدیل نشده‌اند.
- قرارداد retention/disk budget و health نوشتن log برای همهٔ کانال‌ها.
- metrics/alert بدون PII برای استقرار Web واقعی؛ تا آن زمان `DEFERRED`.
- warning فعلی bundle اصلی UI حدود 891 kB minified و بیشتر از آستانهٔ پیشنهادی Vite است؛ blocker عملکردی این تغییر نیست اما برای code splitting در roadmap ثبت شد.

## ۷. نتیجه

Observability Foundation و شکاف‌های high-risk ممیزی بسته و با تست خودکار پذیرفته شدند. بلوغ عملیاتی retention/metrics و مهاجرت کامل رخدادهای legacy همچنان کار آینده است؛ بنابراین وضعیت کل Observability «Foundation کامل، Operations جزئی» است، نه ادعای پوشش نهایی production Web.

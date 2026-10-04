# گزارش فاز پنج — دستیار و اصلاح تعاملی

* **شناسهٔ سند:** `PHASE5-UNIFIED-REPORTING-2026-10-03`
* **تاریخ:** ۲۰۲۶-۱۰-۰۳
* **سند حاکم:** [UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md](../specifications/UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md) (بخش ۷ و بخش ۹، فاز پنج)
* **سند طراحی:** [REPORTING_ASSISTANT_PHASE5_2026-10-03.md](../specifications/REPORTING_ASSISTANT_PHASE5_2026-10-03.md) (`P5-DESIGN-2026-10-03`)
* **وضعیت:** `PHASE5_EXECUTED / GATE_GREEN`

## ۱. دستاوردهای فاز پنج

مطابق بخش ۷ و بخش ۹ فاز پنج سند حاکم راهبردی:

1. **رفتار محافظه‌کارانه و خودداری در ابهام (Conservative Abstain)**:
   - در نسخهٔ پیشین دستیار، در صورت عدم تطابق با الگوها، سیستم به صورت پیش‌فرض برنامه را مراسم عمومی (`ceremonies`) تلقی می‌کرد.
   - در این فاز، رفتار صریح «نمی‌دانم» بر اساس استراتژی پیاده‌سازی شد: اگر متن فاقد نشانه‌ها و کلیدواژه‌های قطعی باشد، دستیار با `is_abstain = True`، `recommended_program = 'unknown'` و `confidence = 0.0` از حدس کورکورانه خودداری کرده و علت را شفاف در استدلال (`reasoning`) ثبت می‌کند.

2. **توضیح‌پذیری و منشأ پیشنهاد (Explainability & Provenance)**:
   - هر پیشنهاد شامل نسخهٔ قاعده (`rule_version = "1.0"`), نام قاعده (`rule_name`) مانند `rule_c12_ashura`، `rule_keyword_honor`، `rule_scoped_alias` و `rule_abstain`، و مشخصات منشأ (`provenance`) است.
   - هیچ پیشنهادی بدون تأیید انسان به فکت قطعی تبدیل نمی‌شود (رعایت کامل ADR-42, ADR-46, ADR-51).

3. **ارتقای Schema به v8 (بازخورد دامنه‌دار و الیاس‌ها)**:
   - جدول `assistant_feedback`: ثبت اقدامات بازبین (accept, correct, reject, abstain) با تفکیک دامنه (`local`, `program`, `unit`, `global`) و قابلیت ابطال (`revoked_at`, `revoked_by`).
   - جدول `assistant_scoped_aliases`: مدیریت الیاس‌های مفهومی دارای دامنه. ثبت الیاس سراسری مشروط به تأیید کاربر با دسترسی مدیر (`approved_by`) است تا از آلودگی نام‌فضا جلوگیری شود.

4. **توسعهٔ API v3 و اتصال به سرویس**:
   - مسیرهای `/api/v3/reporting/assistant/feedback` و ابطال آن.
   - مسیرهای `/api/v3/reporting/assistant/aliases` و ابطال آن.
   - تزریق الیاس‌های فعال دامنه‌دار به `suggest_candidate_review` در `service.py`.

## ۲. جدول مصنوعات

| مصنوع | مسیر | نقش |
|---|---|---|
| مهاجرت v8 | `src/eitaa_bridge/reporting/store.py` | جداول `assistant_feedback` و `assistant_scoped_aliases` + اشتراک اجارهٔ مالکیت در سطح پروسه (refcount) |
| متدهای ذخیره‌سازی دستیار | `src/eitaa_bridge/reporting/store.py` | ثبت و ابطال بازخورد و الیاس‌های دامنه‌دار |
| دستیار هوشمند محافظه‌کار | `src/eitaa_bridge/reporting/suggester.py` | پیاده‌سازی Abstain، منشأ، نسخهٔ قاعده، **دروازهٔ دامنه (Scope Gate)** و الیاس‌های دامنه‌دار |
| اتصال سرویس گزارش‌گیری | `src/eitaa_bridge/reporting/service.py` | اتصال الیاس‌های فعال به فرایند پیشنهاددهی |
| مسیرهای API v3 | `src/eitaa_bridge/application/reporting_api_v3.py` | اندپوینت‌های بازخورد و الیاس با کنترل نقش (الیاس سراسری نیازمند نقش admin) |
| تست‌های دروازه فاز پنج | `tests/test_reporting_phase5_gate.py` (۱۰ تست) | راستی‌آزمایی محافظه‌کاری، جداسازی دامنهٔ الیاس (سطح suggester و سرویس)، بازخورد، کنترل نقش و API |

## ۳. نتایج دروازهٔ فاز پنج (بخش ۹ سند حاکم)

| شرط دروازه | نتیجه | شاهد |
|---|---|---|
| عدم تبدیل پیشنهاد غلط به فکت دائمی بدون تأیید | PASS — دستیار فقط پیشنهاد تولید می‌کند؛ تبدیل به فکت فقط از طریق گردش کار بازبینی انسانی صورت می‌گیرد | معماری دستیار + تست ۱ و ۲ |
| مورد مبهم abstain کند | PASS — متن مبهم بدون کلیدواژه رسماً `is_abstain=True` و `recommended_program='unknown'` بازمی‌گرداند | تست ۱ در `test_reporting_phase5_gate.py` |
| عدم آلودگی الیاس در زمینه‌های نامرتبط | PASS (پس از اصلاح V-252) — دروازهٔ دامنه در suggester: الیاس `unit` فقط با شواهد واحد در متن، `program` فقط با تطابق ایندکسر، `local` فقط برای همان کاندید؛ الیاس سراسری در API نیازمند نقش admin است | تست‌های `test_suggester_enforces_alias_scope_isolation`، `test_service_scoped_alias_isolation` و `test_global_alias_via_api_requires_admin_role` |
| قابلیت ابطال بازخورد و الیاس | PASS — بازخورد و الیاس با `revoked_at` و ممیزی کامل ابطال می‌شوند و از فهرست فعال خارج می‌گردند | تست ۴ و ۵ در `test_reporting_phase5_gate.py` |
| مجموعهٔ کامل آزمون‌ها | PASS — مجموعهٔ کامل pytest سبز (به‌همراه tsc و آزمون‌های UI)؛ اجرای نهایی در V-252 ثبت شده است | اجرای کامل تست‌ها |

## ۴. شاهدان

* کامیت فاز پنج؛ تست‌های `tests/test_reporting_phase5_gate.py`؛ دفتر اعتبارسنجی (V-250).

## ۵. اصلاحات بازبینی مستقل (V-252، ۲۰۲۶-۱۰-۰۴)

بازبینی بی‌طرف ZCode روی همین کد سه نکته را اصلاح کرد:

1. **دروازهٔ دامنهٔ الیاس‌ها ناقص بود**: سرویس همهٔ الیاس‌های فعال را بدون فیلتر دامنه به دستیار تزریق می‌کرد و suggester فقط `status` را می‌سنجید؛ بنابراین الیاسِ دامنه‌دارِ یک واحد در زمینهٔ واحدهای دیگر هم اثر می‌گذاشت (نقض معیار دروازهٔ فاز ۵). اکنون دروازهٔ دامنه در `suggester.analyze` اعمال می‌شود و با سه تست جدید (سطح suggester، سطح سرویس و کنترل نقش admin برای الیاس سراسری) پوشش داده شده است.
2. **ادعای «مجموعهٔ کامل pytest سبز» در زمان ثبت V-250 نادرست بود**: اجرای کامل در بازبینی مستقل سه شکست نشان داد (دو تعارض اجارهٔ مالکیت از `acquire_lease=True` با معماری چندنمونه‌ای در یک پروسه، و کهنگی wheel باندل‌شده). ریشهٔ تعارض با اشتراک اجارهٔ refcount‌دار در سطح پروسه برطرف شد (`test_reporting_store_shares_lease_within_process`) و wheel بازسازی شد.
3. شمار تست‌های دروازه در این گزارش از ۷ به ۱۰ به‌روزرسانی شد.

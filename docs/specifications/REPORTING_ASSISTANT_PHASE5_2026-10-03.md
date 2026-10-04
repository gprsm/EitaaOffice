# دستیار و اصلاح تعاملی — فاز پنج (P5-DESIGN-2026-10-03)

| مشخصه | مقدار |
| :--- | :--- |
| **شناسه** | `P5-DESIGN-2026-10-03` |
| **تاریخ** | ۲۰۲۶-۱۰-۰۳ |
| **سند حاکم** | [UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md](UNIFIED_REPORTING_FINAL_STRATEGY_2026-10-01.md) (بخش ۷ و بخش ۹ فاز پنج) |
| **اسناد پیش‌نیاز** | سندهای طراحی فاز ۱ تا ۴ |
| **وضعیت** | `PHASE5_DESIGN_APPROVED` |
| **مبنای کد واقعی** | `reporting/suggester.py`، `reporting/store.py`، `application/reporting_api_v3.py` |

## ۱. اصول و اهداف راهبردی (مطابق بخش ۷ سند حاکم)

1. **محافظه‌کاری و پرهیز از پیش‌فرض کورکورانه (Abstain on Ambiguity)**:
   - دستیار اگر اطمینان کافی ندارد یا متن فاقد نشانه‌های روشن است، نباید به شکل پیش‌فرض رویداد را «مراسم» (`ceremonies`) تلقی کند.
   - در چنین شرایطی دستیار رسماً حالت «نمی‌دانم» (`is_abstain = True`, `recommended_program = 'unknown'`, `confidence = 0.0`) را همراه با استدلال واضح بازمی‌گرداند.

2. **توضیح‌پذیری و منشأ پیشنهاد (Explainability & Provenance)**:
   - هر پیشنهاد دستیار شامل نسخهٔ قاعده (`rule_version = '1.0'`)، نام قاعده (`rule_name`)، و جزئیات منشأ و سیگنال‌های شناسایی‌شده (`provenance`) است.
   - کاربر انسانی همواره تصمیم‌گیرندهٔ نهایی است و هیچ پیشنهادی بدون تأیید به فکت قطعی تبدیل نمی‌شود (ADR-42, ADR-46, ADR-51).

3. **بازخورد دامنه‌دار و قابل‌ابطال (Scoped & Revocable Feedback)**:
   - بازخورد کاربر نسبت به پیشنهاد (تأیید، تصحیح، رد یا ممتنع) در جدول `assistant_feedback` با دامنهٔ مشخص (`scope_kind`: `local`, `program`, `unit`, `global`) ثبت می‌شود.
   - هر بازخورد دارای امکان ابطال (`revoked_at`, `revoked_by`) است.

4. **جلوگیری از آلودگی الیاس سراسری (No Global Alias Pollution)**:
   - وزن ۱.۰ کورکورانه به هر تصحیح داده نمی‌شود.
   - الیاس‌های مفهومی در جدول `assistant_scoped_aliases` با دامنهٔ محلی یا واحد ثبت می‌شوند و تبدیل به الیاس سراسری مستلزم تأیید صریح کاربر مسئول (`approved_by`) است.

## ۲. مدل داده و ارتقای Schema به v8

```sql
-- Migration v7 -> v8: Assistant scoped feedback and aliases

CREATE TABLE IF NOT EXISTS assistant_feedback (
    feedback_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    scope_kind TEXT NOT NULL CHECK(scope_kind IN ('local', 'program', 'unit', 'global')),
    scope_target TEXT NOT NULL DEFAULT '',
    suggested_program TEXT NOT NULL DEFAULT '',
    suggested_unit TEXT NOT NULL DEFAULT '',
    chosen_program TEXT NOT NULL DEFAULT '',
    chosen_unit TEXT NOT NULL DEFAULT '',
    rule_version TEXT NOT NULL DEFAULT '1.0',
    actor TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('accept', 'correct', 'reject', 'abstain')),
    revoked_at TEXT,
    revoked_by TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_candidate ON assistant_feedback(candidate_id);
CREATE INDEX IF NOT EXISTS idx_feedback_scope ON assistant_feedback(scope_kind, scope_target);

CREATE TABLE IF NOT EXISTS assistant_scoped_aliases (
    alias_id TEXT PRIMARY KEY,
    alias_text TEXT NOT NULL,
    canonical_target TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('program', 'unit', 'occasion')),
    scope_kind TEXT NOT NULL CHECK(scope_kind IN ('local', 'program', 'unit', 'global')),
    scope_target TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL DEFAULT 1.0,
    approved_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'revoked'))
);
CREATE INDEX IF NOT EXISTS idx_alias_lookup ON assistant_scoped_aliases(alias_text, scope_kind, status);
```

## ۳. دروازهٔ پذیرش فاز پنج

- [x] پیشنهاد غلط بدون تأیید به فکت یا قانون دائمی تبدیل نشود.
- [x] مورد مبهم abstain کند (`is_abstain = True`, `recommended_program = 'unknown'`).
- [x] اصلاح محلی در زمینهٔ مجاز اثر بگذارد و در زمینهٔ نامرتبط آلودگی ایجاد نکند.
- [x] ابطال بازخورد و مدیریت الیاس‌های دامنه‌دار با موفقیت تست شود.
- [x] تمام آزمون‌های سیستم سبز باشند.

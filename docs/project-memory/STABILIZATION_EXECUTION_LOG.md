# دفتر اجرای تثبیت AntiGravity2

وضعیت: `APPEND_ONLY / ACTIVE_RESUMED`  
طرح مرجع: [STABILIZATION_REMEDIATION_PLAN_2026-08-25.md](STABILIZATION_REMEDIATION_PLAN_2026-08-25.md)

## قواعد تغییرناپذیر

1. رکورد موجود حذف یا بازنویسی نمی‌شود.
2. retry، correction و rollback همیشه رکورد تازه دارند.
3. correction باید `supersedes` و retry باید `retry_of` داشته باشد.
4. مقدار حساس با `[redacted]` جایگزین می‌شود؛ اصل مقدار حتی موقت در این سند نوشته نمی‌شود.
5. یک Run بدون `RUN_FINISHED`، `RUN_BLOCKED` یا `USER_PAUSED` ناقص تلقی می‌شود.
6. زمان‌ها ISO-8601 با timezone و مدت‌ها millisecond هستند.
7. hash فقط برای source/docs امن ثبت می‌شود؛ فایل عملیاتی، secret و session hash نمی‌شود.

## واژگان کنترل‌شده

- `action_kind`: `READ`, `WRITE`, `TEST`, `BUILD`, `GENERATE`, `OPERATION`, `DECISION`
- `result`: `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, `PARTIAL`
- `failure_class`: `none`, `product_regression`, `test_drift`, `environment`, `permission`, `contract`, `privacy`
- `external_effect`: `none`, `read_only`, `test_temp`, `config`, `data`, `network`, `process`, `system`
- وضعیت هدف: `QUEUED`, `SCOPED`, `BASELINED`, `RED_VERIFIED`, `IMPLEMENTING`, `TARGETED_GREEN`, `REGRESSION_GREEN`, `DOCUMENTED`, `USER_ACCEPTED`, `CLOSED`, `BLOCKED`, `USER_PAUSED`, `USER_RESUMED`, `ROLLED_BACK`, `SUPERSEDED`

## قالب رکورد

```yaml
event_id: STAB-Gxx-Rnn-Snn
event: ACTION_NAME
started_at: 2026-08-25T00:00:00.000+03:30
ended_at: 2026-08-25T00:00:00.000+03:30
duration_ms: 0
goal_id: G-xx
run_id: STAB-Gxx-Rnn
state_before: QUEUED
state_after: SCOPED
actor: codex
action_kind: READ
cwd: <project-root>
intent: شرح کوتاه هدف اقدام
command_safe: فرمان بدون secret یا N/A
files_intended: []
files_changed: []
pre_sha256: {}
post_sha256: {}
exit_code: 0
result: PASS
test_counts: {collected: 0, passed: 0, failed: 0, errors: 0, skipped: 0}
failure_class: none
reason_code: ok
retry_of: null
supersedes: null
external_effect: read_only
approval_ref: null
output_summary: خلاصهٔ امن و قابل‌ممیزی
artifacts: []
```

## کنترل یکپارچگی دفتر

در پایان هر هدف باید این کنترل‌ها ثبت شوند:

- یکتایی `event_id` و `run_id`؛
- ترتیب `started_at <= ended_at` و نبود Run باز؛
- وجود فایل/مرجع اعلام‌شده؛
- انطباق `files_changed` با تغییر واقعی؛
- کامل‌بودن failure/retry/supersedes؛
- اسکن Token، Cookie، OTP، password، شمارهٔ کامل، متن خصوصی و مسیر حساس؛
- همخوانی نتیجهٔ پذیرش با `VALIDATION_LEDGER.md`.

## رخدادهای ثبت‌شده

### STAB-GPLAN-R00-S01 — ایجاد برنامه و قرارداد لاگ‌گذاری

```yaml
event_id: STAB-GPLAN-R00-S01
event: STABILIZATION_PLAN_DOCUMENTED
started_at: 2026-08-25T05:46:13.4673634+03:30
ended_at: 2026-08-25T05:51:59.8943232+03:30
duration_ms: 346427
goal_id: G-PLAN
run_id: STAB-GPLAN-R00
state_before: QUEUED
state_after: DOCUMENTED
actor: codex
action_kind: WRITE
cwd: <project-root>
intent: تعریف هدف کدها، حلقه G-00 تا G-09، ترتیب رفع F-039 تا F-044 و قرارداد لاگ‌گذاری؛ بدون اصلاح کد
command_safe:
  - apply_patch <planning-and-governance-documents>
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
files_intended:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/README.md
  - docs/project-memory/implementation_plan.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-map/PROJECT_FILE_MAP.md
  - docs/project-map/SYMBOL_INDEX.json
  - docs/REPORTS_INDEX.md
files_changed:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/README.md
  - docs/project-memory/implementation_plan.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-map/PROJECT_FILE_MAP.md
  - docs/project-map/SYMBOL_INDEX.json
  - docs/REPORTS_INDEX.md
pre_sha256:
  status: unavailable
  reason: new-root-has-no-git-baseline-and-this-is-the-governance-bootstrap-run
post_sha256:
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 8a8a5a74d455dcbe4f8340d3f4e6ad639668ebf7c9c9f520f2ccbbaaa50d0348
  docs/project-memory/README.md: 205e076d2449fd27f3d93161a763faa6a0b84b1482e1461a685953325bb884a1
  docs/project-memory/implementation_plan.md: 558a515d7c4e0da6bc7deef7ff16cfab9df1cbce9799d1e0c428f3ee3becb679
  docs/project-memory/FINDINGS_REGISTER.md: ceb9ae8ca4397c01c5971472beb6259786aa77e4874d03f24f1ffa02d0b8984a
  docs/project-map/PROJECT_FILE_MAP.md: 1d129e7426a65e242add481d410e3e01e8381640a374964ef690fc7e4e020852
  docs/project-map/SYMBOL_INDEX.json: 1414a87eb7da3b7a42cbc6ffc4cddd954f30ec49c66eb412e41427857622ad81
  docs/REPORTS_INDEX.md: 539df5c32e4780dbc2995c534a9859f957ba5f3cb4dbcefc3922e5709ae992a9
  self_referential_files: omitted
exit_code: 0
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: planning_documents_created_and_doc_checks_passed
retry_of: null
supersedes: null
external_effect: none
approval_ref: user-requested-plan-and-exact-logging
output_summary: برنامه و دفتر اجرا ثبت شدند؛ refresh، check و check-links هر سه exit code صفر داشتند. تست کد تکرار نشد چون کد تغییر نکرده است.
artifacts:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-104
  - docs/project-memory/FINDINGS_REGISTER.md#F-045
```

یادداشت یکپارچگی: hash خود دفتر اجرا و `VALIDATION_LEDGER.md` در همین رکورد عمداً درج نشده، زیرا نوشتن رکورد مقدار آن‌ها را تغییر می‌دهد. hash آن‌ها در ابتدای Run اجرایی بعدی به‌عنوان pre-image ثبت خواهد شد.

### STAB-GPLAN-R00-S02 — ثبت Ledger، retry مستندی و کنترل نهایی

```yaml
event_id: STAB-GPLAN-R00-S02
event: GOVERNANCE_LOG_AND_LEDGER_FINALIZED
started_at: 2026-08-25T05:51:59.8943232+03:30
ended_at: 2026-08-25T05:55:18.6532078+03:30
duration_ms: 198759
goal_id: G-PLAN
run_id: STAB-GPLAN-R00
state_before: DOCUMENTED
state_after: DOCUMENTED
actor: codex
action_kind: WRITE
cwd: <project-root>
intent: ثبت V-104 و Run برنامه‌ریزی، سپس کنترل نهایی اسناد و لینک‌ها
command_safe:
  - apply_patch <execution-log-and-validation-ledger>
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
attempts:
  - attempt_id: STAB-GPLAN-R00-S02-A01
    result: FAIL
    failure_class: contract
    reason_code: patch_context_not_found
    effect: none
    summary: context انتهای Ledger به‌علت متن قبلاً آسیب‌دیده با patch اولیه منطبق نبود؛ هیچ بخش patch اعمال نشد.
  - attempt_id: STAB-GPLAN-R00-S02-A02
    result: PASS
    retry_of: STAB-GPLAN-R00-S02-A01
    summary: تغییر دفتر اجرا و Ledger با context دقیق و patchهای جداگانه اعمال شد.
files_intended:
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/VALIDATION_LEDGER.md
files_changed:
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/VALIDATION_LEDGER.md
pre_sha256:
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 4f7c25de54e5cc1f2732b8162c8e60a34a63ad216a57c75042ba9c47c5ea2a8e
  docs/project-memory/VALIDATION_LEDGER.md: 9dabb4e8bb279566b90e263248253747e0d4013fea97a340c2053e3800a73688
post_sha256_before_this_self_record:
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 2e3223e35fb4df570209239b221e28d6dfc3ce7fc79af48b6286c48629d00ac7
  docs/project-memory/VALIDATION_LEDGER.md: ff3a4c7b0e756e936666c6f9778204e3091ff32fce6f45892e53a37c74c2116c
exit_code: 0
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: governance_ledger_and_final_doc_checks_passed
retry_of: STAB-GPLAN-R00-S02-A01
supersedes: null
external_effect: none
approval_ref: user-requested-plan-and-exact-logging
output_summary: شکست context پنهان نشد؛ retry ثبت شد. پس از ثبت V-104، check و check-links هر دو exit code صفر داشتند.
artifacts:
  - docs/project-memory/VALIDATION_LEDGER.md#V-104
```

### STAB-GPLAN-R00-S03 — پایان Run برنامه‌ریزی

```yaml
event_id: STAB-GPLAN-R00-S03
event: RUN_FINISHED
started_at: 2026-08-25T05:55:18.6532078+03:30
ended_at: 2026-08-25T05:55:18.6532078+03:30
duration_ms: 0
goal_id: G-PLAN
run_id: STAB-GPLAN-R00
state_before: DOCUMENTED
state_after: DOCUMENTED
actor: codex
action_kind: DECISION
cwd: <project-root>
intent: توقف پیش از هر اصلاح کد و انتظار برای دستور کاربر
command_safe: N/A
files_intended: []
files_changed: []
pre_sha256: {}
post_sha256: {}
exit_code: N/A
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: awaiting_user_execution_command
retry_of: null
supersedes: null
external_effect: none
approval_ref: null
output_summary: برنامه آماده است؛ G-00 تا دریافت دستور صریح کاربر آغاز نشده است.
artifacts:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
```

### STAB-GPLAN-R01-S01 — اصلاح دامنه بر پایهٔ تصمیم تازهٔ کاربر

```yaml
event_id: STAB-GPLAN-R01-S01
event: STABILIZATION_PLAN_SCOPE_AMENDED
started_at: 2026-08-25T06:01:50.6557715+03:30
ended_at: 2026-08-25T06:13:23.0509738+03:30
duration_ms: 692395
goal_id: G-PLAN
run_id: STAB-GPLAN-R01
state_before: DOCUMENTED
state_after: DOCUMENTED
actor: codex
action_kind: DECISION
cwd: <project-root>
intent: حذف هدف rollback قراردادهای متأخر، حفظ نمایش کامل شماره در محصول و محدودکردن Bale به مهار خرابی بدون توسعهٔ تازه
command_safe:
  - rg <security-identity-bale-contract-evidence>
  - apply_patch <planning-and-canonical-document-amendment>
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
attempts:
  - attempt_id: STAB-GPLAN-R01-S01-A01
    result: FAIL
    failure_class: contract
    reason_code: patch_context_not_found
    effect: none
    summary: patch چندفایلی نخست به‌علت عبارت مورد انتظار نادرست در بخش G-06 اعمال نشد؛ هیچ فایل تغییر نکرد.
  - attempt_id: STAB-GPLAN-R01-S01-A02
    result: PASS
    retry_of: STAB-GPLAN-R01-S01-A01
    summary: اصلاح plan و Findings با context دقیق و patchهای محدود اعمال شد.
  - attempt_id: STAB-GPLAN-R01-S01-A03
    result: FAIL
    failure_class: contract
    reason_code: patch_context_not_found
    effect: none
    summary: patch اسناد canonical به‌علت فرض نادرست دربارهٔ header سند Bale Discovery اعمال نشد؛ هیچ بخش patch تغییر نکرد.
  - attempt_id: STAB-GPLAN-R01-S01-A04
    result: PASS
    retry_of: STAB-GPLAN-R01-S01-A03
    summary: Baseline، Specification، Discovery و Architecture با patchهای دقیق و مستقل اصلاح شدند.
files_intended:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/CURRENT_SYSTEM_BASELINE.md
  - docs/project-memory/BALE_PROVIDER_DISCOVERY.md
  - ARCHITECTURE_DECISIONS.md
  - docs/PROJECT_SPECIFICATION.md
  - docs/project-map/PROJECT_FILE_MAP.md
  - docs/project-map/SYMBOL_INDEX.json
  - docs/REPORTS_INDEX.md
files_changed:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/CURRENT_SYSTEM_BASELINE.md
  - docs/project-memory/BALE_PROVIDER_DISCOVERY.md
  - ARCHITECTURE_DECISIONS.md
  - docs/PROJECT_SPECIFICATION.md
pre_sha256:
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 8a8a5a74d455dcbe4f8340d3f4e6ad639668ebf7c9c9f520f2ccbbaaa50d0348
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 389424538c1cd7ba16df58852274855715b3e70a2a6a52f0678afb9ef7870874
  docs/project-memory/FINDINGS_REGISTER.md: ceb9ae8ca4397c01c5971472beb6259786aa77e4874d03f24f1ffa02d0b8984a
  docs/project-memory/VALIDATION_LEDGER.md: ff3a4c7b0e756e936666c6f9778204e3091ff32fce6f45892e53a37c74c2116c
  docs/project-memory/CURRENT_SYSTEM_BASELINE.md: 67a1e42901b40adf06b742f5558bba26d1aa6fcdac2e8f70ee636e2cae7f0c3f
  docs/project-memory/BALE_PROVIDER_DISCOVERY.md: 9dec89d103b1067bdd711b4fd044b1ff118bc71a24c6fcfab0fec545bb323821
  ARCHITECTURE_DECISIONS.md: 7f943d5c161f8355ce9f37c74c3b662a21d286820cffda56fee4691d2d6d7419
  docs/PROJECT_SPECIFICATION.md: fd5cdb7b20686edb71a103b523cfa21f681c1c62e640ddbc2cb396b979486f31
post_sha256:
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 49321f69d40c265948202b9ff85ff05ab1d5f2b0eb18fcf566abfaff822b199c
  docs/project-memory/FINDINGS_REGISTER.md: fbad766c1b98abc44894a8589ac3af2234f3e35e961d468099773be9ad09da26
  docs/project-memory/VALIDATION_LEDGER.md: 123ba285bd9b48987f2c3dd73c407b6b777209e497ee768f4e6486b5a740f069
  docs/project-memory/CURRENT_SYSTEM_BASELINE.md: 3d0e8e0052bc4dce9121b35b45d2c4ae0a0befc4cb0c7569a41bf531329f1a99
  docs/project-memory/BALE_PROVIDER_DISCOVERY.md: 105885e250e309f7c19ecb07b6e951cbca7cdff9b7cd1cce2666510296d01f39
  ARCHITECTURE_DECISIONS.md: c4610eb358f9c86b26e141d551926ab8d05ed92e402ee996574fcfb0e0fe2107
  docs/PROJECT_SPECIFICATION.md: 7d0a3d1d4338214eade19d435457cac00733fc779dd9efe82bab70c2c33c836c
  self_referential_file: omitted
exit_code: 0
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: user_security_contract_scope_applied
retry_of: null
supersedes: null
external_effect: none
approval_ref: user-goal-amendment-2026-08-25
output_summary: G-04 دیگر masking را بازنمی‌گرداند؛ نمایش کامل در محصول حفظ و منع ثبت آن در لاگ مستقل شد. F-040 فقط runtime safety blocker است. refresh/check/check-links هر سه exit code صفر داشتند.
artifacts:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/FINDINGS_REGISTER.md#F-046
  - docs/project-memory/VALIDATION_LEDGER.md#V-105
  - ARCHITECTURE_DECISIONS.md#34
```

### STAB-GPLAN-R01-S02 — پایان Run اصلاح دامنه

```yaml
event_id: STAB-GPLAN-R01-S02
event: RUN_FINISHED
started_at: 2026-08-25T06:13:23.0509738+03:30
ended_at: 2026-08-25T06:13:23.0509738+03:30
duration_ms: 0
goal_id: G-PLAN
run_id: STAB-GPLAN-R01
state_before: DOCUMENTED
state_after: DOCUMENTED
actor: codex
action_kind: DECISION
cwd: <project-root>
intent: پایان amendment بدون شروع اصلاح کد
command_safe: N/A
files_intended: []
files_changed: []
pre_sha256: {}
post_sha256: {}
exit_code: N/A
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: plan_amended_awaiting_execution_scope
retry_of: null
supersedes: null
external_effect: none
approval_ref: null
output_summary: هیچ کد یا عملیات Provider آغاز نشد؛ اهداف اجرایی G-00 تا G-09 باز هستند.
artifacts:
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
```

### STAB-GPAUSE-R00-S01 — توقف فوری کاربر

```yaml
event_id: STAB-GPAUSE-R00-S01
event: USER_PAUSED
started_at: 2026-08-25T06:16:50.0038568+03:30
ended_at: 2026-08-25T06:16:50.0038568+03:30
duration_ms: 0
goal_id: G-PLAN
run_id: STAB-GPAUSE-R00
state_before: DOCUMENTED
state_after: USER_PAUSED
actor: user_approved_operation
action_kind: DECISION
cwd: <project-root>
intent: توقف فوری و حفظ نقطهٔ ازسرگیری
command_safe: N/A
files_intended:
  - docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/README.md
files_changed:
  - docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/README.md
pre_sha256:
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 49321f69d40c265948202b9ff85ff05ab1d5f2b0eb18fcf566abfaff822b199c
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 2eaf3628c779223e4caa58617ef93d4db9b6ae66abfe2cd2d52382345488dbad
  docs/project-memory/VALIDATION_LEDGER.md: 123ba285bd9b48987f2c3dd73c407b6b777209e497ee768f4e6486b5a740f069
  docs/project-memory/README.md: 205e076d2449fd27f3d93161a763faa6a0b84b1482e1461a685953325bb884a1
post_sha256_before_resume:
  docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md: f1a36c941abb999993ff06c009303ea73384fd3ad0c2413376733f5ae3401f2b
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 63a458b58b04fdc9539d467dbaff5fcd0fea361565ebe3b7239fe8ba87e71753
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 5d8152db5ea22a557b0689e8f2a1fcb91af076a4b42a0594a828ab85a142dacf
  docs/project-memory/VALIDATION_LEDGER.md: e0d2039626b15eca1143adba0f919127ec93f6fc7d800f3cf2a36d23e43c7c33
  docs/project-memory/README.md: 82b20b6d6fc43f42ac6e96081b378a3713c353ed45555c704820f3a1a652a06f
exit_code: N/A
result: PARTIAL
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: user_requested_immediate_stop_before_doc_refresh
retry_of: null
supersedes: null
external_effect: none
approval_ref: user-pause-request
output_summary: Handoff و V-106 نوشته شدند؛ به‌علت دستور توقف فوری generator/check اجرا نشد. این کار ناتمام در ازسرگیری بررسی می‌شود.
artifacts:
  - docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-106
```

### STAB-GRESUME-R00-S01 — ازسرگیری و RED اسناد

```yaml
event_id: STAB-GRESUME-R00-S01
event: USER_RESUMED
started_at: 2026-08-25T22:54:14.9396835+03:30
ended_at: 2026-08-25T22:54:24.1396835+03:30
duration_ms: 9200
goal_id: G-PLAN
run_id: STAB-GRESUME-R00
state_before: USER_PAUSED
state_after: RED_VERIFIED
actor: codex
action_kind: TEST
cwd: <project-root>
intent: بررسی یکپارچگی باقی‌مانده از توقف و شروع همکاری Codex/AntiGravity
command_safe:
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
files_intended: []
files_changed: []
pre_sha256:
  docs/REPORTS_INDEX.md: 539df5c32e4780dbc2995c534a9859f957ba5f3cb4dbcefc3922e5709ae992a9
post_sha256:
  docs/REPORTS_INDEX.md: 539df5c32e4780dbc2995c534a9859f957ba5f3cb4dbcefc3922e5709ae992a9
exit_code: 1
result: FAIL
test_counts: {collected: 2, passed: 0, failed: 2, errors: 0, skipped: 0}
failure_class: test_drift
reason_code: generated_reports_index_stale_after_user_pause
retry_of: null
supersedes: null
external_effect: read_only
approval_ref: user-resume-and-fix-all-request
output_summary: هر دو docs check فقط STALE بودن docs/REPORTS_INDEX.md را گزارش کردند؛ هیچ broken link یا تغییر source بررسی‌شده‌ای ثبت نشد.
artifacts:
  - docs/handoffs/STABILIZATION_PAUSE_HANDOFF_2026-08-25.md
```

### STAB-GRESUME-R00-S02 — تکمیل Handoff مشترک و GREEN اسناد

```yaml
event_id: STAB-GRESUME-R00-S02
event: RESUME_DOCUMENTATION_GREEN
started_at: 2026-08-25T22:54:24.1396835+03:30
ended_at: 2026-08-25T22:56:55.3996741+03:30
duration_ms: 151260
goal_id: G-PLAN
run_id: STAB-GRESUME-R00
state_before: RED_VERIFIED
state_after: REGRESSION_GREEN
actor: codex
action_kind: GENERATE
cwd: <project-root>
intent: رفع stale artifact، ایجاد قرارداد همکاری و Handoff قابل‌فهم برای AntiGravity
command_safe:
  - apply_patch <collaboration-protocol-current-handoff-resume-log>
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check
  - .\.venv\Scripts\python.exe scripts\refresh_project_docs.py --check --check-links
files_intended:
  - docs/project-memory/CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/README.md
  - docs/REPORTS_INDEX.md
files_changed:
  - docs/project-memory/CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/README.md
  - docs/REPORTS_INDEX.md
pre_sha256:
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: 63a458b58b04fdc9539d467dbaff5fcd0fea361565ebe3b7239fe8ba87e71753
  docs/project-memory/STABILIZATION_EXECUTION_LOG.md: 5d8152db5ea22a557b0689e8f2a1fcb91af076a4b42a0594a828ab85a142dacf
  docs/project-memory/README.md: 82b20b6d6fc43f42ac6e96081b378a3713c353ed45555c704820f3a1a652a06f
  docs/REPORTS_INDEX.md: 539df5c32e4780dbc2995c534a9859f957ba5f3cb4dbcefc3922e5709ae992a9
post_sha256:
  docs/project-memory/CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md: 73de69d58d30adb474c4911055fb6750a7bdf31536677800b366adb9a1cde62f
  docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md: 474f1dd93db4657245132098ac35e2cd9151cc9c455db17533f95edf49e3eba7
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: ab68463895975feb4198ffbad8192efa8bcf57537a01c507464645ded4abd97c
  docs/project-memory/README.md: 16d4e7dd1afa33926d944a07dc94fb5e0fddd32d744130a8f571573158b3d302
  docs/REPORTS_INDEX.md: 7dd2f31c033b1e961769c929d2a640aec062c5068f0a711a0b5e4f54af073a46
  self_referential_file: omitted
exit_code: 0
result: PASS
test_counts: {collected: 2, passed: 2, failed: 0, errors: 0, skipped: 0}
failure_class: none
reason_code: resume_docs_and_links_green
retry_of: STAB-GRESUME-R00-S01
supersedes: null
external_effect: none
approval_ref: user-resume-and-fix-all-request
output_summary: REPORTS_INDEX به‌روزرسانی شد؛ docs check و docs+links هر دو exit code صفر دارند. قرارداد همکاری و Handoff جاری ایجاد شدند.
artifacts:
  - docs/project-memory/CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-107
```

### STAB-GRESUME-R00-S03 — پایان Run ازسرگیری

```yaml
event_id: STAB-GRESUME-R00-S03
event: RUN_FINISHED
started_at: 2026-08-25T22:56:55.3996741+03:30
ended_at: 2026-08-25T22:56:55.3996741+03:30
duration_ms: 0
goal_id: G-PLAN
run_id: STAB-GRESUME-R00
state_before: REGRESSION_GREEN
state_after: DOCUMENTED
actor: codex
action_kind: DECISION
cwd: <project-root>
intent: بستن ازسرگیری و انتقال کنترل به G-00
command_safe: N/A
files_intended: []
files_changed: []
pre_sha256: {}
post_sha256: {}
exit_code: N/A
result: PASS
test_counts: {collected: N/A, passed: N/A, failed: N/A, errors: N/A, skipped: N/A}
failure_class: none
reason_code: resume_complete_start_g00
retry_of: null
supersedes: null
external_effect: none
approval_ref: null
output_summary: ثبت توقف کامل شد و اولین Goal اجرایی G-00 می‌تواند آغاز شود.
artifacts:
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G00-R01-S01 — آغاز و RED فاز baseline

```yaml
event_id: STAB-G00-R01-S01
event: RUN_STARTED_AND_RED_VERIFIED
started_at: 2026-08-25T22:58:22.9642834+03:30
ended_at: 2026-08-25T22:58:22.9642834+03:30
duration_ms: 0
goal_id: G-00
run_id: STAB-G00-R01
state_before: QUEUED
state_after: RED_VERIFIED
actor: codex
action_kind: TEST
cwd: <project-root>
intent: اثبات نبود repository و نبود ابزار baseline قابل‌آزمون
command_safe:
  - git rev-parse --is-inside-work-tree
  - .\.venv\Scripts\python.exe -m pytest tests\test_stabilization_baseline.py -q
files_intended:
  - tests/test_stabilization_baseline.py
files_changed:
  - tests/test_stabilization_baseline.py
pre_sha256:
  tests/test_stabilization_baseline.py: absent
post_sha256:
  tests/test_stabilization_baseline.py: 7908862b7712343f8bce8d864341c9f301d9b5dc9d0beadc2692e16e7c180589
exit_code: 1
result: FAIL
test_counts: {collected: 0, passed: 0, failed: 0, errors: 1, skipped: 0}
failure_class: product_regression
reason_code: repository_and_baseline_tool_missing
retry_of: null
supersedes: null
external_effect: test_temp
approval_ref: user-fix-all-phased-request
output_summary: Git exit 128 و pytest collection error با ModuleNotFoundError؛ warning cache محیطی جدا ثبت شد.
artifacts:
  - docs/reports/stabilization/G00_TRACEABILITY_BASELINE_REPORT_2026-08-25.md
```

### STAB-G00-R01-S02 — baseline، تست و بازیابی Git

```yaml
event_id: STAB-G00-R01-S02
event: TRACEABILITY_BASELINE_CREATED
started_at: 2026-08-25T22:58:22.9642834+03:30
ended_at: 2026-08-25T23:08:12.0018711+03:30
duration_ms: 589038
goal_id: G-00
run_id: STAB-G00-R01
state_before: RED_VERIFIED
state_after: TARGETED_GREEN
actor: codex
action_kind: OPERATION
cwd: <project-root>
intent: ساخت baseline قابل‌بازگشت و اتصال metadata ریشه به تاریخچهٔ legacy بدون stage/commit
command_safe:
  - apply_patch <baseline-tool-tests-gitignore>
  - .\.venv\Scripts\python.exe -m pytest tests\test_stabilization_baseline.py -q -p no:cacheprovider
  - .\.venv\Scripts\python.exe scripts\stabilization_baseline.py
  - independent archive receipt/hash/scope verification
  - git init -b stabilization
  - git remote add legacy <legacy-workspace>
  - git fetch --no-tags legacy main:refs/remotes/legacy/main
  - git update-ref refs/heads/stabilization refs/remotes/legacy/main
attempts:
  - attempt_id: STAB-G00-R01-S02-A01
    result: PASS
    summary: targeted baseline tests 2/2 green with cacheprovider disabled.
  - attempt_id: STAB-G00-R01-S02-A02
    result: PASS
    summary: deterministic archive/receipt created for 613 safe files.
  - attempt_id: STAB-G00-R01-S02-A03
    result: FAIL
    failure_class: test_drift
    reason_code: verification_regex_overbroad
    effect: none
    summary: independent regex counted 7 documentation paths because it matched forbidden words below root.
  - attempt_id: STAB-G00-R01-S02-A04
    result: PASS
    retry_of: STAB-G00-R01-S02-A03
    summary: top-level operational-scope verifier returned forbidden_entry_count=0.
  - attempt_id: STAB-G00-R01-S02-A05
    result: PARTIAL
    failure_class: environment
    reason_code: git_metadata_owned_by_sandbox
    summary: initial repository/history connection succeeded but host Git rejected ownership; default shell refresh failed.
  - attempt_id: STAB-G00-R01-S02-A06
    result: FAIL
    failure_class: permission
    reason_code: global_safe_directory_rejected
    effect: none
    summary: global safe.directory request was rejected as unnecessarily weakening ownership checks; no global config changed.
  - attempt_id: STAB-G00-R01-S02-A07
    result: PASS
    retry_of: STAB-G00-R01-S02-A05
    summary: sandbox-owned metadata moved to recoverable ignored artifact; repository rebuilt with Windows owner and local history reconnected.
files_intended:
  - .gitignore
  - scripts/stabilization_baseline.py
  - tests/test_stabilization_baseline.py
  - artifacts/stabilization/STAB-G00-R01-safe-baseline.zip
  - artifacts/stabilization/STAB-G00-R01-safe-baseline.receipt.json
  - .git metadata
files_changed:
  - .gitignore
  - scripts/stabilization_baseline.py
  - tests/test_stabilization_baseline.py
  - artifacts/stabilization/STAB-G00-R01-safe-baseline.zip
  - artifacts/stabilization/STAB-G00-R01-safe-baseline.receipt.json
  - .git metadata
pre_sha256:
  .gitignore:
    status: unavailable
    reason: logging-gap-pre-hash-was-not-captured-before-first-G00-patch
  scripts/stabilization_baseline.py: absent
  tests/test_stabilization_baseline.py: absent
post_sha256:
  .gitignore: cf2cbaf1c01188144957cec1bbe1dadd9ce21a72b8e45ca3af36f51db503346e
  scripts/stabilization_baseline.py: 2aee314d50eec5d6cc909af26f9a50ad42676333dd70396bafb76a8ebbaedfc0
  tests/test_stabilization_baseline.py: 7908862b7712343f8bce8d864341c9f301d9b5dc9d0beadc2692e16e7c180589
  baseline_zip: 70908224926eb45791bdc504558478756328743f0a9f7b8355f19b30d73ca8ab
  baseline_receipt: f89f96b4d883fd9ccca85e9f42bce68561b4233fd01abd629e38ac6d26491fcb
exit_code: 0
result: PASS
test_counts: {collected: 2, passed: 2, failed: 0, errors: 0, skipped: 0}
failure_class: none
reason_code: crypto_baseline_and_git_history_connected
retry_of: STAB-G00-R01-S01
supersedes: null
external_effect: config
approval_ref: user-fix-all-phased-request
output_summary: 613-file deterministic recovery snapshot verified; Git refs connected; owner corrected; no global trust weakening, stage or commit.
artifacts:
  - docs/reports/stabilization/G00_TRACEABILITY_BASELINE_REPORT_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-108
  - docs/project-memory/FINDINGS_REGISTER.md#F-039
```

### STAB-G00-R01-S03 — پایان G-00 مجاز

```yaml
event_id: STAB-G00-R01-S03
event: RUN_FINISHED
started_at: 2026-08-25T23:08:12.0018711+03:30
ended_at: 2026-08-25T23:08:12.0018711+03:30
duration_ms: 0
goal_id: G-00
run_id: STAB-G00-R01
state_before: TARGETED_GREEN
state_after: DOCUMENTED
actor: codex
action_kind: DECISION
cwd: <project-root>
intent: بستن دامنهٔ مجاز G-00 و انتقال به G-01
command_safe: N/A
files_intended: []
files_changed: []
pre_sha256: {}
post_sha256: {}
exit_code: N/A
result: PASS
test_counts: {collected: 2, passed: 2, failed: 0, errors: 0, skipped: 0}
failure_class: none
reason_code: g00_complete_without_stage_or_commit
retry_of: null
supersedes: null
external_effect: none
approval_ref: null
output_summary: baseline و تاریخچه قابل‌دسترسی‌اند؛ commit gate باز است و G-01 آغاز می‌شود.
artifacts:
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G01-R01-S01 — RED سلامت حافظه و ساخت checker

```yaml
event_id: STAB-G01-R01-S01
event: DOCUMENTATION_INTEGRITY_RED_AND_CHECKER_CREATED
recorded_at: 2026-08-25T23:30:34.7125859+03:30
time_precision_note: زمان آغاز ممیزی 2026-08-25T23:12:25.4921629+03:30 ثبت شد؛ timestamp دقیق پایان تک‌تک retryها پیش از اجرا capture نشده و از ترتیب toolها جعل نمی‌شود.
goal_id: G-01
run_id: STAB-G01-R01
state_before: QUEUED
state_after: RED_VERIFIED
actor: codex
action_kind: TEST_FIRST_AND_STATIC_AUDIT
cwd: <project-root>
intent: اثبات ماشینی خرابی encoding/ID/Markdown و افزودن guard دائمی قابل‌فهم برای AntiGravity
red_attempts:
  - attempt_id: STAB-G01-R01-S01-A01
    command_safe: .\.venv\Scripts\python.exe -m pytest tests\test_project_memory_integrity.py -q -p no:cacheprovider
    result: FAIL
    reason_code: integrity_checker_module_missing
    counts: {collected: 0, errors: 1}
  - attempt_id: STAB-G01-R01-S01-A02
    command_safe: .\.venv\Scripts\python.exe scripts\check_project_memory_integrity.py --json
    result: FAIL_EXPECTED
    reason_code: existing_document_corruption
    issue_count: 143
    breakdown: {replacement_character: 2, question_mark_run: 129, control_character: 4, duplicate_validation_id: 2, malformed_command_row: 6}
  - attempt_id: STAB-G01-R01-S01-A03
    result: FAIL_ENVIRONMENT
    reason_code: pytest_default_temp_permission_denied
    counts: {errors: 3}
  - attempt_id: STAB-G01-R01-S01-A04
    result: FAIL_ENVIRONMENT
    reason_code: workspace_basetemp_parent_missing
    counts: {errors: 3}
  - attempt_id: STAB-G01-R01-S01-A05
    result: PASS
    retry_of: STAB-G01-R01-S01-A03
    summary: parent ایزوله ساخته شد و unitهای اولیه 3/3 سبز شدند.
files_intended:
  - scripts/check_project_memory_integrity.py
  - tests/test_project_memory_integrity.py
files_changed:
  - scripts/check_project_memory_integrity.py
  - tests/test_project_memory_integrity.py
pre_sha256:
  scripts/check_project_memory_integrity.py: absent
  tests/test_project_memory_integrity.py: absent
post_sha256:
  scripts/check_project_memory_integrity.py: 0ebbf7be58b654a9126e9ae1f1af50b7320f0fac3d303b24a40abd2c7e4236ac
  tests/test_project_memory_integrity.py: dff0614e63b742c9759e02459dd6f37966ed69009017c62fb7eb881d8e451736
exit_code: 1
result: FAIL_EXPECTED_THEN_TOOL_GREEN
failure_class: product_documentation_integrity
reason_code: corrupted_memory_and_missing_automated_guard
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: RED واقعی و مستقل ثبت شد؛ checker ساخته شد ولی repository تا ترمیم اسناد عمداً قرمز باقی ماند.
artifacts:
  - docs/reports/stabilization/G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md
```

### STAB-G01-R01-S02 — ترمیم مستندات و targeted GREEN

```yaml
event_id: STAB-G01-R01-S02
event: DOCUMENTATION_RECOVERED_AND_TARGETED_GREEN
recorded_at: 2026-08-25T23:30:34.7125859+03:30
goal_id: G-01
run_id: STAB-G01-R01
state_before: RED_VERIFIED
state_after: TARGETED_GREEN
actor: codex
action_kind: DOCUMENTATION_RECOVERY_AND_TEST
cwd: <project-root>
intent: بازیابی بدون حدس، حذف collision شناسه و همسان‌سازی ادعاهای جاری با V-103/F-046
recovery_attempts:
  - attempt_id: STAB-G01-R01-S02-A01
    result: FAIL_NO_EFFECT
    reason_code: patch_template_backtick_parse_error
  - attempt_id: STAB-G01-R01-S02-A02
    result: FAIL_NO_EFFECT
    reason_code: apply_patch_could_not_match_control_byte_hunk
  - attempt_id: STAB-G01-R01-S02-A03
    result: PARTIAL
    reason_code: simple_F035_lines_repaired_control_lines_remained
  - attempt_id: STAB-G01-R01-S02-A04
    result: PASS
    retry_of: STAB-G01-R01-S02-A02
    summary: محتوای دقیق خوانده، replacement محدود اعمال، ابتدا artifact موقت قابل‌بازیابی با apply_patch ساخته، original با apply_patch بازسازی و artifact موقت حذف شد.
  - attempt_id: STAB-G01-R01-S02-A05
    result: FAIL_ENVIRONMENT
    reason_code: git_owner_differs_from_sandbox_user
    summary: Git read-only بدون safe-directory invocation رد شد؛ config تغییر نکرد.
  - attempt_id: STAB-G01-R01-S02-A06
    result: PASS
    retry_of: STAB-G01-R01-S02-A05
    summary: git -c safe.directory=<project-root> diff --check exit 0؛ status index عمداً normalize نشده و برای دامنه تغییر معتبر نیست.
files_changed:
  - AGENTS.md
  - docs/PROJECT_SPECIFICATION.md
  - docs/project-memory/BALE_PROVIDER_DISCOVERY.md
  - docs/project-memory/CURRENT_SYSTEM_BASELINE.md
  - docs/project-memory/ENGINEERING_DOCUMENTATION_PROTOCOL.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/README.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/reports/features/PROJECT_FINALIZATION_REPORT_2026-08-21.md
  - docs/reports/stabilization/G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md
  - scripts/check_project_memory_integrity.py
  - tests/test_project_memory_integrity.py
pre_sha256:
  docs/project-memory/FINDINGS_REGISTER.md: 0936b7a83db9fa651af203b99260486d78658662ba362a9680fa50a00d8daddd
  docs/project-memory/VALIDATION_LEDGER.md: bb96de2e82e0c3ef2f54854731fbd60e49a65a8ef2dff95b8a8796a198f2c1d9
  docs/project-memory/BALE_PROVIDER_DISCOVERY.md: 105885e250e309f7c19ecb07b6e951cbca7cdff9b7cd1cce2666510296d01f39
  docs/project-memory/CURRENT_SYSTEM_BASELINE.md: e1c49df388e377253810b188669789ddee8e2630061ebf7e963494f991b9f40c
  docs/PROJECT_SPECIFICATION.md: 7d0a3d1d4338214eade19d435457cac00733fc779dd9efe82bab70c2c33c836c
  docs/reports/features/PROJECT_FINALIZATION_REPORT_2026-08-21.md: 12d9cc250cdde743d9527d17da10a0f948054180fe0cd11ab68d933adae1c03e
  AGENTS.md: 2963ce2f7d284826927c3e6424445ba4db5219b3c7daeec635d52d0dccddba8d
  docs/project-memory/ENGINEERING_DOCUMENTATION_PROTOCOL.md: b914c450ec4b5502764ac01a6e4a0e6a59065d29b3246b8e27aab99d8caf2e30
  docs/project-memory/README.md: 16d4e7dd1afa33926d944a07dc94fb5e0fddd32d744130a8f571573158b3d302
  docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md: ab68463895975feb4198ffbad8192efa8bcf57537a01c507464645ded4abd97c
targeted_results:
  pytest_integrity: 4/4_pass
  live_repository_checker: issue_count_0
  git_diff_check: pass_with_invocation_only_safe_directory
failure_class: none
reason_code: documentation_integrity_targeted_green
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: حافظه سالم و guard دائمی شد؛ final generated-doc/link check و ثبت V-109 باقی است.
artifacts:
  - docs/reports/stabilization/G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md
  - docs/project-memory/FINDINGS_REGISTER.md#F-035
```

### STAB-G01-R01-S03 — کشف report-index drift و پایان G-01

```yaml
event_id: STAB-G01-R01-S03
event: REPORT_INDEX_FIXED_AND_RUN_FINISHED
ended_at: 2026-08-25T23:34:39.3395055+03:30
goal_id: G-01
run_id: STAB-G01-R01
state_before: TARGETED_GREEN
state_after: DOCUMENTED
actor: codex
action_kind: TEST_FIRST_FIX_AND_ACCEPTANCE
cwd: <project-root>
intent: قابل‌کشف‌کردن گزارش‌های تثبیت و بستن همهٔ دروازه‌های G-01
attempts:
  - attempt_id: STAB-G01-R01-S03-A01
    result: PASS_BUT_FINDING
    summary: refresh/check/check-links سبز بود، اما inspection نشان داد stabilization در REPORT_GROUPS نیست.
  - attempt_id: STAB-G01-R01-S03-A02
    result: FAIL_EXPECTED
    command_safe: .\.venv\Scripts\python.exe -m pytest tests\test_refresh_project_docs.py -q
    reason_code: stabilization_report_group_missing
    counts: {collected: 1, failed: 1}
  - attempt_id: STAB-G01-R01-S03-A03
    result: PASS
    retry_of: STAB-G01-R01-S03-A02
    counts: {collected: 1, passed: 1}
  - attempt_id: STAB-G01-R01-S03-A04
    result: PASS
    summary: targeted combined 5/5؛ checker issue_count=0؛ generated docs/link checks exit0؛ diff-check exit0.
files_changed:
  - scripts/refresh_project_docs.py
  - tests/test_refresh_project_docs.py
  - docs/REPORTS_INDEX.md
  - docs/project-map/PROJECT_FILE_MAP.md
  - docs/project-map/SYMBOL_INDEX.json
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/reports/stabilization/G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md
post_sha256_before_closure_records:
  scripts/check_project_memory_integrity.py: 0ebbf7be58b654a9126e9ae1f1af50b7320f0fac3d303b24a40abd2c7e4236ac
  scripts/refresh_project_docs.py: d1c2c08524b4eaba76f9a7f27a5b3408f2c1b06ba8533df2eb05e036e9730e2e
  tests/test_project_memory_integrity.py: dff0614e63b742c9759e02459dd6f37966ed69009017c62fb7eb881d8e451736
  tests/test_refresh_project_docs.py: df968ea73c6cd2ba1240b41d765214b42c584517cfad471dbe4c377720170f47
  docs/REPORTS_INDEX.md: fdea7afae7163ee05fac4c1cb693a8cb79bcd01490984bbfb2db0152037c9388
  docs/project-map/PROJECT_FILE_MAP.md: da31ac21f25554be90427555890233c302251bc78e317a20dfcbda3b48d66f8a
  docs/project-map/SYMBOL_INDEX.json: 442a2bedf522b4dd313f060c8bd972d2c88a171d475e79f576114147c74f5a8c
test_counts: {collected: 5, passed: 5, failed: 0, errors: 0, skipped: 0}
exit_code: 0
result: PASS
failure_class: none
reason_code: g01_complete_documentation_guarded
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: G-01 بسته شد؛ حافظه clean، report index قابل‌کشف و G-02 آماده است.
artifacts:
  - docs/reports/stabilization/G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-109
  - docs/project-memory/FINDINGS_REGISTER.md#F-047
```

### STAB-G02-R01-S01 — RED مهار Bale

```yaml
event_id: STAB-G02-R01-S01
event: BALE_FAIL_CLOSED_RED_VERIFIED
started_at: 2026-08-25T23:38:28.0841702+03:30
goal_id: G-02
run_id: STAB-G02-R01
state_before: QUEUED
state_after: RED_VERIFIED
actor: codex
action_kind: TEST_FIRST
cwd: <project-root>
intent: اثبات آفلاین ادعای فعال نادرست، factory/adapter ناامن و BOM
attempts:
  - attempt_id: STAB-G02-R01-S01-A01
    result: ERROR_TEST_SETUP
    reason_code: wrong_test_store_import
    counts: {collected: 0, errors: 1}
  - attempt_id: STAB-G02-R01-S01-A02
    result: FAIL_EXPECTED_WITH_ONE_TEST_SETUP_DEFECT
    counts: {collected: 4, failed: 4}
    summary: سه failure محصولی و یک failure BOM؛ context test نیز یک keyword ناموجود داشت و قبل از constructor متوقف شد.
  - attempt_id: STAB-G02-R01-S01-A03
    result: RED_VALIDATED
    summary: setup context تست اصلاح شد؛ قرارداد موردانتظار fail-closed مستقل از secret واقعی تعریف شد.
pre_sha256:
  src/eitaa_bridge/providers/bale/slot.py: e88d695be22f272f5d499545fe6646b9c57a5c82214b3757ecaf222848798a72
  src/eitaa_bridge/application/bale_provider_adapter.py: 7d87058ec104d31616b394be86989222f263c08bdedb4cfe5b96196d1b8c2cd3
  tests/test_phase11b_provider_extension_foundation.py: ae0c1a2f55d1d721c9004b8a39158179602b2069919e5723d8f56573b28287c3
  tests/test_phase4d_account_management.py: 1aef63ec30833a5d4dbc5cf4783b0f24994732d535efba1a97af102950b68dc0
  ui/src/main.tsx: 1f9d6a9640f3ae73abc665be8bb3d4f3a71aecb9d4101525d888767a52d6630d
exit_code: 1
result: FAIL_EXPECTED
failure_class: product_runtime_safety
reason_code: bale_advertised_active_but_unverified_and_broken
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: RED معتبر ثبت شد؛ هیچ client/network/Live فراخوانی نشد.
artifacts:
  - tests/test_bale_stabilization_fail_closed.py
```

### STAB-G02-R01-S02 — quarantine، regression و پایان G-02

```yaml
event_id: STAB-G02-R01-S02
event: BALE_FAIL_CLOSED_AND_FULL_BACKEND_GREEN
ended_at: 2026-08-25T23:50:33.4768194+03:30
goal_id: G-02
run_id: STAB-G02-R01
state_before: RED_VERIFIED
state_after: DOCUMENTED
actor: codex
action_kind: CODE_TEST_DOCUMENTATION
cwd: <project-root>
intent: حفظ تصمیم F-046 و حذف هر مسیر اجرایی/ادعای Live تا فاز توسعهٔ جداگانه
implementation:
  - manifest implemented اما configured/runtime/onboarding false و بدون capability/auth/factory
  - adapter compatibility constructor quarantine قبل از client/session/network
  - BOM حذف و UI fixture صادقانه غیرفعال
  - test contracts قدیمی active Bale همسو شدند
retry_notes:
  - foundation پس از code patch یک failure expectation drift داشت؛ سپس 7/7 سبز شد.
  - account-management پس از code patch یک failure expectation drift داشت؛ سپس 9/9 سبز شد.
  - Phase11 onboarding UI همچنان روی allowlist assertion قدیمی شکست دارد و به G-06 منتقل است.
post_sha256:
  src/eitaa_bridge/providers/bale/slot.py: c610b8e6d3857060a63535be649727ba7a616172e0df079309550b1d66d746a0
  src/eitaa_bridge/application/bale_provider_adapter.py: d28ab48a6e6aa2dd2565772d81bc5546f40d95c1e50fbd6db67a238a4789aa9c
  tests/test_bale_stabilization_fail_closed.py: e1e0dc92b88d096c6326ca7de1e641551a846a05d781bf48071b747084254de5
  tests/test_phase11b_provider_extension_foundation.py: 77421efb9ba688e92c60084bbdc656833a20b96c78ec4deaf503761af4695225
  tests/test_phase4d_account_management.py: dd3c64916b7e53e9dade93851c6fff28d9b9198e9be1c7d5130c6ba88670c2d4
  ui/src/main.tsx: 388bf13e4bf81ca08f79a281375f495bf3c5011e3ad0526a9681ed993621aaac
  docs/project-map/PROJECT_FILE_MAP.md: 32f53e39be074658958a6d4afa52cfcf091a35b1a2b738fd7a06cacfb74bba5f
  docs/project-map/SYMBOL_INDEX.json: af8ea005d73946e738c84563a7f729ad1f8712bf0827e5aa212de898ccd8cc1d
  docs/REPORTS_INDEX.md: ee413e493e74afed7d3c99fe23e43171de74f8975f73c386ee01ac5be84dd03c
test_counts:
  dedicated: {collected: 5, passed: 5}
  targeted: {collected: 21, passed: 21}
  full_backend: {collected: 599, passed: 599}
  ui_b2: {collected: 6, passed: 6}
exit_code: 0
result: PASS
failure_class: none
reason_code: bale_safely_quarantined_full_backend_green
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: F-040 بسته؛ G-03 آماده است و هیچ عملیات Bale/Live انجام نشد.
artifacts:
  - docs/reports/stabilization/G02_BALE_FAIL_CLOSED_REPORT_2026-08-25.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-110
  - docs/project-memory/FINDINGS_REGISTER.md#F-040
```

### STAB-G03-R01-S01 — RED نصب تمیز و Legacy challenge

```yaml
event_id: STAB-G03-R01-S01
event: CLEAN_INSTALL_AUTH_RED_VERIFIED
started_at: 2026-08-25T23:52:00+03:30
goal_id: G-03
run_id: STAB-G03-R01
state_before: QUEUED
state_after: RED_VERIFIED
actor: codex
action_kind: TEST_FIRST
cwd: <project-root>
intent: اثبات آفلاین blockerهای Coordinator خالی و binding واقعی challenge در Legacy
attempts:
  - attempt_id: STAB-G03-R01-S01-A01
    result: ERROR_COLLECTION_EXPECTED
    reason_code: legacy_auth_challenge_model_missing
  - attempt_id: STAB-G03-R01-S01-A02
    result: ERROR_ENVIRONMENT
    reason_code: pytest_default_temp_permission_denied
    retry_of: STAB-G03-R01-S01-A01
  - attempt_id: STAB-G03-R01-S01-A03
    result: FAIL_WITH_TEST_DEFECT
    counts: {collected: 4, failed: 4}
    summary: سه failure محصولی و یک TypeError در test password material؛ test defect جداگانه اصلاح شد.
  - attempt_id: STAB-G03-R01-S01-A04
    result: RED_VALIDATED
    counts: {collected: 4, failed: 4}
    summary: empty-admin bootstrap، startup DB، challenge id و expiry همگی failure محصولی مستقل دادند.
pre_sha256:
  src/eitaa_bridge/application/api.py: 10805b4b8ef0c664396df2c998445923e67ac4a92ffc7fdbef6a8f2d15c5c594
  src/eitaa_bridge/application/account_auth.py: eb35a1614e0937a5f6fbbbe16b3eab0ba4c815bb43ee8f5b36d53cdbda7f4d04
  src/eitaa_bridge/application/account_runtime.py: 1632e533cfee3ee17a5ff30c6387a8e5cb029e37ff6b1e42b5cc2df1427ac3ae
  src/eitaa_bridge/infrastructure/coordinator/app_auth.py: b9ea2066ad017f7f99c05086619d380753fa6e92187047a9da88c75501cfaade
exit_code: 1
result: FAIL_EXPECTED
failure_class: clean_install_and_auth_contract
reason_code: f041_reproduced_by_executable_tests
external_effect: test_temp_only
approval_ref: user-fix-all-phased-request
output_summary: RED معتبر ثبت شد؛ هیچ Provider/Network/Login/OTP واقعی اجرا نشد.
artifacts:
  - tests/test_clean_install_auth_stabilization.py
```

### STAB-G03-R01-S02 — patch اولیه و توقف فوری کاربر

```yaml
event_id: STAB-G03-R01-S02
event: USER_PAUSED
paused_at: 2026-08-26T00:02:36.7075930+03:30
goal_id: G-03
run_id: STAB-G03-R01
state_before: IMPLEMENTING
state_after: USER_PAUSED
actor: codex
action_kind: CODE_AND_HANDOFF
cwd: <project-root>
intent: حفظ دقیق patch نیمه‌تمام و توقف به درخواست کاربر پیش از مصرف token بیشتر
implementation_unvalidated:
  - LegacyAuthChallenge با شناسه محلی، stage، expiry و allowlist summary
  - bootstrap اتمیک اولین مدیر در Coordinator واقعاً خالی
  - empty-bootstrap محدود برای startup چندحسابی بدون default
  - initialize خودکار Coordinator هنگام AppUser Auth
  - الزام challenge_id/stage/expiry در Legacy submit-code و submit-password
post_sha256:
  src/eitaa_bridge/application/api.py: a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6
  src/eitaa_bridge/application/account_auth.py: 6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da
  src/eitaa_bridge/application/account_runtime.py: 7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b
  src/eitaa_bridge/infrastructure/coordinator/app_auth.py: 637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c
  tests/test_clean_install_auth_stabilization.py: f88ffae3e15575039cd8e53dcc32a8ef22b734e9239c5b132910aec0db32f59d
tests_after_patch: NOT_RUN_USER_PAUSE
exit_code: null
result: INCOMPLETE
failure_class: user_requested_pause
reason_code: token_budget_near_exhaustion
external_effect: source_test_docs_and_test_temp_only
approval_ref: user-pause-request
output_summary: G-03 باز و patch آزموده‌نشده است؛ ادامه باید از targeted test آغاز شود، نه از اصلاح تازه یا ادعای GREEN.
artifacts:
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-111
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
```

### STAB-G03-R02-S01 — ازسرگیری، تطبیق هش و نخستین آزمون پس از patch

```yaml
event_id: STAB-G03-R02-S01
event: PAUSED_PATCH_HASH_MATCHED_AND_TARGETED_RETRY_EXECUTED
recorded_at: 2026-08-26T05:37:53.5336485+03:30
goal_id: G-03-A
run_id: STAB-G03-R02
state_before: USER_PAUSED_UNVALIDATED
state_after: TARGETED_PARTIAL_GREEN
actor: codex
action_kind: HASH_VERIFY_AND_TARGETED_TEST
cwd: <project-root>
intent: اعتبارسنجی دقیق patch نقطهٔ توقف بدون گسترش دامنه به regression بعدی
hash_verification:
  product_files_matched_v111: 4/4
attempt:
  attempt_id: STAB-G03-R02-S01-A01
  command_scope: tests/test_clean_install_auth_stabilization.py با basetemp ایزوله resume-a
  counts: {collected: 4, passed: 3, failed: 1}
  result: TEST_FIXTURE_CONTRACT_FAILURE
  reason_code: synthetic_password_material_length_violated_schema_check
  classification: test_drift_not_product_failure
exit_code: 1
external_effect: test_temp_only
approval_ref: user-resume-g03-phased-request
output_summary: سه قرارداد محصول سبز شدند؛ failure چهارم در دادهٔ مصنوعی fixture و پیش از هر اثر بیرونی رخ داد.
```

### STAB-G03-R02-S02 — اصلاح fixture و GREEN اختصاصی G-03-A

```yaml
event_id: STAB-G03-R02-S02
event: CLEAN_INSTALL_AUTH_TARGETED_GREEN
recorded_at: 2026-08-26T05:37:53.5336485+03:30
goal_id: G-03-A
run_id: STAB-G03-R02
state_before: TARGETED_PARTIAL_GREEN
state_after: TARGETED_GREEN
actor: codex
action_kind: TEST_FIXTURE_FIX_AND_RETRY
cwd: <project-root>
intent: همسوکردن test double مصنوعی با CHECK طول credential و تکرار مستقل چهار قرارداد
change_scope:
  product_files_changed: 0
  test_files_changed: 1
  description: فقط material مصنوعی fixture به طول معتبر schema تغییر کرد.
pre_sha256:
  tests/test_clean_install_auth_stabilization.py: f88ffae3e15575039cd8e53dcc32a8ef22b734e9239c5b132910aec0db32f59d
post_sha256:
  src/eitaa_bridge/application/api.py: a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6
  src/eitaa_bridge/application/account_auth.py: 6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da
  src/eitaa_bridge/application/account_runtime.py: 7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b
  src/eitaa_bridge/infrastructure/coordinator/app_auth.py: 637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c
  tests/test_clean_install_auth_stabilization.py: 1e5be6e0bbb998b2de8fd6aca442a48df5f4ec224286c4b9bf2a8d8b1c565344
attempt:
  attempt_id: STAB-G03-R02-S02-A01
  command_scope: tests/test_clean_install_auth_stabilization.py با basetemp ایزوله resume-b
  counts: {collected: 4, passed: 4}
  result: PASS
exit_code: 0
failure_class: none
reason_code: g03a_four_synthetic_contracts_green
external_effect: source_test_docs_and_test_temp_only
approval_ref: user-resume-g03-phased-request
output_summary: G-03-A فقط در سطح targeted سبز است؛ F-041 باز و G-03-B منتظر دستور کاربر است.
artifacts:
  - docs/project-memory/VALIDATION_LEDGER.md#V-112
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G03-R02-S03 — کنترل اسناد و توقف بین‌مرحله‌ای

```yaml
event_id: STAB-G03-R02-S03
event: G03A_DOCUMENTED_AND_PAUSED_AWAITING_USER
ended_at: 2026-08-26T05:40:31.7383806+03:30
goal_id: G-03-A
run_id: STAB-G03-R02
state_before: TARGETED_GREEN
state_after: USER_PAUSED_AWAITING_G03B
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: بستن مستقل زیرمرحله با حافظهٔ قابل‌فهم برای Codex و AntiGravity و توقف پیش از regression بعدی
documentation_controls:
  refresh_project_docs: {exit_code: 0, updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json]}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
acceptance:
  g03a: TARGETED_GREEN
  f041: OPEN
  g03b: NOT_STARTED_AWAITING_USER
external_effect: source_test_docs_and_test_temp_only
approval_ref: user-resume-g03-phased-request
output_summary: توقف کنترل‌شده انجام شد؛ هیچ regression مرحلهٔ بعد، Provider/Live یا Git mutation اجرا نشد.
```

### STAB-G03-R03-S01 — regression مرتبط G-03-B

```yaml
event_id: STAB-G03-R03-S01
event: G03B_RELATED_REGRESSION_GREEN
started_at: 2026-08-26T05:42:45.5898197+03:30
ended_at: 2026-08-26T05:43:34.0843609+03:30
goal_id: G-03-B
run_id: STAB-G03-R03
state_before: USER_PAUSED_AWAITING_G03B
state_after: RELATED_REGRESSION_GREEN
actor: codex
action_kind: RELATED_REGRESSION_TEST
cwd: <project-root>
intent: سنجش عدم regression در AppAuth، AppUser API، AccountRuntime و Application API پس از patch G-03
test_scope:
  - tests/test_app_user_auth.py
  - tests/test_app_user_api.py
  - tests/test_account_runtime.py
  - tests/test_application_api.py
attempt:
  attempt_id: STAB-G03-R03-S01-A01
  basetemp: artifacts/stabilization/pytest-g03b-r01-a
  counts: {collected: 57, passed: 57}
  result: PASS
hash_verification:
  product_files_unchanged: 4/4
  related_test_files_unchanged: 4/4
source_or_test_changes: none
exit_code: 0
failure_class: none
reason_code: g03b_related_regression_green_first_attempt
external_effect: test_temp_only
approval_ref: user-start-g03b-command
output_summary: regression مرتبط کامل سبز شد؛ G-03-C و Backend کامل اجرا نشدند.
artifacts:
  - docs/project-memory/VALIDATION_LEDGER.md#V-113
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G03-R03-S02 — ثبت نهایی و توقف G-03-B

```yaml
event_id: STAB-G03-R03-S02
event: G03B_DOCUMENTED_AND_PAUSED_AWAITING_USER
ended_at: 2026-08-26T05:46:16.0729909+03:30
goal_id: G-03-B
run_id: STAB-G03-R03
state_before: RELATED_REGRESSION_GREEN
state_after: USER_PAUSED_AWAITING_G03C
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: بستن زیرمرحلهٔ regression مرتبط و توقف پیش از adversarial/restart
documentation_controls:
  refresh_project_docs: {exit_code: 0, result: PASS}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
acceptance:
  g03a: TARGETED_GREEN
  g03b: RELATED_REGRESSION_GREEN
  f041: OPEN
  g03c: NOT_STARTED_AWAITING_USER
external_effect: docs_and_test_temp_only
approval_ref: user-start-g03b-command
output_summary: G-03-B کامل و مستند شد؛ توقف کنترل‌شده بدون Backend کامل، Provider/Live یا Git mutation.
```

### STAB-G03-R04-S01 — RED قراردادهای adversarial/restart

```yaml
event_id: STAB-G03-R04-S01
event: G03C_ADVERSARIAL_RESTART_RED_VERIFIED
started_at: 2026-08-26T05:51:39.0396706+03:30
goal_id: G-03-C
run_id: STAB-G03-R04
state_before: USER_PAUSED_AWAITING_G03C
state_after: RED_VERIFIED
actor: codex
action_kind: TEST_FIRST_ADVERSARIAL
cwd: <project-root>
intent: اثبات fail-closed بودن شناسه/stage/expiry/replay/supersession و چرخهٔ restart بدون Provider واقعی
contracts_added: 5
attempt:
  attempt_id: STAB-G03-R04-S01-A01
  basetemp: artifacts/stabilization/pytest-g03c-r01-red-a
  counts: {collected: 5, passed: 4, failed: 1}
  result: FAIL_EXPECTED
  failure_class: persistent_challenge_lifecycle
  reason_code: account_restart_left_challenge_pending
product_observation: پاسخ missing و عدم Provider call درست بود، اما رکورد Coordinator به expired reconcile نشد.
pre_sha256:
  src/eitaa_bridge/application/api.py: a8a4ae666684c010d63c4052038ea1d9f71fd7c28adce8bf1b70eb8b614174b6
  src/eitaa_bridge/application/account_auth.py: 6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da
  tests/test_clean_install_auth_stabilization.py: 1e5be6e0bbb998b2de8fd6aca442a48df5f4ec224286c4b9bf2a8d8b1c565344
  tests/test_account_auth_lifecycle.py: 89621f194f5a41ef6e26e18e7c10c92a7bf4d3219be49ed6b04bbd7861d00a25
exit_code: 1
external_effect: synthetic_test_temp_only
approval_ref: user-start-g03c-command
output_summary: RED یگانه و قابل‌تکرار ثبت شد؛ چهار قرارداد دفاعی دیگر از ابتدا سبز بودند.
```

### STAB-G03-R04-S02 — اصلاح restart، GREEN و regression مرتبط

```yaml
event_id: STAB-G03-R04-S02
event: G03C_ADVERSARIAL_RESTART_AND_RELATED_REGRESSION_GREEN
ended_at: 2026-08-26T05:54:03.9205955+03:30
goal_id: G-03-C
run_id: STAB-G03-R04
state_before: RED_VERIFIED
state_after: ADVERSARIAL_RESTART_GREEN
actor: codex
action_kind: CODE_TEST_AND_DIFF_VALIDATION
cwd: <project-root>
intent: reconcile اتمیک و audit‌شدهٔ challenge گم‌شده پس از restart و جلوگیری از وضعیت پایدار کاذب
implementation:
  - guard نبود AccountAuthChallenge/runtime تلاش محلی را می‌بندد.
  - رکورد challenge_pending با generation ثابت و reason challenge_runtime_missing به expired منتقل می‌شود.
  - metadata فقط stage امن را حمل می‌کند.
attempts:
  - attempt_id: STAB-G03-R04-S02-A01
    scope: پنج تست g03c با basetemp تازه
    counts: {collected: 5, passed: 5}
    result: PASS
  - attempt_id: STAB-G03-R04-S02-A02
    scope: clean-install + AccountAuth lifecycle + چهار suite G-03-B
    counts: {passed: 81}
    result: PASS
  - attempt_id: STAB-G03-R04-S02-A03
    scope: git diff check هدفمند بدون git-dir/work-tree صریح
    result: ERROR_ENVIRONMENT
    reason_code: git_worktree_not_auto_discovered
  - attempt_id: STAB-G03-R04-S02-A04
    retry_of: STAB-G03-R04-S02-A03
    scope: git diff check read-only با git-dir/work-tree صریح
    result: PASS
post_sha256:
  src/eitaa_bridge/application/api.py: 1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4
  src/eitaa_bridge/application/account_auth.py: 6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da
  tests/test_clean_install_auth_stabilization.py: 05ac08438f7da1b7692caa1bf4a9b0af846975ddf6ffe0d6d38df5ca5c7fea45
  tests/test_account_auth_lifecycle.py: ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882
exit_code: 0
failure_class: none
reason_code: g03c_adversarial_restart_green
external_effect: source_test_docs_and_synthetic_temp_only
approval_ref: user-start-g03c-command
output_summary: G-03-C سبز است؛ Backend کامل و UI اجرا نشد و F-041 باز ماند.
artifacts:
  - docs/project-memory/VALIDATION_LEDGER.md#V-114
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G03-R04-S03 — ثبت نهایی و توقف G-03-C

```yaml
event_id: STAB-G03-R04-S03
event: G03C_DOCUMENTED_AND_PAUSED_AWAITING_USER
ended_at: 2026-08-26T05:57:11.9650376+03:30
goal_id: G-03-C
run_id: STAB-G03-R04
state_before: ADVERSARIAL_RESTART_GREEN
state_after: USER_PAUSED_AWAITING_G03D
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: بستن مستقل adversarial/restart و توقف پیش از full regression
documentation_controls:
  refresh_project_docs: {exit_code: 0, updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json]}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
acceptance:
  g03a: TARGETED_GREEN
  g03b: RELATED_REGRESSION_GREEN
  g03c: ADVERSARIAL_RESTART_GREEN
  f041: OPEN
  g03d: NOT_STARTED_AWAITING_USER
external_effect: source_test_docs_and_synthetic_temp_only
approval_ref: user-start-g03c-command
output_summary: G-03-C کامل و مستند شد؛ توقف کنترل‌شده بدون Backend کامل، UI، Provider/Live یا Git mutation.
```

### STAB-G03-R05-S01 — full Backend و RED observability catalog

```yaml
event_id: STAB-G03-R05-S01
event: G03D_FULL_BACKEND_OBSERVABILITY_RED
started_at: 2026-08-26T05:59:22.9409854+03:30
goal_id: G-03-D
run_id: STAB-G03-R05
state_before: USER_PAUSED_AWAITING_G03D
state_after: FULL_REGRESSION_RED
actor: codex
action_kind: FULL_BACKEND_TEST
cwd: <project-root>
intent: پذیرش کامل Backend پس از تغییر guard مرکزی و افزودن قراردادهای G-03
attempt:
  attempt_id: STAB-G03-R05-S01-A01
  basetemp: artifacts/stabilization/pytest-g03d-r01-full-backend-a
  counts: {collected: 608, passed: 607, failed: 1}
  result: FAIL
  failure_class: observability_contract
  reason_code: g03_auth_events_missing_from_catalog
missing_events: [auth_challenge_denied, auth_challenge_expired]
path_verification: cwd و Resolve-Path فایل آزمون به AntiGravity2 اشاره داشتند؛ مسیر قدیمی traceback metadata bytecode بود.
exit_code: 1
external_effect: synthetic_test_temp_only
approval_ref: user-start-g03d-command
output_summary: یک regression مستقیم G-03 یافت شد؛ هیچ failure دیگر و هیچ Provider/Live وجود نداشت.
```

### STAB-G03-R05-S02 — catalog، Backend و UI سبز

```yaml
event_id: STAB-G03-R05-S02
event: G03D_FULL_BACKEND_AND_UI_CONTROLS_GREEN
ended_at: 2026-08-26T06:04:45.1200535+03:30
goal_id: G-03-D
run_id: STAB-G03-R05
state_before: FULL_REGRESSION_RED
state_after: FULL_REGRESSION_GREEN
actor: codex
action_kind: OBSERVABILITY_FIX_FULL_RETRY_AND_UI_VALIDATION
cwd: <project-root>
intent: ثبت privacy-safe رویدادهای مادی G-03 و اثبات عدم regression کامل
implementation:
  - auth_challenge_denied با authentication/rejected/audit_required ثبت شد.
  - auth_challenge_expired با authentication/rejected/audit_required ثبت شد.
attempts:
  - attempt_id: STAB-G03-R05-S02-A01
    scope: tests/test_observability_contract.py
    counts: {collected: 6, passed: 6}
    result: PASS
  - attempt_id: STAB-G03-R05-S02-A02
    scope: full Backend با basetemp تازه
    counts: {collected: 608, passed: 608}
    duration_seconds: 85.33
    result: PASS
  - attempt_id: STAB-G03-R05-S02-A03
    scope: npm UI TypeScript check
    result: PASS
  - attempt_id: STAB-G03-R05-S02-A04
    scope: npm UI/Electron observability contract
    result: PASS
  - attempt_id: STAB-G03-R05-S02-A05
    scope: git diff check هدفمند read-only
    result: PASS
not_repeated:
  phase10_local_activation: no_trigger_existing_f042_g06_drift
  phase11_onboarding: no_trigger_existing_f042_g06_drift
post_sha256:
  src/eitaa_bridge/application/api.py: 1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4
  src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py: 33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9
  tests/test_clean_install_auth_stabilization.py: 05ac08438f7da1b7692caa1bf4a9b0af846975ddf6ffe0d6d38df5ca5c7fea45
  tests/test_account_auth_lifecycle.py: ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882
  tests/test_observability_contract.py: 748b2d9437e2fcd82ad20047e77e356031b936364f740a08d9fcdf1bdc245ad5
exit_code: 0
failure_class: none
reason_code: g03d_full_regression_green
external_effect: source_docs_synthetic_test_temp_and_local_ts_metadata_only
approval_ref: user-start-g03d-command
output_summary: G-03-D سبز است؛ F-041 برای G-03-E باز و هیچ Live/Git mutation انجام نشد.
artifacts:
  - docs/project-memory/VALIDATION_LEDGER.md#V-115
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
```

### STAB-G03-R05-S03 — ثبت نهایی و توقف G-03-D

```yaml
event_id: STAB-G03-R05-S03
event: G03D_DOCUMENTED_AND_PAUSED_AWAITING_USER
ended_at: 2026-08-26T06:07:33.5911391+03:30
goal_id: G-03-D
run_id: STAB-G03-R05
state_before: FULL_REGRESSION_GREEN
state_after: USER_PAUSED_AWAITING_G03E
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: بستن full regression و توقف پیش از finalization و بستن finding
documentation_controls:
  refresh_project_docs: {exit_code: 0, updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json]}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
acceptance:
  g03a: TARGETED_GREEN
  g03b: RELATED_REGRESSION_GREEN
  g03c: ADVERSARIAL_RESTART_GREEN
  g03d: FULL_REGRESSION_GREEN
  f041: OPEN_FINALIZATION_PENDING
  g03e: NOT_STARTED_AWAITING_USER
external_effect: source_docs_synthetic_test_temp_and_local_ts_metadata_only
approval_ref: user-start-g03d-command
output_summary: G-03-D کامل و مستند شد؛ توقف کنترل‌شده بدون G-03-E، Provider/Live یا Git mutation.
```

### STAB-G03-R06-S01 — audit معیار خروج و acceptance تکمیلی

```yaml
event_id: STAB-G03-R06-S01
event: G03E_EXIT_CRITERIA_GAP_FOUND_AND_CLOSED
ended_at: 2026-08-26T06:13:09.7015697+03:30
goal_id: G-03-E
run_id: STAB-G03-R06
state_before: USER_PAUSED_AWAITING_G03E
state_after: FINALIZATION_EVIDENCE_GREEN
actor: codex
action_kind: TRACEABILITY_AUDIT_TEST_AND_FULL_REGRESSION
cwd: <project-root>
intent: جلوگیری از بستن کاذب F-041 و اثبات تمام معیارهای خروج رسمی G-03
gap:
  missing_evidence: [repeatable_empty_startup, isolated_installer_config_copy_rehearsal]
  product_defect_found: false
acceptance:
  attempt_id: STAB-G03-R06-S01-A01
  basetemp: artifacts/stabilization/pytest-g03e-r01-acceptance-a
  counts: {collected: 2, passed: 2}
  result: PASS
full_backend:
  attempt_id: STAB-G03-R06-S01-A02
  basetemp: artifacts/stabilization/pytest-g03e-r01-full-backend-a
  counts: {collected: 610, passed: 610}
  duration_seconds: 82.28
  result: PASS
not_repeated:
  ui_controls: no_ui_change_v115_evidence_current
post_sha256:
  src/eitaa_bridge/application/api.py: 1ac2f10ad3ca38861c39a9ed45effe2f954dde4c41daa8efd624456ade7ad1b4
  src/eitaa_bridge/application/account_auth.py: 6cea7a594c4a83afa647d57d8dd55be5a451a3885b45c0be0417d1a62b1785da
  src/eitaa_bridge/application/account_runtime.py: 7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b
  src/eitaa_bridge/infrastructure/coordinator/app_auth.py: 637cb60fd635a542de103b6a5ec405d3dfbe3078c3e92b926abcd0ea37e1048c
  src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py: 33a895d017a8175b4e8fb2d61969fcfaf2b0154b342221f0af43b5d5acb322a9
  tests/test_clean_install_auth_stabilization.py: 980d467153927d6f9b6d8b1ccacfb88ebb3db177dce94b8178524c9912b0830c
  tests/test_account_auth_lifecycle.py: ce9af830fc8e3300a0671e03b5420fd33bfd2908abcb12d6b66edd0456a82882
diff_check: {exit_code: 0, result: PASS}
exit_code: 0
failure_class: none
reason_code: g03_exit_criteria_fully_evidenced
external_effect: test_docs_and_synthetic_temp_only
approval_ref: user-start-g03e-command
output_summary: تمام معیارهای خروج G-03 سبز شد؛ F-041 آمادهٔ closure مستند است.
artifacts:
  - docs/reports/stabilization/G03_CLEAN_INSTALL_AUTH_STABILIZATION_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-116
  - docs/project-memory/FINDINGS_REGISTER.md#F-041
```

### STAB-G03-R06-S02 — closure نهایی G-03 و handoff به G-04

```yaml
event_id: STAB-G03-R06-S02
event: G03_COMPLETE_F041_CLOSED_AND_PAUSED
ended_at: 2026-08-26T06:17:21.1464636+03:30
goal_id: G-03-E
run_id: STAB-G03-R06
state_before: FINALIZATION_EVIDENCE_GREEN
state_after: USER_PAUSED_AWAITING_G04
actor: codex
action_kind: REPORT_FINDING_CLOSURE_AND_HANDOFF
cwd: <project-root>
intent: بستن traceable هدف G-03 بدون گسترش به G-04 یا release readiness عمومی
documentation_controls:
  refresh_project_docs:
    exit_code: 0
    updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json, REPORTS_INDEX.md]
  report_discovery: {result: PASS, reports_index_line: 153}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
acceptance:
  g03: COMPLETE
  f041: CLOSED
  final_backend: {collected: 610, passed: 610}
  release_ready: false
  g04: NOT_STARTED_AWAITING_USER
external_effect: test_docs_and_synthetic_temp_only
approval_ref: user-start-g03e-command
output_summary: G-03 بسته و پروژه در مرز G-04 متوقف شد؛ F-042/F-043/F-044 باز ماندند و هیچ Live/Git mutation انجام نشد.
```

### STAB-G04-R01-S01 — ممیزی قرارداد و RED هدفمند G-04-A

```yaml
event_id: STAB-G04-R01-S01
event: G04A_IDENTITY_PRIVACY_TARGETED_RED
ended_at: 2026-08-26T06:24:23.5049668+03:30
goal_id: G-04-A
run_id: STAB-G04-R01
state_before: USER_PAUSED_AWAITING_G04
state_after: RED_VERIFIED
actor: codex
action_kind: READ_WRITE_TEST
cwd: <project-root>
intent: تفکیک قرارداد مجاز نمایش محصول از ممنوعیت مستقل شماره در observability و اثبات نقص‌ها پیش از patch
files_changed:
  - tests/test_g04_identity_privacy_stabilization.py
pre_sha256:
  src/eitaa_bridge/infrastructure/coordinator/identity.py: 14de42290d97bb0ddc543ffa28dc41402b1619c9a3f91a85faaabaddefb32ac0
  src/eitaa_bridge/infrastructure/diagnostics/redaction.py: 3d688ab266d6856f49b412cfbcb4f82b05ad921139a0e409bdb1e48c9c186cbb
  tests/test_coordinator_schema.py: cfb6c6ebc41e04a6cc644c4bd1e6605fbc46ef610f929e2e40ef348658d0b04e
post_sha256:
  src/eitaa_bridge/infrastructure/coordinator/identity.py: 14de42290d97bb0ddc543ffa28dc41402b1619c9a3f91a85faaabaddefb32ac0
  src/eitaa_bridge/infrastructure/diagnostics/redaction.py: 3d688ab266d6856f49b412cfbcb4f82b05ad921139a0e409bdb1e48c9c186cbb
  tests/test_coordinator_schema.py: cfb6c6ebc41e04a6cc644c4bd1e6605fbc46ef610f929e2e40ef348658d0b04e
  tests/test_g04_identity_privacy_stabilization.py: d78bf0fb9c6c94b417d8420fbbcd613dba53271efb4f5a5834f4079ecad70280
attempt:
  attempt_id: STAB-G04-R01-S01-A01
  basetemp: artifacts/stabilization/pytest-g04a-r01-red-a
  counts: {collected: 3, passed: 1, failed: 2}
  result: FAIL_EXPECTED_RED
  exit_code: 1
verified_contract: canonical_product_display_allowed
failures:
  - {failure_class: test_drift, reason_code: legacy_phone_contract_tests_are_placeholders}
  - {failure_class: privacy_contract, reason_code: identity_hint_keys_not_redacted}
privacy_control: synthetic input؛ failure output و اسناد فاقد مقدار کامل هستند.
full_regression: SKIPPED_INTENTIONAL_RED_NO_PRODUCT_CHANGE
external_effect: test_docs_and_synthetic_basetemp_only
approval_ref: user-start-g04-command
artifacts:
  - docs/reports/stabilization/G04A_IDENTITY_PRIVACY_RED_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-117
  - docs/project-memory/FINDINGS_REGISTER.md#F-044
output_summary: دو RED مستقل بدون rollback قرارداد نمایش و بدون تغییر کد محصول تثبیت شدند.
```

### STAB-G04-R01-S02 — ثبت کامل و توقف پیش از G-04-B

```yaml
event_id: STAB-G04-R01-S02
event: G04A_DOCUMENTED_AND_PAUSED_AWAITING_USER
ended_at: 2026-08-26T06:29:12.4681729+03:30
goal_id: G-04-A
run_id: STAB-G04-R01
state_before: RED_VERIFIED
state_after: USER_PAUSED_AWAITING_G04B
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: ثبت کامل REDها و توقف کنترل‌شده بدون ورود به patch محصول G-04-B
documentation_controls:
  refresh_project_docs:
    exit_code: 0
    updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json, REPORTS_INDEX.md]
  report_discovery: {result: PASS, reports_index_line: 154}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
  targeted_diff_check: {exit_code: 0, result: PASS}
acceptance:
  g04a: RED_VERIFIED
  product_display_contract: PASS
  placeholder_contract: FAIL_EXPECTED_RED
  identity_hint_redaction: FAIL_EXPECTED_RED
  f044: OPEN
  g04b: NOT_STARTED_AWAITING_USER
post_sha256:
  tests/test_g04_identity_privacy_stabilization.py: d78bf0fb9c6c94b417d8420fbbcd613dba53271efb4f5a5834f4079ecad70280
  docs/reports/stabilization/G04A_IDENTITY_PRIVACY_RED_REPORT_2026-08-26.md: dfec21b13e4f300ef1ae8829b5cda9f1bb05685f50500ef13c7867e09359c14e
external_effect: test_docs_generated_indexes_and_synthetic_basetemp_only
approval_ref: user-start-g04-command
output_summary: G-04-A کامل و مستند شد؛ دو RED برای G-04-B باز و کار طبق دستور کاربر متوقف است.
```

### STAB-G04-R02-S01 — اصلاح و پذیرش مستقل G-04-B

```yaml
event_id: STAB-G04-R02-S01
event: G04B_IDENTITY_REDACTION_TARGETED_AND_RELATED_GREEN
ended_at: 2026-08-26T06:35:38.0172023+03:30
goal_id: G-04-B
run_id: STAB-G04-R02
state_before: RED_VERIFIED
state_after: RELATED_REGRESSION_GREEN
actor: codex
action_kind: SOURCE_TEST_PATCH_AND_VALIDATION
cwd: <project-root>
intent: بستن دو RED V-117 بدون بازگرداندن masking محصول
implementation:
  - دو placeholder منقضی با قراردادهای غیرخالی persistence/display جایگزین شدند.
  - phone_hint و display_hint وارد redaction مشترک شدند.
attempts:
  - attempt_id: STAB-G04-R02-S01-A01
    basetemp: artifacts/stabilization/pytest-g04b-r01-targeted-a
    scope: tests/test_g04_identity_privacy_stabilization.py
    counts: {collected: 3, passed: 3}
    result: PASS
  - attempt_id: STAB-G04-R02-S01-A02
    basetemp: artifacts/stabilization/pytest-g04b-r01-related-a
    scope: coordinator_schema + diagnostics + observability + g04
    counts: {collected: 28, passed: 28}
    result: PASS
post_sha256:
  src/eitaa_bridge/infrastructure/diagnostics/redaction.py: 8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe
  tests/test_coordinator_schema.py: e06789ad01726a9544ceb8fbbe36405e6580f17b901948cabd3290f7192e35e3
  tests/test_g04_identity_privacy_stabilization.py: 9a7e80a3ef542bfc289b42185bbcaec77c6a7c6b9c495051785a26afa4d1bbe6
exit_code: 0
failure_class: none
reason_code: g04b_identity_redaction_green
full_regression: DEFERRED_TO_G04E
external_effect: source_test_docs_and_synthetic_basetemp_only
approval_ref: user-start-g04b-and-g04c-command
artifacts:
  - docs/reports/stabilization/G04B_IDENTITY_REDACTION_GREEN_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-118
output_summary: G-04-B سبز شد؛ ورود به G-04-C طبق همان فرمان کاربر مجاز است.
```

### STAB-G04-R02-S02 — ثبت نهایی G-04-B و ورود مجاز به G-04-C

```yaml
event_id: STAB-G04-R02-S02
event: G04B_DOCUMENTED_AND_G04C_AUTHORIZED
ended_at: 2026-08-26T06:38:17.0286808+03:30
goal_id: G-04-B
run_id: STAB-G04-R02
state_before: RELATED_REGRESSION_GREEN
state_after: DOCUMENTED_G04C_IN_PROGRESS
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
documentation_controls:
  refresh_project_docs: {exit_code: 0, updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json, REPORTS_INDEX.md]}
  report_discovery: {result: PASS, reports_index_line: 155}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
  targeted_diff_check: {exit_code: 0, result: PASS}
acceptance: {g04b: TARGETED_AND_RELATED_GREEN, f044: OPEN, g04c: AUTHORIZED_BY_SAME_USER_COMMAND}
external_effect: source_test_docs_generated_indexes_and_synthetic_basetemp_only
approval_ref: user-start-g04b-and-g04c-command
output_summary: G-04-B با لاگ کامل بسته شد و G-04-C بدون نیاز به پرسش میانی، طبق دستور صریح کاربر آغاز می‌شود.
```

### STAB-G04-R03-S01 — RED جداسازی token از هویت تلفنی عمومی

```yaml
event_id: STAB-G04-R03-S01
event: G04C_PUBLIC_IDENTITY_BOUNDARY_RED
ended_at: 2026-08-26T06:39:45+03:30
goal_id: G-04-C
run_id: STAB-G04-R03
state_before: DOCUMENTED_G04C_IN_PROGRESS
state_after: RED_VERIFIED
actor: codex
action_kind: TEST_FIRST_BACKEND_AND_UI_CONTRACT
cwd: <project-root>
attempts:
  - attempt_id: STAB-G04-R03-S01-A01
    basetemp: artifacts/stabilization/pytest-g04c-r01-red-a
    scope: phone_validator + public_onboarding_token_rejection
    counts: {collected: 2, passed: 0, failed: 2}
    result: FAIL_EXPECTED_RED
  - attempt_id: STAB-G04-R03-S01-A02
    scope: ui_phase11_onboarding_contract
    passed_before_failure: 1
    result: FAIL_EXPECTED_RED
    exit_code: 1
failures:
  - {failure_class: contract, reason_code: e164_validator_accepts_token_shape}
  - {failure_class: privacy_contract, reason_code: public_onboarding_accepts_token_field}
  - {failure_class: ui_contract_drift, reason_code: onboarding_allowlist_contains_token}
tool_behavior: UI assertion runner روی failure کل source API را dump کرد؛ PII/credential واقعی وجود نداشت.
external_effect: test_source_and_synthetic_basetemp_only
approval_ref: user-start-g04b-and-g04c-command
output_summary: سه شاهد مستقل پذیرش نادرست token در مرز تلفنی عمومی را اثبات کردند.
```

### STAB-G04-R03-S02 — GREEN و regression مرتبط G-04-C

```yaml
event_id: STAB-G04-R03-S02
event: G04C_PHONE_TOKEN_BOUNDARY_RELATED_GREEN
ended_at: 2026-08-26T06:42:22.0902921+03:30
goal_id: G-04-C
run_id: STAB-G04-R03
state_before: RED_VERIFIED
state_after: RELATED_REGRESSION_GREEN
actor: codex
action_kind: SOURCE_PATCH_TARGETED_AND_RELATED_VALIDATION
cwd: <project-root>
implementation:
  - E.164 validator فقط phone canonical را می‌پذیرد و branch token حذف شد.
  - public onboarding allowlist فقط provider/phone/label است.
  - descriptor غیر phone_e164 پیش از PhoneAccount persistence رد می‌شود.
attempts:
  - {attempt_id: STAB-G04-R03-S02-A01, scope: backend_targeted, counts: {collected: 2, passed: 2}, result: PASS}
  - {attempt_id: STAB-G04-R03-S02-A02, scope: ui_phase11_onboarding, counts: {passed: 7}, result: PASS}
  - {attempt_id: STAB-G04-R03-S02-A03, scope: related_backend_a, counts: {collected: 90, passed: 90}, result: PASS}
  - {attempt_id: STAB-G04-R03-S02-A04, scope: related_backend_b, counts: {collected: 36, passed: 36}, result: PASS}
post_sha256:
  src/eitaa_bridge/application/api.py: c77364d8ee8cc2d82a08b13e975f5653f98999b854e62dc7f60164f0ba007a32
  src/eitaa_bridge/infrastructure/coordinator/identity.py: afe44246c207e6d8b753d5d310ae67fe4ccefad8ac882677aeed4849fe7f6dde
  src/eitaa_bridge/infrastructure/diagnostics/redaction.py: 8f54cb0655ddbe9bcfdc01fdddef205c8f9f77dd51d49cf3ee4faf1313a50bbe
  tests/test_g04_identity_privacy_stabilization.py: 57e992b76a75ee63a2ce4536988dcf11419b14c1f46b9b556d116b5312f75e54
  tests/test_phase11_0_multi_account_onboarding.py: ad520f90da77da2be8fda1e2fcae39153a5acddcc268e6e4416c779588cd6428
exit_code: 0
failure_class: none
reason_code: g04c_phone_token_boundary_green
full_regression: DEFERRED_TO_G04E
external_effect: source_test_docs_static_ui_and_synthetic_basetemp_only
approval_ref: user-start-g04b-and-g04c-command
artifacts:
  - docs/reports/stabilization/G04C_PUBLIC_ONBOARDING_IDENTITY_BOUNDARY_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-119
output_summary: G-04-C سبز است؛ token عمومی حذف، phone_e164 مستقل و Bale بدون توسعه باقی ماند.
```

### STAB-G04-R03-S03 — ثبت نهایی و توقف پیش از G-04-D

```yaml
event_id: STAB-G04-R03-S03
event: G04C_DOCUMENTED_AND_PAUSED_AWAITING_G04D
ended_at: 2026-08-26T06:46:28.3055795+03:30
goal_id: G-04-C
run_id: STAB-G04-R03
state_before: RELATED_REGRESSION_GREEN
state_after: USER_PAUSED_AWAITING_G04D
actor: codex
action_kind: DOCUMENTATION_VALIDATION_AND_HANDOFF
cwd: <project-root>
intent: بستن مستقل G-04-C و توقف بدون ورود به privacy scan یا full regression
documentation_controls:
  refresh_project_docs: {exit_code: 0, updated: [PROJECT_FILE_MAP.md, SYMBOL_INDEX.json, REPORTS_INDEX.md]}
  report_discovery: {result: PASS, reports_index_line: 156}
  memory_integrity: {exit_code: 0, result: PASS}
  generated_docs_stale_check: {exit_code: 0, result: PASS}
  markdown_link_check: {exit_code: 0, result: PASS}
  targeted_diff_check: {exit_code: 0, result: PASS}
acceptance:
  g04b: TARGETED_AND_RELATED_GREEN
  g04c: TARGETED_AND_RELATED_GREEN
  phase11_onboarding_ui: {passed: 7}
  related_backend: {passed: 126}
  f042_phase11_onboarding: GREEN
  f044: OPEN_G04D_G04E_PENDING
  g04d: NOT_STARTED_AWAITING_USER
post_sha256:
  docs/reports/stabilization/G04C_PUBLIC_ONBOARDING_IDENTITY_BOUNDARY_REPORT_2026-08-26.md: dc16ed56e0ffd1edfc64738884ea82bd67f2c6083f423975bc6dc85a68700cbc
external_effect: source_test_docs_generated_indexes_static_ui_and_synthetic_basetemp_only
approval_ref: user-start-g04b-and-g04c-command
output_summary: G-04-B و G-04-C کامل و ثبت شدند؛ پروژه پیش از G-04-D طبق بخش‌بندی کاربر متوقف است.
```

### STAB-G04-R04-S01 — RED پنج‌گانهٔ کانال‌های privacy

```yaml
event_id: STAB-G04-R04-S01
event: G04D_FOUR_CHANNEL_PRIVACY_RED
ended_at: 2026-08-26T17:18:30+03:30
goal_id: G-04-D
run_id: STAB-G04-R04
state_before: USER_PAUSED_AWAITING_G04D
state_after: RED_VERIFIED
actor: codex
action_kind: ADVERSARIAL_TEST_FIRST
cwd: <project-root>
attempt:
  attempt_id: STAB-G04-R04-S01-A01
  basetemp: artifacts/stabilization/pytest-g04d-r01-red-a
  counts: {collected: 5, passed: 0, failed: 5}
  result: FAIL_EXPECTED_RED
failures:
  - {channel: runtime_log, reason_code: unknown_nested_private_value_retained}
  - {channel: diagnostic, reason_code: unknown_nested_private_value_retained}
  - {channel: audit, reason_code: private_metadata_persisted_and_exported}
  - {channel: support_bundle, reason_code: global_e164_retained}
  - {channel: support_scanner, reason_code: global_e164_not_detected}
privacy_control: synthetic markers؛ failure messages فاقد echo؛ stdout bundle فقط مسیر basetemp را داشت.
exit_code: 1
external_effect: synthetic_test_db_logs_diagnostics_and_bundle_only
approval_ref: user-start-g04d-command
output_summary: هر پنج privacy control نقص واقعی و مستقل نشان دادند؛ patch پیش از RED اعمال نشده بود.
```

### STAB-G04-R04-S02 — hardening مشترک و regression سبز

```yaml
event_id: STAB-G04-R04-S02
event: G04D_PRIVACY_CHANNELS_ADVERSARIAL_AND_RELATED_GREEN
ended_at: 2026-08-26T17:26:42.6042148+03:30
goal_id: G-04-D
run_id: STAB-G04-R04
state_before: RED_VERIFIED
state_after: RELATED_REGRESSION_GREEN
actor: codex
action_kind: SOURCE_SCRIPT_PATCH_TARGETED_AND_RELATED_VALIDATION
cwd: <project-root>
implementation:
  - generic/nested string redaction برای global phone، Bearer و provider-token shape.
  - Audit redaction پیش از hash/persistence و دفاع دوباره در query/export.
  - همسان‌سازی global phone pattern در Support Bundle creator/scanner.
attempts:
  - {attempt_id: STAB-G04-R04-S02-A01, scope: g04d_targeted, counts: {collected: 5, passed: 5}, result: PASS}
  - {attempt_id: STAB-G04-R04-S02-A02, scope: privacy_related_a, counts: {collected: 53, passed: 53}, result: PASS}
  - {attempt_id: STAB-G04-R04-S02-A03, scope: privacy_related_b, counts: {collected: 2, passed: 2}, result: PASS}
  - {attempt_id: STAB-G04-R04-S02-A04, scope: privacy_related_c, counts: {collected: 50, passed: 50}, result: PASS}
post_sha256:
  src/eitaa_bridge/infrastructure/diagnostics/redaction.py: 10eb93c1a3ff08845764d55b39c04ba21ed45888e5b767f28c66dbb9ba37a9a4
  src/eitaa_bridge/infrastructure/coordinator/store.py: b7ceb3c5b41bd3071f93e9331623794939eb9ee293210317d068cc65844ef710
  src/eitaa_bridge/infrastructure/coordinator/audit.py: 385f2621726584fe8bc5b6b3b1a8c69b942f8ae62763666464a3d5350b631f22
  scripts/create_diagnostics_bundle.py: 480805802c27b27814f20f60a6fe8a2a9c33c3d58fd67f7b53a959cf81538202
  scripts/scan_diagnostics_bundle.py: b02e66e97a7fcce4661634bf34eeaa117a332f9e50d6f43cb30008b4a143a4cc
  tests/test_g04d_privacy_channels.py: 5096701603a670a3270ddc368ce88ef54c4de0e50acc3359d271eded6bc5244e
exit_code: 0
failure_class: none
reason_code: g04d_privacy_channels_green
full_regression: DEFERRED_TO_G04E
external_effect: source_scripts_tests_docs_and_synthetic_basetemp_only
approval_ref: user-start-g04d-command
artifacts:
  - docs/reports/stabilization/G04D_PRIVACY_CHANNELS_ADVERSARIAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-120
output_summary: چهار کانال privacy و scanner با regression مرتبط سبزند؛ G-04-E هنوز اجرا نشده است.
```

### STAB-G04-R04-S03 — ثبت نهایی و توقف پیش از G-04-E

```yaml
event_id: STAB-G04-R04-S03
event: G04D_DOCUMENTATION_CONTROLS_AND_USER_PAUSE
ended_at: 2026-08-26T17:33:10.1147864+03:30
goal_id: G-04-D
run_id: STAB-G04-R04
state_before: RELATED_REGRESSION_GREEN
state_after: USER_PAUSED_AWAITING_G04E
actor: codex
action_kind: DOCUMENTATION_REFRESH_INTEGRITY_LINK_AND_DIFF_CHECK
cwd: <project-root>
controls:
  - {name: project_docs_refresh, result: UPDATED_GENERATED_MAPS_AND_INDEX, exit_code: 0}
  - {name: memory_integrity, result: PASS, exit_code: 0}
  - {name: generated_docs_stale_check, result: PASS, exit_code: 0}
  - {name: generated_docs_link_check, result: PASS, exit_code: 0}
  - {name: targeted_diff_check, result: PASS, exit_code: 0}
report:
  path: docs/reports/stabilization/G04D_PRIVACY_CHANNELS_ADVERSARIAL_REPORT_2026-08-26.md
  reports_index_line: 157
  sha256: 42cdbf1084169ba268c1565a36b4306464e7a71fa826e049a0467a1a6df3061f
full_backend: DEFERRED_TO_G04E_BY_PHASE_BOUNDARY
finding_state: F-044_OPEN_FINALIZATION_PENDING
external_effect: documentation_and_generated_indexes_only
approval_ref: user-start-g04d-command
output_summary: G-04-D کامل، کنترل‌های ثبت سبز و پروژه پیش از G-04-E طبق درخواست بخش‌بندی‌شدهٔ کاربر متوقف است.
```

### STAB-G04-R05-S01 — آغاز G-04-E و ممیزی معیار خروج A تا D

```yaml
event_id: STAB-G04-R05-S01
event: G04E_EXIT_CRITERIA_AND_HASH_AUDIT
ended_at: 2026-08-26T17:37:23.3669292+03:30
goal_id: G-04-E
run_id: STAB-G04-R05
state_before: USER_PAUSED_AWAITING_G04E
state_after: EXIT_AUDIT_GREEN_FULL_REGRESSION_PENDING
actor: codex
action_kind: READ_ONLY_EXIT_AUDIT_AND_SHA256_COMPARISON
cwd: <project-root>
attempts:
  - {attempt_id: STAB-G04-R05-S01-A01, scope: hash_audit_with_two_assumed_paths, result: TOOL_PATH_ERROR, exit_code: 1, product_failure: false}
  - {attempt_id: STAB-G04-R05-S01-A02, scope: hash_audit_with_discovered_project_paths, result: PASS, exit_code: 0, drift_count: 0}
matched_sha256:
  identity.py: afe44246c207e6d8b753d5d310ae67fe4ccefad8ac882677aeed4849fe7f6dde
  api.py: c77364d8ee8cc2d82a08b13e975f5653f98999b854e62dc7f60164f0ba007a32
  redaction.py: 10eb93c1a3ff08845764d55b39c04ba21ed45888e5b767f28c66dbb9ba37a9a4
  store.py: b7ceb3c5b41bd3071f93e9331623794939eb9ee293210317d068cc65844ef710
  audit.py: 385f2621726584fe8bc5b6b3b1a8c69b942f8ae62763666464a3d5350b631f22
  create_diagnostics_bundle.py: 480805802c27b27814f20f60a6fe8a2a9c33c3d58fd67f7b53a959cf81538202
  scan_diagnostics_bundle.py: b02e66e97a7fcce4661634bf34eeaa117a332f9e50d6f43cb30008b4a143a4cc
  test_coordinator_schema.py: e06789ad01726a9544ceb8fbbe36405e6580f17b901948cabd3290f7192e35e3
  test_g04_identity_privacy_stabilization.py: 57e992b76a75ee63a2ce4536988dcf11419b14c1f46b9b556d116b5312f75e54
  test_phase11_0_multi_account_onboarding.py: ad520f90da77da2be8fda1e2fcae39153a5acddcc268e6e4416c779588cd6428
  test_g04d_privacy_channels.py: 5096701603a670a3270ddc368ce88ef54c4de0e50acc3359d271eded6bc5244e
exit_criteria:
  canonical_product_display_preserved: EVIDENCED_BY_G04A_B
  obsolete_masking_assertions_absent: EVIDENCED_BY_G04B
  public_phone_onboarding_token_separated: EVIDENCED_BY_G04C
  runtime_audit_diagnostic_bundle_privacy: EVIDENCED_BY_G04D
  full_regression_and_docs: PENDING
external_effect: read_only_hash_and_document_audit_only
approval_ref: user-start-g04e-command
output_summary: معیارهای A تا D و هش‌های snapshot بدون drift پذیرفته شدند؛ full regression پیش از closure اجباری است.
```

### STAB-G04-R05-S02 — full Backend قرمز و بازسنجی timeoutها

```yaml
event_id: STAB-G04-R05-S02
event: G04E_FULL_BACKEND_RED_AND_TIMEOUT_ISOLATION_GREEN
ended_at: 2026-08-26T17:50:48.5774909+03:30
goal_id: G-04-E
run_id: STAB-G04-R05
state_before: EXIT_AUDIT_GREEN_FULL_REGRESSION_PENDING
state_after: FULL_REGRESSION_RED_CLEAN_RERUN_PENDING
actor: codex
action_kind: FULL_BACKEND_AND_TARGETED_TIMEOUT_RECHECK
cwd: <project-root>
attempts:
  - {attempt_id: STAB-G04-R05-S02-A01, scope: full_backend, basetemp: artifacts/stabilization/pytest-g04e-r01-full-a, counts: {collected: 620, passed: 618, failed: 2}, result: FAIL, exit_code: 1}
  - {attempt_id: STAB-G04-R05-S02-A02, scope: two_timed_out_worker_nodes_in_isolation, basetemp: artifacts/stabilization/pytest-g04e-r01-timeout-isolation-a, counts: {collected: 2, passed: 2}, result: PASS, exit_code: 0}
failures:
  - {test_area: phase7a_fake_worker_process, failure_class: subprocess_timeout, timeout_seconds: 10}
  - {test_area: phase7b_disabled_eitaa_entrypoint, failure_class: subprocess_timeout, timeout_seconds: 10}
product_patch: none
classification: likely_full_suite_timing_contention_not_yet_accepted
closure_gate: CLEAN_FULL_BACKEND_RERUN_REQUIRED
external_effect: synthetic_subprocess_and_basetemp_only
approval_ref: user-start-g04e-command
output_summary: دو timeout full-suite در isolation سبز شدند، اما F-044 تا full rerun کامل سبز باز می‌ماند.
```

### STAB-G04-R05-S03 — full rerun و کنترل‌های UI سبز

```yaml
event_id: STAB-G04-R05-S03
event: G04E_FULL_BACKEND_RERUN_AND_UI_GREEN
ended_at: 2026-08-26T17:55:40.7068899+03:30
goal_id: G-04-E
run_id: STAB-G04-R05
state_before: FULL_REGRESSION_RED_CLEAN_RERUN_PENDING
state_after: TECHNICAL_EXIT_CRITERIA_GREEN_DOCUMENTATION_PENDING
actor: codex
action_kind: CLEAN_FULL_BACKEND_RERUN_AND_UI_CONTRACT_VALIDATION
cwd: <project-root>
attempts:
  - {attempt_id: STAB-G04-R05-S03-A01, scope: full_backend_clean_rerun, basetemp: artifacts/stabilization/pytest-g04e-r02-full-b, counts: {collected: 620, passed: 620}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G04-R05-S03-A02, scope: ui_typescript, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G04-R05-S03-A03, scope: ui_electron_observability, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G04-R05-S03-A04, scope: phase11_onboarding_contract, counts: {passed: 7}, result: PASS, exit_code: 0}
product_patch: none
source_test_drift_count: 0
finding_state: F-044_TECHNICALLY_CLOSABLE
remaining_gate: DOCUMENTATION_INTEGRITY_AND_DISCOVERABILITY
external_effect: tests_and_synthetic_basetemp_only
approval_ref: user-start-g04e-command
output_summary: همهٔ دروازه‌های فنی G-04 سبزند؛ ثبت نهایی و کنترل اسناد باقی است.
```

### STAB-G04-R05-S04 — کنترل اسناد، closure و توقف پیش از G-05

```yaml
event_id: STAB-G04-R05-S04
event: G04_FINAL_DOCUMENTATION_CONTROLS_AND_USER_PAUSE
ended_at: 2026-08-26T17:59:36.5645404+03:30
goal_id: G-04-E
run_id: STAB-G04-R05
state_before: TECHNICAL_EXIT_CRITERIA_GREEN_DOCUMENTATION_PENDING
state_after: G04_COMPLETE_F044_CLOSED_USER_PAUSED_AWAITING_G05
actor: codex
action_kind: DOCUMENTATION_REFRESH_INTEGRITY_LINK_DIFF_AND_CLOSURE
cwd: <project-root>
controls:
  - {name: reports_index_refresh, result: UPDATED, exit_code: 0}
  - {name: memory_integrity, result: PASS, exit_code: 0}
  - {name: generated_docs_stale_check, result: PASS, exit_code: 0}
  - {name: generated_docs_link_check, result: PASS, exit_code: 0}
  - {name: targeted_diff_check, result: PASS, exit_code: 0}
report:
  path: docs/reports/stabilization/G04_IDENTITY_PRIVACY_STABILIZATION_FINAL_REPORT_2026-08-26.md
  reports_index_line: 154
  sha256: c0f1afd36abfca1a5c9a58fb609a4b321fd4338a4d63bbe4898f6a5dcb8afc08
finding_state: F-044_CLOSED
goal_state: G-04_COMPLETE
next_goal: G-05_AWAITING_EXPLICIT_USER_COMMAND
external_effect: documentation_and_generated_report_index_only
approval_ref: user-start-g04e-command
output_summary: G-04 و F-044 بسته، کنترل‌های اسناد سبز و پروژه پیش از G-05 متوقف شد.
```

### STAB-G05-R01-S01 — ممیزی و RED lifecycle ایندکس خودکار

```yaml
event_id: STAB-G05-R01-S01
event: G05A_AUTO_INDEX_LIFECYCLE_RED
ended_at: 2026-08-26T18:07:23.4317931+03:30
goal_id: G-05-A
run_id: STAB-G05-R01
state_before: G04_COMPLETE_USER_PAUSED_AWAITING_G05
state_after: G05A_RED_VERIFIED_AUTO_CONTINUE_G05B
actor: codex
action_kind: STATIC_AUDIT_AND_OFFLINE_TEST_FIRST
cwd: <project-root>
attempt:
  attempt_id: STAB-G05-R01-S01-A01
  basetemp: artifacts/stabilization/pytest-g05a-r01-red-a
  counts: {collected: 4, passed: 1, failed: 3}
  result: FAIL_EXPECTED_RED
  exit_code: 1
failures:
  - {contract: no_auto_index_thread_safe_default, reason_code: legacy_thread_started_and_survived_close}
  - {contract: scheduler_disabled_observability, reason_code: cataloged_event_missing}
  - {contract: broken_loop_removed, reason_code: unbounded_loop_still_present}
pass_contract: manual_content_index_routes_and_methods_preserved
test_cleanup: controlled_target_released_and_joined
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
external_effect: synthetic_config_log_db_and_controlled_thread_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G05A_AUTO_INDEX_LIFECYCLE_RED_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-122
output_summary: سه نقص F-043 با RED مستقل ثابت و قرارداد manual index سبز شد؛ B خودکار ادامه می‌یابد.
```

### STAB-G05-R01-S02 — safe-default و regression سبز

```yaml
event_id: STAB-G05-R01-S02
event: G05B_AUTO_INDEX_SAFE_DEFAULT_GREEN
ended_at: 2026-08-26T18:11:07.4219223+03:30
goal_id: G-05-B
run_id: STAB-G05-R01
state_before: G05A_RED_VERIFIED_AUTO_CONTINUE_G05B
state_after: G05B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G05C
actor: codex
action_kind: SOURCE_EVENT_CATALOG_PATCH_AND_REGRESSION
cwd: <project-root>
implementation:
  - removed_unbounded_startup_thread_and_loop
  - emitted_cataloged_correlated_safe_default_event
  - preserved_manual_content_index_contract
attempts:
  - {attempt_id: STAB-G05-R01-S02-A01, scope: g05_targeted, counts: {collected: 4, passed: 4}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G05-R01-S02-A02, scope: related_regression, counts: {collected: 76, passed: 76}, result: PASS, exit_code: 0}
product_failure: none
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
external_effect: source_tests_and_synthetic_basetemp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G05B_AUTO_INDEX_SAFE_DEFAULT_GREEN_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-123
output_summary: scheduler ناقص fail-closed حذف، event امن ثبت و manual index با regression سبز حفظ شد؛ C خودکار ادامه می‌یابد.
```

### STAB-G05-R01-S03 — guard تکرار lifecycle و Observability

```yaml
event_id: STAB-G05-R01-S03
event: G05C_REPEATED_LIFECYCLE_CORRELATION_GREEN
ended_at: 2026-08-26T18:13:36.8216662+03:30
goal_id: G-05-C
run_id: STAB-G05-R01
state_before: G05B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G05C
state_after: G05C_ADVERSARIAL_GREEN_AUTO_CONTINUE_G05D
actor: codex
action_kind: ADVERSARIAL_MULTI_START_CLOSE_AND_OBSERVABILITY_VALIDATION
cwd: <project-root>
attempt:
  attempt_id: STAB-G05-R01-S03-A01
  scope: g05_and_observability_contract
  basetemp: artifacts/stabilization/pytest-g05c-r01-adversarial-a
  counts: {collected: 11, passed: 11}
  result: PASS
  exit_code: 0
acceptance:
  repeated_start_close_cycles: 3
  orphan_auto_index_threads: 0
  scheduler_skipped_events: 3
  unique_correlations: 3
  private_or_account_scope_fields: 0
product_patch: none_since_g05b
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
external_effect: synthetic_api_config_log_db_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G05C_AUTO_INDEX_LIFECYCLE_ADVERSARIAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-124
output_summary: restart/close و correlation بدون orphan یا scope leak سبز شد؛ D خودکار ادامه می‌یابد.
```

### STAB-G05-R01-S04 — regression گسترده lifecycle/API

```yaml
event_id: STAB-G05-R01-S04
event: G05D_BROAD_RELATED_REGRESSION_GREEN
ended_at: 2026-08-26T18:16:13.7640296+03:30
goal_id: G-05-D
run_id: STAB-G05-R01
state_before: G05C_ADVERSARIAL_GREEN_AUTO_CONTINUE_G05D
state_after: G05D_BROAD_REGRESSION_GREEN_AUTO_CONTINUE_G05E
actor: codex
action_kind: BROAD_OFFLINE_RELATED_REGRESSION
cwd: <project-root>
attempt:
  attempt_id: STAB-G05-R01-S04-A01
  basetemp: artifacts/stabilization/pytest-g05d-r01-broad-a
  suites: 14
  counts: {collected: 143, passed: 143}
  result: PASS
  exit_code: 0
source_test_change: none
failure_or_retry: none
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
external_effect: tests_and_synthetic_basetemp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G05D_AUTO_INDEX_BROAD_REGRESSION_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-125
output_summary: regression گسترده سبز و E برای full regression/finalization خودکار آغاز می‌شود.
```

### STAB-G05-R01-S05 — full regression و closure فنی

```yaml
event_id: STAB-G05-R01-S05
event: G05E_FULL_REGRESSION_AND_TECHNICAL_CLOSURE_GREEN
ended_at: 2026-08-26T18:20:12.3765784+03:30
goal_id: G-05-E
run_id: STAB-G05-R01
state_before: G05D_BROAD_REGRESSION_GREEN_AUTO_CONTINUE_G05E
state_after: G05E_TECHNICAL_GREEN_DOCUMENTATION_PENDING
actor: codex
action_kind: FULL_BACKEND_UI_OBSERVABILITY_AND_EXIT_AUDIT
cwd: <project-root>
attempts:
  - {attempt_id: STAB-G05-R01-S05-A01, scope: full_backend, basetemp: artifacts/stabilization/pytest-g05e-r01-full-a, counts: {collected: 625, passed: 625}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G05-R01-S05-A02, scope: ui_typescript, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G05-R01-S05-A03, scope: ui_electron_observability, result: PASS, exit_code: 0}
failure_or_retry: none
finding_state: F-043_TECHNICALLY_CLOSED
remaining_gate: DOCUMENTATION_INTEGRITY_AND_DISCOVERABILITY
external_effect: tests_ui_static_and_synthetic_basetemp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G05_AUTO_INDEX_LIFECYCLE_STABILIZATION_FINAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-126
output_summary: همهٔ معیارهای فنی G-05 سبزند؛ کنترل نهایی اسناد باقی است.
```

### STAB-G05-R01-S06 — کنترل اسناد، closure و بازهٔ توقف پیش از G-06

```yaml
event_id: STAB-G05-R01-S06
event: G05_FINAL_DOCUMENTATION_CONTROLS_AND_AUTO_TRANSITION_WAIT
ended_at: 2026-08-26T18:22:53.8833894+03:30
goal_id: G-05-E
run_id: STAB-G05-R01
state_before: G05E_TECHNICAL_GREEN_DOCUMENTATION_PENDING
state_after: G05_COMPLETE_F043_CLOSED_AUTO_WAIT_G06
actor: codex
action_kind: DOCUMENTATION_REFRESH_INTEGRITY_LINK_DIFF_AND_CLOSURE
cwd: <project-root>
controls:
  - {name: reports_index_refresh, result: UPDATED, exit_code: 0}
  - {name: memory_integrity, result: PASS, exit_code: 0}
  - {name: generated_docs_stale_check, result: PASS, exit_code: 0}
  - {name: generated_docs_link_check, result: PASS, exit_code: 0}
  - {name: targeted_diff_check, result: PASS, exit_code: 0}
report:
  path: docs/reports/stabilization/G05_AUTO_INDEX_LIFECYCLE_STABILIZATION_FINAL_REPORT_2026-08-26.md
  reports_index_line: 159
  sha256: 4a2b5bc45dd61ebc41a8a52386f197d2393a5c2b1a40ae9cf3d5d29ab07cf386
finding_state: F-043_CLOSED
goal_state: G-05_COMPLETE
next_goal: G-06_AFTER_FIVE_MINUTES_UNLESS_USER_STOPS
external_effect: documentation_and_generated_report_index_only
approval_ref: user-start-g05-auto-phases-command
output_summary: G-05/F-043 بسته و بازهٔ پنج‌دقیقه‌ای توقف پیش از انتقال خودکار G-06 آغاز شد.
```

### STAB-G06-R01-S01 — ممیزی F-042 و RED Phase 10

```yaml
event_id: STAB-G06-R01-S01
event: G06A_TEST_CONTRACT_RED_AND_SCOPE_AUDIT
ended_at: 2026-08-26T18:32:46.7304049+03:30
goal_id: G-06-A
run_id: STAB-G06-R01
state_before: G05_COMPLETE_F043_CLOSED_AUTO_WAIT_G06
state_after: G06A_RED_VERIFIED_AUTO_CONTINUE_G06B
actor: codex
action_kind: STATIC_CONTRACT_AUDIT_AND_TEST_FIRST
cwd: <project-root>
canonical_red:
  phase10_runner: {passed_before_failure: 5, failed: 1, result: FAIL, exit_code: 1}
  python_guard: {collected: 3, passed: 2, failed: 1, basetemp: artifacts/stabilization/pytest-g06a-r03-red-c, result: FAIL, exit_code: 1}
green_scope:
  empty_python_test_contracts: 0
  invalid_skip_xfail_markers: 0
  other_ui_runners: 8
non_product_events:
  - powershell_quoting_error
  - windows_wildcard_error
  - bom_reader_fixture_error
  - assumed_helper_suffix_missing
resolved_not_reopened: [bale_bom, phase11_onboarding]
deferred_by_plan: packaging_to_g07
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
external_effect: tests_docs_and_ui_static_readers_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G06A_TEST_CONTRACT_RED_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-127
output_summary: تنها RED واقعی Phase10 import contract است؛ empty/skip guard و همهٔ runnerهای دیگر سبزند؛ B خودکار ادامه می‌یابد.
```

### STAB-G06-R01-S02 — اصلاح Phase 10 و regression سبز

```yaml
event_id: STAB-G06-R01-S02
event: G06B_PHASE10_IMPORT_CONTRACT_GREEN
ended_at: 2026-08-26T18:36:13.2017576+03:30
goal_id: G-06-B
run_id: STAB-G06-R01
state_before: G06A_RED_VERIFIED_AUTO_CONTINUE_G06B
state_after: G06B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G06C
actor: codex
action_kind: UI_TEST_RUNNER_PATCH_AND_RELATED_REGRESSION
cwd: <project-root>
implementation:
  - validate_real_helpers_tsx_import_and_export
  - remove_obsolete_local_definition_assertion
  - use_bounded_boolean_assertions_for_changed_contract
attempts:
  - {attempt_id: STAB-G06-R01-S02-A01, scope: python_guard, counts: {collected: 3, passed: 3}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G06-R01-S02-A02, scope: phase10_ui, counts: {passed: 7}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G06-R01-S02-A03, scope: related_backend, counts: {collected: 66, passed: 66}, result: PASS, exit_code: 0}
  - {attempt_id: STAB-G06-R01-S02-A04, scope: mobile_auth_static, result: PASS, exit_code: 0}
product_ui_change: none
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G06B_PHASE10_TEST_CONTRACT_GREEN_REPORT_2026-08-26.md
  reports_index_line: 165
  sha256: b01b575db3637d888b73591ea48550e24c66e4cdd8cef22056b652ad0e5b82cf
external_effect: test_runner_tests_and_synthetic_basetemp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G06B_PHASE10_TEST_CONTRACT_GREEN_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-128
output_summary: test drift Phase10 بسته، guardها و regression مرتبط سبز و C خودکار آغاز می‌شود.
```

### STAB-G06-R01-S03 — همهٔ قراردادهای UI، TypeScript و build

```yaml
event_id: STAB-G06-R01-S03
event: G06C_UI_TYPESCRIPT_LOCAL_BUILD_GREEN
ended_at: 2026-08-26T18:40:32.8043672+03:30
goal_id: G-06-C
run_id: STAB-G06-R01
state_before: G06B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G06C
state_after: G06C_UI_TYPESCRIPT_BUILD_GREEN_AUTO_CONTINUE_G06D
actor: codex
action_kind: TEST_AND_LOCAL_BUILD
cwd: <project-root>
attempts:
  - {scope: ui_scroll, passed: 10, result: PASS, exit_code: 0}
  - {scope: ui_grouped_media, passed: 16, result: PASS, exit_code: 0}
  - {scope: ui_phase9_workspace, passed_groups: [12, 15], result: PASS, exit_code: 0}
  - {scope: ui_phase9_acceptance, passed: 13, result: PASS, exit_code: 0}
  - {scope: ui_phase10, passed: 7, result: PASS, exit_code: 0}
  - {scope: ui_observability, result: PASS, exit_code: 0}
  - {scope: ui_phase11_onboarding, passed: 7, result: PASS, exit_code: 0}
  - {scope: ui_phase11b2, passed: 6, result: PASS, exit_code: 0}
  - {scope: ui_mobile_auth, result: PASS, exit_code: 0}
  - {scope: typescript_check, result: PASS, exit_code: 0}
  - {scope: local_ui_build, modules_transformed: 1015, result: PASS_WITH_WARNING, exit_code: 0}
warning: main_minified_chunk_794_74_kb_exceeds_500_kb
non_product_events:
  - git_status_refused_dubious_ownership
  - git_status_retried_with_command_scoped_safe_directory
packaging: not_executed_deferred_to_g07
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G06C_UI_CONTRACTS_TYPESCRIPT_BUILD_REPORT_2026-08-26.md
  reports_index_line: 166
  sha256: 77c2942993514554851d0a97cdacbbc3eabba2131c7eefe398cfc4752a295a08
external_effect: ui_static_readers_and_local_generated_dist_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G06C_UI_CONTRACTS_TYPESCRIPT_BUILD_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-129
output_summary: همهٔ UI contractها، TypeScript و build محلی سبزند؛ بسته‌بندی اجرا نشد و D خودکار آغاز می‌شود.
```

### STAB-G06-R01-S04 — regression گسترده Backend و skip accounting

```yaml
event_id: STAB-G06-R01-S04
event: G06D_BROAD_BACKEND_AND_SKIP_ACCOUNTING_GREEN
ended_at: 2026-08-26T18:44:58.4178182+03:30
goal_id: G-06-D
run_id: STAB-G06-R01
state_before: G06C_UI_TYPESCRIPT_BUILD_GREEN_AUTO_CONTINUE_G06D
state_after: G06D_BROAD_BACKEND_GREEN_AUTO_CONTINUE_G06E
actor: codex
action_kind: BROAD_OFFLINE_TEST_AND_COLLECTION
cwd: <project-root>
execution:
  suites: 35
  basetemp: artifacts/stabilization/pytest-g06d-r01-broad-a
  counts: {collected: 307, passed: 307, failed: 0, errors: 0, skipped: 0}
  result: PASS_WITH_ENVIRONMENT_WARNING
  exit_code: 0
collection_attempts:
  - {format: quiet_last_three_lines, result: PASS_TOTAL_NOT_RENDERED, exit_code: 0}
  - {format: canonical_no_cacheprovider, collected: 307, result: PASS, exit_code: 0}
warning: pytest_cache_nodeids_permission_denied
failure_class: environment_non_blocking
packaging: not_executed_deferred_to_g07
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G06D_BROAD_BACKEND_REGRESSION_REPORT_2026-08-26.md
  reports_index_line: 167
  sha256: c0db258fdc36dbca3a2309c103fa8f2f648e772d23149c99dd8064694808050f
external_effect: test_temp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G06D_BROAD_BACKEND_REGRESSION_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-130
output_summary: ۳۰۷ تست گسترده بدون skip/failure سبز شد؛ E full regression و closure دامنهٔ تست را ادامه می‌دهد.
```

### STAB-G06-R01-S05 — full Backend و پذیرش فنی G-06

```yaml
event_id: STAB-G06-R01-S05
event: G06E_FULL_BACKEND_AND_TEST_DOMAIN_TECHNICAL_CLOSURE
ended_at: 2026-08-26T18:49:28.1650887+03:30
goal_id: G-06-E
run_id: STAB-G06-R01
state_before: G06D_BROAD_BACKEND_GREEN_AUTO_CONTINUE_G06E
state_after: G06E_TECHNICAL_GREEN_DOCUMENTATION_PENDING
actor: codex
action_kind: FULL_OFFLINE_TEST_AND_ACCEPTANCE_AUDIT
cwd: <project-root>
full_backend:
  basetemp: artifacts/stabilization/pytest-g06e-r01-full-a
  cacheprovider: disabled
  counts: {collected: 628, passed: 628, failed: 0, errors: 0, skipped: 0}
  result: PASS
  exit_code: 0
collect_only: {collected: 628, result: PASS, exit_code: 0}
count_delta_from_g05: 3_g06_guard_tests
current_ui_evidence: V-129
targeted_whitespace_scan: {matches: 0, result: PASS}
finding_state: F-042_TEST_DOMAIN_CLOSED_PACKAGING_OPEN
release_state: NOT_RELEASE_READY
external_effect: test_temp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G06_TEST_CONTRACT_AND_REGRESSION_STABILIZATION_FINAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-131
output_summary: full Backend 628/628 و skip صفر؛ حوزهٔ تست G-06 بسته و final documentation در حال ثبت است.
```

### STAB-G06-R01-S06 — closure مستنداتی و handoff G-06

```yaml
event_id: STAB-G06-R01-S06
event: G06_DOCUMENTATION_CLOSURE_AND_AUTO_WAIT
ended_at: 2026-08-26T18:49:28.1650887+03:30
goal_id: G-06
run_id: STAB-G06-R01
state_before: G06E_TECHNICAL_GREEN_DOCUMENTATION_PENDING
state_after: G06_COMPLETE_TEST_DOMAIN_CLOSED_AUTO_WAIT_G07
actor: codex
action_kind: DOCUMENTATION_REFRESH_INTEGRITY_LINK_AND_CLOSURE
cwd: <project-root>
controls:
  - {name: reports_index_refresh, result: UPDATED, exit_code: 0}
  - {name: memory_integrity, result: PASS, exit_code: 0}
  - {name: generated_docs_stale_check, result: PASS, exit_code: 0}
  - {name: generated_docs_link_check, result: PASS, exit_code: 0}
  - {name: baseline_spec_findings_plan_handoff_alignment, result: PASS}
report:
  path: docs/reports/stabilization/G06_TEST_CONTRACT_AND_REGRESSION_STABILIZATION_FINAL_REPORT_2026-08-26.md
  reports_index_line: 164
  sha256: f55cdbee77c225599dfac4421d669b3af1810875292448cecd9cf6ac9d441e5f
finding_state: F-042_TEST_CONTRACT_DOMAIN_CLOSED_PACKAGING_OPEN
goal_state: G-06_COMPLETE
next_goal: G-07_AFTER_FIVE_MINUTES_UNLESS_USER_STOPS
release_state: NOT_RELEASE_READY
external_effect: documentation_and_generated_reports_index_only
approval_ref: user-start-g05-auto-phases-command
output_summary: G-06 با 628/628 و همهٔ UI/build contractها بسته شد؛ بازهٔ توقف پنج‌دقیقه‌ای پیش از G-07 آغاز می‌شود.
```

### STAB-G07-R01-S01 — ممیزی و RED بسته‌بندی

```yaml
event_id: STAB-G07-R01-S01
event: G07A_RELEASE_PACKAGING_RED
ended_at: 2026-08-26T19:02:28.8690935+03:30
goal_id: G-07-A
run_id: STAB-G07-R01
state_before: G06_COMPLETE_TEST_DOMAIN_CLOSED_AUTO_WAIT_G07
state_after: G07A_PACKAGING_RED_VERIFIED_AUTO_CONTINUE_G07B
actor: codex
action_kind: READ_BYTE_AUDIT_AND_SYNTHETIC_TEST_FIRST
cwd: <project-root>
root_causes:
  - package_clean_utf16le_with_1826_null_bytes_not_python_importable
  - recursive_blacklist_includes_unknown_root_scratch_and_probe_files
attempts:
  - {attempt_id: STAB-G07-R01-S01-A01, result: COLLECTION_ERROR, errors: 1, reason: source_contains_null_bytes, exit_code: 1}
  - {attempt_id: STAB-G07-R01-S01-A02, counts: {collected: 8, failed: 8}, result: RED_WITH_VERBOSE_SAFE_SOURCE_BYTES, exit_code: 1}
  - {attempt_id: STAB-G07-R01-S01-A03, basetemp: artifacts/stabilization/pytest-g07a-r03-red-c, counts: {collected: 8, failed: 8}, result: CANONICAL_RED, exit_code: 1}
harness_change: bounded_boolean_encoding_assertion
product_change: none
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G07A_RELEASE_PACKAGING_RED_REPORT_2026-08-26.md
  reports_index_line: 169
  sha256: dff3d3388a020c3e416d4479ee6a0882f200e592e022f711f8df366ab1c58e9d
external_effect: synthetic_test_zip_under_basetemp_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G07A_RELEASE_PACKAGING_RED_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-132
output_summary: UTF-16/NUL و نشت واقعی blacklist در fixture ثابت شد؛ هشت RED canonical و B خودکار آغاز می‌شود.
```

### STAB-G07-R01-S02 — جایگزینی allowlist و dry-run واقعی

```yaml
event_id: STAB-G07-R01-S02
event: G07B_RELEASE_ALLOWLIST_AND_MANIFEST_GREEN
ended_at: 2026-08-26T19:09:30.3246107+03:30
goal_id: G-07-B
run_id: STAB-G07-R01
state_before: G07A_PACKAGING_RED_VERIFIED_AUTO_CONTINUE_G07B
state_after: G07B_ALLOWLIST_TARGETED_GREEN_AUTO_CONTINUE_G07C
actor: codex
action_kind: RECOVERABLE_PREIMAGE_MOVE_SOURCE_WRITE_TEST_AND_DRY_RUN
cwd: <project-root>
tool_events:
  - {event: apply_patch_utf16_decode_refusal, result: FAIL, failure_class: tool_encoding}
  - {event: contained_preimage_move, target: artifacts/stabilization/G07A_package_clean_utf16_preimage_be8a9cf2.bin, result: PASS}
  - {event: windows_rg_wildcard_refusal, exit_code: 2, failure_class: invocation}
  - {event: rg_internal_glob_retry, result: PASS, exit_code: 0}
implementation:
  - explicit_release_allowlist
  - internal_content_manifest_and_external_receipt
  - deterministic_zip_order_timestamp_and_permissions
  - high_confidence_secret_scan
  - traversal_duplicate_collision_size_and_hash_verifier
  - write_free_dry_run
attempts:
  - {scope: py_compile, result: PASS, exit_code: 0}
  - {scope: targeted, basetemp: artifacts/stabilization/pytest-g07b-r01-targeted-a, counts: {collected: 8, passed: 8}, result: PASS, exit_code: 0}
  - {scope: related, basetemp: artifacts/stabilization/pytest-g07b-r01-related-a, counts: {collected: 21, passed: 21}, result: PASS, exit_code: 0}
dry_run:
  file_count: 296
  content_set_sha256: bf8483fea77af8b29fbc922daf475916bfc05ed83c02eb4d931792b274f52a72
  archive_exists: false
  receipt_exists: false
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G07B_RELEASE_ALLOWLIST_GREEN_REPORT_2026-08-26.md
  reports_index_line: 170
  sha256: 655ae6c036f6a5ba6985af05322699e0608ea8dc88a086a05b8f15f25b6df1fc
external_effect: source_test_docs_and_preserved_safe_preimage_artifact_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G07B_RELEASE_ALLOWLIST_GREEN_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-133
output_summary: allowlist/manifest/verifier سبز و dry-run واقعی بدون write؛ C خودکار آغاز می‌شود.
```

### STAB-G07-R01-S03 — adversarial archive و reproducibility

```yaml
event_id: STAB-G07-R01-S03
event: G07C_RELEASE_ARCHIVE_ADVERSARIAL_AND_REPRODUCIBLE_GREEN
ended_at: 2026-08-26T19:13:54.2503667+03:30
goal_id: G-07-C
run_id: STAB-G07-R01
state_before: G07B_ALLOWLIST_TARGETED_GREEN_AUTO_CONTINUE_G07C
state_after: G07C_ADVERSARIAL_REPRODUCIBLE_GREEN_AUTO_CONTINUE_G07D
actor: codex
action_kind: ADVERSARIAL_TEST_CONTROLLED_ARCHIVE_AND_INDEPENDENT_SCAN
cwd: <project-root>
tests:
  basetemp: artifacts/stabilization/pytest-g07c-r01-adversarial-a
  counts: {collected: 11, passed: 11}
  result: PASS
  exit_code: 0
archives:
  - {name: G07C_release_a.zip, file_count: 296, entries: 297, size_bytes: 2031927, sha256: 3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903}
  - {name: G07C_release_b.zip, file_count: 296, entries: 297, size_bytes: 2031927, sha256: 3641fa43ff756a926dc576cb73869ef91ac8fd5e8575ae2b84ba2d3871063903}
independent_scan: {top_level_forbidden: 0, case_collisions: 0, manifest_last: true, receipts_match: true}
audit_events:
  - {event: broad_nested_scope_scan, findings: 13, result: FALSE_POSITIVE}
  - {event: top_level_scope_scan, findings: 0, result: PASS}
  - {event: python_verifier_quoting, result: SYNTAX_ERROR, exit_code: 1}
  - {event: simplified_verifier_retry, verified_each: 296, result: PASS, exit_code: 0}
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G07C_RELEASE_ADVERSARIAL_REPRODUCIBILITY_REPORT_2026-08-26.md
  reports_index_line: 171
  sha256: b754d82a264f43aae08fd02c6d855b073c22286eca64fd495e53615bf0003d1a
external_effect: controlled_release_zip_and_receipt_artifacts_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G07C_RELEASE_ADVERSARIAL_REPRODUCIBILITY_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-134
output_summary: دو archive بایت‌یکسان و privacy-safe؛ D fresh-install rehearsal ایزوله را ادامه می‌دهد.
```

### STAB-G07-R01-S04 — wheel parity و fresh-install rehearsal

```yaml
event_id: STAB-G07-R01-S04
event: G07D_WHEEL_PARITY_AND_FRESH_INSTALL_REHEARSAL_GREEN
ended_at: 2026-08-26T19:27:21.0923760+03:30
goal_id: G-07-D
run_id: STAB-G07-R01
state_before: G07C_ADVERSARIAL_REPRODUCIBLE_GREEN_AUTO_CONTINUE_G07D
state_after: G07D_FRESH_INSTALL_REHEARSAL_GREEN_AUTO_CONTINUE_G07E
actor: codex
action_kind: TEST_FIRST_OFFLINE_WHEEL_BUILD_EXTRACT_AND_ISOLATED_INSTALL
cwd: <project-root>
red_events:
  - {event: wheel_audit_python_quoting, result: SYNTAX_ERROR, exit_code: 1, failure_class: invocation}
  - {event: wheel_parity_guard_missing, counts: {passed: 11, failed: 2}, result: RED, exit_code: 1}
  - {event: fixture_newline_mismatch, result: TEST_FIXTURE_FAILURE}
  - {event: canonical_stale_wheel, counts: {passed: 12, failed: 1}, missing: 57, mismatched: 20, result: RED, exit_code: 1}
  - {event: pip_wheel_no_isolation, reason: setuptools_build_meta_unavailable, result: ENVIRONMENT_FAIL, exit_code: 1}
  - {event: first_fresh_venv_pip_check, missing_dependencies: 3, result: PRODUCT_PACKAGING_RED, exit_code: 1}
implementation:
  - wheel_source_parity_guard
  - parameterized_deterministic_stdlib_wheel_builder
  - pyproject_driven_metadata_dependencies_and_four_entrypoints
  - non_destructive_build_wheel_launcher
  - exclude_quarantined_bale_client_from_release_and_wheel
  - remove_quarantined_only_dependencies_and_keep_fail_closed_slot
final_wheel: {source_files: 90, missing: 0, mismatched: 0, extra: 0, sha256: de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf, two_builds_byte_equal: true}
final_archive: {file_count: 282, sha256: 8b76948818111db7856278f8787ed8c1a277d1b2dd5d0680c0c24733fe3f3437, content_set_sha256: 3c777df594577009860338934bf0dec4f34fdb0ee309f10497adf46ae50a1c1b}
fresh_rehearsal:
  required_files: {expected: 15, missing: 0}
  quarantined_bale_client_files: 0
  self_dry_run: {file_count: 282, outputs_exist: false}
  compileall: PASS
  offline_install: PASS
  runtime_environment_check: PASS
  pip_check: PASS
  central_imports: PASS
tests:
  - {scope: builder_package_bale, counts: {collected: 20, passed: 20}, result: PASS}
  - {scope: related, basetemp: artifacts/stabilization/pytest-g07d-r07-related-green, counts: {collected: 102, passed: 102}, result: PASS}
documentation_controls: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS}
report:
  path: docs/reports/stabilization/G07D_FRESH_INSTALL_REHEARSAL_REPORT_2026-08-26.md
  reports_index_line: 172
  sha256: 2e72a0c25a420b0a8a6d56b6eff5f191416e38e770682c38f56e6753b1b1c52f
external_effect: controlled_build_archive_extract_and_fresh_venv_under_artifacts_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G07D_FRESH_INSTALL_REHEARSAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-135
output_summary: stale wheel/dependency RED بسته، fresh venv آفلاین سبز و E خودکار آغاز می‌شود.
```

### STAB-G07-R01-S05 — full regression و پذیرش فنی G-07

```yaml
event_id: STAB-G07-R01-S05
event: G07E_FULL_REGRESSION_AND_TECHNICAL_CLOSURE
ended_at: 2026-08-26T19:32:33.6622400+03:30
goal_id: G-07-E
run_id: STAB-G07-R01
state_before: G07D_FRESH_INSTALL_REHEARSAL_GREEN_AUTO_CONTINUE_G07E
state_after: G07E_TECHNICAL_GREEN_FINAL_ARCHIVES_AND_DOCS_PENDING
actor: codex
action_kind: FULL_TEST_UI_STATIC_AND_DOCUMENTATION_ALIGNMENT
cwd: <project-root>
full_backend:
  basetemp: artifacts/stabilization/pytest-g07e-r01-full-a
  counts: {collected: 643, passed: 643, failed: 0, errors: 0, skipped: 0}
  result: PASS
  exit_code: 0
collect_only: {collected: 643, result: PASS, exit_code: 0}
ui:
  typescript: {result: PASS, exit_code: 0}
  observability: {result: PASS, exit_code: 0}
  build: {result: NOT_REPEATED, reason: no_ui_change_since_g06c}
finding_state: F-042_TECHNICALLY_CLOSED_DOCUMENTATION_PENDING
technical_report:
  path: docs/reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md
release_state: NOT_RELEASE_READY
external_effect: tests_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-136
output_summary: 643/643 و UI static سبز؛ final archives و کنترل اسناد closure در حال تکمیل است.
```

### STAB-G07-R01-S06 — archive نهایی، closure اسناد و handoff G-07

```yaml
event_id: STAB-G07-R01-S06
event: G07_FINAL_ARCHIVES_DOCUMENTATION_CLOSURE_AND_AUTO_WAIT
ended_at: 2026-08-26T19:37:00.4108349+03:30
goal_id: G-07
run_id: STAB-G07-R01
state_before: G07E_TECHNICAL_GREEN_FINAL_ARCHIVES_AND_DOCS_PENDING
state_after: G07_COMPLETE_F042_CLOSED_AUTO_WAIT_G08
actor: codex
action_kind: FINAL_ARCHIVE_VERIFICATION_DOCUMENTATION_AND_CLOSURE
cwd: <project-root>
final_archives:
  - {name: G07E_release_final_a.zip, file_count: 282, entries: 283, sha256: 729a3d613f8e941c7b973af2e6433fb387b1f97fee2b4e07e72d196b79e2cb57}
  - {name: G07E_release_final_b.zip, file_count: 282, entries: 283, sha256: 729a3d613f8e941c7b973af2e6433fb387b1f97fee2b4e07e72d196b79e2cb57}
content_set_sha256: 1b7cc61fac50c3b581aaa6c577f6a64589ff921370d80bf0e75c12ee43e4170c
independent_controls: {forbidden: 0, collisions: 0, manifest_last: true, receipts_match: true, verifier_each: 282}
tool_event:
  event: combined_python_verifier_invocation_not_parsed
  result: INVOCATION_ERROR_NO_EXECUTION
  retry: two_short_verifier_commands_passed
documentation_controls:
  release_manifest_json: PASS
  reports_index_refresh: PASS
  memory_integrity: PASS
  generated_docs_stale_check: PASS
  generated_docs_link_check: PASS
  canonical_alignment: PASS
report:
  path: docs/reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md
  reports_index_line: 169
  sha256: bfcb2a3fe6e64ef0ce6c488bbeb50e4be4f491d56fecb64f2c1b2edc3ffd97a8
finding_state: F-042_CLOSED
goal_state: G-07_COMPLETE
next_goal: G-08_AFTER_FIVE_MINUTES_UNLESS_USER_STOPS
release_state: NOT_RELEASE_READY
external_effect: controlled_final_release_archives_receipts_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
output_summary: G-07/F-042 بسته، دو archive نهایی بایت‌یکسان و بازهٔ پنج‌دقیقه‌ای پیش از G-08 آغاز شد.
```

### STAB-G08-R01-S01 — ممیزی و RED canonical مشاهده‌پذیری

```yaml
event_id: STAB-G08-R01-S01
event: G08A_OBSERVABILITY_AUDIT_AND_RED
started_at: 2026-08-26T19:40:00+03:30
ended_at: 2026-08-26T19:48:04.3812392+03:30
goal_id: G-08-A
run_id: STAB-G08-R01
state_before: G07_COMPLETE_AUTO_WAIT_EXPIRED
state_after: G08A_RED_VERIFIED_AUTO_CONTINUE_G08B
actor: codex
action_kind: READ_TEST_WRITE_DOCUMENT
cwd: <project-root>
intent: تثبیت شکاف scanner چندحسابی، logger write-health و retention/disk-health با قراردادهای مصنوعی
command_safe: python -m pytest -q tests/test_g08_observability_completion.py --basetemp <artifact-temp>
files_intended:
  - scripts/phase10_log_redaction_verify.py
  - src/eitaa_bridge/infrastructure/diagnostics/runtime_logger.py
  - src/eitaa_bridge/infrastructure/diagnostics/manager.py
  - tests/test_g08_observability_completion.py
files_changed:
  - tests/test_g08_observability_completion.py
  - docs/reports/stabilization/G08A_OBSERVABILITY_GAP_RED_REPORT_2026-08-26.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/OBSERVABILITY_AND_LOGGING_AUDIT.md
  - docs/project-memory/STABILIZATION_REMEDIATION_PLAN_2026-08-25.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
pre_sha256:
  scanner: 99c34024b9b24477dc5fde05f88045dcdb87e6f9058773192a3c15e457b8958d
  runtime_logger: 2dc04203775c829ebafd34f4ebc960232b7e34f8507465aecef87d65cc554fc1
  manager: fba43190216467231baffeca8838fe24a057812e74c586d9ef3c8521532face9
post_sha256:
  red_test: 1644076e371754207add4ed52e64d3f63ed29ca3f21a34ef927526ec90a09071
exit_code: 1
result: EXPECTED_FAIL_RED_VERIFIED
test_counts: {collected: 4, passed: 0, failed: 4, errors: 0, skipped: 0}
failure_class: contract
reason_code: observability_operations_contracts_missing
external_effect: synthetic_test_temp_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G08A_OBSERVABILITY_GAP_RED_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-137
output_summary: چهار RED معتبر ثبت و F-048 ساخته شد؛ B خودکار آغاز می‌شود.
```

### STAB-G08-R01-S02 — اسکنر امن چندحسابی و regression مرتبط

```yaml
event_id: STAB-G08-R01-S02
event: G08B_MULTI_ACCOUNT_LOG_SCANNER_GREEN
started_at: 2026-08-26T19:48:05+03:30
ended_at: 2026-08-26T19:52:57.7516756+03:30
goal_id: G-08-B
run_id: STAB-G08-R01
state_before: G08A_RED_VERIFIED_AUTO_CONTINUE_G08B
state_after: G08B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G08C
actor: codex
action_kind: SOURCE_TEST_DOCUMENT
cwd: <project-root>
intent: کشف همهٔ account logها و rotationهای مجاز با report opaque و malformed fail-closed
files_changed:
  - scripts/phase10_log_redaction_verify.py
  - tests/test_g08_observability_completion.py
  - docs/reports/stabilization/G08B_MULTI_ACCOUNT_LOG_SCANNER_REPORT_2026-08-26.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/CURRENT_SYSTEM_BASELINE.md
  - docs/project-memory/OBSERVABILITY_AND_LOGGING_AUDIT.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
pre_sha256: {scanner: 99c34024b9b24477dc5fde05f88045dcdb87e6f9058773192a3c15e457b8958d}
post_sha256:
  scanner: a0c28c122d54896082318545d56c884f12c65292871323a0bfeb4df22eb893d5
  test: 3922875718d92d72a652a598c9bd68a3d8bef0c8bd9f33259cdb63064b16b043
tests:
  - {scope: scanner_targeted, counts: {collected: 2, passed: 2, failed: 0}, exit_code: 0}
  - {scope: related, counts: {collected: 18, passed: 18, failed: 0}, exit_code: 0}
result: PASS
external_effect: source_test_temp_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G08B_MULTI_ACCOUNT_LOG_SCANNER_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-138
output_summary: scanner چندحسابی opaque و fail-closed سبز شد؛ C خودکار آغاز می‌شود.
```

### STAB-G08-R01-S03 — Event Catalog و lifecycle کارهای پس‌زمینه

```yaml
event_id: STAB-G08-R01-S03
event: G08C_EVENT_CATALOG_BACKGROUND_LIFECYCLE_GREEN
started_at: 2026-08-26T19:53:00+03:30
ended_at: 2026-08-26T19:59:19.1382494+03:30
goal_id: G-08-C
run_id: STAB-G08-R01
state_before: G08B_TARGETED_RELATED_GREEN_AUTO_CONTINUE_G08C
state_after: G08C_EVENT_LIFECYCLE_GREEN_AUTO_CONTINUE_G08D
actor: codex
action_kind: AUDIT_SOURCE_TEST_DOCUMENT
cwd: <project-root>
intent: پوشش material background/manual/best-effort و application/auth lifecycle با event امن و correlation
red: {collected: 4, passed: 0, failed: 4, exit_code: 1}
green: {collected: 4, passed: 4, failed: 0, exit_code: 0}
related_attempt_a:
  result: EXPECTED_FUTURE_RED_INCLUDED
  failure_class: test_scope_selection
  failed: 2
  reason: two_known_g08d_health_retention_red_tests
related_retry_b: {collected: 98, passed: 98, failed: 0, exit_code: 0}
catalog_count: {before: 92, after: 102}
files_changed:
  - src/eitaa_bridge/application/api.py
  - src/eitaa_bridge/application/account_runtime.py
  - src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py
  - tests/test_g08_observability_completion.py
  - ARCHITECTURE_DECISIONS.md
  - docs/reports/stabilization/G08C_EVENT_LIFECYCLE_COVERAGE_REPORT_2026-08-26.md
  - docs/project-memory/CURRENT_SYSTEM_BASELINE.md
  - docs/project-memory/FINDINGS_REGISTER.md
  - docs/project-memory/VALIDATION_LEDGER.md
  - docs/project-memory/STABILIZATION_EXECUTION_LOG.md
  - docs/project-memory/OBSERVABILITY_AND_LOGGING_AUDIT.md
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
pre_sha256: {api: d5f3bde003b9c5827429727446f870feddc91ebe0d7d90e158a06e9b51486f79, account_runtime: 7b30786294b166fd4ae92d3ce7a41947c807572a76e92dc9cb63202b95588f0b, event_catalog: 3b60caeaa08f768613d269558f5f531b6ff9601e92e396476a7b81245407e47f}
post_sha256: {api: cdc21b9ab2c10056c3a27c8ae45147e2e579710bc339ef96e1f2ecacb4c1f8b4, account_runtime: 8dfee07d7c514ce0d120485e124b924415dd1c07650bd2010c7bf3f80d785286, event_catalog: f4e96b84d9040e32424cc88764d6ee34ae55ec15a5acb2937246946dbc8a99a3, test: d0a7738ff4f647e3a5d50c2d2a8b40d8369ff36c06f27f32c01fc14b980cc185}
result: PASS
external_effect: synthetic_test_temp_source_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G08C_EVENT_LIFECYCLE_COVERAGE_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-139
output_summary: background/lifecycle/catalog سبز و D خودکار آغاز می‌شود.
```

### STAB-G08-R01-S04 — سلامت logger، retention و Support Bundle

```yaml
event_id: STAB-G08-R01-S04
event: G08D_HEALTH_RETENTION_SUPPORT_BUNDLE_GREEN
started_at: 2026-08-26T19:59:20+03:30
ended_at: 2026-08-26T20:08:31.2326757+03:30
goal_id: G-08-D
run_id: STAB-G08-R01
state_before: G08C_EVENT_LIFECYCLE_GREEN_AUTO_CONTINUE_G08D
state_after: G08D_ADVERSARIAL_RELATED_GREEN_AUTO_CONTINUE_G08E
actor: codex
action_kind: SOURCE_ADVERSARIAL_TEST_DOCUMENT
cwd: <project-root>
red: {main: {collected: 4, failed: 4}, health_endpoint: {collected: 1, failed: 1, status: 404}}
green_attempt_a:
  counts: {collected: 5, passed: 4, failed: 1}
  failure_class: test_fixture_arithmetic
  reason: remaining_bytes_expected_54_actual_57
green_retry_b: {collected: 5, passed: 5, failed: 0, exit_code: 0}
expanded_attempt:
  counts: {collected: 13, passed: 12, failed: 1}
  failure_class: test_double_contract
  reason: broken_stream_missing_seek_tell
expanded_retry: {collected: 13, passed: 13, failed: 0, exit_code: 0}
related: {collected: 78, passed: 78, failed: 0, exit_code: 0}
catalog_count: 103
external_effect: synthetic_test_files_only_including_bounded_rotation_deletion
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G08D_OBSERVABILITY_HEALTH_RETENTION_SUPPORT_BUNDLE_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-140
output_summary: health/retention/disk/Support Bundle سبز و E خودکار آغاز می‌شود.
```

### STAB-G08-R01-S05 — full regression، wheel parity و پذیرش فنی

```yaml
event_id: STAB-G08-R01-S05
event: G08E_FULL_REGRESSION_WHEEL_PARITY_TECHNICAL_ACCEPTANCE
started_at: 2026-08-26T20:08:32+03:30
ended_at: 2026-08-26T20:16:02.3152766+03:30
goal_id: G-08-E
run_id: STAB-G08-R01
state_before: G08D_ADVERSARIAL_RELATED_GREEN_AUTO_CONTINUE_G08E
state_after: G08E_TECHNICAL_GREEN_DOCUMENTATION_CLOSURE_PENDING
actor: codex
action_kind: FULL_TEST_BUILD_VERIFY_UI_STATIC_DOCUMENT
cwd: <project-root>
full_attempt_a: {collected: 656, passed: 655, failed: 1, errors: 0, skipped: 0, exit_code: 1}
failure:
  class: packaging_artifact_drift
  node: test_bundled_bridge_wheel_matches_current_source_tree
  parity: {missing: 0, mismatched: 6, extra: 0}
wheel:
  preimage_sha256: de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf
  post_sha256: 9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70
  second_build_sha256: 9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70
  parity: {source_files: 90, missing: 0, mismatched: 0, extra: 0}
wheel_related: {collected: 28, passed: 28, failed: 0, exit_code: 0}
full_retry_b: {collected: 656, passed: 656, failed: 0, errors: 0, skipped: 0, exit_code: 0}
collect_only: {total: 656, exit_code: 0}
ui: {typescript: PASS, observability: PASS, build: NOT_REPEATED_NO_UI_CHANGE}
result: PASS
release_state: NOT_RELEASE_READY_G09_PENDING
external_effect: tests_and_controlled_local_wheel_builds_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - artifacts/stabilization/G08E_bridge_wheel_preimage_de9dd96f.whl
  - artifacts/stabilization/G08E-wheel-b/eitaa_bridge-0.7.0.dev31-py3-none-any.whl
  - docs/reports/stabilization/G08_OBSERVABILITY_COMPLETION_FINAL_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-141
output_summary: full 656/656، wheel 90/0 drift و UI static سبز؛ closure اسناد در حال تکمیل است.
```

### STAB-G08-R01-S06 — closure اسناد، F-048 و handoff G-08

```yaml
event_id: STAB-G08-R01-S06
event: G08_FINAL_DOCUMENTATION_CLOSURE_AND_AUTO_WAIT
ended_at: 2026-08-26T20:18:19.7413835+03:30
goal_id: G-08
run_id: STAB-G08-R01
state_before: G08E_TECHNICAL_GREEN_DOCUMENTATION_CLOSURE_PENDING
state_after: G08_COMPLETE_F048_CLOSED_AUTO_WAIT_G09
actor: codex
action_kind: DOCUMENTATION_INTEGRITY_AND_HANDOFF
cwd: <project-root>
documentation_controls:
  release_manifest_json: PASS
  reports_index_refresh: PASS
  memory_integrity: PASS
  generated_docs_stale_check: PASS
  generated_docs_link_check: PASS
  canonical_alignment: PASS
report:
  path: docs/reports/stabilization/G08_OBSERVABILITY_COMPLETION_FINAL_REPORT_2026-08-26.md
  reports_index_line: 174
  sha256: d0c819e6aeb97c5e323b583dd1c00c64fdb59b09de11c157169475e3d1fb32b0
release_manifest_sha256: 3b1010b892f80eca0fc8a95c8c396359ceeba30bcd1ba57a18521f0e74cc622c
wheel_sha256: 9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70
finding_state: F-048_CLOSED
goal_state: G-08_COMPLETE
next_goal: G-09_AFTER_FIVE_MINUTES_UNLESS_USER_STOPS
release_state: NOT_RELEASE_READY_G09_PENDING
external_effect: documentation_and_controlled_local_artifacts_only
approval_ref: user-start-g05-auto-phases-command
output_summary: G-08/F-048 بسته؛ پنج دقیقه فرصت توقف پیش از G-09 آغاز می‌شود.
```

### STAB-G09-R01-S01 — baseline پذیرش و package dry-run

```yaml
event_id: STAB-G09-R01-S01
event: G09A_FINAL_ACCEPTANCE_BASELINE_DRY_RUN
started_at: 2026-08-26T20:23:20+03:30
ended_at: 2026-08-26T20:25:57.6506440+03:30
goal_id: G-09-A
run_id: STAB-G09-R01
state_before: G08_COMPLETE_F048_CLOSED_AUTO_WAIT_EXPIRED
state_after: G09A_BASELINED_DRY_RUN_GREEN_AUTO_CONTINUE_G09B
actor: codex
action_kind: READ_AUDIT_TEST_DOCUMENT
cwd: <project-root>
dry_run: {file_count: 282, content_set_sha256: cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a, output_writes: 0, exit_code: 0}
red: {result: NOT_APPLICABLE, reason: read_only_acceptance_baseline}
external_effect: read_only_and_documentation
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G09A_FINAL_ACCEPTANCE_BASELINE_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-142
output_summary: acceptance baseline و dry-run سبز؛ B خودکار آغاز می‌شود.
```

### STAB-G09-R01-S02 — archive نهایی، verifier و reproducibility

```yaml
event_id: STAB-G09-R01-S02
event: G09B_FINAL_ARCHIVE_REPRODUCIBILITY_AND_PRIVACY
started_at: 2026-08-26T20:26:00+03:30
ended_at: 2026-08-26T20:29:55.8708591+03:30
goal_id: G-09-B
run_id: STAB-G09-R01
state_before: G09A_BASELINED_DRY_RUN_GREEN_AUTO_CONTINUE_G09B
state_after: G09B_FINAL_ARCHIVE_GREEN_AUTO_CONTINUE_G09C
actor: codex
action_kind: CONTROLLED_ARTIFACT_WRITE_VERIFY_TEST_DOCUMENT
cwd: <project-root>
archives: {count: 2, file_count_each: 282, zip_entries_each: 283, sha256_each: a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360, content_set_sha256_each: cf055cd4856ca9e05250700ff2d745f769ebbd1d7fb47d5fbd623af4fe20fc3a}
independent_checks: {manifest_last: true, duplicate: 0, case_collision: 0, forbidden_entry: 0, privacy_findings: 0}
test_attempt_a: {result: ENVIRONMENT_BLOCKED, passed: 3, setup_errors: 12, cause: default_pytest_temp_permission_denied}
test_retry: {result: PASS, passed: 15, failed: 0, errors: 0, basetemp: artifacts/stabilization/G09B_pytest_20260826}
red: {result: NOT_APPLICABLE, reason: artifact_acceptance_reuses_V132_and_V141_adversarial_RED}
source_or_test_change: 0
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 180, sha256: e8ca7f336402f62be07015c65071754e7e6651fc3b33207dbe0528022681fd9d}
external_effect: controlled_archives_receipts_test_temp_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - artifacts/stabilization/G09B_final_a.zip
  - artifacts/stabilization/G09B_final_a.receipt.json
  - artifacts/stabilization/G09B_final_b.zip
  - artifacts/stabilization/G09B_final_b.receipt.json
  - docs/reports/stabilization/G09B_FINAL_ARCHIVE_VERIFICATION_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-143
output_summary: دو archive نهایی بایت‌یکسان و privacy/verifier/package regression سبز؛ C خودکار آغاز می‌شود.
```

### STAB-G09-R01-S03 — extract و fresh-install کاملاً آفلاین

```yaml
event_id: STAB-G09-R01-S03
event: G09C_OFFLINE_FRESH_INSTALL_ACCEPTANCE
started_at: 2026-08-26T20:30:00+03:30
ended_at: 2026-08-26T20:35:22.1808057+03:30
goal_id: G-09-C
run_id: STAB-G09-R01
state_before: G09B_FINAL_ARCHIVE_GREEN_AUTO_CONTINUE_G09C
state_after: G09C_OFFLINE_FRESH_INSTALL_GREEN_AUTO_CONTINUE_G09D
actor: codex
action_kind: CONTROLLED_EXTRACT_COMPILE_OFFLINE_INSTALL_TEST_DOCUMENT
cwd: <project-root>
input_archive: {sha256: a637250e1ec45e583804415075a3e9155b5e133a7836552af966be9168c8f360, extracted_files: 283}
extract_checks: {required: 15, missing: 0, quarantined_bale_client_files: 0, self_dry_run_files: 282, self_dry_run_writes: 0, compileall: PASS}
checklist_attempt_a: {result: INVOCATION_ERROR, stale_event_catalog_path_missing: 1, product_failure: false}
wheel_parity: {source_files: 90, missing: 0, mismatched: 0, extra: 0, sha256: 9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70}
fresh_install: {network: 0, pip_no_index: true, runtime_check: PASS, pip_check: PASS, isolated_import: PASS, event_catalog_count: 103, entrypoints: 4}
red: {result: NOT_APPLICABLE, reason: acceptance_rehearsal_reuses_V132_V135_V141_RED}
source_or_test_change: 0
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 181, sha256: be707f7b85f82c85f090f02c35cf5104dffb1adcd4c64d85942b79795b318309}
external_effect: controlled_extract_compile_cache_fresh_venv_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - artifacts/stabilization/G09C_extracted
  - artifacts/stabilization/G09C_fresh_venv
  - docs/reports/stabilization/G09C_OFFLINE_FRESH_INSTALL_ACCEPTANCE_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-144
output_summary: extract/parity و fresh install کاملاً آفلاین سبز؛ D خودکار آغاز می‌شود.
```

### STAB-G09-R01-S04 — full Backend، تمام UI contracts و build

```yaml
event_id: STAB-G09-R01-S04
event: G09D_FULL_UI_BUILD_AND_BACKEND_ACCEPTANCE
started_at: 2026-08-26T20:36:00+03:30
ended_at: 2026-08-26T20:41:52.1937700+03:30
goal_id: G-09-D
run_id: STAB-G09-R01
state_before: G09C_OFFLINE_FRESH_INSTALL_GREEN_AUTO_CONTINUE_G09D
state_after: G09D_FULL_AUTOMATED_ACCEPTANCE_GREEN_AUTO_CONTINUE_G09E
actor: codex
action_kind: FULL_TEST_UI_CONTRACT_BUILD_READ_AUDIT_DOCUMENT
cwd: <project-root>
backend: {collected: 656, passed: 656, failed: 0, errors: 0, skipped: 0, attempt: 1, basetemp: artifacts/stabilization/G09D_full_20260826}
ui: {runners: 9, runner_failures: 0, typescript: PASS, build: PASS, modules: 1015}
bundle: {bytes: 794741, sha256: 6659940b0dd49cf0a0cff3f5e23b200e7f5cdc8529ecf7a89373f3f379f17461, large_chunk_warning: NON_BLOCKING}
privacy_log_acceptance: {g08_contracts_in_full_suite: 13, archive_privacy_findings: 0, live_logs_scanned: false}
safe_status_audit: {result: PASS, worktree: INTENTIONALLY_DIRTY_UNCHANGED, root_operational_rows: 0, git_mutation: 0}
red: {result: NOT_APPLICABLE, reason: final_aggregate_acceptance_without_source_or_test_change}
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 182, sha256: 951a3c2975db874b77af41212d687bae648d083f9a1ce6cb97fb5e151a0d0f80}
external_effect: backend_test_temp_ui_dist_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - ui/dist
  - artifacts/stabilization/G09D_full_20260826
  - docs/reports/stabilization/G09D_FULL_UI_BUILD_AND_BACKEND_ACCEPTANCE_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-145
output_summary: full Backend و تمام UI contracts/TypeScript/build سبز؛ E closure اسناد را ادامه می‌دهد.
```

### STAB-G09-R01-S05 — closure فنی، طبقه‌بندی انتشار و handoff

```yaml
event_id: STAB-G09-R01-S05
event: G09E_FINAL_CANONICAL_ALIGNMENT_AND_HANDOFF
started_at: 2026-08-26T20:42:00+03:30
ended_at: 2026-08-26T20:47:56.0640297+03:30
goal_id: G-09-E
run_id: STAB-G09-R01
state_before: G09D_FULL_AUTOMATED_ACCEPTANCE_GREEN_AUTO_CONTINUE_G09E
state_after: G09_AUTOMATED_SCOPE_COMPLETE_OFFLINE_RELEASE_CANDIDATE_USER_ACCEPTANCE_PENDING
actor: codex
action_kind: CANONICAL_DOCUMENT_ALIGNMENT_RELEASE_CLASSIFICATION_HANDOFF
cwd: <project-root>
technical_acceptance: {package_dry_run: PASS, reproducible_archive: PASS, privacy: PASS, offline_fresh_install: PASS, backend: 656/656, backend_skips: 0, ui_contracts: PASS, typescript: PASS, build: PASS}
finding_alignment: {F005: CLOSED_CURRENT_PROGRAM_SCOPE, F006: CLOSED, F045: TECHNICAL_COMPLETE_USER_ACCEPTANCE_PENDING, F039: COMMIT_PENDING, F013: OPEN_NON_BLOCKING, OBS008: DEFERRED}
release_classification: {offline_release_candidate: true, production_release_authorized: false, explicit_user_acceptance: PENDING, external_release_gates: PENDING}
release_manifest: {json_parse: PASS, sha256: b4d27d10b68b579be641bd92ee44c4c1489b2ce95ed813b51a495bbc1e44d122}
red: {result: NOT_APPLICABLE, reason: documentation_only_final_alignment_after_A_to_D_acceptance}
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 179, sha256: 314819c90a045a404a7750c449c0229f80a6355f302b95f8e6d682be18c60c46}
handoff_sha256: 5e7224f3a7fe569b799f55ac4d3c7d0103131933f1762474181d10330ad2486b
external_effect: documentation_only
approval_ref: user-start-g05-auto-phases-command
artifacts:
  - docs/reports/stabilization/G09_FINAL_ACCEPTANCE_AND_HANDOFF_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-146
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
output_summary: دامنهٔ فنی G-00 تا G-09 کامل؛ offline release candidate، پذیرش کاربر و دروازه‌های Production pending.
```

### STAB-G09-R01-S06 — reconciliation آرشیو منتخب پس از closure اسناد

```yaml
event_id: STAB-G09-R01-S06
event: G09E_FINAL_SELECTED_DOCUMENT_ARCHIVE_RECONCILIATION
started_at: 2026-08-26T20:48:00+03:30
ended_at: 2026-08-26T20:52:17.9008124+03:30
goal_id: G-09-E
run_id: STAB-G09-R01
state_before: G09_AUTOMATED_SCOPE_COMPLETE_OFFLINE_RELEASE_CANDIDATE_USER_ACCEPTANCE_PENDING
state_after: G09_FINAL_ARCHIVE_RECONCILED_AUTOMATED_SCOPE_COMPLETE_USER_ACCEPTANCE_PENDING
actor: codex
action_kind: DRIFT_DETECT_REBUILD_VERIFY_EXTRACT_OFFLINE_INSTALL_DOCUMENT
cwd: <project-root>
trigger: selected_release_document_changed_after_G09B_archive
manifest_diff: {changed: [ARCHITECTURE_DECISIONS.md], added: 0, removed: 0}
final_archives: {count: 2, file_count_each: 282, entries_each: 283, sha256_each: 6ff12e2b82bcaf35833a16d158502fad507a4f16a177113d5b6c65ea87528071, content_set_sha256_each: d60b10eac4abdd1fd28d1cd6e1ff9f955576b2e393e926e8945a913667a41a49, privacy_findings: 0, forbidden: 0}
exact_artifact_rehearsal: {extract: PASS, self_dry_run: PASS, wheel_parity: 90/0, pip_no_index: true, runtime_check: PASS, pip_check: PASS, imports: PASS, event_catalog_count: 103}
final_dry_run: {file_count: 282, content_set_sha256: d60b10eac4abdd1fd28d1cd6e1ff9f955576b2e393e926e8945a913667a41a49, writes: 0}
release_manifest: {json_parse: PASS, sha256: 05282e5da4331f478c7bb97d6333434f2a2410137e158e56e2191c4357ef12e9}
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 179, sha256: f785e84cabaaa218c6ca539b89703f995f1af1557018f6292bcb33d5a23e49ad}
handoff_sha256: 6f5cf5198d94184751c66e1b874b422c7713914e8a5c5fdd8efeb585ad1dc1a6
historical_artifacts: artifacts/stabilization/G09B_final_a_and_b
canonical_artifacts:
  - artifacts/stabilization/G09E_release_final_a.zip
  - artifacts/stabilization/G09E_release_final_a.receipt.json
  - artifacts/stabilization/G09E_release_final_b.zip
  - artifacts/stabilization/G09E_release_final_b.receipt.json
  - artifacts/stabilization/G09E_extracted_final
  - artifacts/stabilization/G09E_fresh_venv_final
external_effect: controlled_archives_extract_fresh_venv_and_documentation_only
approval_ref: user-start-g05-auto-phases-command
output_summary: drift یک سند منتخب کشف؛ archiveهای canonical بازسازی و exact-artifact fresh-install سبز شد.
```

### STAB-G09-R01-S07 — پذیرش کاربر و closure رسمی

```yaml
event_id: STAB-G09-R01-S07
event: G09_USER_ACCEPTANCE_AND_FORMAL_CLOSURE
started_at: 2026-08-26T21:54:16.9907168+03:30
ended_at: 2026-08-26T21:54:16.9907168+03:30
goal_id: G-09
run_id: STAB-G09-R01
state_before: G09_FINAL_ARCHIVE_RECONCILED_AUTOMATED_SCOPE_COMPLETE_USER_ACCEPTANCE_PENDING
state_after: G09_COMPLETE_USER_ACCEPTED_OFFLINE_RELEASE_CANDIDATE
actor: user_and_codex
action_kind: USER_ACCEPTANCE_DOCUMENTATION_ONLY_CLOSURE
cwd: <project-root>
user_command: G09 را می‌پذیرم و closure نهایی را ثبت کن
finding_transition: {F045: CLOSED_USER_ACCEPTED}
release_classification: {offline_release_candidate: true, production_release_authorized: false, external_release_gates: PENDING}
product_source_change: 0
archive_change: 0
operational_data_change: 0
git_mutation: 0
release_manifest: {json_parse: PASS, sha256: 596d75e4658ed063af4bd37e1ae2b953eeb6f71a72a68ede7fd8f4a93a7b5191}
post_acceptance_dry_run: {file_count: 282, content_set_sha256: d60b10eac4abdd1fd28d1cd6e1ff9f955576b2e393e926e8945a913667a41a49, writes: 0, canonical_archive_still_current: true}
documentation_controls: {reports_index_refresh: PASS, memory_integrity: PASS, generated_docs_stale_check: PASS, generated_docs_link_check: PASS}
report: {reports_index_line: 179, sha256: 23d939e842ef96df75b6e7a8b7752cc073c9bcfa4a942c38b1d60c22964a6316}
handoff_sha256: 8c277648ffe0f508780f07b460b7691de262e5af1668c45ce3e7da37e5eee441
external_effect: documentation_only
approval_ref: user-explicit-g09-acceptance-2026-08-26
artifacts:
  - docs/reports/stabilization/G09_FINAL_ACCEPTANCE_AND_HANDOFF_REPORT_2026-08-26.md
  - docs/project-memory/VALIDATION_LEDGER.md#V-148
  - docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md
output_summary: پذیرش صریح کاربر ثبت و G-09/F-045 رسماً بسته شد؛ دروازه‌های Production مستقل باقی‌اند.
```

### STAB-GIT-R01-S01 — ممیزی commit PyCharm و backup بازیابی‌پذیر

```yaml
event_id: STAB-GIT-R01-S01
event: GIT_PUBLISH_PRE_CLEAN_AUDIT_AND_BACKUP_REF
started_at: 2026-08-26T22:00:00+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: G09_COMPLETE_USER_ACCEPTED_LOCAL_COMMIT_UNAUDITED
state_after: BAD_COMMIT_BACKED_UP_CLEANUP_AUTHORIZED_PUSH_PENDING
actor: user_and_codex
action_kind: READ_AUDIT_AND_RECOVERABLE_GIT_REF
cwd: <project-root>
initial_commit: f4464ef8bc971462ffdc61c82d0b158a1d3f3660
initial_commit_files: 7213
temp_or_cache_files: 6068
archive_or_binary_files: 100
root_operational_files: 0
github_live_check: {repository: EitaaDesktop, main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, new_commit_present: false, stabilization_branch_present: false}
backup_ref: {name: codex/backup-pycharm-f4464ef, hash: f4464ef8bc971462ffdc61c82d0b158a1d3f3660, result: PASS}
cleanup_policy: cached_only_no_local_deletion
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: commit آلوده روی backup ref حفظ و پاک‌سازی cached-only برای انتشار شاخهٔ جدا مجاز شد.
```

### STAB-GIT-R01-S02 — پاک‌سازی cached-only و audit candidate

```yaml
event_id: STAB-GIT-R01-S02
event: GIT_INDEX_CACHED_ONLY_SANITIZATION
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: BAD_COMMIT_BACKED_UP_CLEANUP_AUTHORIZED_PUSH_PENDING
state_after: INDEX_CLEAN_COMMIT_PENDING
actor: codex
action_kind: GIT_INDEX_ONLY_REMOVE_AND_AUDIT
cwd: <project-root>
passes:
  - {scope: pytest_tmp_codex_bale_prompt_fix_backup, local_delete: 0, result: PASS}
  - {scope: phase10_legacy_pytest_171_files, local_delete: 0, result: PASS}
candidate: {files: 642, temp_cache: 0, operational_root: 0, databases: 0, bale_top_level: 0, scratch_fix_backup: 0, engineering_logs: 177}
secret_scan: {high_confidence_paths: 1, classification: synthetic_adversarial_fixture}
local_preservation: {pytest_work: true, tmp: true, bale_research: true, prompt_out: true}
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: candidate 642فایلی بدون temp/operational آمادهٔ commit؛ لاگ‌ها و فایل‌های محلی حفظ شدند.
```

### STAB-GIT-R01-S03 — reconciliation release پس از `.gitignore`

```yaml
event_id: STAB-GIT-R01-S03
event: GIT_POLICY_SELECTED_RELEASE_DOCUMENT_RECONCILIATION
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: INDEX_CLEAN_COMMIT_PENDING
state_after: INDEX_AND_RELEASE_ARTIFACT_GREEN_COMMIT_PENDING
actor: codex
action_kind: DRY_RUN_REBUILD_VERIFY_MANIFEST_DIFF
cwd: <project-root>
trigger: gitignore_is_release_allowlisted
final_archives: {count: 2, file_count_each: 282, sha256_each: 187ea793cc43db2cb4f427201ee845e6d997581aaf5d5094a9d5d227626ebf6b, content_set_sha256_each: 6b9a37c1279923627b78b09935f6298c751302721322827d80a651406f0221ea, privacy_findings: 0}
manifest_diff: {changed: [.gitignore], added: 0, removed: 0}
source_ui_wheel_drift: 0
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: policy Git با archive canonical تازه همسو؛ فقط gitignore تغییر و commit هنوز pending است.
```

### STAB-GIT-R01-S04 — ممیزی base واقعی و archive canonical نهایی

```yaml
event_id: STAB-GIT-R01-S04
event: BASE_AWARE_INDEX_AUDIT_AND_FINAL_ARCHIVE_RECONCILIATION
started_at: 2026-08-26T22:20:00+03:30
ended_at: 2026-08-26T22:35:54.8792835+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: INDEX_CLEAN_INTERMEDIATE_ARCHIVE_CURRENT_COMMIT_PENDING
state_after: INDEX_CLEAN_FINAL_ARCHIVE_CURRENT_COMMIT_PENDING
actor: codex
action_kind: CACHE_ONLY_INDEX_SANITIZATION_AND_CONTROLLED_ARCHIVE_BUILD
cwd: <project-root>
history_audit: {github_base: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, local_commits_after_base: 4, backup_ref_preserved: codex/backup-pycharm-f4464ef}
index_cleanup: {local_delete: 0, cached_only: true, one_shot_scripts_excluded: true, canonical_scripts_retained: 21}
candidate_vs_github_base: {files: 426, root: 13, docs: 206, lab: 2, scripts: 21, src: 77, tests: 57, ui: 50, temp_cache: 0, operational_root: 0, db: 0, bale_top_level: 0, scratch: 0}
dry_run: {file_count: 282, content_set_sha256: 43c67c2eba3c30c534c855119287793eeb2ae7fc8fc61ab7aed19ecfc6dc217a, writes: 0}
final_archives: {count: 2, file_count_each: 282, sha256_each: 481ed1be889892dc2802fa2052c27ef9ef3078994e3cc377b1e1a1c59f3b3384, content_set_sha256_each: 43c67c2eba3c30c534c855119287793eeb2ae7fc8fc61ab7aed19ecfc6dc217a, privacy_findings: 0}
manifest_diff_vs_intermediate: {changed: [.gitignore], added: 0, removed: 0}
product_source_change_in_step: 0
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: نامزد نسبت به base واقعی ممیزی، فایل‌های یک‌بارمصرف فقط از index خارج و archive final2 بایت‌یکسان شد؛ فایل و لاگ محلی حذف نشد.
```

### STAB-GIT-R01-S05 — کنترل کامل پیش از commit و retry محیطی

```yaml
event_id: STAB-GIT-R01-S05
event: PRECOMMIT_FULL_VALIDATION_AND_ENVIRONMENTAL_RETRY
started_at: 2026-08-26T22:36:00+03:30
ended_at: 2026-08-26T22:40:00.9174580+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: INDEX_CLEAN_FINAL_ARCHIVE_CURRENT_COMMIT_PENDING
state_after: PRECOMMIT_VALIDATION_GREEN_COMMIT_PENDING
actor: codex
action_kind: READ_AND_CONTROLLED_TEST_WRITES
cwd: <project-root>
backend_collect: {files: 74, collected: 656, result: PASS, exit_code: 0}
backend_full: {basetemp: artifacts/stabilization/GITPUBLISH_full_20260826, collected: 656, passed: 656, failed: 0, errors: 0, result: PASS, exit_code: 0}
ui: {typescript: PASS, observability: PASS}
attempts:
  - {attempt_id: STAB-GIT-R01-S05-A01, scope: package_targeted_without_controlled_basetemp, result: ENVIRONMENT_ERROR, passed_before_error_summary: 3, setup_errors: 12, reason: windows_global_pytest_temp_permission, product_failure: false, exit_code: 1}
  - {attempt_id: STAB-GIT-R01-S05-A02, retry_of: STAB-GIT-R01-S05-A01, scope: package_targeted_controlled_basetemp, basetemp: artifacts/stabilization/GITPUBLISH_package_retry_20260826, collected: 15, passed: 15, result: PASS, exit_code: 0}
release_controls: {dry_run_files: 282, content_set_sha256: 43c67c2eba3c30c534c855119287793eeb2ae7fc8fc61ab7aed19ecfc6dc217a, release_manifest_json: PASS, release_manifest_sha256: e3a5b606f8f95910f80de93299d38884a8c7371aa1632e6e4517434096744a27}
documentation_controls: {refresh: PASS, memory_integrity: PASS, stale_check: PASS, link_check: PASS}
live_provider_or_operational_action: 0
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: full Backend و UI سبز؛ خطای صرفاً محیطی temp در retry کنترل‌شده 15/15 بسته و با شناسهٔ مستقل ثبت شد.
```

### STAB-GIT-R01-S06 — reset نرم، commit تمیز و شاخهٔ انتشار

```yaml
event_id: STAB-GIT-R01-S06
event: RECOVERABLE_HISTORY_SQUASH_AND_CLEAN_COMMIT
started_at: 2026-08-26T22:40:30+03:30
ended_at: 2026-08-26T22:43:45.4064736+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: PRECOMMIT_VALIDATION_GREEN_COMMIT_PENDING
state_after: CLEAN_COMMIT_CREATED_RELEASE_BRANCH_ACTIVE_PUSH_PENDING
actor: codex
action_kind: USER_AUTHORIZED_GIT_MUTATION
cwd: <project-root>
backup_ref: {name: codex/backup-pycharm-f4464ef, commit: f4464ef8bc971462ffdc61c82d0b158a1d3f3660, preserved: true}
github_base: a4df3ecf2bcd4ab658c5361afdc287444694fcd2
tree_continuity: {before_soft_reset: 5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d, after_soft_reset: 5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d, equal: true}
reset: {mode: soft, local_delete: 0, hard_reset: false}
clean_commit: {hash: fca3ea72c54c0b7226f4dbabc54b4684e1215513, parent: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, tree: 5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d, files: 426, subject: "chore(stabilization): complete G00-G09 offline acceptance"}
release_branch: codex/stabilization-g09
tool_events:
  - {attempt_id: STAB-GIT-R01-S06-A01, scope: tree_lookup_with_braces_in_powershell, result: POWERSHELL_PARSE_ERROR, state_change: 0, product_failure: false}
  - {attempt_id: STAB-GIT-R01-S06-A02, retry_of: STAB-GIT-R01-S06-A01, scope: tree_lookup_via_git_show_format, result: PASS, tree: 5a7f4067fe4c0b5b0348a8c1d1fa9de79b400b7d}
main_branch_mutation: 0
push: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: چهار commit در یک commit تمیز با tree یکسان تجمیع؛ backup کامل و شاخهٔ انتشار مستقل حفظ شد.
```

### STAB-GIT-R01-S07 — push اولیه و verify شاخهٔ GitHub

```yaml
event_id: STAB-GIT-R01-S07
event: GITHUB_RELEASE_BRANCH_INITIAL_PUSH_AND_VERIFY
started_at: 2026-08-26T22:44:00+03:30
ended_at: 2026-08-26T22:46:27.9671454+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: CLEAN_COMMIT_CREATED_RELEASE_BRANCH_ACTIVE_PUSH_PENDING
state_after: REMOTE_BRANCH_PUSH_VERIFIED_FINAL_LOG_COMMIT_PENDING
actor: codex
action_kind: USER_AUTHORIZED_GITHUB_BRANCH_PUSH
cwd: <project-root>
remotes: {origin: https://github.com/gprsm/EitaaDesktop.git, legacy_preserved: true}
prepush_remote: {main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, release_branch: absent}
push: {branch: codex/stabilization-g09, force: false, upstream_set: true, result: PASS, exit_code: 0}
postpush_remote: {release_branch: 66f7beaca6a2cd0a67c54ec5705dcf5c381a8e9f, main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, main_unchanged: true}
pull_request_url: https://github.com/gprsm/EitaaDesktop/pull/new/codex/stabilization-g09
final_documentation_commit_required: true
live_provider_or_operational_action: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: شاخهٔ مستقل بدون force منتشر و hash آن زنده تأیید شد؛ main بدون تغییر باقی ماند.
```

### STAB-GIT-R01-S08 — verify دوم و closure مستند انتشار

```yaml
event_id: STAB-GIT-R01-S08
event: FINAL_DOCUMENTATION_PUSH_VERIFY_AND_GIT_PUBLICATION_CLOSURE
started_at: 2026-08-26T22:46:30+03:30
ended_at: 2026-08-26T22:48:46.4453207+03:30
goal_id: GIT-PUBLISH
run_id: STAB-GIT-R01
state_before: REMOTE_BRANCH_PUSH_VERIFIED_FINAL_LOG_COMMIT_PENDING
state_after: COMPLETE_PUSH_VERIFIED_MAIN_UNCHANGED
actor: codex
action_kind: USER_AUTHORIZED_GITHUB_BRANCH_PUSH_AND_READ_VERIFY
cwd: <project-root>
documentation_commit: {hash: 1f0f546b7532c5d856f82552f1abd69f8e337a10, subject: "docs(git): record GitHub push verification"}
push: {branch: codex/stabilization-g09, force: false, result: PASS, exit_code: 0}
live_verify: {release_branch: 1f0f546b7532c5d856f82552f1abd69f8e337a10, main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, equal_local_remote: true, main_unchanged: true}
tracking: {remote: origin, merge: refs/heads/codex/stabilization-g09, status_clean_and_synchronized: true}
tool_events:
  - {attempt_id: STAB-GIT-R01-S08-A01, scope: upstream_lookup_with_at_brace_shorthand, result: POWERSHELL_PARSE_ERROR, state_change: 0, product_failure: false}
  - {attempt_id: STAB-GIT-R01-S08-A02, retry_of: STAB-GIT-R01-S08-A01, scope: upstream_lookup_via_config_and_status, result: PASS}
backup_ref_preserved: {name: codex/backup-pycharm-f4464ef, commit: f4464ef8bc971462ffdc61c82d0b158a1d3f3660}
final_closure_commit_requires_normal_push: true
live_provider_or_operational_action: 0
approval_ref: user-approved-cleanup-and-github-push-with-log-preservation
output_summary: push دوم و tracking تأیید، main ثابت و Run کامل شد؛ hash commit closure پس از push نهایی در تحویل گفتگو ثبت می‌شود.
```

### STAB-GIT-R02-S01 — ثبت دستور دائمی انتشار محصول نهایی

```yaml
event_id: STAB-GIT-R02-S01
event: USER_STANDING_FINAL_PRODUCT_GITHUB_PUBLICATION_AUTHORIZATION
started_at: 2026-08-26T22:54:30+03:30
ended_at: 2026-08-26T22:55:52.4427828+03:30
goal_id: GIT-PUBLICATION-GOVERNANCE
run_id: STAB-GIT-R02
state_before: PER_TASK_EXPLICIT_GIT_AUTHORIZATION
state_after: STANDING_FINAL_SCENARIO_PUBLICATION_AUTHORIZATION_ACTIVE
actor: user_and_codex
action_kind: DOCUMENTATION_ONLY_POLICY_UPDATE
cwd: <project-root>
authorization: {stage: final_tested_scenario_only, commit: precise_message_required, push: dedicated_working_branch_required, repeat_confirmation_required: false}
excluded_without_separate_explicit_command: [direct_main_push_or_merge, force_push, remote_history_rewrite, ref_deletion, incomplete_or_red_snapshot, credential_or_operational_data]
prepush_requirements: [scope_audit, relevant_tests_green, documentation_controls_green, privacy_and_operational_scan, remote_precheck]
postpush_requirements: [local_remote_hash_equal, main_unchanged, handoff_with_branch_and_commit]
files_recorded: [AGENTS.md, docs/project-memory/CODEX_ANTIGRAVITY_COLLABORATION_PROTOCOL.md, docs/handoffs/ANTIGRAVITY_STABILIZATION_CURRENT.md, docs/project-memory/VALIDATION_LEDGER.md, docs/project-memory/STABILIZATION_EXECUTION_LOG.md]
approval_ref: user-standing-final-product-github-push-command
output_summary: مجوز دائمی انتشار هر سناریوی نهایی با guardهای تست، privacy، شاخهٔ اختصاصی و حفاظت main ثبت شد.
```

### STAB-G10-R01-S01 — ممیزی ماسک‌شده، تشخیص علت و RED

```yaml
event_id: STAB-G10-R01-S01
event: SELECTED_GROUP_STALE_TIMELINE_MASKED_DIAGNOSIS_AND_RED
started_at: 2026-08-26T22:56:00+03:30
ended_at: 2026-08-26T23:05:00+03:30
goal_id: G-10
run_id: STAB-G10-R01
state_before: USER_REPORTED_SELECTED_GROUP_ONE_MONTH_STALE
state_after: ROOT_CAUSE_CONFIRMED_RED_VERIFIED
actor: codex
action_kind: READ_AND_TEST
cwd: <project-root>
authorization: {messenger_view: true, saved_messages_send_if_needed: true, third_party_send: false}
computer_use:
  attempts: 3
  reset_attempts: 1
  result: BLOCKED_BEFORE_WINDOW_SELECTION
  failure_class: environment
  error_summary: kernel_assets_path_not_found
  input_or_click_count: 0
masked_live_read: {catalog_active_favorite_count: 1, local_message_count: 674, catalog_top_equals_local_max: true, latest_local_day: current_day, operational_write: 0}
masked_log_scan: {files_scanned: 91, relevant_records: 5613, sync_success_types_present: true, failure_records: 0}
tool_events:
  - {attempt_id: STAB-G10-R01-S01-A01, scope: masked_db_probe_orchestration, result: FAIL, failure_class: environment, error_summary: TextEncoder_unavailable, state_change: 0}
  - {attempt_id: STAB-G10-R01-S01-A02, retry_of: STAB-G10-R01-S01-A01, result: FAIL, failure_class: environment, error_summary: btoa_unavailable, state_change: 0}
  - {attempt_id: STAB-G10-R01-S01-A03, retry_of: STAB-G10-R01-S01-A02, result: PASS, access: read_only}
  - {attempt_id: STAB-G10-R01-S01-A04, scope: masked_log_scan, result: PARTIAL, error_summary: two_null_array_index_warnings, state_change: 0}
  - {attempt_id: STAB-G10-R01-S01-A05, retry_of: STAB-G10-R01-S01-A04, result: PASS, null_guard: true}
root_cause: runtime_patch_rewrote_messages_list_before_id_and_limit_from_persisted_checkpoint
red_test: {result: EXPECTED_FAIL, passed: 5, failed: 1, product_regression_confirmed: true}
privacy: {raw_title: not_recorded, raw_peer_or_account_id: not_recorded, message_text: not_recorded}
message_send_count: 0
output_summary: دادهٔ محلی و sync جاری بود؛ redirect درخواست history به checkpoint قدیمی علت قطعی و با RED تثبیت شد.
```

### STAB-G10-R01-S02 — اصلاح request، regression و reconciliation انتشار

```yaml
event_id: STAB-G10-R01-S02
event: REMOVE_READING_CHECKPOINT_PAGINATION_REWRITE_AND_VALIDATE
started_at: 2026-08-26T23:05:00+03:30
ended_at: 2026-08-26T23:20:17.0371045+03:30
goal_id: G-10
run_id: STAB-G10-R01
state_before: ROOT_CAUSE_CONFIRMED_RED_VERIFIED
state_after: DOCUMENTATION_AND_PUBLICATION_PENDING
actor: codex
action_kind: WRITE_TEST_BUILD_GENERATE
cwd: <project-root>
product_change: messages_list_fetch_preserves_original_input_and_init
source_dist_sha256: 6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893
validation: {source_contract: 1/1_pass, targeted: 11/11_pass, full_backend: 657/657_pass, collected_files: 74, skipped: 0, ui_runners: 9/9_pass, typescript: pass, vite_modules: 1015}
release: {archive_count: 2, byte_identical: true, file_count: 282, sha256: 077d316d5a546fa20eff39a9e77205e57756050ed293884bd34d09cba52a7f3e, content_set_sha256: 36012dbba19eb2b464bfa5df2de37006157e7515a774784738bc9d57fadcc1ff, privacy_findings: 0}
external_effect: test_temp
operational_data_write: 0
message_login_otp_wordpress_bale: 0
output_summary: بازنویسی pagination حذف و مجموعهٔ کامل آزمون و بستهٔ نهایی سبز شد؛ فقط کنترل اسناد و انتشار Git باقی است.
```

### STAB-G10-R01-S03 — کنترل اسناد و آماده‌سازی انتشار

```yaml
event_id: STAB-G10-R01-S03
event: DOCUMENTATION_INTEGRITY_RELEASE_DRY_RUN_AND_PUBLICATION_READINESS
started_at: 2026-08-26T23:20:17.0371045+03:30
ended_at: 2026-08-26T23:22:46.8856815+03:30
goal_id: G-10
run_id: STAB-G10-R01
state_before: DOCUMENTATION_AND_PUBLICATION_PENDING
state_after: TESTED_DOCUMENTED_READY_TO_PUBLISH
actor: codex
action_kind: GENERATE_TEST
cwd: <project-root>
documentation_checks: {refresh: pass, integrity: pass, stale: pass, links: pass, release_manifest_json: pass}
package_dry_run: {result: pass, file_count: 282, content_set_sha256: 36012dbba19eb2b464bfa5df2de37006157e7515a774784738bc9d57fadcc1ff, output_write: 0}
privacy_and_operational_effect: {release_findings: 0, message_send: 0, operational_write: 0}
next_action: exact_scope_git_stage_commit_push_and_remote_verify
output_summary: حافظهٔ مهندسی و نامزد release هم‌تراز و آمادهٔ انتشار عادی روی شاخهٔ کاری هستند.
```

### STAB-G10-R01-S04 — commit اصلی، push و verify شاخهٔ کاری

```yaml
event_id: STAB-G10-R01-S04
event: FINAL_SCENARIO_COMMIT_PUSH_AND_REMOTE_VERIFICATION
started_at: 2026-08-26T23:22:46.8856815+03:30
ended_at: 2026-08-26T23:25:35.3506616+03:30
goal_id: G-10
run_id: STAB-G10-R01
state_before: TESTED_DOCUMENTED_READY_TO_PUBLISH
state_after: PRIMARY_COMMIT_PUSH_VERIFIED_DOCUMENTATION_CLOSURE_PENDING
actor: codex
action_kind: USER_STANDING_AUTHORIZED_GIT_PUBLICATION
cwd: <project-root>
candidate: {files: 12, high_confidence_secret_findings: 0, operational_data_files: 0}
prepush_remote: {working_branch: 4f70ecd9af734685befa38ed31a6c7818d1c6803, main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2}
commit: {hash: 407cd418c2249fb6d9b51827e0601d9ca883d0d0, subject: 'fix(ui): show latest messages for selected groups'}
push: {branch: codex/stabilization-g09, force: false, result: PASS}
postpush_remote: {working_branch: 407cd418c2249fb6d9b51827e0601d9ca883d0d0, main: a4df3ecf2bcd4ab658c5361afdc287444694fcd2, equal_local_remote: true, main_unchanged: true}
excluded_actions: [main_push_or_merge, force_push, ref_delete, provider_operation, message_send]
next_action: documentation_closure_commit_normal_push_and_final_remote_verify
output_summary: commit اصلی G-10 روی شاخهٔ کاری منتشر و با حفظ کامل main زنده تأیید شد.
```

### STAB-G11-R01-S01 — تشخیص storage جاری/تاریخی و علت cache

```yaml
event_id: STAB-G11-R01-S01
event: MASKED_SELECTED_GROUP_CURRENT_HISTORICAL_MAPPING_AND_CACHE_ROOT_CAUSE
started_at: 2026-08-26T23:26:00+03:30
ended_at: 2026-08-27T00:05:00+03:30
goal_id: G-11
run_id: STAB-G11-R01
state_before: G10_PUBLISHED_USER_REPORTS_PROBLEM_UNRESOLVED
state_after: CACHE_DELIVERY_ROOT_CAUSE_CONFIRMED_RED_VERIFIED
actor: codex
action_kind: READ_ONLY_DIAGNOSIS_AND_CONTROLLED_TEST
cwd: <project-root>
masked_storage: {historical_messages: 420, historical_latest: 6_mordad, current_messages: 674, current_latest: 4_shahrivar, messages_after_historical_checkpoint: 254, current_catalog_top_matches_db: true}
root_cause: fixed_url_runtime_patch_served_with_one_year_immutable_cache
red: {passed: 6, failed: 3, expected_failure: true}
tool_events:
  - {scope: peer_file_mapping, attempt_a: FALSE_MISMATCH_WRONG_FIELD_NAME, retry: PASS_CANONICAL_LOADER, state_change: 0}
  - {scope: computer_use, attempts: 2, reset: 1, result: BLOCKED_BEFORE_INPUT, error: kernel_assets_path_not_found}
  - {scope: broad_runtime_scan, result: TERMINATED_AFTER_60_SECONDS, state_change: 0}
  - {scope: network_parser_path_probe_leveldb_identity_header, result: INVOCATION_ERRORS_CORRECTED_OR_NONESSENTIAL, state_change: 0}
privacy: {raw_title: not_recorded, peer_or_account_id: not_recorded, message_text: not_recorded}
operational_effect: 0
message_send_count: 0
output_summary: دادهٔ جاری تا ۴ شهریور حاضر بود؛ مرورگر به‌علت URL ثابت و cache immutable، pre-image منتهی به ۶ مرداد را اجرا می‌کرد.
```

### STAB-G11-R01-S02 — اصلاح build/cache و پذیرش کامل خودکار

```yaml
event_id: STAB-G11-R01-S02
event: CONTENT_HASH_RUNTIME_PATCH_AND_STATIC_CACHE_POLICY_REPAIR
started_at: 2026-08-27T00:05:00+03:30
ended_at: 2026-08-27T00:35:00+03:30
goal_id: G-11
run_id: STAB-G11-R01
state_before: CACHE_DELIVERY_ROOT_CAUSE_CONFIRMED_RED_VERIFIED
state_after: FULL_AUTOMATED_ACCEPTANCE_GREEN
actor: codex
action_kind: WRITE_TEST_BUILD_PACKAGE
cwd: <project-root>
product_change: {runtime_patch_filename: sha256_first_16, fixed_asset_cleanup: true, immutable_only_for_hashed_assets: true, fixed_and_index_cache: no_store}
targeted: {first_green: 8/9, regex_contract_retry: 9/9, related: 54/54}
ui: {runners: 9/9, typescript: PASS, build: PASS, modules: 1015, patch_sha256: 6de1ad483e2c97af76fd070abca34464d5ff158094ba7e0634d470620efc9893}
backend_attempt_a: {passed: 657, failed: 1, total: 658, only_failure: expected_wheel_source_parity_drift}
wheel: {builds: 2, byte_identical: true, sha256: ba05c810792fe695a96b90ce4b313ef3b5e15e7b9ef70032518c96923e295e7a, source_files: 90, missing: 0, mismatched: 0, extra: 0}
backend_retry: {passed: 658, failed: 0, errors: 0, skipped: 0, collected_files: 74}
external_effect: controlled_test_temp_ui_dist_wheel_artifacts
operational_data_write: 0
output_summary: cache-busting محتوایی و policy امن cache پیاده شد؛ کل Backend/UI پس از wheel reconciliation سبز است.
```

### STAB-G11-R01-S03 — archive، fresh-install و مستندسازی پیش از انتشار

```yaml
event_id: STAB-G11-R01-S03
event: REPRODUCIBLE_ARCHIVE_OFFLINE_FRESH_INSTALL_AND_DOCUMENTATION_ALIGNMENT
started_at: 2026-08-27T00:35:00+03:30
ended_at: 2026-08-27T01:05:00+03:30
goal_id: G-11
run_id: STAB-G11-R01
state_before: FULL_AUTOMATED_ACCEPTANCE_GREEN
state_after: TESTED_DOCUMENTED_READY_FOR_GIT_PUBLICATION
actor: codex
action_kind: PACKAGE_OFFLINE_INSTALL_DOCUMENT
cwd: <project-root>
archive: {count: 2, byte_identical: true, files: 282, sha256: 08c5d5dd132f2c4d7a41c27f0cd26d084630d747a542a8c7383296e906a2c61c, content_set: 4ec774ed765b932bb93fece08596108524608c18dc926be0d13b63a09e6c731e, internal_verification: PASS, rebuilt_after_adr40: true}
fresh_install: {network: 0, pip_no_index: true, runtime_checker: PASS, pip_check: PASS, isolated_import: PASS, event_catalog_count: 103}
live_http_attempt: {result: CONNECTION_REFUSED_APPLICATION_NOT_RUNNING, application_started_by_agent: false, product_failure: false}
tool_event: {scope: receipt_privacy_property_probe, attempt_a: WRONG_ABSENT_PROPERTY_COUNT, retry: CANONICAL_VERIFICATION_PASS, state_change: 0}
documentation_scope: [F-049, F-050, V-160, V-161, ADR-40, G10-correction, G11-report, baseline, handoff, release-manifest]
documentation_checks: {refresh: PASS, integrity: PASS, stale: PASS, links: PASS, report_index_line: 185, release_manifest_json: PASS, release_manifest_sha256: b89f4c2a592a9dc12f8f12cdd115fa05b5a686498f5f9cf4c450dc927f6d8f9c}
final_package_dry_run: {files: 282, content_set: 4ec774ed765b932bb93fece08596108524608c18dc926be0d13b63a09e6c731e, output_write: 0}
privacy_and_operational_effect: {raw_title_or_ids_logged: false, message_send: 0, provider_action: 0, data_write: 0}
next_action: documentation_checks_then_standing_authorized_working_branch_commit_push_verify
output_summary: artifact و نصب آفلاین G-11 سبز؛ تأیید زنده پس از restart کاربر pending و انتشار Git پس از کنترل اسناد انجام می‌شود.
```

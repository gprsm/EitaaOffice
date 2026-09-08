# دفتر اجرای append-only هوشمندسازی ایندکس و گزارش

وضعیت: `ACTIVE / PHASE_0`  
نقشه‌راه: [INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md](INDEX_INTELLIGENCE_REPORTING_ROADMAP_2026-08-27.md)  
قاعده: ورودی‌های ثبت‌شده حذف یا بازنویسی نمی‌شوند؛ correction با رکورد superseding تازه افزوده می‌شود.

## Run IDX-R01 — ثبت نقشه‌راه و آغاز کنترل‌شدهٔ Phase 0

### IDX-R01-S01 — ممیزی حافظهٔ قبلی و ثبت مرجع canonical

```yaml
event_id: IDX-R01-S01
event: INDEX_INTELLIGENCE_ROADMAP_REGISTRATION
started_at: 2026-08-27T00:00:00+03:30
ended_at: pending_final_validation
goal_id: IR-ROADMAP
run_id: IDX-R01
state_before: CHAT_ANALYSIS_AND_DUPLICATE_UNVALIDATED_MEMORY_RECORDS
state_after: ROADMAP_DRAFTED_PHASE_0_AUTHORIZED_VALIDATION_PENDING
actor: codex
action_kind: DOCUMENTATION_ONLY
cwd: <project-root>
user_authorization: ثبت نقشه‌راه و شروع از فاز صفر
product_source_change: 0
schema_or_runtime_change: 0
provider_or_network_operation: 0
operational_data_write: 0
private_message_content_recorded: false
legacy_memory_action: preserve_with_legacy_ids_and_supersession
canonical_finding: F-051
canonical_validation: V-163
next_action: refresh_integrity_stale_link_checks_then_document_scope_audit
```

### IDX-R01-S02 — کنترل اسناد و بستن ثبت نقشه‌راه

```yaml
event_id: IDX-R01-S02
event: ROADMAP_DOCUMENTATION_VALIDATED
started_at: 2026-08-27T07:43:00+03:30
ended_at: 2026-08-27T07:46:53+03:30
goal_id: IR-ROADMAP
run_id: IDX-R01
state_before: ROADMAP_DRAFTED_PHASE_0_AUTHORIZED_VALIDATION_PENDING
state_after: ROADMAP_REGISTERED_PHASE_0_AUTHORIZED
actor: codex
action_kind: DOCUMENTATION_VALIDATION
product_test_suite_run: false
product_test_suite_reason: DOCS_ONLY_NO_SOURCE_OR_RUNTIME_TRIGGER
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
duplicate_official_finding_or_validation_id: 0
operational_workbook_committed: false
next_action: IR-0-A_SOURCE_INVENTORY_AND_PROVENANCE
```

## Run IDX-R02 — IR-0-A / ثبت تنها منبع موجود

### IDX-R02-S01 — استخراج فقط‌خواندنی workbook و تشکیل مرجع

```yaml
event_id: IDX-R02-S01
event: PRIMARY_WORKBOOK_SOURCE_REGISTERED
observed_at: 2026-08-27T08:28:56+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: PRIMARY_REPORTING_SOURCE_UNREGISTERED
state_after: SRC-IR-001_REGISTERED_USER_CLARIFICATIONS_PENDING
actor: codex
action_kind: READ_ONLY_SOURCE_ANALYSIS_AND_DOCUMENTATION
user_authorization: workbook موجود تنها سند است و باید مرجع شود
source_id: SRC-IR-001
source_sha256: B7A8A79F9C4D093AD001294097FAC8930E0BCEE80191D06AD17E5C8825FB9296
workbook_sheet_count: 7
workbook_formula_count: 0
visual_sheet_pass_count: 7
source_file_modified: false
source_file_committed: false
product_source_change: 0
schema_or_runtime_change: 0
provider_or_network_operation: 0
canonical_finding: F-052
canonical_validation: V-164
open_question_range: Q-IR-001..Q-IR-012
next_action: validate_documentation_then_collect_numbered_user_answers
```

### IDX-R02-S02 — کنترل اسناد و توقف برای پاسخ دامنه

```yaml
event_id: IDX-R02-S02
event: PRIMARY_SOURCE_REFERENCE_VALIDATED
observed_at: 2026-08-27T08:31:02+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: SRC-IR-001_REGISTERED_DOCUMENTATION_VALIDATION_PENDING
state_after: USER_CLARIFICATIONS_PENDING
actor: codex
action_kind: DOCUMENTATION_VALIDATION
product_test_suite_run: false
product_test_suite_reason: READ_ONLY_SOURCE_ANALYSIS_NO_PRODUCT_TRIGGER
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS_AFTER_ONE_NEW_HARD_BREAK_CLEANUP
source_file_modified: false
source_file_committed: false
next_user_question_range: Q-IR-001..Q-IR-003
```

### IDX-R02-S03 — مهار artifactهای بیرونی و ثبت پاسخ جزئی

```yaml
event_id: IDX-R02-S03
event: EXTERNAL_AGENT_ARTIFACTS_CONTAINED_AND_USER_CLARIFICATIONS_RECORDED
observed_at: 2026-08-27T08:42:39+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: USER_CLARIFICATIONS_PENDING_EXTERNAL_AGENT_PLANS_UNGOVERNED
state_after: EXTERNAL_PLANS_SUPERSEDED_Q_IR_013_OPEN
actor: codex
action_kind: NON_DESTRUCTIVE_EXTERNAL_DOCUMENT_CORRECTION_AND_DOMAIN_RECORDING
external_markdown_files_corrected: 5
external_metadata_files_corrected: 5
external_files_deleted: 0
out_of_scope_similar_plans_modified: 0
canonical_external_artifact_register: EXTERNAL_AGENT_ARTIFACT_REGISTER.md
user_source_id: SRC-USER-IR-001
user_hypothesis_ceremony_code: 80403_UNCONFIRMED
framework_validity: EXPECTED_THROUGH_1405_YEAR_END_CHANGE_POSSIBLE
star_semantics: CENTRAL_UNIT_CLARIFICATION_REQUIRED
synthetic_statistics_policy: Q-IR-013_OPEN
product_or_schema_change: 0
next_action: validate_docs_then_collect_remaining_numbered_answers
```

### IDX-R02-S04 — کنترل نهایی و انتظار برای تصمیم دامنه

```yaml
event_id: IDX-R02-S04
event: EXTERNAL_ARTIFACT_AND_DOMAIN_RECORD_VALIDATION_COMPLETE
observed_at: 2026-08-27T08:42:39+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: EXTERNAL_PLANS_SUPERSEDED_DOCUMENTATION_VALIDATION_PENDING
state_after: Q_IR_004_THROUGH_013_PENDING
actor: codex
external_utf8_control_header_metadata_check: PASS
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
external_files_deleted: 0
product_test_suite_run: false
product_test_suite_reason: DOCUMENT_AND_EXTERNAL_ARTIFACT_GOVERNANCE_ONLY
next_action: COLLECT_NUMBERED_DOMAIN_ANSWERS
```

### IDX-R02-S05 — پذیرش سیاست کیفیت آمار دستی

```yaml
event_id: IDX-R02-S05
event: MANUAL_STATISTICS_VALUE_KIND_POLICY_ACCEPTED
observed_at: 2026-08-27T09:01:57+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_013_PENDING
state_after: Q_IR_013_RESOLVED_OTHER_DOMAIN_QUESTIONS_PENDING
actor: codex
user_source_id: SRC-USER-IR-002
accepted_value_kinds: observed,reported_by_unit,estimated,synthetic_placeholder,verified
estimated_or_synthetic_auto_verified: false
estimated_or_synthetic_auto_training_truth: false
explicit_user_confirmation_required: true
canonical_finding: F-054
canonical_validation: V-167
architecture_decision: ADR-42
product_or_schema_change: 0
next_action: VALIDATE_DOCUMENTATION_THEN_CONTINUE_IR_0_A
```

### IDX-R02-S06 — کنترل ثبت تصمیم Q-IR-013

```yaml
event_id: IDX-R02-S06
event: MANUAL_STATISTICS_POLICY_DOCUMENTATION_VALIDATED
observed_at: 2026-08-27T09:04:04+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_013_RESOLVED_DOCUMENTATION_VALIDATION_PENDING
state_after: Q_IR_004_THROUGH_012_PENDING
actor: codex
project_map_refresh: PASS
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
product_test_suite_run: false
product_test_suite_reason: DOMAIN_DOCUMENTATION_ONLY
next_action: CONTINUE_NUMBERED_DOMAIN_CLARIFICATIONS
```

### IDX-R02-S07 — پذیرش grain تجمیعی گزارش استانی

```yaml
event_id: IDX-R02-S07
event: PROVINCE_AGGREGATE_REPORTING_GRAIN_ACCEPTED
observed_at: 2026-08-27T09:12:42+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_004_PENDING
state_after: Q_IR_004_RESOLVED_Q_IR_005_THROUGH_012_PENDING
actor: codex
user_source_id: SRC-USER-IR-003
internal_grain: EVENT_AND_EVIDENCE
workbook_projection_grain: PROVINCE_PERIOD_PROGRAM_SUBTABLE
province_scope: PROVINCIAL_HEADQUARTERS_PLUS_COUNTY_UNITS
event_per_workbook_row: false
detail_breakdown_retained: true
canonical_finding: F-055
canonical_validation: V-168
architecture_decision: ADR-43
product_or_schema_change: 0
next_action: VALIDATE_DOCUMENTATION_THEN_Q_IR_005
```

### IDX-R02-S08 — کنترل ثبت grain گزارش

```yaml
event_id: IDX-R02-S08
event: PROVINCE_AGGREGATE_GRAIN_DOCUMENTATION_VALIDATED
observed_at: 2026-08-27T09:14:58+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_004_RESOLVED_DOCUMENTATION_VALIDATION_PENDING
state_after: Q_IR_005_THROUGH_012_PENDING
actor: codex
project_map_refresh: PASS
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
product_test_suite_run: false
product_test_suite_reason: DOMAIN_DOCUMENTATION_ONLY
next_action: Q_IR_005
```

### IDX-R02-S09 — ضمیمهٔ زیارت عاشورا و proposal پرسشنامهٔ برنامه

```yaml
event_id: IDX-R02-S09
event: SPECIAL_METRIC_ACCEPTED_AND_PROGRAM_QUESTIONNAIRE_PROPOSED
observed_at: 2026-08-27T18:16:16+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_005_PENDING
state_after: Q_IR_005_RESOLVED_QUESTIONNAIRE_PROPOSAL_RECORDED
actor: codex
user_source_id: SRC-USER-IR-004
ziyarat_ashura_separate_provincial_metric: true
ziyarat_ashura_separate_annex: true
ziyarat_ashura_increments_main_ceremony_count: false
questionnaire_model_status: PROPOSAL_NOT_IMPLEMENTED
questionnaire_shared_core_plus_program_modules: true
derived_values_require_formula_inputs_and_provenance: true
workflow_question: Q-IR-014
canonical_findings: F-057,F-058
canonical_validation: V-171
architecture_decision: ADR-45
product_or_schema_change: 0
next_action: VALIDATE_DOCUMENTATION_AND_CLARIFY_Q_IR_014
```

### IDX-R02-S10 — بازیابی از collision writer موازی

```yaml
event_id: IDX-R02-S10
event: CANONICAL_DOCUMENT_ID_COLLISION_RECOVERED
observed_at: 2026-08-27T18:22:39+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: DUPLICATE_F056_V169_AND_ADR44
state_after: UNIQUE_CANONICAL_IDS_DOCUMENTATION_GREEN
actor: codex
initial_memory_integrity: FAIL_DUPLICATE_FINDING_AND_VALIDATION
parallel_records_preserved: F-056,V-169,V-170,ADR-44
index_records_reallocated: F-057,F-058,V-171,ADR-45
final_memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
canonical_concurrency_finding: F-059
canonical_concurrency_validation: V-172
product_change_from_recovery: 0
next_action: Q_IR_014_OR_REMAINING_IR_0_A_QUESTIONS
```

### IDX-R02-S11 — پذیرش workflow ستادمحور و اختیار نهایی انسانی

```yaml
event_id: IDX-R02-S11
event: CENTRAL_OFFICE_ONLY_HUMAN_APPROVAL_WORKFLOW_ACCEPTED
observed_at: 2026-08-27T18:50:58+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_014_PENDING
state_after: Q_IR_014_RESOLVED_DOCUMENTATION_VALIDATION_PENDING
actor: codex
user_source_id: SRC-USER-IR-005
county_units_have_system_access: false
county_inbound_channel: EITAA
authorized_users: CENTRAL_OFFICE_HUMANS_ONLY
deployment_boundary: LOCAL_PRIVATE_LAN
wordpress_role: ACTIVITY_REPOSITORY_AND_SOURCE_OR_PROJECTION
preferred_assistance: LOCAL_LEARNING_AUTOMATION
external_agent_api: OPTIONAL_CONTROLLED_FALLBACK
agent_has_approval_authority: false
final_approval_aggregation_export: AUTHORIZED_CENTRAL_HUMAN_ONLY
canonical_finding: F-060
architecture_decision: ADR-46
product_or_schema_change: 0
next_action: VALIDATE_DOCUMENTATION_THEN_Q_IR_006_THROUGH_012
```

### IDX-R02-S12 — کنترل ثبت workflow ستادمحور

```yaml
event_id: IDX-R02-S12
event: CENTRAL_OFFICE_WORKFLOW_DOCUMENTATION_VALIDATED
observed_at: 2026-08-27T18:53:00+03:30
goal_id: IR-0-A
run_id: IDX-R02
state_before: Q_IR_014_RESOLVED_DOCUMENTATION_VALIDATION_PENDING
state_after: Q_IR_006_THROUGH_012_PENDING
actor: codex
canonical_finding: F-060
canonical_validation: V-173
architecture_decision: ADR-46
adr_numeric_order: PASS
project_map_refresh: PASS
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
product_test_suite_run: false
product_test_suite_reason: DOMAIN_DOCUMENTATION_ONLY
product_or_operational_change: 0
next_action: Q_IR_006_THROUGH_012
```

## Run IDX-R03 — ثبت مدل چهارسطحی و IR-GOV-01

### IDX-R03-S01 — پذیرش و تدوین مدل عملیاتی/واگذاری

```yaml
event_id: IDX-R03-S01
event: FOUR_LEVEL_OPERATING_MODEL_AND_AGENT_GOVERNANCE_ACCEPTED
observed_at: 2026-08-28T16:59:51+03:30
goal_id: IR-GOV-01
run_id: IDX-R03
state_before: TWO_CONCEPTUAL_AREAS_AND_GOVERNANCE_DEFERRED
state_after: FOUR_LEVEL_MODEL_AND_POLICY_V1_DOCUMENTED_VALIDATION_PENDING
actor: codex
user_source_id: SRC-USER-IR-006
levels: L1_SEMANTIC_INDEX,L2_WORDPRESS_PROJECTION,L3_REPORTING_CORE,L4_CONTROLLED_INTELLIGENCE
product_owner_and_final_acceptor: USER
architecture_and_integration_lead: CODEX
delegated_agent_default_output: AGENT_COMPLETED_UNREVIEWED
canonical_writer_and_promoter: CODEX_BY_DEFAULT
parallel_read_only_allowed: true
parallel_shared_worktree_write_allowed: false
isolated_nonoverlapping_worktree_write_allowed: true
automated_id_allocator_or_lock_implemented: false
initial_requested_ids: F-064,V-186,ADR-50
concurrent_collision: INTERNAL_CODE_SIGNING_WRITER_USED_INITIAL_IDS
reallocated_ids: F-065,V-187,ADR-51
canonical_finding: F-065
architecture_decision: ADR-51
product_or_schema_change: 0
next_action: VALIDATE_DOCUMENTATION_AND_REGISTER_V187
```

### IDX-R03-S02 — بازیابی collision و کنترل نهایی اسناد

```yaml
event_id: IDX-R03-S02
event: FOUR_LEVEL_MODEL_AND_IR_GOV_01_DOCUMENTATION_VALIDATED
observed_at: 2026-08-28T17:06:50+03:30
goal_id: IR-GOV-01
run_id: IDX-R03
state_before: DUPLICATE_F064_AND_ADR50_AFTER_CONCURRENT_WRITE
state_after: FOUR_LEVEL_MODEL_AND_POLICY_V1_CANONICAL_Q_IR_006_THROUGH_012_PENDING
actor: codex
parallel_records_preserved: F-064,V-186,ADR-50
index_governance_records: F-065,V-187,ADR-51
project_map_refresh: PASS
memory_integrity: PASS
generated_docs_freshness: PASS
markdown_link_check: PASS
git_diff_check: PASS
duplicate_official_id: 0
product_test_suite_run: false
product_test_suite_reason: DOMAIN_AND_GOVERNANCE_DOCUMENTATION_ONLY
product_or_operational_change: 0
next_action: CREATE_SEPARATE_TASK_CONTRACTS_OR_CONTINUE_Q_IR_006_THROUGH_012
```

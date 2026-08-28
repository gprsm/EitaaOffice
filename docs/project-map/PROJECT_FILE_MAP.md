# نقشهٔ ماشینی فایل‌های پروژه

> این فایل تولیدشونده است؛ با `scripts/refresh_project_docs.py` بازسازی شود.

- تعداد فایل‌های نقشه: 264
- اثرانگشت منبع: `872d083733503797`
- دامنه: source، test، tooling و installer؛ runtime/data/config خصوصی عمداً حذف شده‌اند.

| فایل | نقش | تعداد نماد | توضیح ماژول |
|---|---:|---:|---|
| `installer/EitaaBridge.iss` | Installer | 0 | — |
| `scripts/backup_runtime.py` | Operations/tooling | 3 | — |
| `scripts/build_gmi4_release.py` | Operations/tooling | 3 | Generate review artifacts and privacy-clean GMI4 ZIPs from the signed GMI3 base. |
| `scripts/build_wheel_stdlib.py` | Operations/tooling | 9 | Build the pure-Python bridge wheel without network or build backends. |
| `scripts/check_gmi4_invariants.py` | Operations/tooling | 1 | Compare frozen assets directly against the signed clean GMI3 base ZIP. |
| `scripts/check_project_memory_integrity.py` | Operations/tooling | 8 | — |
| `scripts/check_runtime_environment.py` | Operations/tooling | 1 | — |
| `scripts/clean_app.py` | Operations/tooling | 0 | — |
| `scripts/create_diagnostics_bundle.py` | Operations/tooling | 11 | — |
| `scripts/create_shortcuts.ps1` | Operations/tooling | 0 | — |
| `scripts/doctor.py` | Operations/tooling | 0 | — |
| `scripts/gmi4_smoke.py` | Operations/tooling | 2 | Deterministic no-network smoke suite for source and installed-wheel validation. |
| `scripts/migrate_legacy_account.py` | Operations/tooling | 6 | Interactive, no-network migration utility for the initial legacy Eitaa account. |
| `scripts/office_runtime.py` | Operations/tooling | 54 | — |
| `scripts/phase10_auth_failure_verify.py` | Operations/tooling | 1 | Print only safe recent authentication failure metadata from the live coordinator. |
| `scripts/phase10_contacts_migrate.py` | Operations/tooling | 5 | Controlled live Contacts schema 1-to-2 migration for Phase 10. |
| `scripts/phase10_copy_rehearsal.py` | Operations/tooling | 7 | Read-only Phase 10 rehearsal using disposable copies of runtime state. |
| `scripts/phase10_identity_verify.py` | Operations/tooling | 2 | Safely verify the live coordinator phone identity without disclosing it. |
| `scripts/phase10_local_activation_verify.py` | Operations/tooling | 4 | Read-only verifier for the real Phase 10-B loopback activation. |
| `scripts/phase10_log_redaction_verify.py` | Operations/tooling | 7 | Scan every runtime JSONL log without echoing paths, account ids, or values. |
| `scripts/phase10_rewrap_app_auth_key.py` | Operations/tooling | 1 | Rewrap the live AppUser subject key for stable local-machine execution. |
| `scripts/phase10d_copy_rehearsal.py` | Operations/tooling | 4 | Restore and roll back a verified backup only inside an isolated temporary copy. |
| `scripts/prepare_windows_release.py` | Operations/tooling | 3 | — |
| `scripts/refresh_project_docs.py` | Operations/tooling | 11 | Generate safe project maps and document indexes without reading runtime data. |
| `scripts/restore_runtime.py` | Operations/tooling | 6 | — |
| `scripts/runtime_state.py` | Operations/tooling | 9 | — |
| `scripts/scan_diagnostics_bundle.py` | Operations/tooling | 5 | Verify a diagnostics ZIP without echoing any bundled value. |
| `scripts/stabilization_baseline.py` | Operations/tooling | 14 | — |
| `scripts/sync_ui_fonts.py` | Operations/tooling | 2 | — |
| `scripts/write_iexpress_sed.py` | Operations/tooling | 1 | — |
| `src/eitaa_bridge/__init__.py` | Project | 0 | Eitaa Bridge public package. |
| `src/eitaa_bridge/application/__init__.py` | Application | 0 | — |
| `src/eitaa_bridge/application/account_auth.py` | Application | 15 | In-memory, account-bound Eitaa authentication challenge metadata. |
| `src/eitaa_bridge/application/account_runtime.py` | Application | 47 | Account-scoped Eitaa runtime and fail-closed registry. |
| `src/eitaa_bridge/application/api.py` | Application | 268 | UI-facing local application API independent of any web framework. |
| `src/eitaa_bridge/application/bale_client/__init__.py` | Application | 0 | Bale Personal Client research framework. |
| `src/eitaa_bridge/application/bale_client/auth.py` | Application | 9 | — |
| `src/eitaa_bridge/application/bale_client/catalog.py` | Application | 0 | — |
| `src/eitaa_bridge/application/bale_client/cli.py` | Application | 9 | — |
| `src/eitaa_bridge/application/bale_client/client.py` | Application | 44 | — |
| `src/eitaa_bridge/application/bale_client/codecs.py` | Application | 31 | — |
| `src/eitaa_bridge/application/bale_client/config.py` | Application | 1 | — |
| `src/eitaa_bridge/application/bale_client/errors.py` | Application | 12 | — |
| `src/eitaa_bridge/application/bale_client/grpc_web.py` | Application | 9 | — |
| `src/eitaa_bridge/application/bale_client/lab.py` | Application | 45 | — |
| `src/eitaa_bridge/application/bale_client/models.py` | Application | 15 | — |
| `src/eitaa_bridge/application/bale_client/vault.py` | Application | 7 | — |
| `src/eitaa_bridge/application/bale_client/wire.py` | Application | 39 | — |
| `src/eitaa_bridge/application/bale_client/ws.py` | Application | 26 | — |
| `src/eitaa_bridge/application/bale_provider_adapter.py` | Application | 2 | Quarantine boundary for the incomplete Bale application adapter. |
| `src/eitaa_bridge/application/contact_import.py` | Application | 4 | Dependency-free CSV/TXT/XLSX contact import parsing and explicit column mapping. |
| `src/eitaa_bridge/application/content_index.py` | Application | 16 | Explainable, dependency-free Persian multi-label content indexing. |
| `src/eitaa_bridge/application/content_index_service.py` | Application | 7 | Local-only indexing orchestration over public Core message services. |
| `src/eitaa_bridge/application/doctor.py` | Application | 5 | — |
| `src/eitaa_bridge/application/eitaa_provider_runtime_operations.py` | Application | 24 | Bounded Eitaa application operations owned by one account runtime. |
| `src/eitaa_bridge/application/eitaa_provider_worker.py` | Application | 11 | Dedicated Child-process host for one Eitaa MessengerAccount runtime. |
| `src/eitaa_bridge/application/fake_provider_worker.py` | Application | 5 | Provider-neutral fake worker used to prove the Phase 7 IPC boundary. |
| `src/eitaa_bridge/application/process_runtime.py` | Application | 39 | Parent-side control proxy for one account-owned Eitaa Child process. |
| `src/eitaa_bridge/application/provider_adapter.py` | Application | 1 | Compatibility facade for the versioned provider extension SDK. |
| `src/eitaa_bridge/application/provider_capabilities.py` | Application | 10 | Account-scoped capability decisions for every registered provider. |
| `src/eitaa_bridge/application/provider_orchestration.py` | Application | 31 | Provider-neutral application orchestration for bounded messaging operations. |
| `src/eitaa_bridge/application/scheduler.py` | Application | 12 | Single-session priority scheduler for Eitaa operations. |
| `src/eitaa_bridge/application/services/__init__.py` | Application | 0 | — |
| `src/eitaa_bridge/application/services/wordpress_service.py` | Application | 15 | — |
| `src/eitaa_bridge/application/workflows/__init__.py` | Application | 0 | — |
| `src/eitaa_bridge/application/workflows/compose_wordpress_post.py` | Application | 20 | — |
| `src/eitaa_bridge/application/workflows/create_text_draft.py` | Application | 2 | — |
| `src/eitaa_bridge/application/workflows/publish_stored_message.py` | Application | 29 | — |
| `src/eitaa_bridge/application/workflows/upload_wordpress_media.py` | Application | 2 | — |
| `src/eitaa_bridge/config.py` | Project | 35 | Typed Bridge configuration independent of secret values. |
| `src/eitaa_bridge/domain/__init__.py` | Domain | 0 | — |
| `src/eitaa_bridge/domain/composer.py` | Domain | 17 | — |
| `src/eitaa_bridge/domain/health.py` | Domain | 6 | — |
| `src/eitaa_bridge/domain/publication.py` | Domain | 4 | — |
| `src/eitaa_bridge/domain/wordpress.py` | Domain | 13 | — |
| `src/eitaa_bridge/errors.py` | Project | 40 | Typed, safe exception hierarchy for Eitaa Bridge. |
| `src/eitaa_bridge/facade.py` | Project | 40 | — |
| `src/eitaa_bridge/infrastructure/__init__.py` | Infrastructure | 0 | — |
| `src/eitaa_bridge/infrastructure/composition_manifest.py` | Infrastructure | 4 | — |
| `src/eitaa_bridge/infrastructure/composition_store.py` | Infrastructure | 10 | — |
| `src/eitaa_bridge/infrastructure/config/__init__.py` | Infrastructure | 0 | Configuration adapters. |
| `src/eitaa_bridge/infrastructure/config/deployment_settings.py` | Infrastructure | 11 | Validated, atomic editing of the internal HTTP deployment port. |
| `src/eitaa_bridge/infrastructure/config/env_loader.py` | Infrastructure | 2 | — |
| `src/eitaa_bridge/infrastructure/config/loader.py` | Infrastructure | 28 | — |
| `src/eitaa_bridge/infrastructure/config/site_settings.py` | Infrastructure | 12 | Safe local editing of WordPress site configuration and credentials. |
| `src/eitaa_bridge/infrastructure/contact_store.py` | Infrastructure | 31 | Bridge-owned local contact directory with conservative deduplication. |
| `src/eitaa_bridge/infrastructure/content_index_store.py` | Infrastructure | 22 | Bridge-owned SQLite storage for local index suggestions and feedback. |
| `src/eitaa_bridge/infrastructure/coordinator/__init__.py` | Infrastructure | 0 | Coordinator persistence and safe legacy-migration primitives. |
| `src/eitaa_bridge/infrastructure/coordinator/app_auth.py` | Infrastructure | 66 | Local AppUser credentials, sessions, throttling, roles, and safe audit. |
| `src/eitaa_bridge/infrastructure/coordinator/audit.py` | Infrastructure | 21 | Authorized, tamper-evident Coordinator audit query and JSONL export. |
| `src/eitaa_bridge/infrastructure/coordinator/identity.py` | Infrastructure | 18 | Protected phone identity primitives for the local Windows coordinator. |
| `src/eitaa_bridge/infrastructure/coordinator/jobs.py` | Infrastructure | 35 | Persistent, account-scoped operation jobs owned by the Coordinator. |
| `src/eitaa_bridge/infrastructure/coordinator/migration.py` | Infrastructure | 28 | Copy-and-verify migration from the single-account legacy layout. |
| `src/eitaa_bridge/infrastructure/coordinator/rate_policy.py` | Infrastructure | 25 | Persisted per-account execution limits, backoff, and circuit breaking. |
| `src/eitaa_bridge/infrastructure/coordinator/receipts.py` | Infrastructure | 13 | Persistent, privacy-safe idempotency claims for provider mutations. |
| `src/eitaa_bridge/infrastructure/coordinator/schema.py` | Infrastructure | 2 | Versioned SQLite schema for the multi-provider coordinator. |
| `src/eitaa_bridge/infrastructure/coordinator/store.py` | Infrastructure | 74 | Transactional coordinator database with safe bootstrap and append-only audit. |
| `src/eitaa_bridge/infrastructure/data_scope.py` | Infrastructure | 12 | Canonical provider/account scope for Bridge-owned data repositories. |
| `src/eitaa_bridge/infrastructure/diagnostics/__init__.py` | Infrastructure | 0 | — |
| `src/eitaa_bridge/infrastructure/diagnostics/event_catalog.py` | Infrastructure | 9 | Versioned, privacy-safe observability event contract. |
| `src/eitaa_bridge/infrastructure/diagnostics/manager.py` | Infrastructure | 13 | — |
| `src/eitaa_bridge/infrastructure/diagnostics/redaction.py` | Infrastructure | 5 | — |
| `src/eitaa_bridge/infrastructure/diagnostics/runtime_logger.py` | Infrastructure | 15 | — |
| `src/eitaa_bridge/infrastructure/dialog_catalog.py` | Infrastructure | 19 | — |
| `src/eitaa_bridge/infrastructure/eitaa/__init__.py` | Infrastructure | 0 | — |
| `src/eitaa_bridge/infrastructure/eitaa/core_binding.py` | Infrastructure | 8 | Composition through the public eitaa_core package only. |
| `src/eitaa_bridge/infrastructure/eitaa/dialog_permissions.py` | Infrastructure | 4 | Capture safe current-account management hints from pinned Core dialog data. |
| `src/eitaa_bridge/infrastructure/eitaa/sender_directory.py` | Infrastructure | 14 | Persist human-readable message authors exposed by Eitaa history responses. |
| `src/eitaa_bridge/infrastructure/eitaa/session_ownership.py` | Infrastructure | 9 | Explicit, side-effect-free ownership contract for Eitaa session storage. |
| `src/eitaa_bridge/infrastructure/windows_lan.py` | Infrastructure | 15 | — |
| `src/eitaa_bridge/infrastructure/wordpress/__init__.py` | Infrastructure | 0 | — |
| `src/eitaa_bridge/infrastructure/wordpress/auth.py` | Infrastructure | 5 | — |
| `src/eitaa_bridge/infrastructure/wordpress/client.py` | Infrastructure | 33 | — |
| `src/eitaa_bridge/infrastructure/worker_ipc/__init__.py` | Infrastructure | 0 | Authenticated, versioned local IPC primitives for provider workers. |
| `src/eitaa_bridge/infrastructure/worker_ipc/error_taxonomy.py` | Infrastructure | 1 | Stable safe error categories for the worker IPC protocol. |
| `src/eitaa_bridge/infrastructure/worker_ipc/protocol.py` | Infrastructure | 12 | Signed JSON-line envelope contract for local provider worker processes. |
| `src/eitaa_bridge/infrastructure/worker_ipc/secret_file.py` | Infrastructure | 11 | Short-lived, current-user-only authentication material for worker IPC. |
| `src/eitaa_bridge/interfaces/__init__.py` | Interface | 0 | — |
| `src/eitaa_bridge/interfaces/cli.py` | Interface | 5 | — |
| `src/eitaa_bridge/interfaces/http_api.py` | Interface | 64 | Config-bound loopback/trusted-LAN HTTP adapter for the application API. |
| `src/eitaa_bridge/interfaces/provider_worker.py` | Interface | 6 | Independent provider-worker process entrypoint for the Phase 7 IPC contract. |
| `src/eitaa_bridge/interfaces/windows_lan.py` | Interface | 3 | — |
| `src/eitaa_bridge/providers/__init__.py` | Project | 0 | Public, provider-neutral extension contracts and the built-in registry. |
| `src/eitaa_bridge/providers/bale/__init__.py` | Project | 0 | Disabled Bale extension slot; contains no endpoint or protocol implementation. |
| `src/eitaa_bridge/providers/bale/slot.py` | Project | 1 | Fail-closed Bale registration for the stabilization baseline. |
| `src/eitaa_bridge/providers/contracts.py` | Project | 88 | Versioned, bounded contracts for authorized messaging-provider extensions. |
| `src/eitaa_bridge/providers/eitaa/__init__.py` | Project | 0 | Eitaa provider integration behind the public provider contract. |
| `src/eitaa_bridge/providers/eitaa/application_adapter.py` | Project | 16 | Compatibility adapter that keeps Eitaa translation outside orchestration. |
| `src/eitaa_bridge/providers/fake/__init__.py` | Project | 0 | Offline provider used only for shared contract and isolation tests. |
| `src/eitaa_bridge/providers/fake/adapter.py` | Project | 11 | Deterministic, network-free implementation of ProviderAdapter. |
| `src/eitaa_bridge/providers/fake/slot.py` | Project | 4 | Allowlisted Fake provider composition; never enabled in product catalogs. |
| `src/eitaa_bridge/providers/registry.py` | Project | 2 | Built-in allowlisted provider composition root. |
| `src/eitaa_bridge/providers/testing.py` | Project | 9 | Offline-only contract harness for provider-extension authors. |
| `src/eitaa_bridge/version.py` | Project | 0 | — |
| `tests/conftest.py` | Python test | 8 | — |
| `tests/test_account_auth_lifecycle.py` | Python test | 35 | — |
| `tests/test_account_runtime.py` | Python test | 12 | — |
| `tests/test_app_user_api.py` | Python test | 9 | — |
| `tests/test_app_user_auth.py` | Python test | 25 | — |
| `tests/test_application_api.py` | Python test | 40 | — |
| `tests/test_bale_stabilization_fail_closed.py` | Python test | 6 | — |
| `tests/test_clean_install_auth_stabilization.py` | Python test | 27 | — |
| `tests/test_composer_workflow.py` | Python test | 48 | — |
| `tests/test_config.py` | Python test | 14 | — |
| `tests/test_contact_directory.py` | Python test | 14 | — |
| `tests/test_contact_sources_handoff.py` | Python test | 3 | — |
| `tests/test_content_index.py` | Python test | 13 | — |
| `tests/test_coordinator_migration.py` | Python test | 9 | — |
| `tests/test_coordinator_schema.py` | Python test | 12 | — |
| `tests/test_core_binding.py` | Python test | 4 | — |
| `tests/test_deployment_port_settings.py` | Python test | 4 | — |
| `tests/test_diagnostics.py` | Python test | 4 | — |
| `tests/test_dialog_catalog.py` | Python test | 7 | — |
| `tests/test_dialog_permissions.py` | Python test | 3 | — |
| `tests/test_env_and_credentials.py` | Python test | 6 | — |
| `tests/test_facade_and_cli.py` | Python test | 11 | — |
| `tests/test_g04_identity_privacy_stabilization.py` | Python test | 4 | — |
| `tests/test_g04d_privacy_channels.py` | Python test | 9 | — |
| `tests/test_g05_auto_index_lifecycle_stabilization.py` | Python test | 6 | — |
| `tests/test_g06_test_contract_integrity.py` | Python test | 6 | — |
| `tests/test_g07_release_packaging.py` | Python test | 16 | — |
| `tests/test_g08_observability_completion.py` | Python test | 15 | — |
| `tests/test_gmi42_contacts_send.py` | Python test | 8 | — |
| `tests/test_grouped_media.py` | Python test | 9 | — |
| `tests/test_http_api_media.py` | Python test | 2 | — |
| `tests/test_material_ui_repair.py` | Python test | 27 | — |
| `tests/test_multi_account_lab.py` | Python test | 3 | — |
| `tests/test_mvp6_operations.py` | Python test | 23 | — |
| `tests/test_observability_contract.py` | Python test | 7 | — |
| `tests/test_phase10b_local_activation.py` | Python test | 3 | — |
| `tests/test_phase10c_web_reverse_proxy_contract.py` | Python test | 20 | — |
| `tests/test_phase10d_operational_acceptance.py` | Python test | 10 | — |
| `tests/test_phase11_0_multi_account_onboarding.py` | Python test | 13 | — |
| `tests/test_phase11b1_multi_provider_core.py` | Python test | 10 | — |
| `tests/test_phase11b2_provider_neutral_orchestration.py` | Python test | 0 | — |
| `tests/test_phase11b_provider_extension_foundation.py` | Python test | 20 | — |
| `tests/test_phase4d_account_management.py` | Python test | 14 | — |
| `tests/test_phase5_shared_contacts.py` | Python test | 12 | — |
| `tests/test_phase6a_trusted_lan_http.py` | Python test | 9 | — |
| `tests/test_phase6b_lan_http_auth_session_hardening.py` | Python test | 29 | — |
| `tests/test_phase6c_windows_lan_serving_operations.py` | Python test | 9 | — |
| `tests/test_phase6d_mobile_lan_concurrency_acceptance.py` | Python test | 12 | — |
| `tests/test_phase7a_worker_ipc_protocol.py` | Python test | 7 | — |
| `tests/test_phase7b_eitaa_process_runtime.py` | Python test | 10 | — |
| `tests/test_phase7c_process_supervisor.py` | Python test | 12 | — |
| `tests/test_phase7d_process_isolation_adversarial.py` | Python test | 9 | — |
| `tests/test_phase8a_account_scoped_data.py` | Python test | 8 | — |
| `tests/test_phase8b_persistent_jobs.py` | Python test | 9 | — |
| `tests/test_phase8c_account_execution_policy.py` | Python test | 7 | — |
| `tests/test_phase8d_audit_stress_acceptance.py` | Python test | 6 | — |
| `tests/test_phase9a_access_management.py` | Python test | 5 | — |
| `tests/test_phase9c_device_sessions.py` | Python test | 4 | — |
| `tests/test_phase9d_multi_client_acceptance.py` | Python test | 2 | — |
| `tests/test_priority_scheduler.py` | Python test | 2 | — |
| `tests/test_project_memory_integrity.py` | Python test | 5 | — |
| `tests/test_publication_workflow.py` | Python test | 55 | — |
| `tests/test_refresh_project_docs.py` | Python test | 1 | — |
| `tests/test_runtime_backup.py` | Python test | 6 | — |
| `tests/test_runtime_ownership.py` | Python test | 23 | — |
| `tests/test_sender_directory.py` | Python test | 1 | — |
| `tests/test_session_ownership.py` | Python test | 8 | — |
| `tests/test_stabilization_baseline.py` | Python test | 3 | — |
| `tests/test_ui2_scroll_repair.py` | Python test | 8 | — |
| `tests/test_ui31_composer_refinement.py` | Python test | 4 | — |
| `tests/test_ui32_composer_usage_layout.py` | Python test | 5 | — |
| `tests/test_ui33_usage_reading_position.py` | Python test | 7 | — |
| `tests/test_ui3_dialog_operations.py` | Python test | 6 | — |
| `tests/test_ui_repair.py` | Python test | 10 | — |
| `tests/test_wordpress_client.py` | Python test | 33 | — |
| `tests/test_wordpress_taxonomies.py` | Python test | 5 | — |
| `ui/electron/main.cjs` | Electron shell | 24 | — |
| `ui/electron/observability.cjs` | Electron shell | 6 | — |
| `ui/electron/preload.cjs` | Electron shell | 0 | — |
| `ui/scripts/capture-rtl-layout.cjs` | UI validation | 5 | — |
| `ui/scripts/finalize-ui-build.mjs` | UI validation | 0 | — |
| `ui/scripts/run-grouped-media-tests.mjs` | UI validation | 1 | — |
| `ui/scripts/run-mobile-auth-live-tests.mjs` | UI validation | 1 | — |
| `ui/scripts/run-observability-tests.mjs` | UI validation | 0 | — |
| `ui/scripts/run-phase10-local-activation-tests.mjs` | UI validation | 2 | — |
| `ui/scripts/run-phase11-onboarding-tests.mjs` | UI validation | 2 | — |
| `ui/scripts/run-phase11b2-orchestration-tests.mjs` | UI validation | 2 | — |
| `ui/scripts/run-phase9-acceptance-tests.mjs` | UI validation | 2 | — |
| `ui/scripts/run-phase9-workspace-tests.mjs` | UI validation | 3 | — |
| `ui/scripts/run-scroll-tests.mjs` | UI validation | 2 | — |
| `ui/src/AccessManagementPanel.tsx` | React UI | 4 | — |
| `ui/src/App.tsx` | React UI | 69 | — |
| `ui/src/AppUserGate.tsx` | React UI | 11 | — |
| `ui/src/AppUserManagementPanel.tsx` | React UI | 6 | — |
| `ui/src/AuthBrand.tsx` | React UI | 2 | — |
| `ui/src/ChatHeader.tsx` | React UI | 1 | — |
| `ui/src/ClientErrorBoundary.tsx` | React UI | 4 | — |
| `ui/src/ConnectionStatus.tsx` | React UI | 4 | — |
| `ui/src/ContactDirectoryModal.tsx` | React UI | 20 | — |
| `ui/src/ContentIndexDialog.tsx` | React UI | 2 | — |
| `ui/src/ConversationListPage.tsx` | React UI | 4 | — |
| `ui/src/HeaderMessageSearch.tsx` | React UI | 3 | — |
| `ui/src/lib/accountScope.mjs` | React UI | 3 | — |
| `ui/src/lib/api.ts` | React UI | 17 | — |
| `ui/src/lib/avatarLoader.ts` | React UI | 7 | — |
| `ui/src/lib/avatarQueue.mjs` | React UI | 2 | — |
| `ui/src/lib/groupedMedia.ts` | React UI | 12 | — |
| `ui/src/lib/polling.mjs` | React UI | 3 | — |
| `ui/src/lib/scrollMath.ts` | React UI | 8 | — |
| `ui/src/lib/types.ts` | React UI | 0 | — |
| `ui/src/LoginExperience.tsx` | React UI | 6 | — |
| `ui/src/main.tsx` | React UI | 7 | — |
| `ui/src/MaterialToast.tsx` | React UI | 3 | — |
| `ui/src/MessageContentCard.tsx` | React UI | 8 | — |
| `ui/src/MessageFilterDialog.tsx` | React UI | 1 | — |
| `ui/src/MessageIndexEditor.tsx` | React UI | 1 | — |
| `ui/src/MessengerAccountGate.tsx` | React UI | 12 | — |
| `ui/src/QuickSendBar.tsx` | React UI | 4 | — |
| `ui/src/rtlCache.ts` | React UI | 0 | — |
| `ui/src/SessionManagementPanel.tsx` | React UI | 5 | — |
| `ui/src/SettingsPage.tsx` | React UI | 10 | — |
| `ui/src/stylis.d.ts` | React UI | 0 | — |
| `ui/src/theme.ts` | React UI | 2 | — |
| `ui/src/ui33-runtime-patch.js` | React UI | 26 | — |
| `ui/src/UsageInfoDialog.tsx` | React UI | 1 | — |
| `ui/src/utils/helpers.tsx` | React UI | 30 | — |
| `ui/src/utils/jalali.tsx` | React UI | 20 | — |
| `ui/src/vite-env.d.ts` | React UI | 0 | — |
| `ui/src/WordPressIcon.tsx` | React UI | 1 | — |
| `ui/src/WorkspaceNavigation.tsx` | React UI | 4 | — |

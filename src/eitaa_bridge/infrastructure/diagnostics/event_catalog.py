"""Versioned, privacy-safe observability event contract.

All literal ``RuntimeLogger`` events are registered here. Dynamic feature
events remain readable, but should be migrated to a named catalog entry before
new code relies on them for support or alerting.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final


EVENT_SCHEMA_VERSION: Final[int] = 1
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_SOURCE_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,47}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_CORRELATION_ID = re.compile(r"^[0-9a-f]{12,64}$")

LEVELS: Final[frozenset[str]] = frozenset({"debug", "info", "warning", "error", "critical"})
RESULTS: Final[frozenset[str]] = frozenset(
    {"observed", "started", "succeeded", "failed", "rejected", "degraded", "cancelled", "uncertain"}
)


@dataclass(frozen=True, slots=True)
class EventDefinition:
    name: str
    category: str
    default_result: str
    material: bool = True
    audit_required: bool = False


_DEFINITIONS: Final[tuple[EventDefinition, ...]] = (
    EventDefinition("application_started", "lifecycle", "succeeded"),
    EventDefinition("application_start_failed", "lifecycle", "failed"),
    EventDefinition("application_stopping", "lifecycle", "started"),
    EventDefinition("application_stopped", "lifecycle", "succeeded"),
    EventDefinition("application_stop_failed", "lifecycle", "failed"),
    EventDefinition("api_request", "request", "observed"),
    EventDefinition("account_api_request", "request", "observed"),
    EventDefinition("renderer_error_reported", "client", "failed"),
    EventDefinition("desktop_api_start_failed", "desktop", "failed"),
    EventDefinition("desktop_api_process_started", "desktop", "succeeded"),
    EventDefinition("desktop_api_process_error", "desktop", "failed"),
    EventDefinition("desktop_api_process_exited", "desktop", "observed"),
    EventDefinition("desktop_api_ownership_conflict", "desktop", "rejected"),
    EventDefinition("desktop_api_health_timeout", "desktop", "failed"),
    EventDefinition("desktop_api_recovery_requested", "desktop", "started"),
    EventDefinition("desktop_api_request_failed", "desktop", "failed"),
    EventDefinition("desktop_api_retry_failed", "desktop", "failed"),
    EventDefinition("desktop_renderer_error_reported", "client", "failed"),
    EventDefinition("desktop_renderer_process_gone", "desktop", "failed"),
    EventDefinition("desktop_renderer_unresponsive", "desktop", "degraded"),
    EventDefinition("desktop_renderer_load_failed", "desktop", "failed"),
    EventDefinition("desktop_process_warning", "desktop", "degraded"),
    EventDefinition("desktop_uncaught_exception", "desktop", "failed"),
    EventDefinition("operation_started", "operation", "started"),
    EventDefinition("operation_succeeded", "operation", "succeeded"),
    EventDefinition("operation_failed", "operation", "failed"),
    EventDefinition("operation_cancelled", "operation", "cancelled"),
    EventDefinition("operation_uncertain", "operation", "uncertain", audit_required=True),
    EventDefinition("auth_audit_write_failed", "authentication", "failed"),
    EventDefinition("auth_challenge_advanced", "authentication", "observed"),
    EventDefinition("auth_challenge_created", "authentication", "started"),
    EventDefinition("auth_challenge_denied", "authentication", "rejected", audit_required=True),
    EventDefinition("auth_challenge_expired", "authentication", "rejected", audit_required=True),
    EventDefinition("auth_logout_local_fallback_completed", "authentication", "succeeded", audit_required=True),
    EventDefinition("auth_runtime_close_failed", "authentication", "degraded"),
    EventDefinition("auth_session_invalid_detected", "authentication", "failed", audit_required=True),
    EventDefinition("auth_state_transition", "authentication", "observed", audit_required=True),
    EventDefinition("auth_uncoordinated_session_archive_failed", "authentication", "failed"),
    EventDefinition("auth_uncoordinated_session_archived", "authentication", "succeeded", audit_required=True),
    EventDefinition("background_task_failed", "background_task", "failed"),
    EventDefinition("community_member_mutation_completed", "community", "succeeded", audit_required=True),
    EventDefinition("contact_import_completed", "contacts", "succeeded", audit_required=True),
    EventDefinition("contact_import_failed", "contacts", "failed"),
    EventDefinition("contact_import_local_completed", "contacts", "succeeded", audit_required=True),
    EventDefinition("contact_import_started", "contacts", "started"),
    EventDefinition("contact_source_import_completed", "contacts", "succeeded", audit_required=True),
    EventDefinition("contact_source_import_failed", "contacts", "failed"),
    EventDefinition("contact_source_import_started", "contacts", "started"),
    EventDefinition("content_auto_index_scheduler_skipped", "content_index", "rejected"),
    EventDefinition("content_index_job_started", "content_index", "started"),
    EventDefinition("content_index_job_succeeded", "content_index", "succeeded"),
    EventDefinition("content_index_job_cancelled", "content_index", "cancelled"),
    EventDefinition("content_index_job_failed", "content_index", "failed"),
    EventDefinition("content_index_job_cleanup_failed", "content_index", "degraded"),
    EventDefinition("diagnostics_pruned", "diagnostics", "succeeded"),
    EventDefinition("deployment_port_update_failed", "deployment", "failed", audit_required=True),
    EventDefinition("deployment_port_update_rejected", "deployment", "rejected", audit_required=True),
    EventDefinition("deployment_port_update_succeeded", "deployment", "succeeded", audit_required=True),
    EventDefinition("dialog_sync_completed", "dialogs", "succeeded"),
    EventDefinition("dialog_sync_failed", "dialogs", "failed"),
    EventDefinition("eitaa_contact_import_item_failed", "contacts", "failed"),
    EventDefinition("eitaa_process_heartbeat_failed", "process_supervisor", "degraded"),
    EventDefinition("eitaa_process_heartbeat_recovered", "process_supervisor", "succeeded"),
    EventDefinition("eitaa_process_recovery_callback_failed", "process_supervisor", "failed"),
    EventDefinition("eitaa_process_recovery_decided", "process_supervisor", "observed", audit_required=True),
    EventDefinition("eitaa_process_restart_failed", "process_supervisor", "failed"),
    EventDefinition("eitaa_process_restart_succeeded", "process_supervisor", "succeeded"),
    EventDefinition("eitaa_process_supervisor_started", "process_supervisor", "started"),
    EventDefinition("eitaa_process_worker_fenced", "process_supervisor", "rejected", audit_required=True),
    EventDefinition("eitaa_runtime_started", "account_runtime", "started"),
    EventDefinition("eitaa_runtime_stopped", "account_runtime", "succeeded"),
    EventDefinition("eitaa_worker_heartbeat_failed", "worker_supervisor", "degraded"),
    EventDefinition("eitaa_worker_heartbeat_recovered", "worker_supervisor", "succeeded"),
    EventDefinition("eitaa_worker_lease_generation_refresh_failed", "worker_supervisor", "failed"),
    EventDefinition("eitaa_worker_stale_lease_recovered", "worker_supervisor", "succeeded", audit_required=True),
    EventDefinition("eitaa_worker_stop_reconciliation_failed", "worker_supervisor", "failed"),
    EventDefinition("eitaa_worker_supervisor_started", "worker_supervisor", "started"),
    EventDefinition("media_cache", "media", "observed", material=False),
    EventDefinition("messenger_account_onboarding_started", "account_onboarding", "started", audit_required=True),
    EventDefinition("messenger_account_onboarding_succeeded", "account_onboarding", "succeeded", audit_required=True),
    EventDefinition("messenger_account_onboarding_reused", "account_onboarding", "succeeded", audit_required=True),
    EventDefinition("messenger_account_onboarding_rejected", "account_onboarding", "rejected", audit_required=True),
    EventDefinition("message_sender_contact_enrichment_failed", "sender_enrichment", "degraded"),
    EventDefinition("message_sender_member_enrichment_failed", "sender_enrichment", "degraded"),
    EventDefinition("observability_maintenance_completed", "diagnostics", "succeeded"),
    EventDefinition("persistent_job_completion_failed", "persistent_job", "failed"),
    EventDefinition("persistent_job_lease_renew_failed", "persistent_job", "degraded"),
    EventDefinition("persistent_jobs_recovered", "persistent_job", "succeeded", audit_required=True),
    EventDefinition("provider_adapter_activation_started", "provider_extension", "started"),
    EventDefinition("provider_adapter_activation_succeeded", "provider_extension", "succeeded", audit_required=True),
    EventDefinition("provider_adapter_activation_rejected", "provider_extension", "rejected", audit_required=True),
    EventDefinition("provider_adapter_activation_failed", "provider_extension", "failed"),
    EventDefinition("provider_registry_reconciled", "provider_extension", "succeeded", audit_required=True),
    EventDefinition("provider_capability_check_rejected", "provider_extension", "rejected", audit_required=True),
    EventDefinition("provider_operation_started", "provider_operation", "started"),
    EventDefinition("provider_operation_succeeded", "provider_operation", "succeeded"),
    EventDefinition("provider_operation_rejected", "provider_operation", "rejected", audit_required=True),
    EventDefinition("provider_operation_failed", "provider_operation", "failed"),
    EventDefinition("provider_operation_uncertain", "provider_operation", "uncertain", audit_required=True),
    EventDefinition("provider_operation_idempotency_replayed", "provider_operation", "succeeded", audit_required=True),
    EventDefinition("provider_operation_idempotency_interrupted", "provider_operation", "uncertain", audit_required=True),
    EventDefinition("provider_operation_adapter_close_failed", "provider_operation", "degraded"),
    EventDefinition("read_receipt_failed", "read_receipt", "failed"),
    EventDefinition("service_credential_created", "service_credential", "succeeded", audit_required=True),
    EventDefinition("service_credential_revoked", "service_credential", "succeeded", audit_required=True),
    EventDefinition("service_credential_rotated", "service_credential", "succeeded", audit_required=True),
    EventDefinition("service_sender_profile_updated", "service_credential", "succeeded", audit_required=True),
    EventDefinition("service_sender_profile_removed", "service_credential", "succeeded", audit_required=True),
    EventDefinition("ai_connection_settings_updated", "ai_connection", "succeeded", audit_required=True),
    EventDefinition("ai_connection_probe_executed", "ai_connection", "succeeded", audit_required=True),
    EventDefinition("ai_data_policy_updated", "ai_data_policy", "succeeded", audit_required=True),
)
EVENT_CATALOG: Final[dict[str, EventDefinition]] = {item.name: item for item in _DEFINITIONS}


def event_definition(name: str) -> EventDefinition | None:
    return EVENT_CATALOG.get(str(name or "").strip().lower())


def validate_event_name(name: str) -> str:
    selected = str(name or "").strip().lower()
    if not _EVENT_NAME.fullmatch(selected):
        raise ValueError("Observability event name is invalid.")
    return selected


def validate_source(name: str) -> str:
    selected = str(name or "").strip().lower()
    if not _SOURCE_NAME.fullmatch(selected):
        raise ValueError("Observability source is invalid.")
    return selected


def normalize_level(value: str) -> str:
    selected = str(value or "info").strip().lower()
    return selected if selected in LEVELS else "info"


def normalize_result(value: str | None, *, level: str, definition: EventDefinition | None) -> str:
    selected = str(value or "").strip().lower()
    if selected in RESULTS:
        return selected
    if definition is not None:
        if level in {"error", "critical"}:
            return "failed"
        if level == "warning" and definition.default_result == "observed":
            return "degraded"
        return definition.default_result
    if level in {"error", "critical"}:
        return "failed"
    if level == "warning":
        return "degraded"
    return "observed"


def normalize_reason_code(value: object, *, event: str, level: str) -> str | None:
    selected = str(value or "").strip().lower()
    if selected and _REASON_CODE.fullmatch(selected):
        return selected
    return event if level in {"warning", "error", "critical"} else None


def normalize_correlation_id(value: object) -> str | None:
    selected = str(value or "").strip().lower().replace("-", "")
    return selected if _CORRELATION_ID.fullmatch(selected) else None


def catalog_payload() -> dict[str, object]:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "levels": sorted(LEVELS),
        "results": sorted(RESULTS),
        "events": {
            name: {
                "category": definition.category,
                "default_result": definition.default_result,
                "material": definition.material,
                "audit_required": definition.audit_required,
            }
            for name, definition in sorted(EVENT_CATALOG.items())
        },
    }

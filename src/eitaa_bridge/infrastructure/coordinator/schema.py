"""Versioned SQLite schema for the multi-provider coordinator."""

from __future__ import annotations

import hashlib

COORDINATOR_SCHEMA_VERSION = 9

SCHEMA_V1_SQL = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE app_users (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 120),
    global_role TEXT NOT NULL CHECK(global_role IN ('admin','user')),
    status TEXT NOT NULL CHECK(status IN ('active','disabled','archived')),
    auth_subject_fingerprint TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE phone_accounts (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    phone_ciphertext BLOB NOT NULL CHECK(length(phone_ciphertext) > 0),
    phone_key_version INTEGER NOT NULL CHECK(phone_key_version > 0),
    phone_fingerprint TEXT NOT NULL UNIQUE CHECK(length(phone_fingerprint) = 64),
    display_hint TEXT,
    status TEXT NOT NULL CHECK(status IN ('active','disabled','archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE phone_account_memberships (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    app_user_id TEXT NOT NULL REFERENCES app_users(id),
    phone_account_id TEXT NOT NULL REFERENCES phone_accounts(id),
    role TEXT NOT NULL CHECK(role IN ('owner','operator','viewer')),
    status TEXT NOT NULL CHECK(status IN ('active','revoked')),
    created_by_app_user_id TEXT NOT NULL REFERENCES app_users(id),
    revoked_by_app_user_id TEXT REFERENCES app_users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(app_user_id, phone_account_id)
);
CREATE INDEX idx_memberships_phone
    ON phone_account_memberships(phone_account_id, status, role);

CREATE TABLE messenger_accounts (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    phone_account_id TEXT NOT NULL REFERENCES phone_accounts(id),
    provider TEXT NOT NULL CHECK(provider IN ('eitaa','bale')),
    label TEXT CHECK(label IS NULL OR length(label) <= 120),
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN ('created','active','paused','disabled','quarantined','archived')
    ),
    desired_worker_state TEXT NOT NULL CHECK(desired_worker_state IN ('running','stopped')),
    provider_subject_fingerprint TEXT,
    capability_revision INTEGER NOT NULL DEFAULT 0 CHECK(capability_revision >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(phone_account_id, provider)
);
CREATE UNIQUE INDEX idx_messenger_provider_subject
    ON messenger_accounts(provider, provider_subject_fingerprint)
    WHERE provider_subject_fingerprint IS NOT NULL;

CREATE TABLE messenger_session_metadata (
    messenger_account_id TEXT PRIMARY KEY REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    auth_state TEXT NOT NULL CHECK(
        auth_state IN ('absent','challenge_pending','authenticated','expired','revoked','invalid')
    ),
    session_generation INTEGER NOT NULL CHECK(session_generation >= 0),
    storage_revision INTEGER NOT NULL CHECK(storage_revision > 0),
    last_validated_at TEXT,
    last_auth_transition_at TEXT NOT NULL,
    safe_reason_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE messenger_capabilities (
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('supported','unsupported','unknown','restricted')),
    reason_code TEXT,
    constraints_json TEXT,
    revision INTEGER NOT NULL CHECK(revision >= 0),
    observed_at TEXT NOT NULL,
    PRIMARY KEY(messenger_account_id, capability)
);

CREATE TABLE worker_instances (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id),
    generation INTEGER NOT NULL CHECK(generation > 0),
    runtime_state TEXT NOT NULL CHECK(
        runtime_state IN ('starting','ready','busy','rate_limited','stopping','stopped','crashed')
    ),
    process_id INTEGER,
    started_at TEXT NOT NULL,
    last_heartbeat_at TEXT,
    retry_not_before TEXT,
    stopped_at TEXT,
    exit_code INTEGER,
    safe_reason_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(messenger_account_id, generation)
);
CREATE INDEX idx_worker_account_state
    ON worker_instances(messenger_account_id, runtime_state, generation);

CREATE TABLE local_contacts (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    organization TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    sendable INTEGER NOT NULL DEFAULT 1 CHECK(sendable IN (0,1)),
    opt_out INTEGER NOT NULL DEFAULT 0 CHECK(opt_out IN (0,1)),
    opt_out_reason_code TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE local_contact_phones (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    local_contact_id TEXT NOT NULL REFERENCES local_contacts(id) ON DELETE CASCADE,
    phone_ciphertext BLOB NOT NULL CHECK(length(phone_ciphertext) > 0),
    phone_key_version INTEGER NOT NULL CHECK(phone_key_version > 0),
    phone_fingerprint TEXT NOT NULL UNIQUE CHECK(length(phone_fingerprint) = 64),
    display_hint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE account_contact_bindings (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    local_contact_id TEXT NOT NULL REFERENCES local_contacts(id) ON DELETE CASCADE,
    worker_binding_id TEXT NOT NULL CHECK(length(worker_binding_id) = 36),
    provider_subject_fingerprint TEXT,
    reachability TEXT NOT NULL CHECK(
        reachability IN ('unknown','reachable','unreachable','blocked')
    ),
    last_resolved_at TEXT,
    safe_reason_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(messenger_account_id, local_contact_id)
);
CREATE UNIQUE INDEX idx_binding_provider_subject
    ON account_contact_bindings(messenger_account_id, provider_subject_fingerprint)
    WHERE provider_subject_fingerprint IS NOT NULL;

CREATE TABLE recipient_capabilities (
    account_contact_binding_id TEXT NOT NULL
        REFERENCES account_contact_bindings(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('supported','unsupported','unknown','restricted')),
    safe_reason_code TEXT,
    observed_at TEXT NOT NULL,
    expires_at TEXT,
    PRIMARY KEY(account_contact_binding_id, capability)
);

CREATE TABLE operation_jobs (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    actor_app_user_id TEXT REFERENCES app_users(id),
    phone_account_id TEXT NOT NULL REFERENCES phone_accounts(id),
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id),
    provider TEXT NOT NULL CHECK(provider IN ('eitaa','bale')),
    operation TEXT NOT NULL,
    status TEXT NOT NULL CHECK(
        status IN ('pending','leased','running','succeeded','failed','cancelled','uncertain')
    ),
    idempotency_key TEXT NOT NULL,
    safe_payload_ref TEXT,
    correlation_id TEXT NOT NULL CHECK(length(correlation_id) = 36),
    scheduled_at TEXT,
    lease_owner TEXT,
    lease_generation INTEGER,
    lease_expires_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(messenger_account_id, operation, idempotency_key)
);
CREATE INDEX idx_jobs_account_status
    ON operation_jobs(messenger_account_id, status, scheduled_at);

CREATE TABLE job_attempts (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    job_id TEXT NOT NULL REFERENCES operation_jobs(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
    worker_id TEXT CHECK(worker_id IS NULL OR length(worker_id) = 36),
    worker_generation INTEGER,
    result TEXT CHECK(result IN ('succeeded','failed','cancelled','uncertain')),
    error_class TEXT,
    error_code TEXT,
    retry_after_ms INTEGER CHECK(retry_after_ms IS NULL OR retry_after_ms >= 0),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, attempt_number)
);

CREATE TABLE app_integrations (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    integration_type TEXT NOT NULL CHECK(integration_type IN ('wordpress')),
    integration_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','disabled','archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(integration_type, integration_key)
);

CREATE TABLE app_integration_memberships (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    app_user_id TEXT NOT NULL REFERENCES app_users(id),
    integration_id TEXT NOT NULL REFERENCES app_integrations(id),
    role TEXT NOT NULL CHECK(role IN ('owner','operator','viewer')),
    status TEXT NOT NULL CHECK(status IN ('active','revoked')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(app_user_id, integration_id)
);

CREATE TABLE publishing_compositions (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    app_user_id TEXT NOT NULL REFERENCES app_users(id),
    source_messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id),
    source_message_ref_hash TEXT NOT NULL,
    target_integration_id TEXT NOT NULL REFERENCES app_integrations(id),
    composition_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','committed','archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(
        app_user_id,
        source_messenger_account_id,
        target_integration_id,
        composition_key
    )
);

CREATE TABLE migration_runs (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    migration_kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK(
        status IN ('staging','verified','activated','failed','rolled_back')
    ),
    backup_name TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL CHECK(length(source_manifest_sha256) = 64),
    source_file_count INTEGER NOT NULL CHECK(source_file_count >= 0),
    source_total_bytes INTEGER NOT NULL CHECK(source_total_bytes >= 0),
    messenger_account_id TEXT REFERENCES messenger_accounts(id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    safe_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    schema_version INTEGER NOT NULL CHECK(schema_version = 1),
    at TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK(actor_type IN ('app_user','system')),
    actor_app_user_id TEXT REFERENCES app_users(id),
    actor_global_role TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    phone_account_id TEXT REFERENCES phone_accounts(id),
    messenger_account_id TEXT REFERENCES messenger_accounts(id),
    provider TEXT CHECK(provider IS NULL OR provider IN ('eitaa','bale')),
    result TEXT NOT NULL,
    reason_code TEXT,
    request_id TEXT,
    correlation_id TEXT,
    confirmation_id TEXT,
    safe_metadata_json TEXT NOT NULL DEFAULT '{}',
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE CHECK(length(event_hash) = 64)
);
CREATE INDEX idx_audit_at ON audit_events(at, id);
CREATE INDEX idx_audit_account ON audit_events(messenger_account_id, at);

CREATE TRIGGER prevent_last_owner_delete
BEFORE DELETE ON phone_account_memberships
WHEN OLD.role = 'owner'
 AND OLD.status = 'active'
 AND EXISTS (
     SELECT 1 FROM phone_accounts
     WHERE id = OLD.phone_account_id AND status != 'archived'
 )
 AND NOT EXISTS (
     SELECT 1 FROM phone_account_memberships
     WHERE phone_account_id = OLD.phone_account_id
       AND role = 'owner' AND status = 'active' AND id != OLD.id
 )
BEGIN
    SELECT RAISE(ABORT, 'last_active_owner_required');
END;

CREATE TRIGGER prevent_last_owner_update
BEFORE UPDATE OF role, status ON phone_account_memberships
WHEN OLD.role = 'owner'
 AND OLD.status = 'active'
 AND (NEW.role != 'owner' OR NEW.status != 'active')
 AND EXISTS (
     SELECT 1 FROM phone_accounts
     WHERE id = OLD.phone_account_id AND status != 'archived'
 )
 AND NOT EXISTS (
     SELECT 1 FROM phone_account_memberships
     WHERE phone_account_id = OLD.phone_account_id
       AND role = 'owner' AND status = 'active' AND id != OLD.id
 )
BEGIN
    SELECT RAISE(ABORT, 'last_active_owner_required');
END;

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events_are_append_only');
END;

CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events_are_append_only');
END;
"""

SCHEMA_V2_SQL = """
CREATE TABLE app_user_credentials (
    app_user_id TEXT PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    credential_kind TEXT NOT NULL CHECK(credential_kind = 'local_password'),
    password_scheme TEXT NOT NULL CHECK(password_scheme = 'pbkdf2_sha256'),
    password_iterations INTEGER NOT NULL CHECK(
        password_iterations BETWEEN 600000 AND 10000000
    ),
    password_salt BLOB NOT NULL CHECK(length(password_salt) BETWEEN 16 AND 64),
    password_digest BLOB NOT NULL CHECK(length(password_digest) = 32),
    credential_version INTEGER NOT NULL CHECK(credential_version > 0),
    password_changed_at TEXT NOT NULL,
    last_authenticated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE app_user_sessions (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    app_user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE CHECK(length(token_hash) = 64),
    csrf_token_hash TEXT NOT NULL CHECK(length(csrf_token_hash) = 64),
    status TEXT NOT NULL CHECK(status IN ('active','revoked','expired')),
    client_kind TEXT NOT NULL CHECK(client_kind IN ('electron','browser','api','test')),
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    idle_expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked_at TEXT,
    safe_reason_code TEXT
);
CREATE INDEX idx_app_user_sessions_user_status
    ON app_user_sessions(app_user_id, status, absolute_expires_at);

CREATE TABLE app_auth_throttles (
    subject_fingerprint TEXT PRIMARY KEY CHECK(length(subject_fingerprint) = 64),
    failure_count INTEGER NOT NULL CHECK(failure_count >= 0),
    window_started_at TEXT NOT NULL,
    blocked_until TEXT,
    last_failed_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TRIGGER app_user_credentials_require_subject
BEFORE INSERT ON app_user_credentials
WHEN (
    SELECT auth_subject_fingerprint FROM app_users WHERE id = NEW.app_user_id
) IS NULL
BEGIN
    SELECT RAISE(ABORT, 'app_user_auth_subject_required');
END;

CREATE TRIGGER prevent_last_active_admin_delete
BEFORE DELETE ON app_users
WHEN OLD.global_role = 'admin'
 AND OLD.status = 'active'
 AND NOT EXISTS (
     SELECT 1 FROM app_users
     WHERE id != OLD.id AND global_role = 'admin' AND status = 'active'
 )
BEGIN
    SELECT RAISE(ABORT, 'last_active_admin_required');
END;

CREATE TRIGGER prevent_last_active_admin_update
BEFORE UPDATE OF global_role, status ON app_users
WHEN OLD.global_role = 'admin'
 AND OLD.status = 'active'
 AND (NEW.global_role != 'admin' OR NEW.status != 'active')
 AND NOT EXISTS (
     SELECT 1 FROM app_users
     WHERE id != OLD.id AND global_role = 'admin' AND status = 'active'
 )
BEGIN
    SELECT RAISE(ABORT, 'last_active_admin_required');
END;
"""

SCHEMA_V3_SQL = """
ALTER TABLE operation_jobs ADD COLUMN recipient_ref_hash TEXT
    CHECK(recipient_ref_hash IS NULL OR length(recipient_ref_hash) = 64);
ALTER TABLE operation_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0
    CHECK(attempt_count >= 0);
ALTER TABLE operation_jobs ADD COLUMN cancel_requested_at TEXT;
ALTER TABLE operation_jobs ADD COLUMN cancelled_at TEXT;
ALTER TABLE operation_jobs ADD COLUMN last_error_class TEXT;
ALTER TABLE operation_jobs ADD COLUMN last_error_code TEXT;

CREATE TABLE operation_job_recipients (
    job_id TEXT NOT NULL REFERENCES operation_jobs(id) ON DELETE CASCADE,
    recipient_ref_hash TEXT NOT NULL CHECK(length(recipient_ref_hash) = 64),
    status TEXT NOT NULL CHECK(
        status IN ('pending','running','succeeded','failed','cancelled','uncertain')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    last_error_class TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(job_id, recipient_ref_hash)
);
CREATE INDEX idx_job_recipients_status
    ON operation_job_recipients(job_id,status,recipient_ref_hash);
"""

SCHEMA_V4_SQL = """
CREATE TABLE account_execution_limits (
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK(provider IN ('eitaa','bale')),
    operation_scope TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000),
    refill_per_second REAL NOT NULL CHECK(refill_per_second > 0),
    available_tokens REAL NOT NULL CHECK(available_tokens >= 0),
    last_refill_at TEXT NOT NULL,
    retry_not_before TEXT,
    circuit_state TEXT NOT NULL CHECK(circuit_state IN ('closed','open','half_open')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_failures >= 0),
    circuit_open_until TEXT,
    half_open_claim_id TEXT CHECK(half_open_claim_id IS NULL OR length(half_open_claim_id)=36),
    last_error_class TEXT CHECK(
        last_error_class IS NULL OR last_error_class IN (
            'transient','auth','privacy','permanent','uncertain','internal'
        )
    ),
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(messenger_account_id,operation_scope)
);
CREATE INDEX idx_account_execution_retry
    ON account_execution_limits(retry_not_before,circuit_open_until,messenger_account_id);
"""

SCHEMA_V5_SQL = """
CREATE TABLE job_leases (
    id TEXT PRIMARY KEY CHECK(length(id)=36),
    job_id TEXT NOT NULL REFERENCES operation_jobs(id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL CHECK(length(worker_id)=36),
    worker_generation INTEGER NOT NULL CHECK(worker_generation > 0),
    correlation_id TEXT NOT NULL CHECK(length(correlation_id)=36),
    status TEXT NOT NULL CHECK(status IN ('active','released','expired','lost')),
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    released_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_job_leases_one_active
    ON job_leases(job_id) WHERE status='active';
CREATE INDEX idx_job_leases_worker
    ON job_leases(worker_id,worker_generation,status,expires_at);

ALTER TABLE job_attempts ADD COLUMN lease_id TEXT REFERENCES job_leases(id);
ALTER TABLE job_attempts ADD COLUMN correlation_id TEXT
    CHECK(correlation_id IS NULL OR length(correlation_id)=36);
CREATE UNIQUE INDEX idx_job_attempt_correlation
    ON job_attempts(correlation_id) WHERE correlation_id IS NOT NULL;
"""

SCHEMA_V6_SQL = """
CREATE TABLE provider_registrations (
    provider TEXT PRIMARY KEY CHECK(
        length(provider) BETWEEN 2 AND 32
        AND provider=lower(provider)
        AND substr(provider,1,1) GLOB '[a-z]'
        AND provider NOT GLOB '*[^a-z0-9_]*'
    ),
    display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 64),
    account_kind TEXT NOT NULL CHECK(account_kind IN ('personal','bot','service','test','legacy')),
    implementation_state TEXT NOT NULL CHECK(
        implementation_state IN ('scaffold','implemented','contract_verified','live_accepted')
    ),
    authorization_basis TEXT CHECK(
        authorization_basis IS NULL OR authorization_basis IN (
            'official_api','written_permission','existing_accepted_integration','test_only'
        )
    ),
    configured INTEGER NOT NULL CHECK(configured IN (0,1)),
    runtime_enabled INTEGER NOT NULL CHECK(runtime_enabled IN (0,1)),
    onboarding_enabled INTEGER NOT NULL CHECK(onboarding_enabled IN (0,1)),
    account_identity_kind TEXT,
    auth_steps_json TEXT NOT NULL DEFAULT '[]',
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    catalog_visible INTEGER NOT NULL CHECK(catalog_visible IN (0,1)),
    extension_api_version INTEGER NOT NULL CHECK(extension_api_version > 0),
    status TEXT NOT NULL CHECK(status IN ('active','disabled','retired')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO provider_registrations(
    provider,display_name,account_kind,implementation_state,authorization_basis,
    configured,runtime_enabled,onboarding_enabled,account_identity_kind,
    auth_steps_json,capabilities_json,catalog_visible,extension_api_version,status,
    created_at,updated_at
) VALUES
(
    'eitaa','ایتا','personal','live_accepted','existing_accepted_integration',
    1,1,1,'phone_e164',
    '["identity","challenge","second_factor_optional"]',
    '["auth.logout","auth.phone","contacts.read","contacts.write","dialogs.read","history.read","media.read","media.send","messages.send","updates.live"]',
    1,1,'active',strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now')
),
(
    'bale','بله','personal','scaffold',NULL,
    0,0,0,NULL,'[]','[]',1,1,'active',
    strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now')
);

CREATE TABLE messenger_accounts_v6 (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    phone_account_id TEXT NOT NULL REFERENCES phone_accounts(id),
    provider TEXT NOT NULL REFERENCES provider_registrations(provider),
    label TEXT CHECK(label IS NULL OR length(label) <= 120),
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN ('created','active','paused','disabled','quarantined','archived')
    ),
    desired_worker_state TEXT NOT NULL CHECK(desired_worker_state IN ('running','stopped')),
    provider_subject_fingerprint TEXT,
    capability_revision INTEGER NOT NULL DEFAULT 0 CHECK(capability_revision >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(phone_account_id, provider)
);
INSERT INTO messenger_accounts_v6 SELECT * FROM messenger_accounts;
DROP TABLE messenger_accounts;
ALTER TABLE messenger_accounts_v6 RENAME TO messenger_accounts;
CREATE UNIQUE INDEX idx_messenger_provider_subject
    ON messenger_accounts(provider, provider_subject_fingerprint)
    WHERE provider_subject_fingerprint IS NOT NULL;

CREATE TABLE operation_jobs_v6 (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    actor_app_user_id TEXT REFERENCES app_users(id),
    phone_account_id TEXT NOT NULL REFERENCES phone_accounts(id),
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id),
    provider TEXT NOT NULL REFERENCES provider_registrations(provider),
    operation TEXT NOT NULL,
    status TEXT NOT NULL CHECK(
        status IN ('pending','leased','running','succeeded','failed','cancelled','uncertain')
    ),
    idempotency_key TEXT NOT NULL,
    safe_payload_ref TEXT,
    correlation_id TEXT NOT NULL CHECK(length(correlation_id) = 36),
    scheduled_at TEXT,
    lease_owner TEXT,
    lease_generation INTEGER,
    lease_expires_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    recipient_ref_hash TEXT CHECK(recipient_ref_hash IS NULL OR length(recipient_ref_hash) = 64),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    cancel_requested_at TEXT,
    cancelled_at TEXT,
    last_error_class TEXT,
    last_error_code TEXT,
    UNIQUE(messenger_account_id, operation, idempotency_key)
);
INSERT INTO operation_jobs_v6 SELECT * FROM operation_jobs;
DROP TABLE operation_jobs;
ALTER TABLE operation_jobs_v6 RENAME TO operation_jobs;
CREATE INDEX idx_jobs_account_status
    ON operation_jobs(messenger_account_id, status, scheduled_at);

DROP TRIGGER audit_events_no_update;
DROP TRIGGER audit_events_no_delete;
CREATE TABLE audit_events_v6 (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    schema_version INTEGER NOT NULL CHECK(schema_version = 1),
    at TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK(actor_type IN ('app_user','system')),
    actor_app_user_id TEXT REFERENCES app_users(id),
    actor_global_role TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    phone_account_id TEXT REFERENCES phone_accounts(id),
    messenger_account_id TEXT REFERENCES messenger_accounts(id),
    provider TEXT REFERENCES provider_registrations(provider),
    result TEXT NOT NULL,
    reason_code TEXT,
    request_id TEXT,
    correlation_id TEXT,
    confirmation_id TEXT,
    safe_metadata_json TEXT NOT NULL DEFAULT '{}',
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE CHECK(length(event_hash) = 64)
);
INSERT INTO audit_events_v6 SELECT * FROM audit_events ORDER BY rowid;
DROP TABLE audit_events;
ALTER TABLE audit_events_v6 RENAME TO audit_events;
CREATE INDEX idx_audit_at ON audit_events(at, id);
CREATE INDEX idx_audit_account ON audit_events(messenger_account_id, at);
CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events_are_append_only');
END;
CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events_are_append_only');
END;

CREATE TABLE account_execution_limits_v6 (
    messenger_account_id TEXT NOT NULL REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    provider TEXT NOT NULL REFERENCES provider_registrations(provider),
    operation_scope TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000),
    refill_per_second REAL NOT NULL CHECK(refill_per_second > 0),
    available_tokens REAL NOT NULL CHECK(available_tokens >= 0),
    last_refill_at TEXT NOT NULL,
    retry_not_before TEXT,
    circuit_state TEXT NOT NULL CHECK(circuit_state IN ('closed','open','half_open')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_failures >= 0),
    circuit_open_until TEXT,
    half_open_claim_id TEXT CHECK(half_open_claim_id IS NULL OR length(half_open_claim_id)=36),
    last_error_class TEXT CHECK(
        last_error_class IS NULL OR last_error_class IN (
            'transient','auth','privacy','permanent','uncertain','internal'
        )
    ),
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(messenger_account_id,operation_scope)
);
INSERT INTO account_execution_limits_v6 SELECT * FROM account_execution_limits;
DROP TABLE account_execution_limits;
ALTER TABLE account_execution_limits_v6 RENAME TO account_execution_limits;
CREATE INDEX idx_account_execution_retry
    ON account_execution_limits(retry_not_before,circuit_open_until,messenger_account_id);

CREATE TRIGGER operation_jobs_provider_scope_insert
BEFORE INSERT ON operation_jobs
WHEN NEW.provider != (SELECT provider FROM messenger_accounts WHERE id=NEW.messenger_account_id)
BEGIN
    SELECT RAISE(ABORT, 'operation_job_provider_scope_mismatch');
END;
CREATE TRIGGER operation_jobs_provider_scope_update
BEFORE UPDATE OF provider,messenger_account_id ON operation_jobs
WHEN NEW.provider != (SELECT provider FROM messenger_accounts WHERE id=NEW.messenger_account_id)
BEGIN
    SELECT RAISE(ABORT, 'operation_job_provider_scope_mismatch');
END;
CREATE TRIGGER account_execution_provider_scope_insert
BEFORE INSERT ON account_execution_limits
WHEN NEW.provider != (SELECT provider FROM messenger_accounts WHERE id=NEW.messenger_account_id)
BEGIN
    SELECT RAISE(ABORT, 'account_execution_provider_scope_mismatch');
END;
CREATE TRIGGER account_execution_provider_scope_update
BEFORE UPDATE OF provider,messenger_account_id ON account_execution_limits
WHEN NEW.provider != (SELECT provider FROM messenger_accounts WHERE id=NEW.messenger_account_id)
BEGIN
    SELECT RAISE(ABORT, 'account_execution_provider_scope_mismatch');
END;
"""

SCHEMA_V7_SQL = """
CREATE TABLE provider_operation_receipts (
    messenger_account_id TEXT NOT NULL
        REFERENCES messenger_accounts(id) ON DELETE CASCADE,
    actor_app_user_id TEXT NOT NULL REFERENCES app_users(id),
    provider TEXT NOT NULL REFERENCES provider_registrations(provider),
    operation TEXT NOT NULL CHECK(
        operation IN ('messages.send_text','contacts.upsert')
    ),
    idempotency_key TEXT NOT NULL CHECK(
        length(idempotency_key) BETWEEN 16 AND 128
    ),
    request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint) = 64),
    claim_deadline_unix_ms INTEGER NOT NULL CHECK(claim_deadline_unix_ms > 0),
    outcome TEXT NOT NULL CHECK(
        outcome IN ('in_progress','succeeded','uncertain')
    ),
    result_reference TEXT CHECK(
        result_reference IS NULL OR length(result_reference) BETWEEN 1 AND 256
    ),
    contact_created INTEGER CHECK(contact_created IS NULL OR contact_created IN (0,1)),
    safe_reason_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY(messenger_account_id,operation,idempotency_key),
    CHECK(
        (outcome='in_progress' AND result_reference IS NULL
         AND contact_created IS NULL AND completed_at IS NULL)
        OR
        (operation='messages.send_text' AND outcome!='in_progress'
         AND contact_created IS NULL AND completed_at IS NOT NULL
         AND (outcome='uncertain' OR result_reference IS NOT NULL))
        OR
        (operation='contacts.upsert' AND outcome='succeeded'
         AND result_reference IS NOT NULL AND contact_created IN (0,1)
         AND completed_at IS NOT NULL)
        OR
        (operation='contacts.upsert' AND outcome='uncertain'
         AND result_reference IS NULL AND contact_created IS NULL
         AND completed_at IS NOT NULL)
    )
);
CREATE INDEX idx_provider_receipts_actor
    ON provider_operation_receipts(actor_app_user_id,created_at);

CREATE TRIGGER provider_operation_receipts_provider_scope_insert
BEFORE INSERT ON provider_operation_receipts
WHEN NEW.provider != (
    SELECT provider FROM messenger_accounts WHERE id=NEW.messenger_account_id
)
BEGIN
    SELECT RAISE(ABORT, 'provider_operation_receipt_scope_mismatch');
END;

"""

SCHEMA_V8_SQL = """
CREATE TABLE service_credentials (
    id TEXT PRIMARY KEY CHECK(length(id) = 36),
    service_name TEXT NOT NULL UNIQUE CHECK(length(service_name) BETWEEN 3 AND 64),
    token_hash TEXT NOT NULL,
    salt BLOB NOT NULL,
    allowed_providers TEXT NOT NULL,
    allowed_messenger_account_ids TEXT,
    scopes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revoked_at TEXT,
    created_by_app_user_id TEXT NOT NULL REFERENCES app_users(id),
    description TEXT NOT NULL
);
"""

SCHEMA_V1_CHECKSUM = hashlib.sha256(SCHEMA_V1_SQL.encode("utf-8")).hexdigest()
SCHEMA_V2_CHECKSUM = hashlib.sha256(SCHEMA_V2_SQL.encode("utf-8")).hexdigest()
SCHEMA_V3_CHECKSUM = hashlib.sha256(SCHEMA_V3_SQL.encode("utf-8")).hexdigest()
SCHEMA_V4_CHECKSUM = hashlib.sha256(SCHEMA_V4_SQL.encode("utf-8")).hexdigest()
SCHEMA_V5_CHECKSUM = hashlib.sha256(SCHEMA_V5_SQL.encode("utf-8")).hexdigest()
SCHEMA_V6_CHECKSUM = hashlib.sha256(SCHEMA_V6_SQL.encode("utf-8")).hexdigest()
SCHEMA_V7_CHECKSUM = hashlib.sha256(SCHEMA_V7_SQL.encode("utf-8")).hexdigest()
SCHEMA_V8_CHECKSUM = hashlib.sha256(SCHEMA_V8_SQL.encode("utf-8")).hexdigest()

SCHEMA_V9_SQL = """
ALTER TABLE provider_operation_receipts ADD COLUMN service_credential_id TEXT;
"""

SCHEMA_V9_CHECKSUM = hashlib.sha256(SCHEMA_V9_SQL.encode("utf-8")).hexdigest()
SCHEMA_CHECKSUMS = {
    1: SCHEMA_V1_CHECKSUM,
    2: SCHEMA_V2_CHECKSUM,
    3: SCHEMA_V3_CHECKSUM,
    4: SCHEMA_V4_CHECKSUM,
    5: SCHEMA_V5_CHECKSUM,
    6: SCHEMA_V6_CHECKSUM,
    7: SCHEMA_V7_CHECKSUM,
    8: SCHEMA_V8_CHECKSUM,
    9: SCHEMA_V9_CHECKSUM,
}
SCHEMA_CHECKSUM = SCHEMA_V9_CHECKSUM


def initial_schema_script() -> str:
    return (
        "PRAGMA foreign_keys=OFF;\nBEGIN IMMEDIATE;\n"
        + SCHEMA_V1_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"1,'{SCHEMA_V1_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V2_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"2,'{SCHEMA_V2_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V3_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"3,'{SCHEMA_V3_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V4_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"4,'{SCHEMA_V4_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V5_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"5,'{SCHEMA_V5_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V6_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"6,'{SCHEMA_V6_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V7_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"7,'{SCHEMA_V7_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V8_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"8,'{SCHEMA_V8_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + SCHEMA_V9_SQL
        + "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES("
        + f"9,'{SCHEMA_V9_CHECKSUM}',"
        + "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
        + f"PRAGMA user_version={COORDINATOR_SCHEMA_VERSION};\n"
        + "COMMIT;\nPRAGMA foreign_keys=ON;\n"
    )


def upgrade_schema_script(from_version: int) -> str:
    if from_version not in {1, 2, 3, 4, 5, 6, 7, 8}:
        raise ValueError("unsupported coordinator schema upgrade")
    parts = ["PRAGMA foreign_keys=OFF;\nBEGIN IMMEDIATE;\n"]
    if from_version == 1:
        parts.extend(
            [
                SCHEMA_V2_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"2,'{SCHEMA_V2_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 2:
        parts.extend(
            [
                SCHEMA_V3_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"3,'{SCHEMA_V3_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 3:
        parts.extend(
            [
                SCHEMA_V4_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"4,'{SCHEMA_V4_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 4:
        parts.extend(
            [
                SCHEMA_V5_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"5,'{SCHEMA_V5_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 5:
        parts.extend(
            [
                SCHEMA_V6_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"6,'{SCHEMA_V6_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 6:
        parts.extend(
            [
                SCHEMA_V7_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"7,'{SCHEMA_V7_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    if from_version <= 7:
        parts.extend(
            [
                SCHEMA_V8_SQL,
                "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
                f"8,'{SCHEMA_V8_CHECKSUM}',",
                "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            ]
        )
    parts.extend(
        [
            SCHEMA_V9_SQL,
            "\nINSERT INTO schema_migrations(version,checksum,applied_at) VALUES(",
            f"9,'{SCHEMA_V9_CHECKSUM}',",
            "strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n",
            "PRAGMA user_version=9;\n",
            "COMMIT;\n",
            "PRAGMA foreign_keys=ON;\n",
        ]
    )
    return "".join(parts)


REQUIRED_TABLES_V1 = frozenset(
    {
        "schema_migrations",
        "app_users",
        "phone_accounts",
        "phone_account_memberships",
        "messenger_accounts",
        "messenger_session_metadata",
        "messenger_capabilities",
        "worker_instances",
        "local_contacts",
        "local_contact_phones",
        "account_contact_bindings",
        "recipient_capabilities",
        "operation_jobs",
        "job_attempts",
        "app_integrations",
        "app_integration_memberships",
        "publishing_compositions",
        "migration_runs",
        "audit_events",
    }
)

REQUIRED_TABLES_V2 = REQUIRED_TABLES_V1 | frozenset(
    {
        "app_user_credentials",
        "app_user_sessions",
        "app_auth_throttles",
    }
)

REQUIRED_TABLES_V3 = REQUIRED_TABLES_V2 | frozenset({"operation_job_recipients"})

REQUIRED_TABLES_V4 = REQUIRED_TABLES_V3 | frozenset({"account_execution_limits"})

REQUIRED_TABLES_V5 = REQUIRED_TABLES_V4 | frozenset({"job_leases"})

REQUIRED_TABLES_V6 = REQUIRED_TABLES_V5 | frozenset({"provider_registrations"})

REQUIRED_TABLES_V7 = REQUIRED_TABLES_V6 | frozenset({"provider_operation_receipts"})

REQUIRED_TABLES = REQUIRED_TABLES_V7 | frozenset({"service_credentials"})

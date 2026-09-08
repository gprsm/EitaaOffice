# Security and diagnostics

Bridge diagnostics are component-separated JSONL files. Each run has a manifest that explicitly states the excluded data classes.

Redacted data includes:

- credentials, usernames, Application Passwords, Authorization headers, and cookies;
- Eitaa token, IMEI, access hash, session material, phone numbers, and SQLite contents;
- post/message content, titles, excerpts, captions, descriptions, and alternative text;
- local media filenames and file bytes;
- raw request and response bodies.

Media diagnostics may record only non-content properties such as byte count, suffix, MIME type, selected site, method, endpoint path, HTTP status, and created Media ID.

Exceptions use stable safe error codes. WordPress response bodies are never copied into exception messages or diagnostics. Only HTTP status, method, endpoint path, retry count, and a sanitized WordPress error code may be recorded.

For troubleshooting, share only the exact component file named by the error. Never share an entire diagnostics directory.

Release archives are allowlist-only. Live `.env`/`bridge.json`, sessions, databases, runtime logs, diagnostics, backups, prompt/probe/scratch artifacts, internal handoffs and quarantined provider clients are never selected. Every archive is reopened and checked for canonical non-traversing names, case-insensitive uniqueness, manifest/hash consistency, size bounds and high-confidence private-key/JWT patterns. The external receipt may contain hashes and counts only; it must not contain file payloads, credentials, phone numbers or private paths.

The shareable self-contained Windows Setup follows the same private-state boundary. It embeds only sample configuration, operator scripts, the validated UI, offline wheels, installed runtime packages and an application-local Python runtime. Copying a live project directory is not a supported transfer mechanism; operational state moves only through the separately reviewed Backup/Restore workflow.

Packaged Office installations are fail-closed behind offline device activation. The customer artifact contains Ed25519 public verification material only. The private issuing key and owner-side tool are excluded from every allowlisted release. A request code contains only a versioned hash of normalized device components. The signed activation is protected at rest with user-scoped Windows DPAPI and rechecked before Config, Coordinator or Provider startup.

DPAPI confidentiality and a digital signature prevent accidental disclosure, editing and ordinary file copying; they do not make locally executed Python impossible to reverse engineer or patch. Production hardening still requires a private Production key, offline key backup, code-signing, clean-machine acceptance and an explicit key-rotation/revocation process.

Internal Windows code signing is separate from license issuance. The Authenticode RSA private key is created as non-exportable in the build owner's `Cert:\CurrentUser\My` store; no PFX or private key is written to the repository or delivery. The delivery trust bundle contains only the public CER, pinned thumbprint metadata and an explicit trust installer. Setup never silently imports its own publisher into Root or TrustedPublisher. A self-signed signature provides integrity and publisher continuity only after deliberate local trust; it does not create public CA or SmartScreen reputation.

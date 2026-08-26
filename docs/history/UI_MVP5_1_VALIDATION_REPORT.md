# Eitaa Bridge UI MVP 5.1 Validation Report

## Release identity

- Product: `0.7.0-ui-mvp5.1`
- Python package: `0.7.0.dev7`
- UI package: `0.7.5`
- Core product/package: `0.6.0-core7.4.1` / `0.6.0.dev15`

## Fixed failure mode

UI MVP 5 treated every exception raised while opening an existing Core session as `authenticated=false`. This could incorrectly route the user to the login screen even though the session file remained present. The Electron launcher also started the local API with `stdio=ignore`, preventing diagnosis of the underlying process failure. A new login attempt could therefore return only `api_internal_error` and the generic message `The local API request failed unexpectedly.`

UI MVP 5.1:

- distinguishes a missing session from a present-but-temporarily-unavailable session;
- presents a recovery screen instead of a login form for the latter state;
- supervises, restarts, and retries the local API once;
- persists API/Desktop logs under `runtime/logs`;
- wraps native authentication failures as typed safe errors;
- preserves explicit logout as the only action that archives the session.

The exact exception on the user's Windows installation cannot be reconstructed from UI MVP 5 because that build discarded API stdout/stderr. UI MVP 5.1 preserves the evidence if the underlying failure recurs.

## Automated validation

- Source test suite: `120 passed`
- Installed-wheel test suite in a clean virtual environment: `120 passed`
- TypeScript strict check: passed
- Vite production build: passed
- Electron main/preload syntax check: passed
- Public npm registry scan: no internal OpenAI registry references
- Direct SQLite imports in Bridge: none
- Direct SQL statements in Bridge: none
- Internal Core package imports in Bridge: none

## Immutable Core verification

- Core wheel SHA-256: `0e16dac9fbb1d1994301012f36f5a83286ce56631cb0d22f0425a56f87d8a092`
- Bridge wheel SHA-256: `0ec2a94831bd05540ebd275280eb3d2d4de058da519e3bfe59359322c35530cd`

Core 7.4.1 was not modified.

## Runtime files added

- `runtime/logs/api.log`
- `runtime/logs/desktop.log`
- `open_runtime_logs.bat`
- `run_auth_status.bat`

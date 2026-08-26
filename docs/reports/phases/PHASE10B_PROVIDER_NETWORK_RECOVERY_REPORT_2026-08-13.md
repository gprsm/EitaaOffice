# Phase 10-B Provider Network Recovery Report — 2026-08-13

## Scope

This report records the safe diagnosis and correction of the Eitaa login
request-code startup failure. It intentionally contains no phone number, OTP,
password, provider token, or protected identity material.

## Diagnosis

- The protected phone identity recovery had already completed successfully.
- The account remained in `auth_state=absent`; no provider challenge was active.
- Three prior request-code attempts failed with `NetworkError` before a challenge
  was issued.
- DNS resolution for the configured Eitaa API and media hosts succeeded.
- TLS sockets from the restricted test process were denied by Windows with
  `PermissionError`, `winerror=10013`, `errno=13`.
- A read-only TLS probe with authorized outbound access succeeded for both
  configured Eitaa hosts.
- The former launch command loaded the installed package copy rather than the
  current project source tree.

## Corrections

- Added explicit `NetworkError` handling for account-scoped and legacy login.
- The API now returns the actionable error code
  `auth_provider_network_unreachable` and a Persian network-access message.
- Account-scoped failures are audited as
  `eitaa.auth.request_code.failed/provider_network_unreachable`.
- Error responses, audit metadata, and runtime logs retain only the exception
  type; provider endpoint details and phone identity are not exposed.
- The old local listener was identified by exact PID and command line, stopped,
  and replaced with the current project source running on Loopback with the
  authorized outbound network capability.

## Verification

- Focused Python tests: `45 passed`.
- New tests cover both legacy and account-scoped network failure paths.
- Secret-absence assertions cover the API response, audit metadata, and worker
  log.
- Live health endpoint: `ok=true`.
- Live readiness endpoint: `ok=true`, `status=ready`.
- Live account state after restart: `auth_state=absent`, no pending challenge.

## Remaining live acceptance

The operator must request the code once in the local UI and enter any OTP or
two-factor password only in that UI. Phase 10-B is not considered fully accepted
until the resulting provider challenge and authenticated session transitions are
verified through safe status and audit metadata.

# Phase 10-B Challenge-ID Recovery Report — 2026-08-13

## Scope

This report records the correction and verification of the provider login UI
failure reported after the operator entered the one-time code. No phone number,
OTP, password, provider token, or challenge identifier is recorded here.

## Finding

- The provider request-code call succeeded and created an account-scoped login
  challenge.
- The UI displayed the code step but sent only the OTP field to
  `/api/v1/auth/submit-code`.
- The required `challenge_id` returned by the request-code response was not held
  in component state.
- The password step had the same omission.
- The API correctly rejected the incomplete request with
  `challenge_id is required.`

## Correction

- The UI now captures the returned challenge identifier before opening the code
  step.
- Code and password submissions both include the same challenge identifier.
- A password-stage response preserves the identifier while clearing the OTP
  field.
- `/api/v1/auth/status` challenge metadata is passed into the login gate so a
  still-valid in-memory challenge can be resumed after a page refresh.
- Selecting another phone clears all local challenge and secret fields.
- Missing challenge metadata now produces an actionable local message rather
  than an incomplete API request.

## Verification

- Phase 10 local activation assertions: `7/7 passed`.
- TypeScript project check: passed.
- Production UI build: passed.
- Phase 9 workspace regression assertions: `10/10 passed`.
- Phase 9 visual/interaction acceptance assertions: `10/10 passed`.
- Scroll model assertions: `10/10 passed`.
- Grouped-media UI assertions: `16/16 passed`.
- The rebuilt UI was loaded from the running Loopback service.

## Live state

The earlier challenge expired normally after its bounded lifetime and the
coordinator recorded `eitaa.auth.challenge.expired/challenge_expired`. The
operator must request one fresh code and enter it only in the local UI. The
backend remains running and ready with authorized outbound network access.

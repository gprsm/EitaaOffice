# Eitaa Bridge v0.7 UI MVP 5.5 — Validation Report

## Versions

- Bridge product: `0.7.0-ui-mvp5.5`
- Bridge package: `0.7.0.dev11`
- UI package: `0.7.11`
- Core product: `0.6.0-core7.4.3`
- Core package: `0.6.0.dev17`
- SQLite schema: `8`

## Scope

- Restored the standard Windows/Electron frame.
- Removed automatic read-history calls when a dialog is merely opened.
- Added unread-aware initial history depth and viewport positioning.
- Added a visible unread separator.
- Added user-scroll and dwell-based read detection.
- Added a non-blocking, coalescing read-receipt queue in the local API.
- Preserved serialization of all Core RPCs to protect the shared Session.
- Persisted `read_inbox_max_id` in the Bridge dialog catalog.
- Supported partial unread-count updates instead of always forcing the counter to zero.

## Validation results

- Source test suite: `129 passed`.
- Installed-Wheel test suite in a clean virtual environment: `129 passed`.
- TypeScript strict check: passed.
- Vite production build: passed.
- Clean-environment `pip check`: no broken requirements.
- Bridge Doctor with a safe validation configuration and `--skip-core-open`: `17/17` checks passed.
- Core Wheel is byte-identical to UI MVP 5.4 and was not modified.
- Direct SQL usage in Bridge source: no matches.
- Core-internal imports in Bridge source: no matches.
- Eitaa protocol/constructor implementation in Bridge source: no matches.
- Private npm registry references: no matches.

## Important behavioral contract

Opening a conversation does not mark messages read. The initial viewport is positioned at the last read message when the exact Core boundary is available, otherwise immediately before the inferred unread block. A server read receipt is queued only after genuine user scrolling downward and after an incoming unread message has passed within the visible viewport for the configured dwell period. The queue returns immediately to the UI, while the actual Core RPC remains serialized for Session safety.

## Acceptance testing still required on Windows

- Verify standard Windows title bar and window controls.
- Open a dialog with a known unread count and confirm initial positioning at the read/unread boundary.
- Scroll gradually through unread messages and verify the counter decreases progressively rather than immediately becoming zero.
- Confirm no `/api/v1/messages/read/enqueue` request occurs before the first real user scroll.
- Confirm Session stability while switching dialogs during queued read receipts.

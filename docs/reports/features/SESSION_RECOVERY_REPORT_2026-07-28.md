# Session Recovery Continuation Report — 2026-07-28

## Outcome

The expired/rejected-session flow is now fail-closed and recoverable:

- An Eitaa `RPC 401` no longer leaves the UI inside an apparently authenticated workspace.
- Startup status returns `authenticated: false` with the stable code
  `auth_session_invalid` and opens the session-recovery surface.
- A `401` raised by any authenticated UI operation is normalized to the same
  API contract and causes the UI to refresh authentication state immediately.
- Logout first attempts remote logout. If Eitaa already rejects the token, the
  app completes a local logout, archives the session beside the original with
  an `.invalid.<timestamp>.bak` suffix, and opens a clean login flow.
- No message database, media, dialog catalog, contact data, or WordPress state
  is deleted by this recovery path.
- A rejected session is never archived automatically. The recovery surface
  retains a retry action because the same real session became reachable again
  later during validation, proving that a temporary server-side rejection is
  possible.

## Root cause addressed

`BridgeApplicationApi._auth_status()` previously returned
`authenticated: true` for every remote-probe exception, including
`RpcError(code=401)`. The logout flow also archived the local session only after
a successful remote `auth.logOut`, which made local logout impossible after the
server had already invalidated the token.

## Changed files

- `src/eitaa_bridge/application/api.py`
  - Classifies `RpcError(401, ...)` through exception chains.
  - Returns a fail-closed invalid-session status.
  - Normalizes runtime `401` responses to `auth_session_invalid`.
  - Adds safe local-archive fallback for logout.
  - Adds redacted runtime lifecycle events.
- `ui/src/lib/api.ts`
  - Emits a process-local invalid-session event for the stable API error.
- `ui/src/App.tsx`
  - Refreshes authentication state when that event occurs.
  - Shows a specific, non-destructive recovery explanation.
  - Keeps both retry and explicit archive/fresh-login actions.
- `tests/test_application_api.py`
  - Covers startup `401`, the stable error contract, and logout fallback.
- `tests/test_material_ui_repair.py`
  - Guards the UI event/recovery wiring.

The pre-existing user edit in `ui/src/styles.css` was detected and preserved
without modification.

## Verification

- Related Python/API/UI-source tests: **50 passed**
- Full Python suite excluding the known unrelated fixture failure:
  **264 passed**
- Full Python suite including all tests: **264 passed, 1 failed**
  - Remaining failure:
    `tests/test_runtime_ownership.py::test_windows_process_query_uses_explicit_utf8`
  - Cause is unchanged from the prior baseline: the test fixture uses Latin
    `Eitaa` in a path but asserts that it ends with Persian `ایتا`.
- TypeScript check: **passed**
- Production UI build: **passed**
  - Existing non-blocking Vite warning remains: the main minified JS chunk is
    approximately 836 KB and is a future code-splitting candidate.
- Scroll-model tests: **10/10 passed**
- Grouped-media UI assertions: **16/16 passed**
- `git diff --check`: **passed**

## Responsive UI validation

The invalid-session recovery surface was served with a controlled local mock;
no real session or user data was changed.

- Desktop: **1440 × 900**
  - RTL confirmed.
  - No horizontal overflow.
  - Recovery copy, stable error code, retry, and archive/login actions visible.
- Mobile: **390 × 844**
  - No horizontal overflow.
  - Recovery panel width: 366 px inside the 390 px viewport.
  - Both action buttons were enabled and fully inside the viewport.

All temporary mock files and test servers were removed after validation.

## Multi-account compatibility

This work is reusable rather than throwaway. A production multi-account design
should place the same single-session lifecycle behind each isolated account
worker:

- one session file per account;
- one scheduler/core/database/cache/log boundary per account;
- the same `auth_session_invalid` state per worker;
- local archive/re-login scoped only to the affected account;
- coordinator health derived from worker states without sharing tokens.

## Runtime source-loading follow-up

The reported behavior persisted after the session-recovery code was completed
because the running backend imported an older installed copy from:

`<project>/.venv/Lib/site-packages/eitaa_bridge`

instead of the current code under:

`<project>/src/eitaa_bridge`

The launch paths now explicitly put the project's `src` directory first on
`PYTHONPATH`. This is a durable launcher fix and does not modify or duplicate
files inside `.venv`.

Additional changed files:

- `scripts/office_runtime.py`
  - Prepends `<project>/src` for both the bundled Python and `.venv` runtime.
  - Preserves the bundled `python-packages` directory and any existing
    `PYTHONPATH` entries after the current source tree.
- `ui/electron/main.cjs`
  - Starts both the generated API executable and the Python fallback with the
    same source-first environment.
- `tests/test_runtime_ownership.py`
  - Verifies source-first behavior for the Office launcher.
  - Guards the Electron launcher environment wiring.

Follow-up verification:

- Runtime/API/UI-source tests: **66 passed**
  - The unchanged, known Unicode fixture mismatch was excluded.
- Electron entry-point syntax check: **passed**
- Production UI build: **passed**
- Real `.venv` child-process import resolved to:
  `src/eitaa_bridge/application/api.py`
- Desktop UI: RTL and no horizontal overflow at the available
  **1280 × 720** browser viewport.
- Mobile UI: RTL and no horizontal overflow at **390 × 844**.
- The isolated validation server was stopped after inspection.

An already-running backend must be closed and reopened once because Python
modules already loaded in that process cannot be replaced in memory by a file
change.

## Follow-up: Office launcher version alignment (2026-10-01, F-103/V-265)

The Bale stage updated the first line of `VERSION.txt` to Bale1 while the
backend's `eitaa_bridge.version.__version__` still reported GMI4.2. The Office
controller received HTTP 200 from its owned backend but correctly rejected the
exact version handshake; the backend then expired without UI heartbeats. The
source product version now matches the release manifest. The runtime checker
and smoke suite read the canonical manifest, and a regression test checks
source/manifest equality. The actual `EitaaBridge.bat` launched the backend and
Edge app, and health plus ownership remained valid beyond the heartbeat window.
No provider login or message operation was part of this verification.

# Eitaa Bridge MVP 6.1.1 UI 3.3 – Usage State & Reading Position

## Scope

This review stage starts from the user-accepted UI 3.2 package and changes only:

1. authoritative WordPress source-usage confirmation;
2. unread-first dialog opening;
3. low-overhead approximate reading-position persistence.

Contact management, remote avatar retrieval, first-load optimization, Core, schema, runtime ownership, installer behavior, WordPress transport, member operations, and the frozen UI 2 scroll implementation are outside this stage.

## WordPress usage-state repair

- A WordPress create/update result is accepted only after the composition record, publication rows, post ID, and source-message index are read back consistently.
- The API result exposes `confirmed_source_keys` only after that verification succeeds.
- The UI 3.3 runtime layer stores only those confirmed keys.
- Confirmed messages are immediately styled as used, their selection control is removed, and capture-phase click/context-menu handling prevents reuse.
- Subsequent message-list responses are overlaid with the locally confirmed usage record, so the state remains visible after changing dialogs or reopening the application.

## Unread-first and remembered reading position

- When a dialog has unread messages, the unread separator takes priority over a remembered position.
- When no unread messages exist, the last approximate anchor is restored.
- When both exist, a small “ادامه از آخرین موقعیت” control keeps the remembered position available without overriding the unread boundary.
- For a no-unread dialog with a saved checkpoint, the first local message request opens a bounded window around the last visible message instead of loading an unbounded history.

## Overhead controls

- Reading positions are stored only in browser `localStorage`; no network request or SQLite write is added for scrolling.
- Persistence is delayed by 2.5 seconds and dispatched through `requestIdleCallback` when available.
- At most 120 dialog positions are kept.
- At most 2,000 confirmed WordPress usage records are kept.
- The checkpoint stores an approximate first/last visible message ID, anchor key, pixel offset, `scrollTop`, and near-bottom state.

## Verification

- Source tests: `208/208` passed.
- Isolated installed-wheel tests: `208/208` passed.
- Python compileall: passed.
- Standalone UI 3.3 JavaScript syntax check: passed for source and production copy.
- Runtime environment identity: passed with Bridge `0.7.0.dev25`, Core `0.6.0.dev18`, requests `2.34.2`, and tzdata `2026.3`.
- Bridge product identity: `0.7.0-ui-mvp6.1.1-ui3.3`.
- Main UI 3.2 production JavaScript and CSS bundles are byte-identical.
- `App.tsx`, `scrollMath.ts`, and the frozen scroll-model test script are byte-identical to UI 3.2.
- The scroll-model test was not re-executed in this environment because the retained test runner requires the absent local `esbuild` package. No pass result is fabricated; byte identity preserves the already field-accepted UI 3.2 scroll code.
- Core wheel and SQLite schema 8 are unchanged.
- No private session, database, runtime state, log, media, or credential file is included.

## Build identity

- Product: `0.7.0-ui-mvp6.1.1-ui3.3`
- Bridge package: `0.7.0.dev25`
- UI package: `0.7.22`
- Stage: `ui-mvp6.1.1-ui3.3-usage-reading-position`
- Core: `0.6.0-core7.4.4` / package `0.6.0.dev18`
- SQLite schema: `8`

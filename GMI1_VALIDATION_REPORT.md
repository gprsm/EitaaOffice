# GMI 1 validation report

Date: 2026-07-24  
Baseline: Eitaa Bridge MVP 6.1.1 UI 3.3  
Candidate: Eitaa Bridge `0.7.0-ui-mvp6.1.1-gmi1`

## Result

Automated validation passed. Real-account acceptance against a known Eitaa
album remains required because no Session or private account data was used.

## Automated evidence

- Source tests: **214/214 passed**.
- Isolated installed-Wheel tests: **214/214 passed** with
  `eitaa-bridge==0.7.0.dev26` and `eitaa-core==0.6.0.dev19`.
- Grouped-media tests cover layer-134 decode, unsupported-entity resilience,
  schema 8 to 9 migration, rollback/recovery backup, metadata-only updates,
  local album lookup, page-boundary completion and API serialization.
- TypeScript check: passed.
- Vite production build: passed with Vite 7.3.6.
- Scroll model: **10/10 passed** with 5,000 mixed synthetic messages.
- Grouped-media UI model: **7/7 assertions passed**.
- Exact Runtime environment: passed for Bridge dev26, Core dev19,
  requests 2.34.2 and tzdata 2026.3.
- Core Wheel integrity: passed; only `eitaa_core` and its dist-info are present,
  with no bytecode, build directory or nested Wheel.
- Bridge Wheel integrity: passed; only `eitaa_bridge` and its dist-info are
  present, with no bytecode or build directory.
- UI 3.3 runtime patch source and distribution copy remain byte-identical and
  load before the main module.

## Functional contract verified

- Only a real, server-provided `grouped_id` forms an album.
- Album identity is scoped to one dialog.
- A locally split page is completed from Core SQLite without remote traffic.
- One gallery is one selection unit.
- Any already-used member prevents partial WordPress reuse.
- Search expands a matching member to its locally loaded album.
- `grouped_id` does not affect the message content hash.

## Not performed

- Login or synchronization against a real Eitaa account.
- Visual acceptance with a real multi-photo Eitaa post.
- WordPress write against a real production site.
- Windows installer EXE build or clean-machine installation.
- Local content-index Lab execution.

Use `GMI1_WINDOWS_ACCEPTANCE_CHECKLIST.md` for the required user acceptance.


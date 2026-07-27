# Core 7.4.3 Validation Report

- Product version: `0.6.0-core7.4.3`
- Package version: `0.6.0.dev17`
- SQLite schema: `8`
- Validation date: 2026-07-17

## Scope

This is a limited post-freeze compatibility and stability release. It adds server-side read acknowledgement and closes Session-refresh races exposed by long-running complete dialog synchronization. It does not add unrelated product capabilities.

## Automated validation

- `145` source-tree pytest tests passed.
- `145` tests passed against the installed Wheel in a clean environment.
- Offline Core Doctor passed all `18` checks.
- Schema remains 8; cumulative schema migration coverage remains green.
- New regression tests cover private/basic-group read history, channel/supergroup read history, ordinary RPC 401 refresh/replay, and process-wide Session refresh coordination.

## Architecture and safety

- Read acknowledgement is exposed through the public `history.mark_read` API.
- Ordinary authentication failures receive at most one refresh and one replay.
- Concurrent Core instances reload the latest Session under a process-wide lock and reuse a token already refreshed by another instance.
- No Session, database, token, access hash, downloaded media, or private diagnostics are included in the distributable artifacts.

## Live-validation boundary

No live `readHistory` write was sent from this build environment to the user's account. The server-write path is covered by codec, repository, service, and Gateway regression tests. Complete dialog synchronization and avatar behavior remain inherited from the separately validated Core 7.4.2 path.

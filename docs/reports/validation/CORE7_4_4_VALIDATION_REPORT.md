# Core 7.4.4 Validation Report

## Versions

- Product: `0.6.0-core7.4.4`
- Package: `0.6.0.dev18`
- SQLite schema: `8`
- Wheel: `vendor/eitaa_core-0.6.0.dev18-py3-none-any.whl`
- Wheel SHA-256: `3f03b7bc1d5294890d5102627e743e0c70bf5c76511fda3a4c1b990aa4e25739`

## Scope

Core 7.4.4 is a compatibility and consistency successor of Core 7.4.3. It adds
public snapshot persistence for cooperative dialog pagination and updates the
local schema-8 dialog read state only after the server accepts `mark_read`.
The existing complete dialog classification, token refresh coordination,
message/media/publication services, and schema remain intact.

## Validation

- Source tests: `142/142` passed.
- Installed-wheel tests: `142/142` passed.
- Offline Core Doctor: `18/18` checks passed.
- Database schema remained `8`.
- No live Eitaa account was used during this validation.

## Read-state consistency

`HistoryService.mark_read()` now performs this order:

1. send the public remote read-history request;
2. require an accepted response;
3. update `read_inbox_max_id`, `unread_count`, and `unread_mark` in the Core
   dialog snapshot;
4. return the accepted result to Bridge.

A failed remote receipt does not optimistically alter Core SQLite.

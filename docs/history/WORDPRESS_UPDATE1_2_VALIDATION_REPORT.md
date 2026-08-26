# Eitaa Bridge v0.4 WordPress Update 1.2 — Validation Report

Validation date: 2026-07-17  
Product version: `0.4.0-wordpress-update1.2`  
Python package version: `0.4.0.dev3`  
Required Core product: `0.6.0-core7.4.1`  
Required Core package: `0.6.0.dev15`  
Core database schema: `7`

## Operator case reproduced

The recorded WordPress Post ID was found correctly, but the remote post had status `trash`. Update 1.1 classified every non-`draft` status as live and therefore returned `blocked_live_post` / `publication_live_update_blocked`. This was semantically incorrect because Trash is neither Draft nor live content.

Update 1.2 separates three states:

- `draft`: normal controlled update;
- live non-Draft states such as `publish`, `private`, `pending`, or `future`: require explicit live-update permission;
- `trash`: requires a separate explicit restore operation.

## Safety behavior added

- Read-only update preview reports `blocked_trashed_post` by default.
- Restore preview reports `restore_required` only when `--restore-trashed` is explicit.
- Normal update stops with `publication_trashed_post_blocked` and performs no write.
- Explicit restore updates exactly the recorded WordPress Post ID and sends `status=draft` together with the current deterministic Bridge payload.
- The response is accepted only when the same Post ID is returned, the deterministic Bridge identity is valid, and the final remote status is `draft`.
- No replacement post is created.
- `--allow-live-update` does not authorize restoration from Trash.
- Existing compatible media is reused; no media deletion is performed.

## Commands added

```bat
run_publication_restore_preview.bat SITE_KEY "PEER_FILE" MESSAGE_ID
run_publication_restore.bat SITE_KEY "PEER_FILE" MESSAGE_ID
```

Equivalent CLI option: `--restore-trashed` on `publication update-preview` and `publication update`.

## Baseline and packaging

- Complete successor package; no source merge is required.
- Foundation 3 remains the frozen lineage baseline.
- Core source is neither included nor modified.
- The bundled Core Wheel is byte-identical to Foundation 3.
- Configuration schema remains `1`.

Core Wheel SHA-256:

`0e16dac9fbb1d1994301012f36f5a83286ce56631cb0d22f0425a56f87d8a092`

Bridge Wheel SHA-256:

`d4b9e8508c076694fe01d4e21004b72f83f538ef39130a3835b97e4b048881fc`

## Automated validation

- Python: `3.13.5`
- Tests collected: `78`
- Tests passed from source tree: `78`
- Tests passed against clean installed Wheel: `78`
- Clean Wheel installation: passed
- `pip check`: no broken requirements
- Bridge Doctor: `14/14` checks passed
- Core Doctor through Bridge: `18/18` checks passed
- Core capability contract: publication workflow present, schema 7
- Direct SQL implementation scan in Bridge source: no matches
- Eitaa protocol implementation scan in Bridge source: no protocol implementation found

## New deterministic scenarios

- Trash is not labeled as a live update.
- Trash preview is read-only and blocked by default.
- Update of Trash is blocked without explicit restore permission.
- Explicit restore sends `status=draft`.
- Explicit restore retains the same recorded Post ID.
- Explicit restore never calls WordPress post creation.
- A restored response that does not become Draft cannot be reconciled as successful.
- Existing v0.3/v0.4 slug-identity collision protections remain active.

## Live-site limitation

No write was performed against the operator's live WordPress site in the build environment because the site's credentials were not available here. The reported Post-ID/status scenario is covered by deterministic workflow and HTTP payload tests. The operator should run the new restore preview first, then the explicit restore command on the same recorded Post ID.

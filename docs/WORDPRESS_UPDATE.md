# WordPress Update 1.2

## Scope

Update 1 modifies exactly one previously recorded WordPress post for exactly one locally stored Eitaa message and one configured site. It never creates a replacement post.

## Preconditions

- A Core publication record exists for the same peer, message ID, target type `wordpress`, and site key.
- The record contains a valid WordPress Post ID or the deterministic slug resolves uniquely.
- The latest Eitaa message version has already been stored through Core.
- WordPress credentials can edit the target post.
- Media updates also require `upload_files`.

## Read-only preview

`publication update-preview` reads Core state, the recorded WordPress Post, the deterministic slug, and any reusable Media item. It performs no WordPress POST and no Core state transition.

Possible actions include:

- `already_current`: local and remote payloads already match;
- `reconcile_local_state`: remote already has the current payload while Core is stale;
- `update_required`: Core reports changed content and the remote post is old;
- `blocked_live_post`: the target is a live non-Draft post and explicit permission is absent;
- `blocked_trashed_post`: the target is in WordPress Trash and explicit restoration is absent;
- `restore_required`: the same recorded Post ID can be explicitly restored to Draft;
- `remote_drift`: WordPress differs although the Core message hash is unchanged;
- `remote_missing`: the recorded post and deterministic slug cannot be found.

## Identity rules

The recorded Post ID and deterministic slug must resolve to the same WordPress object. A mismatch or duplicate slug stops with a collision error. Update mode never silently chooses another post.

## Drift rules

Bridge compares:

- deterministic slug;
- hidden Bridge content-hash marker;
- raw title and content when WordPress exposes edit context;
- featured Media ID;
- requested category when explicitly selected.

Unexpected remote drift is blocked by default. `--overwrite-remote-drift` is an explicit operator decision after reviewing the WordPress post.

## Status rules

Normal update requests omit the WordPress `status` field, so the existing status is preserved. Live statuses such as `publish`, `private`, `pending`, or `future` remain blocked unless `--allow-live-update` is supplied.

The `trash` status is handled separately and is never authorized by `--allow-live-update`. A trashed post remains blocked unless `--restore-trashed` is explicit. The restore request updates the same recorded Post ID and includes `status=draft`; Bridge then verifies that the returned object is the same ID, has the deterministic identity, and is now a Draft. No replacement post is created.

## Media rule

New Media slugs use a media-specific fingerprint rather than the complete message hash. Text-only edits can therefore reuse v0.4 media. A first update from a v0.3 publication may upload one fingerprinted replacement because v0.3 Media identity used the complete content hash.

Old Media Library objects are retained. No automatic deletion or rollback occurs.

## Ambiguous update recovery

A WordPress update POST is sent once. If its outcome is unknown, Bridge performs an authenticated GET of the same Post ID and verifies the complete expected Bridge payload. A verified result is recorded as `recovered_update`. Otherwise Core remains `processing`, and another write is blocked.

## Missing post

If the recorded Post ID returns 404 and the deterministic slug also resolves to nothing, Update 1 stops with `publication_remote_post_missing`. Recreating a deleted remote post is deliberately outside this phase.


## Update 1.1 compatibility fix

A v0.3 creation response could contain a WordPress-normalized slug even though Bridge requested the deterministic slug. Update 1.1 accepts that recorded Post ID only when its raw content contains the stable hidden Bridge identity marker for the same site key, peer type, peer ID, and message ID, and no different Post owns the deterministic slug. The subsequent explicit update repairs the slug on that same Post ID. Missing markers and true slug collisions remain blocked.


## Update 1.2 Trash reconciliation fix

Update 1.2 separates Trash from live publication states. The default update command stops with `publication_trashed_post_blocked`. `publication update-preview --restore-trashed` remains read-only and reports `restore_required`. `publication update --restore-trashed` restores and updates exactly the recorded Post ID as a Draft. This operation is explicit because restoring a user-trashed post is a material state change, even though it is reversible.

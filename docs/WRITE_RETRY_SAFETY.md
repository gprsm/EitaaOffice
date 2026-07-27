# WordPress write and recovery safety

## Base rule

Bridge never automatically retries WordPress writes.

This applies to:

- `POST /wp/v2/media`;
- `POST /wp/v2/posts`;
- `POST /wp/v2/posts/<id>`.

Safe GET operations may use bounded retry according to the configured `retry_attempts` value.

## Unknown outcome

A write is considered ambiguous when the request may have reached WordPress but Bridge cannot prove the result, including:

- network interruption;
- transient HTTP status after a POST;
- non-JSON success response;
- success JSON without a valid created object ID.

## Creation and update reconciliation

Before creation, Bridge queries the deterministic slug. After ambiguous creation, it queries that slug again.

Before update, Bridge verifies the recorded Post ID and deterministic slug resolve to the same object. After ambiguous update, it GETs the same Post ID and verifies the expected title, content marker, raw content when available, featured Media, category, and slug.

A verified object is recovered. An unresolved outcome leaves Core `processing`; the write is not repeated automatically. Multiple or conflicting identities produce a collision error. GET reconciliation is not a retry of the write.

## Core state

- deterministic external failure: `failed`;
- proven Draft creation: `published` with WordPress Post ID and URL;
- unresolved external outcome: `processing`;
- edited local message after publication: `needs_update`, owned by Core;
- verified existing-post update: `published` with the current Core hash;
- unresolved update outcome: `processing`.

Bridge does not reproduce Core content-hash or staleness logic.

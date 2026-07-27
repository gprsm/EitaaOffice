# GMI 1 architecture, data model and UI scope

## Decision

GMI 1 implements only server-declared grouped media. It does not infer albums
from adjacent message IDs, dates, captions, or sender identity. The independent
local content-indexing experiment remains outside the production application
until its Lab acceptance criteria are met.

## Data flow

```text
Eitaa messages response
  -> Core layer-134 Message decoder
  -> Message.grouped_id
  -> Core SQLite schema 9
  -> public messages.list_album(peer, grouped_id)
  -> Bridge page-boundary completion and JSON serialization
  -> UI album lookup
  -> one gallery card / one selection unit
```

The message constructor carries `grouped_id` as the optional 64-bit field at
flag bit 17. Core advances through the optional metadata preceding this field,
retains the value, and returns a safe parse warning if an unsupported metadata
shape prevents alignment. A message is still retained when that optional
metadata cannot be decoded.

## Data model

The existing Core `Message` gains one nullable value:

```text
grouped_id: signed 64-bit integer or NULL
```

The `messages` table gains the same nullable column and a partial lookup index:

```sql
CREATE INDEX idx_messages_peer_grouped
ON messages(peer_type, peer_id, grouped_id, message_id)
WHERE grouped_id IS NOT NULL;
```

Album identity is scoped by `(peer_type, peer_id, grouped_id)`. A value is never
joined across dialogs. `grouped_id` is metadata and is deliberately excluded
from the content hash, so learning an album identity for an already stored
message does not mark a published WordPress source as stale.

## Migration and recovery

- The supported database version changes from schema 8 to schema 9.
- Before any migration, SQLite creates a consistent backup named
  `DATABASE.pre-schema9-v8.bak` through the SQLite backup API.
- The column, index and `user_version` update are one explicit transaction.
- A migration failure rolls the transaction back and closes the connection.
- The untouched schema-8 backup is the recovery source; the application does
  not delete or overwrite it.
- New databases run the cumulative migrations and finish at schema 9.

## Bridge boundary

Bridge uses only the public Core facade. When a locally listed page contains
part of an album, Bridge calls `messages.list_album` and completes that album
from local SQLite. This is a local database operation: it issues no Eitaa RPC
and does not occupy the Eitaa scheduler.

The application API adds only two response fields:

- `grouped_id`: nullable album identifier;
- `album_size`: count of locally returned members in the album.

No HTTP route, authentication contract, WordPress route, or scheduler priority
is changed.

## Exact UI scope

- All locally available messages with the same dialog-scoped `grouped_id` are
  rendered as one gallery card.
- Every image is visible in the gallery; non-image media remain visible as file
  chips.
- Non-empty member captions are combined once, in message order.
- Selecting or clearing a gallery affects every member as one unit.
- If any member is already assigned to WordPress, partial reuse is prevented
  and the existing usage view opens.
- Search includes the whole locally loaded album when any member caption or ID
  matches.
- Unread and reading-position calculations normalize to the gallery leader.
- Album follower rows occupy no rendered height; the accepted Scroll math
  module itself is unchanged.

## Explicitly out of scope

- guessing album membership when `grouped_id` is absent;
- changing download, upload, WordPress composition, or publication behavior;
- remote album completion beyond the current history sync;
- bulk/campaign sending;
- local semantic indexing or automatic WordPress category assignment;
- changes to Runtime ownership, Installer logic, Scheduler logic, or the
  standalone UI 3.3 reading-position patch.


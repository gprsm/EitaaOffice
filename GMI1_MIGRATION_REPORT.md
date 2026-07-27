# GMI 1 SQLite migration report

## Change

Core SQLite moves from schema 8 to schema 9. The existing `messages` table
receives one nullable `grouped_id INTEGER` column and one partial album lookup
index. No table, message, publication, dialog, member, job or composition row
is deleted.

## Safety sequence

1. Read the existing `PRAGMA user_version`.
2. Refuse a database newer than schema 9.
3. For an existing non-empty schema, create a consistent SQLite backup through
   the SQLite backup API.
4. Run `ALTER TABLE`, index creation and `PRAGMA user_version=9` in one explicit
   transaction.
5. Roll back and close the connection if SQLite reports a failure.

For the normal schema-8 upgrade, the backup is:

```text
messages.sqlite3.pre-schema9-v8.bak
```

An existing backup with that name is never overwritten.

## Data compatibility

- Existing rows receive `grouped_id=NULL`.
- Future history synchronization can enrich those rows with a server album ID.
- Album metadata is excluded from the content hash.
- A metadata-only enrichment therefore does not mark a published WordPress
  source as changed.
- The migration performs no Eitaa operation and uses no scheduler slot.

## Recovery

If startup reports a migration failure:

1. stop Eitaa Bridge;
2. retain the failed database for diagnosis;
3. make an additional copy of the `.pre-schema9-v8.bak` file;
4. restore that copied backup as the active database;
5. run the previous UI 3.3 package, or correct the failure and retry GMI 1.

Do not overwrite the only backup copy. No automatic destructive recovery is
performed.

## Test evidence

- successful schema-8 upgrade to schema 9;
- backup remains readable as schema 8 without `grouped_id`;
- injected mid-migration SQL failure rolls the live schema back to version 8;
- recovery backup remains present after the injected failure;
- fresh database initialization reaches schema 9;
- message and album round trips pass.


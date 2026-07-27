# WordPress Multi-Message Composer Contract

## Aggregate identity

A composition is identified by `site_key + composition_key`. Its deterministic WordPress slug also includes a short SHA-256 suffix. The same composition key cannot later be rebound to unrelated sources. During an explicit update, the recorded sources must all remain present; new sources may be appended safely, while removal or replacement of recorded sources is blocked.

Each source is identified by:

```text
peer_type + peer_id + message_id
```

Core publication records link every source to the same external WordPress post ID. The Bridge JSON store preserves order, source hashes, categories, tags, excerpt, featured-source identity, and post metadata.

## Write order

1. Validate all source messages and current Core hashes.
2. Reject sources already linked to another WordPress post.
3. Resolve deterministic media slugs with safe GET.
4. Download missing media through Core public `MediaDownloadService`.
5. Upload missing media without automatic POST retry.
6. Render the complete ordered body.
7. Create one WordPress post without automatic POST retry.
8. Reconcile ambiguous creation by deterministic slug.
9. Mark every source published to the same post ID through Core `PublicationService`.
10. Atomically persist the Bridge composition record.

A rerun recovers an existing correctly marked post and completes missing source links/state instead of creating a duplicate.

## Rendering

Text is HTML-escaped and split into paragraphs. Line breaks inside one paragraph become `<br>`. Media is emitted after the text of its source. Images, video, audio, and documents use ordinary WordPress-compatible HTML. Sources are separated by a WordPress separator block.

## Update contract

An explicit update writes to the same recorded WordPress Post ID. Existing source messages may be reordered and new sources may be added. Every recorded source must remain in the request; deleting or replacing recorded sources is blocked. Newly added sources are checked for collisions and, after the remote post is verified, are linked to the same WordPress post through Core publication records.

## Deliberate exclusions

- no automatic publish status;
- no source reuse override across different WordPress posts;
- no category/tag creation outside the UI action;
- no destructive cleanup of old media or posts.


## Post status

Composer accepts `post_status` values `draft` and `publish`. `draft` is the default. `publish` also requires `confirm_publish=true` and the configured WordPress account must have `publish_posts`. Preview never writes.

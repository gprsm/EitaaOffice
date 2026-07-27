# WordPress Publication and Update

## Scope

Creation converts exactly one locally stored Core message into one WordPress Draft on one configured site. Update 1 can later modify that same recorded Post ID explicitly.

It is intentionally operator-driven. Preview, status, and run are separate explicit commands. There is no polling loop, queue, scheduler, or unattended execution.

## Preconditions

- Core 7.4.5 GMI 1 is installed from the exact bundled Wheel.
- The Eitaa session and Core database paths in `bridge.json` point to the working Core data.
- The selected message has already been stored by Core.
- The peer JSON can be loaded through the public Core `load_peer_file` helper.
- WordPress credentials can edit posts; media messages also require `upload_files`.

## Draft rendering

- The first non-empty line becomes the default title, limited to 160 characters.
- The full plain text is HTML-escaped and converted into paragraphs and line breaks.
- A deterministic, non-visible Bridge marker is appended to the content.
- Images become `featured_media`.
- Audio and video receive HTML5 media elements using the WordPress source URL.
- Other files receive a download link.
- If WordPress omits a source URL, the Draft records that an attachment exists in the Media Library.

The operator may override the title or category. Creation always creates a Draft and does not auto-publish. Update preserves the existing WordPress status and blocks non-Drafts unless explicitly allowed.

## State rules

### No record, pending, or failed

A safe slug lookup runs first. If no existing Post is found, the workflow enters `processing` and performs the external write sequence.

### Published

If the Core content hash still matches, the run returns `already_published` without a WordPress write.

### Needs update

The create command stops with `publication_needs_update`. Use `publication update-preview` and then the explicit `publication update` command from Update 1.

### Processing

The workflow attempts read-only reconciliation:

- a matching Post finalizes Core as published;
- a matching Media item allows Draft creation to continue;
- no matching external object blocks further writes with `publication_processing_unresolved`.

### Skipped

The run is blocked unless `--retry-skipped` is explicitly supplied.

## Failure rules

A deterministic WordPress rejection records `failed` with a safe error code. An ambiguous write remains `processing`. Raw request bodies, response bodies, message text, titles, descriptions, credentials, file bytes, tokens, IMEI values, and access hashes are excluded from Bridge diagnostics.

## Local media

Downloaded media is retained under:

```text
<core.media_directory>/bridge-publications/
```

The filename is deterministic and may be replaced on a later deliberate retry. Bridge does not delete Core-owned downloaded media or WordPress Media Library objects. Update 1 also does not remove superseded attachments automatically.

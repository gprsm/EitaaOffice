# Eitaa Bridge WordPress Media 1 Validation Report

Product version: `0.2.0-wordpress-media1`  
Package version: `0.2.0.dev1`  
Direct baseline: frozen Foundation 3  
Required Core: `0.6.0-core7.4.1` / `0.6.0.dev15` / schema `7`

## Scope

This build adds the WordPress-side media boundary only: local file upload, Media Item retrieval, `upload_files` capability reporting, and optional Featured Media on Draft creation.

It does not add Eitaa retrieval, Core publication-state orchestration, automatic media download, update/delete workflows, queue, scheduler, API server, or UI.

## Safety properties

- media upload uses one multipart POST;
- the file is streamed from disk and the handle is closed after the request;
- POST is never retried automatically;
- uncertain upload or Draft results return `wordpress_ambiguous_write`;
- local file errors are typed as `media_file_error` before network access;
- diagnostics exclude file bytes, local filenames, title, caption, description, alt text, credentials, and post content;
- each operation targets exactly one selected `site_key`;
- Foundation 3 configuration remains valid without schema changes.

## Automated validation

- Python source compile: passed
- tests: 47 passed
- clean dependency environment uses bundled Core 7.4.1 Wheel
- Core Wheel SHA-256 retained unchanged: `0e16dac9fbb1d1994301012f36f5a83286ce56631cb0d22f0425a56f87d8a092`
- Bridge Wheel SHA-256: `4ef3bd453f273910e6ce4708b1c6d2cfa5f2e8be24a40bc548f243a481ca185b`
- clean Wheel installation and `pip check`: passed
- forbidden Eitaa endpoint/TL and direct SQL scans: passed

## Live WordPress validation

No user credential or production site is included in this build environment. Run the documented small-file media test locally on the selected site.

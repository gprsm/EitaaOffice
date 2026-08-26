# Eitaa Bridge Foundation 3 Validation Report

Product version: `0.1.0-foundation3`  
Package version: `0.1.0.dev3`  
Required Core: `0.6.0-core7.4.1` / `0.6.0.dev15` / schema `7`

## Scope

Foundation 3 is a safety and multi-site selection refresh of Foundation 2. It does not add media, automated publication, Queue, Scheduler, FastAPI, UI, Eitaa protocol code, or direct Core SQL.

## Implemented changes

- safe retries remain enabled for `GET`, `HEAD`, and `OPTIONS`;
- `POST`, `PUT`, `PATCH`, and `DELETE` are never automatically retried;
- uncertain write results raise typed `wordpress_ambiguous_write`;
- successful write responses without valid JSON or a usable Post ID are also classified as ambiguous;
- multiple WordPress sites can be configured with separate credentials;
- each command targets exactly one selected `site_key`;
- `sites list` safely reports configured destinations and credential presence;
- Windows Batch files accept explicit site selection;
- no fan-out to multiple sites exists.

## Validation

- Python: `3.13.5`
- Bridge tests: `36 passed`
- clean Wheel installation: passed
- installed Bridge: `0.1.0-foundation3` / `0.1.0.dev3`
- installed Core: `0.6.0-core7.4.1`
- Core sender-filter public contract: present
- bundled Core Wheel byte-identical to the released Core 7.4.1 Wheel: yes
- source compile check: passed
- no Eitaa endpoint/TL implementation in Bridge source: confirmed
- no direct SQLite statements in Bridge source: confirmed
- no real `.env`, `bridge.json`, Eitaa session, selected-peer files, or SQLite database included: confirmed

## Live WordPress test

The build environment has no user credentials, so a live Foundation 3 WordPress call was not performed here. After local upgrade, run `run_sites_list.bat`, `run_wp_test.bat SITE_KEY`, and one test Draft on the selected site. Application Password and theme configuration do not need to change.

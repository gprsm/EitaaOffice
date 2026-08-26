# Member Directory and Audience Management Roadmap

This capability is intentionally outside UI 3.2 because it requires a durable local data model, migrations, import mapping, consent/status tracking, and campaign reporting.

## Local directory

The directory is independent from Eitaa server peer types. One person can have:

- first name, last name and display name;
- one or more normalized phone numbers;
- local categories such as friends, classmates, executive colleagues, or department staff;
- source information such as manual entry, Excel import, phone list, Eitaa member snapshot, or contact sync;
- optional notes and organization/unit fields;
- resolution state, linked Eitaa user ID/access hash when available, last resolution time and last error;
- communication status such as active, do-not-contact, failed/privacy-blocked, or unknown.

## Import

Native XLSX import should provide a mapping screen for name, family name, phone, category, organization and notes. The importer must normalize Persian/Arabic digits, deduplicate phone numbers, preview changes, and report inserted, updated, duplicate and invalid rows before commit.

## Audiences

Users should be able to build reusable audiences from local categories, Eitaa groups, selected members, imported lists and intersections/exclusions. Audience membership must be previewable and deduplicated before a campaign runs.

## Campaign composer

A campaign can contain text, text plus photo, or text plus file. It should support a test recipient, throttling, pause/resume/cancel, delivery reports, per-recipient errors, and a clear distinction between server acceptance and confirmed delivery.

## Safety and platform constraints

The directory does not bypass Eitaa permissions, privacy restrictions, flood limits, access-hash requirements or anti-spam rules. Bulk actions must remain previewed, explicitly confirmed, throttled and auditable.

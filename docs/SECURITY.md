# Security and diagnostics

Bridge diagnostics are component-separated JSONL files. Each run has a manifest that explicitly states the excluded data classes.

Redacted data includes:

- credentials, usernames, Application Passwords, Authorization headers, and cookies;
- Eitaa token, IMEI, access hash, session material, phone numbers, and SQLite contents;
- post/message content, titles, excerpts, captions, descriptions, and alternative text;
- local media filenames and file bytes;
- raw request and response bodies.

Media diagnostics may record only non-content properties such as byte count, suffix, MIME type, selected site, method, endpoint path, HTTP status, and created Media ID.

Exceptions use stable safe error codes. WordPress response bodies are never copied into exception messages or diagnostics. Only HTTP status, method, endpoint path, retry count, and a sanitized WordPress error code may be recorded.

For troubleshooting, share only the exact component file named by the error. Never share an entire diagnostics directory.

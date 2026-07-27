# Core 7.4.4 public contract

Eitaa Bridge UI MVP 6.1 requires the bundled public Core contract:

- product `0.6.0-core7.4.4`;
- package `eitaa-core==0.6.0.dev18`;
- SQLite schema `8`;
- complete, classified dialog pagination through the public discovery service;
- public page-level dialog retrieval and public snapshot persistence;
- public history synchronization/search/date-range services;
- server `mark_read` followed by local dialog-snapshot update only after acceptance;
- shared Session refresh coordination;
- public member synchronization/search/export;
- public persistent bulk-send jobs for text/photo/file;
- public phone-list import/resolve/cleanup/send;
- public membership preview, reversible invite jobs, and rollback.

Bridge must not import Core infrastructure, issue SQL, or implement Eitaa TL/RPC
constructors. All remote operations are invoked through the public `EitaaCore`
facade and are serialized by the Bridge priority scheduler.

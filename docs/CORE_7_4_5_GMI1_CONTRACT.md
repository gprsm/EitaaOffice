# Core 7.4.5 GMI 1 public contract

Eitaa Bridge GMI 1 requires the bundled public Core contract:

- product `0.6.0-core7.4.5-gmi1`;
- package `eitaa-core==0.6.0.dev19`;
- SQLite schema `9`;
- layer-134 `Message.grouped_id` decoding;
- persistent nullable `grouped_id` message metadata;
- public `messages.list_album(peer, grouped_id)` local lookup;
- capability flag `grouped_media=true`;
- all Core 7.4.4 dialog, history, read-state, member, phone, bulk-send and
  membership operations.

Bridge must not import Core infrastructure, issue SQL, or implement Eitaa
TL/RPC constructors. Album completion uses the public Core facade and local
SQLite only. All remote Eitaa operations continue to use the single Bridge
priority scheduler.


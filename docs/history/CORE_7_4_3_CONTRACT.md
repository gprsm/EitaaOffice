# Core 7.4.3 public contract

Eitaa Bridge UI MVP 5.2 requires:

- product `0.6.0-core7.4.3`;
- package `eitaa-core==0.6.0.dev17`;
- SQLite schema `8`;
- public facade services `messages`, `retrieval`, `media`, `publications`, `sync`, and `discovery`;
- public discovery methods `list_all_dialogs`, `cached_dialogs`, `resolve_peer_photo`, and `save_peer`;
- publication workflow and sender filtering.

Bridge does not import Core infrastructure modules, execute Core SQL, or implement Eitaa TL/RPC constructors. Dialog pagination, classification, persistence, and token refresh remain Core responsibilities.

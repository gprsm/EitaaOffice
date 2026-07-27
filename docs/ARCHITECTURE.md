# Architecture

```text
Future UI
   |
   v
Local JSON API (interfaces/http_api.py)
   |
   v
BridgeApplicationApi (application/api.py)
   |
   +--> EitaaBridge public facade
   |       +--> Core 7.4.5 GMI 1 public facade
   |       +--> WordPressService
   |       +--> Composer workflow
   |
   +--> Bridge-owned atomic composition JSON state
   |
   +--> Bridge-owned content-index SQLite
          +--> transient Persian TF-IDF centroid model
          +--> staged advisory results and feedback
```

The HTTP adapter contains no product logic. The application API performs route-level validation and calls the same facade methods used by CLI. Bridge does not import Core persistence, transport, codec, or protocol modules and does not write Core SQLite directly.

Grouped-media support follows the same boundary: Core decodes and stores
`grouped_id`, exposes local album lookup through its public message service,
and Bridge serializes the result. See `GMI1_ARCHITECTURE_AND_SCOPE.md`.

GMI 2 adds no second Eitaa scheduler and changes no Core persistence. Its
indexing worker owns a short-lived Bridge/Core instance and performs public
local message-store reads only. Result staging is promoted atomically. Inferred
galleries are computed only in UI memory from strict sender/time/adjacency
rules, are marked as suggestions, and never become Core facts. See
`GMI2_ARCHITECTURE_CRITIQUE.md`.


## v0.7 desktop layer

The Electron main process owns the local API lifecycle and exposes a narrow IPC request function through a context-isolated preload. The React renderer has no Node integration. UI state never bypasses Bridge or Core; dialogs, messages, media, authentication, and WordPress composition use public application APIs.

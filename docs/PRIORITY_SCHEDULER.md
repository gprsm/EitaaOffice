# Eitaa operation priority scheduler

The HTTP API is threaded, but the Eitaa Session is a single mutable resource.
MVP 5.6 therefore schedules all remote Eitaa work on one worker.

| Priority | Work |
|---:|---|
| 0 | Authentication and Session-sensitive recovery |
| 10 | Active conversation messages and date-range requests |
| 20 | One remote dialog page |
| 30 | Message media preview |
| 50 | Avatar download |
| 70 | Snapshot persistence and other background work |
| 100 | Delayed, coalesced read receipt |

Dialog synchronization yields after every page. A new active-message request can
therefore move ahead of the next dialog page. Read receipts are delayed and
coalesced per peer, and are deferred whenever higher-priority work exists.
Remote calls never overlap against the same Session.

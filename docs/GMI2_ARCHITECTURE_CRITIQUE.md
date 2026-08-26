# GMI 2 — local index, conservative inferred galleries and content filters

## Scope decision

GMI 2 contains exactly three related changes:

1. a local, explainable Persian content index;
2. conservative visual grouping of consecutive ungrouped photos;
3. one collapsible content-filter panel.

It does not implement automatic WordPress categorization, automatic publishing,
remote AI, bulk messaging, member-directory work, or a second Eitaa scheduler.

## Two kinds of gallery

The UI must never present an inferred relationship as a server fact.

### Server gallery

Messages share the same dialog-scoped `grouped_id`. This remains the strongest
and preferred signal.

### Inferred gallery

Ungrouped messages may form a temporary UI gallery only when all conditions
below hold:

- every item is an image;
- every item lacks `grouped_id`;
- every item exposes the same non-empty sender key;
- items are consecutive in the loaded message order, with adjacent message IDs
  and no intervening message;
- adjacent timestamps differ by at most 120 seconds;
- reply context is identical;
- the run contains at least two items.

The group is computed in memory and is not written to Core SQLite. It is marked
`inferred` in the API/UI, can change when more history is loaded, and never
overrides a server gallery.

### Self-criticism

Temporal adjacency is correlation, not authorship intent. A person can send two
unrelated photos within 120 seconds, or pause longer than 120 seconds while
uploading one report. The conservative rules reduce false joins but cannot
remove them. Therefore inferred galleries are visually labelled
`گالری پیشنهادی`, remain reversible, and must not create a durable server fact.

## Local content index

```text
local Core messages
  -> Persian normalization
  -> word/character n-gram features
  -> explainable TF-IDF centroid classifier
  -> cautious multi-label threshold
  -> Bridge-owned SQLite result store
  -> review badges and filters
```

No message text is sent outside the computer. Indexing opens a short-lived Core
instance on its own worker thread and performs only public local message-store
reads. It does not submit work to the Eitaa scheduler.

### Training evidence

The first useful training source is the user's own confirmed WordPress
composition history:

- source messages are positive examples;
- their recorded WordPress category IDs are labels;
- current category names provide cold-start seed text;
- optional user-entered guide words are local aliases for the selected
  category;
- accepted/rejected local feedback is additional versioned evidence.

The classifier stores neither raw training text nor raw indexed text in its own
database. It stores a text hash, category predictions, scores and short feature
evidence.

Each run writes first to a staging table. Completion or user cancellation
promotes that run in one SQLite transaction; an unexpected failure discards the
staging rows and leaves the previous visible result set intact. Schema 1 to 2
migration creates a SQLite backup before the additive staging-table migration.

### What “learning” means

Learning means rebuilding a small local statistical model from confirmed local
examples. It does not mean semantic comprehension or autonomous continuous
self-training. A new WordPress composition improves the next explicit index
run; a user correction is append-only evidence; every run gets a reproducible
model fingerprint.

### Self-criticism

- With no prior categorized messages, the model mainly matches category-name
  vocabulary and must report `cold_start`.
- Rare categories cannot be learned reliably from one example.
- Similar administrative language can create false positives.
- Synthetic Lab accuracy cannot establish accuracy on the user's real data.
- Scores from a centroid model are ranking signals, not probabilities.
- Persian spelling, half-space and colloquial variation remain imperfect even
  after normalization.

For these reasons results are suggestions only. The default threshold is
conservative, uncertain results remain unlabelled, and no result changes a
WordPress post or Composition record.

## Local index database

GMI 2 adds a separate Bridge-owned database:

```text
data/content_index.sqlite3
```

Schema 1 contains:

- `index_results`: one current result per site/dialog/message;
- `index_feedback`: append-only accepted/rejected label evidence;
- `index_runs`: durable run summaries without message text.

This is not a Core schema migration. Core remains schema 9. Database creation
and writes are transactional; an existing future/newer schema is rejected.

## Background job contract

- one active index job per dialog and site;
- local worker thread, independent of the Eitaa scheduler;
- bounded message count (default 20,000; hard maximum 50,000);
- progress counters, cancel event, terminal report and safe error type;
- cancellation commits completed batches and records a cancelled run;
- no UI polling loop may block message scrolling.

## Filter panel

The content header gains one collapsible `فیلتر` control containing:

- `ایندکس‌گذاری محلی` start/cancel and progress;
- `نمایش پیام‌های ثبت‌شده در وردپرس` checkbox;
- category-result selector after an index exists;
- short status explaining local-only/cold-start/partial results.

Filters change only the rendered list. They do not delete messages, change read
state, alter selection records or modify WordPress.

## Frozen boundaries

- Core protocol, Core schema 9 and Core Wheel;
- Eitaa Scheduler and priorities;
- WordPress client and publish/update workflows;
- Runtime ownership and Installer behavior;
- Scroll math and UI 3.3 reading-position patch.

Only message serialization gains a sender key needed by conservative gallery
inference. No new Eitaa RPC is introduced.

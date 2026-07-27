# Local content index — isolated Lab plan

## Status

Architecture only. No classifier, index database, background worker, or UI
control from this proposal is included in GMI 1.

## Goal

Measure whether inexpensive local techniques can assign one or more useful
activity labels to Persian Eitaa messages without an online service or a large
language model. An example target is recognizing a theme such as memorial-site
maintenance from related wording even when the canonical category phrase is
absent.

## Lab boundary

The Lab must run in a separate folder, process and SQLite database against
synthetic or explicitly exported test data. It must not read the live Session,
write Core SQLite, invoke Eitaa RPC, occupy the Eitaa scheduler, or alter
WordPress. Promotion to the product requires a separate review and migration.

## Candidate pipeline

```text
message text
  -> PersianNormalizer
  -> exact/phrase rules
  -> weighted related-term rules
  -> lightweight multi-label model
  -> confidence + explanation
  -> human accept/reject/correct feedback
```

The first baseline should use:

- Arabic/Persian character normalization (`ي/ی`, `ك/ک`);
- whitespace, half-space, digit and punctuation normalization;
- user-defined phrases, exclusions and weighted related terms;
- word and character n-gram TF-IDF;
- a small one-vs-rest linear model such as logistic regression or SGD;
- explicit per-label thresholds and an `uncertain` result;
- stored explanations showing matched rules and model scores.

Feedback must be append-only training evidence, not immediate self-training on
every click. Retraining is a separate, cancellable Lab action with a model
version, dataset hash and evaluation report.

## Evaluation protocol

Use a manually labelled, de-identified test set split by time or source so near
duplicates do not leak across train/test. Report per-label precision, recall,
F1, confusion examples, coverage above threshold, CPU time, peak memory and
database growth. Compare at least:

1. exact phrases only;
2. weighted rule graph;
3. TF-IDF linear model;
4. rules plus model.

Promotion requires user-approved labels, useful precision at the chosen
threshold, stable explanations, bounded resource use on the target office PC,
and successful cancel/recovery/privacy tests.

## Proposed later UI

Only after Lab acceptance, a dialog-level `Index locally` command may start a
separate local job with progress, cancel and an error report. Results should be
reviewable before they influence search or WordPress category suggestions.
Automatic publishing and automatic category assignment remain prohibited.


# Phase 10-B Account Boundary and Layout Recovery Report — 2026-08-13

## Reported symptoms

1. Selecting or refreshing a conversation produced
   `peer_file is outside the selected MessengerAccount.`
2. At the observed `1146 x 912` browser size, the navigation, conversation
   list, and content pane occupied two half-height grid rows and left a large
   unused area.

## Account-boundary finding

The rejection was correct and prevented account-crossing file access. Phase 10
had copied all 427 legacy peer files into the selected account directory, but
the copied catalogue still contained the old `data/ui-peers/...` values. Before
repair:

- copied account-owned peer files present: 427
- copied account-owned peer files missing: 0
- catalogue rows pointing outside the account: 427

The repair is intentionally conservative. It changes a legacy path only when
the corresponding copied file exists below the selected account's catalogue
directory. It does not accept unrelated absolute paths or missing files.

After the controlled restart:

- catalogue rows inside the selected account: 427
- catalogue rows outside the selected account: 0
- provider authentication state: authenticated
- health: OK
- readiness: ready

The pre-repair catalogue is preserved at:

`backups/phase10-rollout/dialog-catalog-pre-rebase-20260813-194511-966.json`

- bytes: 437676
- SHA-256: `907430B71D26B6B7A1C9BA23813740890EA1FEB8CE1130691382BD3518F0B94F`

## Layout finding

The shell already used native CSS Grid. The defect was not a missing grid
primitive: an unscoped legacy `max-width: 1199px` rule assigned every
`.chats-pane` to grid column 1 and every `.messages-pane` to column 2. Those
generic selectors leaked from the retired `.three-column` layout into the
newer `.telegram-layout`. With a fourth fixed-position composer child, browser
auto-placement moved the rail to row 1 and the two main panes to row 2.

Observed before repair at `1146 x 912`:

- rail: `x=1074`, `y=0`, `72 x 456`
- conversations: `x=1074`, `y=456`, `72 x 456`
- content: `x=707.28`, `y=456`, `366.72 x 456`

Corrections:

- legacy column assignments are scoped to direct children of `.three-column`;
- the laptop `.telegram-layout` explicitly keeps rail, conversations, and
  content in grid row 1;
- the WordPress composer remains a fixed drawer below 1500 px and does not
  consume a grid track.

Visual fixture verification after repair at `1280 x 720`:

- rail: row 1, `72 x 720`
- conversations: row 1, `409.59 x 720`
- content: row 1, `798.41 x 720`
- no second grid row or unused left-side region

## Why the supplied MUI BasicGrid was not used directly

The sample is a valid 12-column proportional layout, but this shell needs one
fixed 72 px rail, a bounded conversation column, one fluid content column, and
a breakpoint-dependent fixed drawer. Native CSS Grid expresses those mixed
fixed/minmax/fluid tracks more directly than `size={8}`/`size={4}`. The failure
was caused by competing CSS generations, not by a limitation of either MUI
Grid or CSS Grid. Replacing the container with MUI Grid without removing the
leaking selectors would not by itself fix the placement bug.

## Verification

- Python account/API/catalog regression tests: 65 passed
- Phase 9 workspace assertions: 11/11 passed
- Phase 9 responsive/visual acceptance assertions: 10/10 passed
- Phase 10 local activation assertions: 7/7 passed
- TypeScript check: passed
- production UI build: passed
- live catalogue boundary scan: 427 inside, 0 outside
- live provider session: authenticated
- live health/readiness: passed

The local AppUser session is intentionally memory-bound and therefore requires
the operator to sign in again after the controlled service restart. The Eitaa
provider session remains authenticated.

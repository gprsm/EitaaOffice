# UI MVP Contract

## Layout

The application is RTL and uses four visual bands on large screens:

1. a narrow navigation rail on the far right;
2. dialogs: filters, favorites, search and unread state;
3. messages: virtualized history, local search, selection and media preview;
4. a tabbed third pane for WordPress composition and future conversation/community operations.

At narrower widths the dialog list and third pane become drawers over the message stream.

## State ownership

- Core owns Eitaa session, messages, media downloads, publications and protocol behavior.
- Bridge owns WordPress composition records, persistent dialog catalogue and the UI-facing application API.
- Electron renderer owns transient UI state.
- Electron main process owns API process lifecycle and IPC.

## Duplicate safety

Used messages are visually distinct and cannot enter a new composition without a future explicit reuse workflow. A multi-message composition maps every source to the same WordPress post ID.

## Existing-post behavior

For compositions created by the multi-message Composer, selecting a used source can load the saved relationship and current WordPress fields. The update action targets the same recorded WordPress Post ID and does not create a replacement post. Older single-message publication records remain view/open-only in this Composer.

## Scroll anchoring

When older messages are prepended, the renderer snapshots the scroll height and current offset, measures the virtual list after insertion, and restores the viewport relative to the previous first visible content. Users remain at their reading position and can scroll upward again for the next page.

## UI components

- daisyUI radio tabs for WordPress/Conversation operations and manual-add modes;
- daisyUI fieldsets, inputs, selects, textareas, neutral checkboxes and loading dots;
- React-Toastify for compact transient notifications;
- optional user-supplied IRANSans web font at `ui/fonts/IRANSansWeb.woff2`.

## Responsive breakpoints

- `>=1500px`: rail + dialogs + messages + third pane;
- `1200–1499px`: rail + dialogs + messages, third pane as a drawer;
- `<=1050px`: message-first layout with dialog and third-pane drawers.

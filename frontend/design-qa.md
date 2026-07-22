# Design QA — mobile document cards

- Source visual truth: screenshot attached by the user in the conversation; no local source path is available.
- Implementation screenshot: unavailable because the in-app browser is not exposed in this session.
- Viewport: source approximately 356 × 469 px; implementation viewport not captured.
- Source pixel dimensions: approximately 356 × 469 px.
- Implementation pixel dimensions: not available.
- CSS size and density normalization: not available.
- State: narrow document list with a regulation requiring acknowledgement and a regular document.

## Full-view comparison evidence

Blocked. The source screenshot is visible in the conversation, but a browser-rendered implementation screenshot could not be captured for a same-viewport comparison.

## Focused region comparison evidence

Blocked for the same reason. Static source inspection confirms that the card now uses stable rows for type, acknowledgement state, folder, title, metadata, and actions, but static inspection is not a visual comparison.

## Findings and fixes implemented

- P1: the fixed-width status/menu column squeezed the title and metadata. Fixed by removing that competing column and anchoring the overflow menu independently.
- P1: primary and secondary actions wrapped unpredictably. Fixed by placing the acknowledgement action on its own responsive row and keeping utility actions in a non-wrapping group.
- P2: folder and type badges competed in one wrapping row. Fixed by giving the folder path its own truncating row.
- P2: the chevron implied navigation while opening a menu. Fixed by using an overflow-menu icon.
- P2: document type could be duplicated. Fixed by rendering type once and reserving the status badge for acknowledgement state.
- P2: title and author text truncated or wrapped unpredictably. Fixed with a two-line title and stable mobile metadata rows.
- P2: compact icon targets and weak icon-only labels. Fixed with 44 px targets and explicit accessible labels.
- P2: the actions popup lacked complete menu semantics and Escape handling. Fixed with menu roles, relationships, and Escape dismissal.

## Required fidelity surfaces

- Fonts and typography: existing product typography preserved; title wrapping changed to two lines on narrow cards.
- Spacing and layout rhythm: source-level structure corrected; browser measurement blocked.
- Colors and visual tokens: existing application tokens preserved.
- Image quality and asset fidelity: no raster assets are used by this component.
- Copy and content: acknowledgement action changed to “Подтвердить ознакомление”; document type and acknowledgement state are no longer duplicated.

## Comparison history

- Initial source evidence showed squeezed metadata, inconsistent badge placement, and orphaned action buttons.
- Source fixes were implemented and passed ESLint, TypeScript, and the production Next.js build.
- A user-provided implementation screenshot then exposed a container-width regression: the viewport-level `sm` breakpoint put the acknowledgement button and five utility actions on one line inside a narrow sidebar column. The action area was changed to remain stacked according to its actual card width.
- A second user-provided screenshot showed that the safe stacked layout made the acknowledgement action unnecessarily full-width in a wide card. The card now establishes an inline-size container and switches to a compact horizontal action row only when the card itself is at least 32rem wide.
- A third screenshot showed that five 44px utility targets still exceeded the content width of an approximately 15rem card. The redundant “Details” icon is now hidden below a 20rem card width; the title and overflow menu continue to provide the same action, while four full-size utility targets remain visible.
- Post-fix browser evidence could not be captured in this session.

## Remaining blocker

A same-viewport browser capture and interaction check are still required to verify the final visual result.

final result: blocked

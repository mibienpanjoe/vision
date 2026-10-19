# Visual identity and agent-interface direction

**Status:** maintainer-selected direction, 2026-10-19; initial generated assets
are candidates, not final identity approval. No UI has been implemented.

## Identity reference

The supplied [Icon direction.png](../../Icon%20direction.png) is the original
reference and remains unchanged. It combines a charcoal open book, an arched
doorway in its right page, and warm gold light opening toward the spine. The
symbol connects reading with entering a visual world.

Preserve that motif, the recognizable page/doorway silhouette, the negative
space between pages, and a quiet warm/charcoal character. Do not substitute an
eye, generic AI sparkle, orb, or unrelated book icon. Derived files are separate
from the original reference.

The overview's editorial/cinematic UX remains useful input. Its exact colors,
fonts, and styling are not newly approved design tokens. Extracting colors from
a raster logo does not establish accessible text or control colors.

## Component direction

Use **shadcn/ui and Tailwind CSS** for the application foundation. Use selected
specialized agent-interface components where they serve the reconstruction
workflow. [Agents Kit](https://github.com/agents-ui/agents-kit) is the maintainer's
named reference. Its current project describes React components for chat, tools,
approvals, and generated output, with additional voice collections.

Candidate uses include a query composer, answer/result containers, source
references, structured work products, and visible processing/error states.
Choose exact components when implementing those flows. A component library does
not introduce multi-agent orchestration, voice, or decorative effects into the
product scope.

Keep Vision's entity/time/context/cutoff and evidence model authoritative. A
chat-shaped component must still support context-selection and insufficient-
evidence outcomes. Evidence should remain inspectable beside visual output;
do not conceal the workflow entirely inside a message transcript.

### Licensing and integration check

The inspected [Agents Kit license](https://github.com/agents-ui/agents-kit/blob/main/LICENSE.md)
is titled **Non-Commercial License** and restricts commercial use without
permission. Its [third-party notices](https://github.com/agents-ui/agents-kit/blob/main/THIRD_PARTY_NOTICES.md)
also identify upstream component sources and their notices. Referencing the
catalog is not permission to copy every component under one assumed license.

Before importing source, record the exact upstream revision, component origin,
applicable license/notices, dependencies, required CSS, and changes made. Confirm
the chosen use is permitted; where necessary obtain permission or select a
suitably licensed upstream alternative. No Agents Kit source is included here.

## Asset generation and exports

Use built-in image generation with the supplied raster reference for initial
logo derivatives. Generate a clean transparent primary mark first, then a
matching light mark for dark surfaces. The retained initial dark variant uses
an opaque charcoal tile after a transparent attempt failed visual inspection.
Preserve geometry between variants as
far as generation permits; inspect differences rather than assuming identical
pixels. Save prompts and output provenance with the assets.

Deterministic resizing/encoding can derive PNG/WebP/ICO exports from inspected
masters. Those conversions do not need another generative reinterpretation.
Image generation produces raster artwork: an SVG containing an embedded PNG is
not a genuine vector logo. A future true SVG requires deliberate vector work
and a separate fidelity check.

Proposed use targets:

| Target | Format / intended sizes | State |
|---|---|---|
| Light-surface primary mark | Transparent PNG master | Initial generated candidate |
| Dark-surface inverse mark | Opaque charcoal PNG tile, same motif | Inspected initial candidate; transparent inverse deferred |
| README / documentation | Theme-aware PNG, 96 px displayed | Wired to inspected candidates |
| Web app icon | PNG, 192 and 512 px | Exported; not wired to an application |
| Apple touch icon | Opaque PNG, 180 px | Exported on a warm neutral tile |
| Browser favicon | ICO, 16/32/48 px | Exported; 16 px detail is limited |
| Compact web asset | WebP with alpha | Lossless export present |
| Vector, wordmark, social card | True SVG / typography / composed image | Deferred; not supplied by the reference alone |

The [asset manifest](../../assets/brand/asset-manifest.md) owns actual filenames,
dimensions, generation provenance, prompts, conversion commands, and inspection
limitations. This table is a target list, not evidence every export exists.

## Review criteria

Inspect actual files on warm light and charcoal backgrounds, at full size and
at representative header/favicon sizes. Check the silhouette, transparent page
gaps, gold path, clean edges, absence of text/extra symbols, and adequate padding.
Verify alpha and file dimensions independently of visual appearance. A checkerboard
or black preview alone does not prove transparency.

Tiny sizes may need an optically simplified mark; do not claim favicon quality
from a large preview. Inspect every retained generated master and derivative
preview. Keep rejected generations outside the published asset set.

## Still to decide

Final logo approval, production palette/contrast pairs, font selections, spacing
and radius tokens, exact agent-interface components, and any wordmark remain
open. The direction authorizes exploration and initial assets; it is not proof
of a final accessible application theme.

# Visual identity and agent-interface direction

**Status:** logo approved by the maintainer; typography and theme selected under
maintainer delegation, 2026-10-19. T05 implements the themed foundation shell;
full library/reconstruction workflows remain pending.

## Identity reference

The supplied [Icon direction.png](../../Icon%20direction.png) is the original
reference and remains unchanged. It combines a charcoal open book, an arched
doorway in its right page, and warm gold light opening toward the spine. The
symbol connects reading with entering a visual world.

Preserve that motif, the recognizable page/doorway silhouette, the negative
space between pages, and a quiet warm/charcoal character. Do not substitute an
eye, generic AI sparkle, orb, or unrelated book icon. Derived files are separate
from the original reference.

## Theme

Use **warm paper, charcoal, and restrained gold**. Light mode feels like a
reading desk; dark mode provides the cinematic workspace. Keep source passages,
forms, and evidence easy to read in both. Artwork carries the visual atmosphere;
the surrounding interface stays quiet.

Follow the system color preference initially. Offer explicit light/dark choices
and retain the reader's choice. The immersive artwork viewer can use a charcoal
canvas in either theme without changing the surrounding research workspace.

### Semantic tokens

These are the selected design values, expressed as hex for review. Map them to
shadcn/ui CSS variables during implementation; copied agent components use the
same tokens. Gold identifies selection and emphasis rather than covering every
button or appearing as low-contrast body text.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `--background` | `#F8F7F4` | `#252527` | Main canvas |
| `--foreground` | `#242424` | `#F8F7F4` | Main text |
| `--card` | `#FFFFFF` | `#2F2F32` | Panels and raised surfaces |
| `--card-foreground` | `#242424` | `#F8F7F4` | Panel text |
| `--muted` | `#EFEDE8` | `#39393C` | Quiet inset areas |
| `--muted-foreground` | `#625E57` | `#BDB7AD` | Secondary text |
| `--primary` | `#242424` | `#F1D59D` | Primary action fill |
| `--primary-foreground` | `#F8F7F4` | `#252527` | Text on primary action |
| `--accent` | `#F4E5C8` | `#453B2A` | Selected item background |
| `--accent-foreground` | `#624415` | `#F1D59D` | Selected item text |
| `--border` | `#D8D4CD` | `#4A4845` | Decorative divisions |
| `--input` | `#8A847A` | `#8F897F` | Required control outline |
| `--ring` | `#8C641F` | `#E5BB6A` | Keyboard focus indicator |
| `--destructive` | `#A02E2A` | `#F6A9A3` | Destructive action fill |
| `--destructive-foreground` | `#FFFFFF` | `#252527` | Text on destructive action |

Use foreground colors for links, with an underline or another persistent link
cue. Decorative borders are deliberately subtle; they do not serve as the only
boundary of an interactive control. Input outlines and focus indicators use the
stronger tokens. Check hover, selected, disabled, and overlay combinations when
implementing them instead of reducing every text color with opacity.

The selected text pairs must meet a 4.5:1 contrast target; required control
outlines and focus indicators must meet 3:1 against their adjacent backgrounds.
Static token calculations do not establish WCAG conformance of a rendered UI.

## Typography

Use three families with distinct jobs; avoid introducing a fourth display font.

| Role | Family and weight | Starting treatment |
|---|---|---|
| Controls, navigation, metadata, forms | [Inter](https://rsms.me/inter/), 400/500/600 | 14 px / 20 px; normal body copy 16 px / 24 px |
| Editorial headings and narrative passages | [Source Serif 4](https://github.com/adobe-fonts/source-serif), 400/600 and true italic | Headings 28–40 px; reading text 18 px / 30 px, about 60–72 characters wide |
| JSON, schema fields, technical output | [Geist Mono](https://github.com/vercel/geist-font), 400/500 | 13 px / 20 px; tabular numbers for aligned data |

Inter keeps the dense workspace clear, Source Serif connects the reader to the
book, and Geist Mono makes structured output easy to scan. Use serif headings
selectively on the library and major book titles; panel labels and ordinary
controls stay in Inter. Do not impose uppercase tracking on long labels.

Self-host the needed font files through the application's font pipeline rather
than requiring a third-party font request at runtime. Load interface fonts first
and reader/JSON faces where needed. Include the applicable font notices when
bundling. Use `system-ui, sans-serif`, `Georgia, serif`, and
`ui-monospace, monospace` as respective fallbacks. Exact file versions, language
subsets, and loading behavior are settled in the executable frontend increment.

## Component treatment

Use a 4 px spacing base, with compact 8–12 px control gaps and 16–24 px panel
padding. Controls start with an 8 px radius; larger panels/dialogs start at
12 px. Nested corners should remain concentric. Reserve pill shapes for short
chips rather than turning every container into a capsule.

Keep structural dividers thin and shadows restrained. Give cover art and
visualizations a subtle outline; do not decorate ordinary panels with gold
borders or persistent glow. Use one icon set with `currentColor`, aligned to the
weight of adjacent text.

Use short color/opacity transitions for interaction. Avoid repeated entrance
animations while reading or querying; respect reduced motion. Progress needs a
plain state/stage label, and evidence categories need text labels—Explicit,
Inferred, Creative, Disputed, Unknown—rather than color alone. No animated orb,
neon effect, glass panels, or voice controls are implied by the component source.

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

Approved asset uses and remaining export work:

| Target | Format / intended sizes | State |
|---|---|---|
| Light-surface primary mark | Transparent PNG master | Approved retained mark |
| Dark-surface inverse mark | Opaque charcoal PNG tile, same motif | Approved opaque counterpart; transparent inverse deferred |
| README / documentation | Theme-aware PNG, 96 px displayed | Wired to approved retained assets |
| Web app icon | PNG, 192 and 512 px | Wired to the shell manifest; both exports served in browser checks |
| Apple touch icon | Opaque PNG, 180 px | Exported on a warm neutral tile |
| Browser favicon | ICO, 16/32/48 px | Exported; 16 px detail is limited |
| Compact web asset | WebP with alpha | Lossless export present |
| Vector, wordmark, social card | True SVG / typography / composed image | Deferred; not supplied by the reference alone |

The [asset manifest](../../assets/brand/asset-manifest.md) owns actual filenames,
dimensions, generation provenance, prompts, conversion commands, and inspection
limitations. The table distinguishes existing exports from deferred work.

## Review criteria

Inspect actual files on warm light and charcoal backgrounds, at full size and
at representative header/favicon sizes. Check the silhouette, transparent page
gaps, gold path, clean edges, absence of text/extra symbols, and adequate padding.
Verify alpha and file dimensions independently of visual appearance. A checkerboard
or black preview alone does not prove transparency.

Tiny sizes may need an optically simplified mark; do not claim favicon quality
from a large preview. Inspect every retained generated master and derivative
preview. Keep rejected generations outside the published asset set.

## Remaining implementation work

The logo approval and font/theme decisions are settled. Exact agent-interface
components, a wordmark or true vector source, and an optically simplified 16 px
favicon remain future work. The T05 shell uses the selected semantic tokens and self-hosted fonts with
[retained notices](../../apps/web/THIRD_PARTY_NOTICES.md). Build/type checks and
Chromium checks cover system/manual themes, retained preference, actual font/icon
delivery, 320 px overflow and keyboard skip-to-main. Light/dark/narrow screenshots
were inspected. Full populated interaction, contrast/accessibility and product
acceptance remain with their feature tasks; shell checks do not establish them.

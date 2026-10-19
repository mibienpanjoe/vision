# Vision brand asset manifest

**Status:** generated and inspected on 2026-10-19; retained logo assets approved
by the maintainer. Application icon wiring has not started.

## Sources and masters

The unchanged [original direction](../../Icon%20direction.png) is a 1254 × 1254
RGB PNG. Its SHA-256 is
`c95d03220884b7b55fbbac28b662f2f714a6a15e0d916143a167d553aa38346f`.

Built-in image generation produced a transparent primary extraction, then an
edge-cleanup pass. A transparent ivory variant was rejected for ragged alpha
edges and holes. An opaque dark-surface counterpart was generated instead and
retained after inspection. Exact [generation prompts](generation-prompts.md)
record the retained pipeline. No CLI image API or project image-rendering
integration was used.

| File | Dimensions | Transparency / intended use |
|---|---|---|
| [vision-mark.png](vision-mark.png) | 1254 × 1254 | RGBA; transparent primary master for light surfaces |
| [vision-mark-dark-tile.png](vision-mark-dark-tile.png) | 1254 × 1254 | Opaque ivory/gold counterpart on charcoal; dark README theme |
| [vision-mark-192.png](vision-mark-192.png) | 192 × 192 | Transparent primary derivative |
| [vision-mark-512.png](vision-mark-512.png) | 512 × 512 | Transparent primary derivative |
| [vision-mark.webp](vision-mark.webp) | 1254 × 1254 | Lossless WebP, alpha retained |
| [icon-192.png](icon-192.png) | 192 × 192 | Opaque warm neutral app-icon export |
| [icon-512.png](icon-512.png) | 512 × 512 | Opaque warm neutral app-icon export |
| [apple-touch-icon.png](apple-touch-icon.png) | 180 × 180 | Opaque warm neutral touch-icon export |
| [favicon.ico](favicon.ico) | 48, 32, and 16 px entries | Opaque warm neutral browser-icon export |

There is no true SVG, final wordmark, maskable-icon guarantee, or social card.
Do not label the opaque dark tile a transparent mark. The generated raster is
a faithful interpretation of the supplied motif, not a pixel-identical vector
trace. The dark counterpart is a separately generated color interpretation.

## Deterministic export commands

Run from the repository root with ImageMagick (`convert`/`identify` in the
environment used here). These commands derive raster sizes and encodings;
they do not regenerate the artwork.

```bash
convert assets/brand/vision-mark.png -resize 192x192 assets/brand/vision-mark-192.png
convert assets/brand/vision-mark.png -resize 512x512 assets/brand/vision-mark-512.png
convert assets/brand/vision-mark.png -define webp:lossless=true assets/brand/vision-mark.webp
convert assets/brand/vision-mark.png -background '#F8F7F4' -alpha remove -alpha off -resize 180x180 assets/brand/apple-touch-icon.png
convert assets/brand/vision-mark.png -background '#F8F7F4' -alpha remove -alpha off -resize 512x512 assets/brand/icon-512.png
convert assets/brand/icon-512.png -resize 192x192 assets/brand/icon-192.png
convert assets/brand/vision-mark.png -background '#F8F7F4' -alpha remove -alpha off -define icon:auto-resize=48,32,16 assets/brand/favicon.ico
```

## Inspection and limits

Viewed the original and generated masters, composited the primary over warm
light and charcoal backgrounds, and inspected the retained dark counterpart.
Checked the primary and dark marks at a 96 px header size, the 192/512 px and
touch-icon exports, and magnified each favicon entry. ImageMagick confirms the
listed dimensions, actual alpha in the primary PNG/WebP, and opacity in tile
exports. Lossless WebP is compared against the PNG master during verification.

The primary loses contrast against charcoal, so the README selects the dark
tile through `picture`. The rejected transparent inverse is not shipped. Minor
raster edge variation remains possible at master scale; approval of these raster
assets does not make them vector masters. At 32/48 px the book and doorway read more
clearly; at 16 px the fine page/doorway detail is limited. A dedicated simplified
favicon remains a future refinement, not an already completed export.

Local previews establish asset appearance, not GitHub's final HTML sanitization
or every browser's theme behavior. No application shell or manifest consumes
the icon exports yet. The selected palette and contrast tokens, plus the remaining
wordmark work, belong to the [visual identity](../../docs/design/visual-identity.md).

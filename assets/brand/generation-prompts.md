# Brand generation prompts

**Tool:** built-in image generation. The supplied raster is the authoritative
direction. Generated candidates are distinct files; the original is unchanged.

## Primary extraction

Input: `Icon direction.png`. Transparent background requested.

```text
Use case: logo-brand / background-extraction. Asset type: Vision primary logo mark for web header, README and app icons. Input image 1 is the authoritative edit target and visual identity direction. Create a single clean high-resolution isolated logo mark on a truly transparent background, no tile or white/off-white canvas. Preserve the reference logo's distinctive silhouette: dark charcoal open book with its tall curving central page on the left and right page forming an arched doorway; a warm soft golden illuminated doorway and a short golden path opening toward the lower central spine. Keep its left narrow outer cover, elegant rounded corners, negative-space white/transparent page gutter, and overall geometry/proportions faithful to reference. Remove only the off-white rounded square tile and outer white canvas. Simplify paper/grain texture into crisp professional flat charcoal and a restrained gold gradient, with clean antialiased edges. The doorway inner paper/light region can be warm ivory, but exterior and page gaps must be actually transparent. No text, no wordmark, no new symbols, no drop shadow around the isolated mark. Center mark and leave roughly 8 percent transparent safe padding. Output a single logo only.
```

## Primary edge refinement

Input: primary extraction result. Transparent background requested.
The retained refined output is `vision-mark.png`.

```text
Use case: precise-object-edit. Edit target: the isolated Vision book-and-doorway logo. Make a production-clean version with genuinely transparent background, preserving this EXACT layout, silhouette, charcoal page colors, warm gold doorway/path, dimensions and padding. Change ONLY the edge quality: remove the tiny colored red/yellow/blue fringes and noisy speckles visible along the vertical central spine, at the bottom central point, and along the lower diagonal edge of the golden path. Render every outer edge and transparent gap as clean smooth antialiased pixels without chromatic fringes, dark halos, white outline, stray pixels or grain. Preserve all intended gold pixels in doorway and path. No redesign, no new text, no tile, no shadows, no extra symbols. This is a cleanup pass, keep the visual identity unchanged.
```

## Dark-surface counterpart

Input: `vision-mark.png`. Opaque background requested. A preceding transparent
ivory attempt was rejected after inspection because of irregular alpha edges
and holes; it is not part of the retained asset set.

```text
Use case: precise-object-edit. Asset: Vision dark-mode logo, same exact book-and-doorway silhouette as supplied reference. Preserve the input logo's geometry, framing and gold doorway/path. Recolor ONLY charcoal book/page shapes to solid warm ivory #F8F7F4, and put the mark on a perfectly uniform solid charcoal #252527 background. Page gaps and exterior must be this same charcoal background, no alpha transparency requested. Keep all edges pristine smooth and continuous with NO grunge, holes, missing chunks, outlines, halos or distressed texture. The book cover and pages must have clean solid ivory surfaces, not torn or speckled. Gold doorway and path retain restrained warm gold gradient and original position. A single centered logo on charcoal, no text, no wordmark, no rounded-square border, no extra symbols, no glow. This is a strict color variant of supplied image, not a redesign. The entire square canvas is opaque charcoal.
```

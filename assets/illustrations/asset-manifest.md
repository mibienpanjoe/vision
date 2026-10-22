# Interface illustration manifest

**Status:** generated, inspected in both themes and wired on 2026-10-22 at the
maintainer's request ([visual identity](../../docs/design/visual-identity.md#interface-illustrations)).

These are decorative spot illustrations derived from the book-and-doorway mark.
They depict no people, story scenes or narrative content, so they cannot be read
as a reconstruction of anyone's book. They are not evidence and carry no alt text.

## Generation

OpenAI `gpt-image-1`, quality `medium`, PNG, `n: 1`, called directly with the
maintainer's API key (not through the render pipeline or its acceptance budget).
Each motif was generated twice: a light variant on pure white and a dark variant
on pure black. Every prompt is the subject sentence followed by the shared style
and the theme sentence:

| Motif | Size | Subject |
|---|---|---|
| `sign-in` | 1024 × 1536 | A large open book seen from slightly above. On its right-hand page stands an open arched doorway, and warm gold light spills out of it across the pages. Through the doorway, a faint sketched landscape of rolling hills and one distant tree, its ink lines rising softly out of the page. |
| `library` | 1536 × 1024 | A short row of leaning hardback books on a simple wooden shelf; at the end of the row one book stands open, and its right-hand page holds a small arched doorway glowing with warm gold light. |
| `workspace` | 1024 × 1536 | Light: A tall narrow arched doorway standing open on a sheet of paper; a soft beam of warm gold light falls out of it across a few loose abstract horizontal ink strokes; a thin ink path winds through the doorway into pale distance. Dark: the same, with "on a sheet of paper" replaced by "drawn directly on the background with no paper, card or panel behind it". |
| `empty` | 1024 × 1024 | A single closed hardback book lying flat, a small arched doorway outlined on its cover, a soft gold glow beneath it, and two loose blank pages drifting above. |

Shared style: "Delicate ink-and-wash editorial illustration for a quiet literary
reading app. Fine hand-drawn pen linework, soft translucent washes, generous
empty space around the subject, the subject centered with wide margins. No text,
no letters, no writing, no numbers, no people, no faces, no hands, no animals, no
frame, no border, no vignette, no shadow on the background."

Light theme: "Charcoal-black ink lines (#242424), warm grey wash, and restrained
warm gold light (#c8963e). Background is pure flat white (#ffffff) edge to edge."
Dark theme: "Warm ivory lines (#f1e8d8), muted smoky wash, and restrained warm
gold light (#e5bb6a). Background is pure flat black (#000000) edge to edge."

One generation was rejected: the first dark `workspace` drew an ivory paper card
on black, which would show as a bright panel in dark mode. Masters stay in the
ignored `.local/illustrations/`; their SHA-256 digests identify them:

| Master | SHA-256 |
|---|---|
| `sign-in-light.png` | `aec8a5a8abd55b80b599d4d4db234ca7ad07fe8eb868e12ff8ae2379ffd59bf1` |
| `sign-in-dark.png` | `ef67c3c24e0579c8ef583e414c38e98266503ec064839e8c11004c4c90ec44ca` |
| `library-light.png` | `d2fe197d13f1132c74431b2aaa759042ce484e7d362390c7c53d9435bc49019f` |
| `library-dark.png` | `68404b56fb39087e48f702275cde5fd726012dfcd3b914f853165a2b9fcf3569` |
| `workspace-light.png` | `d24704c8ef3c444bdc21805dbd0e17d2d265e7392d7d21199ef9e5ad29f27bfe` |
| `workspace-dark.png` | `64e67f10b0068cd9455f3d904f06516875cc257dc16b7eac01830a76fb5978de` |
| `empty-light.png` | `068dc283801ea00b8b5cddd7ba7fae7ed43b719d103edbf36d87a8434900c1f7` |
| `empty-dark.png` | `d0aeb1fb01cbb00f81d0b95c07170909e382ea72373c9937c4ba3c90a22186a8` |

## Deterministic processing

Pillow, without regeneration: levels force the background to pure white
(`v × 255/235`, light) or pure black (`(v − 18) × 255/237`, dark); an 8 % Gaussian
edge feather fades every border into that background, hiding crops; Lanczos
resizing to about twice the displayed width; WebP quality 82, method 6.

| File | Dimensions | Bytes | Used by |
|---|---|---|---|
| `sign-in-{light,dark}.webp` | 1024 × 1536 | 49,312 / 62,820 | Sign-in, beside the form (square centered crop in CSS) |
| `library-{light,dark}.webp` | 768 × 512 | 38,904 / 29,596 | Library heading, signed in |
| `workspace-{light,dark}.webp` | 512 × 768 | 13,150 / 14,698 | Book workspace, sticky under the entity list |
| `empty-{light,dark}.webp` | 384 × 384 | 6,466 / 10,404 | Empty library and no-matching-entities states |

The interface shows only the active theme's variant and blends it with
`mix-blend-mode: multiply` (light) or `screen` (dark), so the pure background
disappears into the page or card surface. The art is `aria-hidden`, has empty
alt text, and is hidden below 56rem (library/sign-in) or 36rem (workspace).

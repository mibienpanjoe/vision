# Web asset notices

Font files are bundled locally from these pinned Fontsource packages. No external
font service is contacted at application runtime. Latin subsets include the
accented fixture names; this is not a multilingual product-quality claim.

| Family | Package version | Font license copy served with the application |
|---|---|---|
| Inter | `@fontsource/inter` 5.3.0 | [SIL OFL](public/notices/inter-OFL.txt) |
| Source Serif 4 | `@fontsource/source-serif-4` 5.3.1 | [SIL OFL](public/notices/source-serif-4-OFL.txt) |
| Geist Mono | `@fontsource/geist-mono` 5.3.0 | [SIL OFL](public/notices/geist-mono-OFL.txt) |

Notices are copied verbatim from the locked packages. Retain notices and review
them when changing versions. UI weights: Inter 400/500/600; Source Serif 400/600
and true 400 italic; Geist Mono 400/500. Fallbacks are in app/globals.css.

The shadcn/ui foundation uses the documented manual configuration and its small
clsx/tailwind-merge helper pattern. No specialized Agents Kit component source is
included. Package licenses remain in their installed distributions; future copied
components require exact source/license records before integration.

Vision's approved logo remains in the repository's canonical assets/brand folder
and is imported directly. Favicon, Apple and manifest icons are byte-identical
application exports of those approved files. Their provenance and small-size
limitations remain owned by the [asset manifest](../../assets/brand/asset-manifest.md).

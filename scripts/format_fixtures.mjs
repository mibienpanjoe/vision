// Regenerates synthetic PDF fixtures from the annotated narrative corpus.
// Run from the repository root: node scripts/format_fixtures.mjs
import { execFileSync } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";

const require = createRequire(resolve("apps/web/package.json"));
const { chromium } = require("@playwright/test");
const out = resolve("apps/api/tests/fixtures/formats");
const story = readFileSync("apps/api/tests/fixtures/narrative/story.md", "utf8");

const escape = (value) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const blocks = story.trim().split(/\n\n/).map((block) => {
  if (block.startsWith("## ")) return `<h2>${escape(block.slice(3))}</h2>`;
  if (block.startsWith("# ")) return `<h1>${escape(block.slice(2))}</h1>`;
  return `<p>${escape(block)}</p>`;
});
const html = `<!doctype html><meta charset="utf-8"><style>
body { font: 12pt "DejaVu Serif", serif; margin: 0; }
h2 { break-before: page; font-size: 16pt; }
h1 + h2 { break-before: auto; }
</style>${blocks.join("\n")}`;

mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setContent(html);
  await page.pdf({ path: `${out}/story.pdf`, format: "A5", margin: { top: "2cm", bottom: "2cm", left: "2cm", right: "2cm" } });
} finally {
  await browser.close();
}
const gs = (args) => execFileSync("gs", ["-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", ...args]);
// Text converted to vector outlines: no extractable text layer, as in a scan.
gs(["-dNoOutputFonts", `-sOutputFile=${out}/outlined.pdf`, `${out}/story.pdf`]);
gs(["-sOwnerPassword=vision-owner", "-sUserPassword=vision-user", `-sOutputFile=${out}/encrypted.pdf`, `${out}/story.pdf`]);

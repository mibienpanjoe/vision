import assert from "node:assert/strict";
import test from "node:test";
import { highlightSegments } from "../features/reader/highlight.ts";

test("highlights use code points and retain overlapping evidence membership", () => {
  const text = "é🦊é <Arthur>";
  const span = (start, end, quote) => ({ document_revision_id: "d", passage_id: "p", start, end, quote });
  const segments = highlightSegments(text, 0, [
    { id: "unicode", label: "Unicode", span: span(1, 4, "🦊é") },
    { id: "accent", label: "Accent", span: span(2, 4, "é") },
    { id: "markup", label: "Markup", span: span(5, 13, "<Arthur>") },
  ]);
  assert.equal(segments.map(s => s.text).join(""), text);
  assert.equal(segments.filter(s => s.ids.includes("unicode")).map(s => s.text).join(""), "🦊é");
  assert.deepEqual(segments.find(s => s.text === "é").ids, ["unicode", "accent"]);
  assert.equal(segments.filter(s => s.ids.includes("markup")).map(s => s.text).join(""), "<Arthur>");
});

test("altered, normalized or out-of-excerpt anchors receive no invented highlight", () => {
  const span = { document_revision_id: "d", passage_id: "p", start: 11, end: 13, quote: "é" };
  const segments = highlightSegments("é", 11, [{ id: "changed", label: "Changed", span }]);
  assert.equal(segments.some(s => s.ids.length), false);
});

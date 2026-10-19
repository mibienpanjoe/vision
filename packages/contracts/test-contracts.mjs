import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { sourceSlice, validateSpan } from "./source-span.ts";

const schema = JSON.parse(readFileSync(new URL("schema.json", import.meta.url)));
const cases = JSON.parse(readFileSync(new URL("conformance.json", import.meta.url)));
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
for (const [index, item] of cases.entries()) {
  test(`shared conformance ${index}: ${item.model}`, () => {
    const validator = ajv.getSchema(`${schema.$id}#/$defs/${item.model}`);
    assert.ok(validator, item.model);
    let valid = validator(item.value);
    if (valid) {
      try {
        if (item.model === "SourceSpan") validateSpan(item.value);
        if (item.model === "SpanResolution" && item.value.outcome === "resolved") validateSpan(item.value.data);
      } catch { valid = false; }
    }
    assert.equal(valid, item.valid, JSON.stringify(validator.errors));
  });
}
test("code-point source slices reject altered or normalized evidence", () => {
  const span = { document_revision_id: "r", passage_id: "p", start: 1, end: 2, quote: "🦊" };
  assert.equal(sourceSlice("é🦊é", span), "🦊");
  assert.throws(() => sourceSlice("éXé", span));
  assert.throws(() => sourceSlice("", span));
  const decomposed = { ...span, start: 2, end: 4, quote: "é" };
  assert.equal(sourceSlice("é🦊é", decomposed), "é");
  assert.throws(() => sourceSlice("é🦊é", decomposed));
});

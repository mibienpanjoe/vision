import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const api = fileURLToPath(new URL("../../apps/api", import.meta.url));
const source = execFileSync("uv", ["run", "--project", api, "--locked", "python", "-c",
  "import json; from app.schemas.common import SchemaCatalog; print(json.dumps(SchemaCatalog.model_json_schema(), sort_keys=True))"],
  { cwd: api, encoding: "utf8" });
const schema = { $schema: "https://json-schema.org/draft/2020-12/schema", $id: "urn:vision:contracts:1.0", ...JSON.parse(source) };
const json = JSON.stringify(schema, null, 2) + "\n";
const declarations = await compile(schema, "SchemaCatalog", {
  bannerComment: "/* Generated from Python Pydantic models. Run pnpm --dir packages/contracts generate. */",
  style: { singleQuote: false },
});
for (const [name, content] of [["schema.json", json], ["index.ts", declarations]]) {
  const path = new URL(name, import.meta.url);
  let previous;
  try { previous = readFileSync(path, "utf8"); } catch (error) { if (error.code !== "ENOENT") throw error; }
  if (previous !== content) writeFileSync(path, content);
}

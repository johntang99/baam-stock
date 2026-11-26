// Generates generated/index.ts (TS types) from schemas/*.schema.json.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schemaDir = path.join(root, "schemas");
const outDir = path.join(root, "generated");
fs.mkdirSync(outDir, { recursive: true });

const common = JSON.parse(fs.readFileSync(path.join(schemaDir, "common.schema.json"), "utf8"));
// Inline common $defs so each entity compiles standalone; shared names are emitted once.
const commonDefs = common.$defs;
const rewrite = (node) => {
  if (Array.isArray(node)) return node.map(rewrite);
  if (node && typeof node === "object") {
    const out = {};
    for (const [k, v] of Object.entries(node)) {
      if (k === "$ref" && typeof v === "string" && v.startsWith("common.schema.json#/$defs/")) out[k] = "#/$defs/" + v.split("/").pop();
      else if (k === "x-tabled") continue;
      else out[k] = rewrite(v);
    }
    return out;
  }
  return node;
};

const header = `/* AUTO-GENERATED from packages/contracts/schemas by scripts/gen-ts.mjs. Do not edit. */\n`;
const parts = [];
const seen = new Set();
const files = fs.readdirSync(schemaDir).filter((f) => f.endsWith(".schema.json") && f !== "common.schema.json").sort();
for (const f of files) {
  const s = rewrite(JSON.parse(fs.readFileSync(path.join(schemaDir, f), "utf8")));
  s.$defs = rewrite(commonDefs);
  for (const [k, d] of Object.entries(s.$defs)) d.title = d.title ?? k;
  let ts = await compile(s, s.title, { bannerComment: "", additionalProperties: false, declareExternallyReferenced: true, unreachableDefinitions: false, format: false });
  // drop duplicate shared declarations
  const blocks = ts.split(/\n(?=export )/);
  for (const blk of blocks) {
    const m = blk.match(/^export (?:type|interface) (\w+)/);
    if (m && seen.has(m[1])) continue;
    if (m) seen.add(m[1]);
    parts.push(blk.trim());
  }
}
parts.push(`export const SCHEMA_VERSION = ${JSON.stringify(commonDefs.schema_version.const)} as const;`);
fs.writeFileSync(path.join(outDir, "index.ts"), header + parts.join("\n\n") + "\n");
console.log(`generated/index.ts: ${seen.size} types`);

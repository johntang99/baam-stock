// Validates every schema compiles and every examples/<entity>.<case>.json passes its schema,
// plus contract rules JSON Schema cannot express (DC §1, §3.4 D-46, §3.6).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schemaDir = path.join(root, "schemas");
const exampleDir = path.join(root, "examples");
const schemasOnly = process.argv.includes("--schemas-only");

const ajv = new Ajv2020({ allErrors: true, strict: true, strictTuples: false });
addFormats(ajv);
ajv.addKeyword("x-tabled");

const files = fs.readdirSync(schemaDir).filter((f) => f.endsWith(".schema.json"));
for (const f of files) ajv.addSchema(JSON.parse(fs.readFileSync(path.join(schemaDir, f), "utf8")));
const validators = {};
for (const f of files) {
  const name = f.replace(".schema.json", "");
  if (name === "common") continue;
  validators[name] = ajv.getSchema(`https://baam-stock.local/contracts/${f}`);
}
console.log(`schemas: ${Object.keys(validators).length} entity schemas compiled`);
if (schemasOnly) process.exit(0);

const problems = [];
const semantic = (entity, ex, file) => {
  if (ex.probabilities) {
    const sum = Object.values(ex.probabilities).reduce((a, b) => a + b, 0);
    if (Math.abs(sum - 1) > 1e-6) problems.push(`${file}: probabilities sum ${sum} != 1 (DC §1)`);
  }
  if (entity === "benchmark_versions") {
    const sum = ex.constituents.reduce((a, c) => a + c.weight, 0);
    if (Math.abs(sum - 1) > 1e-5) problems.push(`${file}: constituent weights sum ${sum} != 1`);
  }
  const me = ex.market_explanation;
  if (me) {
    for (const k of ["observed_facts", "possible_drivers", "counter_evidence"]) {
      for (const st of me[k] ?? []) {
        if (st.evidence_ids.length + st.quote_ids.length === 0)
          problems.push(`${file}: market_explanation.${k} statement without citation (D-46)`);
      }
    }
  }
  if (entity === "predictions" && ex.status === "abstained" && !ex.abstain_reason)
    problems.push(`${file}: abstained prediction needs abstain_reason (DC §1 null-reason rule)`);
  if (entity === "predictions" && ex.sampling_rule === "schedule_slot" && !ex.schedule_slot_id)
    problems.push(`${file}: schedule_slot prediction needs schedule_slot_id`);
};

const examples = fs.readdirSync(exampleDir).filter((f) => f.endsWith(".json")).sort();
let ok = 0;
for (const f of examples) {
  const entity = f.split(".")[0];
  const v = validators[entity];
  if (!v) { problems.push(`${f}: no schema named ${entity}`); continue; }
  const ex = JSON.parse(fs.readFileSync(path.join(exampleDir, f), "utf8"));
  if (!v(ex)) {
    problems.push(`${f}: ${ajv.errorsText(v.errors, { separator: "\n    " })}`);
    continue;
  }
  semantic(entity, ex, f);
  ok++;
}
if (problems.length) {
  console.error(`FAIL\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log(`examples: ${ok}/${examples.length} valid`);

// Runs the device triage engine (src/lib/triage/engine.ts) in Node on patients read from stdin and prints the results.
// Used by backend/tests/test_device_rules.py to check the device and the server give the same colours and rules.
// stdin: {"cases": [{"intake": {...}, "age": 40, "sex": "F"} or {"scan": "a sentence"}, ...]}   stdout: one result per case
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/lib/triage/engine.ts"), "utf8");
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const dir = mkdtempSync(join(tmpdir(), "jeevia-rules-"));
try {
  writeFileSync(join(dir, "engine.mjs"), js);
  const { createEngine } = await import(pathToFileURL(join(dir, "engine.mjs")).href);
  const engine = createEngine(JSON.parse(readFileSync(join(here, "../src/lib/triage/rulepack.json"), "utf8")));
  const { cases } = JSON.parse(readFileSync(0, "utf8"));
  // A case with "scan" checks the word matcher alone: {finding: true/false} for one sentence.
  const run = (c) => (c.scan !== undefined ? Object.fromEntries(Object.entries(engine.scanText(c.scan, "")).map(([k, f]) => [k, f.value])) : engine.evaluate(c.intake, c.age, c.sex ?? null));
  process.stdout.write(JSON.stringify(cases.map(run)));
} finally {
  rmSync(dir, { recursive: true, force: true });
}

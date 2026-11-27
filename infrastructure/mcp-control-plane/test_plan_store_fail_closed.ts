import assert from "node:assert/strict";
import fs from "node:fs";
import { recordLearning } from "./src/learning/learning_gate.js";
import { savePlan } from "./src/planning/plan_store.js";

// Exercise the real persistence path with a simulated unwritable destination.
// No fixture is written and no actual store is touched.
const originalRead = fs.readFileSync;
const originalMkdir = fs.mkdirSync;
try {
  fs.readFileSync = (() => { const e = new Error("fixture") as NodeJS.ErrnoException; e.code = "ENOENT"; throw e; }) as typeof fs.readFileSync;
  fs.mkdirSync = (() => { throw new Error("private fixture"); }) as typeof fs.mkdirSync;
  assert.throws(() => savePlan({ planId: "fixture" } as never), /^Error: Plan store write failed$/);
  assert.throws(() => recordLearning({tier: "semantic", fact: "fixture"}), /^Error: Learning store write failed$/);
  fs.readFileSync = (() => "not json") as typeof fs.readFileSync;
  assert.throws(() => savePlan({ planId: "fixture" } as never), /^Error: Plan store unavailable or invalid$/);
  assert.throws(() => recordLearning({tier: "semantic", fact: "fixture"}), /^Error: Learning store unavailable or invalid$/);
  fs.readFileSync = (() => '{"plans":false}') as typeof fs.readFileSync;
  assert.throws(() => savePlan({ planId: "fixture" } as never), /^Error: Plan store unavailable or invalid$/);
} finally {
  fs.readFileSync = originalRead;
  fs.mkdirSync = originalMkdir;
}
console.log("Plan store fail-closed checks passed");

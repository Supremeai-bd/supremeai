import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExecutionPlan } from "./planner.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STORE_PATH = path.resolve(__dirname, "../../data/plan_store.json");

interface StoreShape {
  plans: ExecutionPlan[];
}

function load(): StoreShape {
  try {
    const raw = fs.readFileSync(STORE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as StoreShape;
    if (!parsed || !Array.isArray(parsed.plans)) throw new Error("Invalid plan store");
    return parsed;
  } catch (err) {
    if ((err as NodeJS.ErrnoException)?.code === "ENOENT") return { plans: [] };
    // Never silently replace an unreadable or corrupt store with an empty one.
    throw new Error("Plan store unavailable or invalid");
  }
}

function save(store: StoreShape): void {
  // Atomic replacement avoids truncating the last good store on a failed write.
  // This does not provide concurrency control across processes.
  let temp: string | undefined;
  try {
    fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
    temp = path.join(fs.mkdtempSync(path.join(path.dirname(STORE_PATH), ".plan-store-")), "store.json");
    fs.writeFileSync(temp, JSON.stringify(store, null, 2), { encoding: "utf-8", mode: 0o600 });
    fs.renameSync(temp, STORE_PATH);
  } catch {
    throw new Error("Plan store write failed");
  } finally {
    if (temp) {
      try { fs.rmSync(path.dirname(temp), { recursive: true, force: true }); }
      catch { console.error("Plan store temporary cleanup failed"); }
    }
  }
}

export function savePlan(plan: ExecutionPlan): ExecutionPlan {
  const store = load();
  const idx = store.plans.findIndex((p) => p.planId === plan.planId);
  if (idx >= 0) store.plans[idx] = plan;
  else store.plans.push(plan);
  save(store);
  return plan;
}

export function getPlan(planId: string): ExecutionPlan | null {
  const store = load();
  return store.plans.find((p) => p.planId === planId) ?? null;
}

export function listPlans(limit = 20): ExecutionPlan[] {
  const store = load();
  return store.plans.slice(-Math.min(Math.max(1, limit), 100)).reverse();
}

export function updatePlanStatus(planId: string, status: ExecutionPlan["status"]): ExecutionPlan | null {
  const store = load();
  const plan = store.plans.find((p) => p.planId === planId);
  if (!plan) return null;
  plan.status = status;
  save(store);
  return plan;
}

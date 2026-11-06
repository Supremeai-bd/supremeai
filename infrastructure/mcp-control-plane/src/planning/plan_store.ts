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
    if (fs.existsSync(STORE_PATH)) {
      const raw = fs.readFileSync(STORE_PATH, "utf-8");
      const parsed = JSON.parse(raw) as StoreShape;
      if (parsed && Array.isArray(parsed.plans)) return parsed;
    }
  } catch {
    // ignore
  }
  return { plans: [] };
}

function save(store: StoreShape): void {
  try {
    fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
    fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2), "utf-8");
  } catch {
    // best-effort
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

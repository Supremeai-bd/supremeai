import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { env } from "../lib/env.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");
const REGISTRY_PATH = path.join(REPO_ROOT, "config", "service_registry.yaml");

export interface AuthoritativeServiceTarget {
  name: string;
  role: string;
  platform: string;
  renderAccountId: string;
  renderServiceId: string;
  runtimeUrl: string;
  healthPath: string;
  readinessPath: string;
  releasePath: string;
  repo: string;
  branch: string;
  watchPaths?: string[];
}

/**
 * Account ID mapping fallback for Render services based on service key.
 * Mirrors account.registry.ts Render accounts 1..6 and paykari.
 */
const ACCOUNT_MAP: Record<string, string> = {
  api: "render-api",
  core: "render-primary",
  worker: "render-worker",
  scraper: "render-scraper",
  mcp: "render-mcp",
  brain: "render-brain",
  "ci-runner": "render-paykari",
};

/**
 * Lightweight, zero-dependency YAML service registry parser.
 * Reads config/service_registry.yaml directly to provide authoritative topology.
 */
export function loadAuthoritativeServices(): Record<string, AuthoritativeServiceTarget> {
  const result: Record<string, AuthoritativeServiceTarget> = {};

  if (!fs.existsSync(REGISTRY_PATH)) {
    return result;
  }

  const raw = fs.readFileSync(REGISTRY_PATH, "utf-8");
  const lines = raw.split(/\r?\n/);

  let inServices = false;
  let currentKey = "";
  let currentBlock: Record<string, string> = {};
  let currentLists: Record<string, string[]> = {};
  let currentListKey = "";

  function flush() {
    if (currentKey && currentBlock.render_name) {
      const renderAccountId = ACCOUNT_MAP[currentKey] || "render-primary";
      const envIdVar = currentBlock.canonical_service_id_env;
      const envUrlVar = currentBlock.canonical_url_env;
      let renderServiceId = (envIdVar ? process.env[envIdVar] : "") || currentBlock.render_service_id || "";
      let runtimeUrl = (envUrlVar ? process.env[envUrlVar] : "") || currentBlock.production_url || "";

      if (!renderServiceId || !runtimeUrl) {
        const envKey = currentKey === "ci-runner" ? "ciRunner" : currentKey === "mcp" ? "controlTower" : currentKey;
        const envRenderObj = (env.render as Record<string, any>)?.[envKey];
        if (envRenderObj) {
          if (!renderServiceId && envRenderObj.serviceId) renderServiceId = envRenderObj.serviceId;
          if (!runtimeUrl && envRenderObj.url) runtimeUrl = envRenderObj.url;
        }
      }

      result[currentKey] = {
        name: currentKey,
        role: currentBlock.role || "",
        platform: currentBlock.platform || "render",
        renderAccountId,
        renderServiceId,
        runtimeUrl,
        healthPath: currentBlock.health_path || "/health",
        readinessPath: currentBlock.readiness_path || "/health",
        releasePath: currentBlock.release_path || "/release",
        repo: currentBlock.source_repo || "Supremeai-bd/supremeai",
        branch: currentBlock.branch || "main",
        watchPaths: currentLists.watch_paths || [],
      };
    }
    currentBlock = {};
    currentLists = {};
    currentListKey = "";
  }

  for (const line of lines) {
    if (line.trim().startsWith("#") || !line.trim()) continue;

    if (line.startsWith("services:")) {
      inServices = true;
      continue;
    }

    if (!inServices) continue;

    const topMatch = line.match(/^  ([a-zA-Z0-9_-]+):$/);
    if (topMatch) {
      flush();
      currentKey = topMatch[1];
      continue;
    }

    if (currentKey) {
      // Check for list item under current list key
      const listItemMatch = line.match(/^\s{6,8}-\s*["']?(.*?)["']?\s*$/);
      if (listItemMatch && currentListKey) {
        if (!currentLists[currentListKey]) currentLists[currentListKey] = [];
        currentLists[currentListKey].push(listItemMatch[1]);
        continue;
      }

      if (line.startsWith("    ")) {
        const propMatch = line.trim().match(/^([a-zA-Z0-9_-]+):\s*(.*)$/);
        if (propMatch) {
          const key = propMatch[1];
          let val = propMatch[2].trim();
          if (val === "" || val === "[]") {
            currentListKey = key;
            currentLists[key] = [];
            continue;
          }
          currentListKey = "";
          if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
            val = val.slice(1, -1);
          }
          currentBlock[key] = val;
        }
      }
    }
  }

  flush();
  return result;
}

export function resolveServiceTarget(serviceName: string): AuthoritativeServiceTarget | null {
  const catalog = loadAuthoritativeServices();
  const normalized = serviceName.trim().toLowerCase();

  // Direct hit or alias resolution
  if (catalog[normalized]) return catalog[normalized];

  if (normalized === "backend-api" || normalized === "gateway") {
    return catalog["api"] ?? null;
  }
  if (normalized === "primary" || normalized === "supremeai-core") {
    return catalog["core"] ?? null;
  }
  if (normalized === "browser") {
    return catalog["scraper"] ?? null;
  }
  if (normalized === "tower" || normalized === "control-tower") {
    return catalog["mcp"] ?? null;
  }
  if (normalized === "tiny-brain") {
    return catalog["brain"] ?? null;
  }

  return null;
}

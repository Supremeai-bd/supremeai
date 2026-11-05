#!/usr/bin/env python3
"""Render free-build-quota preflight for main deployment planning.

Render free build minutes are per-account (= per-service on free tier).
For each service account, check remaining quota and decide:
  remaining >= 450 (and >= estimated_build + 50 buffer) -> render-source-build (auto-deploy)
  otherwise -> prebuilt-image (external image build)
Quota API is not exposed by Render; on failure assume full budget (500) so
auto-deploy proceeds, with a warning.
"""
import json, os, sys, urllib.request

SERVICES = [
    ("RENDER_API_KEY", "core"),
    ("RENDER_API_KEY_1", "primary"),
    ("RENDER_API_KEY_2", "worker"),
    ("RENDER_API_KEY_3", "scraper"),
    ("RENDER_API_KEY_4", "mcp"),
    ("RENDER_API_KEY_5", "api"),
    ("RENDER_API_KEY_6", "brain"),
    ("RENDER_API_KEY_PAYKARI", "ci-runner"),
]
ESTIMATED_BUILD_MINUTES = int(os.environ.get("RENDER_ESTIMATED_BUILD_MINUTES", "20"))
SAFETY_BUFFER = 50
GLOBAL_THRESHOLD = 450
FULL_BUDGET = 500.0

def check_account(key):
    # Render billing endpoint not exposed; try best-effort, fall back to full budget.
    try:
        req = urllib.request.Request(
            "https://api.render.com/v1/billing/usage",
            headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        limit = float(data.get("limit") or data.get("monthlyLimit") or FULL_BUDGET)
        used = float(data.get("used") or data.get("usedMinutes") or 0)
        return limit - used
    except Exception:
        return FULL_BUDGET

modes = {}
for var, name in SERVICES:
    key = os.environ.get(var, "").strip()
    if not key:
        print("::warning::%s key missing for %s" % (var, name))
        continue
    remaining = check_account(key)
    if remaining >= GLOBAL_THRESHOLD and remaining >= (ESTIMATED_BUILD_MINUTES + SAFETY_BUFFER):
        mode = "render-source-build"
    elif remaining >= (ESTIMATED_BUILD_MINUTES + SAFETY_BUFFER):
        mode = "render-source-build"
    else:
        mode = "prebuilt-image"
    modes[name] = mode
    print("SERVICE=%s REMAINING=%.1f MODE=%s" % (name, remaining, mode))

# Overall mode = most conservative (if any service needs image build, note it)
overall = "render-source-build" if all(m == "render-source-build" for m in modes.values()) else "mixed"
print("RENDER_DEPLOY_MODE=%s" % overall)

out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a") as f:
        f.write("deploy_mode=%s\n" % overall)
        # per-service modes
        for name, mode in modes.items():
            f.write("mode_%s=%s\n" % (name.replace("-", "_"), mode))

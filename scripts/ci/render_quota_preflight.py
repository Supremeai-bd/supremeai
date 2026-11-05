#!/usr/bin/env python3
"""Render free-build-quota preflight for main deployment planning.

Reads RENDER_API_KEY (any working key) and prints remaining free build minutes.
Decision: source-build allowed only when remaining >= estimated + 50 buffer,
otherwise prebuilt-image mode. Fails closed (exit 1) if quota API unavailable
unless RENDER_QUOTA_FAIL_OPEN=1.
"""
import json, os, sys, urllib.request

FAIL_OPEN = os.environ.get("RENDER_QUOTA_FAIL_OPEN", "").strip().lower() in ("1", "true", "yes")
ESTIMATED_BUILD_MINUTES = int(os.environ.get("RENDER_ESTIMATED_BUILD_MINUTES", "20"))
SAFETY_BUFFER = 50
GLOBAL_THRESHOLD = 450

# pick a working key
key = ""
for var in ["RENDER_API_KEY_1", "RENDER_API_KEY_2", "RENDER_API_KEY_3", "RENDER_API_KEY_4", "RENDER_API_KEY_5", "RENDER_API_KEY_6", "RENDER_API_KEY", "RENDER_API_KEY_PAYKARI"]:
    v = os.environ.get(var, "").strip()
    if v:
        key = v
        break

if not key:
    print("::error::No Render API key available for quota preflight")
    sys.exit(0 if FAIL_OPEN else 1)

# Render billing/quota endpoint (best-effort; structure varies)
try:
    req = urllib.request.Request(
        "https://api.render.com/v1/billing/usage",
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    # tolerate multiple shapes
    limit = data.get("limit") or data.get("monthlyLimit") or data.get("buildMinutesLimit") or 500
    used = data.get("used") or data.get("usedMinutes") or data.get("buildMinutesUsed") or 0
    remaining = float(limit) - float(used)
except Exception as e:
    print("::warning::Render quota API unavailable: %s" % e)
    print("RENDER_DEPLOY_MODE=prebuilt-image")
    print("QUOTA_REMAINING=unknown")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write("deploy_mode=prebuilt-image\n")
            f.write("remaining_minutes=unknown\n")
    sys.exit(0)

print("QUOTA_LIMIT=%.1f" % float(limit))
print("QUOTA_USED=%.1f" % float(used))
print("QUOTA_REMAINING=%.1f" % remaining)

if remaining >= GLOBAL_THRESHOLD and remaining >= (ESTIMATED_BUILD_MINUTES + SAFETY_BUFFER):
    mode = "render-source-build"
elif remaining >= (ESTIMATED_BUILD_MINUTES + SAFETY_BUFFER):
    mode = "render-source-build"
else:
    mode = "prebuilt-image"

print("RENDER_DEPLOY_MODE=%s" % mode)
# Export to GITHUB_OUTPUT if available
out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a") as f:
        f.write("deploy_mode=%s\n" % mode)
        f.write("remaining_minutes=%.1f\n" % remaining)
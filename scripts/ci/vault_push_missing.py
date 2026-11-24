"""Push the 15 codebase secrets that have local .env values but are missing from vault.

Reads values from .env, pushes via infisical CLI, reports success/failure without leaking values.
"""
import json
import os
import subprocess


# Load credentials from vault.env (gitignored) or environment variables.
def load_auth():
    auth = {}
    # env vars first
    for k in ("INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID"):
        if os.environ.get(k):
            auth[k] = os.environ[k]
    # fall back to vault.env
    if (not auth.get("INFISICAL_CLIENT_ID") or not auth.get("INFISICAL_PROJECT_ID")) and os.path.exists("vault.env"):
        for line in open("vault.env", encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                kk, vv = line.split("=", 1)
                kk = kk.strip(); vv = vv.strip().strip('"').strip("'")
                if kk in ("INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID"):
                    auth.setdefault(kk, vv)
    return auth

# বাংলা মন্তব্য: হার্ডকোডেড প্রজেক্ট আইডি নিষিদ্ধ — এনভায়রনমেন্ট বা গিটইগনোরড vault.env ছাড়া ফেইল-ক্লোজড
AUTH = load_auth()
PROJECT = AUTH.get("INFISICAL_PROJECT_ID", "").strip()
if not PROJECT:
    raise RuntimeError("INFISICAL_PROJECT_ID environment variable (or vault.env entry) is required.")
ENV = os.environ.get("INFISICAL_ENV", "prod")

# parse .env
env = {}
for line in open(".env", encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

data = json.load(open("scratchpad/real_missing.json", encoding="utf-8"))
keys = data["in_env"]

ok, fail = [], []
for k in keys:
    val = env.get(k, "")
    if not val:
        fail.append((k, "empty value"))
        continue
    e = dict(os.environ)
    e.update(AUTH)
    r = subprocess.run(
        ["infisical", "secrets", "set", f"{k}={val}",
         "--projectId", PROJECT, "--env", ENV, "--silent"],
        capture_output=True, text=True, env=e,
    )
    if r.returncode == 0:
        ok.append(k)
    else:
        fail.append((k, (r.stderr or r.stdout or "").strip()[:200]))

print("pushed:", len(ok))
for k in ok:
    print("  OK  ", k)
print("failed:", len(fail))
for k, msg in fail:
    print("  FAIL", k, "->", msg)

# save report
json.dump({"pushed": ok, "failed": [{"key": k, "msg": m} for k, m in fail]},
          open("scratchpad/vault_push_report.json", "w", encoding="utf-8"), indent=1)

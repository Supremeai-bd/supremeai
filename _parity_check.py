import pathlib, re

root = pathlib.Path("F:/supremeai")

# 1. router-defining files
router_files = []
for p in (root/"backend").rglob("*.py"):
    try:
        t = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if re.search(r"router\s*=\s*APIRouter\s*\(", t):
        router_files.append(str(p.relative_to(root)))

print("ROUTER_DEF_FILES:", len(router_files))

# 2. ALL_ROUTERS entries
t = (root/"backend/api/routers.py").read_text(encoding="utf-8")
paths = re.findall(r'"path"\s*:\s*"([^"]+)"', t)
print("ALL_ROUTERS_ENTRIES:", len(paths))
for p in paths:
    print("  R:", p)

# 3. workspace feature routes
wt = (root/"backend/api/routes/workspace_feature_routes.py").read_text(encoding="utf-8")
mods = re.findall(r'"(api\.routes\.[a-z_]+)"', wt)
print("TIERS_MODS_FOUND:", sorted(set(mods)))
m2 = re.search(r"ROUTER_DEFS\s*=\s*\[(.*?)\]", wt, re.S)
if m2:
    print("TIERS_TUPLES:", m2.group(1).count("("))

# 4. direct includes
for f in ["backend/core/app_builder.py", "backend/core/app.py"]:
    ft = (root/f).read_text(encoding="utf-8", errors="ignore")
    incs = re.findall(r"include_router\s*\(\s*([a-zA-Z0-9_\.]+)", ft)
    reg = re.findall(r"register_router\s*\(\s*app\s*,\s*[\"']([^\"']+)[\"']", ft)
    print(f, "include_router:", incs, "register_router:", reg)

# 5. frontend counts
fe_files = list((root/"frontend/src").rglob("*.ts")) + list((root/"frontend/src").rglob("*.tsx"))
print("FRONTEND_SRC_FILES:", len(fe_files))
app = (root/"frontend/src/App.tsx").read_text(encoding="utf-8")
routes = re.findall(r'path="([^"]+)"', app)
print("APP_ROUTES:", routes)
nav = (root/"frontend/src/config/navigationRegistry.ts").read_text(encoding="utf-8")
impl = re.findall(r"path:\s*'([^']+)'", nav)
print("NAV_PATHS:", impl)

# 6. check specific consumers
import subprocess
def grep(pat, path):
    r = subprocess.run(["git", "-C", "F:/supremeai", "--no-pager", "grep", "-n", pat, "--", path], capture_output=True, text=True)
    return r.stdout.strip()
print("--- socialGrowth consumers ---")
print(grep("socialGrowthService", "frontend/src") or "(none beyond service file)")
print("--- byoc UI ---")
print(grep("byoc_api\\|ByocPanel\\|BYOC", "frontend/src") or "(none)")
print("--- crawler UI ---")
print(grep("crawler", "frontend/src") or "(none)")

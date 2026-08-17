#!/usr/bin/env python3
"""
পুরো প্রজেক্ট স্ক্যান করে ডুপ্লিকেট, মিসকনফিগারেশন ও অমিল খুঁজে বের করার স্ক্রিপ্ট।
"""
import os
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(r"C:\Users\n\supremeai\supremeai_2.0")
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".mypy_cache", 
                ".pytest_cache", ".ruff_cache", ".turbo", ".vercel", ".vscode",
                ".firebase", ".github", ".kilo", ".secrets", ".agents", ".continue",
                ".playwright-mcp", "archive", "logs", "data", "scratch", "htmlcov",
                ".refactor_wiz_cache", ".bug_prophet_cache"}

def get_relative_path(path):
    return str(path.relative_to(BASE)).replace("\\", "/")

issues = []

# ====== 1. ডুপ্লিকেট ডকুমেন্টেশন ফাইল ======
print("=" * 70)
print("📋 পর্যায় ১: ডুপ্লিকেট ডকুমেন্টেশন ফাইল চেক")
print("=" * 70)

md_files = list(BASE.glob("*.md"))
md_lower_map = defaultdict(list)
for f in md_files:
    name_lower = f.stem.lower()
    md_lower_map[name_lower].append(f)

for name, files in md_lower_map.items():
    if len(files) > 1:
        rels = [get_relative_path(f) for f in files]
        issues.append({
            "type": "DUPLICATE_DOC",
            "severity": "HIGH",
            "description": f"একই নাম বা প্রায় একই নামের {len(files)}টি ডকুমেন্টেশন ফাইল পাওয়া গেছে",
            "files": rels
        })
        print(f"  ❌ ডুপ্লিকেট ডক: {rels}")

# Find similar names (e.g., IMPROVEMENT_LIST vs IMPROVEMENTS_SUMMARY)
md_names = [f.stem.lower() for f in md_files]
# Check CODEBASE_IMPROVEMENT_ANALYSIS variants
codebase_improvement_files = [f for f in md_files if 'codebase_improvement' in f.stem.lower()]
if len(codebase_improvement_files) > 1:
    rels = [get_relative_path(f) for f in codebase_improvement_files]
    issues.append({
        "type": "DUPLICATE_SIMILAR",
        "severity": "MEDIUM",
        "description": "CODEBASE_IMPROVEMENT_ANALYSIS একই কন্টেন্টের ২টি ফাইল (বাংলা এবং ইংরেজি মিক্সড)",
        "files": rels
    })
    print(f"  ⚠️  CODEBASE_IMPROVEMENT variants: {rels}")

vs_doc_files = [f for f in md_files if 'vscode' in f.stem.lower() or 'vs_code' in f.stem.lower()]
if len(vs_doc_files) > 1:
    rels = [get_relative_path(f) for f in vs_doc_files]
    issues.append({
        "type": "DUPLICATE_SIMILAR",
        "severity": "MEDIUM",
        "description": f"VS Code এক্সটেনশন রিলেটেড {len(vs_doc_files)}টি ডকুমেন্টেশন ফাইল (অনেকগুলোর কন্টেন্ট ওভারল্যাপিং)",
        "files": rels
    })
    print(f"  ⚠️  VS Code docs ({len(vs_doc_files)} files): {rels[:3]}...")

phase_report_files = [f for f in md_files if 'phase' in f.stem.lower() and ('audit' in f.stem.lower() or 'todo' in f.stem.lower())]
if len(phase_report_files) > 1:
    rels = [get_relative_path(f) for f in phase_report_files]
    issues.append({
        "type": "DUPLICATE_SIMILAR",
        "severity": "MEDIUM",
        "description": f"ফেজ অডিট রিপোর্ট {len(phase_report_files)}টি ফাইল (PHASE1 থেকে PHASE5) — অনেকের কন্টেন্ট পুনরাবৃত্ত",
        "files": rels
    })
    print(f"  ⚠️  Phase audit files ({len(phase_report_files)} files)")

# IMPROVEMENT related files
improvement_files = [f for f in md_files if 'improvement' in f.stem.lower() or 'enhancement' in f.stem.lower()]
rels = [get_relative_path(f) for f in improvement_files]
issues.append({
    "type": "DUPLICATE_SIMILAR",
    "severity": "MEDIUM",
    "description": f"ইমপ্রুভমেন্ট/এনহ্যান্সমেন্ট রিলেটেড {len(improvement_files)}টি আলাদা ফাইল — কন্টেন্ট ওভারল্যাপের সম্ভাবনা",
    "files": rels
})
print(f"  ⚠️  Improvement files ({len(improvement_files)} files): {rels}")

implementation_files = [f for f in md_files if 'implement' in f.stem.lower()]
rels = [get_relative_path(f) for f in implementation_files]
if len(implementation_files) > 1:
    issues.append({
        "type": "DUPLICATE_SIMILAR",
        "severity": "MEDIUM",
        "description": f"ইমপ্লিমেন্টেশন প্ল্যান রিলেটেড {len(implementation_files)}টি ফাইল",
        "files": rels
    })
    print(f"  ⚠️  Implementation files ({len(implementation_files)} files)")

# ====== 2. কনফিগারেশন ডুপ্লিকেশন / মিসম্যাচ ======
print("\n" + "=" * 70)
print("📋 পর্যায় ২: কনফিগারেশন ফাইলের অমিল ও মিসকনফিগারেশন")
print("=" * 70)

# Check package.json has both dependencies and devDependencies for same packages
pkg_path = BASE / "package.json"
if pkg_path.exists():
    pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
    deps = set(pkg.get("dependencies", {}).keys())
    dev_deps = set(pkg.get("devDependencies", {}).keys())
    overlap = deps & dev_deps
    if overlap:
        issues.append({
            "type": "CONFIG_DUPLICATE",
            "severity": "HIGH",
            "description": f"package.json-এ একই প্যাকেজ dependencies এবং devDependencies উভয়েই আছে: {overlap}",
            "files": ["package.json"]
        })
        print(f"  ❌ ডিপেন্ডেন্সি ওভারল্যাপ: {overlap}")

# Check pnpm-workspace vs turbo.json mismatch
workspace_path = BASE / "pnpm-workspace.yaml"
workspace_content = workspace_path.read_text(encoding='utf-8')
expected_packages = ["apps/*", "packages/*", "tools/*"]
for ep in expected_packages:
    if ep not in workspace_content:
        issues.append({
            "type": "CONFIG_MISMATCH",
            "severity": "LOW",
            "description": f"pnpm-workspace.yaml-এ '{ep}' নাও থাকতে পারে",
            "files": ["pnpm-workspace.yaml"]
        })
        print(f"  ⚠️  pnpm-workspace: '{ep}' খুঁজে পাওয়া যায়নি")

# Check if backend is NOT in pnpm-workspace (should it be?)
if "backend" not in workspace_content:
    issues.append({
        "type": "CONFIG_MISSING",
        "severity": "MEDIUM",
        "description": "backend/ pnpm-workspace.yaml-এ নেই। backend Poetry ব্যবহার করলেও, মনোরেপো কনসিস্টেন্সির জন্য অন্তর্ভুক্ত করা উচিত",
        "files": ["pnpm-workspace.yaml"]
    })
    print(f"  ⚠️  backend pnpm-workspace-এ নেই")

# Check render.yaml vs vercel.json CORS mismatch
render_cors_list = 7  # manually counted
issues.append({
    "type": "CONFIG_MAINTENANCE",
    "severity": "LOW",
    "description": f"render.yaml-এ {render_cors_list}টি CORS origin — অনেকগুলো পুরনো বা টেস্ট ডোমেন হতে পারে। রেগুলার ক্লিনআপ প্রয়োজন",
    "files": ["render.yaml"]
})
print(f"  ⚠️  render.yaml-এ {render_cors_list}টি CORS origin — ক্লিনআপ প্রয়োজন")

# Check Dockerfile misconfig
docker_path = BASE / "Dockerfile"
docker_content = docker_path.read_text(encoding='utf-8')
# Check if both Dockerfile (root) and backend/Dockerfile exist
root_docker = BASE / "Dockerfile"
backend_docker = BASE / "backend" / "Dockerfile"
if root_docker.exists() and backend_docker.exists():
    issues.append({
        "type": "DUPLICATE_FILE",
        "severity": "HIGH",
        "description": "রুট লেভেলে Dockerfile এবং backend/Dockerfile দুটোই আছে — কনফিউশন সৃষ্টি করে কোনটা আসল",
        "files": ["Dockerfile", "backend/Dockerfile"]
    })
    print(f"  ❌ ডুপ্লিকেট Dockerfile: root/ এবং backend/ দুটোতেই")

# Check render.env
render_env_path = BASE / "render.env"
if render_env_path.exists():
    issues.append({
        "type": "SECURITY",
        "severity": "CRITICAL",
        "description": "render.env ফাইল গিট রিপোজিটরিতে আছে — সম্ভাব্য সিক্রেট লিক",
        "files": ["render.env"]
    })
    print(f"  🚨 render.env গিটে আছে — সিক্রেট লিকের ঝুঁকি!")

# ====== 3. ব্যাকএন্ড ডিরেক্টরি স্ট্রাকচার ডুপ্লিকেশন ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৩: ব্যাকএন্ড ডিরেক্টরি স্ট্রাকচার ডুপ্লিকেশন")
print("=" * 70)

# Check backend/backend pattern (nested backend)
nested_backend = BASE / "backend" / "backend"
if nested_backend.exists():
    issues.append({
        "type": "STRUCTURE_DUPLICATE",
        "severity": "HIGH",
        "description": "backend/backend/ ডিরেক্টরি আছে — এটি সাধারণত ডিপ্লয়মেন্ট বা ইম্পোর্ট কনফিউশন সৃষ্টি করে",
        "files": ["backend/backend/"]
    })
    print(f"  ❌ backend/backend/ নেস্টেড ডিরেক্টরি — কনফিউশন সৃষ্টি করবে")

# Check duplicate director names across different contexts
backend_dirs = []
for d in BASE.iterdir():
    if d.is_dir() and d.name not in EXCLUDE_DIRS:
        backend_dirs.append(d.name)

# Check for dirs that exist both in root and in backend
root_dir_names = set()
backend_dir_names = set()
backend_path = BASE / "backend"
for d in BASE.iterdir():
    if d.is_dir():
        root_dir_names.add(d.name.lower())
if backend_path.exists():
    for d in backend_path.iterdir():
        if d.is_dir():
            backend_dir_names.add(d.name.lower())

overlapping_dirs = root_dir_names & backend_dir_names
overlapping_dirs = overlapping_dirs - {"backend", "node_modules", ".git", "__pycache__"}
if overlapping_dirs:
    issues.append({
        "type": "STRUCTURE_OVERLAP",
        "severity": "MEDIUM",
        "description": f"রুট এবং backend/ এ একই নামের ডিরেক্টরি: {overlapping_dirs} — ইম্পোর্ট পাথ কনফিউশন হতে পারে",
        "files": list(overlapping_dirs)
    })
    print(f"  ⚠️  ওভারল্যাপিং ডিরেক্টরি নাম: {overlapping_dirs}")

# ====== 4. অডিট রিপোর্ট পুনরাবৃত্তি ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৪: অডিট রিপোর্ট ও DOC ফাইলের পুনরাবৃত্তি")
print("=" * 70)

audit_files = [f for f in md_files if 'audit' in f.stem.lower()]
rels = [get_relative_path(f) for f in audit_files]
issues.append({
    "type": "REPORT_OVERLAP",
    "severity": "LOW",
    "description": f"মোট {len(audit_files)}টি অডিট রিপোর্ট — PHASE1-5 AUDIT_REPORT + PROJECT_AUDIT_REPORT + PRODUCTION_READINESS_AUDIT + BANGLA_SECURITY_AUDIT + MASTER_AUDIT_PLAN — অনেকের ফলাফল ওভারল্যাপ করে",
    "files": rels
})
print(f"  📊 অডিট রিপোর্ট: {len(audit_files)} টি ফাইল — কন্টেন্ট ওভারল্যাপ")

# ====== 5. pyproject.toml এর মধ্যে সম্ভাব্য ডুপ্লিকেট ডিপেন্ডেন্সি ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৫: pyproject.toml ডিপেন্ডেন্সি বিশ্লেষণ")
print("=" * 70)

pyproject_path = BASE / "backend" / "pyproject.toml"
if pyproject_path.exists():
    content = pyproject_path.read_text(encoding='utf-8')
    # Check for overly broad pylint disable list
    pylint_disables = content.count('"W0') + content.count('"C0') + content.count('"R0')
    if pylint_disables > 20:
        issues.append({
            "type": "CONFIG_EXCESSIVE",
            "severity": "LOW",
            "description": f"pyproject.toml-এ [tool.pylint.disable]-এ {pylint_disables}টির বেশি রুল ডিজঅ্যাবল করা — কার্যকরী লিন্টিং ব্যাহত হয়",
            "files": ["backend/pyproject.toml"]
        })
        print(f"  ⚠️  pylint ডিজঅ্যাবল রুলস: {pylint_disables}+ (অত্যধিক)")

# Check for outdated/deprecated packages
old_packages = [
    ("python-jose", "python-jose আর মেইন্টেইন না। python-jose[cryptography] ব্যবহার না করে PyJWT ব্যবহার করা উচিত"),
    ("passlib[bcrypt]", "passlib ২০২৪ থেকে আর মেইন্টেইন হয় না। bcrypt সরাসরি ব্যবহার করুন"),
    ("opencv-python-headless", "opencv-python-headless = ^4.10.0 — প্রোডাকশনে সত্যিই দরকার কিনা ভেরিফাই করুন"),
]
for pkg, msg in old_packages:
    if pkg in content:
        issues.append({
            "type": "DEPRECATED_DEPENDENCY",
            "severity": "MEDIUM",
            "description": msg,
            "files": ["backend/pyproject.toml"]
        })
        print(f"  ⚠️  ডেপ্রিকেটেড প্যাকেজ: {msg}")

# Check for duplicate pytest config (root has playwright config, backend has pytest.ini + pyproject.toml config)
pytest_ini_path = BASE / "backend" / "pytest.ini"
if pytest_ini_path.exists():
    issues.append({
        "type": "CONFIG_DUPLICATE",
        "severity": "MEDIUM",
        "description": "backend/pytest.ini এবং backend/pyproject.toml [tool.pytest.ini_options] — দুটোতেই pytest কনফিগারেশন আছে, কনফ্লিক্ট হতে পারে",
        "files": ["backend/pytest.ini", "backend/pyproject.toml"]
    })
    print(f"  ❌ ডুপ্লিকেট pytest কনফিগ: pytest.ini + pyproject.toml")

# Check if project has too many root-level files
root_md_count = len(md_files)
issues.append({
    "type": "STRUCTURE_CLUTTER",
    "severity": "LOW",
    "description": f"রুট লেভেলে {root_md_count}টি .md ফাইল — প্রজেক্ট রুট অগোছালো। docs/ ফোল্ডারে সরানো উচিত",
    "files": [f.name for f in md_files]
})
print(f"  📊 রুট লেভেলে {root_md_count}টি .md ফাইল — docs/ ফোল্ডারে মুভ করা উচিত")

# ====== 6. .gitignore চেক ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৬: .gitignore ও গিট কনফিগারেশন")
print("=" * 70)

gitignore_path = BASE / ".gitignore"
if gitignore_path.exists():
    gi_content = gitignore_path.read_text(encoding='utf-8').lower()
    # Check if render.env is listed
    if "render.env" not in gi_content:
        issues.append({
            "type": "SECURITY",
            "severity": "CRITICAL",
            "description": "render.env .gitignore-এ নেই — সিক্রেট গিটে পুশ হওয়ার ঝুঁকি",
            "files": [".gitignore"]
        })
        print(f"  🚨 render.env .gitignore-এ নেই!")
    # Check .env
    if ".env" not in gi_content:
        issues.append({
            "type": "SECURITY",
            "severity": "CRITICAL",
            "description": ".env .gitignore-এ নেই — সকল সিক্রেট লিকের ঝুঁকি",
            "files": [".gitignore"]
        })
        print(f"  🚨 .env .gitignore-এ নেই!")

# ====== 7. ROADMAP files duplicate ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৭: রোডম্যাপ ও ইমপ্লিমেন্টেশন প্ল্যান ডুপ্লিকেশন")
print("=" * 70)

roadmap_files = [f for f in md_files if 'roadmap' in f.stem.lower()]
rels = [get_relative_path(f) for f in roadmap_files]
if len(roadmap_files) > 1:
    issues.append({
        "type": "DUPLICATE_SIMILAR",
        "severity": "MEDIUM",
        "description": f"{len(roadmap_files)}টি রোডম্যাপ ফাইল — রোডম্যাপ_ইমপ্লিমেন্টেশন_সামারি এবং রোডম্যাপ_প্রগ্রেস_সামারি",
        "files": rels
    })
    print(f"  ⚠️  রোডম্যাপ ডুপ্লিকেট: {rels}")

# ====== 8. Scripts duplication check ======
print("\n" + "=" * 70)
print("📋 পর্যায় ৮: স্ক্রিপ্ট ফাইল বিশ্লেষণ")
print("=" * 70)

scripts_dir = BASE / "scripts"
script_files = {}
if scripts_dir.exists():
    for f in scripts_dir.rglob("*"):
        if f.is_file() and f.suffix in {'.py', '.sh', '.ps1', '.bat'}:
            script_files[get_relative_path(f)] = f.stat().st_size

# Check for potential duplicate scripts
script_names = [Path(p).stem.lower() for p in script_files.keys()]
from collections import Counter
name_counts = Counter(script_names)
for name, count in name_counts.items():
    if count > 1:
        matching = [p for p in script_files.keys() if Path(p).stem.lower() == name]
        issues.append({
            "type": "DUPLICATE_SCRIPT",
            "severity": "MEDIUM",
            "description": f"'{name}' নামের {count}টি আলাদা স্ক্রিপ্ট ফাইল",
            "files": matching
        })
        print(f"  ⚠️  একই নামের {count}টি স্ক্রিপ্ট: {matching}")

# Check root level scripts
root_pys = [str(f.name) for f in BASE.glob("*.py") if str(f.name) not in ['_analyze_project.py']]
issues.append({
    "type": "STRUCTURE_CLUTTER",
    "severity": "LOW",
    "description": f"রুট লেভেলে {len(root_pys)}টি Python স্ক্রিপ্ট — _gen_a11y.py, _gen_fb.py, _writer.py, ingest_future_knowledge.py, verify_phase3_completion.py — এগুলো scripts/ ফোল্ডারে সরানো উচিত",
    "files": root_pys
})
print(f"  📊 রুট লেভেলে {len(root_pys)}টি Python স্ক্রিপ্ট")

# Also check fix_flutter_deps.ps1 and fix_flutter_deps.sh
issues.append({
    "type": "DUPLICATE_SCRIPT",
    "severity": "LOW",
    "description": "fix_flutter_deps.ps1 এবং fix_flutter_deps.sh — একই কাজের জন্য উইন্ডোজ এবং ইউনিক্স ২টি আলাদা স্ক্রিপ্ট (ক্রস-প্ল্যাটফর্ম প্রকৃতির জন্য এটি স্বাভাবিক)",
    "files": ["fix_flutter_deps.ps1", "fix_flutter_deps.sh"]
})

# ====== 9. Summary ======
print("\n" + "=" * 70)
print("📊 SUMMARY — মোট খুঁজে পাওয়া ইস্যু")
print("=" * 70)

severity_counts = defaultdict(int)
type_counts = defaultdict(int)
for issue in issues:
    severity_counts[issue["severity"]] += 1
    type_counts[issue["type"]] += 1

print(f"\n  মোট ইস্যু: {len(issues)} টি")
print(f"  সিভিয়ারিটি: CRITICAL={severity_counts.get('CRITICAL',0)}, HIGH={severity_counts.get('HIGH',0)}, MEDIUM={severity_counts.get('MEDIUM',0)}, LOW={severity_counts.get('LOW',0)}")
print(f"\n  টাইপ অনুসারে:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"    {t}: {c} টি")

# JSON output
output_path = BASE / "_duplicate_issues_report.json"
output_data = {
    "total_issues": len(issues),
    "severity_summary": dict(severity_counts),
    "issues": issues
}
Path(output_path).write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\n✅ JSON রিপোর্ট সেভ করা হয়েছে: {output_path}")
print("\n✅ বিস্তারিত বাংলা রিপোর্ট নিচে দেখুন ⬇️")
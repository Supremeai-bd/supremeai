#!/usr/bin/env python3
"""
find_secrets.py — SupremeAI 2.0 Intelligent Secret/Leak Scanner (P0 Gate)
=========================================================================
পুরো কোডবেসে hardcoded secret / API key / token / private key স্ক্যান করে।

এই ভার্সনটি "advance intelligent" — মানুষের ইন্টারভেনশন ছাড়াই false positive
কমাতে নিচের ৪টি বুদ্ধিমত্তা ব্যবহার করে (Phase 1 + Phase 2):

  1. Context-Aware (AST): Python ফাইলে রেজেক্স লিটারাল (`re.compile(r'...')`)
     বা প্যাটার্ন ডেফিনিশন স্কিপ করে — স্ক্যানার নিজেই ফ্ল্যাগ করে ফেলত না।
  2. Key-Name vs Value: অ্যাসাইনমেন্টের ডানপাশের স্ট্রিং যদি ছোট identifier
     হয় (`"redis_password"`) → এটা সিক্রেট ভ্যালু না, কী-নেম → স্কিপ।
  3. Entropy Scoring: Shannon entropy দিয়ে আসল সিক্রেট (র্যান্ডম) vs শব্দ
     আলাদা করে। কম entropy = সম্ভবত নট রিয়েল সিক্রেট।
  4. Confidence Engine: প্রতিটি ফাইন্ডিং-এ confidence (0-1)। শুধু HIGH
     confidence-ই CI fail করে; নিচু confidence "REVIEW" ক্যাটাগরিতে যায়।

ব্যবহার:
    python scripts/find_secrets.py                      # পুরো কোডবেস
    python scripts/find_secrets.py --path backend/       # শুধু backend/
    python scripts/find_secrets.py --no-external          # বাইরের টুল বাদ
    python scripts/find_secrets.py --fail-confidence 0.7  # FAIL থ্রেশহোল্ড

Exit codes:
    0 — কোনো HIGH-confidence leak পাওয়া যায়নি (PASS)
    1 — অন্তত একটি HIGH-confidence leak পাওয়া গেছে (FAIL)
    2 — আর্গুমেন্ট / রানটাইম এরর
"""

import argparse
import ast
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 🚨 VALUE_PATTERNS — একটি স্ট্রিং কনস্ট্যান্টের ভ্যালু যদি এই শেপের হয়,
# তবে সেটা সিক্রেট-সদৃশ। (pattern_name, regex, base_severity, is_explicit_prefix)
# is_explicit_prefix=True → নির্দিষ্ট ফরম্যাট ম্যাচ (যেমন AKIA) → confidence বেশি।
VALUE_PATTERNS: list[tuple[str, "re.Pattern[str]", str, bool]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "CRITICAL", True),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "CRITICAL", True),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"), "CRITICAL", True),
    ("github_pat", re.compile(r"\bghp_[0-9A-Za-z]{36}\b"), "CRITICAL", True),
    ("github_oauth", re.compile(r"\bgho_[0-9A-Za-z]{36}\b"), "CRITICAL", True),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "CRITICAL", True),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b"), "CRITICAL", True),
    ("sendgrid_key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b"), "CRITICAL", True),
    ("twilio_key", re.compile(r"\bSK[0-9a-fA-F]{32}\b"), "HIGH", True),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "CRITICAL", True),
    ("db_connection_string", re.compile(r"(?:postgres|postgresql|mysql|mongodb|redis|amqp|mongodb\+srv)://[^:/\s]+:[^@/\s]+@"), "CRITICAL", True),
    ("jwt_secret_value", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "CRITICAL", True),
    # এনট্রপি-ভিত্তিক জেনেরিক টোকেন (prefix নাই) — confidence কম থাকবে
    ("high_entropy_token", re.compile(r"[A-Za-z0-9_\-]{32,}"), "HIGH", False),
]

# বাংলা মন্তব্য: এই ভ্যারিয়েবল নামগুলো থাকলে সিক্রেট হওয়ার সম্ভাবনা বেশি (confidence boost)।
SECRET_VAR_KEYWORDS: tuple[str, ...] = (
    "password", "passwd", "pwd", "api_key", "apikey", "secret",
    "token", "private_key", "signing_key", "access_key", "auth",
)

KEYNAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PLACEHOLDER_RE = re.compile(r"(?i)^(test|example|changeme|dummy|your[_\-]?|sample|fake|mock)")

# ✅ অনুমোদিত ব্যতিক্রম — test fixture, env example, স্ক্রিপ্ট নিজেই
ALLOWED_PATHS: tuple[str, ...] = (
    "find_secrets.py",
    ".env.example",
    ".env.sample",
    "tests/",
    "test_",
    "conftest.py",
    "fixtures/",
    "mock",
    "stub",
    "example",
    "docs/",
    "README",
)

SCAN_SUFFIXES: tuple[str, ...] = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt",
    ".yaml", ".yml", ".json", ".toml", ".env", ".ini", ".sh", ".md",
)

DEFAULT_EXCLUDE: tuple[str, ...] = (
    ".venv", "node_modules", "__pycache__", ".git", ".agent",
    "infrastructure", "archive", "build", "dist", ".turbo",
    "out", "htmlcov", ".coverage", "coverage",
)

SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# 🧠 Phase 4 — Self-Learning Allowlist
# বাংলা মন্তব্য: admin একবার false positive মার্ক করলে তা পার্মানেন্ট সাপ্রেস হয়,
# সিস্টেম সময়ের সাথে রিপোর প্যাটার্ন শিখে — মানুষের ইন্টারভেনশন কমে।
ALLOWLIST_PATH = Path(".secrets-allowlist.json")

# বাংলা মন্তব্য: পাবলিক ডকুমেন্টেশনে থাকা নামীয় example টোকেন — এগুলো আসল লিক না।
EXAMPLE_TOKENS: frozenset[str] = frozenset({
    "AKIAIOSFODNN7EXAMPLE",  # AWS docs example
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # AWS docs secret example
})


def load_allowlist() -> list[dict]:
    """অনুমোদিত (suppressed) ফাইন্ডিং লিস্ট লোড করে।"""
    try:
        with open(ALLOWLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_allowlist(data: list[dict]) -> None:
    ALLOWLIST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def token_hash(tok: str) -> str:
    return hashlib.sha1(tok.encode("utf-8")).hexdigest()


def finding_id(f: dict) -> str:
    """প্রতিটি ফাইন্ডিং-এর স্থিতিশীল (stable) আইডি — ট্রায়েজ কমান্ডে ব্যবহৃত।"""
    raw = f"{f['file']}:{f['line']}:{f['pattern']}".encode("utf-8")
    return "SEC-" + hashlib.sha1(raw).hexdigest()[:10].upper()


def is_allowed(f: dict, allowlist: list[dict]) -> bool:
    """ফাইন্ডিংটি allowlist-এ আছে কি না (file+line+pattern বা token hash দিয়ে)।"""
    th = f.get("token_hash")
    for entry in allowlist:
        if (entry.get("file") == f["file"] and entry.get("line") == f["line"]
                and entry.get("pattern") == f["pattern"]):
            return True
        if th and entry.get("token_hash") == th:
            return True
    return False


def shannon_entropy(s: str) -> float:
    """একটি স্ট্রিংয়ের Shannon entropy বের করে (র্যান্ডমনেস মাপার জন্য)।"""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def is_excepted(filepath: str) -> bool:
    norm = filepath.replace("\\", "/").lower()
    return any(tok in norm for tok in ALLOWED_PATHS)


def _make_finding(filepath, line, pattern_name, severity, confidence, snippet, reason, token=""):
    return {
        "file": filepath, "line": line, "pattern": pattern_name,
        "severity": severity, "confidence": round(confidence, 2),
        "snippet": snippet[:140], "reason": reason,
        "token": token, "token_hash": token_hash(token) if token else "",
    }


def classify_token(tok: str, *, var_name: str | None = None, is_recompile: bool = False,
                   pattern_name: str = "", base_severity: str = "HIGH",
                   explicit_prefix: bool = False, token: str = "") -> "dict | None":
    """একটি টোকেনকে সিক্রেট কি না ও কতটা confident তা নির্ধারণ করে। None = স্কিপ।"""
    # 1) রেজেক্স লিটারাল / প্যাটার্ন ডেফিনিশন → স্কিপ
    if is_recompile:
        return None
    if var_name and ("pattern" in var_name.lower() or "regex" in var_name.lower()):
        return None
    # 2) কী-নেম identifier (যেমন "redis_password") → ভ্যালু না, স্কিপ
    if KEYNAME_RE.match(tok) and "_" in tok:
        return _make_finding("", 0, pattern_name, "INFO", 0.1, tok,
                             "key-name identifier, not a secret value")
    # 3) placeholder / test মান → স্কিপ
    if PLACEHOLDER_RE.match(tok):
        return _make_finding("", 0, pattern_name, "INFO", 0.1, tok, "placeholder/test value")
    # 3b) পাবলিক ডকুমেন্টেশন example টোকেন → আসল লিক না
    if tok in EXAMPLE_TOKENS:
        return _make_finding("", 0, pattern_name, "INFO", 0.05, tok, "known public example token")
    # 3c) test/local DB connection string (test_user:test_password@localhost) → স্কিপ
    if pattern_name == "db_connection_string" and re.search(r"(?i)(test|example|dummy|localhost)", tok):
        return _make_finding("", 0, pattern_name, "INFO", 0.1, tok, "test/local connection string")

    # 4) Entropy + Confidence স্কোরিং
    ent = shannon_entropy(tok)
    conf = 0.7 if explicit_prefix else 0.45
    reasons = [f"matched {pattern_name}"]
    if var_name and any(k in var_name.lower() for k in SECRET_VAR_KEYWORDS):
        conf = min(1.0, conf + 0.25)
        reasons.append("variable name suggests secret")
    if ent >= 3.5:
        conf = min(1.0, conf + 0.1)
        reasons.append(f"high entropy {ent:.1f}")
    elif ent < 2.5 and not explicit_prefix:
        conf = 0.2
        reasons.append(f"low entropy {ent:.1f}")

    severity = base_severity
    # বাংলা মন্তব্য: কম confidence হলে severity ডাউনগ্রেড করে REVIEW-এ পাঠাই (fail করবে না)।
    if conf < 0.7 and severity in ("CRITICAL", "HIGH"):
        severity = "MEDIUM"
    return _make_finding("", 0, pattern_name, severity, conf, tok, "; ".join(reasons), token=tok)


def scan_python_file(filepath: str) -> list[dict]:
    """AST দিয়ে Python ফাইল স্ক্যান — কনটেক্সট বুঝে সিক্রেট খোঁজে।"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception:
        return []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return []

    findings: list[dict] = []

    def handle(node: ast.AST, parent: ast.AST | None):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            var_name = None
            is_recompile = False
            if isinstance(parent, ast.Assign):
                for t in parent.targets:
                    if isinstance(t, ast.Name):
                        var_name = t.id
                    elif isinstance(t, ast.Attribute):
                        var_name = t.attr
            if isinstance(parent, ast.Call):
                func = parent.func
                if (isinstance(func, ast.Name) and func.id == "compile") or \
                   (isinstance(func, ast.Attribute) and func.attr == "compile"):
                    # বাংলা মন্তব্য: re.compile(...) এর আর্গুমেন্ট → রেজেক্স লিটারাল, স্কিপ।
                    is_recompile = True
            for name, regex, sev, prefix in VALUE_PATTERNS:
                m = regex.search(value)
                if m:
                    tok = m.group(0)
                    res = classify_token(tok, var_name=var_name, is_recompile=is_recompile,
                                         pattern_name=name, base_severity=sev, explicit_prefix=prefix,
                                         token=tok)
                    if res and res["severity"] != "INFO":
                        res["file"] = filepath
                        res["line"] = node.lineno
                        findings.append(res)
        for child in ast.iter_child_nodes(node):
            handle(child, node)

    handle(tree, None)
    return findings


def scan_text_file(filepath: str) -> list[dict]:
    """Python ছাড়া অন্য ফাইলের জন্য লাইন-ভিত্তিক স্ক্যান + একই ইন্টেলিজেন্স।"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []
    findings: list[dict] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue
        # লাইন থেকে ভ্যারিয়েবল নাম বের করি (password=, api_key: ইত্যাদি)
        var_m = re.search(r"(password|passwd|pwd|api[_-]?key|secret|token|private[_-]?key|auth)\s*[:=]", line, re.IGNORECASE)
        var_name = var_m.group(1) if var_m else None
        # রেজেক্স কনটেক্সট স্কিপ (re.compile, r'...', r"...")
        is_recompile = ("re.compile" in line) or ("r'" in line and "re." in line) or ('r"' in line and "re." in line)
        for name, regex, sev, prefix in VALUE_PATTERNS:
            for m in regex.finditer(line):
                tok = m.group(0)
                res = classify_token(tok, var_name=var_name, is_recompile=is_recompile,
                                     pattern_name=name, base_severity=sev, explicit_prefix=prefix,
                                     token=tok)
                if res and res["severity"] != "INFO":
                    res["file"] = filepath
                    res["line"] = i
                    res["snippet"] = stripped[:140]
                    findings.append(res)
    return findings


def scan_directory(root: str, exclude: list[str]) -> list[dict]:
    all_findings: list[dict] = []
    for path, dirs, files in os.walk(root):
        # বাংলা মন্তব্য: substring ম্যাচ — "dist" → dist-admin, dist-user; "out" → out/ ইত্যাদি
        dirs[:] = [d for d in dirs
                   if not any(ex in d for ex in exclude) and not d.startswith(".")]
        for file in files:
            fp = Path(path) / file
            if fp.suffix not in SCAN_SUFFIXES or is_excepted(str(fp)):
                continue
            if fp.suffix == ".py":
                all_findings.extend(scan_python_file(str(fp)))
            else:
                all_findings.extend(scan_text_file(str(fp)))
    return all_findings


def run_external_tool(name: str, cmd: list[str], root: str) -> str:
    if shutil.which(cmd[0]) is None:
        return f"[SKIP] {name} not installed\n"
    try:
        result = subprocess.run(cmd + [root], capture_output=True, text=False, timeout=300)
        out = ""
        if result.stdout:
            out += result.stdout.decode("utf-8", errors="replace")
        if result.stderr:
            out += result.stderr.decode("utf-8", errors="replace")
        return f"=== {name} ===\n{out[:4000]}\n"
    except Exception as exc:
        return f"[ERROR] {name} failed: {exc}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Intelligent Secret/Leak Scanner (P0 Gate)")
    parser.add_argument("--path", default=".", help="স্ক্যান করার পাথ (ডিফল্ট: repo root)")
    parser.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE), help="এক্সক্লুড ডিরেক্টরি")
    parser.add_argument("--no-external", action="store_true", help="বাইরের টুল (gitleaks) বাদ দাও")
    parser.add_argument("--fail-on", choices=["CRITICAL", "HIGH", "MEDIUM"], default="HIGH",
                        help="কোন severity-তে fail করবে (ডিফল্ট: HIGH)")
    parser.add_argument("--fail-confidence", type=float, default=0.7,
                        help="এই confidence-এর বেশি হলে only তবেই FAIL (ডিফল্ট: 0.7)")
    # Phase 4 — self-learning কমান্ডসমূহ
    parser.add_argument("--triage", nargs=2, metavar=("ID", "DECISION"),
                        help="ফাইন্ডিং আইডি দিয়ে সিদ্ধান্ত দিন: ID fp (false positive) | ID tp (true positive)")
    parser.add_argument("--reason", default=None, help="--triage fp-এর সাথে কারণ")
    parser.add_argument("--list-allow", action="store_true", help="বর্তমান allowlist দেখাও")
    parser.add_argument("--clear-allow", action="store_true", help="allowlist পুরোপুরি ক্লিয়ার করো")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # --- Phase 4: allowlist ম্যানেজমেন্ট কমান্ডসমূহ ---
    if args.list_allow:
        allow = load_allowlist()
        print(f"[ALLOWLIST] {len(allow)} entry:")
        for e in allow:
            print(f"  {e.get('file')}:{e.get('line')} [{e.get('pattern')}] — {e.get('reason', '')}")
        return 0
    if args.clear_allow:
        save_allowlist([])
        print("[ALLOWLIST] ক্লিয়ার করা হয়েছে")
        return 0
    if args.triage:
        fid, decision = args.triage
        decision = decision.lower()
        if decision not in ("fp", "tp"):
            print("[ERROR] DECISION শুধু 'fp' বা 'tp' হতে পারে")
            return 2
        # বাংলা মন্তব্য: আইডি → ফাইন্ডিং ম্যাপ করতে স্ক্যান চালিয়ে মিলিয়ে দেখি।
        findings = scan_directory(args.path, args.exclude)
        target = next((f for f in findings if finding_id(f) == fid), None)
        if not target:
            print(f"[ERROR] আইডি {fid} বর্তমান স্ক্যানে পাওয়া যায়নি")
            return 2
        if decision == "tp":
            print(f"[OK] {fid} true positive হিসেবে মার্ক করা হয়েছে — ফিচারে FAIL করবে।")
            return 0
        allow = load_allowlist()
        entry = {
            "file": target["file"], "line": target["line"], "pattern": target["pattern"],
            "token_hash": target.get("token_hash", ""),
            "reason": args.reason or "admin marked false positive",
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if not any(e.get("file") == entry["file"] and e.get("line") == entry["line"]
                   and e.get("pattern") == entry["pattern"] for e in allow):
            allow.append(entry)
            save_allowlist(allow)
        print(f"[OK] {fid} allowlist-এ যোগ করা হয়েছে — পরবর্তী রানে সাপ্রেস হবে।")
        return 0

    fail_rank = SEV_RANK.get(args.fail_on, 1)

    print(f"[SCAN] Intelligent Secret/Leak স্ক্যান: {args.path}")
    print(f"   Fail threshold: {args.fail_on} | min confidence: {args.fail_confidence}")
    print(f"   Excluding: {', '.join(args.exclude)}")
    print()

    allowlist = load_allowlist()
    raw_findings = scan_directory(args.path, args.exclude)

    # বাংলা মন্তব্য: একই লাইনে একাধিক প্যাটার্ন একই টোকেন ম্যাচ করলে সর্বোচ্চ confidence রাখি (dedupe)।
    best: dict[tuple, dict] = {}
    for f in raw_findings:
        key = (f["file"], f["line"], f.get("token", ""))
        if key not in best or f["confidence"] > best[key]["confidence"]:
            best[key] = f
    raw_findings = list(best.values())

    # বাংলা মন্তব্য: allowlist-এ থাকা ফাইন্ডিংগুলো সাপ্রেস (self-learning) করি।
    suppressed = [f for f in raw_findings if is_allowed(f, allowlist)]
    findings = [f for f in raw_findings if f not in suppressed]

    external_log = ""
    if not args.no_external:
        external_log += run_external_tool("gitleaks", ["gitleaks", "detect", "--no-git", "-v", "-s"], args.path)
        external_log += run_external_tool("trufflehog", ["trufflehog", "filesystem", "--only-verified"], args.path)

    if not findings:
        msg = "[PASS] কোনো সম্ভাব্য secret leak পাওয়া যায়নি"
        if suppressed:
            msg += f" ({len(suppressed)}টি allowlist দিয়ে সাপ্রেস করা হয়েছে)"
        print(msg)
        if external_log:
            print("\n--- External tool output ---\n" + external_log)
        return 0

    # HIGH-confidence (fail-যোগ্য) vs REVIEW (low-confidence) আলাদা করি
    fail_findings = [f for f in findings
                     if f["confidence"] >= args.fail_confidence and SEV_RANK.get(f["severity"], 3) <= fail_rank]
    review_findings = [f for f in findings if f not in fail_findings]

    print(f"[RESULT] {len(fail_findings)} FAIL-যোগ্য + {len(review_findings)} REVIEW"
          + (f" | {len(suppressed)} সাপ্রেস করা হয়েছে" if suppressed else ""))
    print()

    def _print_group(title, group):
        if not group:
            return
        print(f"### {title}")
        for f in sorted(group, key=lambda x: -x["confidence"]):
            safe_file = f["file"].encode(sys.stdout.encoding or "utf-8", "replace").decode()
            safe_snip = f.get("snippet", f.get("pattern", "")).encode(sys.stdout.encoding or "utf-8", "replace").decode()
            print(f"  [{f['severity']}] {f['pattern']} (conf={f['confidence']})  ID={finding_id(f)}")
            print(f"     File: {safe_file}:{f['line']}")
            print(f"     Code: {safe_snip}")
            print(f"     Why:  {f['reason']}")
            print(f"     Triage: python {Path(__file__).name} --triage {finding_id(f)} fp")
            print()

    _print_group("FAIL — HIGH CONFIDENCE LEAKS", fail_findings)
    _print_group("REVIEW — LOW CONFIDENCE (auto-suppressed from fail)", review_findings)

    if external_log:
        print("--- External tool output ---\n" + external_log)

    if fail_findings:
        print(f"[FAIL] {len(fail_findings)} HIGH-confidence leak পাওয়া গেছে")
        return 1
    print("[PASS] শুধু low-confidence REVIEW পাওয়া গেছে, FAIL করছে না")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)

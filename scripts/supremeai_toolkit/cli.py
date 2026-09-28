# -*- coding: utf-8 -*-
"""SupremeAI Toolkit — Unified CLI dispatcher (#2403 seq:1).

# বাংলা মন্তব্য: ৩৯০+ বিচ্ছিন্ন স্ক্রিপ্টের বুদ্ধিমান সেন্ট্রাল টুলের প্রবেশদ্বার।
# সাবকমান্ড রেজিস্ট্রি মডুলার — ভবিষ্যৎ seq-এ নতুন ক্ষমতা এখানেই যুক্ত হবে।
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import reusability_audit
else:
    from . import reusability_audit


def _cmd_audit(args: argparse.Namespace) -> int:
    """`audit` — Reusability Audit চালায় (read-only; --out দিলে রিপোর্ট লেখে)।"""
    roots = [r.strip() for r in args.roots.split(",") if r.strip()]
    out_md = Path(args.out_md) if args.out_md else None
    out_json = Path(args.out_json) if args.out_json else None
    total, report = reusability_audit.run_audit(REPO_ROOT, roots, out_md, out_json)
    if not out_md:
        # বাংলা মন্তব্য: --out ছাড়া চালালে সারসংক্ষেপ stdout-এ — কোনো ফাইল-লেখা নয়।
        summary = [ln for ln in report.splitlines() if ln.startswith("**মোট") or ln.startswith("| keep")]
        print("\n".join(summary))
    print(f"[OK] audit complete — {total} files scanned across roots: {', '.join(roots)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="supremeai_toolkit", description="SupremeAI Unified Toolkit (#2403)")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="Reusability Audit — প্রমাণ-ভিত্তিক verdict (read-only)")
    a.add_argument("--roots", default="scripts", help="কমা-সেপারেটেড স্ক্যান-রুট (default: scripts)")
    a.add_argument("--out-md", dest="out_md", default=None, help="মার্কডাউন রিপোর্ট আউটপুট পাথ")
    a.add_argument("--out-json", dest="out_json", default=None, help="JSON প্রমাণ আউটপুট পাথ")
    a.set_defaults(func=_cmd_audit)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

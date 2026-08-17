#!/usr/bin/env python3
# =============================================================================
# SupremeAI 2.0 - Codebase Exporter Script
# =============================================================================
#
# এই স্ক্রিপ্টটি আপনার সম্পূর্ণ প্রজেক্ট কোডবেসকে একটি সিঙ্গেল Markdown
# ফাইলে কনভার্ট করে। Claude বা অন্য যেকোনো AI-কে কোডবেস বোঝাতে এটি ব্যবহার করুন।
#
# ============================ কিভাবে ব্যবহার করবেন ============================
#
# ১. সরাসরি রান করুন (ডিফল্ট সেটিংস দিয়ে সম্পূর্ণ কোডবেস এক্সপোর্ট):
#    python scripts/export_codebase.py
#
# ২. কাস্টম আউটপুট পাথ দিয়ে রান করুন:
#    python scripts/export_codebase.py --output "C:\my_output\codebase.md"
#
# ৩. শুধু Backend কোড এক্সপোর্ট করুন:
#    python scripts/export_codebase.py --scope backend
#
# ৪. শুধু Frontend কোড এক্সপোর্ট করুন:
#    python scripts/export_codebase.py --scope frontend
#
# ৫. উভয়ই একসাথে (ফুল স্ট্যাক):
#    python scripts/export_codebase.py --scope full
#
# ৬. একটি নির্দিষ্ট ফোল্ডার এক্সপোর্ট করুন:
#    python scripts/export_codebase.py --root "C:\my_project" --output "C:\out.md"
#
# ========================= এক্সক্লুড করা ফাইল/ফোল্ডার =========================
#
# নিচের জিনিসগুলো সবসময় বাদ দেওয়া হয়:
#   - .env, .env.example, render.env (সিক্রেট ফাইল)
#   - node_modules/, venv/, __pycache__/ (ডিপেন্ডেন্সি ক্যাশ)
#   - dist/, build/, out/, .next/ (বিল্ড আউটপুট)
#   - logs/, *.log (লগ ফাইল)
#   - docs/autogen/ (অটো-জেনারেটেড ডকুমেন্ট)
#   - *.jpg, *.png, *.svg, *.gif (ইমেজ ফাইল)
#   - *.zip, *.tar, *.gz (কম্প্রেসড ফাইল)
#   - .git/, .vscode/, .idea/ (IDE/ভার্সন কন্ট্রোল ফোল্ডার)
#   - পুরানো codebase export ফাইল (*codebase*.md, *full_*.md)
#
# ========================= ফাইল সাইজ গাইডলাইন =========================
#
# Claude-এ আপলোড করার আগে ফাইল সাইজ চেক করুন:
#   - < 5 MB   : Claude.ai-তে সরাসরি আপলোড করা যাবে ✅
#   - 5-20 MB  : Claude.ai-তে আপলোড সম্ভব, কিন্তু slow হতে পারে ⚠️
#   - > 20 MB  : --scope backend অথবা --scope frontend ব্যবহার করুন ❌
#
# ===========================================================================

import argparse
import fnmatch
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows কনসোলে ইউনিকোড ক্যারেক্টার (ইমোজি ও বাংলা) প্রিন্ট করার সময় UnicodeEncodeError এড়াতে stdout এবং stderr-কে utf-8 এনকোডিংয়ে রিকনফিগার করা হয়েছে।
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')



# =============================================================================
# কনফিগারেশন: কোন ফাইল/ফোল্ডার বাদ দেওয়া হবে
# (এখানে প্যাটার্ন যোগ বা বাদ দিয়ে কাস্টমাইজ করুন)
# =============================================================================

IGNORE_DIRS = {
    # ভার্সন কন্ট্রোল এবং IDE
    ".git", ".svn", ".hg",
    ".vscode", ".idea", ".gemini",
    # ডিপেন্ডেন্সি
    "node_modules", "venv", ".venv", "env", "virtualenv",
    # পাইথন ক্যাশ
    "__pycache__", ".pytest_cache",
    # বিল্ড আউটপুট
    "dist", "build", "out", "target", "bin", "obj",
    "dist-admin", "dist-user", "dist-mobile",
    ".next", ".nuxt", ".svelte-kit", ".turbo",
    # লগ
    "logs", "log",
    # অটো-জেনারেটেড ডকস
    "autogen",
    # কভারেজ
    "htmlcov", ".coverage",
}

IGNORE_FILE_PATTERNS = [
    # সিক্রেট ফাইল (কখনো এক্সপোর্ট করবেন না)
    ".env", ".env.*", "*.env", "render.env",
    # পাইথন বাইনারি
    "*.pyc", "*.pyo", "*.pyd",
    # লক ফাইল
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    # ইমেজ ফাইল
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.svg", "*.ico", "*.webp", "*.bmp", "*.tiff",
    # ভিডিও/অডিও
    "*.mp4", "*.mp3", "*.wav", "*.ogg", "*.webm", "*.avi", "*.mov",
    # ডকুমেন্ট
    "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx", "*.ppt", "*.pptx",
    # আর্কাইভ/কম্প্রেসড
    "*.zip", "*.tar", "*.gz", "*.rar", "*.7z", "*.tar.gz",
    # বাইনারি/কম্পাইলড
    "*.exe", "*.dll", "*.so", "*.dylib", "*.wasm",
    # ডেটাবেস
    "*.sqlite", "*.sqlite3", "*.db",
    # লগ ফাইল
    "*.log", "temp_*.txt",
    # পুরানো codebase export ফাইল
    "*codebase*.md", "full_codebase*.md", "codebase_full*.md",
    "*_codebase.md", "backend_codebase.md", "frontend_codebase.md",
    # টার্বো ক্যাশ
    "*.tar.zst",
    # মিনিফাইড JS
    "*.min.js", "*.min.css",
    # Compiled assets
    "*.chunk.js", "*.bundle.js",
    # সিস্টেম ফাইল
    ".DS_Store", "Thumbs.db",
]

# ফাইল এক্সটেনশন থেকে কোড ল্যাঙ্গুয়েজ ম্যাপিং (সিনট্যাক্স হাইলাইটিংয়ের জন্য)
LANG_MAP = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "jsx",
    "tsx": "tsx",
    "html": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "json": "json",
    "yml": "yaml",
    "yaml": "yaml",
    "toml": "toml",
    "md": "markdown",
    "sh": "bash",
    "bash": "bash",
    "ps1": "powershell",
    "dart": "dart",
    "go": "go",
    "rs": "rust",
    "sql": "sql",
    "graphql": "graphql",
    "proto": "protobuf",
    "tf": "hcl",
    "dockerfile": "dockerfile",
}


def is_ignored(path: str, root_dir: str) -> bool:
    """
    একটি ফাইল/ফোল্ডার পাথ চেক করে সেটি বাদ দেওয়া উচিত কিনা।
    প্রতিটি পাথের প্রতিটি অংশ চেক করে।
    """
    rel_path = os.path.relpath(path, root_dir)
    parts = rel_path.split(os.sep)

    # ডিরেক্টরি চেক
    for part in parts:
        if part in IGNORE_DIRS:
            return True

    # ফাইলনেম প্যাটার্ন চেক
    filename = os.path.basename(path)
    for pattern in IGNORE_FILE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return True

    # Dockerfile (এক্সটেনশন নেই কিন্তু ভ্যালিড ফাইল)
    if filename.lower() == "dockerfile":
        return False

    return False


def get_language(filename: str) -> str:
    """ফাইলের এক্সটেনশন থেকে কোড ল্যাঙ্গুয়েজ বের করুন।"""
    if filename.lower() == "dockerfile":
        return "dockerfile"
    ext = os.path.splitext(filename)[1].lstrip(".")
    return LANG_MAP.get(ext.lower(), "")


def export_codebase(root_dir: str, output_file: str, scope: str = "full") -> dict:
    """
    মূল এক্সপোর্ট ফাংশন।

    Args:
        root_dir: প্রজেক্টের রুট ডিরেক্টরি পাথ
        output_file: আউটপুট markdown ফাইলের পাথ
        scope: 'full', 'backend', বা 'frontend'

    Returns:
        এক্সপোর্ট স্ট্যাটাস সম্পর্কিত একটি dict
    """
    # স্কোপ অনুযায়ী রুট ডিরেক্টরি সেট করুন
    if scope == "backend":
        scan_dir = os.path.join(root_dir, "backend")
        print(f"📦 [SCOPE] শুধুমাত্র Backend কোড এক্সপোর্ট হবে: {scan_dir}")
    elif scope == "frontend":
        scan_dir = os.path.join(root_dir, "apps", "studio-client")
        print(f"🎨 [SCOPE] শুধুমাত্র Frontend কোড এক্সপোর্ট হবে: {scan_dir}")
    else:
        scan_dir = root_dir
        print(f"🚀 [SCOPE] সম্পূর্ণ কোডবেস এক্সপোর্ট হবে: {scan_dir}")

    if not os.path.exists(scan_dir):
        print(f"❌ ডিরেক্টরি পাওয়া যায়নি: {scan_dir}")
        sys.exit(1)

    stats = {"files_included": 0, "files_skipped": 0, "total_lines": 0}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(output_file, "w", encoding="utf-8") as outfile:
        # হেডার লিখুন
        outfile.write("# SupremeAI 2.0 — Codebase Export\n\n")
        outfile.write(f"> **Generated At:** `{timestamp}`  \n")
        outfile.write(f"> **Scope:** `{scope}`  \n")
        outfile.write(f"> **Root:** `{scan_dir}`\n\n")
        outfile.write("---\n\n")

        # ডিরেক্টরি ট্রি ওয়াক করুন
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            # ইগনোরড ডিরেক্টরিগুলো ছেঁটে ফেলুন (in-place modification দরকার)
            dirnames[:] = sorted([
                d for d in dirnames
                if not is_ignored(os.path.join(dirpath, d), root_dir)
            ])

            for filename in sorted(filenames):
                filepath = os.path.join(dirpath, filename)

                if is_ignored(filepath, root_dir):
                    stats["files_skipped"] += 1
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8") as infile:
                        content = infile.read()

                    # খালি ফাইল বাদ দিন
                    if not content.strip():
                        stats["files_skipped"] += 1
                        continue

                    rel_path = os.path.relpath(filepath, root_dir).replace("\\", "/")
                    lang = get_language(filename)
                    lines = content.count("\n") + 1

                    # markdown-এ লিখুন
                    outfile.write(f"## `{rel_path}`\n\n")
                    outfile.write(f"```{lang}\n")
                    outfile.write(content)
                    if not content.endswith("\n"):
                        outfile.write("\n")
                    outfile.write("```\n\n")

                    stats["files_included"] += 1
                    stats["total_lines"] += lines
                    print(f"  ✅ {rel_path} ({lines} lines)")

                except UnicodeDecodeError:
                    # বাইনারি ফাইল — বাদ দিন
                    stats["files_skipped"] += 1
                except Exception as e:
                    print(f"  ⚠️  {filepath}: {e}")
                    stats["files_skipped"] += 1

    return stats


def main():
    # ==========================================================================
    # কমান্ড লাইন আর্গুমেন্ট পার্স করুন
    # ==========================================================================
    parser = argparse.ArgumentParser(
        description="SupremeAI 2.0 Codebase Exporter — কোডবেসকে Markdown-এ রূপান্তর করুন",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
উদাহরণ:
  # সম্পূর্ণ কোডবেস এক্সপোর্ট (ডিফল্ট):
  python scripts/export_codebase.py

  # শুধু Backend:
  python scripts/export_codebase.py --scope backend

  # শুধু Frontend:
  python scripts/export_codebase.py --scope frontend

  # কাস্টম আউটপুট:
  python scripts/export_codebase.py --output D:/claude_export.md

  # ভিন্ন প্রজেক্ট রুট:
  python scripts/export_codebase.py --root C:/other_project --output C:/out.md
        """
    )

    # প্রজেক্ট রুট — ডিফল্ট এই স্ক্রিপ্টের দুই লেভেল উপরে
    default_root = str(Path(__file__).resolve().parent.parent)
    # আউটপুট ফাইল — ডিফল্ট প্রজেক্ট রুটে
    default_output = os.path.join(default_root, "codebase_export.md")

    parser.add_argument(
        "--root",
        default=default_root,
        help=f"প্রজেক্টের রুট ডিরেক্টরি (ডিফল্ট: {default_root})",
    )
    parser.add_argument(
        "--output",
        default=default_output,
        help=f"আউটপুট .md ফাইলের পাথ (ডিফল্ট: {default_output})",
    )
    parser.add_argument(
        "--scope",
        choices=["full", "backend", "frontend"],
        default="full",
        help="কোন অংশ এক্সপোর্ট করবেন: full, backend, frontend (ডিফল্ট: full)",
    )

    args = parser.parse_args()

    # ==========================================================================
    # এক্সপোর্ট শুরু করুন
    # ==========================================================================
    print("\n" + "=" * 60)
    print("  🚀 SupremeAI 2.0 Codebase Exporter")
    print("=" * 60)
    print(f"  📁 Root   : {args.root}")
    print(f"  💾 Output : {args.output}")
    print(f"  🎯 Scope  : {args.scope}")
    print("=" * 60 + "\n")

    stats = export_codebase(args.root, args.output, args.scope)

    # আউটপুট ফাইলের সাইজ বের করুন
    file_size_mb = os.path.getsize(args.output) / (1024 * 1024)

    print("\n" + "=" * 60)
    print("  ✅ এক্সপোর্ট সম্পন্ন!")
    print("=" * 60)
    print(f"  📄 ফাইল ইনক্লুড  : {stats['files_included']}")
    print(f"  🚫 ফাইল স্কিপড   : {stats['files_skipped']}")
    print(f"  📝 মোট লাইন      : {stats['total_lines']:,}")
    print(f"  💾 ফাইল সাইজ     : {file_size_mb:.2f} MB")
    print(f"  📍 সেভ হয়েছে     : {args.output}")
    print("=" * 60)

    # সাইজ অনুযায়ী সতর্কবার্তা
    if file_size_mb < 5:
        print("\n  ✅ Claude.ai-তে সরাসরি আপলোড করুন।")
    elif file_size_mb < 20:
        print("\n  ⚠️  ফাইলটি Claude-এ আপলোড করা সম্ভব, কিন্তু বড়।")
        print("     যদি সমস্যা হয়: python scripts/export_codebase.py --scope backend")
    else:
        print("\n  ❌ ফাইলটি অনেক বড়। আলাদা scope-এ এক্সপোর্ট করুন:")
        print("     python scripts/export_codebase.py --scope backend")
        print("     python scripts/export_codebase.py --scope frontend")

    print()


if __name__ == "__main__":
    main()

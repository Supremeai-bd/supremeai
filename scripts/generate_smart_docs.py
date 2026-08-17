#!/usr/bin/env python3
"""
🤖 স্মার্ট ডকুমেন্টেশন জেনারেটর — SupremeAI 2.0
মডুলার কোডবেস, চেঞ্জলগ এবং সিঙ্গেল-ফাইল কোডবেস ডাম্প অটো-জেনারেশন
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime

# ফাইল এক্সটেনশন যা ডকুমেন্ট করতে হবে (বাংলা মন্তব্য: প্রজেক্টের প্রয়োজনীয় সব এক্সটেনশন)
DOCUMENT_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx',
    '.dart', '.yml', '.yaml', '.json',
    '.toml', '.lock', '.md', '.sql',
    '.go', '.rs', '.java', '.rb', '.cpp', '.c'
}

# এড়িয়ে যাওয়ার ফোল্ডার (বাংলা মন্তব্য: যেসব ফোল্ডার আমাদের ডকুমেন্টে অন্তর্ভুক্ত করার প্রয়োজন নেই, মরিচা বা রাস্টের target ডিরেক্টরি সহ)
IGNORE_DIRS = {
    '.git', 'node_modules', '.venv', '.env',
    '.docusaurus', 'docs', '.next', 'dist',
    'build', 'out', '__pycache__', '.pytest_cache',
    '.mypy_cache', 'venv', 'env', '.idea',
    '.vscode', 'coverage', 'logs', 'artifacts', 'brain', '.agents',
    'target'
}

def should_skip_path(path_str: str) -> bool:
    """পাথ স্কিপ করা উচিত কিনা চেক করুন (বাংলা মন্তব্য: পাথ পার্টস চেক করে ডট ফোল্ডার ও ইগনোর লিস্টের ফোল্ডারগুলো স্কিপ করার ফাংশন)"""
    parts = Path(path_str).parts
    for part in parts:
        if part in IGNORE_DIRS:
            return True
        if part.startswith('.') and part != '.github':
            return True
    return False

def sanitize_filename(file_path: str) -> str:
    """ফাইল পাথকে নিরাপদ ফাইলনামে রূপান্তর করুন"""
    name = file_path.replace(os.sep, '_').replace('..', '_parent_').replace(' ', '_')
    while '__' in name:
        name = name.replace('__', '_')
    return name

def generate_docs():
    # ডিরেক্টরি সেটআপ (বাংলা মন্তব্য: সব ফাইল docs/autogen এর ভেতরে তৈরি হবে)
    base_dir = Path("docs/autogen")
    codebase_dir = base_dir / "codebase"
    changes_dir = base_dir / "changes"
    full_dump_path = base_dir / "codebase_full.md"

    # আগে পুরনো ফাইল ডিলিট করে নেওয়া (যেন ডিলিট করা ফাইলের পুরনো ডকস থেকে না যায়)
    import shutil
    if codebase_dir.exists():
        shutil.rmtree(codebase_dir)
    codebase_dir.mkdir(parents=True, exist_ok=True)
    changes_dir.mkdir(parents=True, exist_ok=True)

    print("Generating modular codebase and codebase_full dump...")

    file_count = 0
    total_size = 0
    full_dump_content = "# 🧠 SupremeAI 2.0 Codebase Dump\n"
    full_dump_content += "# বাংলা মন্তব্য: এটি একটি স্বয়ংক্রিয়ভাবে জেনারেট করা কোডবেস ডাম্প ফাইল যা প্রজেক্টের সামগ্রিক বিশ্লেষণের জন্য ব্যবহৃত হয়।\n\n"
    full_dump_content += f"Generated at: {datetime.now().isoformat()}\n\n"

    # ১. মডুলার কোডবেস এবং ফুল ডাম্প জেনারেশন
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if not should_skip_path(os.path.join(root, d))]

        for file in files:
            file_path = Path(root) / file

            if file_path.suffix not in DOCUMENT_EXTENSIONS:
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='replace')
                rel_path = file_path.relative_to(".")

                # মডুলার ফাইল তৈরি
                modular_name = sanitize_filename(str(rel_path))
                output_file = codebase_dir / f"{modular_name}.md"

                file_size = len(content.encode('utf-8'))
                total_size += file_size

                header = f"# 📄 ফাইল: {rel_path}\n\n**প্রকার:** {file_path.suffix}  \n**সাইজ:** {file_size:,} বাইট  \n**আপডেট:** {datetime.now().isoformat()}\n\n---\n\n## কোড\n\n"
                output_file.write_text(header + f"```{file_path.suffix[1:]}\n{content}\n```", encoding='utf-8')
                file_count += 1

                # ফুল ডাম্প ফাইলে যুক্ত করা
                full_dump_content += f"\n## File: `{rel_path}`\n\n```{file_path.suffix[1:]}\n{content}\n```\n"

            except Exception as e:
                print(f"Skipped {file_path}: {e}")

    # ফুল ডাম্প ফাইল লেখা
    full_dump_path.write_text(full_dump_content, encoding='utf-8')
    print(f"Documented {file_count} files ({total_size:,} bytes)")

    # ২. লাস্ট ১০টি কমিটের চেঞ্জলগ তৈরি (বাংলা মন্তব্য: গিট থেকে শেষ ১০টি কমিটের ডিটেইলস নিয়ে ফাইল তৈরি)
    # বাংলা মন্তব্য: ডিফ সাইজ ৫০০ কেবি-তে সীমাবদ্ধ রাখা হচ্ছে যাতে চেঞ্জলগ ফাইল খুব বড় না হয়ে পেজেস ডিপ্লয়মেন্ট ব্যর্থ না হয়
    MAX_DIFF_SIZE = 500 * 1024  # ৫০০ কেবি সর্বোচ্চ ডিফ সাইজ
    print("Generating changelogs for the last 10 commits...")
    try:
        commits = subprocess.check_output(["git", "log", "-n", "10", "--format=%H"]).decode().splitlines()
        for commit in commits:
            try:
                commit_info = subprocess.check_output(["git", "show", "--stat", commit]).decode('utf-8', errors='replace')
                diff = subprocess.check_output(["git", "show", commit]).decode('utf-8', errors='replace')

                # বাংলা মন্তব্য: ডিফ খুব বড় হলে ছেঁটে ফেলা হচ্ছে যাতে GitHub Pages লিমিট অতিক্রম না করে
                if len(diff) > MAX_DIFF_SIZE:
                    diff = diff[:MAX_DIFF_SIZE] + f"\n\n... [TRUNCATED — diff was {len(diff):,} bytes, capped at {MAX_DIFF_SIZE:,}] ...\n"

                changelog_content = f"# 📋 Commit {commit}\n\n## Commit Stats\n```\n{commit_info}\n```\n\n## Diff Detail\n```diff\n{diff}\n```\n"
                (changes_dir / f"change_{commit}.md").write_text(changelog_content, encoding='utf-8')
            except Exception as ce:
                print(f"Failed to process commit {commit}: {ce}")
    except Exception as ge:
        print(f"Failed to get git history: {ge}")

    # ৩. পুরনো চেঞ্জলগ ফাইলগুলো পরিষ্কার করা (সর্বশেষ ১০টি রাখা)
    change_files = sorted(changes_dir.glob("change_*.md"), key=os.path.getmtime, reverse=True)
    if len(change_files) > 10:
        print("Pruning old changelogs (keeping max 10)...")
        for f in change_files[10:]:
            try:
                f.unlink()
            except Exception as e:
                print(f"Failed to delete file {f}: {e}")

    # ৪. ইনডেক্স ফাইল জেনারেশন (docs/autogen/INDEX.md)
    index_content = f"""# 📚 SupremeAI অটো-ডকুমেন্টেশন ইনডেক্স

## পাইপলাইন কনফিগারেশন
- **সিআই/সিডি ওয়ার্কফ্লো ডকুমেন্টেশন:** [CI_PIPELINE.md](../../CI_PIPELINE.md) (বাংলা মন্তব্য: মূল পাইপলাইন আর্কিটেকচার বর্ণনা)

## মডুলার কোডবেস
এই ফোল্ডারটিতে আপনার সম্পূর্ণ প্রজেক্টের মডুলার ডকুমেন্টেশন রয়েছে।
- **ডিরেক্টরি:** [codebase/](codebase/)
- **কোডবেস ডাম্প:** [codebase_full.md](codebase_full.md) (পুরো কোডবেস একটি ফাইলে)

## চেঞ্জলগ
সর্বশেষ ১০টি কমিটের বিস্তারিত পরিবর্তন এখানে সংরক্ষিত।
- **ডিরেক্টরি:** [changes/](changes/)

---
*স্বয়ংক্রিয়ভাবে তৈরি — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    (base_dir / "INDEX.md").write_text(index_content, encoding='utf-8')
    print("Generated INDEX.md successfully.")

if __name__ == "__main__":
    generate_docs()
    print("Documentation generated successfully in docs/autogen/")

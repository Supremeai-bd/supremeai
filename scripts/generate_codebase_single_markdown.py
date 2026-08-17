#!/usr/bin/env python3
"""
🤖 একক-ফাইল কোডবেস ডাম্প জেনারেটর — SupremeAI 2.0
এই স্ক্রিপ্টটি পুরো কোডবেসের সমস্ত ফাইলকে একটি একক মার্কডাউন ফাইলে রূপান্তর করে docs/autogen/full ফোল্ডারে সংরক্ষণ করে।
"""

import os
from pathlib import Path
from datetime import datetime

# ফাইল এক্সটেনশন যা ডকুমেন্ট করতে হবে (বাংলা মন্তব্য: প্রজেক্টের প্রয়োজনীয় সব এক্সটেনশন)
DOCUMENT_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx',
    '.dart', '.yml', '.yaml', '.json',
    '.toml', '.lock', '.md', '.sql',
    '.go', '.rs', '.java', '.rb', '.cpp', '.c'
}

# এড়িয়ে যাওয়ার ফোল্ডার (বাংলা মন্তব্য: যেসব ফোল্ডার আমাদের ডকুমেন্টে অন্তর্ভুক্ত করার প্রয়োজন নেই, রাস্টের target ডিরেক্টরি সহ)
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

def generate_full_codebase_markdown():
    # ডিরেক্টরি সেটআপ (বাংলা মন্তব্য: docs/autogen/full ডিরেক্টরি তৈরি করা হচ্ছে)
    base_dir = Path("docs/autogen/full")
    base_dir.mkdir(parents=True, exist_ok=True)

    output_file_path = base_dir / "codebase_full.md"

    print(f"Generating full codebase markdown at: {output_file_path}")

    file_count = 0
    total_size = 0
    full_dump_content = "# 🧠 SupremeAI 2.0 Full Codebase Dump\n"
    full_dump_content += "# বাংলা মন্তব্য: এটি একটি স্বয়ংক্রিয়ভাবে জেনারেট করা একক-ফাইল কোডবেস ডাম্প যা পুরো কোডবেস একসাথে দেখতে সাহায্য করে।\n\n"
    full_dump_content += f"Generated at: {datetime.now().isoformat()}\n\n"

    # কোডবেসের সব ফাইল ঘুরে দেখা (বাংলা মন্তব্য: os.walk ব্যবহার করে পুরো প্রজেক্ট স্ক্যান করা হচ্ছে)
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if not should_skip_path(os.path.join(root, d))]

        for file in files:
            file_path = Path(root) / file

            if file_path.suffix not in DOCUMENT_EXTENSIONS:
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='replace')
                rel_path = file_path.relative_to(".")

                file_size = len(content.encode('utf-8'))
                total_size += file_size

                # ফাইলে অ্যাপেন্ড করা (বাংলা মন্তব্য: প্রতিটি ফাইলের কোড ফরম্যাট সহ যোগ করা হচ্ছে)
                full_dump_content += f"\n## File: `{rel_path}`\n"
                full_dump_content += f"**Size:** {file_size:,} bytes  \n"
                full_dump_content += f"**Path:** [file:///{file_path.absolute().as_posix()}]\n\n"
                full_dump_content += f"```{file_path.suffix[1:]}\n{content}\n```\n"

                file_count += 1
            except Exception as e:
                print(f"Skipped {file_path}: {e}")

    # রাইট করা (বাংলা মন্তব্য: সব কনটেন্টকে codebase_full.md ফাইলে রাইট করা হচ্ছে)
    output_file_path.write_text(full_dump_content, encoding='utf-8')
    print(f"Successfully documented {file_count} files ({total_size:,} bytes) into {output_file_path}")

if __name__ == "__main__":
    generate_full_codebase_markdown()

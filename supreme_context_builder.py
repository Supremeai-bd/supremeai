import os
import sys
import math
from datetime import datetime

# ⚙️ কনফিগারেশন
ROOT_DIR = "."
OUTPUT_FILE = "supremeai_god_context.xml"

IGNORE_DIRS = {
    '.git', 'node_modules', 'venv', 'env', '__pycache__',
    'dist', 'build', '.next', '.vscode', '.idea', 'coverage', '.github'
}

IGNORE_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3',
    '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
    '.woff', '.woff2', '.ttf', '.eot', '.log'
}

IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock', OUTPUT_FILE, os.path.basename(__file__)
}

def generate_tree(dir_path, prefix=""):
    """প্রজেক্টের ডিরেক্টরি ট্রি তৈরি করে (AI এর Spatial Awareness এর জন্য)"""
    tree_str = ""
    try:
        entries = sorted([e for e in os.listdir(dir_path) if e not in IGNORE_DIRS and not e.startswith('.')], 
                         key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x))
    except PermissionError:
        return ""

    for i, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "
        
        if os.path.isdir(path):
            tree_str += f"{prefix}{connector}{entry}/\n"
            extension = "    " if is_last else "│   "
            tree_str += generate_tree(path, prefix + extension)
        else:
            if entry not in IGNORE_FILES and os.path.splitext(entry)[1].lower() not in IGNORE_EXTS:
                tree_str += f"{prefix}{connector}{entry}\n"
    return tree_str

def generate_ai_context():
    total_words = 0
    file_count = 0
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_file:
        # ১. প্রজেক্ট মেটাডেটা
        out_file.write(f"\n")
        out_file.write(f"\n\n")
        
        # ২. ডিরেক্টরি ট্রি (The Map)
        print("Generating Directory Tree...")
        out_file.write("<project_structure>\n")
        out_file.write("SupremeAI_Root/\n")
        out_file.write(generate_tree(ROOT_DIR))
        out_file.write("</project_structure>\n\n")

        out_file.write("<project_files>\n")

        # ৩. ফাইল কনটেন্ট (XML Format)
        print("Extracting Codebase...")
        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]

            for file in files:
                if file in IGNORE_FILES or file.startswith('.') or os.path.splitext(file)[1].lower() in IGNORE_EXTS:
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, ROOT_DIR)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if content.strip():
                        # AI এর জন্য XML ট্যাগিং
                        out_file.write(f'<file path="{rel_path}">\n')
                        out_file.write("<![CDATA[\n")
                        out_file.write(content)
                        if not content.endswith('\n'):
                            out_file.write("\n")
                        out_file.write("]]>\n")
                        out_file.write("</file>\n\n")
                        
                        total_words += len(content.split())
                        file_count += 1
                        
                except Exception:
                    pass # বাইনারি বা আনরিডেবল ফাইলগুলো সাইলেন্টলি স্কিপ করবে

        out_file.write("</project_files>\n")
        
        # ৪. টোকেন এস্টিমেশন (1 word ≈ 1.3 tokens)
        estimated_tokens = math.ceil(total_words * 1.3)
        
        print("\n=======================================")
        print(f"Success! File saved as: {OUTPUT_FILE}")
        print(f"Total Files Scanned: {file_count}")
        print(f"Estimated AI Tokens: ~{estimated_tokens:,}")
        
        if estimated_tokens > 2000000:
            print("WARNING: This is larger than Gemini 1.5 Pro's 2M context window!")
        elif estimated_tokens > 200000:
            print("TIP: Perfect for Gemini 1.5 Pro or Claude 3.5 Sonnet (200K).")
        else:
            print("TIP: Small enough for GPT-4o or any standard LLM.")
        print("=======================================\n")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    generate_ai_context()

from pathlib import Path
import os

# বাংলা মন্তব্য: স্ক্রিপ্টের সাপেক্ষে প্রজেক্ট রুট ডিরেক্টরি ডাইনামিকভাবে নির্ধারণ করা
root_dir = Path(__file__).resolve().parents[1]
output_file = root_dir / "project_code.md"

exclude_dirs = {'.git', '.venv', 'node_modules', '__pycache__', 'build', 'dist', '.dart_tool', '.idea', '.vscode', 'coverage', '.mypy_cache', '.pytest_cache', 'android', 'ios', 'web', 'windows', 'macos', 'linux'}
exclude_exts = {'.pyc', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.pdf', '.zip', '.tar', '.gz', '.db', '.sqlite3', '.lock', '.ttf'}

with open(output_file, "w", encoding="utf-8") as out:
    out.write("# SupremeAI 2.0 Codebase\n\n")
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Modify dirnames in-place to exclude directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for file in filenames:
            ext = os.path.splitext(file)[1].lower()
            if ext in exclude_exts:
                continue
            filepath = os.path.join(dirpath, file)
            rel_path = os.path.relpath(filepath, root_dir)
            out.write(f"## {rel_path}\n\n")

            # map extension to markdown language
            lang = ext.replace(".", "")
            if lang == "py": lang = "python"
            elif lang == "ts": lang = "typescript"
            elif lang == "tsx": lang = "tsx"
            elif lang == "js": lang = "javascript"
            elif lang == "jsx": lang = "jsx"
            elif lang == "dart": lang = "dart"
            elif lang == "yml" or lang == "yaml": lang = "yaml"
            elif lang == "json": lang = "json"
            elif lang == "md": lang = "markdown"
            elif lang == "sh": lang = "bash"

            out.write(f"```{lang}\n")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f"// Error reading file: {e}\n")
            out.write("\n```\n\n")
print(f"Codebase exported to {output_file}")

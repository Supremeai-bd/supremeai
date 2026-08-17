import os
import sys

# Directory to ignore
IGNORE_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules', '.turbo', 'dist', 
    'build', 'dist-user', 'dist-admin', '.idea', '.vscode', '.next', '.cache',
    'antigravity_brain_backup', '.gemini', 'htmlcov', 'coverage', '.pytest_cache',
    'artifacts', '.system_generated'
}

# Specific file extensions to include
INCLUDE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.md', 
    '.sql', '.sh', '.bat', '.css', '.html', '.env.example', '.dockerignore', '.gitignore'
}

# Explicit files to skip (like heavy lockfiles or minified files)
IGNORE_FILES = {
    'pnpm-lock.yaml', 'package-lock.json', 'poetry.lock', 'yarn.lock',
    'checks.md', 'audit_report.json', 'FULL_CODEBASE_CONTEXT.md', 'full_modified_codebase.md'
}

MAX_FILE_SIZE_KB = 250  # Skip files larger than 250KB

def generate_codebase_markdown(root_dir, output_file):
    print(f"Scanning codebase at: {root_dir}")
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("# 🔱 SupremeAI 2.0 — Complete Codebase Context for AI\n\n")
        out.write("> **System Overview:** Full repository file tree, configurations, backend, frontend, and core modules bundled for LLM contextual reasoning.\n\n")
        
        out.write("## 📁 Project Directory Structure\n\n```text\n")
        
        # 1. Print File Tree
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            rel_path = os.path.relpath(root, root_dir)
            if rel_path == ".":
                depth = 0
            else:
                depth = rel_path.count(os.sep) + 1
            
            indent = "  " * depth
            folder_name = os.path.basename(root) if rel_path != "." else "supremeai_2.0"
            out.write(f"{indent}📂 {folder_name}/\n")
            
            sub_indent = "  " * (depth + 1)
            for f in sorted(files):
                ext = os.path.splitext(f)[1]
                if ext in INCLUDE_EXTENSIONS and f not in IGNORE_FILES:
                    out.write(f"{sub_indent}📄 {f}\n")
                    
        out.write("```\n\n---\n\n## 📜 Source Code & Configuration Files\n\n")
        
        # 2. Append Content of each file
        file_count = 0
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for f in sorted(files):
                ext = os.path.splitext(f)[1]
                if ext not in INCLUDE_EXTENSIONS or f in IGNORE_FILES:
                    continue
                
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                
                # Check file size
                file_size_kb = os.path.getsize(full_path) / 1024
                if file_size_kb > MAX_FILE_SIZE_KB:
                    print(f"Skipping large file ({file_size_kb:.1f} KB): {rel_path}")
                    continue
                
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        content = infile.read()
                        
                    # Determine markdown codeblock language
                    lang = ext.lstrip('.')
                    if lang in ['tsx', 'jsx']:
                        lang = 'typescript'
                    elif lang in ['yml', 'yaml']:
                        lang = 'yaml'
                    elif lang in ['py']:
                        lang = 'python'
                    elif lang in ['ts']:
                        lang = 'typescript'
                    elif lang in ['js']:
                        lang = 'javascript'
                    elif lang in ['json']:
                        lang = 'json'
                    elif lang in ['sh', 'bash']:
                        lang = 'bash'
                    elif lang in ['md']:
                        lang = 'markdown'
                    else:
                        lang = ''

                    out.write(f"### 📄 `{rel_path}`\n\n")
                    out.write(f"```{lang}\n")
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write("```\n\n---\n\n")
                    file_count += 1
                except Exception as e:
                    print(f"Error reading {rel_path}: {e}")
                    
    print(f"Successfully compiled {file_count} files into {output_file}")

if __name__ == "__main__":
    target_root = r"c:\Users\n\supremeai\supremeai_2.0"
    output_md = os.path.join(target_root, "docs", "FULL_CODEBASE_CONTEXT.md")
    generate_codebase_markdown(target_root, output_md)


if __name__ == "__main__":
    target_root = r"c:\Users\n\supremeai\supremeai_2.0"
    output_md = os.path.join(target_root, "docs", "FULL_CODEBASE_CONTEXT.md")
    generate_codebase_markdown(target_root, output_md)

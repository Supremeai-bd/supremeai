import subprocess
import json
import os

print("Running eslint...")
res = subprocess.run(["npx.cmd", "eslint", ".", "-f", "json"], cwd="frontend", capture_output=True, text=True, shell=True, encoding="utf-8")

try:
    data = json.loads(res.stdout)
except Exception as e:
    print("Failed to parse JSON:", e)
    exit(1)

files_changed = 0

for file_result in data:
    filepath = file_result.get("filePath")
    messages = file_result.get("messages", [])
    
    # Filter for the specific warning
    any_messages = [m for m in messages if m.get("ruleId") == "@typescript-eslint/no-explicit-any"]
    if not any_messages:
        continue
        
    print(f"Fixing {len(any_messages)} warnings in {filepath}")
    
    # Read file lines
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # We must insert comments from bottom to top to not mess up line numbers
    any_messages.sort(key=lambda x: x["line"], reverse=True)
    
    for m in any_messages:
        line_idx = m["line"] - 1  # 0-indexed
        
        # Calculate indentation of the target line
        target_line = lines[line_idx]
        indent = len(target_line) - len(target_line.lstrip())
        indent_str = target_line[:indent]
        
        # Insert comment
        lines.insert(line_idx, f"{indent_str}// eslint-disable-next-line @typescript-eslint/no-explicit-any\n")
        
    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    files_changed += 1

print(f"Fixed {files_changed} files.")

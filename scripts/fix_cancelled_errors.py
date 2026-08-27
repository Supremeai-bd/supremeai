import os
import re

TARGET_DIR = r"F:\supremeai\backend"
import_pattern = r"(import\s+asyncio|from\s+asyncio\s+import)"

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: 'except Exception as e:\n    ... Silenced error ...'
    # We want to check if there is an `except asyncio.CancelledError` immediately preceding this `except Exception as e:`
    # We can do this by regex substitution with a function.
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    modified = False
    needs_asyncio = False

    while i < len(lines):
        line = lines[i]
        
        # Check if line is an `except Exception as e:` and we're looking at a silenced error
        if "except Exception as e:" in line:
            # Let's peek ahead a few lines to see if it's a Silenced error pattern
            is_silenced = False
            for peek in range(1, 5):
                if i + peek < len(lines) and "Silenced error" in lines[i+peek]:
                    is_silenced = True
                    break
            
            if is_silenced:
                # Check if the previous non-empty line was `except asyncio.CancelledError:`
                # Or wait, what if we just check if it's missing?
                prev_idx = i - 1
                already_has_cancelled = False
                while prev_idx >= 0 and not lines[prev_idx].strip():
                    prev_idx -= 1
                
                # If there's already an except for CancelledError, skip
                if prev_idx >= 0:
                    prev_code = '\n'.join(lines[max(0, prev_idx-3):i])
                    if "except asyncio.CancelledError:" in prev_code:
                        already_has_cancelled = True
                
                if not already_has_cancelled:
                    indent = len(line) - len(line.lstrip())
                    spaces = " " * indent
                    new_lines.append(f"{spaces}except asyncio.CancelledError:")
                    new_lines.append(f"{spaces}    raise")
                    modified = True
                    needs_asyncio = True
        
        new_lines.append(line)
        i += 1

    if modified:
        final_content = "\n".join(new_lines)
        if needs_asyncio and not re.search(import_pattern, final_content):
            # Put import asyncio at the top after docstring or future imports
            if "from __future__ import" in final_content:
                final_content = re.sub(r'(from __future__ import .*?\n)', r'\1import asyncio\n', final_content, count=1)
            elif final_content.startswith('"""'):
                final_content = re.sub(r'(""".*?""")', r'\1\nimport asyncio', final_content, count=1, flags=re.DOTALL)
            else:
                final_content = "import asyncio\n" + final_content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"Fixed: {filepath}")

def main():
    for root, _, files in os.walk(TARGET_DIR):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                fix_file(filepath)

if __name__ == "__main__":
    main()

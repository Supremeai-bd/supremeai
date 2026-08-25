import os
import re


def fix_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read {path}: {e}")
        return False

    # Match both standard and inline "except:" blocks where the only command is "pass", optionally with comments.
    
    # 1. Multi-line: except [Exception [as e]]:\n    pass
    pattern_multi = re.compile(
        r'^(\s*)except(?:.*?):\s*(?:#[^\n]*)?\n(\s+)pass\b(?:[ \t]*#[^\n]*)?$', 
        re.MULTILINE
    )
    
    def repl_multi(m):
        indent1, indent2 = m.group(1), m.group(2)
        return f'{indent1}except Exception as e:\n{indent2}import logging\n{indent2}logging.getLogger(__name__).exception(f"Silenced error: {{e}}")'

    # 2. Single-line: except [Exception [as e]]: pass
    pattern_single = re.compile(
        r'^(\s*)except(?:.*?):\s*pass\b(?:[ \t]*#[^\n]*)?$', 
        re.MULTILINE
    )

    def repl_single(m):
        indent = m.group(1)
        return f'{indent}except Exception as e: import logging; logging.getLogger(__name__).exception(f"Silenced error: {{e}}")'

    new_content = pattern_multi.sub(repl_multi, content)
    new_content = pattern_single.sub(repl_single, new_content)

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def main():
    changed_files = 0
    # Include backend and its subfolders
    for root_dir in ['backend', 'scripts']:
        if not os.path.exists(root_dir):
            continue
        for subdir, _, files in os.walk(root_dir):
            if '.venv' in subdir or '__pycache__' in subdir:
                continue
            for file in files:
                if file.endswith('.py'):
                    path = os.path.join(subdir, file)
                    if fix_file(path):
                        print(f"Fixed {path}")
                        changed_files += 1
    print(f"Total files fixed: {changed_files}")

if __name__ == '__main__':
    main()

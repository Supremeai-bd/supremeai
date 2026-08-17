import re
import sys
from pathlib import Path

# Python script to safely auto-wire @with_error_bus decorators to functions
# containing silent exceptions or manual ErrorEvent triggers.
#
# বাংলা মন্তব্য: এই স্ক্রিপ্টটি স্বয়ংক্রিয়ভাবে functions সনাক্ত করে যেগুলোতে silent exceptions
# বা manual ErrorEvent ব্যবহার করা হয়েছে, এবং সেগুলোতে @with_error_bus decorator বসায়।

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def get_indent(line: str) -> str:
    return line[:len(line) - len(line.lstrip())]

def process_file(filepath: Path, dry_run: bool = True) -> bool:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    content = "".join(lines)

    # Target patterns
    has_silent = False
    has_error_event = 'ErrorEvent(' in content

    # Find all function definition lines and their indents
    func_pattern = re.compile(r'^(\s*)(async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(')
    functions = [] # list of (line_idx, indent, name)
    for idx, line in enumerate(lines):
        match = func_pattern.match(line)
        if match:
            functions.append((idx, match.group(1), match.group(3)))

    if not functions:
        return False

    # Find target lines (ErrorEvent or silent exception pattern)
    target_lines = []
    for idx, line in enumerate(lines):
        # Silent exception or manual ErrorEvent
        if 'ErrorEvent(' in line or 'except Exception:' in line or 'except:' in line:
            target_lines.append(idx)

    if not target_lines:
        return False

    # Map target lines to the closest preceding function
    funcs_to_decorate = set()
    for t_line in target_lines:
        closest_func = None
        for f_idx, f_indent, f_name in functions:
            if f_idx < t_line:
                closest_func = (f_idx, f_indent, f_name)
            else:
                break
        if closest_func:
            # বাংলা মন্তব্য: ইতিমধ্যেই ডেকোরেট করা ফাংশন ডুপ্লিকেট রিনেমিং/ডেকোরেটিং প্রতিরোধে ফিল্টার করা হচ্ছে
            f_idx = closest_func[0]
            prev_lines = "".join(lines[max(0, f_idx - 3):f_idx])
            if "@with_error_bus" not in prev_lines:
                funcs_to_decorate.add(closest_func)

    if not funcs_to_decorate:
        return False

    # Check if we need to modify the file
    modified = False
    offset = 0

    # Sort functions by line index ascending so we can insert decorators correctly
    sorted_funcs = sorted(list(funcs_to_decorate), key=lambda x: x[0])

    # Prepare import statement
    import_line = "from core.error_bus import with_error_bus\n"
    has_import = "from core.error_bus import with_error_bus" in content or "import with_error_bus" in content

    new_lines = list(lines)

    # Track decorated function names for reporting
    decorated_names = []

    for f_idx, indent, name in sorted_funcs:
        # Check if already decorated
        already_decorated = False
        check_idx = f_idx + offset - 1
        while check_idx >= 0:
            prev_line = new_lines[check_idx].strip()
            if prev_line.startswith("@with_error_bus"):
                already_decorated = True
                break
            if prev_line == "" or prev_line.startswith("#"):
                check_idx -= 1
                continue
            break

        if not already_decorated:
            decorator = f"{indent}@with_error_bus(\"{name}\")\n"
            new_lines.insert(f_idx + offset, decorator)
            offset += 1
            modified = True
            decorated_names.append(name)

    if modified:
        if not has_import:
            # Find a good place to insert import: after __future__ or other imports
            insert_idx = 0
            in_docstring = False
            for idx, line in enumerate(new_lines):
                cleaned = line.strip()
                if cleaned.startswith('"""') or cleaned.startswith("'''"):
                    if cleaned.count('"""') % 2 != 0 or cleaned.count("'''") % 2 != 0:
                        in_docstring = not in_docstring
                    continue
                if in_docstring:
                    continue
                if "__future__" in line:
                    insert_idx = idx + 1
                    continue
                if re.match(r'^\s*(import\s+|from\s+)', line):
                    if insert_idx <= idx:
                        insert_idx = idx
                    break
            new_lines.insert(insert_idx, import_line)

        if not dry_run:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"[Done] Modified {filepath} (Decorated: {', '.join(decorated_names)})")
        else:
            print(f"[Dry-Run] Would modify {filepath} (Decorated: {', '.join(decorated_names)})")

    return modified

def main():
    dry_run = "--apply" not in sys.argv
    backend_dir = Path("backend")

    # File filters
    py_files = list(backend_dir.glob("**/*.py"))

    modified_count = 0
    for f in py_files:
        if "test_" in f.name or f.name == "error_bus.py" or ".venv" in str(f) or "conftest.py" in f.name:
            continue
        try:
            if process_file(f, dry_run=dry_run):
                modified_count += 1
        except Exception as e:
            print(f"Error processing {f}: {e}")

    print("\nSummary:")
    if dry_run:
        print(f"Found {modified_count} files to modify. Run with --apply to write changes.")
    else:
        print(f"Successfully modified {modified_count} files.")

if __name__ == "__main__":
    main()

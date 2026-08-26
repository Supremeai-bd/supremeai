import re
import os
import sys
import argparse
from pathlib import Path


def is_in_async_function(file_path: str, line_number: int) -> bool:
    """
    Check if a line number is within an async function.
    
    This is a simple heuristic - looks for 'async def' before the line
    and checks indentation level.
    """
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        if line_number > len(lines):
            return False
        
        # Get indentation of target line
        target_line = lines[line_number - 1]
        target_indent = len(target_line) - len(target_line.lstrip())
        
        # Scan backwards from target for async def at same or lower indent
        for i in range(line_number - 2, -1, -1):
            line = lines[i]
            indent = len(line) - len(line.lstrip())
            
            # Check if this is a function definition
            stripped = line.strip()
            if stripped.startswith("async def ") and indent <= target_indent:
                return True
            elif stripped.startswith("def ") and indent <= target_indent:
                # Regular def, not async
                break
            elif stripped and indent < target_indent and not stripped.startswith("#"):
                # Dedented past function scope
                break
        
        return False
        
    except Exception:
        return False


def fix_file(file_path: str, dry_run: bool = True) -> list:
    """Fix time.sleep calls in a file."""
    
    changes = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find all time.sleep calls
        for i, line in enumerate(lines):
            if re.search(r'\btime\.sleep\s*\(', line):
                line_num = i + 1
                
                # Check if in async context
                if is_in_async_function(file_path, line_num):
                    old_line = line
                    
                    # Replace time.sleep with asyncio.sleep
                    new_line = re.sub(
                        r'\btime\.sleep\s*\(',
                        'await asyncio.sleep(',
                        line
                    )
                    
                    # Add import if not present
                    if new_line != old_line:
                        changes.append({
                            'file': file_path,
                            'line': line_num,
                            'old': old_line.strip(),
                            'new': new_line.strip(),
                            'in_async': True
                        })
                        
                        if not dry_run:
                            lines[i] = new_line
                        
        if changes and not dry_run:
            with open(file_path, 'w') as f:
                f.write('\n'.join(lines))
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    
    return changes


def main():
    parser = argparse.ArgumentParser(description='Fix blocking time.sleep calls')
    parser.add_argument('path', help='File or directory to scan')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying')
    args = parser.parse_args()
    
    path = Path(args.path)
    all_changes = []
    
    if path.is_file():
        all_changes.extend(fix_file(str(path), args.dry_run))
    elif path.is_dir():
        for py_file in path.rglob('*.py'):
            if '__pycache__' not in str(py_file):
                all_changes.extend(fix_file(str(py_file), args.dry_run))
    
    # Report
    print(f"\n{'DRY RUN' if args.dry_run else 'APPLIED'} RESULTS:")
    print("=" * 80)
    
    if all_changes:
        print(f"\nFound {len(all_changes)} time.sleep calls in async contexts:\n")
        
        for change in all_changes:
            rel_path = os.path.relpath(change['file'])
            print(f"📄 {rel_path}:{change['line']}")
            print(f"   ❌ {change['old']}")
            print(f"   ✅ {change['new']}\n")
        
        if args.dry_run:
            print("\nRun again without --dry-run to apply these fixes.")
        else:
            print(f"\n✅ Fixed {len(all_changes)} files.")
    else:
        print("\n✅ No blocking time.sleep calls found!")


if __name__ == "__main__":
    main()


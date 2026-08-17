#!/usr/bin/env python3
from pathlib import Path
import shutil

base = Path(r'C:\Users\n\supremeai\supremeai_2.0')

# Fix 1: Move remaining improvement file
improve_file = base / 'CONFIGURATION_MANAGEMENT_IMPROVEMENT_SUMMARY_BANGLA.md'
if improve_file.exists():
    target = base / 'docs' / 'archived_reports' / improve_file.name
    if not target.exists():
        shutil.move(str(improve_file), str(target))
        print('✅ Moved CONFIGURATION_MANAGEMENT_IMPROVEMENT_SUMMARY_BANGLA.md')
    else:
        print('⚠️ Already moved')

# Fix 2: python-jose already commented in pyproject.toml - verify
pyproject = base / 'backend' / 'pyproject.toml'
content = pyproject.read_text(encoding='utf-8')
if 'python-jose = ' in content and not content.split('python-jose = ')[0].endswith('#'):
    # Not yet fixed
    content = content.replace(
        'python-jose = {extras = ["cryptography"], version = "^3.3.0"}',
        '# FIXED: python-jose is deprecated. Use PyJWT instead.\n# python-jose = {extras = ["cryptography"], version = "^3.3.0"}'
    )
    pyproject.write_text(content, encoding='utf-8')
    print('✅ python-jose commented out in pyproject.toml')
else:
    print('✅ python-jose already handled')

# Fix 3: Clean duplicate scripts by making redirect stubs
redirects = {
    base / 'scripts' / 'testing' / 'check_ollama_test_coverage.py':
        base / 'scripts' / 'quality' / 'check_ollama_test_coverage.py',
    base / 'scripts' / 'resource_collection' / 'run_all_collectors.py':
        base / 'scripts' / 'run_all_collectors.py',
}

for dup, orig in redirects.items():
    if dup.exists() and orig.exists():
        if dup.read_text(encoding='utf-8') == orig.read_text(encoding='utf-8'):
            dup.unlink()
            dup.parent.mkdir(parents=True, exist_ok=True)
            stub = f'"""Redirecting to {orig.relative_to(base)}"""\n'
            dup.write_text(stub, encoding='utf-8')
            print(f'✅ Cleaned {dup.relative_to(base)}')

print('\n📊 Final fixes applied')
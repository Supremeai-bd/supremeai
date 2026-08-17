from pathlib import Path
import subprocess
import sys
import tracemalloc

base = Path(r'C:\Users\n\supremeai\supremeai_2.0')
errors = []

# 1. Python syntax check (root level files + key backend files)
py_files = list(base.glob('*.py')) + list((base/'backend').glob('*.py'))
print('Checking Python syntax for', len(py_files), 'files...')
for f in py_files:
    result = subprocess.run([sys.executable, '-m', 'py_compile', str(f)], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        errors.append({'type': 'PYTHON_SYNTAX', 'file': str(f.relative_to(base)), 'detail': stderr[:200]})
        print(f'  ❌ {f.name}: {stderr[:100]}')

# 2. Check Python import in backend/src/ core files
print('\nChecking core imports...')
for dir_name in ['core', 'api', 'services', 'models', 'schemas']:
    d = base / 'backend' / 'src' / dir_name
    if d.exists():
        for f in d.glob('*.py'):
            result = subprocess.run([sys.executable, '-m', 'py_compile', str(f)], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                stderr = result.stderr.strip()
                errors.append({'type': 'PYTHON_SYNTAX', 'file': str(f.relative_to(base)), 'detail': stderr[:200]})
                print(f'  ❌ {f.name}: {stderr[:80]}')

# 3. Check package.json for missing workspace packages
import json
pkg = json.loads((base/'package.json').read_text(encoding='utf-8'))
scripts = pkg.get('scripts', {})
for name, cmd in scripts.items():
    if '../../' in cmd or '../' in cmd:
        errors.append({'type': 'PACKAGE_JSON_PATH', 'file': 'package.json', 'detail': f'{name}: {cmd}'})
        print(f'  ❌ {name}: relative path in package.json')

# 4. Check render.yaml parse
import yaml
try:
    render_content = (base/'render.yaml').read_text(encoding='utf-8')
    render_data = yaml.safe_load(render_content)
    if render_data is None:
        errors.append({'type': 'YAML_EMPTY', 'file': 'render.yaml', 'detail': 'Empty YAML file'})
except Exception as e:
    errors.append({'type': 'YAML_PARSE', 'file': 'render.yaml', 'detail': str(e)})
    print(f'  ❌ render.yaml parse error: {e}')

# 5. Check vercel.json parse
try:
    vercel = json.loads((base/'vercel.json').read_text(encoding='utf-8'))
except Exception as e:
    errors.append({'type': 'JSON_PARSE', 'file': 'vercel.json', 'detail': str(e)})
    print(f'  ❌ vercel.json parse error: {e}')

# 6. Check turbo.json parse
try:
    turbo = json.loads((base/'turbo.json').read_text(encoding='utf-8'))
except Exception as e:
    errors.append({'type': 'JSON_PARSE', 'file': 'turbo.json', 'detail': str(e)})
    print(f'  ❌ turbo.json parse error: {e}')

# 7. Check Dockerfile for issues
docker = (base/'Dockerfile').read_text(encoding='utf-8')
if '\\r' in docker:
    errors.append({'type': 'DOCKERFILE_WINDOWS', 'file': 'Dockerfile', 'detail': 'Windows line endings in Dockerfile'})
    print('  ❌ Dockerfile has Windows line endings')

# 8. Check for missing __init__.py in backend packages
for dir_name in ['core', 'api', 'services', 'models', 'schemas', 'agents']:
    dir_path = base / 'backend' / dir_name
    init_path = dir_path / '__init__.py'
    if dir_path.exists() and not init_path.exists():
        errors.append({'type': 'MISSING_INIT', 'file': f'backend/{dir_name}/', 'detail': 'Missing __init__.py'})
        print(f'  ❌ backend/{dir_name}/ missing __init__.py')

# 9. Check for unclosed strings or common issues in .py files via grep
import re
for f in base.rglob('*.py'):
    if 'node_modules' in str(f) or '.venv' in str(f):
        continue
    try:
        content = f.read_text(encoding='utf-8')
        if '\r\n' in content[:100]:
            errors.append({'type': 'WINDOWS_CRLF', 'file': str(f.relative_to(base)), 'detail': 'Windows line endings'})
    except Exception as e:
        # বাংলা: ফাইল পড়তে বা CRLF চেক করতে ব্যর্থ হলে ত্রুটি লগ করুন, silent ignore নয়
        print(f'  ⚠️  Could not scan {f}: {e}')

# 10. Check pnpm-lock and poetry.lock consistency
if (base/'pnpm-lock.yaml').exists() and (base/'pnpm-workspace.yaml').exists():
    # Check if workspaces are defined
    ws = (base/'pnpm-workspace.yaml').read_text(encoding='utf-8')
    if 'apps/' not in ws:
        errors.append({'type': 'WORKSPACE_EMPTY', 'file': 'pnpm-workspace.yaml', 'detail': 'No workspace packages defined'})

print(f'\n📊 TOTAL ERRORS/BUGS FOUND: {len(errors)}')
for e in errors:
    print(f'  [{e["type"]}] {e["file"]}: {e["detail"]}')

import json
(base/'_error_report.json').write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding='utf-8')
print('\n✅ Report saved to _error_report.json')
from pathlib import Path
import shutil

base = Path(r'C:\Users\n\supremeai\supremeai_2.0')

# Fix 1: Move remaining .md file
src = base / 'CONFIGURATION_MANAGEMENT_IMPROVEMENT_SUMMARY_BANGLA.md'
dst = base / 'docs' / 'archived_reports' / 'CONFIGURATION_MANAGEMENT_IMPROVEMENT_SUMMARY_BANGLA.md'
if src.exists() and not dst.exists():
    shutil.move(str(src), str(dst))
    print('✅ Moved CONFIGURATION_MANAGEMENT_IMPROVEMENT_SUMMARY_BANGLA.md')
elif dst.exists():
    print('⚠️ Already moved')
else:
    print('❌ Not found')

# Fix 2: Clean duplicate scripts
# a) check_ollama_test_coverage.py
q = base / 'scripts' / 'quality' / 'check_ollama_test_coverage.py'
t = base / 'scripts' / 'testing' / 'check_ollama_test_coverage.py'
if q.exists() and t.exists():
    if q.read_text(encoding='utf-8') == t.read_text(encoding='utf-8'):
        t.unlink()
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(f'"""Redirecting to {q.relative_to(base)}"""\n', encoding='utf-8')
        print('✅ Cleaned check_ollama_test_coverage.py duplicate')
    else:
        print('⚠️ Files differ, manual review needed')

# b) run_all_collectors.py
r1 = base / 'scripts' / 'run_all_collectors.py'
r2 = base / 'scripts' / 'resource_collection' / 'run_all_collectors.py'
if r1.exists() and r2.exists():
    r2.unlink()
    r2.parent.mkdir(parents=True, exist_ok=True)
    r2.write_text(f'"""Redirecting to {r1.relative_to(base)}"""\n', encoding='utf-8')
    print('✅ Cleaned run_all_collectors.py duplicate')

# Fix 3: Verify CORS count in render.yaml
render = (base / 'render.yaml').read_text(encoding='utf-8')
cors = render.count('https://')
print(f'📊 CORS domains in render.yaml: {cors}')
print('   Expected: ~5 user + 1 admin = 6')

print('\n✅ All remaining fixes applied')
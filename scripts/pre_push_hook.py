#!/usr/bin/env python3
import subprocess, sys
# Zero-regression gate: ensure no syntax errors in changed Python files
r = subprocess.run([sys.executable, '-m', 'py_compile'] + [f for f in __import__('sys').argv[1:] if f.endswith('.py')], capture_output=True)
if r.returncode != 0:
    print(r.stderr.decode(), file=sys.stderr)
    sys.exit(r.returncode)
print('pre-push: OK')


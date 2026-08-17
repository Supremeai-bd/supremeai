import os
import re
from collections import defaultdict

test_root = "backend/tests"
pattern = re.compile(r'^\s*def\s+(test_\w+)\s*\(', re.MULTILINE)

test_map = defaultdict(list)
for root, _, files in os.walk(test_root):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            text = open(path, encoding='utf-8').read()
            for name in pattern.findall(text):
                test_map[name].append(path)

duplicates = {name: paths for name, paths in test_map.items() if len(paths) > 1}
for name, paths in sorted(duplicates.items()):
    print(f"{name}: {len(paths)} occurrences")
    for p in paths:
        print(f"  - {p}")

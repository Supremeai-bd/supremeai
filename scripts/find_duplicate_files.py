import hashlib
import os
from collections import defaultdict

test_root = "backend/tests"
hashes = defaultdict(list)
for root, _, files in os.walk(test_root):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            h = hashlib.md5(open(path, 'rb').read()).hexdigest()
            hashes[h].append(path)

for h, paths in hashes.items():
    if len(paths) > 1:
        print(f"Hash {h}:")
        for p in paths:
            print(f"  - {p}")

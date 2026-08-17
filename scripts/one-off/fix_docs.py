
files = [
    'backend/core/cache/multi_layer_cache.py',
    'backend/core/cache/autocache_proxy.py',
    'backend/core/evolution/auto_skill_creator.py',
    'backend/tools/knowledge/knowledge_base_indexer.py'
]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # find where imports or real code starts
    for idx, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from ') or line.startswith('# '):
            if not lines[idx-1].strip().endswith('\"\"\"'):
                lines.insert(idx, '\"\"\"\n')
            break

    with open(f, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    print(f"Fixed {f}")

import re

files = [
    'backend/core/agent_factory.py',
    'backend/core/config_cache.py',
    'backend/core/constants.py',
    'backend/refactor_remediation.py'
]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    docstrings = re.findall(r'(\"\"\"[\s\S]*?\"\"\")', content)
    if len(docstrings) >= 2 and docstrings[0] == docstrings[1]:
        content = content.replace(docstrings[0], '', 1).lstrip()
        print(f"Removed duplicate docstring in {f}")

    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

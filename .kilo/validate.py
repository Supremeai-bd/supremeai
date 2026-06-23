import yaml
import os

files = [
    '.github/workflows/monorepo_ci_cd.yml',
    '.github/workflows/supreme-smart-skip.yml',
    'Dockerfile.backend',
]

for f in files:
    if f.endswith('.yml'):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                yaml.safe_load(fh)
            print(f'{f}: YAML OK')
        except Exception as e:
            print(f'{f}: YAML ERROR - {e}')
    else:
        print(f'{f}: Skipped (not YAML)')

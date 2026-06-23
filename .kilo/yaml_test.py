import yaml

tests = [
    'name: Test\njobs:\n  t:\n    steps:\n      - run: echo "hello ${{ a.b }}"\n',
    'name: Test\njobs:\n  t:\n    steps:\n      - run: echo "hello world"\n',
    'name: Test\njobs:\n  t:\n    if: a == \'true\'\n    steps: []\n',
]

for i, t in enumerate(tests):
    try:
        yaml.safe_load(t)
        print(f'Test {i+1}: OK')
    except Exception as e:
        print(f'Test {i+1}: ERROR - {e}')
        print(f'Input: {t!r}')

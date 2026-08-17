import yaml
try:
    with open('.github/workflows/supreme-core-ci.yml', encoding='utf-8') as f:
        yaml.safe_load(f)
except yaml.scanner.ScannerError as e:
    print('Error at line:', e.problem_mark.line)
    print('Column:', e.problem_mark.column)
    with open('.github/workflows/supreme-core-ci.yml', encoding='utf-8') as f:
        lines = f.readlines()
        print('Line content:', repr(lines[e.problem_mark.line]))

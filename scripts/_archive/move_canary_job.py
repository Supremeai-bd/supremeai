
maintenance_path = r'c:\Users\n\supremeai\supremeai_2.0\.github\workflows\maintenance_pipeline.yml'
core_ci_path = r'c:\Users\n\supremeai\supremeai_2.0\.github\workflows\supreme-core-ci.yml'

with open(maintenance_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('  canary-deploy:'):
        canary_lines = lines[i:]
        maintenance_lines = lines[:i]
        break
else:
    print("Not found")
    exit(1)

with open(maintenance_path, 'w', encoding='utf-8') as f:
    f.writelines(maintenance_lines)

with open(core_ci_path, 'a', encoding='utf-8') as f:
    f.write('\n')
    f.writelines(canary_lines)

print("Moved canary-deploy from maintenance_pipeline.yml to supreme-core-ci.yml")

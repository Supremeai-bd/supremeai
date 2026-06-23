from pathlib import Path

env_path = Path('.env')
env_example_path = Path('.env.example')

def parse_env(content: str):
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key = line.split('=', 1)[0].strip()
        result[key] = line

env = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
existing = set(parse_env(env).keys())
example = env_example_path.read_text(encoding='utf-8') if env_example_path.exists() else ''
missing = []
for line in example.splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key = line.split('=', 1)[0].strip()
    if key and key not in existing:
        missing.append(line)

out = [env.rstrip('\n')]
if missing:
    out.append('')
    out.append('# Added from .env.example')
    out.extend(missing)

new_content = '\n'.join(out) + '\n'
env_path.write_text(new_content, encoding='utf-8')
print(f'Updated .env with {len(missing)} missing keys')

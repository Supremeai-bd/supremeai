with open('backend/pyproject.toml', 'r', encoding='utf-8') as f:
    c = f.read()

if 'python-jose' not in c:
    c = c.replace('joserfc = "^1.7.4"', 'joserfc = "^1.7.4"\npython-jose = {extras = ["cryptography"], version = "*"}')
    with open('backend/pyproject.toml', 'w', encoding='utf-8') as f:
        f.write(c)

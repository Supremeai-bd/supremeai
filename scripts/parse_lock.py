import re

with open('backend/poetry.lock', 'r') as f:
    content = f.read()

# Find all package blocks
packages = re.findall(r'\[metadata.*?name = "([^"]+)"\nversion = "([^"]+)"', content, re.DOTALL)

# Focus on key packages
key_packages = ['litellm', 'cryptography', 'pydantic', 'fastapi', 'uvicorn', 'sqlalchemy', 'httpx', 'requests']
for name, version in packages:
    if name.lower() in [k.lower() for k in key_packages]:
        print(f"{name}=={version}")

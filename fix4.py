with open('backend/core/middleware/security.py', 'r') as f:
    c = f.read()
c = c.replace('getattr(settings, "environment", "").lower() == "test"', 'getattr(settings, "env", "").lower() == "test"')
with open('backend/core/middleware/security.py', 'w') as f:
    f.write(c)

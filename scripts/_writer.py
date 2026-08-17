import os
BASE = r"c:\Users\n\supremeai\supremeai_2.0\backend\agents"

def w(p, c):
    full = os.path.join(BASE, p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"Written: {p}")

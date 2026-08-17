import re
import os

def parse_policy(filepath: str) -> dict:
    """
    বাংলা: env_maintenance_policy.md থেকে ক্যাটাগরি অনুযায়ী সিক্রেট কি (key) গুলো এক্সট্র্যাক্ট করে।
    এটি Single Source of Truth হিসেবে কাজ করে।
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    categories = {
        'infisical-vault': set(),
        'render-backend': set(),
        'render-admin': set(),
        'render-worker': set(),
        'vercel': set(),
        'github-primary': set()
    }

    # Infisical Vault
    cat1_match = re.search(r'## 🔒 Category 1: Infisical Vault.*?## ⚠️ Category 2', content, re.DOTALL)
    if cat1_match:
        text = cat1_match.group(0).split('**❓ Missing', 1)[0]
        categories['infisical-vault'].update(re.findall(r'- `([A-Za-z0-9_]+)`', text))

    # Render Backend
    rb_match = re.search(r'### ১\. Render Backend.*?### ২\.', content, re.DOTALL)
    if rb_match:
        text = rb_match.group(0).split('**❓ Missing', 1)[0]
        categories['render-backend'].update(re.findall(r'- `([A-Za-z0-9_]+)`', text))

    # Render Admin
    ra_match = re.search(r'### ২\. Render Admin.*?### ৩\.', content, re.DOTALL)
    if ra_match:
        text = ra_match.group(0).split('**❓ Missing', 1)[0]
        categories['render-admin'].update(re.findall(r'- `([A-Za-z0-9_]+)`', text))
        
    # Render Worker (fallback to backend if not defined explicitly)
    categories['render-worker'] = set(categories['render-backend'])

    # Vercel
    ver_match = re.search(r'### ৪\. Vercel Frontend.*?### ৫\.', content, re.DOTALL)
    if ver_match:
        text = ver_match.group(0).split('**❓ Missing', 1)[0]
        categories['vercel'].update(re.findall(r'- `([A-Za-z0-9_]+)`', text))

    # GitHub
    gh_match = re.search(r'### ৫\. GitHub Actions.*?### ৬\.', content, re.DOTALL)
    if gh_match:
        text = gh_match.group(0).split('**❓ Missing', 1)[0]
        categories['github-primary'].update(re.findall(r'- `([A-Za-z0-9_]+)`', text))

    # Always inject base Infisical bootstrap keys for platform envs
    base_bootstrap = {'INFISICAL_CLIENT_ID', 'INFISICAL_CLIENT_SECRET', 'INFISICAL_PROJECT_ID', 'INFISICAL_ENV'}
    categories['render-backend'].update(base_bootstrap)
    categories['render-admin'].update(base_bootstrap)
    categories['render-worker'].update(base_bootstrap)
    categories['vercel'].update(base_bootstrap)

    return categories

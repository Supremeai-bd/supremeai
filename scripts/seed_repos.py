#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> seed_repos.py
# project >> SupremeAI 2.0
# purpose >> Database seed
# module >> scripts
# ============================================================================
import re
import os

md_path = r"c:\Users\n\supremeai\supremeai_2.0\docs\-01-admin's plan\3.1supremeai-tailored-repos.md"
sql_path = r"c:\Users\n\supremeai\supremeai_2.0\backend\database\migrations\05_seed_github_repos.sql"

with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

sql = []
sql.append('-- Migration: 05_seed_github_repos.sql')
sql.append('BEGIN;')

current_category = 'General'
repo_data = {}

for line in lines:
    line = line.strip()
    if line.startswith('## Category '):
        current_category = line.split(':')[1].split('(')[0].strip()
    elif line.startswith('### '):
        repo_data = {'name': line[line.find('.')+1:].strip(), 'category': current_category}
    elif line.startswith('- **URL:**'):
        repo_data['url'] = line.split('URL:**')[1].strip()
        parts = repo_data['url'].split('/')
        if len(parts) >= 5:
            repo_data['id'] = f"{parts[3]}-{parts[4]}".lower()
        else:
            repo_data['id'] = repo_data['name'].lower().replace(' ', '-')
    elif line.startswith('- **Stars:**'):
        s = line.split('Stars:**')[1].strip()
        num = re.search(r'[\d.]+', s)
        if num:
            stars = int(float(num.group()) * (1000 if 'K' in s else 1))
        else:
            stars = 0
        repo_data['stars'] = stars
    elif line.startswith('- **Why:**'):
        repo_data['purpose'] = line.split('Why:**')[1].strip()
    elif line.startswith('- **Priority:**'):
        p = line.split('Priority:**')[1].strip().lower()
        pri = 'medium'
        if 'critical' in p: pri = 'critical'
        elif 'high' in p: pri = 'high'
        elif 'low' in p: pri = 'low'
        repo_data['priority'] = pri
        
        # Save repo
        if 'id' in repo_data and 'url' in repo_data:
            id_val = repo_data['id'].replace("'", "''")
            name_val = repo_data['name'].replace("'", "''")
            url_val = repo_data['url'].replace("'", "''")
            cat_val = repo_data['category'].replace("'", "''")
            pur_val = repo_data.get('purpose', '').replace("'", "''")
            pri_val = repo_data.get('priority', 'medium')
            stars_val = repo_data.get('stars', 0)
            
            sql.append(f"INSERT INTO github_repos (id, name, url, category, purpose, priority, stars) VALUES ('{id_val}', '{name_val}', '{url_val}', '{cat_val}', '{pur_val}', '{pri_val}', {stars_val}) ON CONFLICT (id) DO NOTHING;")
        repo_data = {}

sql.append('COMMIT;')

with open(sql_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql))
print(f'Generated {len(sql)-3} inserts into {sql_path}')

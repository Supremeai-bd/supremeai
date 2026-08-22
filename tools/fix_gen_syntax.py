#!/usr/bin/env python3
"""Fix broken parenthesis/bracket patterns in gen_knowledge_seed.py"""
import re

with open('tools/gen_knowledge_seed.py', 'r') as f:
    content = f.read()

keywords = ['assumptions=', 'invariants=', 'failure_modes=', 'counterarguments=', 'evidence=']

lines = content.split('\n')
fixed = []
for line in lines:
    stripped = line.strip()
    matched_kw = None
    for kw in keywords:
        if stripped.startswith(kw):
            matched_kw = kw
            break

    if matched_kw:
        m = re.match(r'^(\s+)', line)
        indent = m.group(1) if m else ''
        eq_idx = stripped.index('=')
        value_part = stripped[eq_idx+1:]
        # Find the last "] which marks end of last string element + list close ]
        # Pattern: " followed by ] (closing quote of last string + close of list)
        target = '"]'
        last_close = value_part.rfind(target)
        if last_close >= 0:
            list_value = value_part[:last_close + len(target)]
            fixed.append(f'{indent}{matched_kw}{list_value},')
        else:
            # Fallback: find last ] and keep up to it
            last_bracket = value_part.rfind(']')
            if last_bracket >= 0:
                list_value = value_part[:last_bracket + 1]
                fixed.append(f'{indent}{matched_kw}{list_value},')
            else:
                fixed.append(line)
    else:
        fixed.append(line)

with open('tools/gen_knowledge_seed.py', 'w') as f:
    f.write('\n'.join(fixed))

print('Fix applied successfully')

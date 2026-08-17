
path = 'backend/tests/tools/test_style_learner_ast.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('        with patch.object(learner,'):
        new_lines.append(line[4:])
    elif line.startswith('            '):
        # inside the patch
        new_lines.append(line[4:])
    elif line.startswith('        '):
        new_lines.append(line[4:])
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

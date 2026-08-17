import os
import re

tests_dir = 'backend/tests'

def fix_style_learner_ast():
    path = f'{tests_dir}/tools/test_style_learner_ast.py'
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove the `with patch("tools.style_learner.settings") as mock_settings:` and `mock_settings.openai_api_key = "test-key"`
    content = re.sub(r'\s*with patch\("tools\.style_learner\.settings"\) as mock_settings:\n\s*mock_settings\.openai_api_key = "test-key"\n', '\n', content)

    # We must fix indentation for the inner blocks. It might be easier to just remove it and unindent the next 2 lines, or just replace it with something harmless like `if True:`
    content = content.replace('with patch("tools.style_learner.settings") as mock_settings:\n        mock_settings.openai_api_key = "test-key"', 'if True:')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed test_style_learner_ast.py")

fix_style_learner_ast()

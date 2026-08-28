import subprocess
import json

actions = [
    'actions/checkout',
    'actions/cache',
    'actions/setup-python',
    'actions/setup-node',
    'actions/setup-java',
    'actions/upload-artifact',
    'actions/download-artifact',
    'actions/upload-pages-artifact',
    'actions/configure-pages',
    'docker/build-push-action',
    'docker/login-action',
    'docker/metadata-action',
    'Infisical/secrets-action',
    'dorny/paths-filter',
    'aquasecurity/trivy-action',
    'trufflesecurity/trufflehog',
    'pnpm/action-setup'
]

for repo in actions:
    try:
        res = subprocess.run(['gh', 'api', f'repos/{repo}/releases/latest'], capture_output=True, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            tag = data.get('tag_name')
            if tag:
                # Get the SHA of the tag
                res_sha = subprocess.run(['git', 'ls-remote', f'https://github.com/{repo}.git', tag], capture_output=True, text=True)
                sha = res_sha.stdout.split()[0] if res_sha.stdout else 'unknown'
                print(f'{repo}: tag={tag} sha={sha}')
            else:
                print(f'{repo}: no tag found')
        else:
            print(f'{repo}: failed {res.stderr.strip()}')
    except Exception as e:
        print(f'{repo}: failed {e}')

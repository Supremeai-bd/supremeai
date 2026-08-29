import urllib.request
import json
import traceback

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

results = []

for repo in actions:
    try:
        req = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/latest', headers={'User-Agent': 'Python', 'Accept': 'application/vnd.github.v3+json'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            tag = data.get('tag_name')
            
            # Fetch action.yml
            using = 'unknown'
            for branch in [tag, 'main', 'master']:
                yml_url = f'https://raw.githubusercontent.com/{repo}/{branch}/action.yml'
                try:
                    yml_req = urllib.request.Request(yml_url, headers={'User-Agent': 'Python'})
                    with urllib.request.urlopen(yml_req) as yml_resp:
                        yml_content = yml_resp.read().decode()
                        for line in yml_content.splitlines():
                            if 'using:' in line:
                                using = line.split('using:')[1].strip()
                                break
                    if using != 'unknown':
                        break
                except:
                    print('Silenced error in except block')
            print(f'{repo}: {tag} (using: {using})')
    except Exception as e:
        print(f'{repo}: failed {e}')

import re

with open('.github/workflows/ci.yml', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add workflow_dispatch and changes job
new_on = '''on:
  push:
    branches: [main, develop, 'feature/*', 'fix/*']
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      force_backend:
        description: 'Force Backend Run/Deploy'
        type: boolean
        default: false
      force_frontend:
        description: 'Force Frontend Run/Deploy'
        type: boolean
        default: false
      force_infra:
        description: 'Force Edge/Infra Run/Deploy'
        type: boolean
        default: false'''

content = re.sub(r'on:\s*push:.*?branches: \[main, develop\]', new_on, content, flags=re.DOTALL)

changes_job = '''jobs:
  # -----------------------------------------------------------------
  # Job 0: Path Filtering (Optimization)
  # -----------------------------------------------------------------
  changes:
    name: 🚦 Detect Changes
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend == 'true' || github.event.inputs.force_backend == 'true' }}
      frontend: ${{ steps.filter.outputs.frontend == 'true' || github.event.inputs.force_frontend == 'true' }}
      infra: ${{ steps.filter.outputs.infra == 'true' || github.event.inputs.force_infra == 'true' }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'backend/**'
              - '.github/workflows/ci.yml'
              - '.github/actions/setup-backend/**'
            frontend:
              - 'frontend/**'
              - '.github/workflows/ci.yml'
            infra:
              - 'infrastructure/**'
              - '.github/workflows/ci.yml'
'''
content = content.replace('jobs:\n  # -----------------------------------------------------------------', changes_job + '  # -----------------------------------------------------------------')

# 2. Update backend-tests
content = content.replace('  backend-tests:\n    name: 🐍 Backend Tests\n    runs-on: ubuntu-latest', 
                          '  backend-tests:\n    name: 🐍 Backend Tests\n    needs: [changes]\n    if: ${{ needs.changes.outputs.backend == \'true\' }}\n    runs-on: ubuntu-latest')

# 3. Update frontend-tests
content = content.replace('  frontend-tests:\n    name: ⚛️ Frontend Tests\n    runs-on: ubuntu-latest', 
                          '  frontend-tests:\n    name: ⚛️ Frontend Tests\n    needs: [changes]\n    if: ${{ needs.changes.outputs.frontend == \'true\' }}\n    runs-on: ubuntu-latest')

# 4. Update build needs
content = content.replace('needs: [backend-tests, frontend-tests]', 'needs: [frontend-tests]')

# 5. Update deploy-backend-ghcr needs
content = content.replace('deploy-backend-ghcr:\n    name: 🐳 Push to GHCR\n    needs: [build]', 
                          'deploy-backend-ghcr:\n    name: 🐳 Push to GHCR\n    needs: [backend-tests]')

# 6. Update deploy-cloudflare-worker needs
content = re.sub(r'deploy-cloudflare-worker:\n    name: ⚡ Deploy Cloudflare Worker\n    needs: \[build\]\n    runs-on: ubuntu-latest\n    if: github.ref == \'refs/heads/main\'', 
                 'deploy-cloudflare-worker:\n    name: ⚡ Deploy Cloudflare Worker\n    needs: [changes]\n    runs-on: ubuntu-latest\n    if: ${{ github.ref == \'refs/heads/main\' && needs.changes.outputs.infra == \'true\' }}', content)


# Write back
with open('.github/workflows/ci.yml', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated ci.yml")

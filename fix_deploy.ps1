$content = Get-Content -Path .github\workflows\deploy.yml -Raw
$newContent = $content -replace '(?s)on:\s+push:\s+branches:\s+- main', "on:
  workflow_run:
    workflows: [""CI Pipeline""]
    types:
      - completed
    branches:
      - main"
Set-Content -Path .github\workflows\deploy.yml -Value $newContent -NoNewline

<#
.SYNOPSIS
SupremeAI 2.0 deployment orchestrator for GCP Cloud Run, Railway, Render.
.PARAMETER Target
Optional deployment target: gcp | all (default: all)
#>
param(
  [ValidateSet('gcp', 'all')]
  [string]$Target = 'all'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

function Log($Message) { Write-Host "[DEPLOY] $Message" -ForegroundColor Cyan }
function Fail($Message) { Write-Host "[DEPLOY][FAIL] $Message" -ForegroundColor Red; exit 1 }

function Test-Prerequisites {
  Log "Checking prerequisites..."
  $required = @('gcloud', 'docker', 'git')
  $missing = @()
  foreach ($cmd in $required) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { $missing += $cmd }
  }
  if ($missing) { Fail "Missing tools: $($missing -join ', ')" }
  if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
      $trimmed = $line.Trim()
      if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
      $idx = $trimmed.IndexOf('=')
      if ($idx -lt 1) { continue }
      $k = $trimmed.Substring(0, $idx).Trim()
      $v = $trimmed.Substring($idx + 1).Trim()
      if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
        $v = $v.Substring(1, $v.Length - 2)
      }
      [System.Environment]::SetEnvironmentVariable($k, $v, 'Process')
    }
  }
}

function Get-RegistryImage {
  param([string]$ProjectId, [string]$Region)
  $artifactRepo = "$Region-docker.pkg.dev/$ProjectId/supremeai"
  $tag = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } else { "local-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
  return "$artifactRepo/supremeai:$tag"
}

function Deploy-GCP {
  param([string]$EnvTarget)
  Log "Deploying to GCP Cloud Run... (target: $EnvTarget)"
  if (-not $env:GCP_PROJECT_ID) { Fail "GCP_PROJECT_ID is not set" }
  if (-not $env:GCP_REGION) { $env:GCP_REGION = 'us-central1' }
  if (-not $env:GCP_SERVICE_NAME) { $env:GCP_SERVICE_NAME = 'supremeai' }
  if ($EnvTarget -eq 'production') { $env:ENV = 'production' } else { $env:ENV = $EnvTarget }

  $image = Get-RegistryImage -ProjectId $env:GCP_PROJECT_ID -Region $env:GCP_REGION
  Log "Building and pushing $image"
  docker build -t $image (Join-Path $ProjectRoot '.')
  if ($LASTEXITCODE -ne 0) { Fail 'Docker build failed' }
  docker push $image
  if ($LASTEXITCODE -ne 0) { Fail 'Docker push failed' }

  # বাংলা মন্তব্য: P0 Fix — Secrets কে CLI arguments-এ embed করা নিষিদ্ধ।
  # পরিবর্তে --set-secrets flag ব্যবহার করে GCP Secret Manager reference দেওয়া হবে।
  $setEnvVars = @("ENV=$EnvTarget")
  if ($env:GCP_PROJECT_ID) { $setEnvVars += "GCP_PROJECT_ID=$env:GCP_PROJECT_ID" }
  if ($env:GCP_REGION) { $setEnvVars += "GCP_REGION=$env:GCP_REGION" }

  $setSecrets = @()
  if ($env:OPENAI_API_KEY) { $setSecrets += "OPENAI_API_KEY=projects/$env:GCP_PROJECT_ID/secrets/OPENAI_API_KEY:latest" }
  if ($env:TELEGRAM_BOT_TOKEN) { $setSecrets += "TELEGRAM_BOT_TOKEN=projects/$env:GCP_PROJECT_ID/secrets/TELEGRAM_BOT_TOKEN:latest" }
  if ($env:SUPABASE_URL) { $setEnvVars += "SUPABASE_URL=$env:SUPABASE_URL" }
  if ($env:SUPABASE_KEY) { $setSecrets += "SUPABASE_KEY=projects/$env:GCP_PROJECT_ID/secrets/SUPABASE_KEY:latest" }
  if ($env:UPSTASH_REDIS_REST_URL) { $setEnvVars += "UPSTASH_REDIS_REST_URL=$env:UPSTASH_REDIS_REST_URL" }
  if ($env:UPSTASH_REDIS_REST_TOKEN) { $setSecrets += "UPSTASH_REDIS_REST_TOKEN=projects/$env:GCP_PROJECT_ID/secrets/UPSTASH_REDIS_REST_TOKEN:latest" }

  $envValue = $setEnvVars -join ','
  $gcloudArgs = @(
    'run', 'deploy', $env:GCP_SERVICE_NAME,
    '--image', $image,
    '--region', $env:GCP_REGION,
    '--project', $env:GCP_PROJECT_ID,
    '--no-allow-unauthenticated',
    '--set-env-vars', $envValue
  )
  if ($setSecrets.Count -gt 0) {
    $gcloudArgs += '--set-secrets'
    $gcloudArgs += ($setSecrets -join ',')
  }
  if ($env:PORT) {
    $gcloudArgs += '--port'
    $gcloudArgs += $env:PORT
  }

  & gcloud @gcloudArgs
  if ($LASTEXITCODE -ne 0) { Fail "gcloud deploy failed" }

  & gcloud run services update-traffic $env:GCP_SERVICE_NAME --region $env:GCP_REGION --project $env:GCP_PROJECT_ID --to-latest
  if ($LASTEXITCODE -ne 0) { Fail "traffic promotion failed" }
  Log 'GCP Cloud Run deployment completed'
}



try {
  Test-Prerequisites
  if ($Target -eq 'all' -or $Target -eq 'gcp') { Deploy-GCP -EnvTarget production }
  Log 'Deployment orchestration completed.'
}
catch { Fail $_ }

# run_kiri_runner.ps1 - Builds and launches SupremeAI GitHub Actions Runner inside Kiri
param(
    [string]$Repo = "Supremeai-bd/supremeai",
    [string]$RunnerName = "supremeai-kiri-runner",
    [string]$Labels = "self-hosted,local-pc,kiri,linux",
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

# 0. Intelligent RAM Guard Activation
Write-Host "Checking & optimizing host RAM before launching Kiri runner..." -ForegroundColor Cyan
$ramGuard = "C:\Users\N\Desktop\ram_guard.ps1"
if (-not (Test-Path $ramGuard)) { $ramGuard = "C:\Users\N\AppData\Local\Temp\kilo\ram_guard.ps1" }
if (Test-Path $ramGuard) {
    try {
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$ramGuard"
    } catch {
        Write-Warning "RAM guard pre-check encountered an issue: $_"
    }
}

# 1. Add Kiri bin to PATH
$kiriBin = "$env:LOCALAPPDATA\Kiri\bin"
if (Test-Path $kiriBin) {
    $env:Path = "$kiriBin;$env:Path"
}

# 2. Check docker connectivity with Kiri
Write-Host "Verifying Kiri container engine..." -ForegroundColor Cyan
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw $dockerInfo }
} catch {
    Write-Error "Cannot connect to Kiri Docker engine. Ensure Kiri is running (kiri-win.exe)."
    exit 1
}

# 3. Obtain GitHub Runner Registration Token
Write-Host "Fetching runner registration token from GitHub API..." -ForegroundColor Cyan
try {
    $tokenJson = gh api "repos/$Repo/actions/runners/registration-token" -X POST | ConvertFrom-Json
    $regToken = $tokenJson.token
    if (-not $regToken) { throw "Empty token returned" }
    Write-Host "Acquired registration token successfully (expires $($tokenJson.expires_at))." -ForegroundColor Green
} catch {
    Write-Error "Failed to get runner registration token via GitHub CLI (gh): $_"
    exit 1
}

# 4. Build Runner Docker Image
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$imageExists = docker images -q supremeai-kiri-runner:latest 2>$null

if (-not $imageExists -or $Rebuild) {
    Write-Host "Building supremeai-kiri-runner Docker image..." -ForegroundColor Cyan
    docker build -t supremeai-kiri-runner:latest $scriptDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed."
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Using cached supremeai-kiri-runner:latest image." -ForegroundColor Green
}

# 5. Clean up old container if running
Write-Host "Stopping any existing supremeai-kiri-runner container..." -ForegroundColor Cyan
docker rm -f $RunnerName 2>$null | Out-Null

# 6. Launch Kiri Runner Container
Write-Host "Starting $RunnerName in Kiri..." -ForegroundColor Cyan
$containerId = docker run -d `
    --name $RunnerName `
    --restart unless-stopped `
    -e "GH_REPO=$Repo" `
    -e "RUNNER_NAME=$RunnerName" `
    -e "RUNNER_LABELS=$Labels" `
    -e "RUNNER_TOKEN=$regToken" `
    supremeai-kiri-runner:latest

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start container."
    exit $LASTEXITCODE
}

Write-Host "Container started with ID: $containerId" -ForegroundColor Green
Write-Host "Monitoring runner initialization..." -ForegroundColor Cyan

Start-Sleep -Seconds 5
docker logs $RunnerName
Write-Host "`nKiri Local Runner is now running and online!" -ForegroundColor Green

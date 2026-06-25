# WiX Build Script for SupremeAI Desktop Application
# This script builds the Windows Installer package using WiX Toolset

param(
    [string]$Configuration = "Release",
    [string]$Version = "0.1.0"
)

Write-Host "Building SupremeAI 2.0 Windows Installer..." -ForegroundColor Green

# Paths
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$srcDir = Join-Path $projectRoot ".."
$tauriReleaseDir = Join-Path $srcDir "src-tauri\target\$Configuration\bundle\msi"

Write-Host "Tauri release directory: $tauriReleaseDir" -ForegroundColor Yellow

# Check if the MSI bundle directory exists
if (-Not (Test-Path $tauriReleaseDir)) {
    Write-Warning "Tauri MSI bundle directory not found at '$tauriReleaseDir'. Please build the Tauri app first with: tauri build"
    break
}

# Harvest files from the Tauri MSI directory using heat.exe (if available)
$wxsFile = Join-Path $projectRoot "FileList.wxs"
$heatExe = "heat" # Assuming heat is in PATH

if (Get-Command $heatExe -ErrorAction SilentlyContinue) {
    & $heatExe dir "$tauriReleaseDir" -out "$wxsFile" -gg -srd -cg ProductComponents -dr INSTALLFOLDER
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Harvested files into $wxsFile" -ForegroundColor Green
    } else {
        Write-Warning "Failed to harvest files with heat. Falling back to manual WiX."
    }
} else {
    Write-Warning "Heat.exe not found in PATH. Please install WiX Toolset and ensure heat.exe is available."
    Write-Host "To build the installer manually:" -ForegroundColor Yellow
    Write-Host "1. Install WiX Toolset: https://wixtoolset.org/" -ForegroundColor Yellow
    Write-Host "2. Run: heat dir `"$tauriReleaseDir`" -out FileList.wxs -gg -srd -cg ProductComponents -dr INSTALLFOLDER" -ForegroundColor Yellow
    Write-Host "3. Compile: candle supremeai.wxs FileList.wxs" -ForegroundColor Yellow
    Write-Host "4. Link: light supremeai.wixobj FileList.wixobj -ext WixUIExtension -o SupremeAI-Setup.msi" -ForegroundColor Yellow
}

Write-Host "`nNote: This script is a template. Adjust paths as needed." -ForegroundColor Green
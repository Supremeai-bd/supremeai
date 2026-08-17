# ============================================================
# Cloud Run Secret/Env Sync for SUPABASE_DATABASE_URL_POOLER
# বাংলা: লোকাল .env থেকে Supabase Pooled DSN নিয়ে Cloud Run-এ
# SUPABASE_DATABASE_URL_POOLER এনভায়রনমেন্ট ভেরিয়েবল সেট করে।
#
# প্রাক-শর্ত: gcloud CLI ইনস্টল + auth করা থাকতে হবে।
#   gcloud auth login
#   gcloud config set project <GCP_PROJECT_ID>
#
# ব্যবহার: .\sync_cloudrun_secret.ps1 -Service supremeai-backend -Region asia-southeast1
# ============================================================
param(
    [string]$Service  = "supremeai-api",
    [string]$Region   = "us-central1",
    [string]$EnvFile  = "..\..\.env"
)

$ErrorActionPreference = "Stop"

# .env থেকে SUPABASE_DATABASE_URL_POOLER পড়া
$resolved = Resolve-Path $EnvFile -ErrorAction SilentlyContinue
if (-not $resolved) { $resolved = Join-Path $PSScriptRoot "..\..\.env" }
$dsn = (Get-Content $resolved.Path | Where-Object { $_ -match '^\s*SUPABASE_DATABASE_URL_POOLER=' } | Select-Object -First 1) -replace '^\s*SUPABASE_DATABASE_URL_POOLER=\s*"?([^"]*)"?\s*$', '$1'

if (-not $dsn) {
    Write-Error "SUPABASE_DATABASE_URL_POOLER পাওয়া যায়নি: $($resolved.Path)"
    exit 1
}

Write-Host "🔑 Cloud Run service '$Service' ($Region)-এ SUPABASE_DATABASE_URL_POOLER সেট করা হচ্ছে..." -ForegroundColor Cyan
gcloud run services update $Service `
    --region $Region `
    --set-env-vars "SUPABASE_DATABASE_URL_POOLER=$dsn"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ সিক্রেট সিঙ্ক সফল। এখন রিডিপ্লয়/রোলআউট নিশ্চিত করুন এবং /api/v1/health 200 আসে কিনা চেক করুন।" -ForegroundColor Green
} else {
    Write-Error "❌ gcloud সিঙ্ক ব্যর্থ (gcloud auth/login আছে কিনা এবং service/region ঠিক আছে কিনা দেখুন)।"
    exit 1
}

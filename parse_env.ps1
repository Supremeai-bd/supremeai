 = Get-Content -Path "F:\supremeai backup\.env"
 = @()
 = @()

foreach ( in ) {
    if ( -match "^([^#\s][^=]+)=\s*$") {
         += [1]
    }
    elseif ( -match "^([^#\s][^=]+)=(.+)$") {
         += [1]
    }
}
Write-Host "Empty Keys:"
 | ForEach-Object { Write-Host "- " }
Write-Host "
Available Keys (Potential APIs):"
 | Where-Object {  -match "KEY|TOKEN|SECRET|PAT" } | ForEach-Object { Write-Host "- " }

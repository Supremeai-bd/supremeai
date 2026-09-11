cd (Join-Path $PSScriptRoot 'infrastructure/mcp-control-plane') ;
$start = (Get-Date);
$proc = Start-Process -FilePath 'node' -ArgumentList 'node_modules/.bin/tsx','src/index.ts' -PassThru -Wait -NoNewWindow -RedirectStandardOutput 'run_stdout.txt' -RedirectStandardError 'run_stderr.txt';
$end = (Get-Date);
Write-Host start=$start end=$end exitcode=$($proc.ExitCode.ToString());
Get-Content run_stderr.txt | Select-Object -First 30;
if((Test-Path run_stdout.txt)){Get-Content run_stdout.txt | Select-Object -First 10}
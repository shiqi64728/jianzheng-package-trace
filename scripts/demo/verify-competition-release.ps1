$ErrorActionPreference = 'Stop'
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
& (Join-Path $PSScriptRoot 'self-check-competition-mvp.ps1') -Port 8020
if ($LASTEXITCODE -ne 0) { throw 'Self-check failed.' }
& $python (Join-Path $PSScriptRoot 'verify_competition_release.py')
if ($LASTEXITCODE -ne 0) { throw 'Three-run stability verification failed.' }
Write-Host 'Competition release verification PASS (3/3).' -ForegroundColor Green

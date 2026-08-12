param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
$npm = 'C:\Program Files\nodejs\npm.cmd'
$runtime = 'E:\JianZhengData\runtime\competition-rc-v1.0'
$logDir = Join-Path $runtime 'logs'
$pidFile = Join-Path $logDir 'competition-rc-v1.0.pid'
$stdout = Join-Path $logDir 'uvicorn.stdout.log'
$stderr = Join-Path $logDir 'uvicorn.stderr.log'

& (Join-Path $PSScriptRoot 'self-check-competition-mvp.ps1') -Port $Port
if ($LASTEXITCODE -ne 0) { throw 'Competition RC self-check failed.' }

Push-Location (Join-Path $repo 'frontend')
try { & $npm run build; if ($LASTEXITCODE -ne 0) { throw 'frontend build failed.' } }
finally { Pop-Location }

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($health.pipeline_version -eq 'competition-rc-v1.0') {
            Write-Host "JianZheng Competition RC v1.0 already running: http://127.0.0.1:$Port" -ForegroundColor Green
            exit 0
        }
    } catch { }
    throw "Port $Port is occupied by another process."
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$arguments = @('-m','uvicorn','app.backend.main:app','--host','127.0.0.1','--port',"$Port")
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii
$ready = $false
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) { break }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.status -eq 'ok') { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    throw "Uvicorn failed to become ready. Inspect $stderr"
}
$warmup = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/api/model/warmup" -TimeoutSec 90
Write-Host 'JianZheng Competition RC v1.0 ready' -ForegroundColor Green
Write-Host "URL: http://127.0.0.1:$Port"
Write-Host "PID: $($process.Id); stop: scripts\demo\stop-competition-mvp.ps1"
Write-Host "Warmup: loaded=$($warmup.loaded), runtime=$($warmup.runtime), gpu=$($warmup.gpu)"

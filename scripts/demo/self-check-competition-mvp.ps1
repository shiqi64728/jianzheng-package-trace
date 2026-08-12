param([int]$Port = 8000)
$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
$config = Join-Path $repo 'configs\runtime\competition-rc-v1.0.json'
$registry = 'E:\JianZhengData\models\active\detector-v0.1.json'
$fail = 0

function Result([string]$Level, [string]$Name, [string]$Detail) {
    $color = if ($Level -eq 'PASS') {'Green'} elseif ($Level -eq 'WARN') {'Yellow'} else {'Red'}
    Write-Host "[$Level] $Name - $Detail" -ForegroundColor $color
    if ($Level -eq 'FAIL') { $script:fail++ }
}

if (Test-Path -LiteralPath $python) { Result PASS 'Python' $python } else { Result FAIL 'Python' 'not found' }
if (Test-Path -LiteralPath $python) {
    $probe = & $python -c "import json,torch,fastapi,uvicorn,multipart,httpx,cv2,ultralytics; print(json.dumps({'gpu':torch.cuda.is_available(),'gpu_name':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Result PASS 'Offline dependencies' 'FastAPI/Uvicorn/OpenCV/Torch/Ultralytics importable'
        $gpu = $probe | ConvertFrom-Json
        if ($gpu.gpu) { Result PASS 'GPU' $gpu.gpu_name } else { Result WARN 'GPU' 'unavailable; runtime fallback enabled' }
    } else { Result FAIL 'Offline dependencies' 'import failed' }
}
if (Test-Path -LiteralPath $registry) {
    $reg = Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json
    if (Test-Path -LiteralPath $reg.source_pt) {
        $actual = (Get-FileHash -LiteralPath $reg.source_pt -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -eq $reg.sha256) { Result PASS 'Active model SHA' "$($reg.model_version) / $actual" }
        else { Result FAIL 'Active model SHA' "expected=$($reg.sha256), actual=$actual" }
    } else { Result FAIL 'Active model' 'weight file missing' }
} else { Result FAIL 'Active model' 'registry missing' }
if (Test-Path -LiteralPath $config) {
    $cfg = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
    if ($cfg.pipeline_version -eq 'competition-rc-v1.0') { Result PASS 'Runtime config' $cfg.pipeline_version }
    else { Result FAIL 'Runtime config' 'invalid pipeline_version' }
    if ($cfg.database_path -like 'E:/JianZhengData/runtime/competition-rc-v1.0/*') { Result PASS 'Isolated database' $cfg.database_path }
    else { Result FAIL 'Isolated database' 'must not write to v0.1/v0.2 runtime' }
} else { Result FAIL 'Runtime config' 'competition-rc-v1.0.json missing' }
$dist = Join-Path $repo 'frontend\dist\index.html'
if (Test-Path -LiteralPath $dist) { Result PASS 'frontend/dist' $dist } else { Result WARN 'frontend/dist' 'start uses local node_modules build' }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listener) { Result PASS 'Port' "$Port available" }
else {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($health.status -eq 'ok' -and $health.pipeline_version -eq 'competition-rc-v1.0') { Result PASS 'API health' "RC already running, PID=$($listener.OwningProcess)" }
        else { Result FAIL 'Port' "$Port owned by non-RC process" }
    } catch { Result FAIL 'Port' "$Port listens without health" }
}
if (-not $listener) { Result WARN 'API health' 'server not started yet' }
if ($fail -gt 0) { Write-Host "SELF-CHECK FAIL ($fail)" -ForegroundColor Red; exit 1 }
Write-Host 'SELF-CHECK PASS' -ForegroundColor Green
exit 0

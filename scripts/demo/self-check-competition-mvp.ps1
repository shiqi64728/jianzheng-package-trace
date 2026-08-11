param([int]$Port = 8000)
$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
$config = Join-Path $repo 'configs\runtime\mvp-v0.2.json'
$registry = 'E:\JianZhengData\models\active\detector-v0.1.json'
$fail = 0

function Result([string]$Level, [string]$Name, [string]$Detail) {
    $color = if ($Level -eq 'PASS') {'Green'} elseif ($Level -eq 'WARN') {'Yellow'} else {'Red'}
    Write-Host "[$Level] $Name - $Detail" -ForegroundColor $color
    if ($Level -eq 'FAIL') { $script:fail++ }
}

if (Test-Path -LiteralPath $python) { Result PASS 'Python路径' $python } else { Result FAIL 'Python路径' '不存在' }
if (Test-Path -LiteralPath $python) {
    $probe = & $python -c "import json,torch,fastapi,uvicorn,multipart,httpx,cv2,ultralytics; print(json.dumps({'gpu':torch.cuda.is_available(),'gpu_name':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Result PASS 'Python依赖' 'FastAPI/Uvicorn/OpenCV/Torch/Ultralytics 可导入'
        $gpu = $probe | ConvertFrom-Json
        if ($gpu.gpu) { Result PASS 'GPU' $gpu.gpu_name } else { Result WARN 'GPU' '不可用，将允许惰性后备' }
    } else { Result FAIL 'Python依赖' '导入失败' }
}
if (Test-Path -LiteralPath $registry) {
    $reg = Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json
    if (Test-Path -LiteralPath $reg.source_pt) {
        $actual = (Get-FileHash -LiteralPath $reg.source_pt -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -eq $reg.sha256) { Result PASS 'active model SHA' "$($reg.model_version) / $actual" }
        else { Result FAIL 'active model SHA' "expected=$($reg.sha256), actual=$actual" }
    } else { Result FAIL 'active model' '权重文件不存在' }
} else { Result FAIL 'active model' '注册表不存在' }
if (Test-Path -LiteralPath $config) {
    $cfg = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
    if ($cfg.pipeline_version -eq 'competition-mvp-v0.2') { Result PASS 'runtime配置' $cfg.pipeline_version }
    else { Result FAIL 'runtime配置' 'pipeline_version 不正确' }
    $dbDir = Split-Path -Parent $cfg.database_path
    if (Test-Path -LiteralPath $dbDir) { Result PASS 'SQLite目录' $dbDir } else { Result WARN 'SQLite目录' '首次启动时创建' }
} else { Result FAIL 'runtime配置' 'mvp-v0.2.json 不存在' }
$dist = Join-Path $repo 'frontend\dist\index.html'
if (Test-Path -LiteralPath $dist) { Result PASS 'frontend/dist' $dist } else { Result WARN 'frontend/dist' '启动脚本将执行 build' }
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listener) { Result PASS '端口占用' "$Port 可用" }
else {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($health.status -eq 'ok' -and $health.pipeline_version -eq 'competition-mvp-v0.2') {
            Result PASS 'API health' "已有 v0.2 服务运行，PID=$($listener.OwningProcess)"
        } else { Result FAIL '端口占用' "$Port 被非 v0.2 服务占用" }
    } catch { Result FAIL '端口占用' "$Port 已监听但 health 不可用" }
}
if (-not $listener) { Result WARN 'API health' '服务尚未启动' }
if ($fail -gt 0) { Write-Host "SELF-CHECK FAIL ($fail)" -ForegroundColor Red; exit 1 }
Write-Host 'SELF-CHECK PASS' -ForegroundColor Green
exit 0

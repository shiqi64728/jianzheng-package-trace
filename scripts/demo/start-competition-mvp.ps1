param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
$npm = 'C:\Program Files\nodejs\npm.cmd'
$registry = 'E:\JianZhengData\models\active\detector-v0.1.json'

if (-not (Test-Path -LiteralPath $python)) { throw "Python不存在：$python" }
if (-not (Test-Path -LiteralPath $registry)) { throw "活动模型注册表不存在：$registry" }
& $python -c "import fastapi,uvicorn,multipart,httpx,cv2,torch,ultralytics"
if ($LASTEXITCODE -ne 0) { throw 'MVP Python依赖检查失败。' }

$dist = Join-Path $repo 'frontend\dist\index.html'
if (-not (Test-Path -LiteralPath $dist)) {
    Push-Location (Join-Path $repo 'frontend')
    try {
        & $npm install
        if ($LASTEXITCODE -ne 0) { throw 'npm install失败。' }
        & $npm run build
        if ($LASTEXITCODE -ne 0) { throw 'frontend build失败。' }
    } finally { Pop-Location }
}

Set-Location $repo
Write-Host "件证 Competition MVP v0.1 已就绪" -ForegroundColor Green
Write-Host "访问地址：http://127.0.0.1:$Port"
Write-Host '按 Ctrl+C 停止服务。'
& $python -m uvicorn app.backend.main:app --host 127.0.0.1 --port $Port

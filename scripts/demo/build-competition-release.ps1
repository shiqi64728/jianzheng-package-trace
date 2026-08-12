$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = 'D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe'
$npm = 'C:\Program Files\nodejs\npm.cmd'
$runtime = 'E:\JianZhengData\runtime\competition-rc-v1.0'
$release = Join-Path $runtime 'release'

& $python (Join-Path $PSScriptRoot 'build_competition_demo_assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Demo asset build failed.' }
Push-Location (Join-Path $repo 'frontend')
try { & $npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
finally { Pop-Location }
New-Item -ItemType Directory -Force -Path $release | Out-Null

$registry = Get-Content 'E:\JianZhengData\models\active\detector-v0.1.json' -Raw | ConvertFrom-Json
$tracked = @((Join-Path $repo 'configs\runtime\competition-rc-v1.0.json'))
$tracked += Get-ChildItem (Join-Path $repo 'ai\runtime') -File -Filter '*.py' | ForEach-Object FullName
$tracked += Get-ChildItem (Join-Path $repo 'app\backend') -Recurse -File -Filter '*.py' | ForEach-Object FullName
$tracked += Get-ChildItem (Join-Path $repo 'scripts\demo') -File | Where-Object { $_.Extension -in @('.py','.ps1') } | ForEach-Object FullName
$tracked += @(
    (Join-Path $repo 'frontend\package.json'),
    (Join-Path $repo 'frontend\package-lock.json'),
    (Join-Path $repo 'frontend\vite.config.js'),
    (Join-Path $repo 'frontend\src\App.vue'),
    (Join-Path $repo 'frontend\src\api.js'),
    (Join-Path $repo 'frontend\src\main.js'),
    (Join-Path $repo 'frontend\src\style.css')
)
$tracked += Get-ChildItem (Join-Path $repo 'frontend\dist') -Recurse -File | ForEach-Object FullName
$tracked = $tracked | Sort-Object -Unique
$files = foreach ($path in $tracked) {
    [ordered]@{ path=$path; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant(); bytes=(Get-Item -LiteralPath $path).Length }
}
$manifest = [ordered]@{
    release_version='competition-rc-v1.0'
    generated_at=(Get-Date).ToString('o')
    offline_core_runtime=$true
    internet_dependencies=@()
    repository=$repo
    runtime_root=$runtime
    active_model_version=$registry.model_version
    active_model_sha256=$registry.sha256
    active_model_path=$registry.source_pt
    files=$files
}
$path = Join-Path $release 'competition-release-manifest-v1.0.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding utf8
Write-Host "Competition release built: $path" -ForegroundColor Green

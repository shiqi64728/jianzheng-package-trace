$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path 'E:\JianZhengData\runtime\mvp-v0.2').Path
$pidFile = Join-Path $runtime 'logs\competition-mvp-v0.2.pid'
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host '未找到 v0.2 PID 文件；没有执行进程终止。' -ForegroundColor Yellow
    exit 0
}
$resolvedPid = (Resolve-Path -LiteralPath $pidFile).Path
if (-not $resolvedPid.StartsWith($runtime, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'PID 文件不在 v0.2 runtime 内，拒绝操作。'
}
$processId = [int](Get-Content -LiteralPath $resolvedPid -Raw).Trim()
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
if ($process) {
    $command = [string]$process.CommandLine
    if ($command -notmatch 'uvicorn' -or $command -notmatch 'app\.backend\.main:app') {
        throw "PID $processId 不是件证 Uvicorn 进程，拒绝终止。"
    }
    Stop-Process -Id $processId -Force
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) { throw '服务停止超时。' }
    Write-Host "已停止件证 Competition MVP v0.2（PID $processId）。" -ForegroundColor Green
} else { Write-Host "PID $processId 已不存在。" -ForegroundColor Yellow }
Remove-Item -LiteralPath $resolvedPid -Force

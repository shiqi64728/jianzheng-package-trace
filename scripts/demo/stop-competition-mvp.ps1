$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path 'E:\JianZhengData\runtime\competition-rc-v1.0').Path
$pidFile = Join-Path $runtime 'logs\competition-rc-v1.0.pid'
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'RC PID file not found; nothing to stop.' -ForegroundColor Yellow
    exit 0
}
$resolvedPid = (Resolve-Path -LiteralPath $pidFile).Path
if (-not $resolvedPid.StartsWith($runtime, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'PID file is outside RC runtime.' }
$processId = [int](Get-Content -LiteralPath $resolvedPid -Raw).Trim()
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
if ($process) {
    $command = [string]$process.CommandLine
    if ($command -notmatch 'uvicorn' -or $command -notmatch 'app\.backend\.main:app') { throw "PID $processId is not the JianZheng Uvicorn process." }
    Stop-Process -Id $processId -Force
    for ($attempt = 0; $attempt -lt 20; $attempt++) { if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) { break }; Start-Sleep -Milliseconds 250 }
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) { throw 'Server stop timed out.' }
    Write-Host "Stopped JianZheng Competition RC v1.0 (PID $processId)." -ForegroundColor Green
} else { Write-Host "PID $processId no longer exists." -ForegroundColor Yellow }
Remove-Item -LiteralPath $resolvedPid -Force

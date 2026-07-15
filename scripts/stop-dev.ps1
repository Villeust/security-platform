$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$PidFile = Join-Path $Root ".dev-runtime/processes.json"

if (-not (Test-Path $PidFile)) {
    Write-Host "No .dev-runtime/processes.json found. Nothing to stop."
    exit 0
}

$Processes = Get-Content $PidFile -Raw | ConvertFrom-Json

function Stop-ManagedProcess($Name, $Info) {
    $PidValue = [int]$Info.pid
    $Expected = [string]$Info.expectedProcessName
    $Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue

    if (-not $Process) {
        Write-Host "$Name already stopped (PID $PidValue)."
        return
    }

    if ($Process.ProcessName -ne $Expected) {
        Write-Host "$Name PID $PidValue now belongs to '$($Process.ProcessName)', expected '$Expected'. Skipped." -ForegroundColor Yellow
        return
    }

    & taskkill.exe /PID $PidValue /T /F | Out-Null
    Write-Host "$Name stopped (PID $PidValue)."
}

Stop-ManagedProcess "backend" $Processes.backend
Stop-ManagedProcess "frontend" $Processes.frontend

Remove-Item -LiteralPath $PidFile -Force
Write-Host "PID file removed."

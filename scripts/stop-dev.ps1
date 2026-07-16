$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$PidFile = Join-Path $Root ".dev-runtime/processes.json"

function Get-ProcessInfo($ProcessId) {
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $CimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $Process -and -not $CimProcess) {
        return $null
    }
    [pscustomobject]@{
        Pid = $ProcessId
        Name = if ($Process) { $Process.ProcessName } elseif ($CimProcess) { $CimProcess.Name } else { "unknown" }
        CommandLine = if ($CimProcess -and $CimProcess.CommandLine) { $CimProcess.CommandLine } else { "" }
    }
}

function Get-ChildProcessTree($ProcessId) {
    $Children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue)
    foreach ($Child in $Children) {
        $Info = Get-ProcessInfo ([int]$Child.ProcessId)
        if ($Info) {
            $Info
        }
        Get-ChildProcessTree ([int]$Child.ProcessId)
    }
}

function Stop-ManagedProcess($Name, $Info) {
    if (-not $Info -or -not $Info.pid) {
        Write-Host "$Name has no saved PID. Skipped." -ForegroundColor Yellow
        return
    }

    $PidValue = [int]$Info.pid
    $Expected = [string]$Info.expectedProcessName
    $ProcessInfo = Get-ProcessInfo $PidValue

    if (-not $ProcessInfo) {
        Write-Host "$Name already stopped (PID $PidValue)."
        return
    }

    if ($ProcessInfo.Name -ne $Expected) {
        Write-Host "$Name PID $PidValue now belongs to '$($ProcessInfo.Name)', expected '$Expected'. Skipped." -ForegroundColor Yellow
        return
    }

    $Children = @(Get-ChildProcessTree $PidValue)
    if ($Children.Count -gt 0) {
        Write-Host "$Name child processes:"
        foreach ($Child in $Children) {
            Write-Host "  PID $($Child.Pid), process: $($Child.Name)"
        }
    }

    & taskkill.exe /PID $PidValue /T /F | Out-Null
    Write-Host "$Name stopped (PID $PidValue)."
}

function Get-PortOwner($Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Test-PortFree($Port) {
    $Connection = Get-PortOwner $Port
    if (-not $Connection) {
        Write-Host "Port $Port is free."
        return $true
    }

    $OwnerPid = [int]$Connection.OwningProcess
    $ProcessInfo = Get-ProcessInfo $OwnerPid
    if (-not $ProcessInfo) {
        Write-Host "Port $Port is still busy, but the owner process is missing. This may be a stale TCP entry." -ForegroundColor Yellow
        return $false
    }

    Write-Host "Port $Port is still busy. PID: $($ProcessInfo.Pid), process: $($ProcessInfo.Name)" -ForegroundColor Yellow
    Write-Host "Command line: $($ProcessInfo.CommandLine)"
    return $false
}

if (Test-Path $PidFile) {
    $Processes = Get-Content $PidFile -Raw | ConvertFrom-Json
    Stop-ManagedProcess "backend" $Processes.backend
    Stop-ManagedProcess "frontend" $Processes.frontend
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "PID file removed."
}
else {
    Write-Host "No .dev-runtime/processes.json found. Checking ports anyway."
}

$FrontendFree = Test-PortFree 3000
$BackendFree = Test-PortFree 8000

if ($FrontendFree -and $BackendFree) {
    Write-Host "Development environment stopped."
}
else {
    Write-Host "Development environment is not fully stopped. No unrelated processes were terminated." -ForegroundColor Yellow
    exit 1
}

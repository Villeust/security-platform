$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Runtime = Join-Path $Root ".dev-runtime"
$PidFile = Join-Path $Runtime "processes.json"
$Blocked = $false

function Get-PortOwner($Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Get-ProcessInfo($ProcessId, $Port = $null) {
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $CimProcess = $null
    $CimDenied = $false
    try {
        $CimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    }
    catch {
        $CimDenied = $true
    }
    if (-not $Process -and -not $CimProcess) {
        return $null
    }
    $StartTime = $null
    if ($Process) {
        try {
            $StartTime = $Process.StartTime
        }
        catch {
            $StartTime = $null
        }
    }
    [pscustomobject]@{
        Pid = [int]$ProcessId
        Name = if ($Process) { $Process.ProcessName } elseif ($CimProcess) { $CimProcess.Name } else { "unknown" }
        CommandLine = if ($CimProcess -and $CimProcess.CommandLine) { $CimProcess.CommandLine } else { "" }
        ParentProcessId = if ($CimProcess) { $CimProcess.ParentProcessId } else { $null }
        StartTime = $StartTime
        Port = $Port
        Diagnostics = if ($CimDenied) { "Command line unavailable: access denied by Windows." } else { "" }
    }
}

function Get-ChildProcessTree($ProcessId) {
    $Children = @()
    try {
        $Children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction Stop)
    }
    catch {
        return @()
    }
    foreach ($Child in $Children) {
        $Info = Get-ProcessInfo ([int]$Child.ProcessId)
        if ($Info) {
            $Info
        }
        Get-ChildProcessTree ([int]$Child.ProcessId)
    }
}

function Test-ProjectProcess($Info, $SavedRoot = $null) {
    if (-not $Info) {
        return $false
    }
    if ($Info.CommandLine -and $Info.CommandLine.Contains($Root)) {
        return $true
    }
    if ($SavedRoot -and $SavedRoot -eq $Root) {
        return $true
    }
    return $false
}

function Write-ProcessDetails($Label, $Info, $SavedRoot = $null) {
    if (-not $Info) {
        Write-Host "$Label process details unavailable." -ForegroundColor Yellow
        return
    }
    Write-Host "$Label PID: $($Info.Pid)"
    Write-Host "$Label Process: $($Info.Name)"
    Write-Host "$Label Start Time: $($Info.StartTime)"
    Write-Host "$Label Port: $($Info.Port)"
    Write-Host "$Label Project Owned: $(Test-ProjectProcess $Info $SavedRoot)"
    Write-Host "$Label Command Line: $($Info.CommandLine)"
    if ($Info.Diagnostics) {
        Write-Host "$Label Diagnostics: $($Info.Diagnostics)" -ForegroundColor Yellow
    }
}

function Stop-Tree($Label, $PidValue) {
    if (-not $PidValue) {
        return $true
    }
    $Info = Get-ProcessInfo ([int]$PidValue)
    if (-not $Info) {
        Write-Host "$Label already stopped (PID $PidValue)."
        return $true
    }
    $Children = @(Get-ChildProcessTree ([int]$PidValue))
    if ($Children.Count -gt 0) {
        Write-Host "$Label child processes:"
        foreach ($Child in $Children) {
            Write-Host "  PID $($Child.Pid), process: $($Child.Name), started: $($Child.StartTime)"
        }
    }
    Write-Host "Stopping $Label process tree rooted at PID $PidValue..."
    $Output = & taskkill.exe /PID ([int]$PidValue) /T /F 2>&1
    $Exit = $LASTEXITCODE
    if ($Output) {
        $Output | ForEach-Object { Write-Host $_ }
    }
    Start-Sleep -Seconds 1
    if (Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue) {
        Write-Host "$Label could not be fully stopped. Windows may deny access when the process belongs to another integrity level or parent console." -ForegroundColor Yellow
        return $false
    }
    if ($Exit -ne 0) {
        Write-Host "$Label taskkill returned exit code $Exit, but the root PID is gone." -ForegroundColor Yellow
    }
    return $true
}

function Stop-ManagedProcess($Name, $Info) {
    if (-not $Info -or -not $Info.pid) {
        Write-Host "$Name has no saved PID. Skipped." -ForegroundColor Yellow
        return
    }
    $PidValue = [int]$Info.pid
    $Expected = [string]$Info.expectedProcessName
    $SavedRoot = [string]$Info.root
    $ProcessInfo = Get-ProcessInfo $PidValue
    if (-not $ProcessInfo) {
        Write-Host "$Name already stopped (PID $PidValue)."
        return
    }
    Write-ProcessDetails $Name $ProcessInfo $SavedRoot
    if ($Expected -and $ProcessInfo.Name -ne $Expected) {
        Write-Host "$Name PID $PidValue now belongs to '$($ProcessInfo.Name)', expected '$Expected'. Skipped." -ForegroundColor Yellow
        return
    }
    if (-not (Test-ProjectProcess $ProcessInfo $SavedRoot)) {
        Write-Host "$Name PID $PidValue is not verified as this project. Skipped." -ForegroundColor Yellow
        return
    }
    if (-not (Stop-Tree $Name $PidValue)) {
        $script:Blocked = $true
    }
}

function Test-PortFree($Port) {
    $Connection = Get-PortOwner $Port
    if (-not $Connection) {
        Write-Host "Port $Port is free."
        return $true
    }
    $OwnerPid = [int]$Connection.OwningProcess
    $Info = Get-ProcessInfo $OwnerPid $Port
    Write-ProcessDetails "Port $Port owner" $Info
    if (Test-ProjectProcess $Info) {
        Write-Host "Port $Port is still held by a process that appears to belong to this project." -ForegroundColor Yellow
    }
    else {
        Write-Host "Port $Port is still held by an unrelated or unverifiable process; it was not terminated." -ForegroundColor Yellow
    }
    return $false
}

if (Test-Path $PidFile) {
    try {
        $Processes = Get-Content $PidFile -Raw | ConvertFrom-Json
        Stop-ManagedProcess "backend" $Processes.backend
        Stop-ManagedProcess "frontend" $Processes.frontend
    }
    catch {
        Write-Host "Could not read PID file: $($_.Exception.Message)" -ForegroundColor Yellow
        $Blocked = $true
    }
    try {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "PID file removed."
    }
    catch {
        Write-Host "Could not remove PID file: $($_.Exception.Message)" -ForegroundColor Yellow
        $Blocked = $true
    }
}
else {
    Write-Host "No .dev-runtime/processes.json found. Checking ports anyway."
}

$FrontendFree = Test-PortFree 3000
$BackendFree = Test-PortFree 8000

if ($FrontendFree -and $BackendFree -and -not $Blocked) {
    Write-Host "Development environment stopped."
    exit 0
}

Write-Host "Development environment is not fully stopped. No unrelated processes were terminated." -ForegroundColor Yellow
Write-Host "If Windows reports Access is denied, close the owning terminal or run this script from a shell with matching privileges." -ForegroundColor Yellow
exit 1

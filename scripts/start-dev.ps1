param(
    [switch]$Seed,
    [switch]$ForceRestart,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$StartedAt = Get-Date
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Runtime = Join-Path $Root ".dev-runtime"
$PidFile = Join-Path $Runtime "processes.json"
$DoctorJsonPath = Join-Path $Runtime "platform-doctor.json"
$DoctorErrorPath = Join-Path $Runtime "platform-doctor.err"

function Write-Info($Message) {
    Write-Host $Message -ForegroundColor Cyan
}

function Fail($Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    Cleanup-PartialStartup
    exit 1
}

function Require-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "$Name is not installed or not in PATH. $InstallHint"
    }
}

function Import-DotEnv($Path) {
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content $Path | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#") -or -not $Line.Contains("=")) {
            return
        }
        $Parts = $Line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($Parts[0], $Parts[1], "Process")
    }
}

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

function Test-ProjectProcess($Info) {
    if (-not $Info) {
        return $false
    }
    if ($Info.CommandLine -and $Info.CommandLine.Contains($Root)) {
        return $true
    }
    return $false
}

function Write-ProcessDetails($Label, $Info) {
    if (-not $Info) {
        Write-Host "$Label process details unavailable." -ForegroundColor Yellow
        return
    }
    Write-Host "$Label PID: $($Info.Pid)"
    Write-Host "$Label Process: $($Info.Name)"
    Write-Host "$Label Port: $($Info.Port)"
    Write-Host "$Label Start Time: $($Info.StartTime)"
    Write-Host "$Label Project Owned: $(Test-ProjectProcess $Info)"
    Write-Host "$Label Command Line: $($Info.CommandLine)"
    if ($Info.Diagnostics) {
        Write-Host "$Label Diagnostics: $($Info.Diagnostics)" -ForegroundColor Yellow
    }
}

function Cleanup-PartialStartup() {
    if (Test-Path $PidFile) {
        try {
            & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\stop-dev.ps1") | Write-Host
        }
        catch {
            Write-Host "Partial startup cleanup failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

function Assert-PortFree($Port) {
    $Connection = Get-PortOwner $Port
    if (-not $Connection) {
        return
    }
    $Info = Get-ProcessInfo ([int]$Connection.OwningProcess) $Port
    Write-ProcessDetails "Port $Port owner" $Info
    if ((Test-ProjectProcess $Info) -and $ForceRestart) {
        Write-Host "ForceRestart: stopping existing project process on port $Port..."
        & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\stop-dev.ps1")
        Start-Sleep -Seconds 2
        if (-not (Get-PortOwner $Port)) {
            return
        }
        Fail "Port $Port is still busy after ForceRestart."
    }
    if (Test-ProjectProcess $Info) {
        Fail "Port $Port is used by this project. Re-run with -ForceRestart."
    }
    Fail "Port $Port is used by another or unverifiable process. Stop it manually if safe."
}

function Clean-StaleRuntime() {
    New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
    if (-not (Test-Path $PidFile)) {
        return
    }
    $Processes = $null
    try {
        $Processes = Get-Content $PidFile -Raw | ConvertFrom-Json
    }
    catch {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "Removed unreadable PID file."
        return
    }
    $Alive = @()
    foreach ($Name in @("backend", "frontend")) {
        $PidValue = $Processes.$Name.pid
        if ($PidValue -and (Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue)) {
            $Alive += $Name
        }
    }
    if ($Alive.Count -eq 0) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "Removed stale PID file."
        return
    }
    if ($ForceRestart) {
        Write-Host "Stopping existing project runtime from PID file..."
        & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\stop-dev.ps1")
        if (Test-Path $PidFile) {
            Fail "Existing runtime could not be stopped completely."
        }
        return
    }
    Fail "Existing runtime is recorded in $PidFile. Run with -ForceRestart to restart."
}

function Run-Step($WorkingDirectory, $Command, $Arguments) {
    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            Fail "Command failed: $Command $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-PlatformDoctor() {
    Push-Location $Backend
    try {
        & uv run python -m app.scripts.platform_doctor --json --no-color 1> $DoctorJsonPath 2> $DoctorErrorPath
        $DoctorExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    try {
        $DoctorReport = Get-Content $DoctorJsonPath -Raw | ConvertFrom-Json
    }
    catch {
        if (Test-Path $DoctorErrorPath) {
            Get-Content $DoctorErrorPath | Write-Host
        }
        Fail "Platform Doctor did not return valid JSON."
    }
    if ($DoctorReport.error_count -gt 0 -or $DoctorExitCode -ne 0) {
        if ($Force) {
            Write-Host "Platform Doctor found $($DoctorReport.error_count) error(s); continuing because -Force was supplied." -ForegroundColor Yellow
            return $DoctorReport
        }
        Push-Location $Backend
        try {
            & uv run python -m app.scripts.platform_doctor --no-color
        }
        finally {
            Pop-Location
        }
        Fail "Startup aborted by Platform Doctor."
    }
    return $DoctorReport
}

function Wait-Http($Url, $Name, $Seconds = 30) {
    $Deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return $Response
            }
        }
        catch {
        }
        Start-Sleep -Milliseconds 750
    } while ((Get-Date) -lt $Deadline)
    Fail "$Name did not become reachable at $Url."
}

Require-Command "uv" "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
Require-Command "node" "Install Node.js LTS: https://nodejs.org/"
Require-Command "npm.cmd" "Install npm with Node.js and ensure npm.cmd is in PATH."

Import-DotEnv (Join-Path $Root ".env")

if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path $Root ".uv-cache"
}
if (-not $env:UV_PROJECT_ENVIRONMENT) {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $Backend ".venv"
}

Clean-StaleRuntime
Assert-PortFree 3000
Assert-PortFree 8000

Write-Info "Checking backend dependencies..."
Run-Step $Backend "uv" @("sync")

Write-Info "Checking frontend dependencies..."
$NodeModules = Join-Path $Frontend "node_modules"
if (-not (Test-Path $NodeModules)) {
    if (Test-Path (Join-Path $Frontend "package-lock.json")) {
        Run-Step $Frontend "npm.cmd" @("ci")
    }
    else {
        Run-Step $Frontend "npm.cmd" @("install")
    }
}

Write-Info "Running migrations..."
Run-Step $Backend "uv" @("run", "alembic", "upgrade", "head")

if ($Seed) {
    Write-Info "Running demo seed..."
    Run-Step $Backend "uv" @("run", "python", "-m", "app.scripts.seed_demo")
}

Write-Info "Running Platform Doctor..."
$DoctorReport = Invoke-PlatformDoctor

$BackendLog = Join-Path $Runtime "backend.log"
$BackendErrorLog = Join-Path $Runtime "backend.err.log"
$FrontendLog = Join-Path $Runtime "frontend.log"
$FrontendErrorLog = Join-Path $Runtime "frontend.err.log"
$BackendArgs = @("-ExecutionPolicy", "Bypass", "-Command", "`$env:UV_CACHE_DIR='$($env:UV_CACHE_DIR)'; `$env:UV_PROJECT_ENVIRONMENT='$($env:UV_PROJECT_ENVIRONMENT)'; cd '$Backend'; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
$FrontendArgs = @("-ExecutionPolicy", "Bypass", "-Command", "cd '$Frontend'; npm.cmd run dev -- --host 127.0.0.1 --port 3000 --strictPort")

$BackendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $BackendArgs -WindowStyle Hidden -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrorLog -PassThru
$FrontendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $FrontendArgs -WindowStyle Hidden -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrorLog -PassThru

$Processes = [ordered]@{
    backend = [ordered]@{
        pid = $BackendProcess.Id
        expectedProcessName = "powershell"
        command = "uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
        root = $Root
        startedAt = $StartedAt.ToString("o")
    }
    frontend = [ordered]@{
        pid = $FrontendProcess.Id
        expectedProcessName = "powershell"
        command = "npm.cmd run dev -- --host 127.0.0.1 --port 3000 --strictPort"
        root = $Root
        startedAt = $StartedAt.ToString("o")
    }
}
$Processes | ConvertTo-Json -Depth 4 | Set-Content -Path $PidFile -Encoding UTF8

$Readiness = Wait-Http "http://127.0.0.1:8000/api/v1/readiness" "Backend readiness" 45
$Health = Wait-Http "http://127.0.0.1:8000/api/v1/health" "Backend health" 15
$Version = Wait-Http "http://127.0.0.1:8000/api/v1/version" "Backend version" 15
$FrontendResponse = Wait-Http "http://127.0.0.1:3000" "Frontend" 45

$VersionData = $Version.Content | ConvertFrom-Json
$Stopwatch.Stop()

Write-Host ""
Write-Host "========================================="
Write-Host "Security Platform"
Write-Host ""
Write-Host "Version $($VersionData.version)"
Write-Host ""
Write-Host "Environment $($VersionData.environment)"
Write-Host ""
Write-Host "Backend  http://127.0.0.1:8000"
Write-Host "Frontend http://127.0.0.1:3000"
Write-Host "Swagger  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Health $($Health.StatusCode)"
Write-Host "Readiness $(($Readiness.Content | ConvertFrom-Json).status)"
Write-Host "Doctor $($DoctorReport.health)%"
Write-Host "Startup Duration $([math]::Round($Stopwatch.Elapsed.TotalSeconds, 1))s"
Write-Host ""
Write-Host "PIDs saved to $PidFile"
Write-Host "========================================="

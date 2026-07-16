param(
    [switch]$Seed,
    [switch]$ForceRestart,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Runtime = Join-Path $Root ".dev-runtime"
$PidFile = Join-Path $Runtime "processes.json"

function Fail($Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Require-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "$Name is not installed or not in PATH. $InstallHint"
    }
}

function Get-PortOwner($Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

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
        ParentProcessId = if ($CimProcess) { $CimProcess.ParentProcessId } else { $null }
    }
}

function Get-ProcessAncestors($ProcessInfo) {
    $Ancestors = @()
    $Seen = @{}
    $ParentId = $ProcessInfo.ParentProcessId
    while ($ParentId -and -not $Seen.ContainsKey([string]$ParentId)) {
        $Seen[[string]$ParentId] = $true
        $Parent = Get-ProcessInfo $ParentId
        if (-not $Parent) {
            break
        }
        $Ancestors += $Parent
        $ParentId = $Parent.ParentProcessId
    }
    return $Ancestors
}

function Test-CurrentProjectProcess($ProcessInfo) {
    $ProjectPaths = @($Root, $Backend, $Frontend)
    foreach ($Path in $ProjectPaths) {
        if ($ProcessInfo.CommandLine -like "*$Path*") {
            return $true
        }
    }

    $Ancestors = Get-ProcessAncestors $ProcessInfo
    foreach ($Ancestor in $Ancestors) {
        foreach ($Path in $ProjectPaths) {
            if ($Ancestor.CommandLine -like "*$Path*") {
                $Line = "$($ProcessInfo.CommandLine) $($Ancestor.CommandLine)"
                if ($Line -match "vite|uvicorn|npm|uv|node|python|powershell") {
                    return $true
                }
            }
        }
    }

    return $false
}

function Get-ProjectStopPid($ProcessInfo) {
    $Ancestors = Get-ProcessAncestors $ProcessInfo
    foreach ($Ancestor in $Ancestors) {
        if ($Ancestor.CommandLine -like "*$Root*" -and $Ancestor.Name -match "powershell|cmd") {
            return [int]$Ancestor.Pid
        }
    }
    return [int]$ProcessInfo.Pid
}

function Write-PortProcessDetails($Port, $ProcessInfo) {
    Write-Host "Port $Port is busy." -ForegroundColor Yellow
    Write-Host "PID: $($ProcessInfo.Pid)"
    Write-Host "Process: $($ProcessInfo.Name)"
    Write-Host "Command line: $($ProcessInfo.CommandLine)"
}

function Assert-PortFree($Port) {
    $Connection = Get-PortOwner $Port
    if (-not $Connection) {
        return
    }

    $OwnerPid = [int]$Connection.OwningProcess
    $ProcessInfo = Get-ProcessInfo $OwnerPid
    if (-not $ProcessInfo) {
        Write-Host "Обнаружена зависшая запись TCP: порт занят, но процесс-владелец отсутствует. Перезагрузите Windows или очистите сетевой стек." -ForegroundColor Red
        exit 1
    }

    Write-PortProcessDetails $Port $ProcessInfo
    $IsProjectProcess = Test-CurrentProjectProcess $ProcessInfo

    if ($IsProjectProcess -and $ForceRestart) {
        $StopPid = Get-ProjectStopPid $ProcessInfo
        Write-Host "ForceRestart: stopping current project process on port $Port (PID $StopPid)..."
        & taskkill.exe /PID $StopPid /T /F | Out-Null
        Start-Sleep -Seconds 2
        if (Get-PortOwner $Port) {
            Fail "Port $Port is still busy after stopping PID $StopPid."
        }
        return
    }

    if ($IsProjectProcess) {
        Fail "Port $Port is used by this project. To restart it safely, run: powershell -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -ForceRestart"
    }

    Fail "Port $Port is used by another process. Stop it manually if it is safe, then run .\start-dev.cmd again."
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
    $DoctorJsonPath = Join-Path $Runtime "platform-doctor.json"
    $DoctorErrorPath = Join-Path $Runtime "platform-doctor.err"

    Push-Location $Backend
    try {
        & uv run python -m app.scripts.platform_doctor --json --no-color 1> $DoctorJsonPath 2> $DoctorErrorPath
        $DoctorExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $DoctorJson = if (Test-Path $DoctorJsonPath) { Get-Content $DoctorJsonPath -Raw } else { "" }
    try {
        $DoctorReport = $DoctorJson | ConvertFrom-Json
    }
    catch {
        Write-Host "Platform Doctor did not return valid JSON." -ForegroundColor Red
        if (Test-Path $DoctorErrorPath) {
            Get-Content $DoctorErrorPath | Write-Host
        }
        Fail "Platform Doctor failed before startup."
    }

    if ($DoctorReport.errors -gt 0 -or $DoctorExitCode -ne 0) {
        if ($Force) {
            Write-Host "Platform Doctor found $($DoctorReport.errors) error(s); continuing because -Force was supplied." -ForegroundColor Yellow
            return
        }

        Write-Host "Platform Doctor found $($DoctorReport.errors) error(s)." -ForegroundColor Red
        Push-Location $Backend
        try {
            & uv run python -m app.scripts.platform_doctor --no-color
        }
        finally {
            Pop-Location
        }
        Fail "Startup aborted. Re-run with -Force to bypass Platform Doctor errors."
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

Assert-PortFree 3000
Assert-PortFree 8000

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

Write-Host "Checking backend dependencies..."
Run-Step $Backend "uv" @("sync")

Write-Host "Checking frontend dependencies..."
$NodeModules = Join-Path $Frontend "node_modules"
if (-not (Test-Path $NodeModules)) {
    if (Test-Path (Join-Path $Frontend "package-lock.json")) {
        Run-Step $Frontend "npm.cmd" @("ci")
    }
    else {
        Run-Step $Frontend "npm.cmd" @("install")
    }
}

Write-Host "Running migrations..."
Run-Step $Backend "uv" @("run", "alembic", "upgrade", "head")

if ($Seed) {
    Write-Host "Running demo seed..."
    Run-Step $Backend "uv" @("run", "python", "-m", "app.scripts.seed_demo")
}

Invoke-PlatformDoctor

$BackendArgs = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "`$env:UV_CACHE_DIR='$($env:UV_CACHE_DIR)'; `$env:UV_PROJECT_ENVIRONMENT='$($env:UV_PROJECT_ENVIRONMENT)'; cd '$Backend'; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
$FrontendArgs = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$Frontend'; npm.cmd run dev -- --host 127.0.0.1 --port 3000 --strictPort")

$BackendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $BackendArgs -WindowStyle Hidden -PassThru
$FrontendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $FrontendArgs -WindowStyle Hidden -PassThru

$Processes = [ordered]@{
    backend = [ordered]@{
        pid = $BackendProcess.Id
        expectedProcessName = "powershell"
    }
    frontend = [ordered]@{
        pid = $FrontendProcess.Id
        expectedProcessName = "powershell"
    }
}
$Processes | ConvertTo-Json -Depth 4 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ""
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Swagger:  http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "PIDs saved to $PidFile"

param(
    [switch]$Seed
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
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

function Assert-PortFree($Port) {
    $Connection = Get-PortOwner $Port
    if ($Connection) {
        $OwnerPid = $Connection.OwningProcess
        $Process = Get-Process -Id $OwnerPid -ErrorAction SilentlyContinue
        $CimProcess = $null
        if (-not $Process) {
            $CimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $OwnerPid" -ErrorAction SilentlyContinue
            if (-not $CimProcess) {
                $StaleTcpMessage = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("0J7QsdC90LDRgNGD0LbQtdC90LAg0LfQsNCy0LjRgdGI0LDRjyDQt9Cw0L/QuNGB0YwgVENQOiDQv9C+0YDRgiDQt9Cw0L3Rj9GCLCDQvdC+INC/0YDQvtGG0LXRgdGBLdCy0LvQsNC00LXQu9C10YYg0L7RgtGB0YPRgtGB0YLQstGD0LXRgi4g0J/QtdGA0LXQt9Cw0LPRgNGD0LfQuNGC0LUgV2luZG93cyDQuNC70Lgg0L7Rh9C40YHRgtC40YLQtSDRgdC10YLQtdCy0L7QuSDRgdGC0LXQui4="))
                Write-Host $StaleTcpMessage -ForegroundColor Red
                exit 1
            }
        }
        $Name = if ($Process) { $Process.ProcessName } elseif ($CimProcess) { $CimProcess.Name } else { "unknown" }
        Fail "Port $Port is busy. PID: $($Connection.OwningProcess), process: $Name. Stop it manually or run .\stop-dev.cmd if it was started by this project."
    }
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

$BackendArgs = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "cd '$Backend'; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
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

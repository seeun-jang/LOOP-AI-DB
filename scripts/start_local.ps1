$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$appUrl = 'http://127.0.0.1:8000'

function Test-LoopRunning {
    try {
        $health = Invoke-RestMethod -Uri "$appUrl/api/health" -TimeoutSec 2
        return ($health.status -eq 'ok' -and $health.database -eq 'postgresql')
    } catch { return $false }
}

try {
    if (Test-LoopRunning) {
        Write-Host 'LOOP AI is already running. Opening the app...'
        Start-Process $appUrl
        exit 0
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop is required. Install it and run this launcher again.'
    }
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop, wait until it is ready, then run this launcher again.' }
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.12 or newer is required.' }
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    $runtimeDir = Join-Path $projectRoot 'work'
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $stampPath = Join-Path $runtimeDir 'requirements.sha256'
    $requiredHash = (Get-FileHash -LiteralPath (Join-Path $projectRoot 'requirements.txt') -Algorithm SHA256).Hash
    $installedHash = if (Test-Path -LiteralPath $stampPath) { (Get-Content -LiteralPath $stampPath -Raw).Trim() } else { '' }
    if ($installedHash -ne $requiredHash) {
        Write-Host 'Preparing Python packages (first run may take a few minutes)...'
        & $pythonExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check the internet connection.' }
        Set-Content -LiteralPath $stampPath -Value $requiredHash
    }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
        & $pythonExe scripts/setup_env.py
        if ($LASTEXITCODE -ne 0) { throw 'Could not create local settings.' }
    }
    Write-Host 'Starting the PostgreSQL database...'
    docker compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not start. Check Docker Desktop and port 5433.' }
    Write-Host 'Starting LOOP AI...'
    $serverProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','backend.main:create_app','--factory','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'server.log') -RedirectStandardError (Join-Path $runtimeDir 'server-error.log') -PassThru
    Set-Content -LiteralPath (Join-Path $runtimeDir 'server.pid') -Value $serverProcess.Id
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-LoopRunning) { Start-Process $appUrl; Write-Host "LOOP AI is ready: $appUrl"; exit 0 }
        Start-Sleep -Seconds 1
    }
    throw 'The app did not become ready. Check work/server-error.log in this project folder.'
} catch {
    Write-Host "LOOP AI could not start: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

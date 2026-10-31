# GitPulse — Start Backend (FastAPI + Uvicorn)
# Run from ANY directory; the script resolves paths automatically.

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir  = Join-Path $ProjectRoot "backend"
$EnvFile     = Join-Path $ProjectRoot ".env"
$EnvExample  = Join-Path $ProjectRoot ".env.example"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  GitPulse  |  FastAPI Backend" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ── .env check ──────────────────────────────────────────────────────────────
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "[WARN] .env not found. Copying from .env.example ..." -ForegroundColor Yellow
        Copy-Item $EnvExample $EnvFile
        Write-Host "[INFO] Edit '$EnvFile' and add your secrets before production use." -ForegroundColor Yellow
    } else {
        Write-Host "[WARN] Neither .env nor .env.example found. Using defaults." -ForegroundColor Yellow
    }
}

# ── Python check ─────────────────────────────────────────────────────────────
try {
    $PyVersion = python --version 2>&1
    Write-Host "[OK]  Python: $PyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERR] Python not found. Install Python 3.10+ and try again." -ForegroundColor Red
    exit 1
}

# ── uvicorn check ────────────────────────────────────────────────────────────
$UvicornInstalled = python -c "import uvicorn; print(uvicorn.__version__)" 2>$null
if (-not $UvicornInstalled) {
    Write-Host "[INFO] Installing uvicorn ..." -ForegroundColor Yellow
    pip install uvicorn[standard] fastapi
}

Write-Host ""
Write-Host "[INFO] Starting FastAPI on http://localhost:8000" -ForegroundColor Cyan
Write-Host "[INFO] API docs  → http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "[INFO] Health    → http://localhost:8000/api/v1/health" -ForegroundColor Cyan
Write-Host "[INFO] Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

Set-Location $BackendDir
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info


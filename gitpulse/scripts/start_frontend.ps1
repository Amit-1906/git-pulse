# GitPulse — Start Frontend (Streamlit)
# Run from ANY directory; the script resolves paths automatically.

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot  = Split-Path -Parent $ScriptDir
$FrontendDir  = Join-Path $ProjectRoot "frontend"
$FrontendApp  = Join-Path $FrontendDir "app.py"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host "  GitPulse  |  Streamlit Frontend" -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host ""

# ── Python check ─────────────────────────────────────────────────────────────
try {
    $PyVersion = python --version 2>&1
    Write-Host "[OK]  Python: $PyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERR] Python not found. Install Python 3.10+ and try again." -ForegroundColor Red
    exit 1
}

# ── Streamlit check ───────────────────────────────────────────────────────────
$StVersion = python -c "import streamlit; print(streamlit.__version__)" 2>$null
if (-not $StVersion) {
    Write-Host "[INFO] Installing Streamlit ..." -ForegroundColor Yellow
    pip install streamlit plotly requests
}

# ── Entry-point check ────────────────────────────────────────────────────────
if (-not (Test-Path $FrontendApp)) {
    Write-Host "[ERR] Entry point not found: $FrontendApp" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[INFO] Starting Streamlit on http://localhost:8501" -ForegroundColor Magenta
Write-Host "[INFO] The app will open automatically in your browser." -ForegroundColor Magenta
Write-Host "[INFO] Backend API expected at http://localhost:8000" -ForegroundColor Gray
Write-Host "[INFO] Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

Set-Location $FrontendDir
python -m streamlit run app.py --server.port 8501 --server.address localhost --browser.gatherUsageStats false


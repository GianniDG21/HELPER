# HELPER — avvio ambiente: Docker Compose (DB) + Uvicorn (API)
# Uso: dalla root del repo  .\scripts\start.ps1
# Opzionale: $env:HELPER_PORT = "8001" per cambiare porta

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "== HELPER: directory progetto = $ProjectRoot" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker non trovato nel PATH. Avvia Docker Desktop e riprova."
    exit 1
}

Write-Host "== Docker Compose: avvio servizi (Postgres reparti + pratiche)..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$port = if ($env:HELPER_PORT) { $env:HELPER_PORT } else { "8000" }
Write-Host "== API: uvicorn su http://127.0.0.1:$port (Ctrl+C per fermare; i container Docker restano attivi)" -ForegroundColor Cyan
Write-Host "   UI: http://127.0.0.1:$port/ui/  |  Vista pulita: http://127.0.0.1:$port/ui/clean.html" -ForegroundColor DarkGray

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Warning "Venv non trovato (.venv). Esegui: python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
}

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $port

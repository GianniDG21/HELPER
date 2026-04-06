#!/usr/bin/env bash
# HELPER — avvio ambiente: Docker Compose (DB) + Uvicorn (API)
# Uso: dalla root del repo  ./scripts/start.sh
# Opzionale: HELPER_PORT=8001 ./scripts/start.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== HELPER: directory progetto = $ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Errore: docker non trovato nel PATH." >&2
  exit 1
fi

echo "== Docker Compose: avvio servizi (Postgres reparti + pratiche)..."
docker compose up -d

PORT="${HELPER_PORT:-8000}"
echo "== API: uvicorn su http://127.0.0.1:${PORT} (Ctrl+C per fermare; i container Docker restano attivi)"
echo "   UI: http://127.0.0.1:${PORT}/ui/  |  Vista pulita: http://127.0.0.1:${PORT}/ui/clean.html"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
else
  echo "Attenzione: venv non trovato (.venv). Esegui: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
fi

exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"

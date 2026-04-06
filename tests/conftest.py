"""
Ordine importante: variabili d'ambiente prima di qualsiasi import di `app.*`
che carichi Settings (altrimenti si leggerebbe il .env reale dello sviluppatore).
"""
from __future__ import annotations

import os

_USE_REAL_DB = os.environ.get("HELPER_TEST_USE_REAL_DB", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

if not _USE_REAL_DB:
    # Porta inesistente: init_pools fallisce → app in modalità degraded (nessun Docker richiesto)
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["VENDITA_DATABASE_URL"] = (
        "postgresql://team:team@127.0.0.1:59999/__helper_test__"
    )
    os.environ["ACQUISTO_DATABASE_URL"] = (
        "postgresql://team:team@127.0.0.1:59999/__helper_test__"
    )
    os.environ["MANUTENZIONE_DATABASE_URL"] = (
        "postgresql://team:team@127.0.0.1:59999/__helper_test__"
    )
    os.environ["PRATICHE_DATABASE_URL"] = (
        "postgresql://team:team@127.0.0.1:59999/__helper_test__"
    )

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Client ASGI: con DB fittizio l'app resta usable con /health in degraded."""
    from app.main import app

    # httpx<0.28 non accetta lifespan=; il default invoca il ciclo di vita Starlette
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac

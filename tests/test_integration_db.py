"""
Test opzionali contro Postgres reale.
Esempio: `$env:HELPER_TEST_USE_REAL_DB='1'; docker compose up -d; python -m pytest -m integration`
"""
from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_health_database_available_with_real_db(client):
    if not os.environ.get("HELPER_TEST_USE_REAL_DB", "").strip():
        pytest.skip("Imposta HELPER_TEST_USE_REAL_DB=1 e avvia i container Postgres")
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["database"] is True
    assert data["status"] == "ok"

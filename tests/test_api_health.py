import os

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_json(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "database" in data


async def test_health_degraded_without_database(client):
    if os.environ.get("HELPER_TEST_USE_REAL_DB", "").lower() in ("1", "true", "yes"):
        pytest.skip("Modalità DB reale: stato non necessariamente degraded")
    data = (await client.get("/health")).json()
    assert data["status"] == "degraded"
    assert data["database"] is False


async def test_openapi_when_database_offline(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    assert "openapi" in r.json()


async def test_intake_chat_503_when_database_unavailable(client):
    if os.environ.get("HELPER_TEST_USE_REAL_DB", "").lower() in ("1", "true", "yes"):
        pytest.skip("Serve DB per intake")
    r = await client.post(
        "/intake/chat",
        json={
            "message": "test",
            "contact_first_name": "T",
            "contact_last_name": "T",
            "contact_email": "t@t.it",
        },
    )
    assert r.status_code == 503
    assert "detail" in r.json()

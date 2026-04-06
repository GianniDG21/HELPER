from __future__ import annotations

from fastapi import APIRouter

from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.services.pratiche_enrichment import pratiche_rows_with_operator_names

router = APIRouter(tags=["pratiche"])


@router.get("/pratiche/pending")
async def list_all_pratiche_pending():
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        rows = await pract_repo.list_all_pending(conn)
    return {"tickets": rows, "total": len(rows)}


@router.get("/pratiche")
async def list_all_pratiche_registry():
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        raw_rows = await pract_repo.list_all(conn)
    out = await pratiche_rows_with_operator_names(raw_rows)
    return {"pratiche": out, "total": len(out)}

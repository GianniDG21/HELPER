"""Smoke test: verifica che ogni team legga solo il proprio DB."""
from __future__ import annotations

import asyncio
import os
import sys

# Permette esecuzione senza PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.context import reset_team_id, set_team_id
from app.db.registry import close_pools, init_pools
from app.db.repositories import tickets as repo


async def main() -> None:
    settings = get_settings()
    await init_pools(settings)
    try:
        for team_id in ("vendita", "acquisto", "manutenzione"):
            token = set_team_id(team_id)
            try:
                from app.db import registry

                pool = registry.get_pool(team_id)
                async with pool.acquire() as conn:
                    rows = await repo.list_tickets(conn, None)
                    titles = [r["title"] for r in rows]
                    print(f"{team_id}: {titles}")
            finally:
                reset_team_id(token)
    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(main())

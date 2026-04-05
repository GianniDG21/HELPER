from __future__ import annotations

import asyncpg

from app.config import Settings

_pools: dict[str, asyncpg.Pool] = {}
_pratiche_pool: asyncpg.Pool | None = None


async def init_pools(settings: Settings) -> None:
    global _pratiche_pool
    for team_id, url in settings.db_urls_by_team.items():
        _pools[team_id] = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )
    _pratiche_pool = await asyncpg.create_pool(
        settings.pratiche_database_url,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )


async def close_pools() -> None:
    global _pratiche_pool
    for pool in _pools.values():
        await pool.close()
    _pools.clear()
    if _pratiche_pool is not None:
        await _pratiche_pool.close()
        _pratiche_pool = None


def get_pool(team_id: str) -> asyncpg.Pool:
    try:
        return _pools[team_id]
    except KeyError as e:
        raise KeyError(f"Pool sconosciuto per team_id={team_id}") from e


def get_pratiche_pool() -> asyncpg.Pool:
    if _pratiche_pool is None:
        raise RuntimeError("Pool pratiche non inizializzato")
    return _pratiche_pool

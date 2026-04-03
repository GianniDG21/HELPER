from __future__ import annotations

import asyncpg

from app.config import Settings

_pools: dict[str, asyncpg.Pool] = {}


async def init_pools(settings: Settings) -> None:
    for team_id, url in settings.db_urls_by_team.items():
        _pools[team_id] = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )


async def close_pools() -> None:
    for pool in _pools.values():
        await pool.close()
    _pools.clear()


def get_pool(team_id: str) -> asyncpg.Pool:
    try:
        return _pools[team_id]
    except KeyError as e:
        raise KeyError(f"Pool sconosciuto per team_id={team_id}") from e

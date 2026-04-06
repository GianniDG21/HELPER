"""Arricchimento elenchi pratiche registry con nomi operatori (query sui DB reparto)."""
from __future__ import annotations

import uuid
from collections import defaultdict

from app.config import TEAM_IDS
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import pratiche as pract_repo


async def pratiche_rows_with_operator_names(raw_rows: list[dict]) -> list[dict]:
    teams: frozenset[str] = frozenset(TEAM_IDS)
    uids_by_dept: dict[str, list[uuid.UUID]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for r in raw_rows:
        aid = r.get("assigned_to")
        dept = str(r.get("department") or "")
        if aid is None or dept not in teams:
            continue
        sid = str(aid)
        key = (dept, sid)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        try:
            uids_by_dept[dept].append(uuid.UUID(sid))
        except ValueError:
            continue
    name_by_key: dict[tuple[str, str], str] = {}
    for dept, uids in uids_by_dept.items():
        if not uids:
            continue
        token = set_team_id(dept)  # type: ignore[arg-type]
        try:
            pool = registry.get_pool(dept)
            async with pool.acquire() as conn:
                erows = await conn.fetch(
                    "SELECT id::text AS id, name FROM employees WHERE id = ANY($1::uuid[])",
                    uids,
                )
                for row in erows:
                    name_by_key[(dept, str(row["id"]))] = str(row["name"])
        finally:
            reset_team_id(token)
    out: list[dict] = []
    for r in raw_rows:
        shape = pract_repo.row_as_ticket_api_shape(dict(r))
        aid = shape.get("assigned_to")
        dept = str(shape.get("department") or "")
        shape["assigned_to_name"] = (
            name_by_key[(dept, aid)] if aid and (dept, aid) in name_by_key else None
        )
        out.append(shape)
    return out

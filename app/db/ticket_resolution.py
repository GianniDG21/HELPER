"""Risoluzione id pratica globale (DB pratiche) vs id ticket nel DB di settore (legacy)."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import TeamId
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.db.repositories import tickets as repo

_TEAMS: tuple[TeamId, ...] = ("vendita", "acquisto", "manutenzione")


@dataclass(frozen=True)
class ResolvedTicket:
    """pratica_id: id pubblico (tabella pratiche); sector_ticket_id: id nel DB reparto."""

    pratica_id: str
    department: str
    sector_ticket_id: str


async def resolve_for_department(
    ticket_id: str, department: TeamId
) -> ResolvedTicket | None:
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        row = await pract_repo.get_pratica(conn, ticket_id)
    if row:
        if row["department"] != department:
            return None
        return ResolvedTicket(
            pratica_id=str(row["id"]),
            department=row["department"],
            sector_ticket_id=str(row["sector_ticket_id"]),
        )
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            t = await repo.get_ticket(conn, ticket_id)
        if not t:
            return None
        return ResolvedTicket(
            pratica_id=ticket_id,
            department=department,
            sector_ticket_id=ticket_id,
        )
    finally:
        reset_team_id(token)


async def locate_with_metadata(ticket_id: str) -> dict | None:
    """Per GET /tickets/{id}/department: pratiche prima, altrimenti scansione settori."""
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        row = await pract_repo.get_pratica(conn, ticket_id)
    if row:
        return {
            "ticket_id": str(row["id"]),
            "department": row["department"],
            "status": row["status"],
            "title": row.get("title"),
            "requested_by_name": row.get("requested_by_name"),
            "requested_by_email": row.get("requested_by_email"),
            "opened_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
    for dept in _TEAMS:
        token = set_team_id(dept)
        try:
            pool = registry.get_pool(dept)
            async with pool.acquire() as conn:
                trow = await repo.get_ticket(conn, ticket_id)
            if trow:
                return {
                    "ticket_id": ticket_id,
                    "department": dept,
                    "status": trow.get("status"),
                    "title": trow.get("title"),
                    "requested_by_name": trow.get("customer_name"),
                    "requested_by_email": trow.get("customer_email"),
                    "opened_at": None,
                }
        finally:
            reset_team_id(token)
    return None


async def resolve_department_and_sector_id(
    ticket_id: str,
) -> tuple[str, str] | None:
    """Per email simulate: (department, sector_ticket_id)."""
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        row = await pract_repo.get_pratica(conn, ticket_id)
    if row:
        return row["department"], str(row["sector_ticket_id"])
    for dept in _TEAMS:
        token = set_team_id(dept)
        try:
            pool = registry.get_pool(dept)
            async with pool.acquire() as conn:
                trow = await repo.get_ticket(conn, ticket_id)
            if trow:
                return dept, ticket_id
        finally:
            reset_team_id(token)
    return None

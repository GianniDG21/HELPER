from __future__ import annotations

import uuid
from typing import Any

import asyncpg

from app.db.repositories.tickets import parse_ticket_pk

_VALID_STATUS = frozenset(
    {"pending_acceptance", "open", "in_progress", "resolved"}
)


async def insert_pratica(
    conn: asyncpg.Connection,
    department: str,
    sector_ticket_id: int,
    requested_by_name: str,
    requested_by_email: str,
    title: str,
    full_summary: str,
    company_id: str | None = None,
    vehicle: str | None = None,
    part_code: str | None = None,
    requested_by_phone: str | None = None,
) -> str:
    comp = uuid.UUID(company_id) if company_id else None
    row = await conn.fetchrow(
        """
        INSERT INTO pratiche (
            department, sector_ticket_id,
            requested_by_name, requested_by_email, requested_by_phone,
            title, full_summary, company_id, vehicle, part_code, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending_acceptance')
        RETURNING id::text AS id
        """,
        department,
        sector_ticket_id,
        requested_by_name,
        requested_by_email,
        requested_by_phone,
        title,
        full_summary or "",
        comp,
        vehicle,
        part_code,
    )
    assert row is not None
    return str(row["id"])


async def get_pratica(conn: asyncpg.Connection, pratica_id: str) -> dict[str, Any] | None:
    pid = parse_ticket_pk(pratica_id)
    row = await conn.fetchrow(
        """
        SELECT id::text AS id, department, sector_ticket_id::text AS sector_ticket_id,
               requested_by_name, requested_by_email, requested_by_phone,
               company_id::text AS company_id,
               title, full_summary, vehicle, part_code, status,
               assigned_to::text AS assigned_to,
               created_at, accepted_at
        FROM pratiche WHERE id = $1
        """,
        pid,
    )
    return dict(row) if row else None


async def list_all_for_department(
    conn: asyncpg.Connection, department: str
) -> list[dict[str, Any]]:
    """Tutte le pratiche del reparto (ogni stato), per tab operatore."""
    rows = await conn.fetch(
        """
        SELECT id, department, sector_ticket_id, requested_by_name, requested_by_email,
               requested_by_phone, company_id, title, full_summary, vehicle, part_code,
               status, assigned_to, created_at, accepted_at
        FROM pratiche
        WHERE department = $1
        ORDER BY created_at DESC
        """,
        department,
    )
    return [dict(r) for r in rows]


async def list_pending_for_department(
    conn: asyncpg.Connection, department: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, department, sector_ticket_id, requested_by_name, requested_by_email,
               requested_by_phone, company_id, title, full_summary, vehicle, part_code,
               status, assigned_to, created_at, accepted_at
        FROM pratiche
        WHERE department = $1 AND status = 'pending_acceptance'
        ORDER BY created_at ASC
        """,
        department,
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(row_as_ticket_api_shape(dict(r)))
    return out


async def list_all_pending(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Tutte le pratiche in attesa (tutti i reparti), registry centrale."""
    rows = await conn.fetch(
        """
        SELECT id, department, sector_ticket_id, requested_by_name, requested_by_email,
               requested_by_phone, company_id, title, full_summary, vehicle, part_code,
               status, assigned_to, created_at, accepted_at
        FROM pratiche
        WHERE status = 'pending_acceptance'
        ORDER BY created_at ASC
        """
    )
    return [row_as_ticket_api_shape(dict(r)) for r in rows]


def row_as_ticket_api_shape(r: dict[str, Any]) -> dict[str, Any]:
    """Forma simile a list_tickets per la UI/API esistente."""
    cid = r.get("company_id")
    aid = r.get("assigned_to")
    dept = r.get("department")
    return {
        "id": str(r["id"]),
        "department": str(dept) if dept else None,
        "title": r["title"],
        "status": r["status"],
        "description": r.get("full_summary") or "",
        "original_request": r.get("full_summary") or "",
        "source_email": r.get("requested_by_email") or "",
        "vehicle": r.get("vehicle"),
        "part_code": r.get("part_code"),
        "company_id": str(cid) if cid else None,
        "assigned_to": str(aid) if aid else None,
        "company_trade_name": None,
        "customer_id": None,
        "customer_name": r.get("requested_by_name") or "",
        "customer_email": r.get("requested_by_email") or "",
        "customer_phone": r.get("requested_by_phone"),
        "opened_at": r["created_at"].isoformat() if r.get("created_at") else None,
        "accepted_at": r["accepted_at"].isoformat() if r.get("accepted_at") else None,
        "sector_ticket_id": str(r["sector_ticket_id"]),
    }


async def mark_accepted(
    conn: asyncpg.Connection, pratica_id: str, employee_id: str
) -> bool:
    pid = parse_ticket_pk(pratica_id)
    eid = uuid.UUID(employee_id)
    res = await conn.execute(
        """
        UPDATE pratiche
        SET status = 'in_progress', assigned_to = $1, accepted_at = NOW()
        WHERE id = $2 AND status = 'pending_acceptance'
        """,
        eid,
        pid,
    )
    return res.split()[-1] != "0"


async def update_status(
    conn: asyncpg.Connection, pratica_id: str, status: str
) -> bool:
    if status not in _VALID_STATUS:
        raise ValueError(f"status non valido: {status}")
    pid = parse_ticket_pk(pratica_id)
    res = await conn.execute(
        "UPDATE pratiche SET status = $1 WHERE id = $2",
        status,
        pid,
    )
    return res.split()[-1] != "0"


async def update_status_by_sector(
    conn: asyncpg.Connection,
    department: str,
    sector_ticket_id: str,
    status: str,
) -> bool:
    """Allinea lo stato alla copia nel DB reparto (tool assistenza)."""
    if status not in _VALID_STATUS:
        raise ValueError(f"status non valido: {status}")
    sid = parse_ticket_pk(sector_ticket_id)
    res = await conn.execute(
        """
        UPDATE pratiche SET status = $1
        WHERE department = $2 AND sector_ticket_id = $3
        """,
        status,
        department,
        sid,
    )
    return res.split()[-1] != "0"

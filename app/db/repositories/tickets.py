from __future__ import annotations

import uuid
from typing import Any

import asyncpg

_VALID_STATUS = frozenset(
    {"pending_acceptance", "open", "in_progress", "resolved"}
)


def parse_ticket_pk(ticket_id: str) -> int:
    """ID ticket POC: intero positivo (BIGSERIAL)."""
    t = (ticket_id or "").strip()
    if not t.isdigit():
        raise ValueError("ID pratica non valido: atteso un numero (es. 12).")
    n = int(t)
    if n < 1:
        raise ValueError("ID pratica non valido.")
    return n


async def upsert_customer(
    conn: asyncpg.Connection,
    name: str,
    email: str,
    phone: str | None = None,
) -> str:
    row = await conn.fetchrow(
        "SELECT id::text FROM customers WHERE lower(email) = lower($1)",
        email,
    )
    if row:
        return row["id"]
    ins = await conn.fetchrow(
        "INSERT INTO customers (name, email, phone) VALUES ($1, $2, $3) RETURNING id::text",
        name,
        email,
        phone,
    )
    assert ins is not None
    return ins["id"]


async def list_tickets(conn: asyncpg.Connection, status: str | None = None) -> list[dict[str, Any]]:
    base = (
        "SELECT t.id::text AS id, t.title, t.status, t.description, "
        "t.original_request, t.source_email, "
        "t.vehicle, t.part_code, "
        "t.company_id::text AS company_id, "
        "t.assigned_to::text AS assigned_to, "
        "co.trade_name AS company_trade_name, "
        "e.name AS assigned_to_name, "
        "c.id::text AS customer_id, c.name AS customer_name, c.email AS customer_email, c.phone AS customer_phone "
        "FROM tickets t JOIN customers c ON c.id = t.customer_id "
        "LEFT JOIN companies co ON co.id = t.company_id "
        "LEFT JOIN employees e ON e.id = t.assigned_to "
    )
    if status is None:
        rows = await conn.fetch(base + "ORDER BY t.created_at")
    else:
        if status not in _VALID_STATUS:
            raise ValueError(f"status non valido: {status}")
        rows = await conn.fetch(
            base + "WHERE t.status = $1 ORDER BY t.created_at",
            status,
        )
    return [dict(r) for r in rows]


async def list_pending_acceptance(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    return await list_tickets(conn, "pending_acceptance")


async def get_ticket(conn: asyncpg.Connection, ticket_id: str) -> dict[str, Any] | None:
    tid = parse_ticket_pk(ticket_id)
    row = await conn.fetchrow(
        "SELECT t.id::text AS id, t.title, t.status, t.description, t.original_request, t.source_email, "
        "t.vehicle, t.part_code, "
        "t.company_id::text AS company_id, t.assigned_to::text AS assigned_to, "
        "co.trade_name AS company_trade_name, co.legal_name AS company_legal_name, "
        "e.name AS assigned_to_name, e.email AS assigned_to_email, "
        "c.id::text AS customer_id, c.name AS customer_name, c.email AS customer_email, c.phone AS customer_phone "
        "FROM tickets t JOIN customers c ON c.id = t.customer_id "
        "LEFT JOIN companies co ON co.id = t.company_id "
        "LEFT JOIN employees e ON e.id = t.assigned_to "
        "WHERE t.id = $1",
        tid,
    )
    return dict(row) if row else None


async def list_customers(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        "SELECT id::text AS id, name, email, phone FROM customers ORDER BY name"
    )
    return [dict(r) for r in rows]


async def list_employees(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        "SELECT id::text AS id, name, email, active FROM employees WHERE active = true ORDER BY name"
    )
    return [dict(r) for r in rows]


async def create_ticket(
    conn: asyncpg.Connection,
    customer_id: str,
    title: str,
    description: str | None,
    vehicle: str | None = None,
    part_code: str | None = None,
    status: str = "open",
    company_id: str | None = None,
    original_request: str | None = None,
    source_email: str | None = None,
) -> str:
    cid = uuid.UUID(customer_id)
    comp = uuid.UUID(company_id) if company_id else None
    row = await conn.fetchrow(
        "INSERT INTO tickets (customer_id, company_id, title, description, status, vehicle, part_code, "
        "original_request, source_email) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id::text AS id",
        cid,
        comp,
        title,
        description or "",
        status,
        vehicle,
        part_code,
        original_request,
        source_email,
    )
    assert row is not None
    return str(row["id"])


async def create_intake_routed_ticket(
    conn: asyncpg.Connection,
    customer_name: str,
    source_email: str,
    title: str,
    full_summary: str,
    company_id: str | None,
    vehicle: str | None = None,
    part_code: str | None = None,
    sender_phone: str | None = None,
) -> str:
    cust = await upsert_customer(conn, customer_name, source_email, sender_phone)
    return await create_ticket(
        conn,
        cust,
        title,
        full_summary,
        vehicle=vehicle,
        part_code=part_code,
        status="pending_acceptance",
        company_id=company_id,
        original_request=full_summary,
        source_email=source_email,
    )


async def accept_ticket(
    conn: asyncpg.Connection,
    ticket_id: str,
    employee_id: str,
) -> bool:
    tid = parse_ticket_pk(ticket_id)
    eid = uuid.UUID(employee_id)
    emp = await conn.fetchrow("SELECT 1 FROM employees WHERE id = $1 AND active = true", eid)
    if not emp:
        return False
    res = await conn.execute(
        "UPDATE tickets SET assigned_to = $1, status = 'in_progress' "
        "WHERE id = $2 AND status = 'pending_acceptance'",
        eid,
        tid,
    )
    return res.split()[-1] != "0"


async def insert_simulated_email(
    conn: asyncpg.Connection,
    ticket_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    tid = parse_ticket_pk(ticket_id)
    row = await conn.fetchrow(
        "INSERT INTO simulated_emails (ticket_id, to_email, subject, body) "
        "VALUES ($1, $2, $3, $4) RETURNING id::text",
        tid,
        to_email.strip(),
        subject.strip(),
        body.strip(),
    )
    assert row is not None
    return row["id"]


async def list_simulated_emails_for_ticket(
    conn: asyncpg.Connection, ticket_id: str
) -> list[dict[str, Any]]:
    tid = parse_ticket_pk(ticket_id)
    rows = await conn.fetch(
        "SELECT id::text AS id, ticket_id::text AS ticket_id, to_email, subject, body, "
        "created_at::text AS created_at FROM simulated_emails WHERE ticket_id = $1 "
        "ORDER BY created_at ASC",
        tid,
    )
    return [dict(r) for r in rows]


async def update_ticket_status(conn: asyncpg.Connection, ticket_id: str, status: str) -> bool:
    if status not in _VALID_STATUS:
        raise ValueError(f"status non valido: {status}")
    tid = parse_ticket_pk(ticket_id)
    result = await conn.execute(
        "UPDATE tickets SET status = $1 WHERE id = $2",
        status,
        tid,
    )
    return result.split()[-1] != "0"

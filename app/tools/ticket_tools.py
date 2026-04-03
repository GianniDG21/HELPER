"""Tool LangChain per ticket officina; il settore e risolto dal contesto richiesta (mai dall LLM)."""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from app.context import get_team_id
from app.db import registry
from app.db.repositories import tickets as repo

log = logging.getLogger(__name__)


async def _run_db(coro_factory):
    team_id = get_team_id()
    pool = registry.get_pool(team_id)
    try:
        async with pool.acquire() as conn:
            return await coro_factory(conn)
    except Exception as e:  # noqa: BLE001
        log.exception("Errore tool DB settore=%s", team_id)
        return f"Errore database: {e!s}. Riprovare o riformulare la richiesta."


@tool
async def list_tickets(status: str | None = None) -> str:
    """Elenca i ticket del reparto corrente. Args: status opzionale pending_acceptance | open | in_progress | resolved; se omesso, tutti."""

    async def work(conn):
        rows = await repo.list_tickets(conn, status)
        return json.dumps(rows, ensure_ascii=False)

    return await _run_db(work)


@tool
async def get_ticket(ticket_id: str) -> str:
    """Dettaglio completo di un ticket per numero pratica (id intero). Args: ticket_id."""

    async def work(conn):
        row = await repo.get_ticket(conn, ticket_id)
        if not row:
            return f"Nessun ticket con id={ticket_id}"
        return json.dumps(row, ensure_ascii=False)

    return await _run_db(work)


@tool
async def list_customers() -> str:
    """Elenca clienti/fornitori del settore (id, nome, email, telefono). Usare prima di aprire un nuovo ticket."""

    async def work(conn):
        rows = await repo.list_customers(conn)
        return json.dumps(rows, ensure_ascii=False)

    return await _run_db(work)


@tool
async def list_employees() -> str:
    """Elenca i dipendenti del reparto (helpdesk) corrente per accettazione o riferimenti."""

    async def work(conn):
        rows = await repo.list_employees(conn)
        return json.dumps(rows, ensure_ascii=False)

    return await _run_db(work)


@tool
async def create_ticket(
    customer_id: str,
    title: str,
    description: str = "",
    vehicle: str | None = None,
    part_code: str | None = None,
) -> str:
    """Apre un ticket in stato open (nuova pratica). Args: customer_id UUID; title; description; vehicle (targa o veicolo, opzionale); part_code (codice ricambio, opzionale)."""

    async def work(conn):
        try:
            new_id = await repo.create_ticket(
                conn, customer_id, title, description, vehicle, part_code
            )
        except Exception as e:  # noqa: BLE001
            return f"Impossibile creare il ticket: {e!s}"
        return json.dumps({"created_ticket_id": new_id}, ensure_ascii=False)

    return await _run_db(work)


@tool
async def send_simulated_email_to_requester(
    ticket_id: str, subject: str, body: str
) -> str:
    """SIMULAZIONE POC: registra un messaggio email verso il richiedente del ticket.
    Il destinatario è l'email del ticket (source_email o email cliente). Il richiedente la vede nel tab Richiesta.
    Usa SOLO dopo presa in carico (ticket in_progress). Args: ticket_id (numero pratica); subject; body."""

    async def work(conn):
        row = await repo.get_ticket(conn, ticket_id)
        if not row:
            return "Ticket non trovato."
        if row.get("status") != "in_progress":
            return (
                "Invio non eseguito: il ticket deve essere in lavorazione (in_progress) "
                "dopo la presa in carico."
            )
        to = (row.get("source_email") or "").strip() or (
            row.get("customer_email") or ""
        ).strip()
        if not to:
            return "Nessun indirizzo email destinatario sul ticket."
        mid = await repo.insert_simulated_email(conn, ticket_id, to, subject, body)
        return json.dumps(
            {
                "ok": True,
                "simulated_email_id": mid,
                "to": to,
                "message": "Email simulata registrata; il richiedente può vederla nel tab Richiesta.",
            },
            ensure_ascii=False,
        )

    return await _run_db(work)


@tool
async def update_ticket_status(ticket_id: str, status: str) -> str:
    """Aggiorna lo stato. Args: ticket_id (numero pratica); status: pending_acceptance | open | in_progress | resolved."""

    async def work(conn):
        try:
            ok = await repo.update_ticket_status(conn, ticket_id, status)
        except Exception as e:  # noqa: BLE001
            return f"Errore aggiornamento: {e!s}"
        if not ok:
            return f"Nessun ticket aggiornato per id={ticket_id}"
        return json.dumps({"ticket_id": ticket_id, "status": status}, ensure_ascii=False)

    return await _run_db(work)


def read_ticket_tools() -> list[Any]:
    """Solo lettura: fase Scan the Scene."""
    return [list_tickets, get_ticket, list_customers, list_employees]


def write_ticket_tools() -> list[Any]:
    """Solo scrittura: fase Take Action."""
    return [create_ticket, update_ticket_status, send_simulated_email_to_requester]


def all_ticket_tools() -> list[Any]:
    return read_ticket_tools() + write_ticket_tools()

"""Tool per fase intake: anagrafica, helpdesk, apertura ticket smistato (senza team_id in contesto)."""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.tools import tool

from app.config import TeamId
from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.db.repositories import tickets as repo
from app.intake.companies_registry import list_helpdesks_payload
from app.intake.companies_registry import lookup_company_by_email as match_company

log = logging.getLogger(__name__)


@tool
def lookup_company_by_email(sender_email: str) -> str:
    """Cerca l azienda in anagrafica dal mittente email (dominio). Restituisce suggested_helpdesk se nota."""
    c = match_company(sender_email)
    if not c:
        return json.dumps(
            {"found": False, "hint": "Nessuna anagrafica per questo dominio; lo smistamento sara solo sul contenuto."},
            ensure_ascii=False,
        )
    return json.dumps({"found": True, **c}, ensure_ascii=False)


@tool
def list_helpdesks() -> str:
    """Elenco helpdesk/reparti interni: chiave, nome e competenza. Usare prima dello smistamento."""
    return json.dumps(list_helpdesks_payload(), ensure_ascii=False)


async def execute_route_and_open_ticket(
    helpdesk: TeamId,
    title: str,
    full_summary: str,
    sender_email: str,
    sender_name: str,
    company_id: str | None = None,
    sender_phone: str | None = None,
    vehicle: str | None = None,
    part_code: str | None = None,
) -> dict[str, str]:
    """Apre ticket nel DB reparto + riga registry pratiche. Solleva su errore DB."""
    pool = registry.get_pool(helpdesk)
    async with pool.acquire() as conn:
        sector_tid_str = await repo.create_intake_routed_ticket(
            conn,
            sender_name,
            sender_email,
            title,
            full_summary,
            company_id,
            vehicle=vehicle,
            part_code=part_code,
            sender_phone=sender_phone,
        )
    sector_tid = int(sector_tid_str)
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as pconn:
        pratica_id = await pract_repo.insert_pratica(
            pconn,
            helpdesk,
            sector_tid,
            sender_name,
            sender_email,
            title,
            full_summary,
            company_id=company_id,
            vehicle=vehicle,
            part_code=part_code,
            requested_by_phone=sender_phone,
        )
    return {
        "ticket_id": str(pratica_id),
        "sector_ticket_id": str(sector_tid),
        "helpdesk": str(helpdesk),
        "queue_status": "pending_acceptance",
    }


@tool
async def route_and_open_ticket(
    helpdesk: Literal["vendita", "acquisto", "manutenzione"],
    title: str,
    full_summary: str,
    sender_email: str,
    sender_name: str,
    company_id: str | None = None,
    sender_phone: str | None = None,
    vehicle: str | None = None,
    part_code: str | None = None,
) -> str:
    """Apre il ticket nel DB del reparto scelto, in coda in attesa di accettazione dipendente (pending_acceptance).
    Args: helpdesk obbligatorio; title breve; full_summary testo completo per il team (includi anno, km o quantita
    ricambi se pertinenti); sender_email; sender_name; company_id UUID da anagrafica se noto;
    sender_phone, vehicle (es. modello e anno), part_code opzionali."""
    try:
        out = await execute_route_and_open_ticket(
            helpdesk=helpdesk,
            title=title,
            full_summary=full_summary,
            sender_email=sender_email,
            sender_name=sender_name,
            company_id=company_id,
            sender_phone=sender_phone,
            vehicle=vehicle,
            part_code=part_code,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("route_and_open_ticket verso %s", helpdesk)
        return f"Errore apertura ticket: {e!s}"
    return json.dumps(
        {
            **out,
            "message": "Pratica registrata e inoltrata alla coda del reparto; un dipendente deve accettarla.",
        },
        ensure_ascii=False,
    )


def read_intake_tools() -> list[Any]:
    return [lookup_company_by_email, list_helpdesks]


def write_intake_tools() -> list[Any]:
    return [route_and_open_ticket]

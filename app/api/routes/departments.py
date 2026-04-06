from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam

from app.config import TeamId
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.db.repositories import tickets as repo
from app.schemas.api import (
    AcceptTicketBody,
    MailRichiedenteBody,
    TICKET_ID_STR_PATTERN,
)
from app.services.pratiche_enrichment import pratiche_rows_with_operator_names
from app.uuid_utils import uuid_equal

log = logging.getLogger(__name__)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("/{department}/employees")
async def list_department_employees(department: TeamId):
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            rows = await repo.list_employees(conn)
        return {
            "department": department,
            "employees": [{"id": r["id"], "name": r["name"]} for r in rows],
        }
    finally:
        reset_team_id(token)


@router.get("/{department}/tickets/pending")
async def list_pending(department: TeamId):
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        rows = await pract_repo.list_pending_for_department(conn, department)
    return {"department": department, "tickets": rows}


@router.get("/{department}/pratiche")
async def list_department_pratiche(department: TeamId):
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        raw_rows = await pract_repo.list_all_for_department(conn, department)
    out = await pratiche_rows_with_operator_names(raw_rows)
    return {"department": department, "pratiche": out}


@router.post("/{department}/pratiche/{pratica_id}/mail-richiedente")
async def mail_richiedente(
    department: TeamId,
    body: MailRichiedenteBody,
    pratica_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN)
    ],
):
    try:
        eid = uuid.UUID(body.employee_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="employee_id non è un UUID valido."
        ) from e
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        prow = await pract_repo.get_pratica(conn, pratica_id)
    if not prow:
        raise HTTPException(status_code=404, detail="Pratica non trovata nel registry.")
    if prow["department"] != department:
        raise HTTPException(
            status_code=404,
            detail="Il reparto nell'URL non coincide con quello della pratica.",
        )
    if str(prow.get("status") or "") != "in_progress":
        raise HTTPException(
            status_code=400,
            detail="La pratica deve essere in lavorazione (in_progress) dopo la presa in carico.",
        )
    if not uuid_equal(prow.get("assigned_to"), eid):
        raise HTTPException(
            status_code=403,
            detail="Solo il dipendente assegnato può inviare messaggi al richiedente.",
        )
    sector_id = str(prow["sector_ticket_id"])
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            row = await repo.get_ticket(conn, sector_id)
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Ticket reparto non trovato per questa pratica.",
                )
            to = (row.get("source_email") or "").strip() or (
                (row.get("customer_email") or "") or ""
            ).strip()
            if not to:
                raise HTTPException(
                    status_code=400,
                    detail="Nessun indirizzo email destinatario sul ticket.",
                )
            mid = await repo.insert_simulated_email(
                conn, sector_id, to, body.subject, body.body
            )
        return {
            "ok": True,
            "simulated_email_id": mid,
            "to": to,
            "department": department,
            "pratica_id": pratica_id,
        }
    finally:
        reset_team_id(token)


@router.post("/{department}/tickets/{ticket_id}/accept")
async def accept_ticket_endpoint(
    department: TeamId,
    body: AcceptTicketBody,
    ticket_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN)
    ],
):
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        prow = await pract_repo.get_pratica(conn, ticket_id)
    if not prow:
        raise HTTPException(
            status_code=404,
            detail=(
                "Pratica non trovata nel registry centrale. Usa il ticket_id "
                "restituito dall'intake (DB pratiche)."
            ),
        )
    if prow["department"] != department:
        raise HTTPException(
            status_code=404,
            detail="Il reparto nell URL non coincide con quello della pratica.",
        )
    st = str(prow.get("status") or "")
    if st != "pending_acceptance":
        raise HTTPException(
            status_code=400,
            detail=(
                f"La pratica non è in coda (stato «{st}», atteso "
                "«pending_acceptance»)."
            ),
        )
    try:
        eid = uuid.UUID(body.employee_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="employee_id non è un UUID valido."
        ) from e

    sector_id = str(prow["sector_ticket_id"])
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            emp_ok = await conn.fetchrow(
                "SELECT 1 FROM employees WHERE id = $1 AND active = true",
                eid,
            )
            if not emp_ok:
                raise HTTPException(
                    status_code=400,
                    detail="Operatore non trovato o non attivo in questo reparto.",
                )
            row = await repo.get_ticket(conn, sector_id)
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Copia settore del ticket assente: controllare integrazione DB.",
                )
            if str(row.get("status") or "") != "pending_acceptance":
                raise HTTPException(
                    status_code=400,
                    detail="Il ticket nel DB reparto non è in attesa di accettazione.",
                )
            ok_sector = await repo.accept_ticket(conn, sector_id, body.employee_id)
        if not ok_sector:
            raise HTTPException(
                status_code=500,
                detail="Presa in carico sul DB reparto non riuscita.",
            )
        async with ppool.acquire() as conn:
            okp = await pract_repo.mark_accepted(conn, ticket_id, body.employee_id)
        if not okp:
            log.error(
                "Accettazione settore OK ma aggiornamento pratica %s fallito",
                ticket_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Inconsistenza registry pratiche dopo accettazione; controllare i log.",
            )
        return {
            "ok": True,
            "department": department,
            "ticket_id": ticket_id,
            "employee_id": body.employee_id,
        }
    finally:
        reset_team_id(token)


@router.post("/{department}/pratiche/{pratica_id}/resolve")
async def resolve_pratica_endpoint(
    department: TeamId,
    body: AcceptTicketBody,
    pratica_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN)
    ],
):
    try:
        eid = uuid.UUID(body.employee_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="employee_id non è un UUID valido."
        ) from e
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        prow = await pract_repo.get_pratica(conn, pratica_id)
    if not prow:
        raise HTTPException(status_code=404, detail="Pratica non trovata nel registry.")
    if prow["department"] != department:
        raise HTTPException(
            status_code=404,
            detail="Il reparto nell'URL non coincide con quello della pratica.",
        )
    if str(prow.get("status") or "") != "in_progress":
        raise HTTPException(
            status_code=400,
            detail="Solo pratiche «In lavorazione» possono essere chiuse così.",
        )
    if not uuid_equal(prow.get("assigned_to"), eid):
        raise HTTPException(
            status_code=403,
            detail="Solo il dipendente assegnato può chiudere la pratica.",
        )
    sector_id = str(prow["sector_ticket_id"])
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            ok_sector = await repo.update_ticket_status(conn, sector_id, "resolved")
        if not ok_sector:
            raise HTTPException(
                status_code=404,
                detail="Ticket di reparto non trovato o non aggiornabile.",
            )
        async with ppool.acquire() as conn:
            okp = await pract_repo.update_status(conn, pratica_id, "resolved")
        if not okp:
            log.error(
                "Chiusura settore OK ma registry pratica %s non aggiornato",
                pratica_id,
            )
            raise HTTPException(
                status_code=500,
                detail="Inconsistenza registry dopo chiusura; controllare i log.",
            )
        return {
            "ok": True,
            "department": department,
            "pratica_id": pratica_id,
            "status": "resolved",
        }
    finally:
        reset_team_id(token)

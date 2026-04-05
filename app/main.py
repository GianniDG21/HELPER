from __future__ import annotations

import logging
import re
import uuid
from typing import Annotated
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent.assist_graph import build_assist_graph
from app.agent.intake_graph import build_intake_graph
from app.agent.intake_debug import build_intake_debug, intake_debug_log_line
from app.agent.trace import (
    intake_routing_from_turn,
    intake_routing_from_turn_loose,
    messages_to_trace,
    transcript_turns,
    user_visible_reply,
)
from app.intake.fallback_open import try_intake_fallback_open
from app.config import TeamId, get_settings
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.db.repositories import tickets as repo
from app.db.registry import close_pools, init_pools
from app.db.ticket_resolution import (
    locate_with_metadata,
    resolve_department_and_sector_id,
    resolve_for_department,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_TEAMS: tuple[TeamId, ...] = ("vendita", "acquisto", "manutenzione")

_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_TICKET_ID_RE = r"^\d+$"


def _intake_thread_ckpt(client_thread_id: str) -> str:
    return f"inbox:{client_thread_id}"


def _assist_thread_ckpt(
    department: str,
    ticket_id: str,
    employee_id: str,
    client_thread_id: str,
) -> str:
    return f"assist:{department}:{ticket_id}:{employee_id}:{client_thread_id}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_pools(settings)
    app.state.checkpointer = MemorySaver()
    app.state.intake_graph = build_intake_graph(
        settings, checkpointer=app.state.checkpointer
    )
    app.state.assist_graph = build_assist_graph(
        settings, checkpointer=app.state.checkpointer
    )
    if settings.llm_provider == "ollama":
        log.info(
            "Grafi pronti (Ollama %s @ %s, checkpointer in-memory)",
            settings.ollama_model,
            settings.ollama_base_url,
        )
    else:
        log.info(
            "Grafi pronti (Groq %s, checkpointer in-memory)",
            settings.groq_model,
        )
    yield
    await close_pools()
    log.info("Pool DB chiusi")


app = FastAPI(title="Ticket Agent POC — intake + assist", lifespan=lifespan)


class IntakeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None
    contact_first_name: str | None = Field(default=None, max_length=120)
    contact_last_name: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=320)

    @model_validator(mode="after")
    def _contact_triplet(self) -> IntakeChatRequest:
        fn = (self.contact_first_name or "").strip()
        ln = (self.contact_last_name or "").strip()
        em = (self.contact_email or "").strip()
        any_set = bool(fn or ln or em)
        if any_set:
            if not fn or not ln or not em:
                raise ValueError(
                    "Contatto: compilare insieme nome, cognome e email (o lasciare tutti vuoti)."
                )
            if not _CONTACT_EMAIL_RE.match(em):
                raise ValueError("Contatto: formato email non valido.")
        return self

    def human_message_content(self) -> str:
        fn = (self.contact_first_name or "").strip()
        ln = (self.contact_last_name or "").strip()
        em = (self.contact_email or "").strip()
        parts: list[str] = []
        if fn and ln and em:
            parts.append(
                "[Dati contatto richiedente:\n"
                f"nome={fn}\ncognome={ln}\nemail={em}]\n\n"
            )
        parts.append(self.message.strip())
        return "".join(parts)


class IntakeChatResponse(BaseModel):
    thread_id: str
    reply: str
    trace: list[dict]
    routed_department: str | None = Field(
        default=None,
        description="Reparto effettivo se route_and_open_ticket ha avuto successo nel turno",
    )
    ticket_id: str | None = Field(
        default=None,
        description="ID pratica nel registry centralizzato (DB pratiche) dopo route_and_open_ticket",
    )
    debug: dict | None = Field(
        default=None,
        description="Diagnostica (solo se impostato DEBUG_INTAKE=1 in .env)",
    )

    @field_validator("ticket_id", mode="before")
    @classmethod
    def _ticket_id_as_str(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class AssistChatRequest(BaseModel):
    department: TeamId
    ticket_id: str = Field(min_length=1, max_length=19, pattern=_TICKET_ID_RE)
    employee_id: str = Field(min_length=4, max_length=64)
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None


class AssistChatResponse(BaseModel):
    thread_id: str
    department: str
    ticket_id: str
    employee_id: str
    reply: str
    trace: list[dict]


class ThreadTranscriptResponse(BaseModel):
    thread_id: str
    messages: list[dict]
    mode: str = Field(description="intake | assist")


class AcceptTicketBody(BaseModel):
    employee_id: str = Field(min_length=4, max_length=64)


class MailRichiedenteBody(BaseModel):
    employee_id: str = Field(min_length=4, max_length=64)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=8000)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Apri nel browser: / → reindirizza alla UI statica su /ui/"""
    return RedirectResponse(url="/ui/", status_code=307)


@app.get("/tickets/{ticket_id}/department")
async def locate_ticket_department(
    ticket_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=_TICKET_ID_RE)
    ],
):
    """Individua reparto e metadati: registry pratiche prima, altrimenti ticket nel DB settore."""
    meta = await locate_with_metadata(ticket_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail="Pratica non trovata in nessun reparto.",
        )
    return meta


@app.get("/intake/simulated-mails")
async def intake_simulated_mails(
    ticket_id: str = Query(..., min_length=1, max_length=19, pattern=_TICKET_ID_RE),
):
    """Messaggi email simulati verso il richiedente (per tab Richiesta / stesso ticket)."""
    resolved = await resolve_department_and_sector_id(ticket_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Ticket non trovato in nessun reparto")
    dept, sector_id = resolved
    token = set_team_id(dept)
    try:
        pool = registry.get_pool(dept)
        async with pool.acquire() as conn:
            rows = await repo.list_simulated_emails_for_ticket(conn, sector_id)
        return {
            "department": dept,
            "ticket_id": ticket_id,
            "messages": rows,
        }
    finally:
        reset_team_id(token)


@app.get("/intake/thread", response_model=ThreadTranscriptResponse)
async def get_intake_thread(thread_id: str = Query(..., min_length=4, max_length=128)):
    graph = app.state.intake_graph
    cfg = {"configurable": {"thread_id": _intake_thread_ckpt(thread_id)}}
    snap = await graph.aget_state(cfg)
    raw = list(snap.values.get("messages", [])) if snap.values else []
    return ThreadTranscriptResponse(
        thread_id=thread_id,
        messages=transcript_turns(raw, strip_intake_meta=True),
        mode="intake",
    )


@app.post("/intake/chat", response_model=IntakeChatResponse)
async def intake_chat(body: IntakeChatRequest):
    client_thread_id = body.thread_id or str(uuid.uuid4())
    ckpt = _intake_thread_ckpt(client_thread_id)
    config: dict = {"configurable": {"thread_id": ckpt}, "recursion_limit": 50}
    graph = app.state.intake_graph
    snapshot = await graph.aget_state(config)
    prev_n = len(snapshot.values.get("messages", [])) if snapshot.values else 0

    log.info("intake thread=%s chars=%s", client_thread_id, len(body.message))
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=body.human_message_content())]},
            config=config,
        )
    except Exception as e:  # noqa: BLE001 — vogliamo messaggio utile in UI/log
        log.exception("intake graph fallito thread=%s", client_thread_id)
        raise HTTPException(
            status_code=500,
            detail=f"Elaborazione fallita (LLM o grafo). Dettaglio: {e!s}",
        ) from e
    msgs = result.get("messages", []) if isinstance(result, dict) else []
    if not msgs:
        raise HTTPException(status_code=500, detail="Risposta agente vuota")
    turn_msgs = msgs[prev_n:]
    dept, ticket_uuid = intake_routing_from_turn(turn_msgs)
    if dept is None or ticket_uuid is None:
        dept, ticket_uuid = intake_routing_from_turn_loose(turn_msgs)
    settings = get_settings()
    intake_fallback_applied = False
    if (
        settings.intake_fallback_open
        and (dept is None or ticket_uuid is None)
    ):
        fb_dept, fb_tid = await try_intake_fallback_open(msgs, turn_msgs)
        if fb_dept and fb_tid:
            dept, ticket_uuid = fb_dept, fb_tid
            intake_fallback_applied = True
    n_tools = sum(1 for m in turn_msgs if isinstance(m, ToolMessage))
    log.info(
        "intake_result thread=%s tools_in_turn=%s ticket_id=%s dept=%s fallback=%s",
        client_thread_id,
        n_tools,
        ticket_uuid,
        dept,
        intake_fallback_applied,
    )
    dbg: dict | None = None
    if settings.debug_intake:
        dbg = build_intake_debug(
            turn_msgs,
            dept,
            ticket_uuid,
            prev_n,
            len(msgs),
            intake_fallback_applied=intake_fallback_applied,
        )
        log.info(
            "intake_debug thread=%s %s",
            client_thread_id,
            intake_debug_log_line(dbg),
        )
    if dept is None and ticket_uuid is None:
        for m in reversed(turn_msgs):
            if isinstance(m, ToolMessage) and getattr(m, "name", None) == "route_and_open_ticket":
                log.warning(
                    "intake thread=%s: route_and_open_ticket eseguito ma ticket/reparto "
                    "non estratti dal JSON (controllare formato ToolMessage).",
                    client_thread_id,
                )
                break
    try:
        return IntakeChatResponse(
            thread_id=client_thread_id,
            reply=user_visible_reply(
                turn_msgs,
                strip_intake_meta=True,
                intake_routed_ticket_id=ticket_uuid,
            ),
            trace=messages_to_trace(turn_msgs),
            routed_department=dept,
            ticket_id=ticket_uuid,
            debug=dbg,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("intake serializzazione risposta thread=%s", client_thread_id)
        raise HTTPException(
            status_code=500,
            detail=f"Errore costruzione risposta API: {e!s}",
        ) from e


@app.get("/assist/thread", response_model=ThreadTranscriptResponse)
async def get_assist_thread(
    department: TeamId,
    ticket_id: str = Query(..., min_length=1, max_length=19, pattern=_TICKET_ID_RE),
    employee_id: str = Query(...),
    thread_id: str = Query(..., min_length=4, max_length=128),
):
    graph = app.state.assist_graph
    cfg = {
        "configurable": {
            "thread_id": _assist_thread_ckpt(
                department, ticket_id, employee_id, thread_id
            )
        }
    }
    snap = await graph.aget_state(cfg)
    raw = list(snap.values.get("messages", [])) if snap.values else []
    return ThreadTranscriptResponse(
        thread_id=thread_id,
        messages=transcript_turns(raw, strip_intake_meta=False),
        mode="assist",
    )


@app.post("/assist/chat", response_model=AssistChatResponse)
async def assist_chat(body: AssistChatRequest):
    client_thread_id = body.thread_id or str(uuid.uuid4())
    resolved = await resolve_for_department(body.ticket_id, body.department)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail="Pratica non trovata per questo reparto (id registry o ticket settore).",
        )
    sector_id = resolved.sector_ticket_id
    public_id = resolved.pratica_id
    token = set_team_id(body.department)
    try:
        pool = registry.get_pool(body.department)
        async with pool.acquire() as conn:
            t = await repo.get_ticket(conn, sector_id)
            emprow = await conn.fetchrow(
                "SELECT id::text, name, email FROM employees WHERE id = $1 AND active = true",
                uuid.UUID(body.employee_id),
            )
        if not t:
            raise HTTPException(status_code=404, detail="Ticket non trovato")
        if not emprow:
            raise HTTPException(status_code=404, detail="Dipendente non trovato")
        if str(t.get("assigned_to") or "") != str(body.employee_id):
            raise HTTPException(
                status_code=403,
                detail="Il ticket non e assegnato a questo dipendente",
            )
        if t.get("status") != "in_progress":
            raise HTTPException(
                status_code=400,
                detail="Il ticket deve essere accettato (in_progress)",
            )

        prefix = (
            f"[Contesto assistenza: reparto={body.department} | pratica_id={public_id} | "
            f"ticket_id={sector_id} | dipendente={emprow['name']} | email={emprow['email']}]\n"
        )
        human = HumanMessage(content=prefix + body.message)

        graph = app.state.assist_graph
        cfg: dict = {
            "configurable": {
                "thread_id": _assist_thread_ckpt(
                    body.department,
                    public_id,
                    body.employee_id,
                    client_thread_id,
                )
            },
            "recursion_limit": 50,
        }
        snapshot = await graph.aget_state(cfg)
        prev_n = len(snapshot.values.get("messages", [])) if snapshot.values else 0

        log.info(
            "assist dept=%s pratica=%s sector_ticket=%s emp=%s thread=%s",
            body.department,
            public_id,
            sector_id,
            body.employee_id,
            client_thread_id,
        )
        result = await graph.ainvoke({"messages": [human]}, config=cfg)
        msgs = result.get("messages", [])
        if not msgs:
            raise HTTPException(status_code=500, detail="Risposta agente vuota")
        turn_msgs = msgs[prev_n:]
        return AssistChatResponse(
            thread_id=client_thread_id,
            department=body.department,
            ticket_id=public_id,
            employee_id=body.employee_id,
            reply=user_visible_reply(turn_msgs, strip_intake_meta=False),
            trace=messages_to_trace(turn_msgs),
        )
    finally:
        reset_team_id(token)


@app.get("/departments/{department}/employees")
async def list_department_employees(department: TeamId):
    """Elenco dipendenti attivi del reparto (per menu UI: id + nome)."""
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


@app.get("/pratiche/pending")
async def list_all_pratiche_pending():
    """Tutte le pratiche `pending_acceptance` nel DB centrale (diagnostica + UI coda globale)."""
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        rows = await pract_repo.list_all_pending(conn)
    return {"tickets": rows, "total": len(rows)}


@app.get("/departments/{department}/tickets/pending")
async def list_pending(department: TeamId):
    """Coda da DB centralizzato pratiche (richiedente + apertura), filtrata per reparto."""
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        rows = await pract_repo.list_pending_for_department(conn, department)
    return {"department": department, "tickets": rows}


@app.get("/departments/{department}/pratiche")
async def list_department_pratiche(department: TeamId):
    """Elenco completo pratiche del reparto (tutti gli stati) con nome operatore assegnato."""
    ppool = registry.get_pratiche_pool()
    async with ppool.acquire() as conn:
        raw_rows = await pract_repo.list_all_for_department(conn, department)
    uids: list[uuid.UUID] = []
    seen: set[str] = set()
    for r in raw_rows:
        aid = r.get("assigned_to")
        if aid is None:
            continue
        sid = str(aid)
        if sid in seen:
            continue
        seen.add(sid)
        try:
            uids.append(uuid.UUID(sid))
        except ValueError:
            continue
    name_by_id: dict[str, str] = {}
    token = set_team_id(department)
    try:
        if uids:
            pool = registry.get_pool(department)
            async with pool.acquire() as conn:
                erows = await conn.fetch(
                    "SELECT id::text AS id, name FROM employees WHERE id = ANY($1::uuid[])",
                    uids,
                )
                name_by_id = {str(row["id"]): str(row["name"]) for row in erows}
    finally:
        reset_team_id(token)
    out: list[dict] = []
    for r in raw_rows:
        shape = pract_repo.row_as_ticket_api_shape(dict(r))
        aid = shape.get("assigned_to")
        shape["assigned_to_name"] = name_by_id.get(aid) if aid else None
        out.append(shape)
    return {"department": department, "pratiche": out}


@app.post("/departments/{department}/pratiche/{pratica_id}/mail-richiedente")
async def mail_richiedente(
    department: TeamId,
    body: MailRichiedenteBody,
    pratica_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=_TICKET_ID_RE)
    ],
):
    """Registra email simulata al richiedente (stesso flusso del tool assistenza)."""
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
    if str(prow.get("assigned_to") or "") != str(eid):
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


@app.post("/departments/{department}/tickets/{ticket_id}/accept")
async def accept_ticket_endpoint(
    department: TeamId,
    body: AcceptTicketBody,
    ticket_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=_TICKET_ID_RE)
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


if STATIC_DIR.is_dir():
    app.mount(
        "/ui",
        StaticFiles(directory=str(STATIC_DIR), html=True),
        name="ui",
    )

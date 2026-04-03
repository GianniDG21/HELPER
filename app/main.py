from __future__ import annotations

import logging
import re
import uuid
from typing import Annotated
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field, model_validator

from app.agent.assist_graph import build_assist_graph
from app.agent.intake_graph import build_intake_graph
from app.agent.trace import (
    intake_routing_from_turn,
    messages_to_trace,
    transcript_turns,
    user_visible_reply,
)
from app.config import TeamId, get_settings
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import tickets as repo
from app.db.registry import close_pools, init_pools

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
        description="Numero pratica (BIGSERIAL) creato da route_and_open_ticket nel turno",
    )


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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/intake/simulated-mails")
async def intake_simulated_mails(
    ticket_id: str = Query(..., min_length=1, max_length=19, pattern=_TICKET_ID_RE),
):
    """Messaggi email simulati verso il richiedente (per tab Richiesta / stesso ticket)."""
    for dept in _TEAMS:
        token = set_team_id(dept)
        try:
            pool = registry.get_pool(dept)
            async with pool.acquire() as conn:
                t = await repo.get_ticket(conn, ticket_id)
                if not t:
                    continue
                rows = await repo.list_simulated_emails_for_ticket(conn, ticket_id)
                return {
                    "department": dept,
                    "ticket_id": ticket_id,
                    "messages": rows,
                }
        finally:
            reset_team_id(token)
    raise HTTPException(status_code=404, detail="Ticket non trovato in nessun reparto")


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
    try:
        return IntakeChatResponse(
            thread_id=client_thread_id,
            reply=user_visible_reply(turn_msgs, strip_intake_meta=True),
            trace=messages_to_trace(turn_msgs),
            routed_department=dept,
            ticket_id=ticket_uuid,
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
    token = set_team_id(body.department)
    try:
        pool = registry.get_pool(body.department)
        async with pool.acquire() as conn:
            t = await repo.get_ticket(conn, body.ticket_id)
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
            f"[Contesto assistenza: reparto={body.department} | ticket_id={body.ticket_id} | "
            f"dipendente={emprow['name']} | email={emprow['email']}]\n"
        )
        human = HumanMessage(content=prefix + body.message)

        graph = app.state.assist_graph
        cfg: dict = {
            "configurable": {
                "thread_id": _assist_thread_ckpt(
                    body.department,
                    body.ticket_id,
                    body.employee_id,
                    client_thread_id,
                )
            },
            "recursion_limit": 50,
        }
        snapshot = await graph.aget_state(cfg)
        prev_n = len(snapshot.values.get("messages", [])) if snapshot.values else 0

        log.info(
            "assist dept=%s ticket=%s emp=%s thread=%s",
            body.department,
            body.ticket_id,
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
            ticket_id=body.ticket_id,
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


@app.get("/departments/{department}/tickets/pending")
async def list_pending(department: TeamId):
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            rows = await repo.list_pending_acceptance(conn)
        return {"department": department, "tickets": rows}
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
    token = set_team_id(department)
    try:
        pool = registry.get_pool(department)
        async with pool.acquire() as conn:
            ok = await repo.accept_ticket(conn, ticket_id, body.employee_id)
        if not ok:
            raise HTTPException(
                status_code=400,
                detail="Accettazione non riuscita (ticket non in coda o dipendente non valido)",
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

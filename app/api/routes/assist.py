from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from langchain_core.messages import HumanMessage

from app.agent.trace import messages_to_trace, transcript_turns, user_visible_reply
from app.api.checkpoints import assist_thread_ckpt
from app.config import TeamId
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import tickets as repo
from app.db.ticket_resolution import resolve_for_department
from app.schemas.api import (
    AssistChatRequest,
    AssistChatResponse,
    ThreadTranscriptResponse,
    TICKET_ID_STR_PATTERN,
)
from app.uuid_utils import uuid_equal

log = logging.getLogger(__name__)

router = APIRouter(prefix="/assist", tags=["assist"])


@router.get("/thread", response_model=ThreadTranscriptResponse)
async def get_assist_thread(
    request: Request,
    department: TeamId,
    ticket_id: str = Query(..., min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN),
    employee_id: str = Query(...),
    thread_id: str = Query(..., min_length=4, max_length=128),
):
    graph = request.app.state.assist_graph
    cfg = {
        "configurable": {
            "thread_id": assist_thread_ckpt(
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


@router.post("/chat", response_model=AssistChatResponse)
async def assist_chat(request: Request, body: AssistChatRequest):
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
        if not uuid_equal(t.get("assigned_to"), body.employee_id):
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

        graph = request.app.state.assist_graph
        cfg: dict = {
            "configurable": {
                "thread_id": assist_thread_ckpt(
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

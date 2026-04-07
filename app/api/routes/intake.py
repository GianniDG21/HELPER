from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi import Path as PathParam
from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.intake_debug import build_intake_debug, intake_debug_log_line
from app.agent.trace import (
    intake_routing_from_turn,
    intake_routing_from_turn_loose,
    messages_to_trace,
    transcript_turns,
    user_visible_reply,
)
from app.api.checkpoints import intake_thread_ckpt
from app.config import get_settings
from app.context import reset_team_id, set_team_id
from app.db import registry
from app.db.repositories import tickets as repo
from app.db.ticket_resolution import locate_with_metadata, resolve_department_and_sector_id
from app.intake.fallback_open import try_intake_fallback_open
from app.schemas.api import IntakeChatRequest, IntakeChatResponse, ThreadTranscriptResponse, TICKET_ID_STR_PATTERN

log = logging.getLogger(__name__)

router = APIRouter(prefix="/intake", tags=["intake"])


def _pick_intake_graph(request: Request):
    req_provider = (request.headers.get("x-llm-provider") or "").strip().lower()
    available = list(getattr(request.app.state, "available_llm_providers", []))
    selected = req_provider or getattr(request.app.state, "llm_default_provider", "ollama")
    if selected not in available:
        if req_provider:
            raise HTTPException(
                status_code=400,
                detail=f"Provider LLM non disponibile: {selected}. Disponibili: {', '.join(available)}",
            )
        selected = available[0] if available else "ollama"
    graphs = getattr(request.app.state, "intake_graphs", {})
    graph = graphs.get(selected) or getattr(request.app.state, "intake_graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Grafo intake non disponibile")
    return selected, graph


@router.get("/simulated-mails")
async def intake_simulated_mails(
    ticket_id: str = Query(..., min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN),
):
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


@router.get("/thread", response_model=ThreadTranscriptResponse)
async def get_intake_thread(
    request: Request,
    thread_id: str = Query(..., min_length=4, max_length=128),
):
    _, graph = _pick_intake_graph(request)
    cfg = {"configurable": {"thread_id": intake_thread_ckpt(thread_id)}}
    snap = await graph.aget_state(cfg)
    raw = list(snap.values.get("messages", [])) if snap.values else []
    return ThreadTranscriptResponse(
        thread_id=thread_id,
        messages=transcript_turns(raw, strip_intake_meta=True),
        mode="intake",
    )


@router.post("/chat", response_model=IntakeChatResponse)
async def intake_chat(request: Request, body: IntakeChatRequest):
    client_thread_id = body.thread_id or str(uuid.uuid4())
    ckpt = intake_thread_ckpt(client_thread_id)
    config: dict = {"configurable": {"thread_id": ckpt}, "recursion_limit": 50}
    selected_provider, graph = _pick_intake_graph(request)
    snapshot = await graph.aget_state(config)
    prev_n = len(snapshot.values.get("messages", [])) if snapshot.values else 0

    log.info("intake thread=%s chars=%s", client_thread_id, len(body.message))
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=body.human_message_content())]},
            config=config,
        )
    except Exception as e:  # noqa: BLE001
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
    if settings.intake_fallback_open and (dept is None or ticket_uuid is None):
        fb_dept, fb_tid = await try_intake_fallback_open(msgs, turn_msgs)
        if fb_dept and fb_tid:
            dept, ticket_uuid = fb_dept, fb_tid
            intake_fallback_applied = True
    n_tools = sum(1 for m in turn_msgs if isinstance(m, ToolMessage))
    log.info(
        "intake_result thread=%s provider=%s tools_in_turn=%s ticket_id=%s dept=%s fallback=%s",
        client_thread_id,
        selected_provider,
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
                intake_routed_department=dept,
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


# Fuori da /intake: meta-handoff (path storico API)
tickets_router = APIRouter(tags=["tickets"])


@tickets_router.get("/tickets/{ticket_id}/department")
async def locate_ticket_department(
    ticket_id: Annotated[
        str, PathParam(min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN)
    ],
):
    meta = await locate_with_metadata(ticket_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail="Pratica non trovata in nessun reparto.",
        )
    return meta

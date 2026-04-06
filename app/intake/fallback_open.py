"""Apertura pratica lato server se il modello non invoca route_and_open_ticket ma il gate è plausibilmente OK."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

from app.agent.trace import (
    _content_str,
    intake_contact_from_human_raw,
    strip_intake_contact_block,
)
from app.intake.companies_registry import lookup_company_by_email
from app.intake.request_hints import operational_gate_heuristic
from app.tools.intake_tools import execute_route_and_open_ticket

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

TeamId = Literal["vendita", "acquisto", "manutenzione"]


def _fallback_skip(reason: str) -> tuple[str | None, str | None]:
    """Early exit con traccia diagnostica (abilitare livello DEBUG su app.intake.fallback_open)."""
    log.debug("intake_fallback_open skipped: %s", reason)
    return None, None


def route_tool_message_seen(turn_msgs: list[BaseMessage]) -> bool:
    """True se compare un ToolMessage per route_and_open_ticket (anche in errore)."""
    return any(
        isinstance(m, ToolMessage)
        and (getattr(m, "name", None) or "").strip() == "route_and_open_ticket"
        for m in turn_msgs
    )


def _human_thread_text(msgs: list[BaseMessage]) -> str:
    chunks: list[str] = []
    for m in msgs:
        if isinstance(m, HumanMessage):
            chunks.append(_content_str(m.content))
    return "\n\n".join(chunks)


def _infer_helpdesk(sender_email: str, summary: str) -> TeamId:
    rec = lookup_company_by_email(sender_email)
    if rec and rec.get("suggested_helpdesk"):
        v = str(rec["suggested_helpdesk"]).strip().lower()
        if v in ("vendita", "acquisto", "manutenzione"):
            return v  # type: ignore[return-value]
    low = (summary or "").lower()
    if any(
        x in low
        for x in (
            "disbrigo",
            "fornitore",
            "fattur",
            "iva",
            "ordine fornitore",
            "acquist",
            "resi verso",
            "pallet",
        )
    ):
        return "acquisto"
    if any(
        x in low
        for x in (
            "targa",
            "tagliando",
            "officina",
            "veicol",
            "motore",
            "flotta",
            "manutenz",
            "intervento meccanic",
        )
    ):
        return "manutenzione"
    return "vendita"


def _last_human_raw(msgs: list[BaseMessage]) -> str | None:
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            return _content_str(m.content)
    return None


def _company_id_for_email(sender_email: str) -> str | None:
    rec = lookup_company_by_email(sender_email)
    if not rec:
        return None
    cid = rec.get("id")
    return str(cid) if cid else None


async def try_intake_fallback_open(
    full_msgs: list[BaseMessage],
    turn_msgs: list[BaseMessage],
) -> tuple[str | None, str | None]:
    """
    Apre ticket+pratica come il tool, senza LLM.
    Solo se nel turno non è mai comparso ToolMessage route_and_open_ticket.
    """
    if route_tool_message_seen(turn_msgs):
        return _fallback_skip("route_tool_message_seen_in_turn")

    raw = _last_human_raw(full_msgs)
    if not raw:
        return _fallback_skip("no_human_message")

    nome, cognome, em = intake_contact_from_human_raw(raw)
    if not em or not nome or not cognome:
        return _fallback_skip("contact_triplet_incomplete")

    thread_t = _human_thread_text(full_msgs)
    if not operational_gate_heuristic(thread_t):
        return _fallback_skip("operational_gate_heuristic_false")

    sender_name = f"{nome.strip()} {cognome.strip()}".strip()
    summary_body = strip_intake_contact_block(raw).strip() or thread_t.strip()
    summary_full = _human_thread_text(full_msgs)
    summary_use = summary_full if len(summary_full) > len(summary_body) else summary_body
    summary_use = summary_use.strip()[:7500]
    if len(summary_use) < 4:
        summary_use = "Richiesta da intake (fallback server)."

    title = summary_use.split("\n")[0].strip()[:200]
    if len(title) < 4:
        title = "Richiesta assistenza"

    helpdesk = _infer_helpdesk(em, summary_use)
    company_id = _company_id_for_email(em)

    try:
        result = await execute_route_and_open_ticket(
            helpdesk=helpdesk,
            title=title,
            full_summary=summary_use,
            sender_email=em.strip(),
            sender_name=sender_name,
            company_id=company_id,
        )
    except Exception:
        log.exception("try_intake_fallback_open fallito helpdesk=%s", helpdesk)
        return None, None
    tid = result.get("ticket_id")
    dept = result.get("helpdesk")
    if tid and dept:
        domain = em.split("@")[-1].strip() if "@" in em else ""
        log.warning(
            "intake_fallback_open_applied helpdesk=%s ticket_id=%s sender_domain=%s "
            "title_preview=%r intake_fallback=True",
            dept,
            tid,
            domain,
            title[:120],
        )
        return str(dept).strip(), str(tid).strip()
    return _fallback_skip("execute_route_and_open_ticket_empty_result")

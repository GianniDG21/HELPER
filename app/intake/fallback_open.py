"""Apertura pratica lato server se il modello non invoca route_and_open_ticket ma il gate è plausibilmente OK."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

from app.agent.trace import (
    _content_str,
    intake_contact_from_human_raw,
    strip_intake_contact_block,
)
from app.intake.companies_registry import lookup_company_by_email
from app.tools.intake_tools import execute_route_and_open_ticket

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

TeamId = Literal["vendita", "acquisto", "manutenzione"]

_AUTH_RE = re.compile(
    r"(?is)\b(confermo|autorizz|autorizza|segnaliamo|chiediamo|richiediamo|"
    r"in\s+qualit[aà]|per\s+conto|nostro\s+ordine|nostra\s+fattura|"
    r"siamo\s+autorizz|ufficio\s+acquisti|procedere\s+con|"
    r"richiesta\s+di\s+verifica|segnalazione)\b"
)


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


def _authorization_heuristic(thread_text: str) -> bool:
    if not thread_text or len(thread_text.strip()) < 8:
        return False
    return bool(_AUTH_RE.search(thread_text))


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
        return None, None

    raw = _last_human_raw(full_msgs)
    if not raw:
        return None, None

    nome, cognome, em = intake_contact_from_human_raw(raw)
    if not em or not nome or not cognome:
        return None, None

    thread_t = _human_thread_text(full_msgs)
    if not _authorization_heuristic(thread_t):
        return None, None

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
        log.warning(
            "intake_fallback_open: apertura server-side helpdesk=%s ticket_id=%s",
            dept,
            tid,
        )
        return str(dept).strip(), str(tid).strip()
    return None, None

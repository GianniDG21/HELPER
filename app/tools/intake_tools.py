"""Tool per fase intake: anagrafica, helpdesk, apertura ticket smistato (senza team_id in contesto)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from langchain_core.tools import tool

from app.config import TeamId
from app.db import registry
from app.db.repositories import pratiche as pract_repo
from app.db.repositories import tickets as repo
from app.intake.companies_registry import list_helpdesks_payload
from app.intake.companies_registry import lookup_company_by_email as match_company
from app.intake.request_hints import missing_intake_fallback_reply, operational_gate_heuristic

log = logging.getLogger(__name__)

_CONTACT_HEADER_RE = re.compile(r"(?i)\[\s*dati\s+contatto\s+richiedente\s*:\s*")
_CONTACT_FIELD_RE = re.compile(r"(?i)^\s*(nome|cognome|email)\s*=")
_SPLIT_SENTENCE_RE = re.compile(r"[.;:!?]\s+|\n+")
_GENERIC_LINE_RE = re.compile(
    r"(?i)\b(richiesta|ticket|pratica|aiuto|assistenza|helpdesk|riepilogo)\b"
)
_DEPT_TITLE_LABEL: dict[str, str] = {
    "manutenzione": "Officina",
    "acquisto": "Acquisto",
    "vendita": "Vendita",
}


def sanitize_intake_title(title: str, full_summary: str) -> str:
    """Crea un titolo breve e pulito, basato sul riepilogo completo della richiesta."""

    def _clean_lines(raw: str) -> list[str]:
        t = (raw or "").replace("\r", "\n")
        t = _CONTACT_HEADER_RE.sub("", t)
        out: list[str] = []
        for ln in t.split("\n"):
            s = ln.strip().strip("[]").strip()
            if not s:
                continue
            if _CONTACT_FIELD_RE.match(s):
                continue
            out.append(s)
        return out

    def _compact(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip(" -:;,|").strip()

    # 1) Prova a ricavare una frase rappresentativa dal full_summary (intero thread elaborato).
    summary_lines = _clean_lines(full_summary)
    if summary_lines:
        summary_text = _compact(" ".join(summary_lines))
        chunks = [c for c in _SPLIT_SENTENCE_RE.split(summary_text) if _compact(c)]
        if chunks:
            # Preferisci la frase più informativa (non troppo corta/generica).
            ranked = sorted(
                chunks,
                key=lambda c: (
                    _GENERIC_LINE_RE.search(c) is not None,  # generica = peggio
                    len(_compact(c)) < 18,  # troppo corta = peggio
                    abs(len(_compact(c)) - 78),  # target titolo leggibile
                ),
            )
            best = _compact(ranked[0])
            if len(best) >= 8:
                return best[:120]

    # 2) Fallback sul titolo passato dal modello.
    title_lines = _clean_lines(title)
    if title_lines:
        candidate = _compact(title_lines[0])
        if len(candidate) >= 4:
            return candidate[:120]
    return "Richiesta assistenza"


def format_intake_title(helpdesk: TeamId, title: str, full_summary: str) -> str:
    short = sanitize_intake_title(title, full_summary)
    dept_label = _DEPT_TITLE_LABEL.get(str(helpdesk), str(helpdesk).capitalize())
    return f"[{dept_label}] {short}"[:120]


def validate_open_ticket_gate(full_summary: str) -> str | None:
    """
    Guardrail server-side: blocca aperture premature anche se il modello chiama il tool.
    Ritorna None se il gate e OK, altrimenti un messaggio cliente-ready.
    """
    s = (full_summary or "").strip()
    if operational_gate_heuristic(s):
        return None
    return missing_intake_fallback_reply(s)


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
    safe_title = format_intake_title(helpdesk, title, full_summary)
    pool = registry.get_pool(helpdesk)
    async with pool.acquire() as conn:
        sector_tid_str = await repo.create_intake_routed_ticket(
            conn,
            sender_name,
            sender_email,
            safe_title,
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
            safe_title,
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
    gate_msg = validate_open_ticket_gate(full_summary)
    if gate_msg:
        return json.dumps(
            {
                "opened": False,
                "reason": "operational_gate_not_satisfied",
                "message": gate_msg,
            },
            ensure_ascii=False,
        )
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

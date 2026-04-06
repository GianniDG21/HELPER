"""Diagnostica per capire perché intake non produce ticket_id / reparto."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from app.agent.trace import _content_str, _try_parse_route_tool_dict


def _tool_call_names(msg: AIMessage) -> list[str]:
    out: list[str] = []
    for tc in msg.tool_calls or []:
        if isinstance(tc, dict):
            n = tc.get("name") or ""
        else:
            n = getattr(tc, "name", "") or ""
        out.append(str(n))
    return out


def build_intake_debug(
    turn_msgs: list[BaseMessage],
    extracted_dept: str | None,
    extracted_ticket: str | None,
    prev_n: int,
    total_msgs: int,
    *,
    intake_fallback_applied: bool = False,
) -> dict[str, Any]:
    ai_calls: list[dict[str, Any]] = []
    for m in turn_msgs:
        if isinstance(m, AIMessage) and m.tool_calls:
            ai_calls.append({"tool_calls": _tool_call_names(m)})

    tool_rows: list[dict[str, Any]] = []
    for m in turn_msgs:
        if not isinstance(m, ToolMessage):
            continue
        name = (getattr(m, "name", None) or "").strip() or "(senza nome)"
        raw = _content_str(m.content).strip()
        parsed = _try_parse_route_tool_dict(raw) if raw else None
        row: dict[str, Any] = {
            "tool_name": name,
            "content_length": len(raw),
            "content_preview": raw[:500] + ("…" if len(raw) > 500 else ""),
            "parsed_ok": parsed is not None,
        }
        if parsed is not None:
            row["parsed_ticket_id"] = parsed.get("ticket_id")
            row["parsed_helpdesk"] = parsed.get("helpdesk")
            row["parsed_queue_status"] = parsed.get("queue_status")
        if name == "route_and_open_ticket":
            if not raw:
                row["hint"] = "contenuto vuoto"
            elif not raw.lstrip().startswith("{") and parsed is None:
                row["hint"] = "uscita testuale (spesso errore tool / eccezione DB), non JSON"
            elif parsed is None:
                row["hint"] = "JSON non decodificabile dopo normalizzazione"
            elif parsed.get("queue_status") != "pending_acceptance":
                row["hint"] = (
                    f"queue_status={parsed.get('queue_status')!r} "
                    "≠ pending_acceptance (estrattore ignora)"
                )
            elif not parsed.get("ticket_id") or not parsed.get("helpdesk"):
                row["hint"] = "mancano ticket_id o helpdesk nel JSON"
            else:
                row["hint"] = "JSON OK; se extraction è null, controllare ordine messaggi nel turno"
        tool_rows.append(row)

    route_ai = any(
        isinstance(m, AIMessage)
        and m.tool_calls
        and "route_and_open_ticket" in _tool_call_names(m)
        for m in turn_msgs
    )
    route_tool = any(
        isinstance(m, ToolMessage) and getattr(m, "name", None) == "route_and_open_ticket"
        for m in turn_msgs
    )

    diagnosis: list[str] = []
    if extracted_ticket and extracted_dept and intake_fallback_applied:
        diagnosis.append(
            "OK: ticket_id e reparto da fallback server-side (nessun estratto valido dal tool nel turno)."
        )
    elif extracted_ticket and extracted_dept:
        diagnosis.append("OK: ticket_id e reparto estratti dal ToolMessage route_and_open_ticket.")
    elif route_tool:
        last = next(
            (
                r
                for r in reversed(tool_rows)
                if r.get("tool_name") == "route_and_open_ticket"
            ),
            None,
        )
        if last and last.get("hint") and "OK" not in last.get("hint", ""):
            diagnosis.append(f"route_and_open_ticket: {last['hint']}")
        else:
            diagnosis.append(
                "route_and_open_ticket eseguito ma estrazione API nulla: verificare parser o duplicati nel turno."
            )
    elif route_ai and not route_tool:
        diagnosis.append(
            "Il modello ha richiesto route_and_open_ticket ma non c’è ToolMessage: "
            "esecuzione tool fallita (log server) o grafo interrotto."
        )
    else:
        diagnosis.append(
            "Nessuna chiamata a route_and_open_ticket nel turno: gate apertura (contatti + dati richiesta), "
            "fase grafo o modello non ha chiuso lo smistamento."
        )

    return {
        "checkpoint": {
            "messages_before_turn": prev_n,
            "messages_total_after": total_msgs,
            "new_messages_in_turn": len(turn_msgs),
        },
        "extraction_api": {
            "routed_department": extracted_dept,
            "ticket_id": extracted_ticket,
            "intake_fallback_applied": intake_fallback_applied,
        },
        "signals": {
            "ai_requested_route_and_open_ticket": route_ai,
            "tool_route_and_open_ticket_ran": route_tool,
        },
        "ai_tool_call_batches": ai_calls,
        "tool_messages": tool_rows,
        "diagnosis": diagnosis,
    }


def intake_debug_log_line(payload: dict[str, Any]) -> str:
    """Riga compatta per log (evita dump enormi)."""
    try:
        return json.dumps(payload, ensure_ascii=False)[:3500]
    except Exception:
        return str(payload)[:3500]

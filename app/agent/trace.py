from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

# Blocco aggiunto dal backend dal form contatto (mostrato senza prefisso in UI)
INTAKE_CONTACT_BLOCK_RE = re.compile(
    r"(?s)^\s*\[Dati contatto richiedente:\s*.*?\]\s*\n*",
)

_PLACEHOLDER_AI_RE = re.compile(
    r"(?is)^\s*\(?\s*(?:"
    r"si\s+aspetta\s+la\s+risposta\s+dell['\u2019]?utente"
    r"|in\s+attesa\s+di\s+risposta"
    r"|waiting\s+for\s+(?:user\s+)?response"
    r")\s*\)?\s*\.?\s*$"
)


def strip_intake_contact_block(text: str) -> str:
    """Rimuove il prefisso modulo contatto dal testo mostrato in chat/traccia."""
    if not text:
        return text
    return INTAKE_CONTACT_BLOCK_RE.sub("", text).strip()


def _is_placeholder_assistant_text(text: str) -> bool:
    """Messaggi interni di stato (es. fasi think/learn) da non mostrare come risposta al cliente."""
    raw = (text or "").strip()
    if not raw:
        return True
    if _PLACEHOLDER_AI_RE.match(raw):
        return True
    if len(raw) < 160 and raw.startswith("(") and raw.endswith(")"):
        low = raw.lower()
        if "attesa" in low or "aspetta" in low:
            return True
    return False


def _raw_synthesis_after_tools(msgs: list[BaseMessage]) -> str:
    """Testo dell ultima risposta utile: preferisce AIMessage dopo l ultimo ToolMessage (sintesi grafo)."""
    last_tool_idx = -1
    for i, m in enumerate(msgs):
        if isinstance(m, ToolMessage):
            last_tool_idx = i

    def last_substantive_ai(below_idx: int) -> str:
        for idx in range(below_idx - 1, last_tool_idx, -1):
            if idx < 0:
                break
            m = msgs[idx]
            if isinstance(m, AIMessage):
                t = _content_str(m.content).strip()
                if t and not _is_placeholder_assistant_text(t):
                    return t
        return ""

    r = last_substantive_ai(len(msgs))
    if r:
        return r
    for idx in range(len(msgs) - 1, -1, -1):
        m = msgs[idx]
        if isinstance(m, AIMessage):
            t = _content_str(m.content).strip()
            if t and not _is_placeholder_assistant_text(t):
                return t
    return ""


def _strip_intake_self_correction(text: str) -> str:
    """Rimuove scuse/meta del modello tipo correzione rispetto alle linee guida (solo testo grezzo)."""
    if not text or not text.strip():
        return text
    t = text.strip()
    m = re.search(r"(?is)\bEcco una risposta corretta\s*:\s*", t)
    if m:
        t = t[m.end() :].strip()
    t = re.sub(
        r"(?is)^(?:Mi scuso per la risposta precedente[^\n]+(?:\n[^\n]+)*?\n\s*)+",
        "",
        t,
    )
    t = re.sub(r"(?is)^(?:ma devo seguire le linee guida fornite\.?\s*\n?\s*)+", "", t)
    return t.strip()


_EMAIL_FIND_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")

_INTAKE_REPLY_FALLBACK = (
    "Grazie per averci scritto. Per aiutarti al meglio, puoi descrivere in breve cosa succede "
    "quando provi a inserire la pratica nel gestionale (messaggio di errore o comportamento)?"
)


def intake_contact_from_human_raw(human_raw: str | None) -> tuple[str | None, str | None, str | None]:
    if not human_raw or "Dati contatto richiedente" not in human_raw:
        return None, None, None
    nome = cognome = em = None
    if m := re.search(r"(?im)^nome\s*=\s*(.+)$", human_raw):
        nome = m.group(1).strip()
    if m := re.search(r"(?im)^cognome\s*=\s*(.+)$", human_raw):
        cognome = m.group(1).strip()
    if m := re.search(r"(?im)^email\s*=\s*(\S+)$", human_raw):
        em = m.group(1).strip()
    return nome, cognome, em


_INTERNAL_INTAKE_SNIPPETS = (
    re.compile(r"(?is)gate\s+contatti"),
    re.compile(r"(?is)punt[oai]\s+del\s+gate"),
    re.compile(r"(?is)\bmodulo\s+contatto\b"),
    re.compile(r"(?is)prefisso\s+tecnico"),
    re.compile(r"(?is)\bINTAKE_?STYLE\b"),
    re.compile(r"(?is)route[_ ]?and[_ ]?open[_ ]?ticket"),
    re.compile(r"(?is)lookup_company"),
    re.compile(r"(?is)list_helpdesks"),
    re.compile(r"(?is)tool\s*message"),
    re.compile(r"(?is)tool\s*calls?\b"),
    re.compile(r"(?is)\bmittente\s+ha\s+confermato\s+l['\u2019]?email\b"),
    re.compile(r"(?is)l['\u2019]?email\s+che\s+ho\s+utilizzato"),
    re.compile(r"(?is)questo\s+punto\s+.*\s+e\s+soddisfatt[oa]"),
    re.compile(r"(?is)^\s*#{1,6}\s*[–-]?\s*0\d"),
)


def _intake_internal_leak(text: str) -> bool:
    if "###" in text:
        return True
    if re.search(r"(?i)\b(?:fase|step)\s+0\d\b", text):
        return True
    for rx in _INTERNAL_INTAKE_SNIPPETS:
        if rx.search(text):
            return True
    return False


def _sanitize_intake_customer_reply(text: str, *, form_email: str | None) -> str:
    """Rimuove paragrafi con leak di prompt / checklist e email non presenti nel modulo contatto."""
    if not text or not text.strip():
        return ""
    paras = re.split(r"\n\s*\n+", text.strip())
    kept: list[str] = []
    for p in paras:
        lines_out: list[str] = []
        for line in p.splitlines():
            sl = line.strip()
            if re.match(r"^#{1,6}\s+", sl):
                continue
            if _intake_internal_leak(line):
                continue
            lines_out.append(line.rstrip())
        sub = "\n".join(lines_out).strip()
        if not sub or _intake_internal_leak(sub):
            continue
        kept.append(sub)
    out = "\n\n".join(kept).strip()
    out = _drop_paragraphs_with_unlisted_emails(out, form_email)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip()


def _drop_paragraphs_with_unlisted_emails(text: str, allowed: str | None) -> str:
    if not text or not allowed:
        return text
    allo = allowed.strip().lower()
    if not allo:
        return text
    paras = re.split(r"\n\s*\n+", text)
    kept: list[str] = []
    for p in paras:
        pt = p.strip()
        if not pt:
            continue
        emails = _EMAIL_FIND_RE.findall(pt)
        if not emails:
            kept.append(pt)
            continue
        if all(e.lower() == allo for e in emails):
            kept.append(pt)
    return "\n\n".join(kept).strip()


def _dedupe_intake_sentences(text: str) -> str:
    """Rimuove frasi consecutive o ripetute quasi identiche (ridondanza LLM)."""
    raw = (text or "").strip()
    if not raw:
        return raw
    parts = re.split(r"(?<=[.!?…])\s+", raw)
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        st = p.strip()
        if not st:
            continue
        key = re.sub(r"\s+", " ", st.lower())
        if len(key) >= 14 and key in seen:
            continue
        seen.add(key)
        out.append(st)
    single = " ".join(out).strip()
    # due paragrafi uguali dopo split su newline
    paras = [x.strip() for x in single.split("\n\n") if x.strip()]
    deduped: list[str] = []
    seen_p: set[str] = set()
    for para in paras:
        pk = re.sub(r"\s+", " ", para.lower())
        if len(pk) >= 24 and pk in seen_p:
            continue
        seen_p.add(pk)
        deduped.append(para)
    return "\n\n".join(deduped).strip()


def user_visible_reply(
    msgs: list[BaseMessage],
    *,
    strip_intake_meta: bool = False,
    intake_human_raw: str | None = None,
) -> str:
    """Risposta unica mostrata in chat/transcript: allineata all ultima sintesi post-tool."""
    text = _raw_synthesis_after_tools(msgs)
    if strip_intake_meta and text:
        text = _strip_intake_self_correction(text)
    text = format_reply_for_end_user(text)
    if strip_intake_meta:
        hr = intake_human_raw
        if hr is None:
            for m in msgs:
                if isinstance(m, HumanMessage):
                    hr = _content_str(m.content)
                    break
        _, _, form_email = intake_contact_from_human_raw(hr) if hr else (None, None, None)
        if text:
            text = _sanitize_intake_customer_reply(text, form_email=form_email)
            text = _dedupe_intake_sentences(text)
        if not text or len(text) < 12:
            text = _INTAKE_REPLY_FALLBACK
    return text


def format_reply_for_end_user(text: str) -> str:
    """Pulisce testo per chat: no meta-intestazioni, no leak di tool/XML."""
    if not text or not text.strip():
        return ""
    t = re.sub(r"<\s*function[^>]*>.*?</\s*function\s*>", "", text, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<\s*function[^>]*/\s*>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<\s*function[^>]*>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<\s*/\s*function\s*>", "", t, flags=re.IGNORECASE)
    kept: list[str] = []
    for line in t.splitlines():
        s = line.strip()
        if re.match(r"^#{1,6}\s+", s):
            continue
        if re.search(r"<\s*function|</\s*function|function\s*=", s, re.IGNORECASE):
            continue
        kept.append(line.rstrip())
    out = "\n".join(kept).strip()
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out


def _content_str(content: str | list[str | dict] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        return "\n".join(parts)
    return str(content)


def _tool_calls_summary(tool_calls: list[Any] | None) -> list[dict[str, Any]]:
    if not tool_calls:
        return []
    out: list[dict[str, Any]] = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            name = tc.get("name", "")
            args = tc.get("args") or tc.get("arguments")
        else:
            name = getattr(tc, "name", "") or ""
            args = getattr(tc, "args", None)
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"raw": args}
        if not isinstance(args, dict):
            args = {"value": args}
        out.append({"name": name, "args": args})
    return out


_TOOL_TITLE_IT: dict[str, str] = {
    "lookup_company_by_email": "Verifica azienda (anagrafica)",
    "list_helpdesks": "Elenco reparti interni",
    "route_and_open_ticket": "Apertura ticket in coda reparto",
    "list_tickets": "Lettura ticket del reparto",
    "get_ticket": "Dettaglio ticket",
    "list_customers": "Elenco clienti/fornitori",
    "list_employees": "Elenco dipendenti del reparto",
    "create_ticket": "Creazione ticket",
    "update_ticket_status": "Aggiornamento stato ticket",
    "send_simulated_email_to_requester": "Email simulata al richiedente",
}


def _tool_title(tool_name: str | None) -> str:
    if not tool_name:
        return "Operazione automatica"
    return _TOOL_TITLE_IT.get(tool_name, tool_name.replace("_", " "))


def _summarize_tool_json(name: str | None, raw: str) -> str:
    if not raw or not raw.strip():
        return "Completato."
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        t = raw.strip()
        return t if len(t) <= 400 else t[:397] + "…"

    if name == "lookup_company_by_email":
        if not isinstance(data, dict):
            return str(data)
        if data.get("found") is True:
            cn = data.get("trade_name") or data.get("legal_name") or "—"
            parts = [f"Azienda riconosciuta: {cn}"]
            if sh := data.get("suggested_helpdesk"):
                parts.append(f"Reparto suggerito: {sh}")
            return " · ".join(parts)
        return "Nessuna azienda in anagrafica per questo dominio email."

    if name == "list_helpdesks":
        if isinstance(data, list):
            n = len(data)
            return f"Caricati {n} reparto/i con le relative competenze."
        return "Reparti caricati."

    if name == "route_and_open_ticket":
        if isinstance(data, dict):
            tid = data.get("ticket_id", "?")
            hd = data.get("helpdesk", "?")
            return f"Ticket creato nel reparto «{hd}». Numero pratica: {tid}."
        return str(data)

    if name == "list_tickets" and isinstance(data, list):
        return f"Trovati {len(data)} ticket."

    if name == "get_ticket" and isinstance(data, dict):
        t = data.get("title") or data.get("id") or "ticket"
        st = data.get("status", "")
        return f"Dettaglio: {t}" + (f" (stato: {st})" if st else "")

    if name in ("list_customers", "list_employees") and isinstance(data, list):
        return f"Letti {len(data)} record."

    if name == "create_ticket" and isinstance(data, dict):
        tid = data.get("created_ticket_id") or data.get("id")
        return f"Nuovo ticket creato: {tid}."

    if name == "update_ticket_status" and isinstance(data, dict):
        st = data.get("status", "?")
        tid = data.get("ticket_id", "")
        return f"Ticket {tid}: stato → {st}."

    if name == "send_simulated_email_to_requester" and isinstance(data, dict):
        if data.get("ok"):
            return (
                f"Email simulata verso {data.get('to', '?')}. "
                f"{data.get('message', 'Registrata.')}"
            )
        return str(data.get("message", data))

    if isinstance(data, dict) and len(json.dumps(data, ensure_ascii=False)) < 280:
        return json.dumps(data, ensure_ascii=False)
    return "Risposta dal sistema ricevuta (vedi dettaglio se serve)."


def _enrich_trace_step(step: dict[str, Any]) -> dict[str, Any]:
    kind = step.get("kind")
    ui: dict[str, Any] = {"title": "", "summary": "", "show_raw": False}

    if kind == "user":
        ui["title"] = "Messaggio in arrivo"
        ui["summary"] = step.get("content") or ""
    elif kind == "assistant":
        tcs = step.get("tool_calls") or []
        if tcs:
            names = [_tool_title(tc.get("name")) for tc in tcs]
            ui["title"] = "Azioni pianificate"
            ui["summary"] = " · ".join(names)
            ui["show_raw"] = True
        else:
            ui["title"] = "Risposta del modello"
            ui["summary"] = (step.get("content") or "").strip()
            ui["show_raw"] = bool(
                ui["summary"] and len(ui["summary"]) > 500
            )
    elif kind == "tool":
        tn = step.get("tool_name")
        content = step.get("content") or ""
        ui["title"] = _tool_title(tn)
        ui["summary"] = _summarize_tool_json(tn, content)
        ui["show_raw"] = len(content) > 180 or "\n" in content

    step = {**step, "ui": ui}
    return step


def messages_to_trace(msgs: list[BaseMessage]) -> list[dict[str, Any]]:
    """Serializza i messaggi del grafo per il pannello operativo (con sintesi leggibile)."""
    trace: list[dict[str, Any]] = []
    for m in msgs:
        if isinstance(m, HumanMessage):
            trace.append(
                {"kind": "user", "content": strip_intake_contact_block(_content_str(m.content))}
            )
        elif isinstance(m, AIMessage):
            tcs = _tool_calls_summary(m.tool_calls)
            content_raw = _content_str(m.content) or ""
            if not tcs and (not content_raw.strip() or _is_placeholder_assistant_text(content_raw)):
                continue
            step: dict[str, Any] = {
                "kind": "assistant",
                "content": content_raw or None,
            }
            if tcs:
                step["tool_calls"] = tcs
            trace.append(step)
        elif isinstance(m, ToolMessage):
            trace.append(
                {
                    "kind": "tool",
                    "tool_name": m.name,
                    "content": _content_str(m.content),
                }
            )
    return [_enrich_trace_step(s) for s in trace]


def final_assistant_reply(msgs: list[BaseMessage]) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            text = _content_str(m.content).strip()
            if text:
                return format_reply_for_end_user(text)
    if msgs:
        return format_reply_for_end_user(_content_str(getattr(msgs[-1], "content", None)))
    return ""


def transcript_turns(
    msgs: list[BaseMessage], *, strip_intake_meta: bool = False
) -> list[dict[str, str]]:
    """Ricostruisce la chat: stessa logica di user_visible_reply per risposta assistente."""
    out: list[dict[str, str]] = []
    i = 0
    while i < len(msgs):
        if isinstance(msgs[i], HumanMessage):
            human = _content_str(msgs[i].content)
            if strip_intake_meta:
                human = strip_intake_contact_block(human)
            j = i + 1
            while j < len(msgs) and not isinstance(msgs[j], HumanMessage):
                j += 1
            chunk = msgs[i + 1 : j]
            human_full = _content_str(msgs[i].content)
            reply = user_visible_reply(
                chunk,
                strip_intake_meta=strip_intake_meta,
                intake_human_raw=human_full if strip_intake_meta else None,
            )
            out.append({"role": "user", "content": human})
            if reply:
                out.append({"role": "assistant", "content": reply})
            i = j
        else:
            i += 1
    return out


def intake_routing_from_turn(msgs: list[BaseMessage]) -> tuple[str | None, str | None]:
    """Ultimo esito route_and_open_ticket nel turno: (helpdesk, ticket_id) o (None, None)."""
    for m in reversed(msgs):
        if not isinstance(m, ToolMessage):
            continue
        if (getattr(m, "name", None) or "") != "route_and_open_ticket":
            continue
        raw = _content_str(m.content).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        tid = data.get("ticket_id")
        if tid is None or tid == "":
            continue
        tid_str = str(tid).strip()
        dept = data.get("helpdesk")
        return (str(dept) if dept else None, tid_str)
    return (None, None)

"""Riduce il contesto inviato al nodo finale dei grafi multi-fase."""
from __future__ import annotations

import re

from langchain_core.messages import AIMessage, BaseMessage

from app.agent.trace import _content_str

# Titoli di fase (01-09, 10, …) o "## 05" che il modello a volte recita nel testo al cliente
_INTERNAL_PHASE_HEADING = re.compile(r"(?m)^\s*#{1,6}\s*\d{1,2}\b")


def _is_internal_phase_ai(m: AIMessage) -> bool:
    """Fasi mission/scan/think/act con tool: non devono arrivare al modello che sintetizza per l'utente."""
    if m.tool_calls:
        return True
    t = _content_str(m.content)
    if _INTERNAL_PHASE_HEADING.search(t):
        return True
    return False


def messages_for_learn(msgs: list[BaseMessage]) -> list[BaseMessage]:
    """Mantiene umani, tool, messaggi assistente gia rivolti al destinatario; esclude traccia fasi interne."""
    out: list[BaseMessage] = []
    for m in msgs:
        if isinstance(m, AIMessage) and _is_internal_phase_ai(m):
            continue
        out.append(m)
    return out

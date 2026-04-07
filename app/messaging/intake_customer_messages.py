"""Messaggi mostrati al richiedente in intake: unica fonte di testo canonico post-apertura pratica."""
from __future__ import annotations

# Chiavi = valore helpdesk da tool / API
_DEPT_CLOSING: dict[str, str] = {
    "manutenzione": "Un operatore la prenderà in carico per l’intervento in officina.",
    "acquisto": "Un operatore seguirà la pratica su ordini, forniture o amministrazione acquisti.",
    "vendita": "Un operatore commerciale la gestirà e ti ricontatterà se necessario.",
}

_DEFAULT_CLOSING = "Un operatore la prenderà in carico al più presto."

_DEPT_LABEL: dict[str, str] = {
    "vendita": "vendita",
    "acquisto": "acquisto",
    "manutenzione": "officina",
}


def department_display_label(department_key: str | None) -> str:
    d = (department_key or "").strip().lower()
    return _DEPT_LABEL.get(d, (department_key or "").strip() or "di competenza")


def canonical_pratica_registered(department_key: str | None, pratica_id: str) -> str:
    """
    Messaggio dopo apertura riuscita: allineato all’esito API (fonte di verità).
    Chiusura dipende leggermente dal reparto (best practice contact center / ticketing).
    """
    tid = (pratica_id or "").strip()
    label = department_display_label(department_key)
    d = (department_key or "").strip().lower()
    closing = _DEPT_CLOSING.get(d, _DEFAULT_CLOSING)
    return (
        f"La pratica è stata registrata e inoltrata al reparto {label}. "
        f"Numero pratica: {tid}. {closing}"
    )

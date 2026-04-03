"""Anagrafica aziende (allineata ai seed SQL companies)."""

from __future__ import annotations

from typing import Any

COMPANY_RECORDS: list[dict[str, Any]] = [
    {
        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "trade_name": "Trasporti Nord",
        "legal_name": "Flotta Trasporti Nord Srl",
        "email_domain": "trasportinord.it",
        "suggested_helpdesk": "manutenzione",
    },
    {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "trade_name": "Disbrigo Ricambi",
        "legal_name": "Disbrigo Ricambi Srl",
        "email_domain": "disbrigo.it",
        "suggested_helpdesk": "acquisto",
    },
    {
        "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "trade_name": "Officina Garino",
        "legal_name": "Garino SNC",
        "email_domain": "garino-officina.it",
        "suggested_helpdesk": "vendita",
    },
    {
        "id": "b0b0b0b0-b0b0-b0b0-b0b0-b0b0b0b0b0b0",
        "trade_name": "Cliente generico",
        "legal_name": "Contatti esterni",
        "email_domain": "email.it",
        "suggested_helpdesk": "vendita",
    },
]


def domain_from_email(email: str) -> str:
    parts = (email or "").strip().lower().split("@")
    return parts[-1] if len(parts) == 2 else ""


def lookup_company_by_email(email: str) -> dict[str, Any] | None:
    """Trova azienda per dominio del mittente (o None)."""
    dom = domain_from_email(email)
    if not dom:
        return None
    for c in COMPANY_RECORDS:
        if c["email_domain"] == dom:
            return dict(c)
    return None


def list_helpdesks_payload() -> list[dict[str, str]]:
    return [
        {
            "key": "vendita",
            "label": "Vendita / banco ricambi",
            "descr": "Preventivi, ordini ricambi, reclami clienti e officine convenzionate.",
        },
        {
            "key": "acquisto",
            "label": "Acquisto",
            "descr": "Fornitori, ordini in ingresso, fatture e resi verso fornitori.",
        },
        {
            "key": "manutenzione",
            "label": "Manutenzione / officina",
            "descr": "Interventi meccanici, diagnostica, tagliandi, flotte.",
        },
    ]

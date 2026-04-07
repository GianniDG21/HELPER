"""Euristiche sul testo del thread intake (veicolo, ricambi) — senza dipendenze da trace o grafo."""
from __future__ import annotations

import re

# Intent: manutenzione / veicolo (serve anno + km prima di aperture automatiche o messaggi mirati)
_VEHICLE_INTENT_RE = re.compile(
    r"(?is)\b(tagliando|tagliand|revisione|revision\b|officina|intervento|manutenz\w*|"
    r"service\b|veicol\w*|automobil|\bauto\b|\bcamion\b|furgon|motore\b|flotta|"
    r"targa|pneumatic|olio\s+motore|cambio\s+olio)\b|"
    r"\b(polo|golf|passat|panda|yaris|ducato|transit|fiat\s+\w{2,}|bmw|mercedes|audi|ford)\b",
)

# Intent: ricambi / materiale (serve quantità)
_PARTS_INTENT_RE = re.compile(
    r"(?is)\b(ricamb|pezzo|pezzi|materiale|articol|fornitura|"
    r"codice\s+articolo|cod\.\s*articolo|filtri?\b|gomm\w*|bulloni)\b|"
    r"\bordine\s+(?:di\s+)?(?:ricamb|pezzi|materiale)",
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Targa italiana tipica: AA123BB (opz. spazi); utile come identificativo veicolo se manca l’anno
_IT_PLATE_RE = re.compile(r"(?i)\b([A-Z]{2}\s?\d{3}\s?[A-Z]{2})\b")
_PLATE_KEYWORD_RE = re.compile(r"(?is)\btarg(?:a|he)\b")

_MILEAGE_RE = re.compile(
    r"(?is)(\d{1,3}(?:[.\s]\d{3})+|\d{4,7})\s*(?:km\b|k\s*m\b)|"
    r"chilometr\w*\s*(?:di|attuali?|correnti?|circa)?\s*[.:]?\s*\d|"
    r"\d{1,3}(?:[.\s]\d{3})*\s*chilometr",
)

_PART_QTY_RE = re.compile(
    r"(?is)\bquantit[aà]\s*[.:]?\s*\d+|\d{1,6}\s*(?:pz|pezzi)\b|"
    r"\bnr\.?\s*[.:]?\s*\d+|\bpezzi\s*[.:]?\s*\d+|\bordino\s+\d+|"
    r"\b\d{1,5}\s+(?:filtri|filtro|ricambi|pezzi?|gomm\w*|bulloni)\b|"
    r"\b\d{1,5}\s*x\s*(?:filtri|filtro|pezzi?|ricambi)\b",
)


def has_vehicle_year(t: str) -> bool:
    return bool(_YEAR_RE.search(t))


def has_vehicle_plate(t: str) -> bool:
    return bool(_IT_PLATE_RE.search(t))


def has_invalid_vehicle_plate_format(t: str) -> bool:
    """
    Se viene citata esplicitamente la targa ma non compare un formato valido AA123BB,
    il dato operativo e da considerare non valido.
    """
    return bool(_PLATE_KEYWORD_RE.search(t)) and not has_vehicle_plate(t)


def has_vehicle_identity(t: str) -> bool:
    """Anno/modello-anno oppure targa: basta uno per considerare il veicolo identificato (oltre ai km)."""
    return has_vehicle_year(t) or has_vehicle_plate(t)


def has_mileage(t: str) -> bool:
    return bool(_MILEAGE_RE.search(t))


def vehicle_service_intent(t: str) -> bool:
    return bool(_VEHICLE_INTENT_RE.search(t))


def parts_intent(t: str) -> bool:
    return bool(_PARTS_INTENT_RE.search(t))


def has_part_quantity(t: str) -> bool:
    return bool(_PART_QTY_RE.search(t))


def operational_gate_heuristic(thread_text: str) -> bool:
    """Allineato al gate prompt: veicolo = identità (anno o targa) + km; ricambi = quantità."""
    t = thread_text.strip()
    if len(t) < 10:
        return False
    v = vehicle_service_intent(t)
    p = parts_intent(t)
    if v and p:
        return (
            not has_invalid_vehicle_plate_format(t)
            and
            has_mileage(t)
            and has_vehicle_identity(t)
            and has_part_quantity(t)
        )
    if v:
        return (
            not has_invalid_vehicle_plate_format(t)
            and has_mileage(t)
            and has_vehicle_identity(t)
        )
    if p:
        return has_part_quantity(t)
    return True


def missing_intake_fallback_reply(thread_text: str) -> str:
    """
    Messaggio mostrato al richiedente quando la risposta LLM è stata scartata dalla sanificazione.
    Deve essere coerente con officina/reparti, mai assumere problemi di «gestionale» software.
    """
    t = (thread_text or "").strip()
    v = vehicle_service_intent(t)
    p = parts_intent(t)
    hy = has_vehicle_year(t)
    hp = has_vehicle_plate(t)
    hip = has_invalid_vehicle_plate_format(t)
    hid = has_vehicle_identity(t)
    hm = has_mileage(t)
    hq = has_part_quantity(t)

    if v and hip:
        return (
            "Per favore indica la targa in formato standard italiano: due lettere, tre cifre, due lettere "
            "(es. AA123BB)."
        )
    if v and hid and not hm:
        return (
            "Grazie per i dettagli sul veicolo. Per completare la richiesta in officina, "
            "indica il chilometraggio attuale (es. 72000 km)."
        )
    if v and hm and not hid:
        return (
            "Grazie per il chilometraggio. Indica anche la targa del veicolo oppure anno di immatricolazione / modello."
        )
    if v and not hid and not hm:
        return (
            "Per l’intervento in officina servono chilometraggio attuale e un identificativo del veicolo "
            "(targa oppure anno/modello). Puoi indicare per primi quelli che hai sotto mano?"
        )
    if p and not hq:
        return (
            "Grazie per la richiesta. Per gli ordini ricambi indica la quantità di pezzi necessaria "
            "(un solo valore per messaggio)."
        )
    if v or p:
        return (
            "Grazie per averci scritto. Per inoltrare la richiesta al reparto corretto "
            "manca un dettaglio operativo: rispondi con una sola informazione chiara per messaggio."
        )
    return (
        "Grazie per averci scritto. Per inoltrare la richiesta al reparto corretto "
        "descrivi in breve il problema operativo (ordine, veicolo, fornitura, ecc.), "
        "una informazione per volta se l’assistente chiede chiarimenti."
    )

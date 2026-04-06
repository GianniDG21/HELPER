"""Confronto UUID tollerante (stringhe da DB/API, uuid.UUID)."""
from __future__ import annotations

import uuid


def uuid_equal(a: object, b: object) -> bool:
    try:
        return uuid.UUID(str(a)) == uuid.UUID(str(b))
    except ValueError:
        return False

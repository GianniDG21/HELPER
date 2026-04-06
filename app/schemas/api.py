"""Modelli Pydantic condivisi dalle route HTTP."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import TeamId

_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
TICKET_ID_STR_PATTERN = r"^\d+$"


class IntakeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None
    contact_first_name: str | None = Field(default=None, max_length=120)
    contact_last_name: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=320)

    @model_validator(mode="after")
    def _contact_triplet(self) -> IntakeChatRequest:
        fn = (self.contact_first_name or "").strip()
        ln = (self.contact_last_name or "").strip()
        em = (self.contact_email or "").strip()
        any_set = bool(fn or ln or em)
        if any_set:
            if not fn or not ln or not em:
                raise ValueError(
                    "Contatto: compilare insieme nome, cognome e email (o lasciare tutti vuoti)."
                )
            if not _CONTACT_EMAIL_RE.match(em):
                raise ValueError("Contatto: formato email non valido.")
        return self

    def human_message_content(self) -> str:
        fn = (self.contact_first_name or "").strip()
        ln = (self.contact_last_name or "").strip()
        em = (self.contact_email or "").strip()
        parts: list[str] = []
        if fn and ln and em:
            parts.append(
                "[Dati contatto richiedente:\n"
                f"nome={fn}\ncognome={ln}\nemail={em}]\n\n"
            )
        parts.append(self.message.strip())
        return "".join(parts)


class IntakeChatResponse(BaseModel):
    thread_id: str
    reply: str
    trace: list[dict]
    routed_department: str | None = Field(
        default=None,
        description="Reparto effettivo se route_and_open_ticket ha avuto successo nel turno",
    )
    ticket_id: str | None = Field(
        default=None,
        description="ID pratica nel registry centralizzato (DB pratiche) dopo route_and_open_ticket",
    )
    debug: dict | None = Field(
        default=None,
        description="Diagnostica (solo se impostato DEBUG_INTAKE=1 in .env)",
    )

    @field_validator("ticket_id", mode="before")
    @classmethod
    def _ticket_id_as_str(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class AssistChatRequest(BaseModel):
    department: TeamId
    ticket_id: str = Field(min_length=1, max_length=19, pattern=TICKET_ID_STR_PATTERN)
    employee_id: str = Field(min_length=4, max_length=64)
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None


class AssistChatResponse(BaseModel):
    thread_id: str
    department: str
    ticket_id: str
    employee_id: str
    reply: str
    trace: list[dict]


class ThreadTranscriptResponse(BaseModel):
    thread_id: str
    messages: list[dict]
    mode: str = Field(description="intake | assist")


class AcceptTicketBody(BaseModel):
    employee_id: str = Field(min_length=4, max_length=64)


class MailRichiedenteBody(BaseModel):
    employee_id: str = Field(min_length=4, max_length=64)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=8000)

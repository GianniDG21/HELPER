from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import tool

from core.settings import get_settings
from integrations.zammad_client import ZammadClient, ZammadConfig


def _required_fields_payload() -> dict[str, Any]:
    settings = get_settings()
    return {
        "required_fields": settings.required_fields_list,
        "ticketing_backend": settings.ticketing_backend,
    }


def _build_zammad_client() -> ZammadClient:
    settings = get_settings()
    config = ZammadConfig(
        base_url=settings.zammad_base_url,
        api_token=settings.zammad_api_token or "",
        default_customer=settings.zammad_customer,
        default_group=settings.zammad_group,
    )
    return ZammadClient(config)


@tool
def read_ticketing_context() -> str:
    """Read ticketing runtime configuration and required fields."""
    return json.dumps(_required_fields_payload(), ensure_ascii=False)


@tool
def open_ticket(
    subject: str,
    description: str,
    name: str,
    email: str,
) -> str:
    """Create a ticket with the configured backend (stub or Zammad)."""
    settings = get_settings()

    if settings.ticketing_backend == "stub":
        fake_id = f"stub-{int(datetime.now(UTC).timestamp())}"
        out = {
            "ok": True,
            "backend": "stub",
            "ticket_id": fake_id,
            "number": fake_id,
            "subject": subject,
            "requester": {"name": name, "email": email},
        }
        return json.dumps(out, ensure_ascii=False)

    client = _build_zammad_client()
    ticket_body = f"Requester: {name} <{email}>\n\n{description}"
    out = client.create_ticket(title=subject, body=ticket_body, customer=email)
    out["backend"] = "zammad"
    out["requester"] = {"name": name, "email": email}
    return json.dumps(out, ensure_ascii=False)


def read_tools() -> list[Any]:
    return [read_ticketing_context]


def write_tools() -> list[Any]:
    return [open_ticket]

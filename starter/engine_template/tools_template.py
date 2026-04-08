"""Minimal read/write tool placeholders.

Swap these with your API/DB tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def read_context() -> str:
    """Read placeholder context."""
    return "No context configured yet."


@tool
def open_ticket_stub(subject: str, body: str) -> str:
    """Write placeholder (replace with your real ticket API call)."""
    return f"stub_ticket_created: subject={subject}"


def read_tools() -> list[Any]:
    return [read_context]


def write_tools() -> list[Any]:
    return [open_ticket_stub]


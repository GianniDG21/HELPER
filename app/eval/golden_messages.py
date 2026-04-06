"""
Costruisce sequenze LangChain da JSON per test/eval sul parsing di route_and_open_ticket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

_GOLDEN_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "intake_golden_scenarios.json"


def messages_from_scenario_messages(spec: list[dict[str, Any]]) -> list[BaseMessage]:
    """Converte la chiave `messages` di uno scenario in BaseMessage."""
    out: list[BaseMessage] = []
    for i, item in enumerate(spec):
        role = (item.get("role") or "").strip().lower()
        if role == "human":
            out.append(HumanMessage(content=str(item.get("content") or "")))
        elif role == "ai":
            out.append(AIMessage(content=str(item.get("content") or "")))
        elif role == "tool":
            name = (item.get("name") or "route_and_open_ticket").strip()
            content = str(item.get("content") or "")
            tcid = str(item.get("tool_call_id") or f"eval-tc-{i}")
            out.append(
                ToolMessage(content=content, name=name, tool_call_id=tcid)
            )
        else:
            raise ValueError(f"Ruolo messaggio golden non supportato: {role!r}")
    return out


def load_golden_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _GOLDEN_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("intake_golden_scenarios.json deve essere un array di scenario")
    return raw


def scenario_messages(scenario: dict[str, Any]) -> list[BaseMessage]:
    msgs = scenario.get("messages")
    if not isinstance(msgs, list):
        raise ValueError(f"Scenario {scenario.get('id')!r}: manca messages[]")
    return messages_from_scenario_messages(msgs)

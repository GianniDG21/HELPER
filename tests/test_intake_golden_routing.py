"""
Golden scenario sul parsing deterministico di intake (estrattore route_and_open_ticket).
Non richiede LLM né database.
"""
from __future__ import annotations

import pytest

from app.agent.trace import intake_routing_from_turn, intake_routing_from_turn_loose
from app.eval.golden_messages import load_golden_scenarios, scenario_messages


def _scenarios():
    return load_golden_scenarios()


@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s["id"])
def test_intake_golden_routing_strict(scenario):
    msgs = scenario_messages(scenario)
    dept, tid = intake_routing_from_turn(msgs)
    exp = scenario.get("expect_strict")
    if exp is None:
        assert dept is None and tid is None
    else:
        assert dept == exp["department"]
        assert tid == exp["ticket_id"]


@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s["id"])
def test_intake_golden_routing_loose(scenario):
    msgs = scenario_messages(scenario)
    dept, tid = intake_routing_from_turn_loose(msgs)
    exp = scenario.get("expect_loose")
    if exp is None:
        assert dept is None and tid is None
    else:
        assert dept == exp["department"]
        assert tid == exp["ticket_id"]


def test_double_open_never_returns_first_ticket():
    """Documenta il comportamento: l'API risponde con un solo (dept, id) dall'ultimo tool valido."""
    scen = next(s for s in _scenarios() if s["id"] == "double_open_last_wins")
    msgs = scenario_messages(scen)
    d, t = intake_routing_from_turn(msgs)
    assert t != "1"
    assert t == "2"

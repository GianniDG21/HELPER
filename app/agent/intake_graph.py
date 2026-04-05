from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.intake_prompts import (
    INTAKE_PHASE_ACT,
    INTAKE_PHASE_LEARN,
    INTAKE_PHASE_MISSION,
    INTAKE_PHASE_SCAN,
    INTAKE_PHASE_THINK,
)
from app.agent.chat_model import build_chat_model
from app.agent.learn_context import messages_for_learn
from app.config import Settings
from app.tools.intake_tools import read_intake_tools, write_intake_tools


class IntakeState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _route_scan(state: IntakeState) -> Literal["scan_tools", "think"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "scan_tools"
    return "think"


def _route_act(state: IntakeState) -> Literal["act_tools", "learn"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act_tools"
    return "learn"


def build_intake_graph(
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
):
    llm = build_chat_model(settings)
    rt = read_intake_tools()
    wt = write_intake_tools()
    # Il backend valida le tool-call contro l elenco inviato: act_agent deve poter richiamare
    # anche i tool di lettura se il modello li ripropone (es. lookup_company_by_email).
    all_act_tools = rt + wt
    llm_scan = llm.bind_tools(rt)
    llm_act = llm.bind_tools(all_act_tools)

    async def mission_node(state: IntakeState) -> dict:
        msgs = [SystemMessage(content=INTAKE_PHASE_MISSION)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    async def scan_agent(state: IntakeState) -> dict:
        msgs = [SystemMessage(content=INTAKE_PHASE_SCAN)] + state["messages"]
        reply = await llm_scan.ainvoke(msgs)
        return {"messages": [reply]}

    async def think_node(state: IntakeState) -> dict:
        msgs = [SystemMessage(content=INTAKE_PHASE_THINK)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    async def act_agent(state: IntakeState) -> dict:
        msgs = [SystemMessage(content=INTAKE_PHASE_ACT)] + state["messages"]
        reply = await llm_act.ainvoke(msgs)
        return {"messages": [reply]}

    async def learn_node(state: IntakeState) -> dict:
        msgs = [SystemMessage(content=INTAKE_PHASE_LEARN)] + messages_for_learn(
            state["messages"]
        )
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    g = StateGraph(IntakeState)
    g.add_node("mission", mission_node)
    g.add_node("scan_agent", scan_agent)
    g.add_node("scan_tools", ToolNode(rt))
    g.add_node("think", think_node)
    g.add_node("act_agent", act_agent)
    g.add_node("act_tools", ToolNode(all_act_tools))
    g.add_node("learn", learn_node)

    g.set_entry_point("mission")
    g.add_edge("mission", "scan_agent")
    g.add_conditional_edges(
        "scan_agent",
        _route_scan,
        {"scan_tools": "scan_tools", "think": "think"},
    )
    g.add_edge("scan_tools", "scan_agent")
    g.add_edge("think", "act_agent")
    g.add_conditional_edges(
        "act_agent",
        _route_act,
        {"act_tools": "act_tools", "learn": "learn"},
    )
    g.add_edge("act_tools", "act_agent")
    g.add_edge("learn", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()

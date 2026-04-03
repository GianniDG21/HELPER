from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.assist_prompts import (
    ASSIST_PHASE_ACT,
    ASSIST_PHASE_LEARN,
    ASSIST_PHASE_MISSION,
    ASSIST_PHASE_SCAN,
    ASSIST_PHASE_THINK,
)
from app.config import Settings
from app.tools.ticket_tools import read_ticket_tools, write_ticket_tools


class AssistState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _route_scan(state: AssistState) -> Literal["scan_tools", "think"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "scan_tools"
    return "think"


def _route_act(state: AssistState) -> Literal["act_tools", "learn"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act_tools"
    return "learn"


def build_assist_graph(
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
):
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
    )
    rt = read_ticket_tools()
    wt = write_ticket_tools()
    all_act_tools = rt + wt
    llm_scan = llm.bind_tools(rt)
    llm_act = llm.bind_tools(all_act_tools)

    async def mission_node(state: AssistState) -> dict:
        hdr = [SystemMessage(content=ASSIST_PHASE_MISSION), state["messages"][-1]]
        reply = await llm.ainvoke(hdr)
        return {"messages": [reply]}

    async def scan_agent(state: AssistState) -> dict:
        msgs = [SystemMessage(content=ASSIST_PHASE_SCAN)] + state["messages"]
        reply = await llm_scan.ainvoke(msgs)
        return {"messages": [reply]}

    async def think_node(state: AssistState) -> dict:
        msgs = [SystemMessage(content=ASSIST_PHASE_THINK)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    async def act_agent(state: AssistState) -> dict:
        msgs = [SystemMessage(content=ASSIST_PHASE_ACT)] + state["messages"]
        reply = await llm_act.ainvoke(msgs)
        return {"messages": [reply]}

    async def learn_node(state: AssistState) -> dict:
        msgs = [SystemMessage(content=ASSIST_PHASE_LEARN)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    g = StateGraph(AssistState)
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

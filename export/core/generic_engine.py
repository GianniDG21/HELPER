from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class GenericAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@dataclass(frozen=True)
class AgentPhasePrompts:
    mission: str
    scan: str
    think: str
    act: str
    learn: str


def _route_scan(state: GenericAgentState) -> Literal["scan_tools", "think"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "scan_tools"
    return "think"


def _route_act(state: GenericAgentState) -> Literal["act_tools", "learn"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act_tools"
    return "learn"


def build_generic_agent_graph(
    *,
    llm: BaseChatModel,
    prompts: AgentPhasePrompts,
    read_tools: list[Any],
    write_tools: list[Any],
    checkpointer: BaseCheckpointSaver | None = None,
    learn_messages_adapter: Callable[[list[BaseMessage]], list[BaseMessage]] | None = None,
):
    all_act_tools = read_tools + write_tools
    llm_scan = llm.bind_tools(read_tools)
    llm_act = llm.bind_tools(all_act_tools)

    async def mission_node(state: GenericAgentState) -> dict:
        msgs = [SystemMessage(content=prompts.mission)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    async def scan_agent(state: GenericAgentState) -> dict:
        msgs = [SystemMessage(content=prompts.scan)] + state["messages"]
        reply = await llm_scan.ainvoke(msgs)
        return {"messages": [reply]}

    async def think_node(state: GenericAgentState) -> dict:
        msgs = [SystemMessage(content=prompts.think)] + state["messages"]
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    async def act_agent(state: GenericAgentState) -> dict:
        msgs = [SystemMessage(content=prompts.act)] + state["messages"]
        reply = await llm_act.ainvoke(msgs)
        return {"messages": [reply]}

    async def learn_node(state: GenericAgentState) -> dict:
        base = state["messages"]
        learn_ctx = learn_messages_adapter(base) if learn_messages_adapter else base
        msgs = [SystemMessage(content=prompts.learn)] + learn_ctx
        reply = await llm.ainvoke(msgs)
        return {"messages": [reply]}

    graph = StateGraph(GenericAgentState)
    graph.add_node("mission", mission_node)
    graph.add_node("scan_agent", scan_agent)
    graph.add_node("scan_tools", ToolNode(read_tools))
    graph.add_node("think", think_node)
    graph.add_node("act_agent", act_agent)
    graph.add_node("act_tools", ToolNode(all_act_tools))
    graph.add_node("learn", learn_node)

    graph.set_entry_point("mission")
    graph.add_edge("mission", "scan_agent")
    graph.add_conditional_edges(
        "scan_agent",
        _route_scan,
        {"scan_tools": "scan_tools", "think": "think"},
    )
    graph.add_edge("scan_tools", "scan_agent")
    graph.add_edge("think", "act_agent")
    graph.add_conditional_edges(
        "act_agent",
        _route_act,
        {"act_tools": "act_tools", "learn": "learn"},
    )
    graph.add_edge("act_tools", "act_agent")
    graph.add_edge("learn", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()

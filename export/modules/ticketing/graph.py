from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from core.generic_engine import AgentPhasePrompts, build_generic_agent_graph
from .prompts import PHASE_ACT, PHASE_LEARN, PHASE_MISSION, PHASE_SCAN, PHASE_THINK
from .tools import read_tools, write_tools


def build_ticketing_graph(
    *,
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
):
    return build_generic_agent_graph(
        llm=llm,
        prompts=AgentPhasePrompts(
            mission=PHASE_MISSION,
            scan=PHASE_SCAN,
            think=PHASE_THINK,
            act=PHASE_ACT,
            learn=PHASE_LEARN,
        ),
        read_tools=read_tools(),
        write_tools=write_tools(),
        checkpointer=checkpointer,
    )

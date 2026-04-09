from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from core.llm_factory import build_llm
from core.settings import get_settings
from modules.ticketing.graph import build_ticketing_graph

app = FastAPI(title="Export Modular Ticket Agent")


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None


class ChatOut(BaseModel):
    reply: str
    thread_id: str
    messages_count: int
    trace: list[dict[str, Any]]


@app.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "llm_provider": settings.llm_provider,
        "ticketing_backend": settings.ticketing_backend,
        "required_fields": settings.required_fields_list,
    }


@app.on_event("startup")
async def startup() -> None:
    settings = get_settings()
    llm = build_llm(settings)
    checkpointer = MemorySaver()
    app.state.graph = build_ticketing_graph(llm=llm, checkpointer=checkpointer)


@app.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn) -> ChatOut:
    graph = app.state.graph
    thread_id = payload.thread_id or str(uuid4())
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=payload.message)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    messages = result.get("messages", [])
    reply = ""
    if messages:
        last = messages[-1]
        reply = str(getattr(last, "content", "") or "")

    trace: list[dict[str, Any]] = []
    for msg in messages[-8:]:
        trace.append(
            {
                "type": msg.__class__.__name__,
                "content": str(getattr(msg, "content", "") or ""),
            }
        )
    return ChatOut(
        reply=reply,
        thread_id=thread_id,
        messages_count=len(messages),
        trace=trace,
    )

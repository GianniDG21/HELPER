from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from .settings import Settings


def build_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "groq":
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            max_retries=settings.groq_max_retries,
            timeout=settings.groq_request_timeout_seconds,
        )
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
    )

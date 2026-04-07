"""Istanziazione LLM condivisa (Groq cloud o Ollama locale)."""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings


def build_chat_model(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ModuleNotFoundError as e:
            raise ValueError(
                "Provider ollama richiesto ma dipendenza mancante: installa "
                "'langchain-ollama' (es. pip install -r requirements.txt)."
            ) from e
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url.rstrip("/"),
            temperature=0,
            num_ctx=settings.ollama_num_ctx,
        )
    try:
        from langchain_groq import ChatGroq
    except ModuleNotFoundError as e:
        raise ValueError(
            "Provider groq richiesto ma dipendenza mancante: installa "
            "'langchain-groq' (es. pip install -r requirements.txt)."
        ) from e
    key = (settings.groq_api_key or "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY obbligatorio quando LLM_PROVIDER=groq")
    return ChatGroq(
        model=settings.groq_model,
        api_key=key,
        temperature=0,
        max_retries=settings.groq_max_retries,
        timeout=settings.groq_request_timeout_seconds,
    )

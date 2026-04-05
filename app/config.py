from functools import lru_cache
from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TeamId = Literal["vendita", "acquisto", "manutenzione"]
LlmProvider = Literal["groq", "ollama"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # groq | ollama — default ollama per sviluppo locale (vedi .env.example)
    llm_provider: LlmProvider = "ollama"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    # Client Groq: più retry e timeout lunghi così i 429 con Retry-After (~20s+) non fanno fallire la richiesta.
    groq_max_retries: int = 8
    groq_request_timeout_seconds: float = 300.0

    ollama_base_url: str = "http://127.0.0.1:11434"
    # Testo + tool calling: qwen2.5 ha buon italiano; alternative: llama3.2, mistral, ecc.
    ollama_model: str = "qwen2.5:7b"
    ollama_num_ctx: int = 8192

    vendita_database_url: str
    acquisto_database_url: str
    manutenzione_database_url: str
    # Default = docker-compose servizio pratiche (porta 6436); sovrascrivibile con PRATICHE_DATABASE_URL
    pratiche_database_url: str = "postgresql://team:team@localhost:6436/pratiche"
    # 1 / true / yes: risposta POST /intake/chat include campo `debug` + log diagnostici
    debug_intake: bool = False
    # Se il modello non invoca route_and_open_ticket (o l’API non estrae tid), prova apertura lato server
    intake_fallback_open: bool = True

    @field_validator("debug_intake", mode="before")
    @classmethod
    def _coerce_debug_intake(cls, v: object) -> bool:
        if v is True or v is False:
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    @field_validator("intake_fallback_open", mode="before")
    @classmethod
    def _coerce_intake_fallback_open(cls, v: object) -> bool:
        if v is True or v is False:
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _norm_llm_provider(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "ollama"
        s = str(v).strip().lower()
        if s in ("groq", "ollama"):
            return s
        raise ValueError("LLM_PROVIDER deve essere groq o ollama")

    @model_validator(mode="after")
    def _require_groq_key_when_cloud(self) -> Self:
        if self.llm_provider == "groq":
            if not (self.groq_api_key or "").strip():
                raise ValueError(
                    "GROQ_API_KEY obbligatorio quando LLM_PROVIDER=groq "
                    "(oppure imposta LLM_PROVIDER=ollama e avvia Ollama)."
                )
        return self

    @property
    def db_urls_by_team(self) -> dict[str, str]:
        return {
            "vendita": self.vendita_database_url,
            "acquisto": self.acquisto_database_url,
            "manutenzione": self.manutenzione_database_url,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["groq", "ollama"]
TicketingBackend = Literal["stub", "zammad"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: LlmProvider = "ollama"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_max_retries: int = 8
    groq_request_timeout_seconds: float = 300.0

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_num_ctx: int = 8192

    ticketing_backend: TicketingBackend = "stub"
    required_fields: str = "name,email,subject,description"

    zammad_base_url: str = "http://127.0.0.1:8080"
    zammad_api_token: str | None = None
    zammad_customer: str = "customer@example.com"
    zammad_group: str = "Users"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value: object) -> str:
        if value is None:
            return "ollama"
        v = str(value).strip().lower()
        if not v:
            return "ollama"
        if v not in ("ollama", "groq"):
            raise ValueError("LLM_PROVIDER must be ollama or groq")
        return v

    @field_validator("ticketing_backend", mode="before")
    @classmethod
    def normalize_ticketing_backend(cls, value: object) -> str:
        if value is None:
            return "stub"
        v = str(value).strip().lower()
        if not v:
            return "stub"
        if v not in ("stub", "zammad"):
            raise ValueError("TICKETING_BACKEND must be stub or zammad")
        return v

    @property
    def required_fields_list(self) -> list[str]:
        fields = [part.strip() for part in self.required_fields.split(",")]
        return [field for field in fields if field]

    @model_validator(mode="after")
    def validate_dependencies(self) -> Self:
        if self.llm_provider == "groq" and not (self.groq_api_key or "").strip():
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        if self.ticketing_backend == "zammad":
            if not (self.zammad_api_token or "").strip():
                raise ValueError(
                    "ZAMMAD_API_TOKEN is required when TICKETING_BACKEND=zammad"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

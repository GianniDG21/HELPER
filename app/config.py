from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

TeamId = Literal["vendita", "acquisto", "manutenzione"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"

    vendita_database_url: str
    acquisto_database_url: str
    manutenzione_database_url: str

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

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver

from app.agent.assist_graph import build_assist_graph
from app.agent.intake_graph import build_intake_graph
from app.api.routes.assist import router as assist_router
from app.api.routes.departments import router as departments_router
from app.api.routes.health import router as health_router
from app.api.routes.intake import router as intake_router
from app.api.routes.intake import tickets_router
from app.api.routes.pratiche_registry import router as pratiche_registry_router
from app.config import get_settings
from app.db.registry import close_pools, init_pools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _path_is_public(path: str) -> bool:
    return (
        path == "/health"
        or path == "/"
        or path.startswith("/ui")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path in ("/openapi.json", "/favicon.ico")
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.db_available = False
    app.state.db_startup_error = None
    try:
        await init_pools(settings)
    except Exception as e:
        app.state.db_startup_error = str(e)
        log.exception(
            "Postgres non raggiungibile all'avvio: la UI su /ui e GET /health restano disponibili. "
            "Avvia i database con `docker compose up -d` e verifica le URL in .env "
            "(es. postgresql://team:team@localhost:6433/tickets e ...:6436/pratiche). Errore: %s",
            e,
        )
    else:
        app.state.db_available = True

    app.state.checkpointer = MemorySaver()
    app.state.llm_default_provider = settings.llm_provider
    app.state.intake_graphs = {}
    app.state.assist_graphs = {}
    app.state.available_llm_providers = []

    # Prova sempre il provider locale.
    settings_ollama = settings.model_copy(update={"llm_provider": "ollama"})
    try:
        app.state.intake_graphs["ollama"] = build_intake_graph(
            settings_ollama, checkpointer=app.state.checkpointer
        )
        app.state.assist_graphs["ollama"] = build_assist_graph(
            settings_ollama, checkpointer=app.state.checkpointer
        )
        app.state.available_llm_providers.append("ollama")
    except Exception as e:
        log.warning("Provider Ollama non disponibile all'avvio: %s", e)

    # Abilita il provider remoto solo se configurato (es. GROQ_API_KEY).
    try:
        settings_groq = settings.model_copy(update={"llm_provider": "groq"})
        app.state.intake_graphs["groq"] = build_intake_graph(
            settings_groq, checkpointer=app.state.checkpointer
        )
        app.state.assist_graphs["groq"] = build_assist_graph(
            settings_groq, checkpointer=app.state.checkpointer
        )
        app.state.available_llm_providers.append("groq")
    except Exception as e:
        log.warning("Provider Groq non disponibile all'avvio: %s", e)

    if not app.state.available_llm_providers:
        raise RuntimeError(
            "Nessun provider LLM disponibile: configura Ollama o GROQ_API_KEY."
        )

    # Fallback sicuro: se il default non e disponibile usa il primo disponibile.
    if app.state.llm_default_provider not in app.state.available_llm_providers:
        app.state.llm_default_provider = app.state.available_llm_providers[0]
    app.state.intake_graph = app.state.intake_graphs[app.state.llm_default_provider]
    app.state.assist_graph = app.state.assist_graphs[app.state.llm_default_provider]
    log.info(
        "Grafi pronti provider=%s disponibili=%s (checkpointer in-memory)",
        app.state.llm_default_provider,
        ",".join(app.state.available_llm_providers),
    )
    yield
    if getattr(app.state, "db_available", False):
        await close_pools()
        log.info("Pool DB chiusi")


app = FastAPI(title="Ticket Agent POC — intake + assist", lifespan=lifespan)


@app.middleware("http")
async def _db_required_for_api_routes(request: Request, call_next):
    if getattr(request.app.state, "db_available", False):
        return await call_next(request)
    path = request.url.path
    if _path_is_public(path):
        return await call_next(request)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database Postgres non disponibile. Avvia i container: docker compose up -d "
                "e controlla .env: URL tipo postgresql://team:team@localhost:6433/tickets "
                "(reparti 6433–6435) e postgresql://team:team@localhost:6436/pratiche."
            )
        },
    )


@app.middleware("http")
async def _api_key_if_configured(request: Request, call_next):
    """Registrato dopo il middleware DB così viene eseguito per primo sulla richiesta."""
    settings = get_settings()
    if not settings.api_key or _path_is_public(request.url.path):
        return await call_next(request)
    key = (request.headers.get("x-api-key") or "").strip()
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        key = auth[7:].strip()
    if key == settings.api_key:
        return await call_next(request)
    return JSONResponse(
        status_code=401,
        content={
            "detail": (
                "API key richiesta. Imposta HELPER_API_KEY sul server e invia "
                "l'header X-API-Key oppure Authorization: Bearer <valore>."
            )
        },
    )


app.include_router(health_router)
app.include_router(intake_router)
app.include_router(tickets_router)
app.include_router(assist_router)
app.include_router(pratiche_registry_router)
app.include_router(departments_router)

if STATIC_DIR.is_dir():
    app.mount(
        "/ui",
        StaticFiles(directory=str(STATIC_DIR), html=True),
        name="ui",
    )
else:
    log.error(
        "Cartella static non trovata (%s): la UI su /ui non è stata montata.",
        STATIC_DIR,
    )

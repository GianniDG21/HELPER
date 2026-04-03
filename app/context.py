"""Request-scoped team id (async-safe per task)."""
from contextvars import ContextVar

team_id_ctx: ContextVar[str | None] = ContextVar("team_id", default=None)


def get_team_id() -> str:
    tid = team_id_ctx.get()
    if not tid:
        raise RuntimeError("team_id non impostato nel contesto della richiesta")
    return tid


def set_team_id(team_id: str):
    return team_id_ctx.set(team_id)


def reset_team_id(token) -> None:
    team_id_ctx.reset(token)

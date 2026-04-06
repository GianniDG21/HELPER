from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    ok = bool(getattr(request.app.state, "db_available", False))
    body: dict = {"status": "ok" if ok else "degraded", "database": ok}
    if not ok and getattr(request.app.state, "db_startup_error", None):
        body["database_error"] = (request.app.state.db_startup_error or "")[:500]
    return body


@router.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/ui/", status_code=307)

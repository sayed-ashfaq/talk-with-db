import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import NL2SQLError
from app.core.logging import get_logger, setup_logging
from app.router.chat import router as chat_router
from app.router.connections import router as connections_router

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="NL2SQL")

# local dev frontend (Vite) — a regex, not a fixed port, because Vite silently moves to the next
# free port (5174, 5175, ...) if 5173 is already taken by another instance. Tighten this to a
# real origin allowlist before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(connections_router)

@app.exception_handler(NL2SQLError)
async def nl2sql_error_handler(request: Request, exc: NL2SQLError) -> JSONResponse:
    logger.error(str(exc), exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception in %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error — check server logs"})


def main():
    # exclude logs/ — without this, log writes inside the watched directory register as file
    # changes and get logged themselves, snowballing (see app/core/logging.py for the full story)
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True, reload_excludes=["logs/*"])


if __name__ == "__main__":
    main()

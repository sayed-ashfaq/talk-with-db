import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import NL2SQLError
from app.core.logging import get_logger, setup_logging
from app.router.chat import router as chat_router
from app.router.connection import router as connection_router

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="NL2SQL")
app.include_router(chat_router)
app.include_router(connection_router)


@app.exception_handler(NL2SQLError)
async def nl2sql_error_handler(request: Request, exc: NL2SQLError) -> JSONResponse:
    logger.error(str(exc))
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()

import uvicorn
from fastapi import FastAPI

from app.router.chat import router as chat_router

app = FastAPI(title="NL2SQL")
app.include_router(chat_router)


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()

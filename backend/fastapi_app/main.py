from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes.runs import router as runs_router
from .routes.events import router as events_router
from .routes.internal import router as internal_router
from .routes.approvals import router as approvals_router
from .routes.chaos import router as chaos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Durable Agentic Harness API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)
app.include_router(events_router)
app.include_router(internal_router)
app.include_router(approvals_router)
app.include_router(chaos_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}

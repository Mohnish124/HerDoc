from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.patients import router as patients_router
from app.api.reviews import router as reviews_router
from app.api.sync import router as sync_router
from app.api.visits import router as visits_router
from app.api.workers import router as workers_router
from app.config import get_settings
from app.db.session import check_database_connection

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    yield


app = FastAPI(title="HerDoc API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(visits_router)
app.include_router(sync_router)
app.include_router(dashboard_router)
app.include_router(reviews_router)
app.include_router(workers_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.guard.router import router as guard_router

app = FastAPI(title="Comply ML Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(guard_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "comply-ml", "version": "0.1.0"}


@app.get("/")
def root() -> dict:
    return {"service": "Comply ML Service", "endpoints": ["/guard/check", "/guard/status", "/health"]}

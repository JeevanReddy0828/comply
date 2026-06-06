from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal
from app.services.loader import load_catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        summary = load_catalog(db, settings.catalog_path)
        db.commit()
        print(f"[Comply] catalog loaded: {summary}")
    finally:
        db.close()
    yield


app = FastAPI(title="Comply API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "Comply API running", "version": "0.1.0"}

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

from app.routers import assessments as assessments_router  # noqa: E402
from app.routers import audit as audit_router  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402
from app.routers import evidence as evidence_router  # noqa: E402
from app.routers import systems as systems_router  # noqa: E402

app.include_router(auth_router.router)
app.include_router(audit_router.router)
app.include_router(systems_router.router)
app.include_router(evidence_router.router)
app.include_router(assessments_router.router)


@app.get("/")
def root():
    return {"status": "Comply API running", "version": "0.1.0"}

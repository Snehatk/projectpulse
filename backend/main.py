"""FastAPI application entry point."""

import sys
from pathlib import Path

# Allow imports from project root when running directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.routers import api, auth

app = FastAPI(
    title=settings.app_name,
    description="ProjectPulse AI — Cross-Functional Project Intelligence",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(api.router, prefix=settings.api_prefix)


@app.on_event("startup")
def on_startup():
    init_db()
    if settings.demo_mode:
        from backend.database import SessionLocal
        from backend.services.seed_service import seed_demo_data

        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "phase": 1,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }

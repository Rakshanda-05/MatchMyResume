"""
WhatsApp Resume Evaluation Bot - Main Application Entry Point
-------------------------------------------------------------
FastAPI application that powers the WhatsApp bot via Twilio webhooks.
Start here: uvicorn main:app --reload
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.routes import whatsapp, health
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    # Ensure output directory exists for generated resumes
    os.makedirs("output", exist_ok=True)
    logger.info("WhatsApp Resume Bot started successfully.")
    yield
    logger.info("WhatsApp Resume Bot shutting down.")


# ─── App Initialization ───────────────────────────────────────────────────────
app = FastAPI(
    title="WhatsApp Resume Evaluation Bot",
    description="AI-powered resume evaluation and improvement via WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve generated resume files for download
app.mount("/output", StaticFiles(directory="output"), name="output")

# ─── Register Routes ──────────────────────────────────────────────────────────
app.include_router(whatsapp.router, prefix="/webhook", tags=["WhatsApp"])
app.include_router(health.router, prefix="/health", tags=["Health"])


@app.get("/")
async def root():
    return {"status": "online", "service": "WhatsApp Resume Evaluation Bot"}

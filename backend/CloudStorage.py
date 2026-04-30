"""
Main entry point.
Run with:  uvicorn CloudStorage:app --reload --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
import authorization
import storage

@asynccontextmanager
async def lifespan(app):
    storage._ensure_bucket()
    yield

authorization.app.router.lifespan_context = lifespan
app = authorization.app
app.include_router(storage.router)
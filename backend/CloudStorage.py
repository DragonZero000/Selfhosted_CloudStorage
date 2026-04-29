"""
Main entry point.
Run with:  uvicorn CloudStorage:app --reload --host 0.0.0.0 --port 8000
"""
from authorization import app
import storage

app.include_router(storage.router)
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.config.logging_config import setup_logging
from src.database.connection import init_db
from src.backend.routers import health, pdfs, study

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting up TestYourself AI Backend Server...")

    # Ensure upload directory exists
    settings.upload_path

    # Initialize database
    await init_db()

    yield

    logger.info("Shutting down TestYourself AI Backend Server...")


app = FastAPI(
    title="TestYourself AI - PDF Study Backend",
    description="Asynchronous REST API supporting PDF text extraction, FAISS vector indexing, and Gemini AI operations.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(pdfs.router)
app.include_router(study.router)


# Dummy endpoints
@app.get("/api/combined-data/")
async def dummy_combined_data():
    return {
        "status": "ignored",
        "message": "Dummy endpoint silencing logs"
    }


@app.websocket("/ws/combined-data/")
async def dummy_websocket_combined_data(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass


@app.get("/")
async def root():
    return {
        "message": "Welcome to TestYourself AI API!",
        "documentation": "/docs"
    }


if __name__ == "__main__":
    import uvicorn

    # Railway provides PORT automatically.
    # Local development falls back to BACKEND_PORT.
    port = int(os.getenv("PORT", settings.BACKEND_PORT))

    logger.info(f"Running server on 0.0.0.0:{port}")

    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=(settings.ENV.lower() == "development"),
        log_level="info",
    )
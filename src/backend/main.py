import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.config.logging_config import setup_logging
from src.database.connection import init_db
from src.backend.routers import health, pdfs, study

# Configure logging before booting the server
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to bootstrap applications (e.g., database tables creation)."""
    logger.info("Starting up TestYourself AI Backend Server...")
    
    # Ensure upload directory exists
    settings.upload_path
    
    # Initialize DB
    await init_db()
    
    yield
    logger.info("Shutting down TestYourself AI Backend Server...")

app = FastAPI(
    title="TestYourself AI - PDF Study Backend",
    description="Asynchronous REST API supporting PDF text extraction, FAISS vector indexing, and Gemini AI operations.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for potential frontend cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import WebSocket, WebSocketDisconnect

# Include API Routers
app.include_router(health.router)
app.include_router(pdfs.router)
app.include_router(study.router)

# Dummy endpoints to silence console spam from other localhost projects (e.g. DMS)
@app.get("/api/combined-data/")
async def dummy_combined_data():
    return {"status": "ignored", "message": "Dummy endpoint silencing logs"}

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
    """Welcome index pointing to the interactive Swagger docs."""
    return {
        "message": "Welcome to TestYourself AI API!",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Running server on {settings.BACKEND_HOST}:{settings.BACKEND_PORT}")
    uvicorn.run(
        "src.backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=(settings.ENV == "development")
    )

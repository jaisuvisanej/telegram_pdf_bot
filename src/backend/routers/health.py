import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health", tags=["Health"])
async def health_check(session: AsyncSession = Depends(get_db)):
    """Health check endpoint to verify backend operational readiness and DB connectivity."""
    db_status = "unhealthy"
    try:
        # Run a simple query to verify DB connection
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "environment": "development"  # or read from settings
    }

import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy models
Base = declarative_base()

# Configure engine arguments based on DB dialect (SQLite vs PostgreSQL)
engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite requires checking same thread flags to allow multithreading in dev
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create asynchronous engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for verbose SQL query logging
    **engine_kwargs
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db() -> None:
    """Initializes the database tables."""
    logger.info("Initializing database tables...")
    try:
        async with engine.begin() as conn:
            # Import models to register them on Base
            from src.database.models import User, UploadedPDF, ChatHistory, GeneratedQuestion, GeneratedSummary, UserSetting
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to yield database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

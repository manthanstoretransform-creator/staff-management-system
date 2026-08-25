import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

# Load environment variables with override enabled to support uvicorn auto-reload of configs
load_dotenv(override=True)

# Create engine lazily to avoid import-time failures in serverless
_engine = None
_SessionLocal = None

def get_database_url():
    """Get the appropriate database URL based on environment"""
    from app.core.config import settings
    
    # Try production URL first, then fallback to dev URL, regardless of the ENV setting 
    # to prevent crashes when ENV is misconfigured in Vercel
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URL or os.getenv("DATABASE_URL_DEV") or settings.DATABASE_URL_DEV
    
    if not url:
        error_msg = f"Database URL not configured. Set DATABASE_URL (prod) or DATABASE_URL_DEV (dev) environment variable."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return url

def get_engine():
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        try:
            db_url = get_database_url()
            _engine = create_engine(
                db_url, 
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections every hour in serverless
                pool_size=5,  # Smaller pool for serverless
                max_overflow=10
            )
            from app.core.config import settings
            logger.info(f"Database engine created for environment: {settings.ENV}")
        except Exception as e:
            logger.error(f"Failed to create database engine: {str(e)}")
            raise
    return _engine

def get_session_local():
    """Get or create the sessionmaker"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal

class Base(DeclarativeBase):
    pass

def get_db():
    """Database dependency for FastAPI"""
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
    except Exception as e:
        logger.error(f"Failed to initialize database session: {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
        
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

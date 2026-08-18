import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load environment variables with override enabled to support uvicorn auto-reload of configs
load_dotenv(override=True)

# Always point to the development database URL as requested
DATABASE_URL = os.getenv("DATABASE_URL_DEV")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL_DEV environment variable is not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

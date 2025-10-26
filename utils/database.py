from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# Get database configuration from centralized settings
DATABASE_URL = settings.get_database_url()

# Create SQLAlchemy engine with configuration from settings
engine = create_engine(
    DATABASE_URL,
    echo=settings.database.echo,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=settings.database.pool_recycle,  # Use setting
    pool_timeout=settings.database.pool_timeout,  # Use setting
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency to get database session
def get_db():
    """Get database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

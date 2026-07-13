from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# Get database configuration from centralized settings
DATABASE_URL = settings.get_database_url()


def _connect_args_for_url(url: str, statement_timeout_seconds: int) -> dict:
    """Dialect-specific connect args for per-statement query timeouts."""
    timeout_ms = max(1, int(statement_timeout_seconds) * 1000)
    lower = url.lower()
    if lower.startswith("mysql") or "+pymysql" in lower:
        # MySQL 5.7.8+ / 8.x: MAX_EXECUTION_TIME is milliseconds (SELECT only).
        return {"init_command": f"SET SESSION MAX_EXECUTION_TIME={timeout_ms}"}
    if lower.startswith("postgresql") or "+psycopg" in lower or "postgres" in lower.split(":", 1)[0]:
        return {"options": f"-c statement_timeout={timeout_ms}"}
    return {}


_connect_args = _connect_args_for_url(
    DATABASE_URL, settings.database.statement_timeout_seconds
)

# Create SQLAlchemy engine with configuration from settings
engine = create_engine(
    DATABASE_URL,
    echo=settings.database.echo,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=settings.database.pool_recycle,  # Use setting
    pool_timeout=settings.database.pool_timeout,  # Use setting
    connect_args=_connect_args,
)


@event.listens_for(engine, "connect")
def _set_sqlite_busy_timeout(dbapi_connection, connection_record) -> None:
    """SQLite (tests/local) — busy_timeout in milliseconds."""
    if "sqlite" not in DATABASE_URL.lower():
        return
    timeout_ms = max(1, int(settings.database.statement_timeout_seconds) * 1000)
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA busy_timeout={timeout_ms}")
    finally:
        cursor.close()


# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency to get database session
def get_db():
    """Get database session dependency.

    Services own commit on success. On uncaught request errors, roll back so
    dirty state is not returned to the pool. See docs/TRANSACTION_BOUNDARIES.md.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

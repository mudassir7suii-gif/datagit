from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from datagit.config import settings
from datagit.storage.models import Base

# Setup engine with appropriate connection args for SQLite if used
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """Initializes tables in database and FTS5 full-text index."""
    try:
        Base.metadata.create_all(bind=engine)
        if is_sqlite:
            with engine.begin() as conn:
                conn.exec_driver_sql("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS repositories_fts USING fts5(
                        id UNINDEXED,
                        full_name,
                        name,
                        description,
                        tokenize = 'porter unicode61'
                    );
                """)
                try:
                    count_fts = conn.exec_driver_sql("SELECT count(*) FROM repositories_fts").scalar() or 0
                    if count_fts == 0:
                        conn.exec_driver_sql("""
                            INSERT INTO repositories_fts (id, full_name, name, description)
                            SELECT id, full_name, name, coalesce(description, '') FROM repositories;
                        """)
                except Exception:
                    pass
    except Exception as e:
        import warnings
        warnings.warn(f"Database initialization notice: {e}", UserWarning)

def get_db() -> Generator[Session, None, None]:
    """Dependency injector for FastAPI and services."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=300 if not is_sqlite else -1
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
                try:
                    cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
                    if cols and "failed_login_attempts" not in cols:
                        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
                    if cols and "locked_until" not in cols:
                        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN locked_until DATETIME")
                    if cols and "plan" not in cols:
                        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN plan VARCHAR(50) DEFAULT 'free'")

                    # Add workspace_id columns if missing
                    for table in ("repositories", "crawl_jobs", "api_keys"):
                        try:
                            t_cols = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]
                            if t_cols and "workspace_id" not in t_cols:
                                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL")
                        except Exception:
                            pass

                    # Add github_app_installation_id to workspaces if missing
                    try:
                        ws_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(workspaces)").fetchall()]
                        if ws_cols and "github_app_installation_id" not in ws_cols:
                            conn.exec_driver_sql("ALTER TABLE workspaces ADD COLUMN github_app_installation_id VARCHAR(100)")
                    except Exception:
                        pass

                    # Add ai_summary to repositories if missing
                    try:
                        repo_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(repositories)").fetchall()]
                        if repo_cols and "ai_summary" not in repo_cols:
                            conn.exec_driver_sql("ALTER TABLE repositories ADD COLUMN ai_summary TEXT")
                    except Exception:
                        pass
                except Exception:
                    pass

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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

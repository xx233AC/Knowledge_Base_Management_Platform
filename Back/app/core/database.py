from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_database(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    else:
        engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                               connect_args={"connect_timeout": 5})
    return engine, sessionmaker(engine, expire_on_commit=False)

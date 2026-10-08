"""Datenbank-Zugriffsschicht.

SQLite als Standard-Engine (ADR-0002), WAL-Modus fuer bessere Nebenlaeufigkeit
bei grossen Bibliotheken (§57 Performance), Fremdschluessel-Pruefung aktiv.
Zugriff ausschliesslich ueber diese Schicht - kein anderes Modul spricht
SQLAlchemy direkt an, damit ein Austausch (z.B. PostgreSQL fuer sehr grosse
Bibliotheken, Prinzip #13) spaeter moeglich bleibt, ohne die Anwendungsschicht
umzuschreiben.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from genesis_core.db import models  # noqa: F401  (registriert alle Tabellen an Base)
from genesis_core.db.base import Base


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def make_engine(database_path: str | Path) -> Engine:
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", future=True)


def init_db(database_path: str | Path) -> Engine:
    """Erstellt alle Tabellen, falls noch nicht vorhanden.

    Fuer produktive Schema-Aenderungen wird spaeter Alembic genutzt
    (Prinzip #7/#20: niemals destruktiv). create_all() ist fuer den
    Erststart/Tests ausreichend und idempotent.
    """
    engine = make_engine(database_path)
    Base.metadata.create_all(engine)
    return engine


class Database:
    """Kleiner Wrapper, der Engine + Session-Factory buendelt."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.engine = init_db(self.database_path)
        self._session_factory = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

"""Database utilities for the citation tracker."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_path: str, create_tables: bool = True):
        """
        Initialize the database manager.

        Parameters
        ----------
        database_path : str
            Path to the SQLite database file.
        create_tables : bool, optional
            Whether to create tables if they don't exist.
        """
        self.database_path = database_path
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.Session = sessionmaker(bind=self.engine)

        if create_tables:
            from .models import Base
            Base.metadata.create_all(self.engine)
            self._migrate()

    def _migrate(self) -> None:
        """Apply any schema migrations needed for existing databases."""
        with self.engine.connect() as conn:
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(publications)"))}
            if "added_via_deep" not in existing:
                conn.execute(text("ALTER TABLE publications ADD COLUMN added_via_deep BOOLEAN DEFAULT 0"))
                conn.commit()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

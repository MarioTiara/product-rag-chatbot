import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.configs.config import get_settings

# PROJECT_ROOT = Path(__file__).resolve().parents[2]


setting=get_settings() 


class DatabaseConnection:
    def __init__(self, db_path: Path = setting.database_path):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
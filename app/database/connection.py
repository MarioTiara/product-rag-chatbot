from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.core.configs.config import get_settings

settings = get_settings()


class DatabaseConnection:

    def __init__(self, database_url: str = settings.database_url):
        self.database_url = database_url

    @contextmanager
    def connect(self) -> Generator[Connection, None, None]:

        connection = psycopg.connect(
            self.database_url,
            row_factory=dict_row
        )

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()